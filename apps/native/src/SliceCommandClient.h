#pragma once

#include <QNetworkAccessManager>
#include <QObject>
#include <QPointer>
#include <QQueue>
#include <QSharedPointer>
#include <QUrl>
#include <QVector3D>
#include <QMatrix4x4>

class SliceCommandClient final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QUrl apiBaseUrl READ apiBaseUrl WRITE setApiBaseUrl NOTIFY apiBaseUrlChanged)

public:
    explicit SliceCommandClient(QObject *parent = nullptr);

    QUrl apiBaseUrl() const { return m_apiBaseUrl; }
    void setApiBaseUrl(const QUrl &url);
    void setOutputDirectory(const QString &path);

    Q_INVOKABLE void registerSource(const QUrl &sourceFile, const QString &filename);
    Q_INVOKABLE void sliceModel(const QString &requestId, const QString &modelId,
                                const QVector3D &originMm, const QVector3D &normal,
                                bool keepPositive, const QMatrix4x4 &localToWorld);

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

private:
    struct PendingSource {
        QUrl sourceUrl;
        QString filename;
    };
    struct PendingSlice;

    QUrl apiUrl(const QString &path) const;
    void createProject();
    void uploadQueuedSources();
    void uploadSource(const PendingSource &source);
    void finishSliceDownload(const QSharedPointer<PendingSlice> &pending, bool top);
    void finalizeSlice(const QSharedPointer<PendingSlice> &pending);

    QNetworkAccessManager m_network;
    QUrl m_apiBaseUrl;
    QString m_outputDirectory;
    QString m_projectId;
    bool m_projectRequestActive = false;
    QQueue<PendingSource> m_pendingSources;
};
