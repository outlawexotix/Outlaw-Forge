#include "NativeProjectStore.h"

#include "MeshGeometry.h"

#include <QCryptographicHash>
#include <QByteArrayView>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QTemporaryDir>
#include <QtEndian>

namespace {
QVariantMap failure(const QString &message)
{
    return {{QStringLiteral("ok"), false}, {QStringLiteral("error"), message}};
}

QByteArray sha256File(const QString &path, QString *error)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        if (error)
            *error = QStringLiteral("Could not read %1: %2").arg(path, file.errorString());
        return {};
    }
    QCryptographicHash hash(QCryptographicHash::Sha256);
    QByteArray buffer(1024 * 1024, Qt::Uninitialized);
    while (!file.atEnd()) {
        const qint64 count = file.read(buffer.data(), buffer.size());
        if (count < 0) {
            if (error)
                *error = QStringLiteral("Could not read %1: %2").arg(path, file.errorString());
            return {};
        }
        hash.addData(QByteArrayView(buffer.constData(), qsizetype(count)));
    }
    return hash.result().toHex();
}

bool copyFileAtomically(const QString &sourcePath, const QString &targetPath, QString *error)
{
    QFile source(sourcePath);
    if (!source.open(QIODevice::ReadOnly)) {
        if (error)
            *error = QStringLiteral("Could not read staged mesh %1: %2").arg(sourcePath, source.errorString());
        return false;
    }
    QSaveFile target(targetPath);
    if (!target.open(QIODevice::WriteOnly)) {
        if (error)
            *error = QStringLiteral("Could not create project mesh %1: %2").arg(targetPath, target.errorString());
        return false;
    }
    QByteArray buffer(1024 * 1024, Qt::Uninitialized);
    while (!source.atEnd()) {
        const qint64 count = source.read(buffer.data(), buffer.size());
        if (count < 0 || target.write(buffer.constData(), count) != count) {
            if (error)
                *error = QStringLiteral("Could not copy project mesh %1: %2").arg(targetPath, target.errorString());
            return false;
        }
    }
    if (!target.commit()) {
        if (error)
            *error = QStringLiteral("Could not finish project mesh %1: %2").arg(targetPath, target.errorString());
        return false;
    }
    return true;
}

bool ensureImmutableAsset(const QString &stagedPath, const QString &assetPath,
                          const QByteArray &digest, QString *error)
{
    if (QFileInfo::exists(assetPath)) {
        QString hashError;
        if (sha256File(assetPath, &hashError) != digest) {
            if (error)
                *error = QStringLiteral("Existing content-addressed mesh %1 does not match its name.").arg(assetPath);
            return false;
        }
        return true;
    }
    if (!copyFileAtomically(stagedPath, assetPath, error))
        return false;
    return true;
}
}

QVariantMap NativeProjectStore::saveProject(const QUrl &folderUrl, const QVariantMap &scene,
                                            const QVariantList &geometryRecords) const
{
    if (!folderUrl.isLocalFile())
        return failure(QStringLiteral("Choose a local folder for the native project."));
    const QString folderPath = QDir::cleanPath(folderUrl.toLocalFile());
    if (folderPath.isEmpty())
        return failure(QStringLiteral("The native project folder path is empty."));

    QDir folder;
    if (!folder.mkpath(folderPath))
        return failure(QStringLiteral("Could not create project folder %1.").arg(folderPath));
    const QString meshesPath = QDir(folderPath).filePath(QStringLiteral("meshes"));
    if (!QDir().mkpath(meshesPath))
        return failure(QStringLiteral("Could not create project mesh folder %1.").arg(meshesPath));

    QJsonArray geometryArray;
    for (const QVariant &value : geometryRecords) {
        const QVariantMap record = value.toMap();
        const QString key = record.value(QStringLiteral("geometryKey")).toString();
        auto *geometry = qobject_cast<MeshGeometry *>(record.value(QStringLiteral("geometry")).value<QObject *>());
        if (key.isEmpty() || !geometry || !geometry->loaded())
            return failure(QStringLiteral("Project geometry '%1' is missing or unavailable.").arg(key));

        QTemporaryDir stagedDirectory(QDir(meshesPath).filePath(QStringLiteral(".snapshot-XXXXXX")));
        if (!stagedDirectory.isValid())
            return failure(QStringLiteral("Could not create temporary staging folder for project mesh '%1'.").arg(key));
        const QString stagedPath = QDir(stagedDirectory.path()).filePath(QStringLiteral("snapshot.stl"));
        const QVariantMap exported = geometry->exportLocalStl(QUrl::fromLocalFile(stagedPath));
        if (exported.contains(QStringLiteral("error")))
            return failure(QStringLiteral("Could not snapshot project geometry '%1': %2")
                               .arg(key, exported.value(QStringLiteral("error")).toString()));

        QString hashError;
        const QByteArray digest = sha256File(stagedPath, &hashError);
        if (digest.isEmpty())
            return failure(hashError.isEmpty() ? QStringLiteral("Could not hash project mesh '%1'.").arg(key) : hashError);
        const QString assetName = QString::fromLatin1(digest) + QStringLiteral(".stl");
        const QString assetPath = QDir(meshesPath).filePath(assetName);
        if (!ensureImmutableAsset(stagedPath, assetPath, digest, &hashError))
            return failure(hashError);

        QJsonObject geometryObject;
        geometryObject.insert(QStringLiteral("geometryKey"), key);
        geometryObject.insert(QStringLiteral("sourceName"), record.value(QStringLiteral("sourceName")).toString());
        geometryObject.insert(QStringLiteral("sourceFormat"), record.value(QStringLiteral("sourceFormat")).toString());
        geometryObject.insert(QStringLiteral("revisionId"), geometry->revisionId());
        geometryObject.insert(QStringLiteral("assetPath"), QStringLiteral("meshes/") + assetName);
        geometryObject.insert(QStringLiteral("sha256"), QString::fromLatin1(digest));
        geometryObject.insert(QStringLiteral("triangleCount"), geometry->triangleCount());
        geometryArray.append(geometryObject);
    }

    QJsonObject document;
    document.insert(QStringLiteral("format"), QStringLiteral("outlaw-forge-native-project"));
    document.insert(QStringLiteral("schemaVersion"), 1);
    document.insert(QStringLiteral("units"), QStringLiteral("mm"));
    document.insert(QStringLiteral("axis"), QStringLiteral("Z-up"));
    document.insert(QStringLiteral("selectedInstanceId"), scene.value(QStringLiteral("selectedInstanceId")).toString());
    document.insert(QStringLiteral("geometries"), geometryArray);
    document.insert(QStringLiteral("instances"), QJsonArray::fromVariantList(scene.value(QStringLiteral("instances")).toList()));

    const QString manifestPath = QDir(folderPath).filePath(QStringLiteral("project.json"));
    QSaveFile manifestFile(manifestPath);
    if (!manifestFile.open(QIODevice::WriteOnly))
        return failure(QStringLiteral("Could not create project manifest %1: %2").arg(manifestPath, manifestFile.errorString()));
    const QByteArray json = QJsonDocument(document).toJson(QJsonDocument::Indented);
    if (manifestFile.write(json) != json.size())
        return failure(QStringLiteral("Could not write project manifest %1: %2").arg(manifestPath, manifestFile.errorString()));
    if (!manifestFile.commit())
        return failure(QStringLiteral("Could not finish project manifest %1: %2").arg(manifestPath, manifestFile.errorString()));

    return {{QStringLiteral("ok"), true},
            {QStringLiteral("folderUrl"), folderUrl},
            {QStringLiteral("manifestPath"), manifestPath},
            {QStringLiteral("geometryCount"), geometryArray.size()}};
}

QVariantMap NativeProjectStore::loadProject(const QUrl &folderUrl) const
{
    if (!folderUrl.isLocalFile())
        return failure(QStringLiteral("Choose a local folder to open the native project."));
    const QString folderPath = QDir::cleanPath(folderUrl.toLocalFile());
    const QString manifestPath = QDir(folderPath).filePath(QStringLiteral("project.json"));
    QFile manifestFile(manifestPath);
    if (!manifestFile.open(QIODevice::ReadOnly))
        return failure(QStringLiteral("Could not open project manifest %1: %2").arg(manifestPath, manifestFile.errorString()));
    QJsonParseError parseError;
    const QJsonDocument manifest = QJsonDocument::fromJson(manifestFile.readAll(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !manifest.isObject())
        return failure(QStringLiteral("Project manifest %1 is invalid JSON: %2").arg(manifestPath, parseError.errorString()));
    const QJsonObject document = manifest.object();
    if (document.value(QStringLiteral("format")).toString() != QStringLiteral("outlaw-forge-native-project"))
        return failure(QStringLiteral("Project manifest %1 has an unsupported format.").arg(manifestPath));
    if (document.value(QStringLiteral("schemaVersion")).toInt() != 1)
        return failure(QStringLiteral("Project manifest %1 uses an unsupported schema version.").arg(manifestPath));

    QVariantList geometries;
    const QJsonArray geometryArray = document.value(QStringLiteral("geometries")).toArray();
    for (const QJsonValue &value : geometryArray) {
        const QJsonObject geometry = value.toObject();
        const QString relativeAsset = geometry.value(QStringLiteral("assetPath")).toString();
        const QString assetPath = QDir(folderPath).filePath(relativeAsset);
        if (!QFileInfo::exists(assetPath))
            return failure(QStringLiteral("Project mesh asset %1 is missing.").arg(assetPath));
        QString hashError;
        const QByteArray digest = sha256File(assetPath, &hashError);
        if (!hashError.isEmpty())
            return failure(hashError);
        if (QString::fromLatin1(digest) != geometry.value(QStringLiteral("sha256")).toString())
            return failure(QStringLiteral("Project mesh asset %1 failed its SHA-256 check.").arg(assetPath));

        QVariantMap loadedGeometry;
        loadedGeometry.insert(QStringLiteral("geometryKey"), geometry.value(QStringLiteral("geometryKey")).toString());
        loadedGeometry.insert(QStringLiteral("revisionId"), geometry.value(QStringLiteral("revisionId")).toString());
        loadedGeometry.insert(QStringLiteral("sourceName"), geometry.value(QStringLiteral("sourceName")).toString());
        loadedGeometry.insert(QStringLiteral("sourceFormat"), geometry.value(QStringLiteral("sourceFormat")).toString());
        loadedGeometry.insert(QStringLiteral("triangleCount"), geometry.value(QStringLiteral("triangleCount")).toInt());
        loadedGeometry.insert(QStringLiteral("assetUrl"), QUrl::fromLocalFile(assetPath));
        geometries.append(loadedGeometry);
    }

    return {{QStringLiteral("ok"), true},
            {QStringLiteral("document"), document.toVariantMap()},
            {QStringLiteral("geometries"), geometries}};
}
