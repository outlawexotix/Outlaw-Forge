#include <QGuiApplication>
#include <QQmlContext>
#include <QQmlApplicationEngine>
#include <QQuickStyle>
#include <QtQml/qqml.h>
#include "MeshGeometry.h"
#include "SliceCommandClient.h"
#include <cstdlib>

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    QGuiApplication::setApplicationName("Outlaw Forge");
    QGuiApplication::setOrganizationName("Outlaw Forge");
    QQuickStyle::setStyle("Basic");
    qmlRegisterType<MeshGeometry>("OutlawForge.NativeTypes", 1, 0, "MeshGeometry");

    SliceCommandClient sliceCommandClient;
    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty("sliceCommandClient", &sliceCommandClient);
    engine.loadFromModule("OutlawForge.Native", "Main");
    if (engine.rootObjects().isEmpty())
        return EXIT_FAILURE;

    return app.exec();
}
