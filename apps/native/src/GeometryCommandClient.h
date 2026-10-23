#pragma once

#include <QNetworkAccessManager>
#include <QHash>
#include <QObject>
#include <QPointer>
#include <QQueue>
#include <QSharedPointer>
#include <QUrl>
#include <QVector3D>
#include <QMatrix4x4>
#include <QVariantMap>

class GeometryCommandClient final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QUrl apiBaseUrl READ apiBaseUrl WRITE setApiBaseUrl NOTIFY apiBaseUrlChanged)

public:
    explicit GeometryCommandClient(QObject *parent = nullptr);

    QUrl apiBaseUrl() const { return m_apiBaseUrl; }
    void setApiBaseUrl(const QUrl &url);
    void setOutputDirectory(const QString &path);

    Q_INVOKABLE void registerSource(const QUrl &sourceFile, const QString &filename);
    Q_INVOKABLE void sliceModel(const QString &requestId, const QString &modelId,
                                const QVector3D &originMm, const QVector3D &normal,
                                bool keepPositive, const QMatrix4x4 &localToWorld);
    Q_INVOKABLE void autoOrientModel(const QString &requestId, const QString &modelId);
    Q_INVOKABLE void retryAutoOrientDownload(const QString &requestId);
    Q_INVOKABLE void repairModel(const QString &requestId, const QString &modelId, double weldToleranceMm);
    Q_INVOKABLE void retryRepairDownload(const QString &requestId);

signals:
    void apiBaseUrlChanged();
    void sourceRegistered(const QUrl &sourceUrl, const QString &projectId, const QString &modelId);
    void sourceRegistrationFailed(const QUrl &sourceUrl, const QString &message);
    void sliceCompleted(const QString &requestId,
                        const QString &topModelId, const QString &topName, const QUrl &topUrl, bool topWatertight,
                        const QString &bottomModelId, const QString &bottomName, const QUrl &bottomUrl, bool bottomWatertight,
                        double cutAreaCm2, const QString &message);
    void sliceFailed(const QString &requestId, const QString &message,
                     const QString &persistedTopModelId, const QString &persistedBottomModelId);
    void autoOrientCompleted(const QString &requestId, const QString &modelId,
                             const QString &filename, const QUrl &localFileUrl,
                             const QVector3D &optimalRotationDeg,
                             double originalOverhangCm2, double optimizedOverhangCm2,
                             double reductionPercentage, const QString &message);
    void autoOrientFailed(const QString &requestId, const QString &message);
    void autoOrientDownloadFailed(const QString &requestId, const QString &modelId, const QString &message);
    void repairCompleted(const QString &requestId, const QString &modelId, const QString &filename,
                         const QUrl &localFileUrl, const QVariantMap &report, const QString &message);
    void repairFailed(const QString &requestId, const QString &message);
    void repairDownloadFailed(const QString &requestId, const QString &modelId, const QString &message);

private:
    struct PendingSource {
        QUrl sourceUrl;
        QString filename;
    };
    struct PendingSlice;
    struct PendingAutoOrient;
    struct PendingRepair;

    QUrl apiUrl(const QString &path) const;
    void createProject();
    void uploadQueuedSources();
    void uploadSource(const PendingSource &source);
    void finishSliceDownload(const QSharedPointer<PendingSlice> &pending, bool top);
    void finalizeSlice(const QSharedPointer<PendingSlice> &pending);
    void startAutoOrientDownload(const QSharedPointer<PendingAutoOrient> &pending);
    void finishAutoOrientDownload(const QSharedPointer<PendingAutoOrient> &pending);
    void startRepairDownload(const QSharedPointer<PendingRepair> &pending);
    void finishRepairDownload(const QSharedPointer<PendingRepair> &pending);

    QNetworkAccessManager m_network;
    QUrl m_apiBaseUrl;
    QString m_outputDirectory;
    QString m_autoOrientOutputDirectory;
    QString m_repairOutputDirectory;
    QString m_projectId;
    bool m_projectRequestActive = false;
    QQueue<PendingSource> m_pendingSources;
    QHash<QString, QSharedPointer<PendingAutoOrient>> m_pendingAutoOrientDownloads;
    QHash<QString, QSharedPointer<PendingRepair>> m_pendingRepairDownloads;
};
