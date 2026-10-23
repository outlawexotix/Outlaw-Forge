#include "../src/SliceCommandClient.h"

#include <QDir>
#include <QElapsedTimer>
#include <QCoreApplication>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkRequest>
#include <QTcpServer>
#include <QTcpSocket>
#include <QTemporaryDir>
#include <QtTest>

class SliceApiStub final : public QObject
{
    Q_OBJECT

public:
    explicit SliceApiStub(QObject *parent = nullptr) : QObject(parent)
    {
        connect(&m_server, &QTcpServer::newConnection, this, [this] {
            while (QTcpSocket *socket = m_server.nextPendingConnection()) {
                connect(socket, &QTcpSocket::readyRead, this, [this, socket] { readRequest(socket); });
                connect(socket, &QTcpSocket::disconnected, socket, &QObject::deleteLater);
            }
        });
    }

    bool listen() { return m_server.listen(QHostAddress::LocalHost); }
    QUrl baseUrl() const { return QUrl(QStringLiteral("http://127.0.0.1:%1").arg(m_server.serverPort())); }
    QStringList paths() const { return m_paths; }
    QJsonObject slicePayload() const { return m_slicePayload; }
    bool failSlice = false;
    bool malformedSlice = false;
    bool failBottomDownload = false;

private:
    void readRequest(QTcpSocket *socket)
    {
        QByteArray request = socket->property("requestBuffer").toByteArray();
        request += socket->readAll();
        socket->setProperty("requestBuffer", request);
        if (socket->property("requestHandled").toBool())
            return;

        const qsizetype headerEnd = request.indexOf("\r\n\r\n");
        if (headerEnd < 0)
            return;
        const QByteArray headers = request.left(headerEnd);
        const QList<QByteArray> lines = headers.split('\n');
        const QByteArray requestLine = lines.isEmpty() ? QByteArray() : lines.first().trimmed();
        const QList<QByteArray> requestParts = requestLine.split(' ');
        if (requestParts.size() < 2)
            return;
        const QByteArray method = requestParts[0];
        const QByteArray path = requestParts[1];
        qsizetype contentLength = 0;
        for (const QByteArray &line : lines) {
            if (line.toLower().startsWith("content-length:"))
                contentLength = line.mid(line.indexOf(':') + 1).trimmed().toLongLong();
        }
        if (request.size() < headerEnd + 4 + contentLength)
            return;
        socket->setProperty("requestHandled", true);
        const QByteArray body = request.mid(headerEnd + 4, contentLength);
        m_paths.append(QString::fromUtf8(path));
        if (method == "POST" && path == "/api/v1/projects") {
            respond(socket, 201, "{\"id\":\"project-1\"}");
        } else if (method == "POST" && path == "/api/v1/projects/project-1/models/import") {
            respond(socket, 201, "{\"id\":\"source-model-1\"}");
        } else if (method == "POST" && path == "/api/v1/projects/project-1/models/source-model-1/slice") {
            m_slicePayload = QJsonDocument::fromJson(body).object();
            if (failSlice) {
                respond(socket, 400, "{\"detail\":\"cut rejected by service\"}");
            } else if (malformedSlice) {
                respond(socket, 200, "not-json");
            } else {
                respond(socket, 200,
                        "{\"top_model\":{\"id\":\"top-model-1\",\"filename\":\"source_top.stl\",\"file_format\":\"stl\",\"is_watertight\":true},"
                        "\"bottom_model\":{\"id\":\"bottom-model-1\",\"filename\":\"source_bottom.stl\",\"file_format\":\"stl\",\"is_watertight\":false},"
                        "\"cut_area_cm2\":1.25,\"message\":\"slice recorded\"}");
            }
        } else if (method == "GET" && path == "/api/v1/projects/project-1/models/top-model-1/file") {
            respond(socket, 200, "top-mesh-data", "model/stl");
        } else if (method == "GET" && path == "/api/v1/projects/project-1/models/bottom-model-1/file") {
            if (failBottomDownload)
                respond(socket, 503, "{\"detail\":\"download unavailable\"}");
            else
                respond(socket, 200, "bottom-mesh-data", "model/stl");
        } else {
            respond(socket, 404, "{\"detail\":\"unknown test route\"}");
        }
    }

    static void respond(QTcpSocket *socket, int status, const QByteArray &body,
                        const QByteArray &contentType = "application/json")
    {
        QByteArray reason = status == 200 || status == 201 ? "OK" : status == 400 ? "Bad Request" : "Service Unavailable";
        if (status == 404)
            reason = "Not Found";
        QByteArray response = "HTTP/1.1 " + QByteArray::number(status) + " " + reason + "\r\n";
        response += "Content-Type: " + contentType + "\r\n";
        response += "Content-Length: " + QByteArray::number(body.size()) + "\r\n";
        response += "Connection: close\r\n\r\n";
        response += body;
        socket->write(response);
        socket->disconnectFromHost();
    }

    QTcpServer m_server;
    QStringList m_paths;
    QJsonObject m_slicePayload;
};

class SliceCommandClientTests final : public QObject
{
    Q_OBJECT

private:
    static QString makeSourceFile(QTemporaryDir &directory)
    {
        const QString path = directory.filePath(QStringLiteral("source.stl"));
        QFile file(path);
        if (!file.open(QIODevice::WriteOnly))
            return {};
        file.write("immutable source mesh");
        file.close();
        return path;
    }

    static bool waitForRegistration(QSignalSpy &registered, QSignalSpy &failed)
    {
        QElapsedTimer timer;
        timer.start();
        while (registered.isEmpty() && failed.isEmpty() && timer.elapsed() < 3000) {
            QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
            QTest::qWait(10);
        }
        return registered.count() == 1;
    }

private slots:
    void createUploadSliceAndDownloadBothResults()
    {
        SliceApiStub server;
        QVERIFY(server.listen());
        QTemporaryDir inputs;
        QTemporaryDir outputs;
        QVERIFY(inputs.isValid() && outputs.isValid());
        const QString sourcePath = makeSourceFile(inputs);
        QVERIFY(!sourcePath.isEmpty());
        SliceCommandClient client;
        client.setApiBaseUrl(server.baseUrl());
        client.setOutputDirectory(outputs.path());
        QSignalSpy registered(&client, &SliceCommandClient::sourceRegistered);
        QSignalSpy registrationFailed(&client, &SliceCommandClient::sourceRegistrationFailed);
        client.registerSource(QUrl::fromLocalFile(sourcePath), QStringLiteral("source.stl"));
        QVERIFY(waitForRegistration(registered, registrationFailed));
        QCOMPARE(registered.first().at(2).toString(), QStringLiteral("source-model-1"));

        QMatrix4x4 transform;
        transform.translate(10.0f, 0.0f, 0.0f);
        QSignalSpy completed(&client, &SliceCommandClient::sliceCompleted);
        QSignalSpy failed(&client, &SliceCommandClient::sliceFailed);
        client.sliceModel(QStringLiteral("instance-1"), QStringLiteral("source-model-1"),
                          QVector3D(10.0f, 0.0f, 2.0f), QVector3D(0.0f, 0.0f, 1.0f), true, transform);
        QTRY_VERIFY_WITH_TIMEOUT(completed.count() + failed.count() > 0, 3000);
        QCOMPARE(failed.count(), 0);
        QCOMPARE(completed.count(), 1);

        const QList<QVariant> result = completed.first();
        QCOMPARE(result.at(0).toString(), QStringLiteral("instance-1"));
        QCOMPARE(result.at(1).toString(), QStringLiteral("top-model-1"));
        QCOMPARE(result.at(4).toBool(), true);
        QCOMPARE(result.at(5).toString(), QStringLiteral("bottom-model-1"));
        QCOMPARE(result.at(8).toBool(), false);
        QVERIFY(qAbs(result.at(9).toDouble() - 1.25) < 1e-6);
        QFile top(result.at(3).toUrl().toLocalFile());
        QFile bottom(result.at(7).toUrl().toLocalFile());
        QVERIFY(top.open(QIODevice::ReadOnly));
        QVERIFY(bottom.open(QIODevice::ReadOnly));
        QCOMPARE(top.readAll(), QByteArray("top-mesh-data"));
        QCOMPARE(bottom.readAll(), QByteArray("bottom-mesh-data"));

        const QJsonObject payload = server.slicePayload();
        const QJsonArray origin = payload.value(QStringLiteral("plane_origin")).toArray();
        const QJsonArray normal = payload.value(QStringLiteral("plane_normal")).toArray();
        QCOMPARE(origin.size(), 3);
        QVERIFY(qAbs(origin[0].toDouble()) < 1e-6);
        QVERIFY(qAbs(origin[2].toDouble() - 2.0) < 1e-6);
        QVERIFY(qAbs(normal[2].toDouble() - 1.0) < 1e-6);
        QCOMPARE(payload.value(QStringLiteral("cap_faces")).toBool(), true);
        QCOMPARE(payload.value(QStringLiteral("create_pegs")).toBool(), false);
        QVERIFY(server.paths().contains(QStringLiteral("/api/v1/projects")));
        QVERIFY(server.paths().contains(QStringLiteral("/api/v1/projects/project-1/models/import")));
        QVERIFY(server.paths().contains(QStringLiteral("/api/v1/projects/project-1/models/source-model-1/slice")));
        QVERIFY(server.paths().contains(QStringLiteral("/api/v1/projects/project-1/models/top-model-1/file")));
        QVERIFY(server.paths().contains(QStringLiteral("/api/v1/projects/project-1/models/bottom-model-1/file")));

        QFile original(sourcePath);
        QVERIFY(original.open(QIODevice::ReadOnly));
        QCOMPARE(original.readAll(), QByteArray("immutable source mesh"));
    }

    void serviceSliceErrorIsReported()
    {
        SliceApiStub server;
        server.failSlice = true;
        QVERIFY(server.listen());
        QTemporaryDir inputs;
        const QString sourcePath = makeSourceFile(inputs);
        SliceCommandClient client;
        client.setApiBaseUrl(server.baseUrl());
        QSignalSpy registered(&client, &SliceCommandClient::sourceRegistered);
        QSignalSpy registrationFailed(&client, &SliceCommandClient::sourceRegistrationFailed);
        client.registerSource(QUrl::fromLocalFile(sourcePath), QStringLiteral("source.stl"));
        QVERIFY(waitForRegistration(registered, registrationFailed));

        QSignalSpy failed(&client, &SliceCommandClient::sliceFailed);
        client.sliceModel(QStringLiteral("instance-2"), QStringLiteral("source-model-1"),
                          QVector3D(), QVector3D(0, 0, 1), true, QMatrix4x4());
        QTRY_COMPARE_WITH_TIMEOUT(failed.count(), 1, 3000);
        QCOMPARE(failed.first().at(0).toString(), QStringLiteral("instance-2"));
        QVERIFY(failed.first().at(1).toString().contains(QStringLiteral("cut rejected by service")));
        QVERIFY(failed.first().at(2).toString().isEmpty());
        QVERIFY(failed.first().at(3).toString().isEmpty());
    }

    void malformedSliceJsonIsReported()
    {
        SliceApiStub server;
        server.malformedSlice = true;
        QVERIFY(server.listen());
        QTemporaryDir inputs;
        const QString sourcePath = makeSourceFile(inputs);
        SliceCommandClient client;
        client.setApiBaseUrl(server.baseUrl());
        QSignalSpy registered(&client, &SliceCommandClient::sourceRegistered);
        QSignalSpy registrationFailed(&client, &SliceCommandClient::sourceRegistrationFailed);
        client.registerSource(QUrl::fromLocalFile(sourcePath), QStringLiteral("source.stl"));
        QVERIFY(waitForRegistration(registered, registrationFailed));

        QSignalSpy failed(&client, &SliceCommandClient::sliceFailed);
        client.sliceModel(QStringLiteral("instance-3"), QStringLiteral("source-model-1"),
                          QVector3D(), QVector3D(0, 0, 1), true, QMatrix4x4());
        QTRY_COMPARE_WITH_TIMEOUT(failed.count(), 1, 3000);
        QVERIFY(failed.first().at(1).toString().contains(QStringLiteral("JSON"), Qt::CaseInsensitive));
    }

    void partialDownloadReportsPersistedIdsAndLeavesNoFiles()
    {
        SliceApiStub server;
        server.failBottomDownload = true;
        QVERIFY(server.listen());
        QTemporaryDir inputs;
        QTemporaryDir outputs;
        const QString sourcePath = makeSourceFile(inputs);
        SliceCommandClient client;
        client.setApiBaseUrl(server.baseUrl());
        client.setOutputDirectory(outputs.path());
        QSignalSpy registered(&client, &SliceCommandClient::sourceRegistered);
        QSignalSpy registrationFailed(&client, &SliceCommandClient::sourceRegistrationFailed);
        client.registerSource(QUrl::fromLocalFile(sourcePath), QStringLiteral("source.stl"));
        QVERIFY(waitForRegistration(registered, registrationFailed));

        QSignalSpy failed(&client, &SliceCommandClient::sliceFailed);
        client.sliceModel(QStringLiteral("instance-4"), QStringLiteral("source-model-1"),
                          QVector3D(), QVector3D(0, 0, 1), true, QMatrix4x4());
        QTRY_COMPARE_WITH_TIMEOUT(failed.count(), 1, 3000);
        QCOMPARE(failed.first().at(2).toString(), QStringLiteral("top-model-1"));
        QCOMPARE(failed.first().at(3).toString(), QStringLiteral("bottom-model-1"));
        const QStringList files = QDir(outputs.path()).entryList(QDir::Files | QDir::Hidden | QDir::NoDotAndDotDot);
        QVERIFY2(files.isEmpty(), qPrintable(files.join(QLatin1Char(','))));
    }
};

QTEST_GUILESS_MAIN(SliceCommandClientTests)
#include "SliceCommandClientTests.moc"
