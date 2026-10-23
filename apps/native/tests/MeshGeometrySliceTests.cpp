#include "../src/MeshGeometry.h"

#include <QFile>
#include <QTemporaryDir>
#include <QQuaternion>
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

QVector<Triangle> disconnectedIslands()
{
    QVector<Triangle> triangles;
    // First island has two edge-connected triangles.
    triangles.append({QVector3D(0, 0, 0), QVector3D(1, 0, 0), QVector3D(1, 1, 0)});
    triangles.append({QVector3D(0, 0, 0), QVector3D(1, 1, 0), QVector3D(0, 1, 0)});
    // Equal-sized islands share only one vertex with each other.
    triangles.append({QVector3D(10, 0, 0), QVector3D(11, 0, 0), QVector3D(10, 1, 0)});
    triangles.append({QVector3D(10, 0, 0), QVector3D(9, 0, 0), QVector3D(10, -1, 0)});
    return triangles;
}

QVector<Triangle> subdividedGrid(int cells)
{
    QVector<Triangle> triangles;
    triangles.reserve(cells * cells * 2);
    for (int y = 0; y < cells; ++y) {
        for (int x = 0; x < cells; ++x) {
            const float x0 = float(x) / cells;
            const float x1 = float(x + 1) / cells;
            const float y0 = float(y) / cells;
            const float y1 = float(y + 1) / cells;
            appendQuad(triangles, QVector3D(x0, y0, 0), QVector3D(x1, y0, 0),
                       QVector3D(x1, y1, 0), QVector3D(x0, y1, 0));
        }
    }
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
    void copyMeshFromCopiesGeometryAndRevision()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("copy-source.stl"));
        QVERIFY(writeAsciiStl(path, openCube()));

        MeshGeometry source;
        MeshGeometry destination;
        QVERIFY(source.loadStl(QUrl::fromLocalFile(path)));
        QVERIFY(destination.copyMeshFrom(&source));

        QCOMPARE(destination.loaded(), source.loaded());
        QCOMPARE(destination.triangleCount(), source.triangleCount());
        QCOMPARE(destination.dimensions(), source.dimensions());
        QCOMPARE(destination.center(), source.center());
        QCOMPARE(destination.analyzeMesh(), source.analyzeMesh());
        QCOMPARE(destination.fileName(), source.fileName());
        QCOMPARE(destination.revisionId(), source.revisionId());

        const QString preservedRevision = destination.revisionId();
        QVERIFY(!destination.copyMeshFrom(nullptr));
        MeshGeometry unloaded;
        QVERIFY(!destination.copyMeshFrom(&unloaded));
        QCOMPARE(destination.revisionId(), preservedRevision);
    }

    void exportLocalStlPreservesRevisionId()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString sourcePath = directory.filePath(QStringLiteral("local-source.stl"));
        const QString snapshotPath = directory.filePath(QStringLiteral("local-snapshot.stl"));
        QVERIFY(writeAsciiStl(sourcePath, openCube()));

        MeshGeometry source;
        MeshGeometry reloaded;
        QVERIFY(source.loadStl(QUrl::fromLocalFile(sourcePath)));
        const QVariantMap result = source.exportLocalStl(QUrl::fromLocalFile(snapshotPath));
        QVERIFY2(!result.contains(QStringLiteral("error")), qPrintable(result.value(QStringLiteral("error")).toString()));
        QCOMPARE(result.value(QStringLiteral("path")).toString(), snapshotPath);
        QVERIFY(reloaded.loadStl(QUrl::fromLocalFile(snapshotPath)));
        QCOMPARE(reloaded.revisionId(), source.revisionId());
        QCOMPARE(reloaded.triangleCount(), source.triangleCount());
        QCOMPARE(reloaded.dimensions(), source.dimensions());
    }

    void splitsEdgeConnectedIslandsInStableOrder()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("islands.stl"));
        QVERIFY(writeAsciiStl(path, disconnectedIslands()));

        MeshGeometry source;
        MeshGeometry first;
        MeshGeometry second;
        MeshGeometry third;
        QVERIFY(source.loadStl(QUrl::fromLocalFile(path)));
        const QString originalRevision = source.revisionId();
        QCOMPARE(source.connectedComponentCount(), 3);

        const QVariantList outputs{QVariant::fromValue(static_cast<QObject *>(&first)),
                                   QVariant::fromValue(static_cast<QObject *>(&second)),
                                   QVariant::fromValue(static_cast<QObject *>(&third))};
        const QVariantMap result = source.splitConnectedComponents(outputs);
        QVERIFY2(!result.contains(QStringLiteral("error")), qPrintable(result.value(QStringLiteral("error")).toString()));
        const QVariantList parts = result.value(QStringLiteral("parts")).toList();
        QCOMPARE(parts.size(), 3);

        QCOMPARE(first.triangleCount(), 2);
        QCOMPARE(second.triangleCount(), 1);
        QCOMPARE(third.triangleCount(), 1);
        QCOMPARE(parts[0].toMap().value(QStringLiteral("componentIndex")).toInt(), 0);
        QCOMPARE(parts[0].toMap().value(QStringLiteral("triangles")).toInt(), 2);
        QVERIFY(qAbs(second.center().x() - third.center().x()) > 0.5f);
        QVERIFY(second.center().x() > third.center().x());
        const QVector3D scale(1.5f, 0.75f, 1.0f);
        const QVector3D rotation(0, 0, 90);
        const QVector3D sourceOrigin(source.center().x(), source.center().y(),
                                     source.center().z() - source.dimensions().z() * 0.5f);
        const QVector3D secondOrigin(second.center().x(), second.center().y(),
                                     second.center().z() - second.dimensions().z() * 0.5f);
        const QVector3D originDelta = secondOrigin - sourceOrigin;
        const QVector3D scaledDelta(originDelta.x() * scale.x(), originDelta.y() * scale.y(),
                                    originDelta.z() * scale.z());
        const QVector3D expectedCorrection = -originDelta
            + QQuaternion::fromEulerAngles(rotation).rotatedVector(scaledDelta);
        const QVector3D correction = source.instanceOffsetCorrection(&second, scale, rotation);
        QVERIFY((correction - expectedCorrection).length() < 1.0e-5f);
        const QVector3D point = second.m_trianglePoints.front();
        const auto worldPoint = [&scale, &rotation](const QVector3D &origin, const QVector3D &vertex) {
            const QVector3D local = vertex - origin;
            const QVector3D scaled(local.x() * scale.x(), local.y() * scale.y(), local.z() * scale.z());
            return origin + QQuaternion::fromEulerAngles(rotation).rotatedVector(scaled);
        };
        QVERIFY((worldPoint(sourceOrigin, point) - (correction + worldPoint(secondOrigin, point))).length() < 1.0e-5f);
        QCOMPARE(source.revisionId(), originalRevision);
        QCOMPARE(source.triangleCount(), 4);
    }

    void doesNotJoinTrianglesTouchingOnlyAtAVertex()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("vertex-contact.stl"));
        QVector<Triangle> triangles{
            {QVector3D(0, 0, 0), QVector3D(1, 0, 0), QVector3D(0, 1, 0)},
            {QVector3D(0, 0, 0), QVector3D(-1, 0, 0), QVector3D(0, -1, 0)},
        };
        QVERIFY(writeAsciiStl(path, triangles));

        MeshGeometry source;
        QVERIFY(source.loadStl(QUrl::fromLocalFile(path)));
        QCOMPARE(source.connectedComponentCount(), 2);
    }

    void rejectsInvalidComponentOutputWithoutChangingSource()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("islands.stl"));
        QVERIFY(writeAsciiStl(path, disconnectedIslands()));

        MeshGeometry source;
        QVERIFY(source.loadStl(QUrl::fromLocalFile(path)));
        const QString originalRevision = source.revisionId();
        const QVariantMap result = source.splitConnectedComponents({});
        QVERIFY(result.contains(QStringLiteral("error")));
        QCOMPARE(source.revisionId(), originalRevision);
        QCOMPARE(source.triangleCount(), 4);
    }

    void simplifiesSubdividedMeshAndPreservesSource()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("grid.stl"));
        QVERIFY(writeAsciiStl(path, subdividedGrid(16)));

        MeshGeometry source;
        MeshGeometry output;
        QVERIFY(source.loadStl(QUrl::fromLocalFile(path)));
        const int sourceTriangles = source.triangleCount();
        const QString sourceRevision = source.revisionId();
        const QVariantMap result = source.simplifyMesh(50.0, &output);
        QVERIFY2(!result.contains(QStringLiteral("error")), qPrintable(result.value(QStringLiteral("error")).toString()));

        QVERIFY(output.loaded());
        QVERIFY(output.triangleCount() < sourceTriangles);
        QCOMPARE(source.triangleCount(), sourceTriangles);
        QCOMPARE(source.revisionId(), sourceRevision);
        QCOMPARE(result.value(QStringLiteral("originalTriangles")).toInt(), sourceTriangles);
        QCOMPARE(result.value(QStringLiteral("resultTriangles")).toInt(), output.triangleCount());
        QVERIFY(result.value(QStringLiteral("actualReductionPercent")).toDouble() > 0.0);
        QCOMPARE(result.value(QStringLiteral("degenerateTriangles")).toInt(), 0);
        for (const QVector3D &point : output.m_trianglePoints)
            QVERIFY(std::isfinite(point.x()) && std::isfinite(point.y()) && std::isfinite(point.z()));
    }

    void rejectsInvalidSimplificationTargetWithoutChangingOutput()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("open-sheet.stl"));
        QVERIFY(writeAsciiStl(path, openSquareSheet()));

        MeshGeometry source;
        MeshGeometry output;
        QVERIFY(source.loadStl(QUrl::fromLocalFile(path)));
        QVERIFY(output.loadStl(QUrl::fromLocalFile(path)));
        const QString outputRevision = output.revisionId();
        const QVariantMap result = source.simplifyMesh(0.0, &output);
        QVERIFY(result.contains(QStringLiteral("error")));
        QCOMPARE(output.revisionId(), outputRevision);
        QCOMPARE(output.triangleCount(), 2);
    }

    void reportsBestEffortWhenTargetCannotBeReached()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("single-triangle.stl"));
        const QVector<Triangle> triangles{{QVector3D(0, 0, 0), QVector3D(1, 0, 0), QVector3D(0, 1, 0)}};
        QVERIFY(writeAsciiStl(path, triangles));

        MeshGeometry source;
        MeshGeometry output;
        QVERIFY(source.loadStl(QUrl::fromLocalFile(path)));
        const QVariantMap result = source.simplifyMesh(95.0, &output);
        QVERIFY2(!result.contains(QStringLiteral("error")), qPrintable(result.value(QStringLiteral("error")).toString()));
        QCOMPARE(output.triangleCount(), 1);
        QVERIFY(result.value(QStringLiteral("actualReductionPercent")).toDouble() < 95.0);
    }

    void rejectsOverLimitSimplificationWithoutChangingOutput()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("output.stl"));
        QVERIFY(writeAsciiStl(path, openSquareSheet()));

        MeshGeometry source;
        source.m_loaded = true;
        source.m_trianglePoints.resize(3'000'003); // 1,000,001 triangles; rejected before geometry access.
        MeshGeometry output;
        QVERIFY(output.loadStl(QUrl::fromLocalFile(path)));
        const QString outputRevision = output.revisionId();
        const QVariantMap result = source.simplifyMesh(50.0, &output);
        QVERIFY(result.contains(QStringLiteral("error")));
        QCOMPARE(output.revisionId(), outputRevision);
        QCOMPARE(output.triangleCount(), 2);
    }

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
