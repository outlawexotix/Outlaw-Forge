#include "../src/MeshGeometry.h"

#include <QFile>
#include <QTemporaryDir>
#include <QTextStream>
#include <QVector2D>
#include <QtTest>
#include <algorithm>
#include <array>
#include <limits>

namespace {
using Triangle = std::array<QVector3D, 3>;

void appendQuad(QVector<Triangle> &triangles, const QVector3D &a, const QVector3D &b,
                const QVector3D &c, const QVector3D &d)
{
    triangles.append({a, b, c});
    triangles.append({a, c, d});
}

QVector<Triangle> hollowSquareTube()
{
    QVector<Triangle> triangles;
    const QVector<QVector2D> outer{{-2, -2}, {2, -2}, {2, 2}, {-2, 2}};
    const QVector<QVector2D> inner{{-1, -1}, {1, -1}, {1, 1}, {-1, 1}};
    const auto point = [](const QVector2D &p, float z) { return QVector3D(p.x(), p.y(), z); };
    for (int i = 0; i < 4; ++i) {
        const int next = (i + 1) % 4;
        // Top and bottom annular surfaces.
        appendQuad(triangles, point(outer[i], 1), point(outer[next], 1), point(inner[next], 1), point(inner[i], 1));
        appendQuad(triangles, point(outer[next], -1), point(outer[i], -1), point(inner[i], -1), point(inner[next], -1));
        // Outer and inner vertical walls.
        appendQuad(triangles, point(outer[i], -1), point(outer[next], -1), point(outer[next], 1), point(outer[i], 1));
        appendQuad(triangles, point(inner[next], -1), point(inner[i], -1), point(inner[i], 1), point(inner[next], 1));
    }
    return triangles;
}

QVector<Triangle> openSquareSheet()
{
    QVector<Triangle> triangles;
    appendQuad(triangles, QVector3D(-1, -1, 0), QVector3D(1, -1, 0),
               QVector3D(1, 1, 0), QVector3D(-1, 1, 0));
    return triangles;
}

QVector<Triangle> openCube()
{
    QVector<Triangle> triangles;
    const QVector3D a(-1, -1, 0), b(1, -1, 0), c(1, 1, 0), d(-1, 1, 0);
    const QVector3D e(-1, -1, 2), f(1, -1, 2), g(1, 1, 2), h(-1, 1, 2);
    appendQuad(triangles, a, d, c, b); // bottom
    appendQuad(triangles, a, b, f, e);
    appendQuad(triangles, b, c, g, f);
    appendQuad(triangles, c, d, h, g);
    appendQuad(triangles, d, a, e, h);
    return triangles;
}

bool writeAsciiStl(const QString &path, const QVector<Triangle> &triangles)
{
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Text))
        return false;
    QTextStream stream(&file);
    stream << "solid hollow_tube\n";
    for (const Triangle &triangle : triangles) {
        stream << " facet normal 0 0 1\n  outer loop\n";
        for (const QVector3D &point : triangle)
            stream << "   vertex " << point.x() << ' ' << point.y() << ' ' << point.z() << "\n";
        stream << "  endloop\n endfacet\n";
    }
    stream << "endsolid hollow_tube\n";
    return stream.status() == QTextStream::Ok;
}

double horizontalCapArea(const QVector<QVector3D> &points)
{
    double area = 0.0;
    for (qsizetype i = 0; i + 2 < points.size(); i += 3) {
        const QVector3D &a = points[i];
        const QVector3D &b = points[i + 1];
        const QVector3D &c = points[i + 2];
        if (qAbs(a.z()) < 1e-5 && qAbs(b.z()) < 1e-5 && qAbs(c.z()) < 1e-5)
            area += 0.5 * QVector3D::crossProduct(b - a, c - a).length();
    }
    return area;
}

double signedVolume(const QVector<QVector3D> &points)
{
    double volume = 0.0;
    for (qsizetype i = 0; i + 2 < points.size(); i += 3)
        volume += QVector3D::dotProduct(points[i], QVector3D::crossProduct(points[i + 1], points[i + 2])) / 6.0;
    return volume;
}
}

class MeshGeometrySliceTests : public QObject
{
    Q_OBJECT

private slots:
    void slicesHollowMeshAndKeepsBothSectionsClosed()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("hollow-tube.stl"));
        QVERIFY(writeAsciiStl(path, hollowSquareTube()));

        const QVector<QPair<QVector3D, QVector3D>> planes{
            {QVector3D(0, 0, 0), QVector3D(0, 0, 1)},
            {QVector3D(0, 0, 0), QVector3D(0.37f, -0.21f, 1).normalized()},
            // This plane passes through shared mesh vertices and triangulation
            // diagonals. Those contacts must still produce closed contours.
            {QVector3D(0, 0, 0), QVector3D(1, 1, 0).normalized()},
        };
        for (const auto &plane : planes) {
            const QVector3D &point = plane.first;
            const QVector3D &normal = plane.second;
            MeshGeometry first;
            MeshGeometry second;
            MeshGeometry source;
            QVERIFY(source.loadStl(QUrl::fromLocalFile(path)));
            const QVariantMap sourceMetrics = source.analyzeMesh();
            QCOMPARE(sourceMetrics.value(QStringLiteral("boundaryEdges")).toInt(), 0);
            QCOMPARE(sourceMetrics.value(QStringLiteral("nonManifoldEdges")).toInt(), 0);
            const QVariantMap result = source.sliceByPlane(point, normal, true, &first, &second);
            QVERIFY2(!result.contains(QStringLiteral("error")), qPrintable(result.value(QStringLiteral("error")).toString()));
            QVERIFY(result.value(QStringLiteral("capped")).toBool());
            QVERIFY(result.value(QStringLiteral("outputsWatertight")).toBool());
            QVERIFY(second.loaded());

            if (normal == QVector3D(0, 0, 1)) {
                // The cut section is an annulus: 4x4 outer square minus
                // 2x2 inner square. This catches caps that fill the hole.
                QVERIFY(qAbs(horizontalCapArea(first.m_trianglePoints) - 12.0) < 1e-3);
                QVERIFY(qAbs(horizontalCapArea(second.m_trianglePoints) - 12.0) < 1e-3);
            }

            const QVariantMap firstMetrics = first.analyzeMesh();
            const QVariantMap secondMetrics = second.analyzeMesh();
            for (const QVariantMap &metrics : {firstMetrics, secondMetrics}) {
                QCOMPARE(metrics.value(QStringLiteral("boundaryEdges")).toInt(), 0);
                QCOMPARE(metrics.value(QStringLiteral("nonManifoldEdges")).toInt(), 0);
                QCOMPARE(metrics.value(QStringLiteral("degenerateTriangles")).toInt(), 0);
            }
        }
    }

    void separatesOpenMeshWhenCutFacesCannotBeCapped()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("open-sheet.stl"));
        QVERIFY(writeAsciiStl(path, openSquareSheet()));

        MeshGeometry first;
        MeshGeometry second;
        MeshGeometry source;
        QVERIFY(source.loadStl(QUrl::fromLocalFile(path)));
        const QVariantMap result = source.sliceByPlane(QVector3D(0, 0, 0), QVector3D(1, 0, 0), true, &first, &second);

        QVERIFY2(!result.contains(QStringLiteral("error")), qPrintable(result.value(QStringLiteral("error")).toString()));
        QVERIFY(!result.value(QStringLiteral("capped")).toBool());
        QVERIFY(!result.value(QStringLiteral("warning")).toString().isEmpty());
        QVERIFY(second.loaded());
        QVERIFY(result.value(QStringLiteral("triangles")).toInt() > 0);
        QVERIFY(result.value(QStringLiteral("oppositeTriangles")).toInt() > 0);
    }

    void slicingKeepsTheImportedSourceMeshUnchanged()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("open-sheet.stl"));
        QVERIFY(writeAsciiStl(path, openSquareSheet()));

        MeshGeometry source;
        MeshGeometry kept;
        MeshGeometry opposite;
        QVERIFY(source.loadStl(QUrl::fromLocalFile(path)));
        const int sourceTriangleCount = source.triangleCount();
        const QString sourceRevisionId = source.revisionId();
        const QVariantMap result = source.sliceByPlane(QVector3D(0, 0, 0), QVector3D(1, 0, 0), true, &kept, &opposite);

        QVERIFY2(!result.contains(QStringLiteral("error")), qPrintable(result.value(QStringLiteral("error")).toString()));
        QCOMPARE(source.triangleCount(), sourceTriangleCount);
        QCOMPARE(source.revisionId(), sourceRevisionId);
        QCOMPARE(result.value(QStringLiteral("sourceRevisionId")).toString(), sourceRevisionId);
        QCOMPARE(result.value(QStringLiteral("keptRevisionId")).toString(), kept.revisionId());
        QVERIFY(kept.loaded());
    }

    void exportsMeshToBinaryStlWithoutChangingSource()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString sourcePath = directory.filePath(QStringLiteral("hollow-tube.stl"));
        const QString exportedPath = directory.filePath(QStringLiteral("cut-section.stl"));
        QVERIFY(writeAsciiStl(sourcePath, hollowSquareTube()));

        MeshGeometry source;
        QVERIFY(source.loadStl(QUrl::fromLocalFile(sourcePath)));
        const QString originalRevision = source.revisionId();
        const int originalTriangleCount = source.triangleCount();

        const QVector3D offset(10, -3, 5);
        const QVector3D rotation(0, 0, 90);
        const QVector3D scale(-2, 1, 0.5f);
        const QVariantMap exportResult = source.exportStl(QUrl::fromLocalFile(exportedPath), offset, rotation, scale);
        QVERIFY2(!exportResult.contains(QStringLiteral("error")),
                 qPrintable(exportResult.value(QStringLiteral("error")).toString()));
        QCOMPARE(exportResult.value(QStringLiteral("triangles")).toInt(), originalTriangleCount);

        QFile exported(exportedPath);
        QVERIFY(exported.open(QIODevice::ReadOnly));
        QCOMPARE(exported.size(), qint64(84 + 50 * originalTriangleCount));
        MeshGeometry roundTrip;
        QVERIFY(roundTrip.loadStl(QUrl::fromLocalFile(exportedPath)));
        QCOMPARE(roundTrip.triangleCount(), originalTriangleCount);
        QVERIFY((roundTrip.dimensions() - QVector3D(4, 8, 1)).length() < 1.0e-4f);
        QVERIFY((roundTrip.center() - QVector3D(10, -3, 4.5f)).length() < 1.0e-4f);
        QCOMPARE(source.revisionId(), originalRevision);
        QVERIFY(roundTrip.analyzeMesh().value(QStringLiteral("watertight")).toBool());
        QVERIFY(signedVolume(roundTrip.m_trianglePoints) > 0.0);
    }

    void keepsCutCapsWhenUnrelatedSourceGeometryIsOpen()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("tube-with-open-island.stl"));
        QVector<Triangle> triangles = hollowSquareTube();
        // This disconnected open island does not intersect the cut plane. Its
        // boundary must not cause valid caps on the tube's cut contours to be
        // discarded.
        triangles.append({QVector3D(4, 0, 0.5f), QVector3D(5, 0, 0.5f), QVector3D(4, 1, 0.5f)});
        QVERIFY(writeAsciiStl(path, triangles));

        MeshGeometry first;
        MeshGeometry second;
        MeshGeometry source;
        QVERIFY(source.loadStl(QUrl::fromLocalFile(path)));
        const QVariantMap result = source.sliceByPlane(QVector3D(0, 0, 0), QVector3D(0, 0, 1), true, &first, &second);

        QVERIFY2(!result.contains(QStringLiteral("error")), qPrintable(result.value(QStringLiteral("error")).toString()));
        QVERIFY(result.value(QStringLiteral("capped")).toBool());
        QVERIFY(!result.value(QStringLiteral("outputsWatertight")).toBool());
        QVERIFY(!result.value(QStringLiteral("warning")).toString().isEmpty());
        QVERIFY(second.loaded());
        QVERIFY(result.value(QStringLiteral("triangles")).toInt() > 0);
        QVERIFY(result.value(QStringLiteral("oppositeTriangles")).toInt() > 0);
    }

    void repairFillsSimpleBoundaryLoopLocally()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("open-cube.stl"));
        QVERIFY(writeAsciiStl(path, openCube()));

        MeshGeometry mesh;
        QVERIFY(mesh.loadStl(QUrl::fromLocalFile(path)));
        QCOMPARE(mesh.analyzeMesh().value(QStringLiteral("boundaryEdges")).toInt(), 4);

        const QVariantMap result = mesh.repairMesh(0.001);

        QVERIFY2(!result.contains(QStringLiteral("error")), qPrintable(result.value(QStringLiteral("error")).toString()));
        QCOMPARE(result.value(QStringLiteral("holesFilled")).toInt(), 1);
        QCOMPARE(mesh.analyzeMesh().value(QStringLiteral("boundaryEdges")).toInt(), 0);
        QCOMPARE(mesh.analyzeMesh().value(QStringLiteral("nonManifoldEdges")).toInt(), 0);
        QVERIFY(signedVolume(mesh.m_trianglePoints) > 0.0);
    }

    void autoOrientRunsLocallyAndPlacesMeshOnBuildPlate()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("hollow-tube.stl"));
        QVERIFY(writeAsciiStl(path, hollowSquareTube()));

        MeshGeometry mesh;
        QVERIFY(mesh.loadStl(QUrl::fromLocalFile(path)));
        const int originalTriangleCount = mesh.triangleCount();
        const QVariantMap result = mesh.autoOrient();

        QVERIFY2(!result.contains(QStringLiteral("error")), qPrintable(result.value(QStringLiteral("error")).toString()));
        QVERIFY(result.value(QStringLiteral("candidateCount")).toInt() > 1);
        QCOMPARE(mesh.triangleCount(), originalTriangleCount);
        QVERIFY(mesh.analyzeMesh().value(QStringLiteral("watertight")).toBool());
        float minimumZ = std::numeric_limits<float>::infinity();
        for (const QVector3D &point : mesh.m_trianglePoints)
            minimumZ = std::min(minimumZ, point.z());
        QVERIFY(qAbs(minimumZ) < 1.0e-3f);
    }
};

QTEST_GUILESS_MAIN(MeshGeometrySliceTests)
#include "MeshGeometrySliceTests.moc"
