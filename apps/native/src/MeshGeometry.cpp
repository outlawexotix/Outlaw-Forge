#include "MeshGeometry.h"

#include <QFile>
#include <QFileInfo>
#include <QCryptographicHash>
#include <QSaveFile>
#include <QDataStream>
#include <QRegularExpression>
#include <QXmlStreamReader>
#include <QtCore/private/qzipreader_p.h>
#include <QTextStream>
#include <QtEndian>
#include <array>
#include <QHash>
#include <QSet>
#include <QQuaternion>
#include <QVector2D>
#include <QtMath>
#include <QVariantMap>
#include <algorithm>
#include <bit>
#include <cmath>
#include <limits>
#include <mapbox/earcut.hpp>
#include <vector>

namespace {
struct Vertex {
    float position[3];
    float normal[3];
};

struct ExactPositionKey {
    quint32 x;
    quint32 y;
    quint32 z;
    bool operator==(const ExactPositionKey &) const = default;
};

size_t qHash(const ExactPositionKey &key, size_t seed = 0) noexcept
{
    return qHashMulti(seed, key.x, key.y, key.z);
}

struct GridCellKey {
    qint64 x;
    qint64 y;
    qint64 z;
    bool operator==(const GridCellKey &) const = default;
};

size_t qHash(const GridCellKey &key, size_t seed = 0) noexcept
{
    return qHashMulti(seed, key.x, key.y, key.z);
}

float littleFloat(const uchar *bytes)
{
    return std::bit_cast<float>(qFromLittleEndian<quint32>(bytes));
}

bool finite(const QVector3D &v)
{
    return std::isfinite(v.x()) && std::isfinite(v.y()) && std::isfinite(v.z());
}

QString vertexKey(const QVector3D &point, double tolerance)
{
    const auto q = [tolerance](float value) { return qlonglong(std::llround(double(value) / tolerance)); };
    return QStringLiteral("%1:%2:%3").arg(q(point.x())).arg(q(point.y())).arg(q(point.z()));
}

QVector<QVector<qsizetype>> connectedTriangleGroups(const QVector<QVector3D> &points, double tolerance)
{
    const qsizetype triangleCount = points.size() / 3;
    QVector<qsizetype> parents(triangleCount);
    for (qsizetype i = 0; i < triangleCount; ++i)
        parents[i] = i;

    const auto root = [&parents](qsizetype index) {
        qsizetype current = index;
        while (parents[current] != current) {
            parents[current] = parents[parents[current]];
            current = parents[current];
        }
        return current;
    };
    const auto join = [&parents, &root](qsizetype left, qsizetype right) {
        const qsizetype leftRoot = root(left);
        const qsizetype rightRoot = root(right);
        if (leftRoot != rightRoot)
            parents[std::max(leftRoot, rightRoot)] = std::min(leftRoot, rightRoot);
    };

    QHash<QString, qsizetype> firstTriangleByEdge;
    firstTriangleByEdge.reserve(triangleCount * 2);
    for (qsizetype triangle = 0; triangle < triangleCount; ++triangle) {
        const qsizetype offset = triangle * 3;
        for (int edge = 0; edge < 3; ++edge) {
            QString first = vertexKey(points[offset + edge], tolerance);
            QString second = vertexKey(points[offset + (edge + 1) % 3], tolerance);
            if (second < first)
                std::swap(first, second);
            const QString edgeKey = first + QLatin1Char('|') + second;
            const auto it = firstTriangleByEdge.constFind(edgeKey);
            if (it == firstTriangleByEdge.cend())
                firstTriangleByEdge.insert(edgeKey, triangle);
            else
                join(triangle, it.value());
        }
    }

    QHash<qsizetype, qsizetype> groupIndexByRoot;
    QVector<QVector<qsizetype>> groups;
    QVector<qsizetype> firstTriangles;
    for (qsizetype triangle = 0; triangle < triangleCount; ++triangle) {
        const qsizetype triangleRoot = root(triangle);
        auto it = groupIndexByRoot.constFind(triangleRoot);
        if (it == groupIndexByRoot.cend()) {
            const qsizetype groupIndex = groups.size();
            groupIndexByRoot.insert(triangleRoot, groupIndex);
            groups.append(QVector<qsizetype>{triangle});
            firstTriangles.append(triangle);
        } else {
            groups[it.value()].append(triangle);
        }
    }

    QVector<qsizetype> order(groups.size());
    for (qsizetype i = 0; i < order.size(); ++i)
        order[i] = i;
    std::sort(order.begin(), order.end(), [&groups, &firstTriangles](qsizetype left, qsizetype right) {
        if (groups[left].size() != groups[right].size())
            return groups[left].size() > groups[right].size();
        return firstTriangles[left] < firstTriangles[right];
    });
    QVector<QVector<qsizetype>> sortedGroups;
    sortedGroups.reserve(groups.size());
    for (qsizetype index : order)
        sortedGroups.append(std::move(groups[index]));
    return sortedGroups;
}

QVector<QVector3D> clusteredCandidate(const QVector<QVector3D> &uniquePoints,
                                      const QVector<qsizetype> &pointIndices,
                                      const QVector3D &minimum, double cellSize)
{
    struct Cell {
        QVector3D sum;
        int count = 0;
    };
    const auto keyFor = [cellSize, &minimum](const QVector3D &point) {
        const auto cell = [cellSize](float value, float origin) {
            return qlonglong(std::floor((double(value) - origin) / cellSize));
        };
        return GridCellKey{cell(point.x(), minimum.x()), cell(point.y(), minimum.y()),
                           cell(point.z(), minimum.z())};
    };

    QVector<qsizetype> representativeIndexByPoint;
    representativeIndexByPoint.reserve(uniquePoints.size());
    QHash<GridCellKey, qsizetype> cellIndices;
    cellIndices.reserve(uniquePoints.size());
    QVector<Cell> cells;
    cells.reserve(uniquePoints.size());
    for (const QVector3D &point : uniquePoints) {
        const GridCellKey key = keyFor(point);
        auto it = cellIndices.constFind(key);
        qsizetype cellIndex;
        if (it == cellIndices.cend()) {
            cellIndex = cells.size();
            cellIndices.insert(key, cellIndex);
            cells.append(Cell{});
        } else {
            cellIndex = it.value();
        }
        representativeIndexByPoint.append(cellIndex);
        Cell &cell = cells[cellIndex];
        cell.sum += point;
        ++cell.count;
    }
    QVector<QVector3D> representatives;
    representatives.reserve(cells.size());
    for (const Cell &cell : cells)
        representatives.append(cell.sum / float(cell.count));

    QVector<QVector3D> result;
    result.reserve(pointIndices.size());
    for (qsizetype i = 0; i + 2 < pointIndices.size(); i += 3) {
        const QVector3D a = representatives[representativeIndexByPoint[pointIndices[i]]];
        const QVector3D b = representatives[representativeIndexByPoint[pointIndices[i + 1]]];
        const QVector3D c = representatives[representativeIndexByPoint[pointIndices[i + 2]]];
        if (QVector3D::crossProduct(b - a, c - a).lengthSquared() <= 1.0e-16f)
            continue;
        result.append(a);
        result.append(b);
        result.append(c);
    }
    return result;
}

bool triangulateCapLoops(const QVector<QVector<QVector3D>> &loops, const QVector3D &planeNormal,
                         bool positiveSide, QVector<QVector3D> *cap, QString *error)
{
    QVector<QVector<QVector3D>> cleanLoops = loops;
    const QVector3D u = QVector3D::crossProduct(planeNormal, std::abs(planeNormal.z()) < 0.9f
                                                     ? QVector3D(0, 0, 1) : QVector3D(0, 1, 0)).normalized();
    const QVector3D v = QVector3D::crossProduct(planeNormal, u).normalized();
    QVector<QVector<QVector2D>> projectedLoops;
    projectedLoops.reserve(loops.size());
    for (const auto &loop : loops) {
        QVector<QVector2D> projected;
        projected.reserve(loop.size());
        for (const QVector3D &point : loop)
            projected.append(QVector2D(QVector3D::dotProduct(point, u), QVector3D::dotProduct(point, v)));
        projectedLoops.append(projected);
    }

    // Clipping a triangulated surface can leave many points along a straight
    // contour edge. Keep those samples in the cap so every cap boundary edge
    // matches the corresponding clipped surface edges. Earcut handles
    // collinear contour vertices; removing them creates T-junctions.
    for (qsizetype loopIndex = 0; loopIndex < projectedLoops.size(); ++loopIndex) {
        auto &projected = projectedLoops[loopIndex];
        auto &points = cleanLoops[loopIndex];
        if (projected.size() < 3)
            continue;
        float extent = 1.0f;
        for (const auto &p : projected)
            extent = std::max(extent, std::max(std::abs(p.x()), std::abs(p.y())));
        const float tolerance = std::max(1.0e-6f, extent * 1.0e-7f);
        QVector<QVector2D> clean2;
        QVector<QVector3D> clean3;
        for (qsizetype i = 0; i < projected.size(); ++i) {
            if (!clean2.isEmpty() && (projected[i] - clean2.back()).lengthSquared() <= tolerance * tolerance)
                continue;
            clean2.append(projected[i]);
            clean3.append(points[i]);
        }
        if (clean2.size() > 1 && (clean2.front() - clean2.back()).lengthSquared() <= tolerance * tolerance) {
            clean2.removeLast();
            clean3.removeLast();
        }
        projected = std::move(clean2);
        points = std::move(clean3);
    }

    using Point = std::array<double, 2>;
    using Polygon = std::vector<std::vector<Point>>;
    const auto signedArea = [](const QVector<QVector2D> &ring) {
        double area = 0;
        for (qsizetype i = 0; i < ring.size(); ++i) {
            const auto &a = ring[i];
            const auto &b = ring[(i + 1) % ring.size()];
            area += double(a.x()) * b.y() - double(b.x()) * a.y();
        }
        return area * 0.5;
    };
    const auto contains = [](const QVector<QVector2D> &ring, const QVector2D &point) {
        bool inside = false;
        for (qsizetype i = 0, j = ring.size() - 1; i < ring.size(); j = i++) {
            const auto &a = ring[i];
            const auto &b = ring[j];
            if ((a.y() > point.y()) != (b.y() > point.y())
                && point.x() < (b.x() - a.x()) * (point.y() - a.y()) / (b.y() - a.y()) + a.x())
                inside = !inside;
        }
        return inside;
    };
    QVector<double> areas(projectedLoops.size());
    QVector<int> parents(projectedLoops.size(), -1);
    for (qsizetype i = 0; i < projectedLoops.size(); ++i) {
        if (projectedLoops[i].size() < 3) {
            *error = QStringLiteral("The cut contour is degenerate and cannot be capped.");
            return false;
        }
        areas[i] = std::abs(signedArea(projectedLoops[i]));
    }
    for (qsizetype i = 0; i < projectedLoops.size(); ++i) {
        double parentArea = std::numeric_limits<double>::infinity();
        for (qsizetype j = 0; j < projectedLoops.size(); ++j) {
            if (i != j && areas[j] > areas[i] && areas[j] < parentArea
                && contains(projectedLoops[j], projectedLoops[i].front())) {
                parents[i] = int(j);
                parentArea = areas[j];
            }
        }
    }
    QVector<int> depths(projectedLoops.size(), 0);
    for (qsizetype i = 0; i < parents.size(); ++i) {
        int parent = parents[i];
        int guard = 0;
        while (parent >= 0 && guard++ < parents.size()) {
            ++depths[i];
            parent = parents[parent];
        }
        if (guard > parents.size()) {
            *error = QStringLiteral("The cut contours have an invalid nesting relationship.");
            return false;
        }
    }

    const QVector3D desiredNormal = positiveSide ? -planeNormal : planeNormal;
    for (qsizetype shell = 0; shell < projectedLoops.size(); ++shell) {
        if (depths[shell] % 2 != 0)
            continue;
        Polygon polygon;
        QVector<int> ringLoops{int(shell)};
        for (qsizetype i = 0; i < parents.size(); ++i)
            if (parents[i] == shell && depths[i] == depths[shell] + 1)
                ringLoops.append(int(i));
        for (int ringIndex : ringLoops) {
            std::vector<Point> ring;
            ring.reserve(size_t(projectedLoops[ringIndex].size()));
            for (const QVector2D &point : projectedLoops[ringIndex])
                ring.push_back({double(point.x()), double(point.y())});
            polygon.push_back(std::move(ring));
        }
        const std::vector<uint32_t> indices = mapbox::earcut<uint32_t>(polygon);
        if (indices.empty() || indices.size() % 3 != 0) {
            *error = QStringLiteral("The cut contours could not be triangulated safely.");
            return false;
        }
        QVector<QVector3D> flattenedPoints;
        QVector<QVector2D> flattenedProjected;
        for (int ringIndex : ringLoops) {
            flattenedPoints += cleanLoops[ringIndex];
            flattenedProjected += projectedLoops[ringIndex];
        }
        for (size_t i = 0; i < indices.size(); i += 3) {
            QVector3D p[3];
            QVector2D q[3];
            for (int corner = 0; corner < 3; ++corner) {
                const int index = int(indices[i + size_t(corner)]);
                p[corner] = flattenedPoints[index];
                q[corner] = flattenedProjected[index];
            }
            const QVector3D center = (p[0] + p[1] + p[2]) / 3.0f;
            const QVector2D center2 = (q[0] + q[1] + q[2]) / 3.0f;
            QVector<QVector3D> perimeter;
            for (int edge = 0; edge < 3; ++edge) {
                const int next = (edge + 1) % 3;
                const QVector2D delta = q[next] - q[edge];
                const float lengthSquared = delta.lengthSquared();
                QVector<QPair<float, int>> splitPoints;
                for (int pointIndex = 0; pointIndex < flattenedProjected.size(); ++pointIndex) {
                    const QVector2D offset = flattenedProjected[pointIndex] - q[edge];
                    const float t = lengthSquared > 0 ? QVector2D::dotProduct(offset, delta) / lengthSquared : 0;
                    if (t <= 1.0e-6f || t >= 1.0f - 1.0e-6f)
                        continue;
                    const float distance = std::abs(delta.x() * offset.y() - delta.y() * offset.x());
                    if (distance <= 1.0e-6f * std::max(1.0f, delta.length()))
                        splitPoints.append({t, pointIndex});
                }
                std::sort(splitPoints.begin(), splitPoints.end(), [](const auto &a, const auto &b) {
                    return a.first < b.first;
                });
                perimeter.append(p[edge]);
                for (const auto &split : splitPoints)
                    if ((perimeter.back() - flattenedPoints[split.second]).lengthSquared() > 1.0e-12f)
                        perimeter.append(flattenedPoints[split.second]);
            }
            for (qsizetype edge = 0; edge < perimeter.size(); ++edge) {
                QVector3D a = perimeter[edge];
                QVector3D b = perimeter[(edge + 1) % perimeter.size()];
                if (QVector3D::dotProduct(QVector3D::crossProduct(b - a, center - a), desiredNormal) < 0)
                    std::swap(a, b);
                cap->append(a);
                cap->append(b);
                cap->append(center);
            }
        }
    }
    return true;
}

QVariantMap meshMetrics(const QVector<QVector3D> &points, double tolerance)
{
    QHash<QString, quint32> ids;
    QVector<QVector3D> uniqueVertices;
    QVector<quint32> indices;
    indices.reserve(points.size());
    for (const QVector3D &point : points) {
        const QString key = vertexKey(point, tolerance);
        auto it = ids.constFind(key);
        if (it == ids.cend()) {
            const quint32 id = quint32(uniqueVertices.size());
            ids.insert(key, id);
            uniqueVertices.append(point);
            indices.append(id);
        } else {
            indices.append(it.value());
        }
    }

    int degenerate = 0;
    QHash<quint64, int> edgeUse;
    for (qsizetype i = 0; i + 2 < indices.size(); i += 3) {
        const quint32 a = indices[i], b = indices[i + 1], c = indices[i + 2];
        if (a == b || b == c || c == a
            || QVector3D::crossProduct(points[i + 1] - points[i], points[i + 2] - points[i]).lengthSquared() <= 1.0e-20f)
            ++degenerate;
        const quint32 tri[] = {a, b, c};
        for (int edge = 0; edge < 3; ++edge) {
            quint32 lo = tri[edge], hi = tri[(edge + 1) % 3];
            if (lo > hi) std::swap(lo, hi);
            edgeUse[(quint64(lo) << 32) | hi] += 1;
        }
    }
    int boundary = 0, nonManifold = 0;
    for (auto it = edgeUse.cbegin(); it != edgeUse.cend(); ++it) {
        const int uses = it.value();
        if (uses == 1) ++boundary;
        else if (uses > 2) ++nonManifold;
    }
    return {{QStringLiteral("triangles"), points.size() / 3},
            {QStringLiteral("vertices"), uniqueVertices.size()},
            {QStringLiteral("degenerateTriangles"), degenerate},
            {QStringLiteral("boundaryEdges"), boundary},
            {QStringLiteral("nonManifoldEdges"), nonManifold},
            {QStringLiteral("watertight"), boundary == 0 && nonManifold == 0 && degenerate == 0}};
}
}

MeshGeometry::MeshGeometry(QQuick3DObject *parent) : QQuick3DGeometry(parent)
{
    setPrimitiveType(PrimitiveType::Triangles);
    setStride(sizeof(Vertex));
    addAttribute(Attribute::PositionSemantic, offsetof(Vertex, position), Attribute::F32Type);
    addAttribute(Attribute::NormalSemantic, offsetof(Vertex, normal), Attribute::F32Type);
}

bool MeshGeometry::loadStl(const QUrl &url)
{
    const QString path = url.isLocalFile() ? url.toLocalFile() : url.toString();
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        emit loadFailed(QStringLiteral("Could not open the selected STL file."));
        return false;
    }
    const QByteArray bytes = file.readAll();
    if (bytes.size() < 15) {
        emit loadFailed(QStringLiteral("The selected file is too small to contain an STL mesh."));
        return false;
    }

    QVector<QVector3D> points;
    const bool hasBinaryHeader = bytes.size() >= 84;
    quint32 triangleCount = 0;
    if (hasBinaryHeader)
        triangleCount = qFromLittleEndian<quint32>(reinterpret_cast<const uchar *>(bytes.constData() + 80));
    const bool binary = hasBinaryHeader && triangleCount > 0
        && quint64(84) + quint64(triangleCount) * 50 <= quint64(bytes.size());

    if (binary) {
        if (triangleCount > 20'000'000) {
            emit loadFailed(QStringLiteral("The STL exceeds the native viewport triangle limit."));
            return false;
        }
        points.reserve(int(triangleCount) * 3);
        const auto *data = reinterpret_cast<const uchar *>(bytes.constData());
        for (quint32 triangle = 0; triangle < triangleCount; ++triangle) {
            const uchar *record = data + 84 + quint64(triangle) * 50;
            for (int vertex = 0; vertex < 3; ++vertex) {
                const uchar *p = record + 12 + vertex * 12;
                points.append(QVector3D(littleFloat(p), littleFloat(p + 4), littleFloat(p + 8)));
            }
        }
    } else {
        QTextStream stream(bytes);
        QString token;
        while (!stream.atEnd()) {
            stream >> token;
            if (token.compare(QStringLiteral("vertex"), Qt::CaseInsensitive) != 0)
                continue;
            float x, y, z;
            if (!(stream >> x >> y >> z)) {
                emit loadFailed(QStringLiteral("The ASCII STL contains an incomplete vertex."));
                return false;
            }
            points.append(QVector3D(x, y, z));
            if (points.size() > 60'000'000) {
                emit loadFailed(QStringLiteral("The STL exceeds the native viewport triangle limit."));
                return false;
            }
        }
    }

    return setTrianglePoints(points, path, QStringLiteral("STL"));
}

bool MeshGeometry::loadObj(const QUrl &url)
{
    const QString path = url.isLocalFile() ? url.toLocalFile() : url.toString();
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        emit loadFailed(QStringLiteral("Could not open the selected OBJ file."));
        return false;
    }

    QVector<QVector3D> sourceVertices;
    QVector<QVector3D> triangles;
    QTextStream stream(&file);
    while (!stream.atEnd()) {
        const QString line = stream.readLine().trimmed();
        if (line.isEmpty() || line.startsWith(QLatin1Char('#')))
            continue;
        const QStringList fields = line.split(QRegularExpression(QStringLiteral("\\s+")), Qt::SkipEmptyParts);
        if (fields.isEmpty())
            continue;
        if (fields[0] == QStringLiteral("v")) {
            if (fields.size() < 4) {
                emit loadFailed(QStringLiteral("The OBJ contains an incomplete vertex."));
                return false;
            }
            bool okX = false, okY = false, okZ = false;
            const float x = fields[1].toFloat(&okX);
            const float y = fields[2].toFloat(&okY);
            const float z = fields[3].toFloat(&okZ);
            const QVector3D vertex(x, y, z);
            if (!okX || !okY || !okZ || !finite(vertex)) {
                emit loadFailed(QStringLiteral("The OBJ contains an invalid or non-finite vertex coordinate."));
                return false;
            }
            sourceVertices.append(vertex);
            if (sourceVertices.size() > 60'000'000) {
                emit loadFailed(QStringLiteral("The OBJ exceeds the native viewport triangle limit."));
                return false;
            }
        } else if (fields[0] == QStringLiteral("f")) {
            if (fields.size() < 4) {
                emit loadFailed(QStringLiteral("The OBJ contains a face with fewer than three vertices."));
                return false;
            }
            QVector<qsizetype> face;
            face.reserve(fields.size() - 1);
            for (qsizetype i = 1; i < fields.size(); ++i) {
                const QString vertexRef = fields[i].section(QLatin1Char('/'), 0, 0);
                bool ok = false;
                const qlonglong rawIndex = vertexRef.toLongLong(&ok);
                if (!ok || rawIndex == 0) {
                    emit loadFailed(QStringLiteral("The OBJ contains an invalid face vertex index."));
                    return false;
                }
                const qlonglong resolved = rawIndex > 0 ? rawIndex - 1 : sourceVertices.size() + rawIndex;
                if (resolved < 0 || resolved >= sourceVertices.size()) {
                    emit loadFailed(QStringLiteral("The OBJ face references a vertex outside the loaded vertex list."));
                    return false;
                }
                face.append(qsizetype(resolved));
            }
            const qsizetype added = (face.size() - 2) * 3;
            if (triangles.size() + added > 60'000'000) {
                emit loadFailed(QStringLiteral("The OBJ exceeds the native viewport triangle limit."));
                return false;
            }
            for (qsizetype i = 1; i + 1 < face.size(); ++i) {
                triangles.append(sourceVertices[face[0]]);
                triangles.append(sourceVertices[face[i]]);
                triangles.append(sourceVertices[face[i + 1]]);
            }
        }
    }

    if (sourceVertices.isEmpty() || triangles.isEmpty()) {
        emit loadFailed(QStringLiteral("No triangulated faces were found in the OBJ."));
        return false;
    }
    return setTrianglePoints(triangles, path, QStringLiteral("OBJ"));
}

bool MeshGeometry::load3mf(const QUrl &url)
{
    const QString path = url.isLocalFile() ? url.toLocalFile() : url.toString();
    QZipReader archive(path);
    if (!archive.isReadable()) {
        emit loadFailed(QStringLiteral("Could not open the selected 3MF package."));
        return false;
    }
    QByteArray model = archive.fileData(QStringLiteral("3D/3dmodel.model"));
    if (model.isEmpty()) {
        emit loadFailed(QStringLiteral("The 3MF package does not contain 3D/3dmodel.model."));
        return false;
    }

    QHash<QString, QVector<QVector3D>> verticesByObject;
    QHash<QString, QVector<std::array<quint32, 3>>> trianglesByObject;
    QSet<QString> objectIds;
    QString currentObject;
    QString buildObject;
    QString unit = QStringLiteral("millimeter");
    QString transformText;
    QXmlStreamReader xml(model);
    while (!xml.atEnd()) {
        xml.readNext();
        if (xml.isEndElement() && xml.name() == QStringLiteral("object")) {
            currentObject.clear();
            continue;
        }
        if (!xml.isStartElement()) continue;
        const QString name = xml.name().toString();
        const auto attrs = xml.attributes();
        if (name == QStringLiteral("model")) {
            unit = attrs.value(QStringLiteral("unit")).toString();
            if (unit.isEmpty()) unit = QStringLiteral("millimeter");
        } else if (name == QStringLiteral("object")) {
            currentObject = attrs.value(QStringLiteral("id")).toString();
            if (currentObject.isEmpty() || objectIds.contains(currentObject)) {
                emit loadFailed(QStringLiteral("The 3MF contains invalid or duplicate object IDs."));
                return false;
            }
            objectIds.insert(currentObject);
            verticesByObject.insert(currentObject, {});
            trianglesByObject.insert(currentObject, {});
        } else if (name == QStringLiteral("vertex") && !currentObject.isEmpty()) {
            bool okX = false, okY = false, okZ = false;
            const QVector3D v(attrs.value(QStringLiteral("x")).toFloat(&okX),
                              attrs.value(QStringLiteral("y")).toFloat(&okY),
                              attrs.value(QStringLiteral("z")).toFloat(&okZ));
            if (!okX || !okY || !okZ || !finite(v)) {
                emit loadFailed(QStringLiteral("The 3MF contains an invalid vertex."));
                return false;
            }
            verticesByObject[currentObject].append(v);
            if (verticesByObject[currentObject].size() > 20'000'000) {
                emit loadFailed(QStringLiteral("The 3MF exceeds the native viewport vertex limit."));
                return false;
            }
        } else if (name == QStringLiteral("triangle") && !currentObject.isEmpty()) {
            bool ok1 = false, ok2 = false, ok3 = false;
            const auto a = attrs.value(QStringLiteral("v1")).toUInt(&ok1);
            const auto b = attrs.value(QStringLiteral("v2")).toUInt(&ok2);
            const auto c = attrs.value(QStringLiteral("v3")).toUInt(&ok3);
            if (!ok1 || !ok2 || !ok3) {
                emit loadFailed(QStringLiteral("The 3MF contains an invalid triangle index."));
                return false;
            }
            if (trianglesByObject[currentObject].size() >= 20'000'000) {
                emit loadFailed(QStringLiteral("The 3MF exceeds the native viewport triangle limit."));
                return false;
            }
            trianglesByObject[currentObject].append({a, b, c});
        } else if (name == QStringLiteral("item") && buildObject.isEmpty()) {
            buildObject = attrs.value(QStringLiteral("objectid")).toString();
            transformText = attrs.value(QStringLiteral("transform")).toString();
        }
    }
    if (xml.hasError()) {
        emit loadFailed(QStringLiteral("The 3MF model XML is malformed."));
        return false;
    }
    if (buildObject.isEmpty()) {
        emit loadFailed(QStringLiteral("The 3MF has no build item to display."));
        return false;
    }
    const double unitScale = unit == QStringLiteral("micron") ? 0.001
        : unit == QStringLiteral("centimeter") ? 10.0
        : unit == QStringLiteral("inch") ? 25.4
        : unit == QStringLiteral("foot") ? 304.8
        : unit == QStringLiteral("meter") ? 1000.0
        : unit == QStringLiteral("millimeter") ? 1.0 : 0.0;
    if (unitScale == 0.0 || !verticesByObject.contains(buildObject)) {
        emit loadFailed(QStringLiteral("The 3MF uses an unsupported unit or referenced object."));
        return false;
    }
    const auto &vertices = verticesByObject[buildObject];
    const auto &triangles = trianglesByObject[buildObject];
    if (vertices.isEmpty() || triangles.isEmpty() || triangles.size() > 20'000'000) {
        emit loadFailed(QStringLiteral("The 3MF build item has no mesh or exceeds the triangle limit."));
        return false;
    }
    QVector<double> t;
    if (!transformText.isEmpty()) {
        const QStringList values = transformText.split(QRegularExpression(QStringLiteral("\\s+")), Qt::SkipEmptyParts);
        if (values.size() != 12) {
            emit loadFailed(QStringLiteral("The 3MF build transform is invalid."));
            return false;
        }
        for (const QString &value : values) {
            bool ok = false;
            const double number = value.toDouble(&ok);
            if (!ok || !std::isfinite(number)) {
                emit loadFailed(QStringLiteral("The 3MF build transform contains an invalid value."));
                return false;
            }
            t.append(number);
        }
    }
    QVector<QVector3D> points;
    points.reserve(triangles.size() * 3);
    for (const auto &tri : triangles) {
        for (quint32 index : tri) {
            if (index >= quint32(vertices.size())) {
                emit loadFailed(QStringLiteral("The 3MF triangle references a missing vertex."));
                return false;
            }
            const QVector3D v = vertices[int(index)];
            double x = v.x(), y = v.y(), z = v.z();
            if (!t.isEmpty()) {
                // 3MF serializes the affine matrix in row-major order and
                // applies it to row-vector coordinates. Translation is the
                // final row (entries 9-11).
                const double tx = x*t[0] + y*t[3] + z*t[6] + t[9];
                const double ty = x*t[1] + y*t[4] + z*t[7] + t[10];
                const double tz = x*t[2] + y*t[5] + z*t[8] + t[11];
                x = tx; y = ty; z = tz;
            }
            points.append(QVector3D(float(x * unitScale), float(y * unitScale), float(z * unitScale)));
        }
    }
    return setTrianglePoints(points, path, QStringLiteral("3MF"));
}

QVariantMap MeshGeometry::exportStl(const QUrl &url, const QVector3D &offsetMm,
                                    const QVector3D &rotationDeg, const QVector3D &scale) const
{
    if (!m_loaded || m_trianglePoints.isEmpty())
        return {{QStringLiteral("error"), QStringLiteral("Load a mesh before exporting STL.")}};
    if (!url.isLocalFile())
        return {{QStringLiteral("error"), QStringLiteral("STL export requires a local file path.")}};
    if (!finite(offsetMm) || !finite(rotationDeg) || !finite(scale)
        || scale.x() == 0.0f || scale.y() == 0.0f || scale.z() == 0.0f)
        return {{QStringLiteral("error"), QStringLiteral("The selected instance has invalid transform values.")}};

    const QString path = url.toLocalFile();
    if (QFileInfo(path).suffix().compare(QStringLiteral("stl"), Qt::CaseInsensitive) != 0)
        return {{QStringLiteral("error"), QStringLiteral("Choose an .stl file for export.")}};
    const quint64 triangleCount = quint64(m_trianglePoints.size() / 3);
    if (triangleCount > std::numeric_limits<quint32>::max())
        return {{QStringLiteral("error"), QStringLiteral("This mesh exceeds the binary STL triangle limit.")}};

    QSaveFile file(path);
    if (!file.open(QIODevice::WriteOnly))
        return {{QStringLiteral("error"), QStringLiteral("Could not create the STL export: %1").arg(file.errorString())}};

    QByteArray header(80, '\0');
    const QByteArray label = QByteArrayLiteral("Outlaw Forge local STL export (millimetres)");
    std::copy(label.cbegin(), label.cend(), header.begin());
    if (file.write(header) != header.size())
        return {{QStringLiteral("error"), QStringLiteral("Could not write the STL header: %1").arg(file.errorString())}};

    QDataStream stream(&file);
    stream.setByteOrder(QDataStream::LittleEndian);
    stream.setFloatingPointPrecision(QDataStream::SinglePrecision);
    stream << quint32(triangleCount);
    const QVector3D origin(m_center.x(), m_center.y(), m_center.z() - m_dimensions.z() * 0.5f);
    const QQuaternion rotation = QQuaternion::fromEulerAngles(rotationDeg.x(), rotationDeg.y(), rotationDeg.z());
    const auto transformed = [&](const QVector3D &point) {
        const QVector3D local((point.x() - origin.x()) * scale.x(),
                              (point.y() - origin.y()) * scale.y(),
                              (point.z() - origin.z()) * scale.z());
        return origin + offsetMm + rotation.rotatedVector(local);
    };
    for (qsizetype i = 0; i + 2 < m_trianglePoints.size(); i += 3) {
        const QVector3D a = transformed(m_trianglePoints[i]);
        QVector3D b = transformed(m_trianglePoints[i + 1]);
        QVector3D c = transformed(m_trianglePoints[i + 2]);
        if (scale.x() * scale.y() * scale.z() < 0.0f)
            std::swap(b, c);
        QVector3D normal = QVector3D::crossProduct(b - a, c - a);
        if (normal.lengthSquared() > 1.0e-20f)
            normal.normalize();
        else
            normal = QVector3D(0, 0, 0);
        for (float value : {normal.x(), normal.y(), normal.z(),
                            a.x(), a.y(), a.z(), b.x(), b.y(), b.z(), c.x(), c.y(), c.z()})
            stream << value;
        stream << quint16(0);
        if (stream.status() != QDataStream::Ok)
            return {{QStringLiteral("error"), QStringLiteral("Could not write all STL triangles: %1").arg(file.errorString())}};
    }
    if (stream.status() != QDataStream::Ok || !file.commit())
        return {{QStringLiteral("error"), QStringLiteral("Could not finish the STL export: %1").arg(file.errorString())}};
    return {{QStringLiteral("path"), path},
            {QStringLiteral("triangles"), qlonglong(triangleCount)},
            {QStringLiteral("units"), QStringLiteral("mm")},
            {QStringLiteral("revisionId"), m_revisionId}};
}

bool MeshGeometry::setTrianglePoints(const QVector<QVector3D> &points, const QString &path, const QString &format)
{
    if (points.isEmpty() || points.size() % 3 != 0) {
        emit loadFailed(QStringLiteral("No complete triangles were found in the %1.").arg(format));
        return false;
    }

    QVector3D minimum(points[0]), maximum(points[0]);
    for (const auto &point : points) {
        if (!finite(point)) {
            emit loadFailed(QStringLiteral("The %1 contains a non-finite vertex coordinate.").arg(format));
            return false;
        }
        minimum.setX(std::min(minimum.x(), point.x()));
        minimum.setY(std::min(minimum.y(), point.y()));
        minimum.setZ(std::min(minimum.z(), point.z()));
        maximum.setX(std::max(maximum.x(), point.x()));
        maximum.setY(std::max(maximum.y(), point.y()));
        maximum.setZ(std::max(maximum.z(), point.z()));
    }

    const QVector3D midpoint = (minimum + maximum) * 0.5f;
    m_dimensions = maximum - minimum;
    m_sampledFaceNormals.clear();
    const qsizetype triangleCount = points.size() / 3;
    constexpr qsizetype maximumNormalSamples = 300;
    const qsizetype sampleCount = std::min(triangleCount, maximumNormalSamples);
    const float normalLength = std::clamp(std::max({m_dimensions.x(), m_dimensions.y(), m_dimensions.z()}) * 0.035f,
                                          0.8f, 4.0f);
    m_sampledFaceNormals.reserve(sampleCount);
    for (qsizetype sample = 0; sample < sampleCount; ++sample) {
        const qsizetype triangle = sample * triangleCount / sampleCount;
        const qsizetype i = triangle * 3;
        QVector3D normal = QVector3D::crossProduct(points[i + 1] - points[i], points[i + 2] - points[i]);
        if (normal.lengthSquared() <= 1.0e-20f)
            continue;
        normal.normalize();
        const QVector3D centroid = (points[i] + points[i + 1] + points[i + 2]) / 3.0f
            - QVector3D(midpoint.x(), midpoint.y(), minimum.z());
        QVariantMap entry;
        entry.insert(QStringLiteral("position"), centroid + normal * (normalLength * 0.5f));
        entry.insert(QStringLiteral("rotation"), QQuaternion::rotationTo(QVector3D(0, 0, 1), normal));
        entry.insert(QStringLiteral("length"), normalLength);
        m_sampledFaceNormals.append(entry);
    }
    QByteArray vertexBytes;
    vertexBytes.resize(points.size() * qsizetype(sizeof(Vertex)));
    auto *vertices = reinterpret_cast<Vertex *>(vertexBytes.data());
    for (qsizetype i = 0; i < points.size(); i += 3) {
        QVector3D normal = QVector3D::crossProduct(points[i + 1] - points[i], points[i + 2] - points[i]);
        if (normal.lengthSquared() > 1.0e-20f)
            normal.normalize();
        else
            normal = QVector3D(0, 0, 1);
        for (qsizetype corner = 0; corner < 3; ++corner) {
            const QVector3D p = points[i + corner] - QVector3D(midpoint.x(), midpoint.y(), minimum.z());
            vertices[i + corner] = {{p.x(), p.y(), p.z()}, {normal.x(), normal.y(), normal.z()}};
        }
    }

    clear();
    setPrimitiveType(PrimitiveType::Triangles);
    setStride(sizeof(Vertex));
    addAttribute(Attribute::PositionSemantic, offsetof(Vertex, position), Attribute::F32Type);
    addAttribute(Attribute::NormalSemantic, offsetof(Vertex, normal), Attribute::F32Type);
    setVertexData(vertexBytes);
    setBounds(QVector3D(-m_dimensions.x() * 0.5f, -m_dimensions.y() * 0.5f, 0),
              QVector3D(m_dimensions.x() * 0.5f, m_dimensions.y() * 0.5f, m_dimensions.z()));
    update();

    m_center = QVector3D(midpoint.x(), midpoint.y(), minimum.z() + m_dimensions.z() * 0.5f);
    m_trianglePoints = points;
    QByteArray revisionBytes;
    revisionBytes.reserve(points.size() * 3 * qsizetype(sizeof(quint32)));
    for (const QVector3D &point : points) {
        for (float coordinate : {point.x(), point.y(), point.z()}) {
            const quint32 bits = qToLittleEndian(std::bit_cast<quint32>(coordinate));
            revisionBytes.append(reinterpret_cast<const char *>(&bits), sizeof(bits));
        }
    }
    m_revisionId = QString::fromLatin1(QCryptographicHash::hash(revisionBytes, QCryptographicHash::Sha256).toHex());
    m_fileName = QFileInfo(path).fileName();
    m_loaded = true;
    emit loadedChanged();
    return true;
}

QVariantMap MeshGeometry::analyzeMesh() const
{
    if (!m_loaded)
        return {};
    return meshMetrics(m_trianglePoints, 0.00001);
}

int MeshGeometry::connectedComponentCount() const
{
    if (!m_loaded)
        return 0;
    return int(connectedTriangleGroups(m_trianglePoints, 0.00001).size());
}

QVariantMap MeshGeometry::splitConnectedComponents(const QVariantList &outputs) const
{
    if (!m_loaded || m_trianglePoints.isEmpty())
        return {{QStringLiteral("error"), QStringLiteral("Load a mesh before splitting components.")}};

    const QVector<QVector<qsizetype>> groups = connectedTriangleGroups(m_trianglePoints, 0.00001);
    if (outputs.size() != groups.size())
        return {{QStringLiteral("error"), QStringLiteral("The output geometry count does not match the mesh component count.")}};

    QVector<MeshGeometry *> geometries;
    geometries.reserve(outputs.size());
    QSet<MeshGeometry *> uniqueOutputs;
    for (const QVariant &value : outputs) {
        auto *geometry = qobject_cast<MeshGeometry *>(qvariant_cast<QObject *>(value));
        if (!geometry || geometry == this || uniqueOutputs.contains(geometry))
            return {{QStringLiteral("error"), QStringLiteral("Each component needs a unique, separate output geometry.")}};
        uniqueOutputs.insert(geometry);
        geometries.append(geometry);
    }

    QVariantList parts;
    parts.reserve(groups.size());
    for (qsizetype index = 0; index < groups.size(); ++index) {
        QVector<QVector3D> points;
        points.reserve(groups[index].size() * 3);
        for (qsizetype triangle : groups[index]) {
            const qsizetype offset = triangle * 3;
            points.append(m_trianglePoints[offset]);
            points.append(m_trianglePoints[offset + 1]);
            points.append(m_trianglePoints[offset + 2]);
        }
        MeshGeometry *output = geometries[index];
        if (!output->setTrianglePoints(points, m_fileName, QStringLiteral("separated component")))
            return {{QStringLiteral("error"), QStringLiteral("Could not create the separated component geometry.")}};
        parts.append(QVariantMap{{QStringLiteral("componentIndex"), index},
                                 {QStringLiteral("triangles"), groups[index].size()},
                                 {QStringLiteral("revisionId"), output->revisionId()}});
    }
    return {{QStringLiteral("components"), groups.size()}, {QStringLiteral("parts"), parts}};
}

QVariantMap MeshGeometry::simplifyMesh(double targetReductionPercent, MeshGeometry *output) const
{
    if (!m_loaded || m_trianglePoints.isEmpty())
        return {{QStringLiteral("error"), QStringLiteral("Load a mesh before simplifying it.")}};
    if (!output || output == this)
        return {{QStringLiteral("error"), QStringLiteral("Simplification needs a separate output geometry.")}};
    if (!std::isfinite(targetReductionPercent) || targetReductionPercent < 1.0 || targetReductionPercent > 95.0)
        return {{QStringLiteral("error"), QStringLiteral("Target reduction must be between 1 and 95 percent.")}};
    constexpr qsizetype maximumSimplificationTriangles = 1000000;
    if (triangleCount() > maximumSimplificationTriangles)
        return {{QStringLiteral("error"), QStringLiteral("Local simplification supports meshes up to 1,000,000 triangles to stay within the native memory budget.")}};

    QVector3D minimum = m_trianglePoints.front();
    QVector3D maximum = minimum;
    for (const QVector3D &point : m_trianglePoints) {
        minimum.setX(std::min(minimum.x(), point.x()));
        minimum.setY(std::min(minimum.y(), point.y()));
        minimum.setZ(std::min(minimum.z(), point.z()));
        maximum.setX(std::max(maximum.x(), point.x()));
        maximum.setY(std::max(maximum.y(), point.y()));
        maximum.setZ(std::max(maximum.z(), point.z()));
    }

    const qsizetype sourceTriangles = triangleCount();
    const qsizetype targetTriangles = std::max<qsizetype>(1, qRound64(sourceTriangles * (1.0 - targetReductionPercent / 100.0)));
    QVector<QVector3D> best = m_trianglePoints;
    qsizetype bestDistance = std::abs(sourceTriangles - targetTriangles);
    const QVector3D dimensions = maximum - minimum;
    const double extent = std::max({double(dimensions.x()), double(dimensions.y()), double(dimensions.z()), 1.0e-5});
    QVector<QVector3D> uniquePoints;
    uniquePoints.reserve(m_trianglePoints.size() / 3);
    QVector<qsizetype> pointIndices;
    pointIndices.reserve(m_trianglePoints.size());
    QHash<ExactPositionKey, qsizetype> uniqueIndexByPosition;
    uniqueIndexByPosition.reserve(m_trianglePoints.size() / 6);
    for (const QVector3D &point : m_trianglePoints) {
        const ExactPositionKey key{std::bit_cast<quint32>(point.x()),
                                   std::bit_cast<quint32>(point.y()),
                                   std::bit_cast<quint32>(point.z())};
        auto it = uniqueIndexByPosition.constFind(key);
        qsizetype index;
        if (it == uniqueIndexByPosition.cend()) {
            index = uniquePoints.size();
            uniqueIndexByPosition.insert(key, index);
            uniquePoints.append(point);
        } else {
            index = it.value();
        }
        pointIndices.append(index);
    }
    double low = extent * 1.0e-8;
    double high = extent * 2.0;
    // Bound full-mesh passes so this local operation remains responsive for
    // large files. Vertex clustering is deterministic for a fixed cell size;
    // keep the nearest candidate found because the target is not a topology
    // guarantee.
    constexpr qsizetype maximumCandidateTriangleVisits = 2000000;
    const int searchIterations = int(std::max<qsizetype>(1, std::min<qsizetype>(14,
        maximumCandidateTriangleVisits / sourceTriangles)));
    for (int iteration = 0; iteration < searchIterations; ++iteration) {
        const double cellSize = (low + high) * 0.5;
        QVector<QVector3D> candidate = clusteredCandidate(uniquePoints, pointIndices, minimum, cellSize);
        const qsizetype candidateTriangles = candidate.size() / 3;
        const qsizetype distance = std::abs(candidateTriangles - targetTriangles);
        if (!candidate.isEmpty() && (distance < bestDistance
            || (distance == bestDistance && candidateTriangles > best.size() / 3))) {
            bestDistance = distance;
            best = std::move(candidate);
        }
        if (candidateTriangles > targetTriangles)
            low = cellSize;
        else
            high = cellSize;
    }

    if (!output->setTrianglePoints(best, m_fileName, QStringLiteral("simplified mesh")))
        return {{QStringLiteral("error"), QStringLiteral("Could not create the simplified mesh geometry.")}};
    const qsizetype resultTriangles = best.size() / 3;
    const double actualReduction = sourceTriangles == 0 ? 0.0
        : (double(sourceTriangles - resultTriangles) * 100.0 / double(sourceTriangles));
    QVariantMap result = meshMetrics(best, 0.00001);
    result.insert(QStringLiteral("sourceTriangles"), sourceTriangles);
    result.insert(QStringLiteral("triangles"), resultTriangles);
    result.insert(QStringLiteral("originalTriangles"), sourceTriangles);
    result.insert(QStringLiteral("resultTriangles"), resultTriangles);
    result.insert(QStringLiteral("requestedReductionPercent"), targetReductionPercent);
    result.insert(QStringLiteral("actualReductionPercent"), actualReduction);
    result.insert(QStringLiteral("searchIterations"), searchIterations);
    result.insert(QStringLiteral("revisionId"), output->revisionId());
    return result;
}

QVector3D MeshGeometry::instanceOffsetCorrection(const MeshGeometry *derivedGeometry,
                                                  const QVector3D &instanceScale,
                                                  const QVector3D &instanceRotationDeg) const
{
    if (!m_loaded || !derivedGeometry || !derivedGeometry->m_loaded
        || !finite(instanceScale) || !finite(instanceRotationDeg))
        return {};
    const QVector3D sourceOrigin(m_center.x(), m_center.y(), m_center.z() - m_dimensions.z() * 0.5f);
    const QVector3D derivedOrigin(derivedGeometry->m_center.x(), derivedGeometry->m_center.y(),
                                  derivedGeometry->m_center.z() - derivedGeometry->m_dimensions.z() * 0.5f);
    const QVector3D originDelta = derivedOrigin - sourceOrigin;
    const QVector3D scaledDelta(originDelta.x() * instanceScale.x(), originDelta.y() * instanceScale.y(),
                                originDelta.z() * instanceScale.z());
    return -originDelta + QQuaternion::fromEulerAngles(instanceRotationDeg).rotatedVector(scaledDelta);
}

QVariantMap MeshGeometry::autoOrient(double criticalAngleDeg)
{
    if (!m_loaded || !std::isfinite(criticalAngleDeg) || criticalAngleDeg < 0.0 || criticalAngleDeg > 90.0)
        return {{QStringLiteral("error"), QStringLiteral("Critical angle must be between 0 and 90 degrees.")}};

    constexpr int maximumFaceCandidates = 24;
    QVector<QQuaternion> candidates{QQuaternion()};
    QVector<QPair<double, QVector3D>> largestFaces;
    const QVector3D down(0, 0, -1);
    for (qsizetype i = 0; i + 2 < m_trianglePoints.size(); i += 3) {
        const QVector3D &a = m_trianglePoints[i];
        const QVector3D &b = m_trianglePoints[i + 1];
        const QVector3D &c = m_trianglePoints[i + 2];
        const QVector3D cross = QVector3D::crossProduct(b - a, c - a);
        const double twiceArea = cross.length();
        if (!std::isfinite(twiceArea) || twiceArea <= 1.0e-10)
            continue;
        const QVector3D normal = cross / float(twiceArea);
        if (largestFaces.size() < maximumFaceCandidates) {
            largestFaces.append({twiceArea, normal});
            if (largestFaces.size() == maximumFaceCandidates)
                std::sort(largestFaces.begin(), largestFaces.end(), [](const auto &left, const auto &right) {
                    return left.first > right.first;
                });
        } else if (twiceArea > largestFaces.back().first) {
            largestFaces.back() = {twiceArea, normal};
            std::sort(largestFaces.begin(), largestFaces.end(), [](const auto &left, const auto &right) {
                return left.first > right.first;
            });
        }
    }
    for (const auto &face : largestFaces)
        candidates.append(QQuaternion::rotationTo(face.second, down));
    for (const QVector3D &axis : {QVector3D(1, 0, 0), QVector3D(-1, 0, 0),
                                  QVector3D(0, 1, 0), QVector3D(0, -1, 0),
                                  QVector3D(0, 0, 1), QVector3D(0, 0, -1)})
        candidates.append(QQuaternion::rotationTo(axis, down));

    const double threshold = -std::sin(qDegreesToRadians(90.0 - criticalAngleDeg));
    const double diagonal = std::max(double(m_dimensions.length()), 1.0);
    double totalArea = 0.0;
    for (qsizetype i = 0; i + 2 < m_trianglePoints.size(); i += 3)
        totalArea += 0.5 * QVector3D::crossProduct(m_trianglePoints[i + 1] - m_trianglePoints[i],
                                                   m_trianglePoints[i + 2] - m_trianglePoints[i]).length();

    double bestCost = std::numeric_limits<double>::infinity();
    double bestOverhangArea = 0.0;
    QQuaternion bestRotation;
    for (const QQuaternion &rotation : candidates) {
        float minZ = std::numeric_limits<float>::infinity();
        float maxZ = -std::numeric_limits<float>::infinity();
        double overhangArea = 0.0;
        double bedArea = 0.0;
        for (qsizetype i = 0; i + 2 < m_trianglePoints.size(); i += 3) {
            const QVector3D a = rotation.rotatedVector(m_trianglePoints[i]);
            const QVector3D b = rotation.rotatedVector(m_trianglePoints[i + 1]);
            const QVector3D c = rotation.rotatedVector(m_trianglePoints[i + 2]);
            minZ = std::min({minZ, a.z(), b.z(), c.z()});
            maxZ = std::max({maxZ, a.z(), b.z(), c.z()});
        }
        for (qsizetype i = 0; i + 2 < m_trianglePoints.size(); i += 3) {
            const QVector3D a = rotation.rotatedVector(m_trianglePoints[i]);
            const QVector3D b = rotation.rotatedVector(m_trianglePoints[i + 1]);
            const QVector3D c = rotation.rotatedVector(m_trianglePoints[i + 2]);
            const QVector3D face = QVector3D::crossProduct(b - a, c - a);
            const double area = 0.5 * face.length();
            if (area <= 1.0e-12)
                continue;
            const float nz = face.z() / float(2.0 * area);
            if (nz < threshold)
                overhangArea += area;
            if (std::min({a.z(), b.z(), c.z()}) <= minZ + 0.3f && nz < -0.8f)
                bedArea += area;
        }
        const double heightPenalty = ((maxZ - minZ) / diagonal) * totalArea;
        const double cost = overhangArea + 0.15 * heightPenalty - 0.8 * bedArea;
        if (cost < bestCost) {
            bestCost = cost;
            bestOverhangArea = overhangArea;
            bestRotation = rotation;
        }
    }

    QVector<QVector3D> oriented;
    oriented.reserve(m_trianglePoints.size());
    QVector3D minimum(std::numeric_limits<float>::infinity(), std::numeric_limits<float>::infinity(),
                      std::numeric_limits<float>::infinity());
    QVector3D maximum(-std::numeric_limits<float>::infinity(), -std::numeric_limits<float>::infinity(),
                      -std::numeric_limits<float>::infinity());
    for (const QVector3D &point : m_trianglePoints) {
        const QVector3D rotated = bestRotation.rotatedVector(point);
        oriented.append(rotated);
        minimum.setX(std::min(minimum.x(), rotated.x()));
        minimum.setY(std::min(minimum.y(), rotated.y()));
        minimum.setZ(std::min(minimum.z(), rotated.z()));
        maximum.setX(std::max(maximum.x(), rotated.x()));
        maximum.setY(std::max(maximum.y(), rotated.y()));
        maximum.setZ(std::max(maximum.z(), rotated.z()));
    }
    const QVector3D translation(-(minimum.x() + maximum.x()) * 0.5f,
                                -(minimum.y() + maximum.y()) * 0.5f, -minimum.z());
    for (QVector3D &point : oriented)
        point += translation;
    if (!setTrianglePoints(oriented, m_fileName, QStringLiteral("auto-oriented mesh")))
        return {{QStringLiteral("error"), QStringLiteral("Auto-orient could not rebuild the mesh; the current geometry was kept unchanged.")}};
    return {{QStringLiteral("candidateCount"), candidates.size()},
            {QStringLiteral("overhangAreaCm2"), bestOverhangArea / 100.0},
            {QStringLiteral("minimumZMm"), 0.0},
            {QStringLiteral("heightMm"), maximum.z() - minimum.z()}};
}

QVariantMap MeshGeometry::repairMesh(double weldToleranceMm)
{
    if (!m_loaded || !std::isfinite(weldToleranceMm) || weldToleranceMm < 0.00001 || weldToleranceMm > 10.0)
        return {{QStringLiteral("error"), QStringLiteral("Weld tolerance must be between 0.00001 and 10 mm.")}};

    const QVariantMap before = meshMetrics(m_trianglePoints, weldToleranceMm);
    QHash<QString, QVector3D> welded;
    QVector<QVector3D> repaired;
    repaired.reserve(m_trianglePoints.size());
    int removed = 0;
    for (qsizetype i = 0; i + 2 < m_trianglePoints.size(); i += 3) {
        QVector3D tri[3];
        for (int corner = 0; corner < 3; ++corner) {
            const QVector3D point = m_trianglePoints[i + corner];
            const QString key = vertexKey(point, weldToleranceMm);
            auto it = welded.constFind(key);
            if (it == welded.cend()) {
                welded.insert(key, point);
                tri[corner] = point;
            } else {
                tri[corner] = it.value();
            }
        }
        if (tri[0] == tri[1] || tri[1] == tri[2] || tri[2] == tri[0]
            || QVector3D::crossProduct(tri[1] - tri[0], tri[2] - tri[0]).lengthSquared() <= 1.0e-20f) {
            ++removed;
            continue;
        }
        repaired.append(tri[0]); repaired.append(tri[1]); repaired.append(tri[2]);
    }
    if (repaired.isEmpty())
        return {{QStringLiteral("error"), QStringLiteral("Repair would remove every triangle. The current mesh was kept unchanged.")}};

    // Fill only closed, planar boundary loops. Branches and non-planar openings
    // are left untouched and are reported by the post-repair mesh analysis.
    struct BoundaryEdge { int from; int to; };
    QHash<QString, int> vertexIds;
    QVector<QVector3D> vertices;
    QVector<std::array<int, 3>> faces;
    faces.reserve(repaired.size() / 3);
    const auto vertexId = [&](const QVector3D &point) {
        const QString key = vertexKey(point, weldToleranceMm);
        auto it = vertexIds.constFind(key);
        if (it != vertexIds.cend())
            return it.value();
        const int id = vertices.size();
        vertexIds.insert(key, id);
        vertices.append(point);
        return id;
    };
    for (qsizetype i = 0; i + 2 < repaired.size(); i += 3)
        faces.append({vertexId(repaired[i]), vertexId(repaired[i + 1]), vertexId(repaired[i + 2])});
    QHash<quint64, int> edgeCounts;
    QHash<quint64, BoundaryEdge> directedEdges;
    const auto edgeKey = [](int a, int b) {
        const quint32 low = quint32(std::min(a, b));
        const quint32 high = quint32(std::max(a, b));
        return (quint64(low) << 32) | high;
    };
    for (const auto &face : faces) {
        for (int edge = 0; edge < 3; ++edge) {
            const int from = face[size_t(edge)];
            const int to = face[size_t((edge + 1) % 3)];
            const quint64 key = edgeKey(from, to);
            if (++edgeCounts[key] == 1)
                directedEdges.insert(key, {from, to});
        }
    }
    QHash<int, QVector<int>> boundaryAdjacency;
    for (auto it = edgeCounts.cbegin(); it != edgeCounts.cend(); ++it) {
        if (it.value() != 1)
            continue;
        const BoundaryEdge edge = directedEdges.value(it.key());
        boundaryAdjacency[edge.from].append(edge.to);
        boundaryAdjacency[edge.to].append(edge.from);
    }
    QVector<QVector<QVector3D>> boundaryLoops;
    QVector<bool> loopFollowsBoundaryDirection;
    QSet<quint64> visitedBoundaryEdges;
    for (auto it = boundaryAdjacency.cbegin(); it != boundaryAdjacency.cend(); ++it) {
        if (it.value().size() != 2)
            continue;
        for (int firstNeighbor : it.value()) {
            if (visitedBoundaryEdges.contains(edgeKey(it.key(), firstNeighbor)))
                continue;
            QVector<int> loopIds{it.key()};
            int previous = it.key();
            int current = firstNeighbor;
            const bool followsBoundaryDirection = directedEdges.value(edgeKey(previous, current)).from == previous;
            bool closed = false;
            for (int guard = edgeCounts.size() + 1; guard > 0; --guard) {
                visitedBoundaryEdges.insert(edgeKey(previous, current));
                if (current == loopIds.front()) {
                    closed = true;
                    break;
                }
                if (boundaryAdjacency.value(current).size() != 2)
                    break;
                loopIds.append(current);
                const auto &neighbors = boundaryAdjacency[current];
                const int next = neighbors[0] == previous ? neighbors[1] : neighbors[0];
                previous = current;
                current = next;
            }
            if (!closed || loopIds.size() < 3)
                continue;
            QVector<QVector3D> loop;
            loop.reserve(loopIds.size());
            QVector3D normal;
            for (qsizetype index = 0; index < loopIds.size(); ++index) {
                const QVector3D &a = vertices[loopIds[index]];
                const QVector3D &b = vertices[loopIds[(index + 1) % loopIds.size()]];
                loop.append(a);
                normal += QVector3D::crossProduct(a, b);
            }
            if (normal.lengthSquared() < 1.0e-12f)
                continue;
            normal.normalize();
            const QVector3D origin = loop.front();
            const float extent = std::max({m_dimensions.x(), m_dimensions.y(), m_dimensions.z(), 1.0f});
            const float planarityTolerance = std::max(float(weldToleranceMm) * 2.0f, extent * 1.0e-5f);
            bool planar = true;
            for (const QVector3D &point : loop)
                planar &= std::abs(QVector3D::dotProduct(point - origin, normal)) <= planarityTolerance;
            if (!planar)
                continue;
            boundaryLoops.append(loop);
            loopFollowsBoundaryDirection.append(followsBoundaryDirection);
        }
    }

    int holesFilled = 0;
    if (!boundaryLoops.isEmpty()) {
        // Current native repair fills the common single-hole case. Each loop
        // must be planar; an invalid cap leaves the imported surface intact.
        for (qsizetype loopIndex = 0; loopIndex < boundaryLoops.size(); ++loopIndex) {
            const auto &loop = boundaryLoops[loopIndex];
            QVector3D normal;
            for (qsizetype i = 0; i < loop.size(); ++i)
                normal += QVector3D::crossProduct(loop[i], loop[(i + 1) % loop.size()]);
            if (normal.lengthSquared() < 1.0e-12f)
                continue;
            normal.normalize();
            QVector<QVector3D> cap;
            QString capError;
            if (triangulateCapLoops({loop}, normal, loopFollowsBoundaryDirection[loopIndex], &cap, &capError)
                && !cap.isEmpty()) {
                repaired += cap;
                ++holesFilled;
            }
        }
    }

    const int verticesAfterRepair = meshMetrics(repaired, weldToleranceMm)
                                        .value(QStringLiteral("vertices")).toInt();
    const int weldedVertices = before.value(QStringLiteral("vertices")).toInt() - verticesAfterRepair;
    if (!setTrianglePoints(repaired, m_fileName, QStringLiteral("repaired mesh")))
        return {{QStringLiteral("error"), QStringLiteral("The repaired mesh could not be rebuilt. The current mesh was kept unchanged.")}};
    return {{QStringLiteral("removedTriangles"), removed},
            {QStringLiteral("weldedVertices"), std::max(0, weldedVertices)},
            {QStringLiteral("holesFilled"), holesFilled},
            {QStringLiteral("remainingTriangles"), triangleCount()}};
}

QVariantMap MeshGeometry::sliceByPlane(const QVector3D &pointMm, const QVector3D &planeNormal, bool keepPositive,
                                       MeshGeometry *keptOutput, MeshGeometry *oppositeOutput) const
{
    if (!keptOutput || keptOutput == this || (oppositeOutput && (oppositeOutput == this || oppositeOutput == keptOutput)))
        return {{QStringLiteral("error"), QStringLiteral("Slice outputs must be separate mesh objects.")}};
    if (!m_loaded)
        return {{QStringLiteral("error"), QStringLiteral("Load a mesh before slicing.")}};
    if (!finite(pointMm) || !finite(planeNormal) || planeNormal.lengthSquared() < 1.0e-12f)
        return {{QStringLiteral("error"), QStringLiteral("Enter finite plane coordinates and a non-zero normal.")}};

    const QVector3D normal = planeNormal.normalized();
    const QVector3D meshExtent = m_dimensions;
    const float epsilon = std::max(1.0e-6f, std::max({meshExtent.x(), meshExtent.y(), meshExtent.z()}) * 1.0e-7f);
    struct ClipResult {
        QVector<QVector3D> points;
        QVector<QPair<QVector3D, QVector3D>> cutSegments;
        int removed = 0;
        int changed = 0;
    };
    const auto clipSide = [&](bool positive) {
        ClipResult result;
        result.points.reserve(m_trianglePoints.size());
        for (qsizetype i = 0; i + 2 < m_trianglePoints.size(); i += 3) {
            QVector3D triangle[] = {m_trianglePoints[i], m_trianglePoints[i + 1], m_trianglePoints[i + 2]};
            float signedDistances[3];
            for (int corner = 0; corner < 3; ++corner) {
                signedDistances[corner] = QVector3D::dotProduct(triangle[corner] - pointMm, normal);
                // Treat near-plane source vertices as exactly on the plane. The
                // clipped faces and cap contour must share the same coordinates.
                if (std::abs(signedDistances[corner]) <= epsilon) {
                    triangle[corner] -= normal * signedDistances[corner];
                    signedDistances[corner] = 0.0f;
                }
            }
            QVector<QVector3D> hits;
            for (int edge = 0; edge < 3; ++edge) {
                const QVector3D &a = triangle[edge];
                const QVector3D &b = triangle[(edge + 1) % 3];
                const float da = signedDistances[edge];
                const float db = signedDistances[(edge + 1) % 3];
                if (da == 0.0f)
                    hits.append(a);
                if ((da < 0.0f && db > 0.0f) || (da > 0.0f && db < 0.0f))
                    hits.append(a + (b - a) * (da / (da - db)));
            }
            QVector<QVector3D> uniqueHits;
            for (const QVector3D &hit : hits) {
                bool duplicate = false;
                for (const QVector3D &prior : uniqueHits)
                    duplicate |= (hit - prior).lengthSquared() <= 1.0e-12f;
                if (!duplicate)
                    uniqueHits.append(hit);
            }
            if (uniqueHits.size() == 2)
                result.cutSegments.append({uniqueHits[0], uniqueHits[1]});
            QVector<QVector3D> polygon;
            polygon.reserve(4);
            int insideCount = 0;
            for (int edge = 0; edge < 3; ++edge) {
                const QVector3D &a = triangle[edge];
                const QVector3D &b = triangle[(edge + 1) % 3];
                const float direction = positive ? 1.0f : -1.0f;
                const float da = signedDistances[edge] * direction;
                const float db = signedDistances[(edge + 1) % 3] * direction;
                const bool aInside = da >= 0.0f;
                const bool bInside = db >= 0.0f;
                insideCount += aInside ? 1 : 0;
                if (aInside)
                    polygon.append(a);
                if (aInside != bInside) {
                    const float denominator = da - db;
                    if (std::abs(denominator) > 1.0e-12f)
                        polygon.append(a + (b - a) * std::clamp(da / denominator, 0.0f, 1.0f));
                }
            }
            if (insideCount == 0) {
                ++result.removed;
                continue;
            }
            if (insideCount != 3)
                ++result.changed;
            if (polygon.size() < 3) {
                ++result.removed;
                continue;
            }
            for (qsizetype fan = 1; fan + 1 < polygon.size(); ++fan) {
                const QVector3D &a = polygon[0], &b = polygon[fan], &c = polygon[fan + 1];
                if (QVector3D::crossProduct(b - a, c - a).lengthSquared() <= 1.0e-20f)
                    continue;
                result.points.append(a);
                result.points.append(b);
                result.points.append(c);
            }
        }
        return result;
    };

    const ClipResult kept = clipSide(keepPositive);
    const ClipResult opposite = oppositeOutput ? clipSide(!keepPositive) : ClipResult{};
    if (kept.points.isEmpty() || (oppositeOutput && opposite.points.isEmpty()))
        return {{QStringLiteral("error"), QStringLiteral("The selected plane removes the entire mesh.")}};
    if (kept.changed == 0 && kept.removed == 0)
        return {{QStringLiteral("error"), QStringLiteral("The plane does not intersect or remove any mesh faces.")}};
    if (oppositeOutput && opposite.changed == 0 && opposite.removed == 0)
        return {{QStringLiteral("error"), QStringLiteral("The plane does not intersect or remove any mesh faces on the opposite side.")}};

    const auto cap = [&](const ClipResult &clipped, bool positiveSide, QVector<QVector3D> *points, QString *error) {
        const double weldTolerance = std::max(0.00001, double(std::max({meshExtent.x(), meshExtent.y(), meshExtent.z()})) * 1.0e-7);
        QHash<QString, QVector3D> positions;
        QHash<QString, QVector<int>> spatialCells;
        QVector<QVector3D> canonicalPoints;
        const auto cellKey = [](qint64 x, qint64 y, qint64 z) {
            return QStringLiteral("%1:%2:%3").arg(x).arg(y).arg(z);
        };
        // Rounded coordinate keys split coincident points when they fall on
        // opposite sides of a quantization-cell boundary. Search adjacent
        // cells and weld by actual distance instead, as STL facets duplicate
        // their vertices independently.
        const auto pointKey = [&](const QVector3D &point) {
            const qint64 cx = qint64(std::floor(double(point.x()) / weldTolerance));
            const qint64 cy = qint64(std::floor(double(point.y()) / weldTolerance));
            const qint64 cz = qint64(std::floor(double(point.z()) / weldTolerance));
            int nearest = -1;
            double nearestDistance = weldTolerance * weldTolerance;
            for (qint64 x = cx - 1; x <= cx + 1; ++x) {
                for (qint64 y = cy - 1; y <= cy + 1; ++y) {
                    for (qint64 z = cz - 1; z <= cz + 1; ++z) {
                        const QVector<int> candidates = spatialCells.value(cellKey(x, y, z));
                        for (int candidate : candidates) {
                            const QVector3D &existing = canonicalPoints[candidate];
                            const double dx = double(point.x()) - existing.x();
                            const double dy = double(point.y()) - existing.y();
                            const double dz = double(point.z()) - existing.z();
                            const double distance = dx * dx + dy * dy + dz * dz;
                            if (distance <= nearestDistance) {
                                nearest = candidate;
                                nearestDistance = distance;
                            }
                        }
                    }
                }
            }
            if (nearest < 0) {
                nearest = canonicalPoints.size();
                canonicalPoints.append(point);
                spatialCells[cellKey(cx, cy, cz)].append(nearest);
            }
            return QString::number(nearest);
        };
        QHash<QString, QVector<int>> adjacency;
        QVector<QPair<QString, QString>> edges;
        QSet<QString> segmentKeys;
        for (const auto &segment : clipped.cutSegments) {
            const QString a = pointKey(segment.first);
            const QString b = pointKey(segment.second);
            if (a == b)
                continue;
            positions.insert(a, canonicalPoints[a.toInt()]);
            positions.insert(b, canonicalPoints[b.toInt()]);
            const QString key = a < b ? a + QLatin1Char('|') + b : b + QLatin1Char('|') + a;
            if (segmentKeys.contains(key))
                continue;
            segmentKeys.insert(key);
            const int edgeIndex = edges.size();
            edges.append({a, b});
            adjacency[a].append(edgeIndex);
            adjacency[b].append(edgeIndex);
        }
        if (adjacency.isEmpty()) {
            *error = QStringLiteral("No closed cut contour was found.");
            return false;
        }
        // A plane through an existing mesh vertex can make several otherwise
        // separate contour arcs share the same welded key. Split that contact
        // into contour continuations by pairing the most opposite tangent
        // directions. Odd degree still means the source boundary is open.
        QHash<QString, QHash<int, int>> continuation;
        for (auto it = adjacency.cbegin(); it != adjacency.cend(); ++it) {
            QVector<int> incident = it.value();
            if (incident.size() < 2 || incident.size() % 2 != 0) {
                *error = QStringLiteral("The cut boundary is open or non-manifold.");
                return false;
            }
            while (!incident.isEmpty()) {
                int bestA = -1, bestB = -1;
                // Dot products can round slightly above 1.0f even after both
                // vectors are normalized. Starting at 1.0 then leaves the
                // pair unset when all candidate directions are parallel (a
                // common case for coincident/duplicated STL facets).
                double bestDot = std::numeric_limits<double>::infinity();
                for (qsizetype aIndex = 0; aIndex < incident.size(); ++aIndex) {
                    for (qsizetype bIndex = aIndex + 1; bIndex < incident.size(); ++bIndex) {
                        const int edgeA = incident[aIndex], edgeB = incident[bIndex];
                        const QString neighborA = edges[edgeA].first == it.key() ? edges[edgeA].second : edges[edgeA].first;
                        const QString neighborB = edges[edgeB].first == it.key() ? edges[edgeB].second : edges[edgeB].first;
                        // Do this in double precision. QVector3D subtraction and
                        // normalization are float operations and can overflow for
                        // valid STL coordinates with a large world-space offset.
                        const QVector3D origin = positions.value(it.key());
                        const QVector3D pointA = positions.value(neighborA);
                        const QVector3D pointB = positions.value(neighborB);
                        const double ax = double(pointA.x()) - origin.x();
                        const double ay = double(pointA.y()) - origin.y();
                        const double az = double(pointA.z()) - origin.z();
                        const double bx = double(pointB.x()) - origin.x();
                        const double by = double(pointB.y()) - origin.y();
                        const double bz = double(pointB.z()) - origin.z();
                        const double lengthA = std::sqrt(ax * ax + ay * ay + az * az);
                        const double lengthB = std::sqrt(bx * bx + by * by + bz * bz);
                        if (!std::isfinite(lengthA) || !std::isfinite(lengthB)
                            || lengthA <= 0.0 || lengthB <= 0.0)
                            continue;
                        const double alignment = (ax * bx + ay * by + az * bz) / (lengthA * lengthB);
                        if (std::isfinite(alignment) && alignment < bestDot) {
                            bestDot = alignment;
                            bestA = int(aIndex);
                            bestB = int(bIndex);
                        }
                    }
                }
                // A degenerate tangent can make every direction comparison
                // unusable. Still consume the two edges deterministically; the
                // subsequent closed-loop and manifold checks reject an invalid
                // result without leaving the user stuck at contour pairing.
                if (bestA < 0 || bestB < 0) {
                    bestA = 0;
                    bestB = 1;
                }
                const int edgeA = incident[bestA], edgeB = incident[bestB];
                continuation[it.key()].insert(edgeA, edgeB);
                continuation[it.key()].insert(edgeB, edgeA);
                incident.removeAt(bestB);
                incident.removeAt(bestA);
            }
        }
        QVector<QVector<QVector3D>> loops;
        QVector<bool> visited(edges.size(), false);
        for (int startEdge = 0; startEdge < edges.size(); ++startEdge) {
            if (visited[startEdge])
                continue;
            QVector<QVector3D> loop;
            const QString start = edges[startEdge].first;
            QString current = start;
            int edgeIndex = startEdge;
            int guard = edges.size() + 1;
            do {
                if (visited[edgeIndex] || guard-- <= 0) {
                    *error = QStringLiteral("The cut boundary crosses itself or repeats an edge.");
                    return false;
                }
                visited[edgeIndex] = true;
                loop.append(positions.value(current));
                const auto &edge = edges[edgeIndex];
                const QString next = edge.first == current ? edge.second : edge.first;
                const int nextEdge = continuation.value(next).value(edgeIndex, -1);
                if (nextEdge < 0) {
                    *error = QStringLiteral("The cut boundary did not form a closed contour.");
                    return false;
                }
                current = next;
                edgeIndex = nextEdge;
            } while (current != start || edgeIndex != startEdge);
            if (current != start || loop.size() < 3) {
                *error = QStringLiteral("The cut boundary did not form a closed contour.");
                return false;
            }
            loops.append(loop);
        }
        QVector<QVector3D> capPoints;
        if (!triangulateCapLoops(loops, normal, positiveSide, &capPoints, error))
            return false;
        *points += capPoints;
        return true;
    };

    QVector<QVector3D> keptPoints = kept.points;
    QVector<QVector3D> oppositePoints = opposite.points;
    QString keptCapError;
    const bool keptCapped = cap(kept, keepPositive, &keptPoints, &keptCapError);
    QString oppositeCapError;
    const bool oppositeCapped = !oppositeOutput
        || cap(opposite, !keepPositive, &oppositePoints, &oppositeCapError);
    const bool capped = keptCapped && oppositeCapped;
    // Cap construction can fail on open or damaged source meshes even though
    // clipping produced usable sections. Discard any partial cap triangles and
    // keep the deterministic clipped shells so the cut itself still succeeds.
    if (!capped) {
        keptPoints = kept.points;
        oppositePoints = opposite.points;
    }
    // Validate both outputs before committing either one. setTrianglePoints
    // cannot fail after this check, keeping a two-piece cut atomic.
    const auto validTrianglePoints = [](const QVector<QVector3D> &points) {
        if (points.isEmpty() || points.size() % 3 != 0)
            return false;
        for (const QVector3D &point : points) {
            if (!finite(point))
                return false;
        }
        return true;
    };
    if (!validTrianglePoints(keptPoints) || (oppositeOutput && !validTrianglePoints(oppositePoints)))
        return {{QStringLiteral("error"), QStringLiteral("The cut produced invalid geometry; the original mesh was kept unchanged.")}};
    const auto isClosedManifold = [](const QVector<QVector3D> &points) {
        const QVariantMap metrics = meshMetrics(points, 1.0e-5);
        return metrics.value(QStringLiteral("boundaryEdges")).toInt() == 0
            && metrics.value(QStringLiteral("nonManifoldEdges")).toInt() == 0
            && metrics.value(QStringLiteral("degenerateTriangles")).toInt() == 0;
    };
    const bool outputsWatertight = capped && isClosedManifold(keptPoints)
        && (!oppositeOutput || isClosedManifold(oppositePoints));
    const int resultTriangles = int(keptPoints.size() / 3);
    const int oppositeTriangles = int(oppositePoints.size() / 3);
    if (!keptOutput->setTrianglePoints(keptPoints, m_fileName, QStringLiteral("kept cut section")))
        return {{QStringLiteral("error"), QStringLiteral("The kept cut section could not be rebuilt; the source mesh was kept unchanged.")}};
    if (oppositeOutput && !oppositeOutput->setTrianglePoints(oppositePoints, m_fileName, QStringLiteral("other cut section")))
        return {{QStringLiteral("error"), QStringLiteral("The second cut section could not be rebuilt; the source mesh was kept unchanged.")}};
    QVariantMap response{{QStringLiteral("triangles"), resultTriangles},
                         {QStringLiteral("removedTriangles"), kept.removed},
                         {QStringLiteral("intersectedTriangles"), kept.changed}};
    if (oppositeOutput)
        response.insert(QStringLiteral("oppositeTriangles"), oppositeTriangles);
    response.insert(QStringLiteral("capped"), capped);
    response.insert(QStringLiteral("outputsWatertight"), outputsWatertight);
    response.insert(QStringLiteral("sourceRevisionId"), m_revisionId);
    response.insert(QStringLiteral("keptRevisionId"), keptOutput->revisionId());
    if (oppositeOutput)
        response.insert(QStringLiteral("oppositeRevisionId"), oppositeOutput->revisionId());
    response.insert(QStringLiteral("operation"), QStringLiteral("slice"));
    if (!capped) {
        const QString capError = !keptCapped ? keptCapError : oppositeCapError;
        response.insert(QStringLiteral("warning"),
                        QStringLiteral("Sections were separated, but the cut faces could not be closed: %1")
                            .arg(capError));
    } else if (!outputsWatertight) {
        response.insert(QStringLiteral("warning"),
                        QStringLiteral("Cut faces were closed, but the result still contains open or non-manifold source geometry."));
    }
    return response;
}

void MeshGeometry::clearMesh()
{
    clear();
    update();
    m_loaded = false;
    m_fileName.clear();
    m_revisionId.clear();
    m_dimensions = {};
    m_center = {};
    m_sampledFaceNormals.clear();
    m_trianglePoints.clear();
    emit loadedChanged();
}
