#include "../src/NativeProjectStore.h"
#include "../src/MeshGeometry.h"

#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTemporaryDir>
#include <QTextStream>
#include <QtTest>

namespace {
bool writeStl(const QString &path, bool altered = false)
{
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Text))
        return false;
    QTextStream stream(&file);
    stream << "solid project_fixture\n"
           << " facet normal 0 0 1\n  outer loop\n"
           << "   vertex 0 0 0\n   vertex " << (altered ? 2 : 1) << " 0 0\n   vertex 0 1 0\n"
           << "  endloop\n endfacet\nendsolid project_fixture\n";
    return stream.status() == QTextStream::Ok;
}

QVariantMap geometryRecord(const QString &key, const QString &sourceName, MeshGeometry *geometry)
{
    return {{QStringLiteral("geometryKey"), key},
            {QStringLiteral("sourceName"), sourceName},
            {QStringLiteral("sourceFormat"), QStringLiteral("STL")},
            {QStringLiteral("geometry"), QVariant::fromValue(static_cast<QObject *>(geometry))}};
}

QVariantMap instance(const QString &id, const QString &geometryKey, double offsetX,
                     bool visible, double scaleX)
{
    return {{QStringLiteral("instanceId"), id},
            {QStringLiteral("name"), id + QStringLiteral(" display")},
            {QStringLiteral("sourceUrl"), QStringLiteral("file:///original/model.stl")},
            {QStringLiteral("piece"), QStringLiteral("model")},
            {QStringLiteral("geometryKey"), geometryKey},
            {QStringLiteral("instanceVisible"), visible},
            {QStringLiteral("offsetX"), offsetX},
            {QStringLiteral("offsetY"), -12.5},
            {QStringLiteral("offsetZ"), 3.0},
            {QStringLiteral("rotationX"), 5.0},
            {QStringLiteral("rotationY"), -7.0},
            {QStringLiteral("rotationZ"), 90.0},
            {QStringLiteral("scaleX"), scaleX},
            {QStringLiteral("scaleY"), 0.75},
            {QStringLiteral("scaleZ"), 1.25}};
}

QVariantMap sceneWith(const QVariantList &instances, const QString &selectedId)
{
    return {{QStringLiteral("selectedInstanceId"), selectedId},
            {QStringLiteral("instances"), instances}};
}

QByteArray fileBytes(const QString &path)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly))
        return {};
    return file.readAll();
}
}

class NativeProjectStoreTests : public QObject
{
    Q_OBJECT

private slots:
    void saveAndLoadRoundTripsSceneAndReusesIdenticalGeometryAssets()
    {
        QTemporaryDir temporary;
        QVERIFY(temporary.isValid());
        const QString sourcePath = temporary.filePath(QStringLiteral("original.stl"));
        const QString projectPath = temporary.filePath(QStringLiteral("Scene.oforge"));
        QVERIFY(writeStl(sourcePath));

        MeshGeometry sourceGeometry;
        MeshGeometry duplicateGeometry;
        QVERIFY(sourceGeometry.loadStl(QUrl::fromLocalFile(sourcePath)));
        QVERIFY(duplicateGeometry.loadStl(QUrl::fromLocalFile(sourcePath)));
        const QVariantList rows{
            instance(QStringLiteral("instance-source"), QStringLiteral("source"), 14.25, true, 1.0),
            instance(QStringLiteral("instance-copy"), QStringLiteral("derived-1"), -8.5, false, -1.0),
        };
        const QVariantMap scene = sceneWith(rows, QStringLiteral("instance-copy"));
        const QVariantList geometries{
            geometryRecord(QStringLiteral("source"), QStringLiteral("original.stl"), &sourceGeometry),
            geometryRecord(QStringLiteral("derived-1"), QStringLiteral("copy.stl"), &duplicateGeometry),
        };

        NativeProjectStore store;
        const QVariantMap saved = store.saveProject(QUrl::fromLocalFile(projectPath), scene, geometries);
        QVERIFY2(saved.value(QStringLiteral("ok")).toBool(), qPrintable(saved.value(QStringLiteral("error")).toString()));

        const QString manifestPath = QDir(projectPath).filePath(QStringLiteral("project.json"));
        const QJsonDocument manifest = QJsonDocument::fromJson(fileBytes(manifestPath));
        QVERIFY(manifest.isObject());
        const QJsonObject document = manifest.object();
        QCOMPARE(document.value(QStringLiteral("format")).toString(), QStringLiteral("outlaw-forge-native-project"));
        QCOMPARE(document.value(QStringLiteral("schemaVersion")).toInt(), 1);
        QCOMPARE(document.value(QStringLiteral("units")).toString(), QStringLiteral("mm"));
        QCOMPARE(document.value(QStringLiteral("axis")).toString(), QStringLiteral("Z-up"));
        QCOMPARE(document.value(QStringLiteral("selectedInstanceId")).toString(), QStringLiteral("instance-copy"));
        QCOMPARE(document.value(QStringLiteral("instances")).toArray().size(), 2);
        QCOMPARE(document.value(QStringLiteral("geometries")).toArray().size(), 2);

        const QJsonArray storedGeometries = document.value(QStringLiteral("geometries")).toArray();
        const QJsonObject storedSource = storedGeometries.at(0).toObject();
        const QJsonObject storedDuplicate = storedGeometries.at(1).toObject();
        QCOMPARE(storedSource.value(QStringLiteral("assetPath")).toString(),
                 storedDuplicate.value(QStringLiteral("assetPath")).toString());
        QCOMPARE(storedSource.value(QStringLiteral("revisionId")).toString(), sourceGeometry.revisionId());
        QCOMPARE(storedSource.value(QStringLiteral("triangleCount")).toInt(), sourceGeometry.triangleCount());
        QCOMPARE(storedSource.value(QStringLiteral("sourceFormat")).toString(), QStringLiteral("STL"));
        QCOMPARE(storedSource.value(QStringLiteral("sourceName")).toString(), QStringLiteral("original.stl"));
        const QString assetPath = QDir(projectPath).filePath(storedSource.value(QStringLiteral("assetPath")).toString());
        const QByteArray asset = fileBytes(assetPath);
        QVERIFY(!asset.isEmpty());
        const QByteArray digest = QCryptographicHash::hash(asset, QCryptographicHash::Sha256).toHex();
        QCOMPARE(digest, storedSource.value(QStringLiteral("sha256")).toString().toLatin1());
        QCOMPARE(QFileInfo(assetPath).fileName(), QString::fromLatin1(digest) + QStringLiteral(".stl"));

        const QVariantMap loaded = store.loadProject(QUrl::fromLocalFile(projectPath));
        QVERIFY2(loaded.value(QStringLiteral("ok")).toBool(), qPrintable(loaded.value(QStringLiteral("error")).toString()));
        const QVariantMap loadedDocument = loaded.value(QStringLiteral("document")).toMap();
        QCOMPARE(loadedDocument.value(QStringLiteral("selectedInstanceId")).toString(), QStringLiteral("instance-copy"));
        QCOMPARE(loadedDocument.value(QStringLiteral("instances")).toList(), rows);
        const QVariantList loadedGeometries = loaded.value(QStringLiteral("geometries")).toList();
        QCOMPARE(loadedGeometries.size(), 2);
        const QVariantMap loadedSource = loadedGeometries.at(0).toMap();
        const QVariantMap loadedDuplicate = loadedGeometries.at(1).toMap();
        QCOMPARE(loadedSource.value(QStringLiteral("geometryKey")).toString(), QStringLiteral("source"));
        QCOMPARE(loadedSource.value(QStringLiteral("revisionId")).toString(), sourceGeometry.revisionId());
        QCOMPARE(loadedSource.value(QStringLiteral("triangleCount")).toInt(), sourceGeometry.triangleCount());
        QCOMPARE(loadedSource.value(QStringLiteral("assetUrl")).toUrl().toLocalFile(), assetPath);
        QCOMPARE(loadedSource.value(QStringLiteral("assetUrl")).toUrl(), loadedDuplicate.value(QStringLiteral("assetUrl")).toUrl());
    }

    void failedSaveKeepsPreviousProjectManifestLoadable()
    {
        QTemporaryDir temporary;
        QVERIFY(temporary.isValid());
        const QString originalPath = temporary.filePath(QStringLiteral("original.stl"));
        const QString changedPath = temporary.filePath(QStringLiteral("changed.stl"));
        const QString projectPath = temporary.filePath(QStringLiteral("Durable.oforge"));
        QVERIFY(writeStl(originalPath));
        QVERIFY(writeStl(changedPath, true));

        MeshGeometry original;
        MeshGeometry changed;
        QVERIFY(original.loadStl(QUrl::fromLocalFile(originalPath)));
        QVERIFY(changed.loadStl(QUrl::fromLocalFile(changedPath)));
        NativeProjectStore store;
        const QVariantMap initial = store.saveProject(QUrl::fromLocalFile(projectPath),
            sceneWith({instance(QStringLiteral("keep"), QStringLiteral("source"), 0, true, 1)}, QStringLiteral("keep")),
            {geometryRecord(QStringLiteral("source"), QStringLiteral("original.stl"), &original)});
        QVERIFY2(initial.value(QStringLiteral("ok")).toBool(), qPrintable(initial.value(QStringLiteral("error")).toString()));
        const QString manifestPath = QDir(projectPath).filePath(QStringLiteral("project.json"));
        const QByteArray priorManifest = fileBytes(manifestPath);

        const QVariantMap failed = store.saveProject(QUrl::fromLocalFile(projectPath),
            sceneWith({instance(QStringLiteral("keep"), QStringLiteral("new-revision"), 0, true, 1)}, QStringLiteral("keep")),
            {geometryRecord(QStringLiteral("new-revision"), QStringLiteral("changed.stl"), &changed),
             geometryRecord(QStringLiteral("unavailable"), QStringLiteral("missing.stl"), nullptr)});
        QVERIFY(!failed.value(QStringLiteral("ok")).toBool());
        QVERIFY(!failed.value(QStringLiteral("error")).toString().isEmpty());
        QCOMPARE(fileBytes(manifestPath), priorManifest);
        QCOMPARE(QDir(QDir(projectPath).filePath(QStringLiteral("meshes"))).entryList({QStringLiteral("*.stl")}, QDir::Files).size(), 2);

        const QVariantMap reopened = store.loadProject(QUrl::fromLocalFile(projectPath));
        QVERIFY2(reopened.value(QStringLiteral("ok")).toBool(), qPrintable(reopened.value(QStringLiteral("error")).toString()));
        QCOMPARE(reopened.value(QStringLiteral("document")).toMap().value(QStringLiteral("selectedInstanceId")).toString(), QStringLiteral("keep"));
    }
};

QTEST_GUILESS_MAIN(NativeProjectStoreTests)
#include "NativeProjectStoreTests.moc"
