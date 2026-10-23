#pragma once

#include <QtQuick3D/QQuick3DGeometry>
#include <QVariantList>
#include <QVariantMap>
#include <QVector3D>

class MeshGeometry : public QQuick3DGeometry
{
    Q_OBJECT
    Q_PROPERTY(bool loaded READ loaded NOTIFY loadedChanged)
    Q_PROPERTY(QString fileName READ fileName NOTIFY loadedChanged)
    Q_PROPERTY(QVector3D dimensions READ dimensions NOTIFY loadedChanged)
    Q_PROPERTY(QVector3D center READ center NOTIFY loadedChanged)
    Q_PROPERTY(QVariantList sampledFaceNormals READ sampledFaceNormals NOTIFY loadedChanged)
    Q_PROPERTY(int triangleCount READ triangleCount NOTIFY loadedChanged)
    Q_PROPERTY(QString revisionId READ revisionId NOTIFY loadedChanged)

public:
    explicit MeshGeometry(QQuick3DObject *parent = nullptr);
    bool loaded() const { return m_loaded; }
    QString fileName() const { return m_fileName; }
    QVector3D dimensions() const { return m_dimensions; }
    QVector3D center() const { return m_center; }
    QVariantList sampledFaceNormals() const { return m_sampledFaceNormals; }
    int triangleCount() const { return int(m_trianglePoints.size() / 3); }
    QString revisionId() const { return m_revisionId; }

    Q_INVOKABLE bool loadStl(const QUrl &url);
    Q_INVOKABLE bool loadObj(const QUrl &url);
    Q_INVOKABLE bool load3mf(const QUrl &url);
    Q_INVOKABLE bool copyMeshFrom(const MeshGeometry *source);
    Q_INVOKABLE QVariantMap exportLocalStl(const QUrl &url) const;
    Q_INVOKABLE QVariantMap exportStl(const QUrl &url, const QVector3D &offsetMm,
                                      const QVector3D &rotationDeg, const QVector3D &scale) const;
    Q_INVOKABLE void clearMesh();
    Q_INVOKABLE QVariantMap analyzeMesh() const;
    Q_INVOKABLE int connectedComponentCount() const;
    Q_INVOKABLE QVariantMap splitConnectedComponents(const QVariantList &outputs) const;
    Q_INVOKABLE QVariantMap simplifyMesh(double targetReductionPercent, MeshGeometry *output) const;
    Q_INVOKABLE QVector3D instanceOffsetCorrection(const MeshGeometry *derivedGeometry,
                                                   const QVector3D &instanceScale,
                                                   const QVector3D &instanceRotationDeg) const;
    Q_INVOKABLE QVariantMap repairMesh(double weldToleranceMm);
    Q_INVOKABLE QVariantMap autoOrient(double criticalAngleDeg = 65.0);
    Q_INVOKABLE QVariantMap sliceByPlane(const QVector3D &pointMm, const QVector3D &normal, bool keepPositive,
                                         MeshGeometry *keptOutput, MeshGeometry *oppositeOutput = nullptr) const;

signals:
    void loadedChanged();
    void loadFailed(const QString &message);

private:
    friend class MeshGeometrySliceTests;

    bool m_loaded = false;
    QString m_fileName;
    QString m_revisionId;
    QVector3D m_dimensions;
    QVector3D m_center;
    QVariantList m_sampledFaceNormals;
    QVector<QVector3D> m_trianglePoints;

    bool setTrianglePoints(const QVector<QVector3D> &points, const QString &path, const QString &format);
};
