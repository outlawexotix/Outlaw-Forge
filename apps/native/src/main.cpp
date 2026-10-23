#include <QGuiApplication>
#include <QQmlContext>
#include <QQmlApplicationEngine>
#include <QQuickStyle>
#include <QIcon>
#include <QtQml/qqml.h>
#include "MeshGeometry.h"
#include "NativeProjectStore.h"
#include <cstdlib>

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    QGuiApplication::setApplicationName("Outlaw Forge");
    QGuiApplication::setOrganizationName("Outlaw Forge");
    QGuiApplication::setWindowIcon(QIcon(":/icons/outlaw-forge-icon.png"));
    QQuickStyle::setStyle("Basic");
    qmlRegisterType<MeshGeometry>("OutlawForge.NativeTypes", 1, 0, "MeshGeometry");
    qmlRegisterType<NativeProjectStore>("OutlawForge.NativeTypes", 1, 0, "NativeProjectStore");

    QQmlApplicationEngine engine;
    engine.loadFromModule("OutlawForge.Native", "Main");
    if (engine.rootObjects().isEmpty())
        return EXIT_FAILURE;

    return app.exec();
}
