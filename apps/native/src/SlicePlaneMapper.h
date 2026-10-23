#pragma once

#include <QMatrix4x4>
#include <QString>
#include <QVector3D>

class SlicePlaneMapper final
{
public:
    static bool mapWorldPlaneToLocal(const QMatrix4x4 &localToWorld,
                                     const QVector3D &worldOrigin,
                                     const QVector3D &worldNormal,
                                     QVector3D *localOrigin,
                                     QVector3D *localNormal,
                                     QString *error);
};
