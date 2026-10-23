#include "MeshGeometry.h"

#include <QFile>
#include <QFileInfo>
#include <QCryptographicHash>
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
#include <QVariantMap>
#include <algorithm>
#include <bit>
#include <cmath>
#include <limits>
#include <mapbox/earcut.hpp>

namespace {
struct Vertex {
    float position[3];
    float normal[3];
};

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
            {QStringLiteral("nonManifoldEdges"), nonManifold}};
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

    const int verticesAfterRepair = meshMetrics(repaired, weldToleranceMm)
                                        .value(QStringLiteral("vertices")).toInt();
    const int weldedVertices = before.value(QStringLiteral("vertices")).toInt() - verticesAfterRepair;
    if (!setTrianglePoints(repaired, m_fileName, QStringLiteral("repaired mesh")))
        return {{QStringLiteral("error"), QStringLiteral("The repaired mesh could not be rebuilt. The current mesh was kept unchanged.")}};
    return {{QStringLiteral("removedTriangles"), removed},
            {QStringLiteral("weldedVertices"), std::max(0, weldedVertices)},
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
