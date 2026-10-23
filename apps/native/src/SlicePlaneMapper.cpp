#include "SlicePlaneMapper.h"

#include <QVector4D>
#include <QtMath>

bool SlicePlaneMapper::mapWorldPlaneToLocal(const QMatrix4x4 &localToWorld,
                                            const QVector3D &worldOrigin,
                                            const QVector3D &worldNormal,
                                            QVector3D *localOrigin,
                                            QVector3D *localNormal,
                                            QString *error)
{
    if (!localOrigin || !localNormal) {
        if (error)
            *error = QStringLiteral("Plane mapping requires output coordinates.");
        return false;
    }

    const float normalLengthSquared = worldNormal.lengthSquared();
    if (!qIsFinite(normalLengthSquared) || normalLengthSquared < 1.0e-12f) {
        if (error)
            *error = QStringLiteral("Slice plane normal must be finite and non-zero.");
        return false;
    }

    bool invertible = false;
    const QMatrix4x4 worldToLocal = localToWorld.inverted(&invertible);
    if (!invertible) {
        if (error)
            *error = QStringLiteral("Selected instance transform cannot be inverted.");
        return false;
    }

    const QVector4D transformedOrigin = worldToLocal * QVector4D(worldOrigin, 1.0f);
    if (!qIsFinite(transformedOrigin.w()) || qAbs(transformedOrigin.w()) < 1.0e-8f) {
        if (error)
            *error = QStringLiteral("Slice plane origin cannot be mapped into mesh coordinates.");
        return false;
    }
    *localOrigin = transformedOrigin.toVector3DAffine();

    // Plane normals transform by the transpose of the forward linear matrix.
    // This keeps the plane equation and signed side correct under non-uniform
    // scale and reflection.
    QVector3D mappedNormal(
        localToWorld(0, 0) * worldNormal.x() + localToWorld(1, 0) * worldNormal.y() + localToWorld(2, 0) * worldNormal.z(),
        localToWorld(0, 1) * worldNormal.x() + localToWorld(1, 1) * worldNormal.y() + localToWorld(2, 1) * worldNormal.z(),
        localToWorld(0, 2) * worldNormal.x() + localToWorld(1, 2) * worldNormal.y() + localToWorld(2, 2) * worldNormal.z());
    const float mappedLengthSquared = mappedNormal.lengthSquared();
    if (!qIsFinite(mappedLengthSquared) || mappedLengthSquared < 1.0e-12f) {
        if (error)
            *error = QStringLiteral("Slice plane normal cannot be mapped into mesh coordinates.");
        return false;
    }

    *localNormal = mappedNormal / qSqrt(mappedLengthSquared);
    if (error)
        error->clear();
    return true;
}
