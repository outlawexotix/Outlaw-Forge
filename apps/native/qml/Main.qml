import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick3D
import QtQuick.Dialogs
import OutlawForge.NativeTypes 1.0

ApplicationWindow {
    id: window
    width: 1440
    height: 900
    minimumWidth: 1100
    minimumHeight: 720
    visible: true
    title: "Outlaw Forge - Native Viewport"
    color: "#0e1112"
    property bool modelSelected: false
    property bool modelVisible: true
    property bool scenePanelVisible: true
    property bool gridVisible: true
    property vector3d modelOffset: Qt.vector3d(0, 0, 0)
    property vector3d modelRotation: Qt.vector3d(0, 0, 0)
    property vector3d modelScale: Qt.vector3d(1, 1, 1)
    property int selectedInstanceIndex: -1
    property var derivedGeometries: ({})
    property string projectDirectory: ""
    property bool projectDirty: false
    property int nextGeometryId: 1
    property int nextSceneInstanceId: 1
    property string pendingImportUrl: ""
    property bool restoringInstanceState: false
    property bool restoringProjectGeometry: false
    property string pendingProjectParent: ""
    property string pendingProjectAction: ""
    property url pendingProjectImportUrl
    property bool wireframeMode: false
    property bool boundsVisible: false
    property bool normalsVisible: false
    property bool measurementMode: false
    property var measurementStart: null
    property var measurementEnd: null
    property int viewportTransformMode: 0 // 0 move, 1 rotate, 2 scale
    property string viewportTransformAxis: "All"
    property string cameraDragMode: ""
    property bool uniformScaleEnabled: true
    property var meshAnalysis: ({})
    property bool slicePlaneActive: false
    property bool slicePlaneDragging: false
    property bool slicePlaneRotateMode: false
    property vector3d sliceDragOrigin: Qt.vector3d(0, 0, 0)
    property vector3d sliceDragNormal: Qt.vector3d(0, 0, 1)
    property vector3d sliceDragWorldAnchor: Qt.vector3d(0, 0, 0)
    property vector3d sliceDragWorldPerMm: Qt.vector3d(0, 0, 0)

    function refreshMeshAnalysis() {
        meshAnalysis = selectedGeometry().analyzeMesh()
    }

    function recordMeasurementPoint(point) {
        if (measurementStart === null || measurementEnd !== null) {
            measurementStart = point
            measurementEnd = null
            statusLabel.text = "Measure: first point set. Select a second point on the model."
            return
        }
        measurementEnd = point
        const dx = point.x - measurementStart.x
        const dy = point.y - measurementStart.y
        const dz = point.z - measurementStart.z
        statusLabel.text = `Distance: ${Math.sqrt(dx * dx + dy * dy + dz * dz).toFixed(3)} mm`
    }

    function clearMeasurement() {
        measurementStart = null
        measurementEnd = null
        statusLabel.text = measurementMode ? "Measure: select a first point on the model." : "Measurement cleared"
    }

    function clearScene() {
        while (sceneInstances.count > 0) {
            selectedInstanceIndex = sceneInstances.count - 1
            removeSelectedInstance()
        }
        statusLabel.text = "Scene cleared"
        markProjectDirty()
    }

    function markProjectDirty() {
        if (!restoringProjectGeometry)
            projectDirty = true
    }

    function requestProjectAction(action, importUrl) {
        pendingProjectAction = action
        pendingProjectImportUrl = importUrl || ""
        if (projectDirty) {
            unsavedProjectDialog.open()
            return
        }
        continuePendingProjectAction()
    }

    function continuePendingProjectAction() {
        const action = pendingProjectAction
        const importUrl = pendingProjectImportUrl
        pendingProjectAction = ""
        pendingProjectImportUrl = ""
        if (action === "open")
            projectOpenDialog.open()
        else if (action === "import")
            performMeshImport(importUrl)
        else if (action === "close")
            window.close()
    }

    function selectedGeometry() {
        if (selectedInstanceIndex < 0 || selectedInstanceIndex >= sceneInstances.count)
            return importedGeometry
        return geometryForKey(sceneInstances.get(selectedInstanceIndex).geometryKey)
    }

    function geometryForKey(key) {
        return key === "source" ? importedGeometry : derivedGeometries[key]
    }

    function projectSceneDocument() {
        syncActiveInstance()
        const rows = []
        for (let index = 0; index < sceneInstances.count; ++index) {
            const row = sceneInstances.get(index)
            rows.push({
                instanceId: row.instanceId, name: row.name, sourceUrl: row.sourceUrl,
                piece: row.piece, geometryKey: row.geometryKey, instanceVisible: row.instanceVisible,
                offsetX: row.offsetX, offsetY: row.offsetY, offsetZ: row.offsetZ,
                rotationX: row.rotationX, rotationY: row.rotationY, rotationZ: row.rotationZ,
                scaleX: row.scaleX, scaleY: row.scaleY, scaleZ: row.scaleZ
            })
        }
        const selectedId = selectedInstanceIndex >= 0 && selectedInstanceIndex < sceneInstances.count
            ? sceneInstances.get(selectedInstanceIndex).instanceId : ""
        return { selectedInstanceId: selectedId, instances: rows }
    }

    function projectGeometryRecords() {
        const records = []
        const addedKeys = ({})
        const addGeometry = (key, geometry) => {
            if (!geometry || !geometry.loaded || addedKeys[key])
                return
            addedKeys[key] = true
            const sourceName = String(geometry.fileName || "")
            const extension = sourceName.match(/\.([^.\\/]+)$/)
            records.push({
                geometryKey: key,
                sourceName: sourceName.split(/[\\/]/).pop(),
                sourceFormat: extension ? extension[1].toUpperCase() : "unknown",
                geometry: geometry
            })
        }
        addGeometry("source", importedGeometry)
        for (let index = 0; index < sceneInstances.count; ++index) {
            const key = sceneInstances.get(index).geometryKey
            if (key !== "source")
                addGeometry(key, derivedGeometries[key])
        }
        return records
    }

    function saveNativeProject(folderUrl) {
        syncActiveInstance()
        const result = projectStore.saveProject(folderUrl, projectSceneDocument(), projectGeometryRecords())
        if (!result.ok) {
            statusLabel.text = result.error || "Could not save the native project."
            if (pendingProjectAction)
                unsavedProjectDialog.open()
            return { ok: false, error: statusLabel.text }
        }
        projectDirectory = folderUrl.toString()
        projectDirty = false
        unsavedProjectDialog.close()
        statusLabel.text = `Saved native project to ${folderUrl.toLocalFile()}`
        if (pendingProjectAction)
            continuePendingProjectAction()
        return { ok: true, folder: folderUrl.toLocalFile() }
    }

    function saveCurrentNativeProject() {
        if (!projectDirectory) {
            projectParentDialog.open()
            return
        }
        saveNativeProject(projectDirectory)
    }

    function saveNativeProjectAs() {
        pendingProjectAction = ""
        projectParentDialog.open()
    }

    function openNativeProjectDialog() {
        projectOpenDialog.open()
    }

    function discardStagedProject(stagedProject) {
        if (!stagedProject || !stagedProject.geometriesByKey)
            return
        for (const geometry of Object.values(stagedProject.geometriesByKey)) {
            if (geometry)
                geometry.destroy()
        }
    }

    function stageNativeProject(folderUrl) {
        const loaded = projectStore.loadProject(folderUrl)
        if (!loaded.ok)
            return { ok: false, error: loaded.error || "Could not open the native project." }

        const geometriesByKey = ({})
        const staged = { ok: false, error: "", document: loaded.document, geometriesByKey: geometriesByKey,
                         folderUrl: folderUrl }
        try {
            for (const record of loaded.geometries) {
                const key = String(record.geometryKey || "")
                if (!key || geometriesByKey[key]) {
                    staged.error = `Project has a duplicate or empty geometry key: ${key}`
                    discardStagedProject(staged)
                    return staged
                }
                const geometry = Qt.createQmlObject("import OutlawForge.NativeTypes 1.0\nMeshGeometry {}",
                                                    view3d, `projectStageGeometry${Date.now()}_${Object.keys(geometriesByKey).length}`)
                if (!geometry || !geometry.loadStl(record.assetUrl)) {
                    staged.error = `Could not load project mesh ${record.assetUrl}`
                    if (geometry)
                        geometry.destroy()
                    discardStagedProject(staged)
                    return staged
                }
                if (geometry.revisionId !== record.revisionId || geometry.triangleCount !== record.triangleCount) {
                    staged.error = `Project mesh ${record.assetUrl} does not match its saved revision metadata.`
                    geometry.destroy()
                    discardStagedProject(staged)
                    return staged
                }
                geometriesByKey[key] = geometry
            }

            for (const row of loaded.document.instances) {
                if (!geometriesByKey[row.geometryKey]) {
                    staged.error = `Scene instance ${row.instanceId} references missing geometry ${row.geometryKey}.`
                    discardStagedProject(staged)
                    return staged
                }
            }
            staged.ok = true
            return staged
        } catch (error) {
            staged.error = `Could not stage native project: ${error}`
            discardStagedProject(staged)
            return staged
        }
    }

    function commitNativeProject(stagedProject) {
        if (!stagedProject || !stagedProject.ok)
            return false
        const document = stagedProject.document
        const sourceGeometry = stagedProject.geometriesByKey.source || null
        restoringProjectGeometry = true
        if (sourceGeometry && !importedGeometry.copyMeshFrom(sourceGeometry)) {
            restoringProjectGeometry = false
            statusLabel.text = "Could not install the validated source mesh; the current scene was kept."
            discardStagedProject(stagedProject)
            return false
        }
        if (!sourceGeometry)
            importedGeometry.clearMesh()

        const previousDerived = derivedGeometries
        const replacementDerived = ({})
        for (const key of Object.keys(stagedProject.geometriesByKey)) {
            if (key !== "source")
                replacementDerived[key] = stagedProject.geometriesByKey[key]
        }
        derivedGeometries = replacementDerived
        sceneInstances.clear()
        for (const row of document.instances)
            sceneInstances.append(row)

        let maxGeometryId = 0
        for (const key of Object.keys(replacementDerived)) {
            const match = key.match(/^derived-(\\d+)$/)
            if (match)
                maxGeometryId = Math.max(maxGeometryId, Number(match[1]))
        }
        nextGeometryId = maxGeometryId + 1
        let maxInstanceId = 0
        for (const row of document.instances) {
            const match = String(row.instanceId).match(/native-instance-(\\d+)$/)
            if (match)
                maxInstanceId = Math.max(maxInstanceId, Number(match[1]))
        }
        nextSceneInstanceId = maxInstanceId + 1

        selectedInstanceIndex = -1
        modelSelected = false
        modelVisible = true
        modelOffset = Qt.vector3d(0, 0, 0)
        modelRotation = Qt.vector3d(0, 0, 0)
        modelScale = Qt.vector3d(1, 1, 1)
        const selectedId = String(document.selectedInstanceId || "")
        for (let index = 0; index < sceneInstances.count; ++index) {
            if (sceneInstances.get(index).instanceId === selectedId) {
                setInstanceSelected(index)
                break
            }
        }

        for (const key of Object.keys(previousDerived)) {
            if (previousDerived[key] && previousDerived[key] !== replacementDerived[key])
                previousDerived[key].destroy()
        }
        for (const key of Object.keys(stagedProject.geometriesByKey)) {
            if (key === "source")
                stagedProject.geometriesByKey[key].destroy()
        }
        restoringProjectGeometry = false
        projectDirectory = stagedProject.folderUrl.toString()
        projectDirty = false
        meshAnalysis = selectedInstanceIndex >= 0 ? selectedGeometry().analyzeMesh() : ({})
        statusLabel.text = `Opened native project from ${stagedProject.folderUrl.toLocalFile()}`
        if (selectedInstanceIndex >= 0)
            Qt.callLater(frameImportedModel)
        return true
    }

    function createDerivedGeometry() {
        const geometry = Qt.createQmlObject("import OutlawForge.NativeTypes 1.0\nMeshGeometry {}", view3d,
                                             `derivedGeometry${nextGeometryId}`)
        const key = `derived-${nextGeometryId++}`
        const updated = Object.assign({}, derivedGeometries)
        updated[key] = geometry
        derivedGeometries = updated
        return { key: key, geometry: geometry }
    }

    function destroyDerivedGeometry(key) {
        const geometry = derivedGeometries[key]
        if (!geometry)
            return
        const updated = Object.assign({}, derivedGeometries)
        delete updated[key]
        derivedGeometries = updated
        geometry.destroy()
    }

    function newSceneInstanceId() {
        return `native-instance-${nextSceneInstanceId++}`
    }

    function loadSliceGeometry(geometry, url) {
        const lowerPath = url.toString().toLowerCase()
        if (lowerPath.endsWith(".obj"))
            return geometry.loadObj(url)
        if (lowerPath.endsWith(".stl"))
            return geometry.loadStl(url)
        return false
    }

    function normalizedSourceUrl(value) {
        let key = String(value || "")
        try {
            key = decodeURIComponent(key)
        } catch (error) {
            // Keep the original URL when a file name contains malformed escapes.
        }
        key = key.replace(/\\/g, "/").replace(/^file:\/{1,3}/i, "")
        return Qt.platform.os === "windows" ? key.toLowerCase() : key
    }

    function selectedAutoOrientRow() {
        if (selectedInstanceIndex < 0 || selectedInstanceIndex >= sceneInstances.count)
            return null
        return sceneInstances.get(selectedInstanceIndex)
    }

    function startAutoOrient() {
        const row = selectedAutoOrientRow()
        if (!row)
            return
        const result = selectedGeometry().autoOrient(65.0)
        if (result.error) {
            statusLabel.text = result.error
            return
        }
        refreshMeshAnalysis()
        statusLabel.text = `Local auto-orient complete: evaluated ${result.candidateCount} build orientations, overhang area ${Number(result.overhangAreaCm2).toFixed(2)} cm2, model placed at Z=0 mm.`
    }

    function repairSelectedMesh() {
        if (selectedInstanceIndex < 0 || selectedInstanceIndex >= sceneInstances.count)
            return
        const geometry = selectedGeometry()
        const before = geometry.analyzeMesh()
        const result = geometry.repairMesh(repairTolerance.value / 100.0)
        if (result.error) {
            statusLabel.text = result.error
            return
        }
        refreshMeshAnalysis()
        const after = meshAnalysis
        statusLabel.text = `Local repair: ${result.holesFilled} planar holes filled, ${result.weldedVertices} vertices welded, ${result.removedTriangles} degenerate triangles removed. Watertight: ${before.watertight ? "yes" : "no"} before, ${after.watertight ? "yes" : "no"} after. Boundary edges: ${before.boundaryEdges} to ${after.boundaryEdges}.`
    }

    function splitSelectedComponents() {
        if (selectedInstanceIndex < 0 || selectedInstanceIndex >= sceneInstances.count)
            return
        const sourceIndex = selectedInstanceIndex
        const sourceRow = sceneInstances.get(sourceIndex)
        const sourceGeometry = geometryForKey(sourceRow.geometryKey)
        if (!sourceGeometry || !sourceGeometry.loaded) {
            statusLabel.text = "The selected mesh geometry is unavailable."
            return
        }
        const count = sourceGeometry.connectedComponentCount()
        if (count < 2) {
            statusLabel.text = "The selected mesh has one edge-connected component; no split was needed."
            return
        }

        const outputs = []
        for (let index = 0; index < count; ++index)
            outputs.push(createDerivedGeometry())
        const result = sourceGeometry.splitConnectedComponents(outputs.map(output => output.geometry))
        if (result.error) {
            for (const output of outputs)
                destroyDerivedGeometry(output.key)
            statusLabel.text = result.error
            return
        }

        const componentName = index => `${sourceRow.name} - component ${index + 1}`
        const scale = Qt.vector3d(sourceRow.scaleX, sourceRow.scaleY, sourceRow.scaleZ)
        const rotation = Qt.vector3d(sourceRow.rotationX, sourceRow.rotationY, sourceRow.rotationZ)
        const firstCorrection = sourceGeometry.instanceOffsetCorrection(outputs[0].geometry, scale, rotation)
        sceneInstances.setProperty(sourceIndex, "geometryKey", outputs[0].key)
        sceneInstances.setProperty(sourceIndex, "name", componentName(0))
        sceneInstances.setProperty(sourceIndex, "piece", "derived")
        sceneInstances.setProperty(sourceIndex, "offsetX", sourceRow.offsetX + firstCorrection.x)
        sceneInstances.setProperty(sourceIndex, "offsetY", sourceRow.offsetY + firstCorrection.y)
        sceneInstances.setProperty(sourceIndex, "offsetZ", sourceRow.offsetZ + firstCorrection.z)
        for (let index = 1; index < outputs.length; ++index) {
            const correction = sourceGeometry.instanceOffsetCorrection(outputs[index].geometry, scale, rotation)
            sceneInstances.append({
                instanceId: newSceneInstanceId(), name: componentName(index), piece: "derived",
                geometryKey: outputs[index].key, sourceUrl: sourceRow.sourceUrl,
                offsetX: sourceRow.offsetX + correction.x,
                offsetY: sourceRow.offsetY + correction.y,
                offsetZ: sourceRow.offsetZ + correction.z,
                rotationX: sourceRow.rotationX, rotationY: sourceRow.rotationY, rotationZ: sourceRow.rotationZ,
                scaleX: sourceRow.scaleX, scaleY: sourceRow.scaleY, scaleZ: sourceRow.scaleZ,
                instanceVisible: sourceRow.instanceVisible
            })
        }
        setInstanceSelected(sourceIndex)
        refreshMeshAnalysis()
        statusLabel.text = `Split into ${outputs.length} edge-connected components. Each component is a separate selectable local mesh.`
        markProjectDirty()
    }

    function simplifySelectedMesh() {
        if (selectedInstanceIndex < 0 || selectedInstanceIndex >= sceneInstances.count)
            return
        const sourceIndex = selectedInstanceIndex
        const sourceRow = sceneInstances.get(sourceIndex)
        const sourceGeometry = geometryForKey(sourceRow.geometryKey)
        if (!sourceGeometry || !sourceGeometry.loaded) {
            statusLabel.text = "The selected mesh geometry is unavailable."
            return
        }
        const derived = createDerivedGeometry()
        const result = sourceGeometry.simplifyMesh(simplifyReduction.value, derived.geometry)
        if (result.error) {
            destroyDerivedGeometry(derived.key)
            statusLabel.text = result.error
            return
        }
        sceneInstances.setProperty(sourceIndex, "geometryKey", derived.key)
        sceneInstances.setProperty(sourceIndex, "name", `${sourceRow.name} - simplified`)
        sceneInstances.setProperty(sourceIndex, "piece", "derived")
        setInstanceSelected(sourceIndex)
        refreshMeshAnalysis()
        statusLabel.text = `Local simplification: ${result.sourceTriangles} to ${result.triangles} triangles (${Number(result.actualReductionPercent).toFixed(1)}% reduction; ${Number(result.requestedReductionPercent).toFixed(0)}% requested). Source mesh retained as its earlier revision.`
        markProjectDirty()
    }

    function applyPlaneSlice() {
        const point = Qt.vector3d(slicePointX.value / 100.0, slicePointY.value / 100.0, slicePointZ.value / 100.0)
        const normal = Qt.vector3d(sliceNormalX.value / 10000.0, sliceNormalY.value / 10000.0, sliceNormalZ.value / 10000.0)
        const keepBoth = sliceKeepSide.currentIndex === 2
        if (selectedInstanceIndex < 0 || selectedInstanceIndex >= sceneInstances.count) {
            sliceStatus.text = "Select a mesh instance before cutting."
            return
        }
        const sourceIndex = selectedInstanceIndex
        const sourceRow = sceneInstances.get(sourceIndex)
        const sourceGeometry = geometryForKey(sourceRow.geometryKey)
        if (!sourceGeometry || !sourceGeometry.loaded) {
            sliceStatus.text = "The selected mesh geometry is unavailable."
            return
        }
        const kept = createDerivedGeometry()
        const opposite = keepBoth ? createDerivedGeometry() : null
        const keepPositive = sliceKeepSide.currentIndex !== 0
        const result = sourceGeometry.sliceByPlane(point, normal, keepPositive, kept.geometry,
                                                   opposite ? opposite.geometry : null)
        if (result.error) {
            destroyDerivedGeometry(kept.key)
            if (opposite)
                destroyDerivedGeometry(opposite.key)
            sliceStatus.text = result.error
            statusLabel.text = result.error
            return
        }

        const firstReport = kept.geometry.analyzeMesh()
        const secondReport = opposite ? opposite.geometry.analyzeMesh() : null
        sceneInstances.setProperty(sourceIndex, "geometryKey", kept.key)
        sceneInstances.setProperty(sourceIndex, "name", `${sourceRow.name} - cut section`)
        sceneInstances.setProperty(sourceIndex, "piece", "derived")
        if (opposite) {
            sceneInstances.append({
                instanceId: newSceneInstanceId(), name: `${sourceRow.name} - separated section`, piece: "derived",
                geometryKey: opposite.key, sourceUrl: sourceRow.sourceUrl,
                offsetX: sourceRow.offsetX + sourceGeometry.dimensions.x + 6,
                offsetY: sourceRow.offsetY, offsetZ: sourceRow.offsetZ,
                rotationX: sourceRow.rotationX, rotationY: sourceRow.rotationY, rotationZ: sourceRow.rotationZ,
                scaleX: sourceRow.scaleX, scaleY: sourceRow.scaleY, scaleZ: sourceRow.scaleZ,
                instanceVisible: sourceRow.instanceVisible
            })
        }
        const keptClosure = firstReport.watertight ? "watertight" : `open (${firstReport.boundaryEdges} boundary edges)`
        const otherClosure = secondReport
            ? ` Other section: ${secondReport.watertight ? "watertight" : `open (${secondReport.boundaryEdges} boundary edges)`}.`
            : ""
        const cutSummary = `Local cut complete. Cut faces closed: ${result.capped ? "yes" : "no"}. Kept section: ${keptClosure}.${otherClosure}`
        sliceStatus.text = cutSummary
        statusLabel.text = cutSummary
        if (keepBoth)
            setInstanceSelected(sceneInstances.count - 1)
        else
            setInstanceSelected(sourceIndex)
        refreshMeshAnalysis()
        slicePlaneActive = false
        sliceDialog.close()
        markProjectDirty()
    }

    function applyNumericScale(axis, targetValue) {
        const currentValue = axis === "X" ? modelScale.x : axis === "Y" ? modelScale.y : modelScale.z
        if (uniformScaleEnabled && Math.abs(currentValue) > 0.000001) {
            const ratio = targetValue / currentValue
            modelScale = Qt.vector3d(modelScale.x * ratio, modelScale.y * ratio, modelScale.z * ratio)
        } else if (axis === "X") modelScale = Qt.vector3d(targetValue, modelScale.y, modelScale.z)
        else if (axis === "Y") modelScale = Qt.vector3d(modelScale.x, targetValue, modelScale.z)
        else modelScale = Qt.vector3d(modelScale.x, modelScale.y, targetValue)
    }

    function setTransformMode(mode) {
        viewportTransformMode = mode
        const names = ["Move", "Rotate", "Scale"]
        statusLabel.text = `${names[mode]} ${viewportTransformAxis === "All" ? "on all axes" : `on ${viewportTransformAxis}`}`
    }

    function setTransformAxis(axis) {
        viewportTransformAxis = axis
        const names = ["Move", "Rotate", "Scale"]
        statusLabel.text = `${names[viewportTransformMode]} ${axis === "All" ? "on all axes" : `on ${axis}`}`
    }

    ListModel { id: sceneInstances }
    NativeProjectStore { id: projectStore }

    onClosing: function(close) {
        if (projectDirty) {
            close.accepted = false
            window.requestProjectAction("close")
        }
    }

    onModelOffsetChanged: { syncActiveInstance(); if (!restoringInstanceState) markProjectDirty() }
    onModelRotationChanged: { syncActiveInstance(); if (!restoringInstanceState) markProjectDirty() }
    onModelScaleChanged: { syncActiveInstance(); if (!restoringInstanceState) markProjectDirty() }
    onModelVisibleChanged: { syncActiveInstance(); if (!restoringInstanceState) markProjectDirty() }

    header: ToolBar {
        height: 52
        background: Rectangle { color: "#191714"; border.color: "#49301f"; border.width: 1 }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            Rectangle {
                Layout.preferredWidth: 27
                Layout.preferredHeight: 27
                radius: 6
                color: "#f28c45"
                Text { anchors.centerIn: parent; text: "OF"; color: "#17120e"; font.pixelSize: 10; font.weight: Font.Black; font.letterSpacing: -0.5 }
            }
            Label {
                text: "OUTLAW FORGE"
                color: "#f2e9dd"
                font.pixelSize: 13
                font.weight: Font.Bold
                font.letterSpacing: 1.35
            }
            Label {
                text: "NATIVE VIEWPORT FOUNDATION"
                color: "#92877c"
                font.pixelSize: 10
                Layout.leftMargin: 12
            }
            ToolButton {
                text: "File"
                onClicked: fileMenu.open()
                contentItem: Text { text: parent.text; color: "#e5e2da"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                background: Rectangle { color: parent.down ? "#343a35" : "transparent"; radius: 3 }
                Menu {
                    id: fileMenu
                    title: "File"
                    MenuItem { text: "Open Project...    Ctrl+Shift+O"; onTriggered: window.requestProjectAction("open") }
                    MenuItem { text: "Save Project    Ctrl+S"; enabled: window.projectDirty || !!window.projectDirectory; onTriggered: window.saveCurrentNativeProject() }
                    MenuItem { text: "Save Project As...    Ctrl+Shift+S"; onTriggered: window.saveNativeProjectAs() }
                    MenuSeparator {}
                    MenuItem { text: "Import model...    Ctrl+O"; onTriggered: meshDialog.open() }
                    MenuItem { text: "Export selected mesh as STL..."; enabled: selectedInstanceIndex >= 0; onTriggered: exportDialog.open() }
                    MenuItem { text: "Clear scene"; enabled: sceneInstances.count > 0; onTriggered: window.clearScene() }
                    MenuSeparator {}
                    MenuItem { text: "Close window"; onTriggered: window.close() }
                }
            }
            ToolButton {
                text: "Edit"
                onClicked: editMenu.open()
                contentItem: Text { text: parent.text; color: "#e5e2da"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                background: Rectangle { color: parent.down ? "#343a35" : "transparent"; radius: 3 }
                Menu {
                    id: editMenu
                    title: "Edit"
                    MenuItem { text: "Duplicate instance    Ctrl+D"; enabled: selectedInstanceIndex >= 0; onTriggered: window.duplicateSelectedInstance() }
                    MenuItem { text: "Remove instance    Delete"; enabled: selectedInstanceIndex >= 0; onTriggered: window.removeSelectedInstance() }
                    MenuSeparator {}
                    MenuItem {
                        text: "Reset transforms"
                        enabled: selectedInstanceIndex >= 0
                        onTriggered: {
                            window.modelOffset = Qt.vector3d(0, 0, 0)
                            window.modelRotation = Qt.vector3d(0, 0, 0)
                            window.modelScale = Qt.vector3d(1, 1, 1)
                            window.modelVisible = true
                            window.frameImportedModel()
                        }
                    }
                    MenuItem { text: "Place on build plate"; enabled: selectedInstanceIndex >= 0; onTriggered: window.placeSelectedOnBed() }
                    MenuItem { text: "Center on build plate"; enabled: selectedInstanceIndex >= 0; onTriggered: window.centerSelectedOnPlate() }
                }
            }
            ToolButton {
                text: "View"
                onClicked: viewMenu.open()
                contentItem: Text { text: parent.text; color: "#e5e2da"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                background: Rectangle { color: parent.down ? "#343a35" : "transparent"; radius: 3 }
                Menu {
                    id: viewMenu
                    title: "View"
                    MenuItem { text: "Top"; onTriggered: window.setCameraView("Top") }
                    MenuItem { text: "Front"; onTriggered: window.setCameraView("Front") }
                    MenuItem { text: "Right"; onTriggered: window.setCameraView("Right") }
                    MenuItem { text: "Isometric"; onTriggered: window.setCameraView("Iso") }
                    MenuItem { text: "Frame selected    Ctrl+F"; enabled: selectedInstanceIndex >= 0; onTriggered: window.frameImportedModel() }
                    MenuSeparator {}
                    MenuItem { text: "Wireframe"; checkable: true; checked: window.wireframeMode; onTriggered: window.wireframeMode = checked }
                    MenuItem { text: "Bounds"; checkable: true; checked: window.boundsVisible; enabled: selectedInstanceIndex >= 0; onTriggered: window.boundsVisible = checked }
                    MenuItem { text: "Normals"; checkable: true; checked: window.normalsVisible; enabled: selectedInstanceIndex >= 0; onTriggered: window.normalsVisible = checked }
                    MenuItem { text: "Measurement"; checkable: true; checked: window.measurementMode; onTriggered: { window.measurementMode = checked; if (checked) window.clearMeasurement() } }
                }
            }
            ToolButton {
                text: "Window"
                onClicked: windowMenu.open()
                contentItem: Text { text: parent.text; color: "#e5e2da"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                background: Rectangle { color: parent.down ? "#343a35" : "transparent"; radius: 3 }
                Menu {
                    id: windowMenu
                    title: "Window"
                    MenuItem { text: "Show scene panel"; checkable: true; checked: window.scenePanelVisible; onTriggered: window.scenePanelVisible = checked }
                    MenuItem { text: "Maximize"; enabled: window.visibility !== Window.Maximized; onTriggered: window.showMaximized() }
                    MenuItem { text: "Restore"; enabled: window.visibility === Window.Maximized; onTriggered: window.showNormal() }
                    MenuSeparator {}
                    MenuItem { text: "Close window"; onTriggered: window.close() }
                }
            }
            ToolButton {
                text: "Settings"
                onClicked: settingsMenu.open()
                contentItem: Text { text: parent.text; color: "#e5e2da"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                background: Rectangle { color: parent.down ? "#343a35" : "transparent"; radius: 3 }
                Menu {
                    id: settingsMenu
                    title: "Settings"
                    MenuItem { text: "Show build plate grid"; checkable: true; checked: window.gridVisible; onTriggered: window.gridVisible = checked }
                }
            }
            Shortcut { sequence: "Ctrl+S"; onActivated: window.saveCurrentNativeProject() }
            Shortcut { sequence: "Ctrl+Shift+S"; onActivated: window.saveNativeProjectAs() }
            Shortcut { sequence: "Ctrl+Shift+O"; onActivated: window.requestProjectAction("open") }
            Item { Layout.fillWidth: true }
            Label {
                text: "Z-UP  /  MILLIMETRES"
                color: "#79dec2"
                font.pixelSize: 10
                font.family: "monospace"
            }
            Button {
                text: "Auto Orient"
                enabled: window.selectedAutoOrientRow() !== null
                onClicked: window.startAutoOrient()
                ToolTip.visible: hovered
                ToolTip.text: "Evaluate local build orientations and bake the selected orientation into the in-memory mesh."
                background: Rectangle { color: parent.enabled ? "#79dec2" : "#343d38"; border.color: "#a2f0d9"; radius: 4 }
                contentItem: Text { text: parent.text; color: parent.enabled ? "#101512" : "#8b968c"; font.pixelSize: 10; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
            }
            Button {
                text: "Export STL"
                enabled: importedGeometry.loaded && selectedInstanceIndex >= 0
                onClicked: exportDialog.open()
                ToolTip.visible: hovered
                ToolTip.text: "Save the selected mesh and bake its current transforms into a local binary STL in millimetres."
                background: Rectangle { color: parent.enabled ? "#202723" : "#171c19"; border.color: "#a96c3a"; radius: 4 }
                contentItem: Text { text: parent.text; color: parent.enabled ? "#e5e2da" : "#746f66"; font.pixelSize: 11; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
            }
            Button {
                text: "Import Model"
                onClicked: meshDialog.open()
                background: Rectangle { color: parent.down ? "#d76c32" : "#f28c45"; border.color: "#ffbd79"; radius: 4 }
                contentItem: Text { text: parent.text; color: "#1c130d"; font.pixelSize: 11; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: 230
            visible: window.scenePanelVisible
            Layout.fillHeight: true
            color: "#141817"
            border.color: "#343a35"
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12
                Label { text: "01   /   SCENE"; color: "#b7a28e"; font.pixelSize: 10; font.weight: Font.Bold; font.letterSpacing: 1.0 }
                Repeater {
                    model: sceneInstances
                    delegate: Rectangle {
                        required property int index
                        required property string name
                        Layout.fillWidth: true
                        height: 36
                        radius: 3
                        color: index === window.selectedInstanceIndex ? "#332219" : "#1d2421"
                        border.color: index === window.selectedInstanceIndex ? "#e57b3e" : "#39433c"
                        MouseArea { anchors.fill: parent; onClicked: window.setInstanceSelected(index) }
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            Label { text: "▰"; color: "#f28c45"; font.pixelSize: 13 }
                            Label { text: name; color: "#e5e2da"; font.pixelSize: 11; elide: Text.ElideMiddle; Layout.fillWidth: true }
                        }
                    }
                }
                Label { visible: sceneInstances.count === 0; text: "No model loaded"; color: "#a8947f"; font.pixelSize: 11 }
                Label {
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    text: importedGeometry.loaded
                        ? `Bounds: ${window.selectedWorldDimensions().x.toFixed(2)} x ${window.selectedWorldDimensions().y.toFixed(2)} x ${window.selectedWorldDimensions().z.toFixed(2)} mm (world aligned)`
                        : "Import an STL or OBJ to inspect a model in the native viewport. Source files are opened read-only."
                    color: "#a8947f"
                    font.pixelSize: 11
                    wrapMode: Text.WordWrap
                }
                Button {
                    text: "Duplicate instance"
                    enabled: importedGeometry.loaded && selectedInstanceIndex >= 0
                    onClicked: window.duplicateSelectedInstance()
                    ToolTip.visible: hovered
                    ToolTip.text: "Duplicate selected mesh (Ctrl+D)"
                    contentItem: Text { text: parent.text; color: parent.enabled ? "#e5e2da" : "#746f66"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    background: Rectangle { color: "#202723"; border.color: "#424b43"; radius: 3 }
                }
                RowLayout {
                    visible: importedGeometry.loaded && selectedInstanceIndex >= 0
                    Layout.fillWidth: true
                    spacing: 4
                    Button {
                        text: "Place on bed"
                        Layout.fillWidth: true
                        onClicked: window.placeSelectedOnBed()
                        ToolTip.visible: hovered
                        ToolTip.text: "Move the lowest point of this model to Z=0 mm"
                        contentItem: Text { text: parent.text; color: "#e5e2da"; font.pixelSize: 10; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                        background: Rectangle { color: "#202723"; border.color: "#424b43"; radius: 3 }
                    }
                    Button {
                        text: "Center XY"
                        Layout.fillWidth: true
                        onClicked: window.centerSelectedOnPlate()
                        ToolTip.visible: hovered
                        ToolTip.text: "Center this model over the build plate origin"
                        contentItem: Text { text: parent.text; color: "#e5e2da"; font.pixelSize: 10; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                        background: Rectangle { color: "#202723"; border.color: "#424b43"; radius: 3 }
                    }
                }
                Button {
                    text: importedGeometry.loaded ? "Remove instance" : "Choose model"
                    onClicked: importedGeometry.loaded ? window.removeSelectedInstance() : meshDialog.open()
                    ToolTip.visible: hovered && importedGeometry.loaded
                    ToolTip.text: "Remove selected scene instance (Delete)"
                    contentItem: Text { text: parent.text; color: "#e5e2da"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    background: Rectangle { color: "#202723"; border.color: "#424b43"; radius: 3 }
                }
                Button {
                    text: modelVisible ? "Hide instance" : "Show instance"
                    enabled: importedGeometry.loaded && selectedInstanceIndex >= 0
                    onClicked: window.modelVisible = !window.modelVisible
                    ToolTip.visible: hovered
                    ToolTip.text: "Toggle selected instance visibility (Ctrl+H)"
                    contentItem: Text { text: parent.text; color: parent.enabled ? "#e5e2da" : "#746f66"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    background: Rectangle { color: "#202723"; border.color: "#424b43"; radius: 3 }
                }
                Button {
                    text: "Reset transforms"
                    enabled: importedGeometry.loaded
                    onClicked: {
                        window.modelOffset = Qt.vector3d(0, 0, 0)
                        window.modelRotation = Qt.vector3d(0, 0, 0)
                        window.modelScale = Qt.vector3d(1, 1, 1)
                        window.modelVisible = true
                        frameImportedModel()
                    }
                    contentItem: Text { text: parent.text; color: parent.enabled ? "#e5e2da" : "#746f66"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    background: Rectangle { color: "#202723"; border.color: "#424b43"; radius: 3 }
                }
                Rectangle {
                    visible: importedGeometry.loaded
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    implicitHeight: meshRepairColumn.implicitHeight + 16
                    color: "#191f1c"
                    border.color: "#3a4a40"
                    radius: 4
                    ColumnLayout {
                        id: meshRepairColumn
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 8
                        spacing: 5
                        Label { text: "02   /   MESH HEALTH"; color: "#79dec2"; font.pixelSize: 10; font.weight: Font.Bold; font.letterSpacing: 1.0 }
                        Label {
                            Layout.fillWidth: true
                            text: meshAnalysis.triangles === undefined
                                ? `${importedGeometry.triangleCount} triangles - analyze for edge counts`
                                : `${meshAnalysis.triangles} tris  /  ${meshAnalysis.degenerateTriangles} degenerate\n${meshAnalysis.boundaryEdges} boundary edges  /  ${meshAnalysis.nonManifoldEdges} non-manifold`
                            color: "#c8c3b8"
                            font.pixelSize: 9
                            wrapMode: Text.WordWrap
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Button {
                                text: "Analyze"
                                Layout.fillWidth: true
                                onClicked: refreshMeshAnalysis()
                                contentItem: Text { text: parent.text; color: "#e5e2da"; font.pixelSize: 10; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                background: Rectangle { color: "#202723"; border.color: "#424b43"; radius: 3 }
                            }
                            Button {
                                text: "Repair"
                                Layout.fillWidth: true
                                onClicked: repairSelectedMesh()
                                contentItem: Text { text: parent.text; color: "#161c18"; font.pixelSize: 10; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                background: Rectangle { color: "#79dec2"; border.color: "#a2f0d9"; radius: 3 }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Label { text: "Weld tol (mm)"; color: "#aa9c89"; font.pixelSize: 9 }
                            Item { Layout.fillWidth: true }
                            SpinBox {
                                id: repairTolerance
                                from: 1
                                to: 1000
                                value: 1
                                editable: true
                                textFromValue: function(value) { return (value / 100.0).toFixed(2) }
                                valueFromText: function(text) { return Math.max(1, Math.min(1000, Math.round(Number(text) * 100))) }
                            }
                        }
                        Button {
                            text: "Split components"
                            Layout.fillWidth: true
                            enabled: selectedInstanceIndex >= 0
                            onClicked: splitSelectedComponents()
                            ToolTip.visible: hovered
                            ToolTip.text: "Create one selectable scene item for each edge-connected mesh component."
                            contentItem: Text { text: parent.text; color: parent.enabled ? "#e5e2da" : "#746f66"; font.pixelSize: 10; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                            background: Rectangle { color: parent.down ? "#424b43" : "#202723"; border.color: "#424b43"; radius: 3 }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Label { text: "Reduce (%)"; color: "#aa9c89"; font.pixelSize: 9 }
                            Item { Layout.fillWidth: true }
                            SpinBox {
                                id: simplifyReduction
                                from: 1
                                to: 95
                                value: 50
                                editable: true
                                textFromValue: function(value) { return `${value}%` }
                                valueFromText: function(text) { return Math.max(1, Math.min(95, parseInt(text, 10) || 1)) }
                            }
                        }
                        Button {
                            text: "Simplify mesh"
                            Layout.fillWidth: true
                            enabled: selectedInstanceIndex >= 0
                            onClicked: simplifySelectedMesh()
                            ToolTip.visible: hovered
                            ToolTip.text: "Create a derived mesh using deterministic local vertex clustering."
                            contentItem: Text { text: parent.text; color: parent.enabled ? "#e5e2da" : "#746f66"; font.pixelSize: 10; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                            background: Rectangle { color: parent.down ? "#424b43" : "#202723"; border.color: "#424b43"; radius: 3 }
                        }
                    }
                }
                Item { Layout.fillHeight: true }
                Label { text: "RENDER CORE"; color: "#b7a28e"; font.pixelSize: 10; font.weight: Font.Bold; font.letterSpacing: 1.0 }
                Label { text: "Qt Quick 3D / C++"; color: "#e5e2da"; font.pixelSize: 11 }
                Label { text: "Rendering Hardware Interface"; color: "#92877c"; font.pixelSize: 10; wrapMode: Text.WordWrap }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            View3D {
                id: view3d
                anchors.fill: parent
                camera: camera
                environment: SceneEnvironment {
                    clearColor: "#151a18"
                    backgroundMode: SceneEnvironment.Color
                    antialiasingMode: SceneEnvironment.MSAA
                    antialiasingQuality: SceneEnvironment.High
                    debugSettings: DebugSettings {
                        wireframeEnabled: window.wireframeMode
                    }
                }

                Node {
                    id: slicerSpace

                    Node {
                        id: cameraRig
                        // Default isometric angle looks toward the common Z-up
                        // CAD front (-Y) side of the build plate.
                        eulerRotation: Qt.vector3d(48, 0, 0)
                        position: Qt.vector3d(0, 0, 0)

                        PerspectiveCamera {
                            id: camera
                            position: Qt.vector3d(0, 0, 520)
                            clipNear: 0.1
                            clipFar: 100000
                            fieldOfView: 42
                        }
                    }

                    DirectionalLight {
                        eulerRotation: Qt.vector3d(-35, -25, -25)
                        brightness: 1.3
                    }
                    DirectionalLight {
                        eulerRotation: Qt.vector3d(35, 145, 0)
                        brightness: 0.45
                    }

                    // Canonical project space stays right-handed and Z-up.
                    // Build plate dimensions and model transforms are in mm.
                    Model {
                        source: "#Cube"
                        position: Qt.vector3d(0, 0, -0.6)
                        scale: Qt.vector3d(2.2, 2.2, 0.012)
                        materials: PrincipledMaterial {
                            baseColor: "#242d28"
                            roughness: 0.88
                            metalness: 0.08
                        }
                    }

                    Repeater3D {
                        model: 23
                        delegate: Model {
                            required property int index
                            visible: window.gridVisible
                            source: "#Cube"
                            position: Qt.vector3d((index - 11) * 10, 0, 0.05)
                            scale: Qt.vector3d(0.003, 2.2, 0.001)
                            materials: PrincipledMaterial { baseColor: "#49544a"; roughness: 1.0 }
                        }
                    }
                    Repeater3D {
                        model: 23
                        delegate: Model {
                            required property int index
                            visible: window.gridVisible
                            source: "#Cube"
                            position: Qt.vector3d(0, (index - 11) * 10, 0.05)
                            scale: Qt.vector3d(2.2, 0.003, 0.001)
                            materials: PrincipledMaterial { baseColor: "#49544a"; roughness: 1.0 }
                        }
                    }

                    Repeater3D {
                        id: instanceRepeater
                        model: sceneInstances
                        delegate: Model {
                            required property int index
                            required property real offsetX
                            required property real offsetY
                            required property real offsetZ
                            required property real rotationX
                            required property real rotationY
                            required property real rotationZ
                            required property real scaleX
                            required property real scaleY
                            required property real scaleZ
                            required property bool instanceVisible
                            required property string piece
                            required property string geometryKey
                            property int instanceIndex: index
                            property var meshGeometry: window.geometryForKey(geometryKey)
                            geometry: meshGeometry
                            position: Qt.vector3d(meshGeometry.center.x + offsetX,
                                                  meshGeometry.center.y + offsetY,
                                                  meshGeometry.center.z - meshGeometry.dimensions.z * 0.5 + offsetZ)
                            eulerRotation: Qt.vector3d(rotationX, rotationY, rotationZ)
                            scale: Qt.vector3d(scaleX, scaleY, scaleZ)
                            visible: meshGeometry.loaded && instanceVisible
                            pickable: true
                            materials: PrincipledMaterial {
                            baseColor: index === window.selectedInstanceIndex ? "#f1a35d" : "#bd7840"
                                roughness: 0.42
                                metalness: 0.22
                                cullMode: Material.NoCulling
                            }

                            Node {
                                position: Qt.vector3d(0, 0, meshGeometry.dimensions.z * 0.5)
                                scale: Qt.vector3d(meshGeometry.dimensions.x * 0.0102,
                                                   meshGeometry.dimensions.y * 0.0102,
                                                   meshGeometry.dimensions.z * 0.0102)
                                visible: window.boundsVisible && index === window.selectedInstanceIndex && instanceVisible
                                Repeater3D {
                                    model: 12
                                    delegate: Model {
                                        required property int index
                                        source: "#Cube"
                                        position: index < 4
                                            ? Qt.vector3d(0, (index % 2 === 0 ? -49 : 49), (index < 2 ? -49 : 49))
                                            : index < 8
                                                ? Qt.vector3d((index % 2 === 0 ? -49 : 49), 0, (index < 6 ? -49 : 49))
                                                : Qt.vector3d((index % 2 === 0 ? -49 : 49), (index < 10 ? -49 : 49), 0)
                                        scale: index < 4 ? Qt.vector3d(1, 0.012, 0.012)
                                            : index < 8 ? Qt.vector3d(0.012, 1, 0.012)
                                            : Qt.vector3d(0.012, 0.012, 1)
                                        materials: PrincipledMaterial {
                                            baseColor: "#61c9ac"
                                            roughness: 0.35
                                            metalness: 0.0
                                        }
                                    }
                                }
                            }

                            Node {
                                visible: window.normalsVisible && index === window.selectedInstanceIndex && instanceVisible
                                Repeater3D {
                                    model: meshGeometry.sampledFaceNormals
                                    delegate: Model {
                                        required property var modelData
                                        source: "#Cube"
                                        position: modelData.position
                                        rotation: modelData.rotation
                                        scale: Qt.vector3d(0.0007, 0.0007, modelData.length / 100)
                                        materials: PrincipledMaterial {
                                            baseColor: "#8ae2cf"
                                            roughness: 0.3
                                            metalness: 0.0
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Model {
                        id: slicePlaneVisual
                        source: "#Rectangle"
                        visible: window.slicePlaneActive && importedGeometry.loaded
                        position: window.slicePlaneScenePosition()
                        rotation: window.slicePlaneSceneRotation()
                        scale: Qt.vector3d(window.slicePlaneSize() / 100,
                                           window.slicePlaneSize() / 100, 0.001)
                        pickable: false
                        materials: PrincipledMaterial {
                            baseColor: "#ff8b45"
                            opacity: 0.3
                            roughness: 0.35
                            metalness: 0.05
                            cullMode: Material.NoCulling
                        }
                    }

                    Model {
                        visible: window.measurementStart !== null
                        source: "#Sphere"
                        position: window.measurementStart || Qt.vector3d(0, 0, 0)
                        scale: Qt.vector3d(0.025, 0.025, 0.025)
                        materials: PrincipledMaterial { baseColor: "#79dec2"; lighting: PrincipledMaterial.NoLighting }
                    }
                    Model {
                        visible: window.measurementEnd !== null
                        source: "#Sphere"
                        position: window.measurementEnd || Qt.vector3d(0, 0, 0)
                        scale: Qt.vector3d(0.025, 0.025, 0.025)
                        materials: PrincipledMaterial { baseColor: "#e57b3e"; lighting: PrincipledMaterial.NoLighting }
                    }

                    MeshGeometry {
                        id: importedGeometry
                        onLoadFailed: function(message) { statusLabel.text = message }
                        onLoadedChanged: {
                            if (loaded && !window.restoringProjectGeometry) {
                                statusLabel.text = `Loaded ${fileName}`
                                sceneInstances.clear()
                                for (const key of Object.keys(window.derivedGeometries))
                                    window.destroyDerivedGeometry(key)
                                sceneInstances.append({
                                    instanceId: window.newSceneInstanceId(), name: fileName, piece: "main", geometryKey: "source",
                                    sourceUrl: window.pendingImportUrl,
                                    offsetX: 0, offsetY: 0, offsetZ: 0,
                                    rotationX: 0, rotationY: 0, rotationZ: 0,
                                    scaleX: 1, scaleY: 1, scaleZ: 1,
                                    instanceVisible: true
                                })
                                window.setInstanceSelected(0)
                                window.markProjectDirty()
                                Qt.callLater(frameImportedModel)
                            }
                        }
                    }

                }
            }

            MouseArea {
                id: viewportInput
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
                hoverEnabled: true
                // Keep Quick 3D and child controls from taking ownership of a
                // slice-plane drag after the pointer has started moving.
                preventStealing: true
                cursorShape: window.slicePlaneActive
                    ? (window.slicePlaneRotateMode ? Qt.SizeAllCursor : Qt.SizeVerCursor)
                    : Qt.ArrowCursor
                property point lastPosition
                property point pressPosition
                property int pressedInstanceIndex: -1
                property vector3d pressOffset: Qt.vector3d(0, 0, 0)
                property vector3d pressRotation: Qt.vector3d(0, 0, 0)
                property vector3d pressScale: Qt.vector3d(1, 1, 1)
                property var pressPlatePosition: null
                property bool movedPointer: false
                property bool draggingSlicePlane: false
                property bool rotatingSlicePlane: false
                property bool cameraGestureActive: false
                property bool rightOrbitActive: false
                property string activeCameraGesture: ""
                property point sliceRotationLastPointer
                property vector3d slicePointerAnchor: Qt.vector3d(0, 0, 0)

                onPressed: function(mouse) {
                    forceActiveFocus()
                    lastPosition = Qt.point(mouse.x, mouse.y)
                    pressPosition = Qt.point(mouse.x, mouse.y)
                    movedPointer = false
                    pressedInstanceIndex = -1
                    pressPlatePosition = null
                    if (mouse.button === Qt.LeftButton && window.slicePlaneActive) {
                        if (window.slicePlaneRotateMode) {
                            rotatingSlicePlane = true
                            sliceRotationLastPointer = Qt.point(mouse.x, mouse.y)
                            mouse.accepted = true
                            return
                        }
                        draggingSlicePlane = window.beginSlicePlaneDrag(mouse.x, mouse.y)
                        if (draggingSlicePlane) {
                            mouse.accepted = true
                            return
                        }
                    }
                    if (mouse.button === Qt.LeftButton && window.cameraDragMode !== "") {
                        const cameraHit = view3d.pick(mouse.x, mouse.y)
                        const startsOnModel = cameraHit && cameraHit.objectHit
                            && cameraHit.objectHit.instanceIndex !== undefined
                        if (!startsOnModel || (mouse.modifiers & Qt.ShiftModifier)) {
                            activeCameraGesture = window.cameraDragMode
                            cameraGestureActive = true
                            mouse.accepted = true
                            statusLabel.text = startsOnModel
                                ? `Camera ${activeCameraGesture}: Shift-drag over a model. Middle drag also pans.`
                                : `Camera ${activeCameraGesture}: drag empty viewport space. Drag a model to manipulate it.`
                            return
                        }
                        window.cameraDragMode = ""
                        statusLabel.text = "Camera drag mode cleared. Drag the model to manipulate it."
                    }
                    if (mouse.button === Qt.LeftButton && window.measurementMode) {
                        mouse.accepted = true
                        return
                    }
                    if (mouse.button === Qt.RightButton) {
                        // Defer the context menu until release so right-drag
                        // remains available as the familiar camera-orbit gesture.
                        rightOrbitActive = false
                        mouse.accepted = true
                        return
                    }
                    if (mouse.button === Qt.LeftButton) {
                        const hit = view3d.pick(mouse.x, mouse.y)
                        if (hit && hit.objectHit && hit.objectHit.instanceIndex !== undefined) {
                            pressedInstanceIndex = hit.objectHit.instanceIndex
                            window.setInstanceSelected(pressedInstanceIndex)
                            pressOffset = window.modelOffset
                            pressRotation = window.modelRotation
                            pressScale = window.modelScale
                            const mode = (mouse.modifiers & Qt.ControlModifier) ? 2
                                : (mouse.modifiers & Qt.AltModifier) ? 1 : window.viewportTransformMode
                            if (mode === 0 && window.viewportTransformAxis !== "Z")
                                pressPlatePosition = window.screenToBuildPlate(mouse.x, mouse.y)
                            dragTransformMode = mode
                        }
                    }
                }

                property int dragTransformMode: 0

                onReleased: function(mouse) {
                    if (mouse.button === Qt.RightButton) {
                        if (rightOrbitActive) {
                            rightOrbitActive = false
                            return
                        }
                        const hit = view3d.pick(mouse.x, mouse.y)
                        viewportContextMenu.instanceIndex = hit && hit.objectHit
                            && hit.objectHit.instanceIndex !== undefined
                            ? hit.objectHit.instanceIndex : -1
                        if (viewportContextMenu.instanceIndex >= 0)
                            window.setInstanceSelected(viewportContextMenu.instanceIndex)
                        viewportContextMenu.popup(view3d, mouse.x, mouse.y)
                        return
                    }
                    if (mouse.button === Qt.LeftButton && cameraGestureActive) {
                        cameraGestureActive = false
                        activeCameraGesture = ""
                        return
                    }
                    if (mouse.button === Qt.LeftButton && rotatingSlicePlane) {
                        rotatingSlicePlane = false
                        statusLabel.text = "Slice plane rotated with mouse. Drag to position it or switch back to Move plane."
                        return
                    }
                    if (mouse.button === Qt.LeftButton && draggingSlicePlane) {
                        draggingSlicePlane = false
                        window.slicePlaneDragging = false
                        statusLabel.text = "Slice plane positioned. Adjust its origin or normal in the slice panel."
                        return
                    }
                    if (mouse.button !== Qt.LeftButton || movedPointer)
                        return
                    const hit = view3d.pick(mouse.x, mouse.y)
                    if (window.measurementMode) {
                        if (hit && hit.objectHit && hit.objectHit.instanceIndex !== undefined)
                            window.recordMeasurementPoint(hit.scenePosition)
                        else
                            statusLabel.text = "Measure: click a point on the model surface."
                        return
                    }
                    if (hit && hit.objectHit && hit.objectHit.instanceIndex !== undefined) {
                        window.setInstanceSelected(hit.objectHit.instanceIndex)
                        statusLabel.text = "Model selected - drag to move on the build plate"
                    } else {
                        window.modelSelected = false
                    }
                }

                onPositionChanged: function(mouse) {
                    if (mouse.buttons & Qt.RightButton) {
                        if (!rightOrbitActive
                                && Math.abs(mouse.x - pressPosition.x)
                                   + Math.abs(mouse.y - pressPosition.y) > 5) {
                            rightOrbitActive = true
                        }
                        if (rightOrbitActive) {
                            const dx = mouse.x - lastPosition.x
                            const dy = mouse.y - lastPosition.y
                            window.orbitCamera(dx, dy)
                            statusLabel.text = "Camera Orbit: right-drag to rotate, middle-drag to pan."
                        }
                        lastPosition = Qt.point(mouse.x, mouse.y)
                        return
                    }
                    if (draggingSlicePlane) {
                        const pointer = window.screenToCameraPlane(mouse.x, mouse.y, slicePointerAnchor)
                        if (pointer !== null) {
                            const delta = pointer.minus(slicePointerAnchor)
                            const direction = window.sliceDragWorldPerMm
                            const lengthSquared = direction.x * direction.x + direction.y * direction.y + direction.z * direction.z
                            if (lengthSquared > 1e-12) {
                                const distance = (delta.x * direction.x + delta.y * direction.y + delta.z * direction.z) / lengthSquared
                                const next = Qt.vector3d(window.sliceDragOrigin.x + window.sliceDragNormal.x * distance,
                                                         window.sliceDragOrigin.y + window.sliceDragNormal.y * distance,
                                                         window.sliceDragOrigin.z + window.sliceDragNormal.z * distance)
                                slicePointX.value = Math.round(next.x * 100)
                                slicePointY.value = Math.round(next.y * 100)
                                slicePointZ.value = Math.round(next.z * 100)
                            }
                        }
                        movedPointer = true
                        return
                    }
                    if (rotatingSlicePlane) {
                        const dx = mouse.x - sliceRotationLastPointer.x
                        const dy = mouse.y - sliceRotationLastPointer.y
                        sliceRotationLastPointer = Qt.point(mouse.x, mouse.y)
                        const n = window.slicePlaneNormal()
                        // Rotate in mesh-local space. The plane normal is stored
                        // in that same coordinate system, so applying camera
                        // world axes directly here made the displayed plane and
                        // the editable normal disagree after camera/model moves.
                        let right = Qt.vector3d(1, 0, 0)
                        let rightDot = n.x
                        right = Qt.vector3d(right.x - n.x * rightDot,
                                            right.y - n.y * rightDot,
                                            right.z - n.z * rightDot)
                        let rightLength = Math.sqrt(right.x * right.x + right.y * right.y + right.z * right.z)
                        if (rightLength < 1e-5) {
                            right = Qt.vector3d(0, 1, 0)
                            rightDot = n.y
                            right = Qt.vector3d(right.x - n.x * rightDot,
                                                right.y - n.y * rightDot,
                                                right.z - n.z * rightDot)
                            rightLength = Math.sqrt(right.x * right.x + right.y * right.y + right.z * right.z)
                        }
                        right = Qt.vector3d(right.x / rightLength, right.y / rightLength, right.z / rightLength)
                        const up = Qt.vector3d(n.y * right.z - n.z * right.y,
                                               n.z * right.x - n.x * right.z,
                                               n.x * right.y - n.y * right.x)
                        const rotateAround = function(v, axis, angle) {
                            const c = Math.cos(angle), s = Math.sin(angle)
                            const dot = v.x * axis.x + v.y * axis.y + v.z * axis.z
                            const cross = Qt.vector3d(axis.y * v.z - axis.z * v.y,
                                                      axis.z * v.x - axis.x * v.z,
                                                      axis.x * v.y - axis.y * v.x)
                            return Qt.vector3d(v.x * c + cross.x * s + axis.x * dot * (1 - c),
                                               v.y * c + cross.y * s + axis.y * dot * (1 - c),
                                               v.z * c + cross.z * s + axis.z * dot * (1 - c))
                        }
                        const yawed = rotateAround(n, up, -dx * 0.012)
                        const rotated = rotateAround(yawed, right, dy * 0.012)
                        window.setSlicePlaneNormal(rotated.x, rotated.y, rotated.z)
                        sliceStatus.text = `Plane normal: ${rotated.x.toFixed(3)}, ${rotated.y.toFixed(3)}, ${rotated.z.toFixed(3)}`
                        movedPointer = true
                        return
                    }
                    if (cameraGestureActive) {
                        const cameraDx = mouse.x - lastPosition.x
                        const cameraDy = mouse.y - lastPosition.y
                        lastPosition = Qt.point(mouse.x, mouse.y)
                        if (activeCameraGesture === "Orbit")
                            window.orbitCamera(cameraDx, cameraDy)
                        else
                            window.panCamera(cameraDx, cameraDy)
                        movedPointer = true
                        return
                    }
                    if (!pressed)
                        return
                    if (Math.abs(mouse.x - pressPosition.x) + Math.abs(mouse.y - pressPosition.y) > 5)
                        movedPointer = true
                    const dx = mouse.x - lastPosition.x
                    const dy = mouse.y - lastPosition.y
                    lastPosition = Qt.point(mouse.x, mouse.y)

                    if (mouse.buttons & Qt.LeftButton) {
                        if (pressedInstanceIndex >= 0 && dragTransformMode === 2) {
                            const factor = Math.exp((pressPosition.y - mouse.y) * 0.01)
                            const clampScale = function(value) {
                                const sign = value < 0 ? -1 : 1
                                return sign * Math.max(0.01, Math.min(10000, Math.abs(value) * factor))
                            }
                            const axis = window.viewportTransformAxis
                            const scaleX = uniformScaleEnabled || axis === "All" || axis === "X"
                            const scaleY = uniformScaleEnabled || axis === "All" || axis === "Y"
                            const scaleZ = uniformScaleEnabled || axis === "All" || axis === "Z"
                            window.modelScale = Qt.vector3d(
                                scaleX ? clampScale(pressScale.x) : pressScale.x,
                                scaleY ? clampScale(pressScale.y) : pressScale.y,
                                scaleZ ? clampScale(pressScale.z) : pressScale.z)
                            statusLabel.text = `Scale ${axis}: ${(window.modelScale.x * 100).toFixed(1)}% / ${(window.modelScale.y * 100).toFixed(1)}% / ${(window.modelScale.z * 100).toFixed(1)}%`
                        } else if (pressedInstanceIndex >= 0 && dragTransformMode === 1) {
                            const axis = window.viewportTransformAxis
                            const amount = axis === "X" ? (pressPosition.y - mouse.y) * 0.5
                                : axis === "Y" ? (mouse.x - pressPosition.x) * 0.5
                                : (mouse.x - pressPosition.x) * 0.5
                            window.modelRotation = Qt.vector3d(
                                pressRotation.x + (axis === "X" ? amount : 0),
                                pressRotation.y + (axis === "Y" ? amount : 0),
                                pressRotation.z + (axis === "All" || axis === "Z" ? amount : 0))
                            statusLabel.text = `Rotate ${axis === "All" ? "Z" : axis}: ${amount.toFixed(1)} deg`
                        } else if (pressedInstanceIndex >= 0 && pressPlatePosition !== null) {
                            const platePosition = window.screenToBuildPlate(mouse.x, mouse.y)
                            if (platePosition !== null) {
                                const axis = window.viewportTransformAxis
                                const pixelsToWorld = 2 * camera.position.z
                                    * Math.tan(camera.fieldOfView * Math.PI / 360)
                                    / Math.max(1, view3d.height)
                                const deltaZ = (pressPosition.y - mouse.y) * pixelsToWorld
                                window.modelOffset = Qt.vector3d(
                                    pressOffset.x + (axis === "All" || axis === "X" ? platePosition.x - pressPlatePosition.x : 0),
                                    pressOffset.y + (axis === "All" || axis === "Y" ? platePosition.y - pressPlatePosition.y : 0),
                                    pressOffset.z + (axis === "Z" ? deltaZ : 0))
                                statusLabel.text = `Move: X ${window.modelOffset.x.toFixed(2)} mm  Y ${window.modelOffset.y.toFixed(2)} mm  Z ${window.modelOffset.z.toFixed(2)} mm`
                            }
                        } else if (pressedInstanceIndex >= 0 && dragTransformMode === 0
                                   && window.viewportTransformAxis === "Z") {
                            const pixelsToWorld = 2 * camera.position.z
                                * Math.tan(camera.fieldOfView * Math.PI / 360)
                                / Math.max(1, view3d.height)
                            window.modelOffset = Qt.vector3d(pressOffset.x, pressOffset.y,
                                pressOffset.z + (pressPosition.y - mouse.y) * pixelsToWorld)
                            statusLabel.text = `Move: Z ${window.modelOffset.z.toFixed(2)} mm`
                        } else if (pressedInstanceIndex < 0) {
                            window.orbitCamera(dx, dy)
                        }
                    } else if (mouse.buttons & Qt.MiddleButton) {
                        window.panCamera(dx, dy)
                    }
                }

                onWheel: function(wheel) {
                    camera.position = Qt.vector3d(0, 0,
                        Math.max(1, Math.min(100000, camera.position.z * (wheel.angleDelta.y > 0 ? 0.88 : 1.14))))
                }
            }

            Menu {
                id: viewportContextMenu
                property int instanceIndex: -1
                title: instanceIndex >= 0 ? sceneInstances.get(instanceIndex).name : "Viewport"

                MenuItem {
                    text: "Select"
                    enabled: viewportContextMenu.instanceIndex >= 0
                    onTriggered: window.setInstanceSelected(viewportContextMenu.instanceIndex)
                }
                MenuItem {
                    text: "Frame selected"
                    enabled: viewportContextMenu.instanceIndex >= 0
                    onTriggered: {
                        window.setInstanceSelected(viewportContextMenu.instanceIndex)
                        frameImportedModel()
                    }
                }
                MenuItem {
                    text: "Place on bed"
                    enabled: viewportContextMenu.instanceIndex >= 0
                    onTriggered: {
                        window.setInstanceSelected(viewportContextMenu.instanceIndex)
                        window.placeSelectedOnBed()
                    }
                }
                MenuItem {
                    text: "Center on build plate"
                    enabled: viewportContextMenu.instanceIndex >= 0
                    onTriggered: {
                        window.setInstanceSelected(viewportContextMenu.instanceIndex)
                        window.centerSelectedOnPlate()
                    }
                }
                MenuSeparator {}
                MenuItem {
                    text: "Duplicate"
                    enabled: viewportContextMenu.instanceIndex >= 0
                    onTriggered: {
                        window.setInstanceSelected(viewportContextMenu.instanceIndex)
                        window.duplicateSelectedInstance()
                    }
                }
                MenuItem {
                    text: viewportContextMenu.instanceIndex >= 0
                        && sceneInstances.get(viewportContextMenu.instanceIndex).instanceVisible ? "Hide" : "Show"
                    enabled: viewportContextMenu.instanceIndex >= 0
                    onTriggered: {
                        window.setInstanceSelected(viewportContextMenu.instanceIndex)
                        window.modelVisible = !window.modelVisible
                    }
                }
                MenuItem {
                    text: "Reset transforms"
                    enabled: viewportContextMenu.instanceIndex >= 0
                    onTriggered: {
                        window.setInstanceSelected(viewportContextMenu.instanceIndex)
                        window.modelOffset = Qt.vector3d(0, 0, 0)
                        window.modelRotation = Qt.vector3d(0, 0, 0)
                        window.modelScale = Qt.vector3d(1, 1, 1)
                        frameImportedModel()
                    }
                }
                MenuSeparator {}
                Menu {
                    title: "Mesh editing"
                    enabled: importedGeometry.loaded

                    MenuItem {
                        text: "Analyze mesh health"
                        onTriggered: {
                            refreshMeshAnalysis()
                            statusLabel.text = `Mesh analysis complete: ${meshAnalysis.triangles} triangles, ${meshAnalysis.degenerateTriangles} degenerate, ${meshAnalysis.boundaryEdges} boundary edges, ${meshAnalysis.nonManifoldEdges} non-manifold edges`
                        }
                    }
                    MenuItem {
                        text: "Repair mesh using weld tolerance ${ (repairTolerance.value / 100.0).toFixed(2) } mm"
                        onTriggered: repairSelectedMesh()
                    }
                    MenuItem {
                        text: "Auto-orient selected mesh locally"
                        enabled: window.selectedAutoOrientRow() !== null
                        onTriggered: window.startAutoOrient()
                    }
                    MenuItem {
                        text: "Slice by free plane..."
                        onTriggered: {
                            const geometry = window.selectedGeometry()
                            slicePointX.value = Math.round(geometry.center.x * 100)
                            slicePointY.value = Math.round(geometry.center.y * 100)
                            slicePointZ.value = Math.round(geometry.center.z * 100)
                            window.slicePlaneActive = true
                            sliceDialog.open()
                        }
                    }
                    Menu {
                        title: "Set weld tolerance"
                        MenuItem {
                            text: "0.01 mm"
                            onTriggered: repairTolerance.value = 1
                        }
                        MenuItem {
                            text: "0.05 mm"
                            onTriggered: repairTolerance.value = 5
                        }
                        MenuItem {
                            text: "0.10 mm"
                            onTriggered: repairTolerance.value = 10
                        }
                        MenuItem {
                            text: "0.25 mm"
                            onTriggered: repairTolerance.value = 25
                        }
                    }
                }
                MenuSeparator {}
                MenuItem {
                    text: "Remove from scene"
                    enabled: viewportContextMenu.instanceIndex >= 0
                    onTriggered: {
                        window.setInstanceSelected(viewportContextMenu.instanceIndex)
                        window.removeSelectedInstance()
                    }
                }
                MenuItem {
                    text: "Import model..."
                    onTriggered: meshDialog.open()
                }
            }

            DropArea {
                id: meshDropArea
                anchors.fill: parent

                onEntered: function(drag) {
                    drag.accepted = drag.hasUrls
                }

                onDropped: function(drop) {
                    if (!drop.hasUrls || drop.urls.length === 0)
                        return
                    drop.acceptProposedAction()
                    window.importMesh(drop.urls[0])
                }

                Rectangle {
                    anchors.fill: parent
                    visible: meshDropArea.containsDrag
                    color: "#a0121921"
                    border.color: "#64c4b7"
                    border.width: 2

                    Column {
                        anchors.centerIn: parent
                        spacing: 8
                        Label {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: "DROP MESH TO IMPORT"
                            color: "#d6f1ec"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1
                        }
                        Label {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: "STL, OBJ, or 3MF"
                            color: "#91aaa8"
                            font.pixelSize: 11
                        }
                    }
                }
            }

            Row {
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.margins: 14
                spacing: 6

                Repeater {
                    model: ["Top", "Front", "Right", "Iso"]
                    delegate: ToolButton {
                        required property string modelData
                        text: modelData
                        onClicked: setCameraView(modelData)
                        background: Rectangle {
                            color: parent.down ? "#424b43" : "#202723"
                            border.color: "#424b43"
                            radius: 3
                        }
                        contentItem: Text {
                            text: parent.text
                            color: "#e5e2da"
                            font.pixelSize: 10
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        ToolTip.visible: hovered
                        ToolTip.text: `${modelData} view (Ctrl+${modelData === "Top" ? "1" : modelData === "Front" ? "2" : modelData === "Right" ? "3" : "4"})`
                    }
                }
                ToolButton {
                    text: "Frame"
                    onClicked: frameImportedModel()
                    enabled: importedGeometry.loaded
                    background: Rectangle { color: parent.down ? "#424b43" : "#202723"; border.color: "#424b43"; radius: 3 }
                    contentItem: Text { text: parent.text; color: parent.enabled ? "#e5e2da" : "#746f66"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                }
                ToolButton {
                    text: "Wire"
                    enabled: importedGeometry.loaded
                    checked: window.wireframeMode
                    onClicked: window.wireframeMode = !window.wireframeMode
                    background: Rectangle { color: parent.checked ? "#254d43" : (parent.down ? "#424b43" : "#202723"); border.color: parent.checked ? "#61c9ac" : "#424b43"; radius: 3 }
                    contentItem: Text { text: parent.text; color: parent.enabled ? "#e5e2da" : "#746f66"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    ToolTip.visible: hovered
                    ToolTip.text: "Toggle wireframe rendering"
                }
                ToolButton {
                    text: "Bounds"
                    enabled: importedGeometry.loaded && selectedInstanceIndex >= 0
                    checked: window.boundsVisible
                    onClicked: window.boundsVisible = !window.boundsVisible
                    background: Rectangle { color: parent.checked ? "#254d43" : (parent.down ? "#424b43" : "#202723"); border.color: parent.checked ? "#61c9ac" : "#424b43"; radius: 3 }
                    contentItem: Text { text: parent.text; color: parent.enabled ? "#e5e2da" : "#746f66"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    ToolTip.visible: hovered
                    ToolTip.text: "Show selected model bounds"
                }
                ToolButton {
                    text: "Normals"
                    enabled: importedGeometry.loaded && selectedInstanceIndex >= 0
                    checked: window.normalsVisible
                    onClicked: window.normalsVisible = !window.normalsVisible
                    background: Rectangle { color: parent.checked ? "#254d43" : (parent.down ? "#424b43" : "#202723"); border.color: parent.checked ? "#61c9ac" : "#424b43"; radius: 3 }
                    contentItem: Text { text: parent.text; color: parent.enabled ? "#e5e2da" : "#746f66"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    ToolTip.visible: hovered
                    ToolTip.text: "Show sampled face normal directions"
                }
                ToolButton {
                    text: "Measure"
                    enabled: importedGeometry.loaded
                    checked: window.measurementMode
                    onClicked: {
                        window.measurementMode = !window.measurementMode
                        if (window.measurementMode)
                            statusLabel.text = "Measure: select a first point on the model."
                        else
                            statusLabel.text = "Measure mode off"
                    }
                    background: Rectangle { color: parent.checked ? "#254d43" : (parent.down ? "#424b43" : "#202723"); border.color: parent.checked ? "#61c9ac" : "#424b43"; radius: 3 }
                    contentItem: Text { text: parent.text; color: parent.enabled ? "#e5e2da" : "#746f66"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    ToolTip.visible: hovered
                    ToolTip.text: "Click two points on the selected model to measure distance in millimetres"
                }
                ToolButton {
                    text: "Clear"
                    visible: window.measurementStart !== null
                    onClicked: window.clearMeasurement()
                    background: Rectangle { color: parent.down ? "#424b43" : "#202723"; border.color: "#424b43"; radius: 3 }
                    contentItem: Text { text: parent.text; color: "#e5e2da"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    ToolTip.visible: hovered
                    ToolTip.text: "Clear measured points"
                }
            }

            Rectangle {
                id: transformToolbar
                anchors.top: parent.top
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.topMargin: 12
                z: 20
                width: transformControls.implicitWidth + 20
                height: transformControls.implicitHeight + 16
                color: "#e6121921"
                border.color: "#3b4b5a"
                radius: 5

                ColumnLayout {
                    id: transformControls
                    anchors.centerIn: parent
                    spacing: 6

                    RowLayout {
                        spacing: 5
                        Repeater {
                            model: ["Move", "Rotate", "Scale"]
                            delegate: ToolButton {
                                required property int index
                                required property string modelData
                                text: `${modelData} (${["G", "R", "S"][index]})`
                                checked: window.viewportTransformMode === index
                                enabled: importedGeometry.loaded && window.modelSelected
                                onClicked: window.setTransformMode(index)
                                background: Rectangle {
                                    color: parent.checked ? "#254d43" : (parent.down ? "#424b43" : "#202723")
                                    border.color: parent.checked ? "#61c9ac" : "#424b43"
                                    radius: 3
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: parent.enabled ? (parent.checked ? "#a8f2d6" : "#e5e2da") : "#746f66"
                                    font.pixelSize: 10
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }

                    RowLayout {
                        spacing: 4
                        Label { text: "AXIS"; color: "#a8947f"; font.pixelSize: 9 }
                        Repeater {
                            model: ["All", "X", "Y", "Z"]
                            delegate: ToolButton {
                                required property string modelData
                                text: modelData
                                checked: window.viewportTransformAxis === modelData
                                enabled: importedGeometry.loaded && window.modelSelected
                                onClicked: window.setTransformAxis(modelData)
                                background: Rectangle {
                                    color: parent.checked ? "#254d43" : (parent.down ? "#424b43" : "#202723")
                                    border.color: parent.checked ? "#61c9ac" : "#424b43"
                                    radius: 3
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: parent.enabled ? "#e5e2da" : "#746f66"
                                    font.pixelSize: 9
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                        Label { text: "Ctrl scale | Alt rotate"; color: "#a8947f"; font.pixelSize: 9; Layout.leftMargin: 4 }
                    }

                    RowLayout {
                        spacing: 4
                                Label { text: "CAMERA"; color: "#a8947f"; font.pixelSize: 9 }
                        Repeater {
                            model: ["Orbit", "Pan"]
                            delegate: ToolButton {
                                required property string modelData
                                text: modelData
                                checkable: true
                                checked: window.cameraDragMode === modelData
                                onClicked: window.cameraDragMode = checked ? modelData : ""
                                ToolTip.visible: hovered
                                ToolTip.text: modelData === "Orbit"
                                    ? "Drag empty space horizontally to orbit and vertically to tilt. Drag a model to manipulate it and exit Orbit. Hold Shift to orbit over a model."
                                    : "Drag empty space to pan in screen directions. Drag a model to manipulate it and exit Pan. Hold Shift to pan over a model."
                                background: Rectangle {
                                    color: parent.checked ? "#254d43" : (parent.down ? "#424b43" : "#202723")
                                    border.color: parent.checked ? "#61c9ac" : "#424b43"
                                    radius: 3
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: parent.checked ? "#a8f2d6" : "#e5e2da"
                                    font.pixelSize: 9
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                id: viewportTransformPanel
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.rightMargin: 14
                z: 21
                width: 220
                height: transformEditor.implicitHeight + 24
                visible: importedGeometry.loaded
                color: "#ed171b18"
                border.color: window.modelSelected ? "#8b5634" : "#414840"
                radius: 5

                ColumnLayout {
                    id: transformEditor
                    anchors.fill: parent
                    anchors.margins: 11
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            text: "TRANSFORM"
                            color: "#d7b28e"
                            font.pixelSize: 10
                            font.weight: Font.Bold
                            font.letterSpacing: 1
                        }
                        Item { Layout.fillWidth: true }
                        Label {
                            text: window.modelSelected ? "ACTIVE" : "SELECT MODEL"
                            color: window.modelSelected ? "#79dec2" : "#8d8a80"
                            font.pixelSize: 8
                            font.family: "monospace"
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        Repeater {
                            model: ["Move", "Rotate", "Scale"]
                            delegate: ToolButton {
                                required property int index
                                required property string modelData
                                Layout.fillWidth: true
                                text: modelData
                                checked: window.viewportTransformMode === index
                                enabled: window.modelSelected
                                onClicked: window.setTransformMode(index)
                                background: Rectangle {
                                    color: parent.checked ? "#345c4e" : "#222923"
                                    border.color: parent.checked ? "#79dec2" : "#414840"
                                    radius: 3
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: parent.enabled ? (parent.checked ? "#b8ffe5" : "#d5d0c7") : "#746f66"
                                    font.pixelSize: 9
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            text: window.viewportTransformMode === 0 ? "POSITION  /  MM"
                                : window.viewportTransformMode === 1 ? "ROTATION  /  DEG" : "SCALE  /  %"
                            color: "#92877c"
                            font.pixelSize: 8
                            font.weight: Font.Bold
                            font.letterSpacing: 0.6
                        }
                        Item { Layout.fillWidth: true }
                        CheckBox {
                            visible: window.viewportTransformMode === 2
                            text: "Uniform"
                            checked: window.uniformScaleEnabled
                            enabled: window.modelSelected
                            onToggled: window.uniformScaleEnabled = checked
                            contentItem: Text {
                                text: parent.text
                                color: "#bcb7ad"
                                font.pixelSize: 9
                                leftPadding: 3
                                verticalAlignment: Text.AlignVCenter
                            }
                            indicator: Rectangle {
                                implicitWidth: 13
                                implicitHeight: 13
                                x: 0
                                y: parent.height / 2 - height / 2
                                radius: 2
                                color: parent.checked ? "#257b63" : "#191f1c"
                                border.color: parent.checked ? "#79dec2" : "#596357"
                                Text { anchors.centerIn: parent; text: "✓"; color: "white"; font.pixelSize: 9; visible: parent.parent.checked }
                            }
                        }
                    }

                    Repeater {
                        model: ["X", "Y", "Z"]
                        delegate: RowLayout {
                            required property string modelData
                            Layout.fillWidth: true
                            spacing: 6
                            Label {
                                text: modelData
                                color: modelData === "X" ? "#e98a70" : modelData === "Y" ? "#79dec2" : "#8ca8ef"
                                font.pixelSize: 10
                                font.weight: Font.Bold
                                font.family: "monospace"
                                Layout.preferredWidth: 12
                            }
                            SpinBox {
                                Layout.fillWidth: true
                                enabled: window.modelSelected
                                editable: true
                                from: window.viewportTransformMode === 2 ? -100000000 : -3600000
                                to: 360000000
                                stepSize: window.viewportTransformMode === 0 ? 100 : window.viewportTransformMode === 1 ? 100 : 100
                                value: {
                                    const axisValue = modelData === "X"
                                        ? (window.viewportTransformMode === 0 ? window.modelOffset.x : window.viewportTransformMode === 1 ? window.modelRotation.x : window.modelScale.x)
                                        : modelData === "Y"
                                            ? (window.viewportTransformMode === 0 ? window.modelOffset.y : window.viewportTransformMode === 1 ? window.modelRotation.y : window.modelScale.y)
                                            : (window.viewportTransformMode === 0 ? window.modelOffset.z : window.viewportTransformMode === 1 ? window.modelRotation.z : window.modelScale.z)
                                    return window.viewportTransformMode === 2 ? Math.round(axisValue * 10000) : Math.round(axisValue * 100)
                                }
                                textFromValue: function(value) {
                                    return window.viewportTransformMode === 2
                                        ? (value / 100).toFixed(2) + "%"
                                        : (value / 100).toFixed(2)
                                }
                                valueFromText: function(text) {
                                    const parsed = Number(text.replace("%", ""))
                                    return Math.round(parsed * (window.viewportTransformMode === 2 ? 100 : 100))
                                }
                                onValueModified: {
                                    const numeric = value / 100
                                    if (window.viewportTransformMode === 0) {
                                        if (modelData === "X") window.modelOffset = Qt.vector3d(numeric, window.modelOffset.y, window.modelOffset.z)
                                        else if (modelData === "Y") window.modelOffset = Qt.vector3d(window.modelOffset.x, numeric, window.modelOffset.z)
                                        else window.modelOffset = Qt.vector3d(window.modelOffset.x, window.modelOffset.y, numeric)
                                    } else if (window.viewportTransformMode === 1) {
                                        if (modelData === "X") window.modelRotation = Qt.vector3d(numeric, window.modelRotation.y, window.modelRotation.z)
                                        else if (modelData === "Y") window.modelRotation = Qt.vector3d(window.modelRotation.x, numeric, window.modelRotation.z)
                                        else window.modelRotation = Qt.vector3d(window.modelRotation.x, window.modelRotation.y, numeric)
                                    } else {
                                        const scaleValue = value / 10000
                                        if (Math.abs(scaleValue) < 0.01) return
                                        window.applyNumericScale(modelData, scaleValue)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Shortcut {
                sequence: "G"
                context: Qt.WindowShortcut
                onActivated: if (viewportInput.activeFocus && modelSelected) setTransformMode(0)
            }
            Shortcut {
                sequence: "R"
                context: Qt.WindowShortcut
                onActivated: if (viewportInput.activeFocus && modelSelected) setTransformMode(1)
            }
            Shortcut {
                sequence: "S"
                context: Qt.WindowShortcut
                onActivated: if (viewportInput.activeFocus && modelSelected) setTransformMode(2)
            }
            Shortcut {
                sequence: "X"
                context: Qt.WindowShortcut
                onActivated: if (viewportInput.activeFocus && modelSelected) setTransformAxis("X")
            }
            Shortcut {
                sequence: "Y"
                context: Qt.WindowShortcut
                onActivated: if (viewportInput.activeFocus && modelSelected) setTransformAxis("Y")
            }
            Shortcut {
                sequence: "Z"
                context: Qt.WindowShortcut
                onActivated: if (viewportInput.activeFocus && modelSelected) setTransformAxis("Z")
            }

            Item {
                id: orientationGizmo
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.rightMargin: 16
                anchors.bottomMargin: 16
                width: 178
                height: 158

                Canvas {
                    id: puzzleCubeCanvas
                    x: 8
                    y: 0
                    width: 162
                    height: 128
                    antialiasing: true
                    property real cubeCenterX: width * 0.5
                    property real cubeCenterY: height * 0.5
                    property real cubeRadius: 27

                    function project(x, y, z) {
                        const mapped = cameraRig.mapDirectionFromScene(Qt.vector3d(x, y, z))
                        return Qt.vector3d(cubeCenterX + mapped.x * cubeRadius,
                                           cubeCenterY - mapped.y * cubeRadius, mapped.z)
                    }

                    function containsCubePoint(x, y) {
                        const corners = []
                        for (let sx = -1; sx <= 1; sx += 2)
                            for (let sy = -1; sy <= 1; sy += 2)
                                for (let sz = -1; sz <= 1; sz += 2) {
                                    const point = project(sx, sy, sz)
                                    corners.push({ x: point.x, y: point.y })
                                }
                        corners.sort(function(a, b) { return a.x === b.x ? a.y - b.y : a.x - b.x })
                        function cross(origin, a, b) {
                            return (a.x - origin.x) * (b.y - origin.y) - (a.y - origin.y) * (b.x - origin.x)
                        }
                        const hull = []
                        for (let i = 0; i < corners.length; ++i) {
                            while (hull.length >= 2 && cross(hull[hull.length - 2], hull[hull.length - 1], corners[i]) <= 0)
                                hull.pop()
                            hull.push(corners[i])
                        }
                        const lowerLength = hull.length
                        for (let i = corners.length - 2; i >= 0; --i) {
                            while (hull.length > lowerLength && cross(hull[hull.length - 2], hull[hull.length - 1], corners[i]) <= 0)
                                hull.pop()
                            hull.push(corners[i])
                        }
                        hull.pop()
                        for (let i = 0; i < hull.length; ++i) {
                            if (cross(hull[i], hull[(i + 1) % hull.length], { x: x, y: y }) < -0.01)
                                return false
                        }
                        return true
                    }

                    function drawFace(ctx, axis, side, corners) {
                        const normal = axis === "X" ? Qt.vector3d(side, 0, 0)
                            : axis === "Y" ? Qt.vector3d(0, side, 0) : Qt.vector3d(0, 0, side)
                        const mappedNormal = cameraRig.mapDirectionFromScene(normal)
                        if (mappedNormal.z <= 0.001)
                            return

                        const points = corners.map(function(point) { return project(point[0], point[1], point[2]) })
                        ctx.beginPath()
                        ctx.moveTo(points[0].x, points[0].y)
                        for (let i = 1; i < points.length; ++i)
                            ctx.lineTo(points[i].x, points[i].y)
                        ctx.closePath()
                        const shade = axis === "Z" ? "#37342d" : axis === "Y" ? "#292b28" : "#30302b"
                        ctx.fillStyle = shade
                        ctx.fill()
                        ctx.strokeStyle = "#b77c45"
                        ctx.lineWidth = 2
                        ctx.stroke()

                        const centerX = points.reduce(function(sum, point) { return sum + point.x }, 0) / points.length
                        const centerY = points.reduce(function(sum, point) { return sum + point.y }, 0) / points.length
                        ctx.beginPath()
                        points.forEach(function(point, index) {
                            const insetX = centerX + (point.x - centerX) * 0.72
                            const insetY = centerY + (point.y - centerY) * 0.72
                            if (index === 0) ctx.moveTo(insetX, insetY)
                            else ctx.lineTo(insetX, insetY)
                        })
                        ctx.closePath()
                        ctx.strokeStyle = "#80603f"
                        ctx.lineWidth = 1
                        ctx.stroke()
                        ctx.beginPath()
                        ctx.moveTo(centerX - 7, centerY)
                        ctx.lineTo(centerX, centerY - 5)
                        ctx.lineTo(centerX + 7, centerY)
                        ctx.lineTo(centerX, centerY + 5)
                        ctx.closePath()
                        ctx.strokeStyle = "#a98156"
                        ctx.stroke()
                        ctx.fillStyle = "#e2c49b"
                        ctx.font = "bold 9px sans-serif"
                        ctx.textAlign = "center"
                        ctx.textBaseline = "middle"
                        ctx.fillText(`${side > 0 ? "+" : "-"}${axis}`, centerX, centerY + 13)
                    }

                    onPaint: {
                        const ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        const faces = [
                            { axis: "X", side: 1, corners: [[1,-1,-1],[1,1,-1],[1,1,1],[1,-1,1]] },
                            { axis: "X", side: -1, corners: [[-1,1,-1],[-1,-1,-1],[-1,-1,1],[-1,1,1]] },
                            { axis: "Y", side: 1, corners: [[-1,1,-1],[1,1,-1],[1,1,1],[-1,1,1]] },
                            { axis: "Y", side: -1, corners: [[1,-1,-1],[-1,-1,-1],[-1,-1,1],[1,-1,1]] },
                            { axis: "Z", side: 1, corners: [[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]] },
                            { axis: "Z", side: -1, corners: [[-1,1,-1],[1,1,-1],[1,-1,-1],[-1,-1,-1]] }
                        ]
                        faces.sort(function(a, b) {
                            const an = a.axis === "X" ? Qt.vector3d(a.side,0,0) : a.axis === "Y" ? Qt.vector3d(0,a.side,0) : Qt.vector3d(0,0,a.side)
                            const bn = b.axis === "X" ? Qt.vector3d(b.side,0,0) : b.axis === "Y" ? Qt.vector3d(0,b.side,0) : Qt.vector3d(0,0,b.side)
                            return cameraRig.mapDirectionFromScene(an).z - cameraRig.mapDirectionFromScene(bn).z
                        })
                        faces.forEach(function(face) { drawFace(ctx, face.axis, face.side, face.corners) })
                    }

                    Connections {
                        target: cameraRig
                        function onEulerRotationChanged() { puzzleCubeCanvas.requestPaint() }
                        function onRotationChanged() { puzzleCubeCanvas.requestPaint() }
                    }
                }

                MouseArea {
                    x: 8
                    y: 0
                    width: 162
                    height: 128
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    property point lastCubeDragPosition
                    property point cubePressPosition
                    property bool cubeDragMoved: false

                    onPressed: function(mouse) {
                        if (!puzzleCubeCanvas.containsCubePoint(mouse.x, mouse.y)) {
                            mouse.accepted = false
                            return
                        }
                        lastCubeDragPosition = Qt.point(mouse.x, mouse.y)
                        cubePressPosition = Qt.point(mouse.x, mouse.y)
                        cubeDragMoved = false
                    }

                    onPositionChanged: function(mouse) {
                        if (!pressed)
                            return
                        const dx = mouse.x - lastCubeDragPosition.x
                        const dy = mouse.y - lastCubeDragPosition.y
                        if (!cubeDragMoved
                                && Math.abs(mouse.x - cubePressPosition.x)
                                   + Math.abs(mouse.y - cubePressPosition.y) > 4) {
                            cubeDragMoved = true
                        }
                        lastCubeDragPosition = Qt.point(mouse.x, mouse.y)
                        if (cubeDragMoved) {
                            window.orbitCamera(dx, dy)
                            statusLabel.text = "Camera orbit: dragged the view cube."
                        }
                    }

                    onClicked: function(mouse) {
                        if (cubeDragMoved) {
                            cubeDragMoved = false
                            return
                        }
                        if (!puzzleCubeCanvas.containsCubePoint(mouse.x, mouse.y))
                            return
                        const candidates = []
                        for (let x = -1; x <= 1; ++x)
                            for (let y = -1; y <= 1; ++y)
                                for (let z = -1; z <= 1; ++z) {
                                    if (x === 0 && y === 0 && z === 0) continue
                                    const mapped = cameraRig.mapDirectionFromScene(Qt.vector3d(x, y, z))
                                    if (mapped.z < -0.001) continue
                                    const px = puzzleCubeCanvas.cubeCenterX + mapped.x * puzzleCubeCanvas.cubeRadius
                                    const py = puzzleCubeCanvas.cubeCenterY - mapped.y * puzzleCubeCanvas.cubeRadius
                                    const distance = Math.pow(mouse.x - px, 2) + Math.pow(mouse.y - py, 2)
                                    candidates.push({ x: x, y: y, z: z, distance: distance })
                                }
                        if (candidates.length === 0) return
                        candidates.sort(function(a, b) { return a.distance - b.distance })
                        const direction = candidates[0]
                        window.setCameraCubeDirection(direction.x, direction.y, direction.z)
                    }
                    ToolTip.visible: containsMouse
                    ToolTip.text: "Drag the box to orbit. Click a face, edge, or corner to snap the view"
                }

                Row {
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 4
                    ToolButton {
                        text: "Fit"
                        enabled: importedGeometry.loaded
                        onClicked: frameImportedModel()
                        ToolTip.visible: hovered
                        ToolTip.text: "Fit selected mesh"
                    }
                    ToolButton {
                        text: "+"
                        onClicked: zoomCamera(0.88)
                        ToolTip.visible: hovered
                        ToolTip.text: "Zoom in"
                    }
                    ToolButton {
                        text: "-"
                        onClicked: zoomCamera(1.14)
                        ToolTip.visible: hovered
                        ToolTip.text: "Zoom out"
                    }
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.bottom: parent.bottom
                anchors.margins: 14
                width: Math.min(500, parent.width * 0.55)
                height: Math.max(54, statusLabel.implicitHeight + 34)
                radius: 3
                color: "#141817"
                border.color: "#39433c"
                opacity: 0.94
                Column {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 12
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    spacing: 3
                    Label {
                        id: statusLabel
                        width: parent.width
                        text: "Drag model: current tool | Alt-drag: rotate model | Ctrl-drag: scale | Right-drag: orbit camera anywhere | Orbit: drag empty space | Shift: camera over model | Pan / middle-drag: pan | Wheel: zoom | Right-click: object menu"
                        color: "#e5e2da"
                        font.pixelSize: 10
                        wrapMode: Text.WordWrap
                        maximumLineCount: 3
                    }
                    Label {
                        width: parent.width
                        text: importedGeometry.loaded
                            ? `${window.selectedWorldDimensions().z.toFixed(1)} mm world height`
                            : "STL / OBJ / 3MF import"
                        color: "#aa9c89"
                        font.pixelSize: 9
                        wrapMode: Text.WordWrap
                        maximumLineCount: 1
                    }
                }
            }

            FileDialog {
                id: meshDialog
                title: "Import a mesh"
                nameFilters: ["Mesh files (*.stl *.obj *.3mf)", "STL mesh (*.stl)", "OBJ mesh (*.obj)", "3MF project (*.3mf)", "All files (*)"]
                onAccepted: {
                    window.requestProjectAction("import", selectedFile)
                }
            }

            FolderDialog {
                id: projectParentDialog
                title: "Choose where to create the native project folder"
                onAccepted: projectNameDialog.open()
                onRejected: if (window.pendingProjectAction) unsavedProjectDialog.open()
            }

            Dialog {
                id: projectNameDialog
                parent: Overlay.overlay
                title: "Save Native Project As"
                modal: true
                standardButtons: Dialog.Save | Dialog.Cancel
                contentItem: ColumnLayout {
                    Label { text: "Project folder name" }
                    TextField {
                        id: projectNameField
                        Layout.fillWidth: true
                        text: "Outlaw Forge Project"
                        selectByMouse: true
                    }
                }
                onAccepted: {
                    const name = projectNameField.text.trim()
                    if (!name || name.includes("/") || name.includes("\\") || name.includes(":")
                            || name.includes("*") || name.includes("?") || name.includes("\"")
                            || name.includes("<") || name.includes(">") || name.includes("|")) {
                        statusLabel.text = "Choose a project name without Windows filename characters."
                        return
                    }
                    const selectedParentUrl = projectParentDialog.selectedFolder.toString()
                    const parentUrl = selectedParentUrl.endsWith("/")
                        ? selectedParentUrl.slice(0, -1) : selectedParentUrl
                    const folderUrl = Qt.resolvedUrl(`${parentUrl}/${encodeURIComponent(name)}.oforge`)
                    window.saveNativeProject(folderUrl)
                }
                onRejected: if (window.pendingProjectAction) unsavedProjectDialog.open()
            }

            FolderDialog {
                id: projectOpenDialog
                title: "Open an Outlaw Forge project folder"
                onAccepted: {
                    const staged = window.stageNativeProject(selectedFolder)
                    if (!staged.ok) {
                        statusLabel.text = staged.error
                        return
                    }
                    window.commitNativeProject(staged)
                }
            }

            Dialog {
                id: unsavedProjectDialog
                parent: Overlay.overlay
                title: "Unsaved Project Changes"
                modal: true
                standardButtons: Dialog.NoButton
                contentItem: ColumnLayout {
                    Label {
                        Layout.fillWidth: true
                        text: "Save changes to the current native project before continuing?"
                        wrapMode: Text.WordWrap
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignRight
                        Button {
                            text: "Save"
                            onClicked: {
                                unsavedProjectDialog.close()
                                window.saveCurrentNativeProject()
                            }
                        }
                        Button {
                            text: "Discard"
                            onClicked: {
                                unsavedProjectDialog.close()
                                if (window.pendingProjectAction === "close")
                                    window.projectDirty = false
                                window.continuePendingProjectAction()
                            }
                        }
                        Button {
                            text: "Cancel"
                            onClicked: {
                                unsavedProjectDialog.close()
                                window.pendingProjectAction = ""
                                window.pendingProjectImportUrl = ""
                            }
                        }
                    }
                }
            }

            FileDialog {
                id: exportDialog
                title: "Export selected mesh as STL"
                fileMode: FileDialog.SaveFile
                defaultSuffix: "stl"
                nameFilters: ["Binary STL mesh (*.stl)"]
                onAccepted: {
                    if (window.selectedInstanceIndex < 0 || window.selectedInstanceIndex >= sceneInstances.count)
                        return
                    const row = sceneInstances.get(window.selectedInstanceIndex)
                    const geometry = window.geometryForKey(row.geometryKey)
                    if (!geometry || !geometry.loaded) {
                        statusLabel.text = "The selected mesh geometry is unavailable."
                        return
                    }
                    const result = geometry.exportStl(selectedFile,
                        Qt.vector3d(row.offsetX, row.offsetY, row.offsetZ),
                        Qt.vector3d(row.rotationX, row.rotationY, row.rotationZ),
                        Qt.vector3d(row.scaleX, row.scaleY, row.scaleZ))
                    if (result.error) {
                        statusLabel.text = result.error
                        return
                    }
                    statusLabel.text = `Exported ${result.triangles} triangles to ${result.path} (millimetres). The imported source remains unchanged.`
                }
            }

            Dialog {
                id: sliceDialog
                parent: Overlay.overlay
                title: "Slice mesh by free plane"
                modal: false
                x: 12
                y: 54
                width: Math.min(400, window.width - 24)
                height: Math.min(650, window.height - 72)
                standardButtons: Dialog.NoButton
                background: Rectangle { color: "#171c19"; border.color: "#e57b3e"; radius: 5 }
                contentItem: ColumnLayout {
                    spacing: 9
                    Label {
                        Layout.fillWidth: true
                        text: "Drag in the viewport to position or tilt the cut plane. Values are in millimetres."
                        color: "#d8d0c5"
                        wrapMode: Text.WordWrap
                        font.pixelSize: 11
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Button {
                            text: "MOVE PLANE"
                            Accessible.name: "Move slice plane"
                            checkable: true
                            checked: !window.slicePlaneRotateMode
                            onClicked: window.slicePlaneRotateMode = false
                            Layout.fillWidth: true
                            Layout.preferredHeight: 40
                            contentItem: Text { text: "MOVE PLANE"; color: window.slicePlaneRotateMode ? "#f3eee6" : "#101512"; font.pixelSize: 12; font.weight: Font.Bold; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                            background: Rectangle { color: !window.slicePlaneRotateMode ? "#79dec2" : "#202723"; border.color: "#a2f0d9"; radius: 3 }
                        }
                        Button {
                            text: "ROTATE PLANE"
                            Accessible.name: "Rotate slice plane"
                            checkable: true
                            checked: window.slicePlaneRotateMode
                            onClicked: window.slicePlaneRotateMode = true
                            Layout.fillWidth: true
                            Layout.preferredHeight: 40
                            contentItem: Text { text: "ROTATE PLANE"; color: window.slicePlaneRotateMode ? "#101512" : "#f3eee6"; font.pixelSize: 12; font.weight: Font.Bold; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                            background: Rectangle { color: window.slicePlaneRotateMode ? "#79dec2" : "#202723"; border.color: "#a2f0d9"; radius: 3 }
                        }
                    }
                    Button {
                        text: sliceKeepSide.currentIndex === 2 ? "CUT & SEPARATE" : "CUT MESH"
                        Accessible.name: sliceKeepSide.currentIndex === 2 ? "Cut mesh and separate both sections" : "Cut mesh with current plane"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 48
                        enabled: window.slicePlaneActive
                            && window.selectedInstanceIndex >= 0
                            && window.selectedInstanceIndex < sceneInstances.count
                        onClicked: applyPlaneSlice()
                        contentItem: Text { text: parent.text; color: "#101512"; font.pixelSize: 14; font.weight: Font.Bold; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                        background: Rectangle { color: parent.enabled ? "#f28c45" : "#76563f"; border.color: "#ffbd79"; radius: 3 }
                    }
                    Label {
                        Layout.fillWidth: true
                        text: window.slicePlaneRotateMode ? "ROTATE MODE - drag in the viewport to tilt the plane." : "MOVE MODE - drag in the viewport to slide the plane."
                        color: "#ffad70"
                        wrapMode: Text.WordWrap
                        font.pixelSize: 10
                    }
                    ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    contentWidth: availableWidth
                    ScrollBar.vertical.policy: ScrollBar.AsNeeded
                    ColumnLayout {
                    width: parent.availableWidth
                    spacing: 12
                    Label {
                        Layout.fillWidth: true
                        text: "Keep this panel open beside the viewport. Choose Move or Rotate, then drag in the viewport. Coordinates use mesh millimetres; the imported file stays unchanged."
                        color: "#d8d0c5"
                        wrapMode: Text.WordWrap
                        font.pixelSize: 11
                    }
                    Label { text: "PLANE ORIGIN / MM"; color: "#b7a28e"; font.pixelSize: 10; font.weight: Font.Bold }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        Label { text: "X"; color: "#e57b3e" }
                        SpinBox { id: slicePointX; from: -100000000; to: 100000000; editable: true; Accessible.name: "Plane origin X in millimetres"; font.pixelSize: 12; palette.text: "#f3eee6"; palette.base: "#202723"; textFromValue: function(v) { return (v / 100).toFixed(2) }; valueFromText: function(t) { return Math.round(Number(t) * 100) }; Layout.fillWidth: true; Layout.minimumWidth: 100; background: Rectangle { color: "#202723"; border.color: parent.activeFocus ? "#79dec2" : "#56645b"; radius: 3 } }
                        Label { text: "Y"; color: "#e57b3e" }
                        SpinBox { id: slicePointY; from: -100000000; to: 100000000; editable: true; Accessible.name: "Plane origin Y in millimetres"; font.pixelSize: 12; palette.text: "#f3eee6"; palette.base: "#202723"; textFromValue: function(v) { return (v / 100).toFixed(2) }; valueFromText: function(t) { return Math.round(Number(t) * 100) }; Layout.fillWidth: true; Layout.minimumWidth: 100; background: Rectangle { color: "#202723"; border.color: parent.activeFocus ? "#79dec2" : "#56645b"; radius: 3 } }
                        Label { text: "Z"; color: "#e57b3e" }
                        SpinBox { id: slicePointZ; from: -100000000; to: 100000000; editable: true; Accessible.name: "Plane origin Z in millimetres"; font.pixelSize: 12; palette.text: "#f3eee6"; palette.base: "#202723"; textFromValue: function(v) { return (v / 100).toFixed(2) }; valueFromText: function(t) { return Math.round(Number(t) * 100) }; Layout.fillWidth: true; Layout.minimumWidth: 100; background: Rectangle { color: "#202723"; border.color: parent.activeFocus ? "#79dec2" : "#56645b"; radius: 3 } }
                    }
                    Label { text: "PLANE NORMAL / DIRECTION"; color: "#b7a28e"; font.pixelSize: 10; font.weight: Font.Bold }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        Label { text: "X"; color: "#e57b3e" }
                        SpinBox { id: sliceNormalX; from: -10000; to: 10000; value: 0; editable: true; Accessible.name: "Plane normal X direction"; font.pixelSize: 12; palette.text: "#f3eee6"; palette.base: "#202723"; textFromValue: function(v) { return (v / 10000).toFixed(4) }; valueFromText: function(t) { return Math.round(Number(t) * 10000) }; Layout.fillWidth: true; Layout.minimumWidth: 100; background: Rectangle { color: "#202723"; border.color: parent.activeFocus ? "#79dec2" : "#56645b"; radius: 3 } }
                        Label { text: "Y"; color: "#e57b3e" }
                        SpinBox { id: sliceNormalY; from: -10000; to: 10000; value: 0; editable: true; Accessible.name: "Plane normal Y direction"; font.pixelSize: 12; palette.text: "#f3eee6"; palette.base: "#202723"; textFromValue: function(v) { return (v / 10000).toFixed(4) }; valueFromText: function(t) { return Math.round(Number(t) * 10000) }; Layout.fillWidth: true; Layout.minimumWidth: 100; background: Rectangle { color: "#202723"; border.color: parent.activeFocus ? "#79dec2" : "#56645b"; radius: 3 } }
                        Label { text: "Z"; color: "#e57b3e" }
                        SpinBox { id: sliceNormalZ; from: -10000; to: 10000; value: 10000; editable: true; Accessible.name: "Plane normal Z direction"; font.pixelSize: 12; palette.text: "#f3eee6"; palette.base: "#202723"; textFromValue: function(v) { return (v / 10000).toFixed(4) }; valueFromText: function(t) { return Math.round(Number(t) * 10000) }; Layout.fillWidth: true; Layout.minimumWidth: 100; background: Rectangle { color: "#202723"; border.color: parent.activeFocus ? "#79dec2" : "#56645b"; radius: 3 } }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: "Keep side"; color: "#d8d0c5" }
                        ComboBox { id: sliceKeepSide; model: ["Negative normal side", "Positive normal side", "Keep both, separate side-by-side"]; currentIndex: 1; Layout.fillWidth: true }
                    }
                    Label { id: sliceStatus; Layout.fillWidth: true; color: "#e5a16d"; wrapMode: Text.WordWrap; font.pixelSize: 10 }
                    RowLayout {
                        Layout.fillWidth: true
                        Item { Layout.fillWidth: true }
                        Button { text: "Hide controls"; onClicked: sliceDialog.close() }
                    }
                    }
                    }
                }
            }

            Rectangle {
                id: slicePlaneBadge
                visible: window.slicePlaneActive && !sliceDialog.visible
                z: 20
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.leftMargin: 12
                anchors.topMargin: 12
                width: sliceBadgeRow.implicitWidth + 20
                height: 36
                radius: 4
                color: "#171c19"
                border.color: "#e57b3e"
                Row {
                    id: sliceBadgeRow
                    anchors.centerIn: parent
                    spacing: 8
                    Label { text: "SLICE PLANE ACTIVE"; color: "#ffad70"; font.pixelSize: 9; font.weight: Font.Bold }
                    ToolButton {
                        text: "Controls"
                        onClicked: sliceDialog.open()
                        contentItem: Text { text: parent.text; color: "#e5e2da"; font.pixelSize: 10; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    }
                    ToolButton {
                        text: "Exit"
                        onClicked: window.slicePlaneActive = false
                        contentItem: Text { text: parent.text; color: "#ffad70"; font.pixelSize: 10; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    }
                }
            }
        }
    }

    function frameImportedModel() {
        const geometry = selectedGeometry()
        if (!geometry || !geometry.loaded)
            return
        const activeModel = selectedInstanceIndex >= 0 ? instanceRepeater.objectAt(selectedInstanceIndex) : null
        if (!activeModel)
            return
        // Aim at the transformed bounds center, while keeping the current
        // translation, rotation, and scale intact when the user presses Frame.
        cameraRig.position = activeModel.mapPositionToScene(
            Qt.vector3d(0, 0, geometry.dimensions.z * 0.5))
        // Fit the full bounding sphere inside both viewport axes. This works
        // for small parts and tall/flat parts, independent of window aspect.
        const d = geometry.dimensions
        const scaleFactor = Math.max(Math.abs(activeModel.scale.x), Math.abs(activeModel.scale.y), Math.abs(activeModel.scale.z))
        const radius = Math.max(Math.sqrt(d.x * d.x + d.y * d.y + d.z * d.z) * 0.5 * scaleFactor, 0.5)
        const aspect = Math.max(0.1, view3d.width / Math.max(1, view3d.height))
        const verticalHalfFov = camera.fieldOfView * Math.PI / 360
        const horizontalHalfFov = Math.atan(Math.tan(verticalHalfFov) * aspect)
        const limitingHalfFov = Math.min(verticalHalfFov, horizontalHalfFov)
        const fitDistance = radius / Math.sin(limitingHalfFov) * 1.12
        camera.position = Qt.vector3d(0, 0, Math.max(1, fitDistance))
        window.modelSelected = true
    }

    function screenToBuildPlate(x, y) {
        // Map two points along the pointer's camera ray into slicer space,
        // then intersect that ray with the canonical Z=0 build plate.
        const nearPoint = view3d.mapTo3DScene(Qt.vector3d(x, y, 0))
        const farPoint = view3d.mapTo3DScene(Qt.vector3d(x, y, camera.clipFar * 0.9))
        const rayZ = farPoint.z - nearPoint.z
        if (Math.abs(rayZ) < 1e-7)
            return null

        const fraction = -nearPoint.z / rayZ
        if (fraction < 0 || fraction > 1)
            return null

        return Qt.vector3d(
            nearPoint.x + (farPoint.x - nearPoint.x) * fraction,
            nearPoint.y + (farPoint.y - nearPoint.y) * fraction,
            0)
    }

    function slicePlaneNormal() {
        const n = Qt.vector3d(sliceNormalX.value / 10000.0, sliceNormalY.value / 10000.0, sliceNormalZ.value / 10000.0)
        const length = Math.sqrt(n.x * n.x + n.y * n.y + n.z * n.z)
        return length > 1e-8 ? Qt.vector3d(n.x / length, n.y / length, n.z / length) : Qt.vector3d(0, 0, 0)
    }

    function setSlicePlaneNormal(x, y, z) {
        const length = Math.sqrt(x * x + y * y + z * z)
        if (length < 1e-8)
            return
        sliceNormalX.value = Math.round(x / length * 10000)
        sliceNormalY.value = Math.round(y / length * 10000)
        sliceNormalZ.value = Math.round(z / length * 10000)
    }

    function slicePlaneScenePosition() {
        const activeModel = selectedInstanceIndex >= 0 ? instanceRepeater.objectAt(selectedInstanceIndex) : null
        const geometry = selectedGeometry()
        if (!activeModel || !geometry)
            return Qt.vector3d(0, 0, 0)
        const baseZ = geometry.center.z - geometry.dimensions.z * 0.5
        const local = Qt.vector3d(slicePointX.value / 100.0 - geometry.center.x,
                                  slicePointY.value / 100.0 - geometry.center.y,
                                  slicePointZ.value / 100.0 - baseZ)
        return activeModel.mapPositionToScene(local)
    }

    function slicePlaneSceneRotation() {
        const activeModel = selectedInstanceIndex >= 0 ? instanceRepeater.objectAt(selectedInstanceIndex) : null
        let n = slicePlaneNormal()
        if (!activeModel || (n.x === 0 && n.y === 0 && n.z === 0))
            return Qt.quaternion(1, 0, 0, 0)
        // Convert the source-space normal correctly through non-uniform scale,
        // then orient the rectangle's local +Z axis to it in scene space.
        const localDirection = Qt.vector3d(n.x / Math.max(Math.abs(activeModel.scale.x), 1e-8),
                                           n.y / Math.max(Math.abs(activeModel.scale.y), 1e-8),
                                           n.z / Math.max(Math.abs(activeModel.scale.z), 1e-8))
        const world = activeModel.mapDirectionToScene(localDirection)
        const length = Math.sqrt(world.x * world.x + world.y * world.y + world.z * world.z)
        if (length < 1e-8)
            return Qt.quaternion(1, 0, 0, 0)
        const x = world.x / length, y = world.y / length, z = world.z / length
        const dot = Math.max(-1, Math.min(1, z))
        if (dot < -0.999999)
            return Qt.quaternion(0, 0, 1, 0)
        const s = Math.sqrt(2 * (1 + dot))
        return Qt.quaternion(s * 0.5, -y / s, x / s, 0)
    }

    function slicePlaneSize() {
        const d = selectedGeometry().dimensions
        return Math.max(d.x, d.y, d.z, 1) * 1.6
    }

    function screenToCameraPlane(x, y, anchor) {
        const nearPoint = view3d.mapTo3DScene(Qt.vector3d(x, y, 0))
        const farPoint = view3d.mapTo3DScene(Qt.vector3d(x, y, camera.clipFar * 0.9))
        const n = camera.mapDirectionToScene(Qt.vector3d(0, 0, 1)).normalized()
        const ray = farPoint.minus(nearPoint)
        const denominator = ray.x * n.x + ray.y * n.y + ray.z * n.z
        if (Math.abs(denominator) < 1e-8)
            return null
        const offset = anchor.minus(nearPoint)
        const t = (offset.x * n.x + offset.y * n.y + offset.z * n.z) / denominator
        return nearPoint.plus(ray.times(t))
    }

    function beginSlicePlaneDrag(x, y) {
        const activeModel = selectedInstanceIndex >= 0 ? instanceRepeater.objectAt(selectedInstanceIndex) : null
        const n = slicePlaneNormal()
        if (!activeModel || (n.x === 0 && n.y === 0 && n.z === 0)) {
            sliceStatus.text = "Enter a non-zero plane normal and select a model."
            return false
        }
        const point = slicePlaneScenePosition()
        const pointer = screenToCameraPlane(x, y, point)
        const baseZ = importedGeometry.center.z - importedGeometry.dimensions.z * 0.5
        const localDirection = Qt.vector3d(n.x / Math.max(Math.abs(activeModel.scale.x), 1e-8),
                                           n.y / Math.max(Math.abs(activeModel.scale.y), 1e-8),
                                           n.z / Math.max(Math.abs(activeModel.scale.z), 1e-8))
        sliceDragWorldPerMm = activeModel.mapDirectionToScene(localDirection)
        sliceDragOrigin = Qt.vector3d(slicePointX.value / 100.0, slicePointY.value / 100.0, slicePointZ.value / 100.0)
        sliceDragNormal = n
        sliceDragWorldAnchor = point
        slicePlaneDragging = pointer !== null
        viewportInput.slicePointerAnchor = pointer !== null ? pointer : point
        if (pointer === null) {
            sliceStatus.text = "Cannot start plane drag from this camera angle."
            return false
        }
        sliceStatus.text = "Dragging slice plane along its normal..."
        return true
    }

    function importMesh(url) {
        requestProjectAction("import", url)
    }

    function performMeshImport(url) {
        const path = url.toString().toLowerCase()
        window.pendingImportUrl = url.toString()
        let loaded = false
        if (path.endsWith(".obj")) loaded = importedGeometry.loadObj(url)
        else if (path.endsWith(".3mf")) loaded = importedGeometry.load3mf(url)
        else if (path.endsWith(".stl")) loaded = importedGeometry.loadStl(url)
        else statusLabel.text = "Supported mesh files are STL, OBJ, and 3MF"
        if (!loaded)
            return
        statusLabel.text = `Imported ${importedGeometry.fileName} locally. Geometry commands run on this device; the source file is unchanged.`
    }

    function selectedWorldDimensions() {
        const source = selectedGeometry().dimensions
        const activeModel = selectedInstanceIndex >= 0 ? instanceRepeater.objectAt(selectedInstanceIndex) : null
        if (!activeModel)
            return source

        // Map the eight source-bound corners through the renderer transform
        // so rotation and signed scale produce accurate world-aligned bounds.
        let minX = Number.POSITIVE_INFINITY
        let minY = Number.POSITIVE_INFINITY
        let minZ = Number.POSITIVE_INFINITY
        let maxX = Number.NEGATIVE_INFINITY
        let maxY = Number.NEGATIVE_INFINITY
        let maxZ = Number.NEGATIVE_INFINITY
        for (let corner = 0; corner < 8; ++corner) {
            const local = Qt.vector3d(
                (corner & 1) ? source.x * 0.5 : -source.x * 0.5,
                (corner & 2) ? source.y * 0.5 : -source.y * 0.5,
                (corner & 4) ? source.z : 0)
            const point = activeModel.mapPositionToScene(local)
            minX = Math.min(minX, point.x)
            minY = Math.min(minY, point.y)
            minZ = Math.min(minZ, point.z)
            maxX = Math.max(maxX, point.x)
            maxY = Math.max(maxY, point.y)
            maxZ = Math.max(maxZ, point.z)
        }
        // Quick3D can return the origin for a newly-created repeater delegate
        // until its scene transform has propagated. Keep split-piece bounds
        // useful during that frame instead of displaying 0 x 0 x 0.
        if (!Number.isFinite(minX) || maxX - minX < 0.000001
                || maxY - minY < 0.000001 || maxZ - minZ < 0.000001) {
            return Qt.vector3d(source.x * Math.abs(activeModel.scale.x),
                               source.y * Math.abs(activeModel.scale.y),
                               source.z * Math.abs(activeModel.scale.z))
        }
        return Qt.vector3d(maxX - minX, maxY - minY, maxZ - minZ)
    }

    function selectedWorldBounds() {
        return instanceWorldBounds(selectedInstanceIndex)
    }

    function instanceWorldBounds(index) {
        const row = index >= 0 && index < sceneInstances.count ? sceneInstances.get(index) : null
        const geometry = row ? geometryForKey(row.geometryKey) : null
        if (!geometry)
            return null
        const source = geometry.dimensions
        const activeModel = index >= 0 ? instanceRepeater.objectAt(index) : null
        if (!activeModel || !geometry.loaded)
            return null
        let minX = Number.POSITIVE_INFINITY
        let minY = Number.POSITIVE_INFINITY
        let minZ = Number.POSITIVE_INFINITY
        let maxX = Number.NEGATIVE_INFINITY
        let maxY = Number.NEGATIVE_INFINITY
        let maxZ = Number.NEGATIVE_INFINITY
        for (let corner = 0; corner < 8; ++corner) {
            const local = Qt.vector3d(
                (corner & 1) ? source.x * 0.5 : -source.x * 0.5,
                (corner & 2) ? source.y * 0.5 : -source.y * 0.5,
                (corner & 4) ? source.z : 0)
            const point = activeModel.mapPositionToScene(local)
            minX = Math.min(minX, point.x)
            minY = Math.min(minY, point.y)
            minZ = Math.min(minZ, point.z)
            maxX = Math.max(maxX, point.x)
            maxY = Math.max(maxY, point.y)
            maxZ = Math.max(maxZ, point.z)
        }
        if (!Number.isFinite(minX) || maxX - minX < 0.000001
                || maxY - minY < 0.000001 || maxZ - minZ < 0.000001) {
            const position = activeModel.position
            const halfX = source.x * Math.abs(activeModel.scale.x) * 0.5
            const halfY = source.y * Math.abs(activeModel.scale.y) * 0.5
            const height = source.z * Math.abs(activeModel.scale.z)
            return { minX: position.x - halfX, minY: position.y - halfY, minZ: position.z,
                     maxX: position.x + halfX, maxY: position.y + halfY, maxZ: position.z + height }
        }
        return { minX: minX, minY: minY, minZ: minZ,
                 maxX: maxX, maxY: maxY, maxZ: maxZ }
    }

    function placeSelectedOnBed() {
        const bounds = selectedWorldBounds()
        if (!bounds)
            return
        modelOffset = Qt.vector3d(modelOffset.x, modelOffset.y, modelOffset.z - bounds.minZ)
        statusLabel.text = "Placed model on build plate at Z=0 mm"
    }

    function centerSelectedOnPlate() {
        const bounds = selectedWorldBounds()
        if (!bounds)
            return
        modelOffset = Qt.vector3d(
            modelOffset.x - (bounds.minX + bounds.maxX) * 0.5,
            modelOffset.y - (bounds.minY + bounds.maxY) * 0.5,
            modelOffset.z)
        statusLabel.text = "Centered model over build plate origin"
    }

    function syncActiveInstance() {
        if (restoringInstanceState || selectedInstanceIndex < 0 || selectedInstanceIndex >= sceneInstances.count)
            return
        sceneInstances.setProperty(selectedInstanceIndex, "offsetX", modelOffset.x)
        sceneInstances.setProperty(selectedInstanceIndex, "offsetY", modelOffset.y)
        sceneInstances.setProperty(selectedInstanceIndex, "offsetZ", modelOffset.z)
        sceneInstances.setProperty(selectedInstanceIndex, "rotationX", modelRotation.x)
        sceneInstances.setProperty(selectedInstanceIndex, "rotationY", modelRotation.y)
        sceneInstances.setProperty(selectedInstanceIndex, "rotationZ", modelRotation.z)
        sceneInstances.setProperty(selectedInstanceIndex, "scaleX", modelScale.x)
        sceneInstances.setProperty(selectedInstanceIndex, "scaleY", modelScale.y)
        sceneInstances.setProperty(selectedInstanceIndex, "scaleZ", modelScale.z)
        sceneInstances.setProperty(selectedInstanceIndex, "instanceVisible", modelVisible)
        if (!restoringInstanceState)
            markProjectDirty()
    }

    function setInstanceSelected(index) {
        if (index < 0 || index >= sceneInstances.count)
            return
        restoringInstanceState = true
        selectedInstanceIndex = index
        const item = sceneInstances.get(index)
        modelOffset = Qt.vector3d(item.offsetX, item.offsetY, item.offsetZ)
        modelRotation = Qt.vector3d(item.rotationX, item.rotationY, item.rotationZ)
        modelScale = Qt.vector3d(item.scaleX, item.scaleY, item.scaleZ)
        modelVisible = item.instanceVisible
        modelSelected = true
        restoringInstanceState = false
    }

    function duplicateSelectedInstance() {
        if (!importedGeometry.loaded || selectedInstanceIndex < 0 || selectedInstanceIndex >= sceneInstances.count)
            return
        const source = sceneInstances.get(selectedInstanceIndex)
        const sourceBounds = selectedWorldBounds()
        if (!sourceBounds)
            return

        // Search to the right using transformed bounds so rotated and scaled
        // instances do not spawn on top of existing models.
        const spacing = Math.max(sourceBounds.maxX - sourceBounds.minX, 10) + 10
        let offsetX = spacing
        let slotFound = false
        for (let attempt = 0; attempt < 256 && !slotFound; ++attempt) {
            slotFound = true
            const candidateMinX = sourceBounds.minX + offsetX
            const candidateMaxX = sourceBounds.maxX + offsetX
            for (let i = 0; i < sceneInstances.count; ++i) {
                if (i === selectedInstanceIndex || !sceneInstances.get(i).instanceVisible)
                    continue
                const other = instanceWorldBounds(i)
                if (!other)
                    continue
                const overlapsX = candidateMinX < other.maxX && candidateMaxX > other.minX
                const overlapsY = sourceBounds.minY < other.maxY && sourceBounds.maxY > other.minY
                if (overlapsX && overlapsY) {
                    slotFound = false
                    offsetX += spacing
                    break
                }
            }
        }
        if (!slotFound) {
            statusLabel.text = "Could not find a clear placement for the duplicate"
            return
        }
        sceneInstances.append({
            instanceId: newSceneInstanceId(), name: `${source.name} copy`, piece: source.piece, geometryKey: source.geometryKey,
            sourceUrl: source.sourceUrl,
            offsetX: source.offsetX + offsetX, offsetY: source.offsetY, offsetZ: source.offsetZ,
            rotationX: source.rotationX, rotationY: source.rotationY, rotationZ: source.rotationZ,
            scaleX: source.scaleX, scaleY: source.scaleY, scaleZ: source.scaleZ,
            instanceVisible: true
        })
        setInstanceSelected(sceneInstances.count - 1)
        markProjectDirty()
        statusLabel.text = "Duplicated mesh instance"
    }

    function removeSelectedInstance() {
        if (selectedInstanceIndex < 0 || selectedInstanceIndex >= sceneInstances.count)
            return
        const removedIndex = selectedInstanceIndex
        const removedGeometryKey = sceneInstances.get(removedIndex).geometryKey
        sceneInstances.remove(removedIndex)
        let pieceStillUsed = false
        for (let i = 0; i < sceneInstances.count; ++i) {
            if (sceneInstances.get(i).geometryKey === removedGeometryKey) {
                pieceStillUsed = true
                break
            }
        }
        if (!pieceStillUsed) {
            if (removedGeometryKey !== "source")
                destroyDerivedGeometry(removedGeometryKey)
        }
        if (sceneInstances.count === 0) {
            selectedInstanceIndex = -1
            modelSelected = false
            modelVisible = true
            for (const key of Object.keys(derivedGeometries))
                destroyDerivedGeometry(key)
            importedGeometry.clearMesh()
            markProjectDirty()
            statusLabel.text = "Scene is empty"
            return
        }
        setInstanceSelected(Math.min(removedIndex, sceneInstances.count - 1))
        markProjectDirty()
        statusLabel.text = "Removed mesh instance"
    }

    function mirrorModel(axis) {
        if (axis === "X")
            modelScale = Qt.vector3d(-modelScale.x, modelScale.y, modelScale.z)
        else if (axis === "Y")
            modelScale = Qt.vector3d(modelScale.x, -modelScale.y, modelScale.z)
        else if (axis === "Z")
            modelScale = Qt.vector3d(modelScale.x, modelScale.y, -modelScale.z)
        statusLabel.text = `Mirrored model across ${axis} axis`
    }

    function setCameraView(viewName) {
        if (viewName === "Top")
            setCameraDirectionZUp(0, 0, 1)
        else if (viewName === "Front")
            setCameraDirectionZUp(0, -1, 0)
        else if (viewName === "Right")
            setCameraDirectionZUp(1, 0, 0)
        else
            setCameraDirectionZUp(0, -Math.sin(48 * Math.PI / 180), Math.cos(48 * Math.PI / 180))

        if (importedGeometry.loaded)
            frameImportedModel()
        else {
            cameraRig.position = Qt.vector3d(0, 0, 0)
            camera.position = Qt.vector3d(0, 0, 520)
        }
    }

    function setCameraAxis(axis, side) {
        if (axis === "X")
            setCameraDirectionZUp(side > 0 ? 1 : -1, 0, 0)
        else if (axis === "Y")
            setCameraDirectionZUp(0, side > 0 ? 1 : -1, 0)
        else
            setCameraDirectionZUp(0, 0, side > 0 ? 1 : -1)

        if (importedGeometry.loaded)
            frameImportedModel()
        else {
            cameraRig.position = Qt.vector3d(0, 0, 0)
            camera.position = Qt.vector3d(0, 0, 520)
        }
    }

    function setCameraCubeDirection(xSign, ySign, zSign) {
        if (xSign === 0 && ySign === 0 && zSign === 0)
            return
        setCameraDirectionZUp(xSign, ySign, zSign)
        if (importedGeometry.loaded)
            frameImportedModel()
    }

    function orbitCamera(dx, dy) {
        // The current view direction is the rig's local +Z axis transformed
        // into scene space. mapDirectionFromScene performs the inverse mapping
        // and made successive orbit drags use camera-local coordinates as if
        // they were world coordinates, causing the view cube and scene to jump.
        const direction = cameraRig.mapDirectionToScene(Qt.vector3d(0, 0, 1))
        const radiansPerPixel = 0.35 * Math.PI / 180
        const horizontalLength = Math.sqrt(direction.x * direction.x + direction.y * direction.y)
        let azimuth
        if (horizontalLength < 0.001) {
            const screenUp = cameraRig.mapDirectionToScene(Qt.vector3d(0, 1, 0))
            azimuth = direction.z >= 0
                ? Math.atan2(-screenUp.y, -screenUp.x)
                : Math.atan2(screenUp.y, screenUp.x)
        } else {
            azimuth = Math.atan2(direction.y, direction.x)
        }
        azimuth += dx * radiansPerPixel
        const elevation = Math.max(-89 * Math.PI / 180,
            Math.min(89 * Math.PI / 180,
                Math.asin(Math.max(-1, Math.min(1, direction.z))) - dy * radiansPerPixel))
        const horizontal = Math.cos(elevation)
        setCameraDirectionZUp(horizontal * Math.cos(azimuth),
            horizontal * Math.sin(azimuth), Math.sin(elevation))
    }

    function panCamera(dx, dy) {
        const viewHeight = 2 * camera.position.z
            * Math.tan(camera.fieldOfView * Math.PI / 360)
            / Math.max(1, view3d.height)
        const panDelta = cameraRig.mapDirectionToScene(
            Qt.vector3d(-dx * viewHeight, dy * viewHeight, 0))
        cameraRig.position = Qt.vector3d(
            cameraRig.position.x + panDelta.x,
            cameraRig.position.y + panDelta.y,
            cameraRig.position.z + panDelta.z)
    }

    function setCameraDirectionZUp(x, y, z) {
        const length = Math.sqrt(x * x + y * y + z * z)
        if (length < 0.000001)
            return
        const direction = [x / length, y / length, z / length]
        let up = [-direction[0] * direction[2], -direction[1] * direction[2], 1 - direction[2] * direction[2]]
        let upLength = Math.sqrt(up[0] * up[0] + up[1] * up[1] + up[2] * up[2])
        if (upLength < 0.000001) {
            up = [0, 1, 0]
            upLength = 1
        }
        up = [up[0] / upLength, up[1] / upLength, up[2] / upLength]
        let right = [up[1] * direction[2] - up[2] * direction[1],
                     up[2] * direction[0] - up[0] * direction[2],
                     up[0] * direction[1] - up[1] * direction[0]]
        const rightLength = Math.sqrt(right[0] * right[0] + right[1] * right[1] + right[2] * right[2])
        right = [right[0] / rightLength, right[1] / rightLength, right[2] / rightLength]
        up = [direction[1] * right[2] - direction[2] * right[1],
              direction[2] * right[0] - direction[0] * right[2],
              direction[0] * right[1] - direction[1] * right[0]]

        // Build a camera rotation whose local +Z faces the requested view
        // direction and whose local +Y follows projected world +Z.
        const m00 = right[0], m01 = up[0], m02 = direction[0]
        const m10 = right[1], m11 = up[1], m12 = direction[1]
        const m20 = right[2], m21 = up[2], m22 = direction[2]
        const trace = m00 + m11 + m22
        let qw, qx, qy, qz, scale
        if (trace > 0) {
            scale = Math.sqrt(trace + 1) * 2
            qw = 0.25 * scale
            qx = (m21 - m12) / scale
            qy = (m02 - m20) / scale
            qz = (m10 - m01) / scale
        } else if (m00 > m11 && m00 > m22) {
            scale = Math.sqrt(1 + m00 - m11 - m22) * 2
            qw = (m21 - m12) / scale
            qx = 0.25 * scale
            qy = (m01 + m10) / scale
            qz = (m02 + m20) / scale
        } else if (m11 > m22) {
            scale = Math.sqrt(1 + m11 - m00 - m22) * 2
            qw = (m02 - m20) / scale
            qx = (m01 + m10) / scale
            qy = 0.25 * scale
            qz = (m12 + m21) / scale
        } else {
            scale = Math.sqrt(1 + m22 - m00 - m11) * 2
            qw = (m10 - m01) / scale
            qx = (m02 + m20) / scale
            qy = (m12 + m21) / scale
            qz = 0.25 * scale
        }
        cameraRig.rotation = Qt.quaternion(qw, qx, qy, qz)
    }

    function zoomCamera(factor) {
        camera.position = Qt.vector3d(0, 0,
            Math.max(1, Math.min(100000, camera.position.z * factor)))
    }

    Shortcut { sequence: "Ctrl+O"; context: Qt.WindowShortcut; onActivated: meshDialog.open() }
    Shortcut { sequence: "Ctrl+1"; onActivated: setCameraView("Top") }
    Shortcut { sequence: "Ctrl+2"; onActivated: setCameraView("Front") }
    Shortcut { sequence: "Ctrl+3"; onActivated: setCameraView("Right") }
    Shortcut { sequence: "Ctrl+4"; onActivated: setCameraView("Iso") }
    Shortcut {
        sequence: "Ctrl+F"
        context: Qt.WindowShortcut
        onActivated: frameImportedModel()
    }
    Shortcut {
        sequence: "Ctrl+D"
        context: Qt.WindowShortcut
        onActivated: duplicateSelectedInstance()
    }
    Shortcut {
        sequence: "Delete"
        context: Qt.WindowShortcut
        onActivated: removeSelectedInstance()
    }
    Shortcut {
        sequence: "Ctrl+H"
        context: Qt.WindowShortcut
        onActivated: {
            if (importedGeometry.loaded && selectedInstanceIndex >= 0)
                modelVisible = !modelVisible
        }
    }
    Shortcut {
        sequence: "Ctrl+Shift+R"
        onActivated: {
            if (!importedGeometry.loaded) return
            modelOffset = Qt.vector3d(0, 0, 0)
            modelRotation = Qt.vector3d(0, 0, 0)
            modelScale = Qt.vector3d(1, 1, 1)
            modelVisible = true
            frameImportedModel()
        }
    }
}
