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
#include <QMetaType>
#include <QSet>
#include <QSaveFile>
#include <QTemporaryDir>
#include <QtEndian>
#include <cmath>

namespace {
constexpr qint64 MaxManifestBytes = 16 * 1024 * 1024;
constexpr qint64 MaxTrianglesPerMesh = 20'000'000;
constexpr quint64 MaxUniqueAssetBytes = 4ULL * 1024 * 1024 * 1024;
constexpr quint64 BinaryStlHeaderBytes = 84;
constexpr quint64 BinaryStlTriangleBytes = 50;
}

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

bool isNumericVariant(const QVariant &value)
{
    const int type = value.metaType().id();
    return type == QMetaType::Double || type == QMetaType::Float
        || type == QMetaType::Int || type == QMetaType::UInt
        || type == QMetaType::LongLong || type == QMetaType::ULongLong
        || type == QMetaType::Short || type == QMetaType::UShort
        || type == QMetaType::Char || type == QMetaType::UChar;
}

bool isSafeAssetPath(const QString &path, const QString &digest)
{
    if (path.contains(QLatin1Char('\\')) || path.contains(QLatin1Char(':')))
        return false;
    const QStringList parts = path.split(QLatin1Char('/'), Qt::KeepEmptyParts);
    return parts.size() == 2 && parts[0] == QStringLiteral("meshes")
        && parts[1] == digest + QStringLiteral(".stl");
}

bool isInsideDirectory(const QString &filePath, const QString &directoryPath)
{
    const QString file = QDir::fromNativeSeparators(QDir::cleanPath(filePath));
    QString directory = QDir::fromNativeSeparators(QDir::cleanPath(directoryPath));
    if (!directory.endsWith(QLatin1Char('/')))
        directory += QLatin1Char('/');
#ifdef Q_OS_WIN
    return file.startsWith(directory, Qt::CaseInsensitive);
#else
    return file.startsWith(directory, Qt::CaseSensitive);
#endif
}

bool validateVariantScene(const QVariantMap &scene, const QSet<QString> &geometryKeys, QString *error)
{
    const QVariant rowsValue = scene.value(QStringLiteral("instances"));
    if (!rowsValue.canConvert<QVariantList>()) {
        if (error)
            *error = QStringLiteral("The project scene instances must be an ordered list.");
        return false;
    }
    QSet<QString> instanceIds;
    const QVariantList rows = rowsValue.toList();
    const QStringList requiredStrings{QStringLiteral("instanceId"), QStringLiteral("name"),
                                      QStringLiteral("sourceUrl"), QStringLiteral("piece"),
                                      QStringLiteral("geometryKey")};
    const QStringList transforms{QStringLiteral("offsetX"), QStringLiteral("offsetY"), QStringLiteral("offsetZ"),
                                 QStringLiteral("rotationX"), QStringLiteral("rotationY"), QStringLiteral("rotationZ"),
                                 QStringLiteral("scaleX"), QStringLiteral("scaleY"), QStringLiteral("scaleZ")};
    for (const QVariant &rowValue : rows) {
        const QVariantMap row = rowValue.toMap();
        for (const QString &field : requiredStrings) {
            if (!row.contains(field) || row.value(field).metaType().id() != QMetaType::QString
                || (field == QStringLiteral("instanceId") && row.value(field).toString().isEmpty())) {
                if (error)
                    *error = QStringLiteral("A project scene instance is missing required field '%1'.").arg(field);
                return false;
            }
        }
        const QString id = row.value(QStringLiteral("instanceId")).toString();
        if (instanceIds.contains(id)) {
            if (error)
                *error = QStringLiteral("Project instance id '%1' is duplicated.").arg(id);
            return false;
        }
        instanceIds.insert(id);
        const QString geometryKey = row.value(QStringLiteral("geometryKey")).toString();
        if (geometryKey.isEmpty() || !geometryKeys.contains(geometryKey)) {
            if (error)
                *error = QStringLiteral("Project instance '%1' references unknown geometry '%2'.").arg(id, geometryKey);
            return false;
        }
        if (!row.contains(QStringLiteral("instanceVisible"))
            || row.value(QStringLiteral("instanceVisible")).metaType().id() != QMetaType::Bool) {
            if (error)
                *error = QStringLiteral("Project instance '%1' has an invalid visibility value.").arg(id);
            return false;
        }
        for (const QString &field : transforms) {
            bool ok = false;
            const double number = row.value(field).toDouble(&ok);
            if (!row.contains(field) || !isNumericVariant(row.value(field)) || !ok || !std::isfinite(number)) {
                if (error)
                    *error = QStringLiteral("Project instance '%1' has a non-finite or missing transform '%2'.").arg(id, field);
                return false;
            }
        }
    }
    const QVariant selectedValue = scene.value(QStringLiteral("selectedInstanceId"));
    if (!selectedValue.isValid() || selectedValue.metaType().id() != QMetaType::QString) {
        if (error)
            *error = QStringLiteral("The selected project instance id must be a string.");
        return false;
    }
    const QString selected = selectedValue.toString();
    if (!selected.isEmpty() && !instanceIds.contains(selected)) {
        if (error)
            *error = QStringLiteral("Selected project instance '%1' does not exist.").arg(selected);
        return false;
    }
    return true;
}

bool finiteJsonNumber(const QJsonObject &object, const QString &field, double *value)
{
    const QJsonValue entry = object.value(field);
    if (!entry.isDouble() || !std::isfinite(entry.toDouble()))
        return false;
    if (value)
        *value = entry.toDouble();
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

    QSet<QString> geometryKeys;
    for (const QVariant &value : geometryRecords) {
        const QVariantMap record = value.toMap();
        const QVariant keyValue = record.value(QStringLiteral("geometryKey"));
        const QVariant sourceNameValue = record.value(QStringLiteral("sourceName"));
        const QVariant sourceFormatValue = record.value(QStringLiteral("sourceFormat"));
        if (keyValue.metaType().id() != QMetaType::QString
            || sourceNameValue.metaType().id() != QMetaType::QString
            || sourceFormatValue.metaType().id() != QMetaType::QString)
            return failure(QStringLiteral("Project geometry metadata must use string keys, source names, and formats."));
        const QString key = keyValue.toString();
        if (key.isEmpty() || geometryKeys.contains(key))
            return failure(QStringLiteral("Project geometry keys must be non-empty and unique."));
        geometryKeys.insert(key);
    }
    QString sceneError;
    if (!validateVariantScene(scene, geometryKeys, &sceneError))
        return failure(sceneError);

    QDir folder;
    if (!folder.mkpath(folderPath))
        return failure(QStringLiteral("Could not create project folder %1.").arg(folderPath));
    const QString meshesPath = QDir(folderPath).filePath(QStringLiteral("meshes"));
    if (!QDir().mkpath(meshesPath))
        return failure(QStringLiteral("Could not create project mesh folder %1.").arg(meshesPath));

    QJsonArray geometryArray;
    QSet<QByteArray> storedDigests;
    quint64 totalAssetBytes = 0;
    for (const QVariant &value : geometryRecords) {
        const QVariantMap record = value.toMap();
        const QString key = record.value(QStringLiteral("geometryKey")).toString();
        auto *geometry = qobject_cast<MeshGeometry *>(record.value(QStringLiteral("geometry")).value<QObject *>());
        if (key.isEmpty() || !geometry || !geometry->loaded())
            return failure(QStringLiteral("Project geometry '%1' is missing or unavailable.").arg(key));
        if (geometry->triangleCount() <= 0 || geometry->triangleCount() > MaxTrianglesPerMesh)
            return failure(QStringLiteral("Project geometry '%1' exceeds the supported triangle limit.").arg(key));

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
        const quint64 stagedSize = quint64(QFileInfo(stagedPath).size());
        const quint64 expectedSize = BinaryStlHeaderBytes + quint64(geometry->triangleCount()) * BinaryStlTriangleBytes;
        if (stagedSize != expectedSize)
            return failure(QStringLiteral("Staged project mesh '%1' has an invalid binary STL size.").arg(key));
        if (!storedDigests.contains(digest)) {
            if (stagedSize > MaxUniqueAssetBytes - totalAssetBytes)
                return failure(QStringLiteral("Project mesh assets exceed the 4 GiB project limit."));
            totalAssetBytes += stagedSize;
            storedDigests.insert(digest);
        }
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
    if (json.size() > MaxManifestBytes)
        return failure(QStringLiteral("Project manifest exceeds the 16 MiB size limit."));
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
    if (manifestFile.size() < 0 || manifestFile.size() > MaxManifestBytes)
        return failure(QStringLiteral("Project manifest %1 exceeds the 16 MiB size limit.").arg(manifestPath));
    QJsonParseError parseError;
    const QJsonDocument manifest = QJsonDocument::fromJson(manifestFile.readAll(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !manifest.isObject())
        return failure(QStringLiteral("Project manifest %1 is invalid JSON: %2").arg(manifestPath, parseError.errorString()));
    const QJsonObject document = manifest.object();
    if (!document.value(QStringLiteral("format")).isString()
        || document.value(QStringLiteral("format")).toString() != QStringLiteral("outlaw-forge-native-project"))
        return failure(QStringLiteral("Project manifest %1 has an unsupported format.").arg(manifestPath));
    const QJsonValue schemaVersion = document.value(QStringLiteral("schemaVersion"));
    if (!schemaVersion.isDouble() || schemaVersion.toDouble() != 1.0)
        return failure(QStringLiteral("Project manifest %1 uses an unsupported schema version.").arg(manifestPath));
    if (!document.value(QStringLiteral("units")).isString()
        || document.value(QStringLiteral("units")).toString() != QStringLiteral("mm"))
        return failure(QStringLiteral("Project manifest %1 must use millimetres.").arg(manifestPath));
    if (!document.value(QStringLiteral("axis")).isString()
        || document.value(QStringLiteral("axis")).toString() != QStringLiteral("Z-up"))
        return failure(QStringLiteral("Project manifest %1 must use the Z-up axis convention.").arg(manifestPath));
    if (!document.value(QStringLiteral("selectedInstanceId")).isString()
        || !document.value(QStringLiteral("geometries")).isArray()
        || !document.value(QStringLiteral("instances")).isArray())
        return failure(QStringLiteral("Project manifest %1 is missing required scene fields.").arg(manifestPath));

    QVariantList geometries;
    const QJsonArray geometryArray = document.value(QStringLiteral("geometries")).toArray();
    const QString meshesPath = QDir(folderPath).filePath(QStringLiteral("meshes"));
    const QString canonicalMeshesPath = QFileInfo(meshesPath).canonicalFilePath();
    QSet<QString> geometryKeys;
    QSet<QString> uniqueAssets;
    quint64 totalAssetBytes = 0;
    for (const QJsonValue &value : geometryArray) {
        if (!value.isObject())
            return failure(QStringLiteral("Project manifest %1 contains a malformed geometry record.").arg(manifestPath));
        const QJsonObject geometry = value.toObject();
        const QJsonValue keyValue = geometry.value(QStringLiteral("geometryKey"));
        const QJsonValue revisionValue = geometry.value(QStringLiteral("revisionId"));
        const QJsonValue sourceNameValue = geometry.value(QStringLiteral("sourceName"));
        const QJsonValue sourceFormatValue = geometry.value(QStringLiteral("sourceFormat"));
        const QJsonValue digestValue = geometry.value(QStringLiteral("sha256"));
        const QJsonValue assetPathValue = geometry.value(QStringLiteral("assetPath"));
        const QJsonValue triangleCountValue = geometry.value(QStringLiteral("triangleCount"));
        if (!keyValue.isString() || keyValue.toString().isEmpty()
            || !revisionValue.isString() || revisionValue.toString().isEmpty()
            || !sourceNameValue.isString() || !sourceFormatValue.isString()
            || !digestValue.isString() || !assetPathValue.isString()
            || !triangleCountValue.isDouble())
            return failure(QStringLiteral("Project manifest %1 contains incomplete geometry metadata.").arg(manifestPath));
        const QString key = keyValue.toString();
        if (geometryKeys.contains(key))
            return failure(QStringLiteral("Project geometry key '%1' is duplicated.").arg(key));
        geometryKeys.insert(key);
        const QString expectedDigest = digestValue.toString();
        if (expectedDigest.size() != 64
            || std::any_of(expectedDigest.cbegin(), expectedDigest.cend(), [](QChar c) {
                return !((c >= QLatin1Char('0') && c <= QLatin1Char('9'))
                         || (c >= QLatin1Char('a') && c <= QLatin1Char('f')));
            }))
            return failure(QStringLiteral("Project geometry '%1' has an invalid SHA-256 digest.").arg(key));
        const double triangleCountNumber = triangleCountValue.toDouble();
        if (!std::isfinite(triangleCountNumber) || std::floor(triangleCountNumber) != triangleCountNumber
            || triangleCountNumber < 1.0 || triangleCountNumber > double(MaxTrianglesPerMesh))
            return failure(QStringLiteral("Project geometry '%1' exceeds the supported triangle limit.").arg(key));
        const quint64 triangleCount = quint64(triangleCountNumber);
        const QString relativeAsset = geometry.value(QStringLiteral("assetPath")).toString();
        if (!isSafeAssetPath(relativeAsset, expectedDigest))
            return failure(QStringLiteral("Project geometry '%1' has an unsafe asset path; assets must be content-addressed under meshes/.").arg(key));
        const QString assetPath = QDir(folderPath).filePath(relativeAsset);
        const QFileInfo assetInfo(assetPath);
        if (!assetInfo.exists() || !assetInfo.isFile())
            return failure(QStringLiteral("Project mesh asset %1 is missing.").arg(assetPath));
        const QString canonicalAssetPath = assetInfo.canonicalFilePath();
        if (canonicalMeshesPath.isEmpty() || !isInsideDirectory(canonicalAssetPath, canonicalMeshesPath))
            return failure(QStringLiteral("Project mesh asset %1 resolves outside the project meshes folder.").arg(assetPath));

        const quint64 expectedByteCount = BinaryStlHeaderBytes + triangleCount * BinaryStlTriangleBytes;
        if (assetInfo.size() < 0 || quint64(assetInfo.size()) != expectedByteCount)
            return failure(QStringLiteral("Project mesh asset %1 has a triangle count or binary STL size mismatch.").arg(assetPath));
        QFile binaryStl(assetPath);
        if (!binaryStl.open(QIODevice::ReadOnly))
            return failure(QStringLiteral("Could not read project mesh asset %1: %2").arg(assetPath, binaryStl.errorString()));
        const QByteArray binaryHeader = binaryStl.read(qint64(BinaryStlHeaderBytes));
        if (binaryHeader.size() != qint64(BinaryStlHeaderBytes)
            || qFromLittleEndian<quint32>(reinterpret_cast<const uchar *>(binaryHeader.constData() + 80)) != triangleCount)
            return failure(QStringLiteral("Project mesh asset %1 has a triangle count mismatch.").arg(assetPath));
        const QString assetIdentity = canonicalAssetPath.toCaseFolded();
        if (!uniqueAssets.contains(assetIdentity)) {
            if (expectedByteCount > MaxUniqueAssetBytes - totalAssetBytes)
                return failure(QStringLiteral("Project mesh assets exceed the 4 GiB project limit."));
            totalAssetBytes += expectedByteCount;
            uniqueAssets.insert(assetIdentity);
        }
        QString hashError;
        const QByteArray digest = sha256File(assetPath, &hashError);
        if (!hashError.isEmpty())
            return failure(hashError);
        if (QString::fromLatin1(digest) != expectedDigest)
            return failure(QStringLiteral("Project mesh asset %1 failed its SHA-256 check.").arg(assetPath));

        QVariantMap loadedGeometry;
        loadedGeometry.insert(QStringLiteral("geometryKey"), key);
        loadedGeometry.insert(QStringLiteral("revisionId"), revisionValue.toString());
        loadedGeometry.insert(QStringLiteral("sourceName"), sourceNameValue.toString());
        loadedGeometry.insert(QStringLiteral("sourceFormat"), sourceFormatValue.toString());
        loadedGeometry.insert(QStringLiteral("triangleCount"), int(triangleCount));
        loadedGeometry.insert(QStringLiteral("assetUrl"), QUrl::fromLocalFile(assetPath));
        geometries.append(loadedGeometry);
    }

    QSet<QString> instanceIds;
    const QJsonArray instanceArray = document.value(QStringLiteral("instances")).toArray();
    const QStringList requiredTextFields{QStringLiteral("instanceId"), QStringLiteral("name"),
                                         QStringLiteral("sourceUrl"), QStringLiteral("piece"),
                                         QStringLiteral("geometryKey")};
    const QStringList transformFields{QStringLiteral("offsetX"), QStringLiteral("offsetY"), QStringLiteral("offsetZ"),
                                      QStringLiteral("rotationX"), QStringLiteral("rotationY"), QStringLiteral("rotationZ"),
                                      QStringLiteral("scaleX"), QStringLiteral("scaleY"), QStringLiteral("scaleZ")};
    for (const QJsonValue &value : instanceArray) {
        if (!value.isObject())
            return failure(QStringLiteral("Project manifest %1 contains a malformed scene instance.").arg(manifestPath));
        const QJsonObject instance = value.toObject();
        for (const QString &field : requiredTextFields) {
            if (!instance.value(field).isString()
                || (field == QStringLiteral("instanceId") && instance.value(field).toString().isEmpty()))
                return failure(QStringLiteral("Project scene instance is missing a valid '%1' field.").arg(field));
        }
        const QString id = instance.value(QStringLiteral("instanceId")).toString();
        if (instanceIds.contains(id))
            return failure(QStringLiteral("Project instance id '%1' is duplicated.").arg(id));
        instanceIds.insert(id);
        const QString geometryKey = instance.value(QStringLiteral("geometryKey")).toString();
        if (!geometryKeys.contains(geometryKey))
            return failure(QStringLiteral("Project instance '%1' references unknown geometry '%2'.").arg(id, geometryKey));
        if (!instance.value(QStringLiteral("instanceVisible")).isBool())
            return failure(QStringLiteral("Project instance '%1' has an invalid visibility value.").arg(id));
        for (const QString &field : transformFields) {
            if (!finiteJsonNumber(instance, field, nullptr))
                return failure(QStringLiteral("Project instance '%1' has a non-finite or missing transform '%2'.").arg(id, field));
        }
    }
    const QString selectedId = document.value(QStringLiteral("selectedInstanceId")).toString();
    if (!selectedId.isEmpty() && !instanceIds.contains(selectedId))
        return failure(QStringLiteral("Selected project instance '%1' does not exist.").arg(selectedId));

    return {{QStringLiteral("ok"), true},
            {QStringLiteral("document"), document.toVariantMap()},
            {QStringLiteral("geometries"), geometries}};
}
