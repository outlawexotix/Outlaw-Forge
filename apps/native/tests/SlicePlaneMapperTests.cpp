#include "../src/SlicePlaneMapper.h"

#include <QMatrix4x4>
#include <QVector4D>
#include <QtTest>

class SlicePlaneMapperTests : public QObject
{
    Q_OBJECT

private:
    static bool mapAndPreserveSide(const QMatrix4x4 &localToWorld, const QVector3D &origin,
                                   const QVector3D &normal, const QVector3D &probe)
    {
        QVector3D localOrigin;
        QVector3D localNormal;
        QString error;
        if (!SlicePlaneMapper::mapWorldPlaneToLocal(localToWorld, origin, normal,
                                                     &localOrigin, &localNormal, &error))
            return false;

        bool invertible = false;
        const QMatrix4x4 worldToLocal = localToWorld.inverted(&invertible);
        if (!invertible)
            return false;
        const QVector3D worldProbe = (localToWorld * QVector4D(probe, 1.0f)).toVector3D();
        const QVector3D localProbe = (worldToLocal * QVector4D(worldProbe, 1.0f)).toVector3D();
        const float worldSide = QVector3D::dotProduct(normal, worldProbe - origin);
        const float localSide = QVector3D::dotProduct(localNormal, localProbe - localOrigin);
        return localSide * worldSide > 0.0f && qAbs(localNormal.length() - 1.0f) < 1e-5f;
    }

private slots:
    void identityKeepsPlaneCoordinates()
    {
        const QMatrix4x4 identity;
        const QVector3D origin(2.0f, -3.0f, 4.0f);
        const QVector3D normal(0.0f, 0.0f, 1.0f);
        QVector3D localOrigin;
        QVector3D localNormal;
        QString error;

        QVERIFY2(SlicePlaneMapper::mapWorldPlaneToLocal(identity, origin, normal,
                                                         &localOrigin, &localNormal, &error),
                 qPrintable(error));
        QVERIFY((localOrigin - origin).length() < 1e-5f);
        QVERIFY((localNormal - normal).length() < 1e-5f);
    }

    void translationAndRotationPreserveTheWorldPlane()
    {
        QMatrix4x4 transform;
        transform.translate(8.0f, -5.0f, 3.0f);
        transform.rotate(37.0f, 0.0f, 0.0f, 1.0f);
        const QVector3D origin(3.0f, 2.0f, 1.0f);
        const QVector3D normal(0.3f, -0.2f, 1.0f);
        QVERIFY(mapAndPreserveSide(transform, origin, normal, QVector3D(1.0f, 3.0f, 2.0f)));
    }

    void nonUniformScalePreservesTheWorldPlane()
    {
        QMatrix4x4 transform;
        transform.rotate(-23.0f, 0.0f, 1.0f, 0.0f);
        transform.scale(2.0f, 0.5f, 3.0f);
        QVERIFY(mapAndPreserveSide(transform, QVector3D(0.5f, 1.0f, -2.0f),
                                  QVector3D(0.4f, 0.6f, 0.7f), QVector3D(2.0f, -1.0f, 3.0f)));
    }

    void reflectionPreservesTheRequestedSignedSide()
    {
        QMatrix4x4 transform;
        transform.translate(4.0f, 0.0f, 0.0f);
        transform.scale(-1.0f, 2.0f, 0.5f);
        QVERIFY(mapAndPreserveSide(transform, QVector3D(1.0f, 0.0f, 0.0f),
                                  QVector3D(1.0f, 0.2f, 0.0f), QVector3D(3.0f, 1.0f, 0.0f)));
    }

    void singularTransformIsRejected()
    {
        QMatrix4x4 transform;
        transform.scale(1.0f, 0.0f, 1.0f);
        QVector3D localOrigin;
        QVector3D localNormal;
        QString error;

        QVERIFY(!SlicePlaneMapper::mapWorldPlaneToLocal(transform, QVector3D(), QVector3D(0, 0, 1),
                                                         &localOrigin, &localNormal, &error));
        QVERIFY(!error.isEmpty());
    }

    void zeroNormalIsRejected()
    {
        QVector3D localOrigin;
        QVector3D localNormal;
        QString error;

        QVERIFY(!SlicePlaneMapper::mapWorldPlaneToLocal(QMatrix4x4(), QVector3D(), QVector3D(),
                                                         &localOrigin, &localNormal, &error));
        QVERIFY(!error.isEmpty());
    }
};

QTEST_GUILESS_MAIN(SlicePlaneMapperTests)
#include "SlicePlaneMapperTests.moc"
