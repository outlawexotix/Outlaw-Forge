#include "SliceCommandClient.h"

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
}

struct SliceCommandClient::PendingSlice {
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

SliceCommandClient::SliceCommandClient(QObject *parent)
    : QObject(parent),
      m_apiBaseUrl(QUrl(qEnvironmentVariable("OUTLAW_FORGE_API_URL", "http://127.0.0.1:8000"))),
      m_outputDirectory(QDir(QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation))
                            .filePath(QStringLiteral("derived-slices")))
{
}

void SliceCommandClient::setApiBaseUrl(const QUrl &url)
{
    if (url == m_apiBaseUrl)
        return;
    m_apiBaseUrl = url;
    emit apiBaseUrlChanged();
}

void SliceCommandClient::setOutputDirectory(const QString &path)
{
    m_outputDirectory = path;
}

QUrl SliceCommandClient::apiUrl(const QString &path) const
{
    QUrl url = m_apiBaseUrl;
    QString basePath = url.path();
    while (basePath.endsWith(QLatin1Char('/')))
        basePath.chop(1);
    url.setPath(basePath + path);
    return url;
}

void SliceCommandClient::registerSource(const QUrl &sourceFile, const QString &filename)
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

void SliceCommandClient::createProject()
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

void SliceCommandClient::uploadQueuedSources()
{
    while (!m_pendingSources.isEmpty())
        uploadSource(m_pendingSources.dequeue());
}

void SliceCommandClient::uploadSource(const PendingSource &source)
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

void SliceCommandClient::sliceModel(const QString &requestId, const QString &modelId,
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

void SliceCommandClient::finishSliceDownload(const QSharedPointer<PendingSlice> &pending, bool top)
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

void SliceCommandClient::finalizeSlice(const QSharedPointer<PendingSlice> &pending)
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
