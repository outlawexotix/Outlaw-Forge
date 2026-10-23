#include "GeometryCommandClient.h"

#include "SlicePlaneMapper.h"

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QHttpMultiPart>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QSaveFile>
#include <QStandardPaths>
#include <QUuid>

#include <cmath>

namespace {
QString responseMessage(QNetworkReply *reply, const QByteArray &body)
{
    const QJsonDocument document = QJsonDocument::fromJson(body);
    if (document.isObject()) {
        const QJsonObject object = document.object();
        const QString detail = object.value(QStringLiteral("detail")).toString();
        if (!detail.isEmpty())
            return detail;
        const QString message = object.value(QStringLiteral("message")).toString();
        if (!message.isEmpty())
            return message;
    }
    if (reply && !reply->errorString().isEmpty())
        return reply->errorString();
    return QStringLiteral("The geometry service returned an unreadable response.");
}

bool isSuccessful(QNetworkReply *reply)
{
    const int status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
    return reply->error() == QNetworkReply::NoError && status >= 200 && status < 300;
}

QString extensionFor(const QString &filename)
{
    return QFileInfo(filename).suffix().toLower();
}

bool jsonNumber(const QJsonValue &value, double *number)
{
    if (!value.isDouble())
        return false;
    const double result = value.toDouble();
    if (!std::isfinite(result))
        return false;
    *number = result;
    return true;
}
}

struct GeometryCommandClient::PendingSlice {
    QString requestId;
    QString topModelId;
    QString topName;
    bool topWatertight = false;
    QString bottomModelId;
    QString bottomName;
    bool bottomWatertight = false;
    QString message;
    QString topPath;
    QString bottomPath;
    double cutAreaCm2 = 0.0;
    QSaveFile topFile;
    QSaveFile bottomFile;
    QPointer<QNetworkReply> topReply;
    QPointer<QNetworkReply> bottomReply;
    bool topFinished = false;
    bool bottomFinished = false;
    QString error;

    PendingSlice(const QString &outputDir, const QString &extension)
        : topPath(QDir(outputDir).filePath(QUuid::createUuid().toString(QUuid::WithoutBraces) + "_top." + extension)),
          bottomPath(QDir(outputDir).filePath(QUuid::createUuid().toString(QUuid::WithoutBraces) + "_bottom." + extension)),
          topFile(topPath), bottomFile(bottomPath)
    {
    }
};

struct GeometryCommandClient::PendingAutoOrient {
    QString requestId;
    QString modelId;
    QString filename;
    QString outputPath;
    QVector3D optimalRotationDeg;
    double originalOverhangCm2 = 0.0;
    double optimizedOverhangCm2 = 0.0;
    double reductionPercentage = 0.0;
    QString message;
    QString writeError;
    QByteArray errorBody;
    QSharedPointer<QSaveFile> file;
    QPointer<QNetworkReply> reply;
    bool downloadActive = false;
    qint64 bytesWritten = 0;
};

struct GeometryCommandClient::PendingRepair {
    QString requestId;
    QString modelId;
    QString filename;
    QString outputPath;
    QVariantMap report;
    QString message;
    QString writeError;
    QByteArray errorBody;
    QSharedPointer<QSaveFile> file;
    QPointer<QNetworkReply> reply;
    bool downloadActive = false;
    qint64 bytesWritten = 0;
};

GeometryCommandClient::GeometryCommandClient(QObject *parent)
    : QObject(parent),
      m_apiBaseUrl(QUrl(qEnvironmentVariable("OUTLAW_FORGE_API_URL", "http://127.0.0.1:8000"))),
      m_outputDirectory(QDir(QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation))
                            .filePath(QStringLiteral("derived-slices"))),
      m_autoOrientOutputDirectory(QDir(QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation))
                                      .filePath(QStringLiteral("derived-geometry"))),
      m_repairOutputDirectory(QDir(QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation))
                                  .filePath(QStringLiteral("derived-repairs")))
{
}

void GeometryCommandClient::setApiBaseUrl(const QUrl &url)
{
    if (url == m_apiBaseUrl)
        return;
    m_apiBaseUrl = url;
    emit apiBaseUrlChanged();
}

void GeometryCommandClient::setOutputDirectory(const QString &path)
{
    m_outputDirectory = path;
    m_autoOrientOutputDirectory = QDir(path).filePath(QStringLiteral("derived-geometry"));
    m_repairOutputDirectory = QDir(path).filePath(QStringLiteral("derived-repairs"));
}

QUrl GeometryCommandClient::apiUrl(const QString &path) const
{
    QUrl url = m_apiBaseUrl;
    QString basePath = url.path();
    while (basePath.endsWith(QLatin1Char('/')))
        basePath.chop(1);
    url.setPath(basePath + path);
    return url;
}

void GeometryCommandClient::registerSource(const QUrl &sourceFile, const QString &filename)
{
    const QString extension = extensionFor(filename);
    if (!sourceFile.isLocalFile() || (extension != QStringLiteral("stl") && extension != QStringLiteral("obj"))) {
        emit sourceRegistrationFailed(sourceFile,
                                      QStringLiteral("Service-backed slicing currently supports local STL and OBJ files."));
        return;
    }

    const QString localPath = sourceFile.toLocalFile();
    if (!QFileInfo::exists(localPath)) {
        emit sourceRegistrationFailed(sourceFile, QStringLiteral("The selected source file could not be found."));
        return;
    }

    m_pendingSources.enqueue({sourceFile, QFileInfo(filename).fileName()});
    if (m_projectId.isEmpty() && !m_projectRequestActive)
        createProject();
    else if (m_projectId.isEmpty())
        return;
    else
        uploadQueuedSources();
}

void GeometryCommandClient::createProject()
{
    m_projectRequestActive = true;
    QNetworkRequest request(apiUrl(QStringLiteral("/api/v1/projects")));
    request.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
    const QJsonObject payload{
        {QStringLiteral("name"), QStringLiteral("Outlaw Forge Native Session")},
        {QStringLiteral("description"), QStringLiteral("Project created by the native viewport")},
        {QStringLiteral("project_type"), QStringLiteral("Other")},
    };
    QNetworkReply *reply = m_network.post(request, QJsonDocument(payload).toJson(QJsonDocument::Compact));
    connect(reply, &QNetworkReply::finished, this, [this, reply] {
        const QByteArray body = reply->readAll();
        m_projectRequestActive = false;
        const QJsonDocument document = QJsonDocument::fromJson(body);
        const QString id = document.isObject() ? document.object().value(QStringLiteral("id")).toString() : QString();
        if (!isSuccessful(reply) || id.isEmpty()) {
            const QString message = responseMessage(reply, body);
            while (!m_pendingSources.isEmpty())
                emit sourceRegistrationFailed(m_pendingSources.dequeue().sourceUrl, message);
            reply->deleteLater();
            return;
        }
        m_projectId = id;
        reply->deleteLater();
        uploadQueuedSources();
    });
}

void GeometryCommandClient::uploadQueuedSources()
{
    while (!m_pendingSources.isEmpty())
        uploadSource(m_pendingSources.dequeue());
}

void GeometryCommandClient::uploadSource(const PendingSource &source)
{
    const QString localPath = source.sourceUrl.toLocalFile();
    auto *file = new QFile(localPath);
    if (!file->open(QIODevice::ReadOnly)) {
        emit sourceRegistrationFailed(source.sourceUrl, QStringLiteral("The source file could not be opened for upload."));
        delete file;
        return;
    }

    auto *multipart = new QHttpMultiPart(QHttpMultiPart::FormDataType);
    QHttpPart part;
    QString safeFilename = source.filename;
    safeFilename.replace(QLatin1Char('"'), QLatin1Char('_'));
    part.setHeader(QNetworkRequest::ContentDispositionHeader,
                   QStringLiteral("form-data; name=\"file\"; filename=\"%1\"").arg(safeFilename));
    part.setHeader(QNetworkRequest::ContentTypeHeader,
                   extensionFor(safeFilename) == QStringLiteral("obj")
                       ? QStringLiteral("model/obj") : QStringLiteral("model/stl"));
    part.setBodyDevice(file);
    file->setParent(multipart);
    multipart->append(part);

    QNetworkRequest request(apiUrl(QStringLiteral("/api/v1/projects/%1/models/import").arg(m_projectId)));
    request.setHeader(QNetworkRequest::ContentTypeHeader,
                      QStringLiteral("multipart/form-data; boundary=%1").arg(QString::fromLatin1(multipart->boundary())));
    QNetworkReply *reply = m_network.post(request, multipart);
    multipart->setParent(reply);
    connect(reply, &QNetworkReply::finished, this, [this, reply, source] {
        const QByteArray body = reply->readAll();
        const QJsonDocument document = QJsonDocument::fromJson(body);
        const QString modelId = document.isObject()
            ? document.object().value(QStringLiteral("id")).toString() : QString();
        if (!isSuccessful(reply) || modelId.isEmpty())
            emit sourceRegistrationFailed(source.sourceUrl, responseMessage(reply, body));
        else
            emit sourceRegistered(source.sourceUrl, m_projectId, modelId);
        reply->deleteLater();
    });
}

void GeometryCommandClient::sliceModel(const QString &requestId, const QString &modelId,
                                    const QVector3D &originMm, const QVector3D &normal,
                                    bool keepPositive, const QMatrix4x4 &localToWorld)
{
    if (m_projectId.isEmpty() || modelId.isEmpty()) {
        emit sliceFailed(requestId, QStringLiteral("This mesh is not registered with the geometry service."), {}, {});
        return;
    }

    const QVector3D requestedNormal = keepPositive ? normal : -normal;
    QVector3D localOrigin;
    QVector3D localNormal;
    QString mappingError;
    if (!SlicePlaneMapper::mapWorldPlaneToLocal(localToWorld, originMm, requestedNormal,
                                                &localOrigin, &localNormal, &mappingError)) {
        emit sliceFailed(requestId, mappingError, {}, {});
        return;
    }

    const QJsonObject payload{
        {QStringLiteral("plane_origin"), QJsonArray{localOrigin.x(), localOrigin.y(), localOrigin.z()}},
        {QStringLiteral("plane_normal"), QJsonArray{localNormal.x(), localNormal.y(), localNormal.z()}},
        {QStringLiteral("cap_faces"), true},
        {QStringLiteral("create_pegs"), false},
    };
    QNetworkRequest request(apiUrl(QStringLiteral("/api/v1/projects/%1/models/%2/slice")
                                       .arg(QString::fromLatin1(QUrl::toPercentEncoding(m_projectId)),
                                            QString::fromLatin1(QUrl::toPercentEncoding(modelId)))));
    request.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
    QNetworkReply *reply = m_network.post(request, QJsonDocument(payload).toJson(QJsonDocument::Compact));
    connect(reply, &QNetworkReply::finished, this, [this, reply, requestId] {
        const QByteArray body = reply->readAll();
        if (!isSuccessful(reply)) {
            emit sliceFailed(requestId, responseMessage(reply, body), {}, {});
            reply->deleteLater();
            return;
        }
        const QJsonDocument document = QJsonDocument::fromJson(body);
        if (!document.isObject()) {
            emit sliceFailed(requestId, QStringLiteral("The geometry service returned invalid slice JSON."), {}, {});
            reply->deleteLater();
            return;
        }

        const QJsonObject result = document.object();
        const QJsonObject top = result.value(QStringLiteral("top_model")).toObject();
        const QJsonObject bottom = result.value(QStringLiteral("bottom_model")).toObject();
        const QString topId = top.value(QStringLiteral("id")).toString();
        const QString bottomId = bottom.value(QStringLiteral("id")).toString();
        const QString extension = top.value(QStringLiteral("file_format")).toString().toLower();
        const QString bottomExtension = bottom.value(QStringLiteral("file_format")).toString().toLower();
        if (topId.isEmpty() || bottomId.isEmpty() || extension != bottomExtension
            || (extension != QStringLiteral("stl") && extension != QStringLiteral("obj"))) {
            emit sliceFailed(requestId, QStringLiteral("The geometry service returned incomplete or unsupported slice metadata."),
                             topId, bottomId);
            reply->deleteLater();
            return;
        }

        if (!QDir().mkpath(m_outputDirectory)) {
            emit sliceFailed(requestId, QStringLiteral("The local derived-mesh folder could not be created."), topId, bottomId);
            reply->deleteLater();
            return;
        }
        auto pending = QSharedPointer<PendingSlice>::create(m_outputDirectory, extension);
        pending->requestId = requestId;
        pending->topModelId = topId;
        pending->bottomModelId = bottomId;
        pending->topName = top.value(QStringLiteral("filename")).toString(QStringLiteral("slice_top.%1").arg(extension));
        pending->bottomName = bottom.value(QStringLiteral("filename")).toString(QStringLiteral("slice_bottom.%1").arg(extension));
        pending->topWatertight = top.value(QStringLiteral("is_watertight")).toBool();
        pending->bottomWatertight = bottom.value(QStringLiteral("is_watertight")).toBool();
        pending->message = result.value(QStringLiteral("message")).toString();
        pending->cutAreaCm2 = result.value(QStringLiteral("cut_area_cm2")).toDouble();
        if (!pending->topFile.open(QIODevice::WriteOnly) || !pending->bottomFile.open(QIODevice::WriteOnly)) {
            pending->topFile.cancelWriting();
            pending->bottomFile.cancelWriting();
            emit sliceFailed(requestId, QStringLiteral("The local derived-mesh files could not be opened."), topId, bottomId);
            reply->deleteLater();
            return;
        }

        reply->deleteLater();
        const QString encodedProject = QString::fromLatin1(QUrl::toPercentEncoding(m_projectId));
        pending->topReply = m_network.get(QNetworkRequest(apiUrl(QStringLiteral("/api/v1/projects/%1/models/%2/file")
            .arg(encodedProject, QString::fromLatin1(QUrl::toPercentEncoding(topId))))));
        pending->bottomReply = m_network.get(QNetworkRequest(apiUrl(QStringLiteral("/api/v1/projects/%1/models/%2/file")
            .arg(encodedProject, QString::fromLatin1(QUrl::toPercentEncoding(bottomId))))));
        for (const auto pair : {qMakePair(pending->topReply.data(), true), qMakePair(pending->bottomReply.data(), false)}) {
            QNetworkReply *download = pair.first;
            const bool isTop = pair.second;
            connect(download, &QIODevice::readyRead, this, [pending, download, isTop] {
                QSaveFile &file = isTop ? pending->topFile : pending->bottomFile;
                const QByteArray bytes = download->readAll();
                if (file.write(bytes) != bytes.size() && pending->error.isEmpty())
                    pending->error = QStringLiteral("Writing a downloaded slice mesh to disk failed.");
            });
            connect(download, &QNetworkReply::finished, this, [this, pending, isTop] {
                finishSliceDownload(pending, isTop);
            });
        }
    });
}

void GeometryCommandClient::autoOrientModel(const QString &requestId, const QString &modelId)
{
    if (m_projectId.isEmpty() || modelId.isEmpty()) {
        emit autoOrientFailed(requestId, QStringLiteral("This mesh is not registered with the geometry service."));
        return;
    }

    const QString encodedProject = QString::fromLatin1(QUrl::toPercentEncoding(m_projectId));
    const QString encodedModel = QString::fromLatin1(QUrl::toPercentEncoding(modelId));
    QNetworkRequest request(apiUrl(QStringLiteral("/api/v1/projects/%1/models/%2/auto_orient")
                                       .arg(encodedProject, encodedModel)));
    request.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
    QNetworkReply *reply = m_network.post(request, QByteArrayLiteral("{}"));
    connect(reply, &QNetworkReply::finished, this, [this, reply, requestId, modelId] {
        const QByteArray body = reply->readAll();
        if (!isSuccessful(reply)) {
            emit autoOrientFailed(requestId, responseMessage(reply, body));
            reply->deleteLater();
            return;
        }

        const QJsonDocument document = QJsonDocument::fromJson(body);
        if (!document.isObject()) {
            emit autoOrientFailed(requestId, QStringLiteral("The geometry service returned invalid auto-orient JSON."));
            reply->deleteLater();
            return;
        }

        const QJsonObject result = document.object();
        const QJsonObject oriented = result.value(QStringLiteral("oriented_model")).toObject();
        const QString returnedModelId = oriented.value(QStringLiteral("id")).toString();
        const QString filename = QFileInfo(oriented.value(QStringLiteral("filename")).toString()).fileName();
        const QString extension = oriented.value(QStringLiteral("file_format")).toString().toLower();
        const QJsonArray rotation = result.value(QStringLiteral("optimal_rotation_deg")).toArray();
        double rx = 0.0;
        double ry = 0.0;
        double rz = 0.0;
        double originalArea = 0.0;
        double optimizedArea = 0.0;
        double reduction = 0.0;
        const bool metricsValid = rotation.size() == 3
            && jsonNumber(rotation[0], &rx) && jsonNumber(rotation[1], &ry) && jsonNumber(rotation[2], &rz)
            && jsonNumber(result.value(QStringLiteral("original_overhang_area_cm2")), &originalArea)
            && jsonNumber(result.value(QStringLiteral("optimized_overhang_area_cm2")), &optimizedArea)
            && jsonNumber(result.value(QStringLiteral("reduction_percentage")), &reduction);
        const QString message = result.value(QStringLiteral("message")).toString();
        if (returnedModelId != modelId || filename.isEmpty()
            || (extension != QStringLiteral("stl") && extension != QStringLiteral("obj"))
            || extensionFor(filename) != extension || !metricsValid || message.isEmpty()) {
            emit autoOrientFailed(requestId,
                                  QStringLiteral("The geometry service returned incomplete or unsupported auto-orient metadata."));
            reply->deleteLater();
            return;
        }

        auto pending = QSharedPointer<PendingAutoOrient>::create();
        pending->requestId = requestId;
        pending->modelId = modelId;
        pending->filename = filename;
        pending->outputPath = QDir(m_autoOrientOutputDirectory).filePath(
            QUuid::createUuid().toString(QUuid::WithoutBraces) + QLatin1Char('_') + filename);
        pending->optimalRotationDeg = QVector3D(static_cast<float>(rx), static_cast<float>(ry), static_cast<float>(rz));
        pending->originalOverhangCm2 = originalArea;
        pending->optimizedOverhangCm2 = optimizedArea;
        pending->reductionPercentage = reduction;
        pending->message = message;
        reply->deleteLater();
        startAutoOrientDownload(pending);
    });
}

void GeometryCommandClient::retryAutoOrientDownload(const QString &requestId)
{
    const auto pending = m_pendingAutoOrientDownloads.value(requestId);
    if (!pending) {
        emit autoOrientFailed(requestId, QStringLiteral("There is no persisted auto-orient result available to retry."));
        return;
    }
    if (!pending->downloadActive)
        startAutoOrientDownload(pending);
}

void GeometryCommandClient::startAutoOrientDownload(const QSharedPointer<PendingAutoOrient> &pending)
{
    if (pending->downloadActive)
        return;
    if (!QDir().mkpath(m_autoOrientOutputDirectory)) {
        m_pendingAutoOrientDownloads.insert(pending->requestId, pending);
        emit autoOrientDownloadFailed(pending->requestId, pending->modelId,
                                      QStringLiteral("The local derived-geometry folder could not be created."));
        return;
    }

    pending->file = QSharedPointer<QSaveFile>::create(pending->outputPath);
    pending->writeError.clear();
    pending->errorBody.clear();
    pending->bytesWritten = 0;
    if (!pending->file->open(QIODevice::WriteOnly)) {
        pending->file.clear();
        m_pendingAutoOrientDownloads.insert(pending->requestId, pending);
        emit autoOrientDownloadFailed(pending->requestId, pending->modelId,
                                      QStringLiteral("The local oriented-mesh file could not be opened."));
        return;
    }

    pending->downloadActive = true;
    const QString encodedProject = QString::fromLatin1(QUrl::toPercentEncoding(m_projectId));
    const QString encodedModel = QString::fromLatin1(QUrl::toPercentEncoding(pending->modelId));
    pending->reply = m_network.get(QNetworkRequest(apiUrl(QStringLiteral("/api/v1/projects/%1/models/%2/file")
                                                              .arg(encodedProject, encodedModel))));
    QNetworkReply *download = pending->reply.data();
    connect(download, &QIODevice::readyRead, this, [pending, download] {
        const QByteArray bytes = download->readAll();
        if (!isSuccessful(download)) {
            pending->errorBody += bytes;
            return;
        }
        if (pending->file && pending->writeError.isEmpty()) {
            const qint64 written = pending->file->write(bytes);
            if (written != bytes.size())
                pending->writeError = QStringLiteral("Writing the downloaded oriented mesh to disk failed.");
            else
                pending->bytesWritten += written;
        }
    });
    connect(download, &QNetworkReply::finished, this, [this, pending] { finishAutoOrientDownload(pending); });
}

void GeometryCommandClient::finishAutoOrientDownload(const QSharedPointer<PendingAutoOrient> &pending)
{
    QNetworkReply *reply = pending->reply.data();
    if (!reply)
        return;

    const QByteArray remainder = reply->readAll();
    if (!isSuccessful(reply)) {
        pending->errorBody += remainder;
    } else if (!remainder.isEmpty() && pending->file && pending->writeError.isEmpty()) {
        const qint64 written = pending->file->write(remainder);
        if (written != remainder.size())
            pending->writeError = QStringLiteral("Writing the downloaded oriented mesh to disk failed.");
        else
            pending->bytesWritten += written;
    }
    const bool httpSuccess = isSuccessful(reply);
    QString failure;
    if (!httpSuccess)
        failure = responseMessage(reply, pending->errorBody);
    else if (!pending->writeError.isEmpty())
        failure = pending->writeError;
    else if (pending->bytesWritten <= 0)
        failure = QStringLiteral("The geometry service returned an empty oriented mesh file.");
    else if (!pending->file || !pending->file->commit())
        failure = QStringLiteral("Saving the oriented mesh failed: %1").arg(pending->file ? pending->file->errorString() : QString());

    reply->deleteLater();
    pending->reply.clear();
    pending->downloadActive = false;
    if (!failure.isEmpty()) {
        if (pending->file)
            pending->file->cancelWriting();
        pending->file.clear();
        m_pendingAutoOrientDownloads.insert(pending->requestId, pending);
        emit autoOrientDownloadFailed(pending->requestId, pending->modelId, failure);
        return;
    }

    m_pendingAutoOrientDownloads.remove(pending->requestId);
    pending->file.clear();
    emit autoOrientCompleted(pending->requestId, pending->modelId, pending->filename,
                             QUrl::fromLocalFile(pending->outputPath), pending->optimalRotationDeg,
                             pending->originalOverhangCm2, pending->optimizedOverhangCm2,
                             pending->reductionPercentage, pending->message);
}

void GeometryCommandClient::repairModel(const QString &requestId, const QString &modelId, double weldToleranceMm)
{
    if (m_projectId.isEmpty() || modelId.isEmpty()) {
        emit repairFailed(requestId, QStringLiteral("This mesh is not registered with the geometry service."));
        return;
    }
    if (!std::isfinite(weldToleranceMm) || weldToleranceMm < 0.00001 || weldToleranceMm > 1.0) {
        emit repairFailed(requestId, QStringLiteral("Weld tolerance must be between 0.00001 and 1.0 mm for service repair."));
        return;
    }
    if (m_pendingRepairDownloads.contains(requestId)) {
        emit repairFailed(requestId, QStringLiteral("A repair download for this request is already pending."));
        return;
    }

    const QJsonObject payload{
        {QStringLiteral("fill_holes"), true},
        {QStringLiteral("fix_normals"), true},
        {QStringLiteral("remove_degenerate"), true},
        {QStringLiteral("weld_vertices"), true},
        {QStringLiteral("weld_tolerance_mm"), weldToleranceMm},
    };
    const QString encodedProject = QString::fromLatin1(QUrl::toPercentEncoding(m_projectId));
    const QString encodedModel = QString::fromLatin1(QUrl::toPercentEncoding(modelId));
    QNetworkRequest request(apiUrl(QStringLiteral("/api/v1/projects/%1/models/%2/repair").arg(encodedProject, encodedModel)));
    request.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
    QNetworkReply *reply = m_network.post(request, QJsonDocument(payload).toJson(QJsonDocument::Compact));
    connect(reply, &QNetworkReply::finished, this, [this, reply, requestId, modelId] {
        const QByteArray body = reply->readAll();
        if (!isSuccessful(reply)) {
            emit repairFailed(requestId, responseMessage(reply, body));
            reply->deleteLater();
            return;
        }
        const QJsonDocument document = QJsonDocument::fromJson(body);
        if (!document.isObject()) {
            emit repairFailed(requestId, QStringLiteral("The geometry service returned invalid repair JSON."));
            reply->deleteLater();
            return;
        }
        const QJsonObject result = document.object();
        const QJsonObject repaired = result.value(QStringLiteral("repaired_model")).toObject();
        const QJsonObject report = result.value(QStringLiteral("report")).toObject();
        const QString returnedModelId = repaired.value(QStringLiteral("id")).toString();
        const QString filename = QFileInfo(repaired.value(QStringLiteral("filename")).toString()).fileName();
        const QString extension = repaired.value(QStringLiteral("file_format")).toString().toLower();
        const QString message = result.value(QStringLiteral("message")).toString();
        const QStringList countFields{QStringLiteral("holes_filled"), QStringLiteral("degenerate_faces_removed"),
                                      QStringLiteral("duplicate_vertices_welded"), QStringLiteral("inverted_normals_fixed"),
                                      QStringLiteral("triangle_count_before"), QStringLiteral("triangle_count_after")};
        const QStringList boolFields{QStringLiteral("is_watertight_before"), QStringLiteral("is_watertight_after")};
        bool validReport = !report.isEmpty();
        for (const QString &field : countFields)
            validReport = validReport && report.value(field).isDouble() && report.value(field).toDouble() >= 0;
        for (const QString &field : boolFields)
            validReport = validReport && report.value(field).isBool();
        if (returnedModelId != modelId || filename.isEmpty()
            || (extension != QStringLiteral("stl") && extension != QStringLiteral("obj"))
            || extensionFor(filename) != extension || message.isEmpty() || !validReport) {
            emit repairFailed(requestId, QStringLiteral("The geometry service returned incomplete or unsupported repair metadata."));
            reply->deleteLater();
            return;
        }
        auto pending = QSharedPointer<PendingRepair>::create();
        pending->requestId = requestId;
        pending->modelId = modelId;
        pending->filename = filename;
        pending->outputPath = QDir(m_repairOutputDirectory).filePath(
            QUuid::createUuid().toString(QUuid::WithoutBraces) + QLatin1Char('_') + filename);
        pending->report = report.toVariantMap();
        pending->message = message;
        reply->deleteLater();
        startRepairDownload(pending);
    });
}

void GeometryCommandClient::retryRepairDownload(const QString &requestId)
{
    const auto pending = m_pendingRepairDownloads.value(requestId);
    if (!pending) {
        emit repairFailed(requestId, QStringLiteral("There is no persisted repair result available to retry."));
        return;
    }
    if (!pending->downloadActive)
        startRepairDownload(pending);
}

void GeometryCommandClient::startRepairDownload(const QSharedPointer<PendingRepair> &pending)
{
    if (pending->downloadActive)
        return;
    if (!QDir().mkpath(m_repairOutputDirectory)) {
        m_pendingRepairDownloads.insert(pending->requestId, pending);
        emit repairDownloadFailed(pending->requestId, pending->modelId,
                                  QStringLiteral("The local derived-repairs folder could not be created."));
        return;
    }
    pending->file = QSharedPointer<QSaveFile>::create(pending->outputPath);
    pending->writeError.clear();
    pending->errorBody.clear();
    pending->bytesWritten = 0;
    if (!pending->file->open(QIODevice::WriteOnly)) {
        pending->file.clear();
        m_pendingRepairDownloads.insert(pending->requestId, pending);
        emit repairDownloadFailed(pending->requestId, pending->modelId,
                                  QStringLiteral("The local repaired-mesh file could not be opened."));
        return;
    }
    pending->downloadActive = true;
    const QString encodedProject = QString::fromLatin1(QUrl::toPercentEncoding(m_projectId));
    const QString encodedModel = QString::fromLatin1(QUrl::toPercentEncoding(pending->modelId));
    pending->reply = m_network.get(QNetworkRequest(apiUrl(QStringLiteral("/api/v1/projects/%1/models/%2/file")
                                                              .arg(encodedProject, encodedModel))));
    QNetworkReply *download = pending->reply.data();
    connect(download, &QIODevice::readyRead, this, [pending, download] {
        const QByteArray bytes = download->readAll();
        if (!isSuccessful(download)) {
            pending->errorBody += bytes;
            return;
        }
        if (pending->file && pending->writeError.isEmpty()) {
            const qint64 written = pending->file->write(bytes);
            if (written != bytes.size())
                pending->writeError = QStringLiteral("Writing the downloaded repaired mesh to disk failed.");
            else
                pending->bytesWritten += written;
        }
    });
    connect(download, &QNetworkReply::finished, this, [this, pending] { finishRepairDownload(pending); });
}

void GeometryCommandClient::finishRepairDownload(const QSharedPointer<PendingRepair> &pending)
{
    QNetworkReply *reply = pending->reply.data();
    if (!reply)
        return;
    const QByteArray remainder = reply->readAll();
    if (!isSuccessful(reply))
        pending->errorBody += remainder;
    else if (!remainder.isEmpty() && pending->file && pending->writeError.isEmpty()) {
        const qint64 written = pending->file->write(remainder);
        if (written != remainder.size())
            pending->writeError = QStringLiteral("Writing the downloaded repaired mesh to disk failed.");
        else
            pending->bytesWritten += written;
    }
    QString failure;
    if (!isSuccessful(reply))
        failure = responseMessage(reply, pending->errorBody);
    else if (!pending->writeError.isEmpty())
        failure = pending->writeError;
    else if (pending->bytesWritten <= 0)
        failure = QStringLiteral("The geometry service returned an empty repaired mesh file.");
    else if (!pending->file || !pending->file->commit())
        failure = QStringLiteral("Saving the repaired mesh failed: %1").arg(pending->file ? pending->file->errorString() : QString());
    reply->deleteLater();
    pending->reply.clear();
    pending->downloadActive = false;
    if (!failure.isEmpty()) {
        if (pending->file)
            pending->file->cancelWriting();
        pending->file.clear();
        m_pendingRepairDownloads.insert(pending->requestId, pending);
        emit repairDownloadFailed(pending->requestId, pending->modelId, failure);
        return;
    }
    m_pendingRepairDownloads.remove(pending->requestId);
    pending->file.clear();
    emit repairCompleted(pending->requestId, pending->modelId, pending->filename,
                         QUrl::fromLocalFile(pending->outputPath), pending->report, pending->message);
}

void GeometryCommandClient::finishSliceDownload(const QSharedPointer<PendingSlice> &pending, bool top)
{
    QPointer<QNetworkReply> &replyPointer = top ? pending->topReply : pending->bottomReply;
    QSaveFile &file = top ? pending->topFile : pending->bottomFile;
    bool &finished = top ? pending->topFinished : pending->bottomFinished;
    QNetworkReply *reply = replyPointer.data();
    if (reply) {
        const QByteArray remainder = reply->readAll();
        if (!remainder.isEmpty() && file.write(remainder) != remainder.size() && pending->error.isEmpty())
            pending->error = QStringLiteral("Writing a downloaded slice mesh to disk failed.");
        if (!isSuccessful(reply) && pending->error.isEmpty())
            pending->error = responseMessage(reply, remainder);
        reply->deleteLater();
        replyPointer.clear();
    }
    finished = true;
    if (pending->topFinished && pending->bottomFinished)
        finalizeSlice(pending);
}

void GeometryCommandClient::finalizeSlice(const QSharedPointer<PendingSlice> &pending)
{
    if (!pending->error.isEmpty()) {
        pending->topFile.cancelWriting();
        pending->bottomFile.cancelWriting();
        emit sliceFailed(pending->requestId, pending->error, pending->topModelId, pending->bottomModelId);
        return;
    }

    if (!pending->topFile.commit()) {
        pending->bottomFile.cancelWriting();
        emit sliceFailed(pending->requestId, QStringLiteral("Saving the top slice mesh failed: %1").arg(pending->topFile.errorString()),
                         pending->topModelId, pending->bottomModelId);
        return;
    }
    if (!pending->bottomFile.commit()) {
        const QString message = QStringLiteral("Saving the bottom slice mesh failed: %1").arg(pending->bottomFile.errorString());
        QFile::remove(pending->topPath);
        emit sliceFailed(pending->requestId, message, pending->topModelId, pending->bottomModelId);
        return;
    }

    emit sliceCompleted(pending->requestId,
                        pending->topModelId, pending->topName, QUrl::fromLocalFile(pending->topPath), pending->topWatertight,
                        pending->bottomModelId, pending->bottomName, QUrl::fromLocalFile(pending->bottomPath), pending->bottomWatertight,
                        pending->cutAreaCm2, pending->message);
}
