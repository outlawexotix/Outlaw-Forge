#pragma once

#include <QObject>
#include <QUrl>
#include <QVariantList>
#include <QVariantMap>

class NativeProjectStore : public QObject
{
    Q_OBJECT

public:
    explicit NativeProjectStore(QObject *parent = nullptr) : QObject(parent) {}

    Q_INVOKABLE QVariantMap saveProject(const QUrl &folderUrl, const QVariantMap &scene,
                                        const QVariantList &geometryRecords) const;
    Q_INVOKABLE QVariantMap loadProject(const QUrl &folderUrl) const;
};
