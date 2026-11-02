import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
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
    visibility: Window.Maximized
    title: "Outlaw Forge - Native Viewport"
    color: "#566372"
    property bool modelSelected: false
    property bool modelVisible: true
    property bool scenePanelVisible: true
    property bool gridVisible: true
    property real buildPlateWidthMm: 220
    property real buildPlateDepthMm: 220
    property vector3d modelOffset: Qt.vector3d(0, 0, 0)
    property vector3d modelRotation: Qt.vector3d(0, 0, 0)
    property vector3d modelScale: Qt.vector3d(1, 1, 1)
    property int selectedInstanceIndex: -1
    property var selectedInstanceIds: []
    property string selectionAnchorId: ""
    property var derivedGeometries: ({})
    property var booleanOperandOptions: []
    property bool booleanUsesMultiSelection: false
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
    property bool pendingProjectDiscardChanges: false
    property string projectSaveError: ""
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

    function viewportHorizontalOffset() {
        return scenePanelVisible ? -scenePanel.width * 0.125 : 0
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

    function arrangeInstances(selectedOnly, bedWidth, bedDepth, spacingMm) {
        const margin = 2.0
        if (!Number.isFinite(bedWidth) || !Number.isFinite(bedDepth)
                || !Number.isFinite(spacingMm) || bedWidth <= margin * 2
                || bedDepth <= margin * 2 || spacingMm < 0) {
            statusLabel.text = "Arrangement needs positive bed dimensions and non-negative spacing"
            return false
        }

        const items = []
        for (let i = 0; i < sceneInstances.count; ++i) {
            const row = sceneInstances.get(i)
            if (!row.instanceVisible || (selectedOnly && !isInstanceSelected(i)))
                continue
            const bounds = instanceWorldBounds(i)
            if (!bounds) {
                statusLabel.text = `Arrangement stopped: could not measure ${row.name}`
                return false
            }
            const width = bounds.maxX - bounds.minX
            const depth = bounds.maxY - bounds.minY
            if (width > bedWidth - margin * 2 || depth > bedDepth - margin * 2) {
                statusLabel.text = `Arrangement stopped: ${row.name} exceeds the ${bedWidth} x ${bedDepth} mm build plate`
                return false
            }
            items.push({ index: i, name: row.name, bounds: bounds, width: width, depth: depth })
        }
        if (items.length === 0) {
            statusLabel.text = selectedOnly ? "Select a visible object to arrange" : "No visible objects to arrange"
            return false
        }

        const placements = []
        if (selectedOnly) {
            let minX = Number.POSITIVE_INFINITY
            let minY = Number.POSITIVE_INFINITY
            let maxX = Number.NEGATIVE_INFINITY
            let maxY = Number.NEGATIVE_INFINITY
            for (const item of items) {
                minX = Math.min(minX, item.bounds.minX)
                minY = Math.min(minY, item.bounds.minY)
                maxX = Math.max(maxX, item.bounds.maxX)
                maxY = Math.max(maxY, item.bounds.maxY)
            }
            const shiftX = -(minX + maxX) * 0.5
            const shiftY = -(minY + maxY) * 0.5
            for (const item of items)
                placements.push({ index: item.index, x: shiftX, y: shiftY })
        } else {
            // Stable, largest-first shelf packing reduces wasted bed area while
            // keeping every model's current orientation unchanged.
            items.sort((a, b) => (b.depth - a.depth) || (b.width - a.width) || (a.index - b.index))
            const minX = -bedWidth * 0.5 + margin
            const maxX = bedWidth * 0.5 - margin
            const minY = -bedDepth * 0.5 + margin
            const maxY = bedDepth * 0.5 - margin
            let cursorX = minX
            let cursorY = minY
            let shelfDepth = 0
            for (const item of items) {
                if (cursorX + item.width > maxX + 0.000001) {
                    cursorX = minX
                    cursorY += shelfDepth + spacingMm
                    shelfDepth = 0
                }
                if (cursorY + item.depth > maxY + 0.000001) {
                    statusLabel.text = `Arrangement stopped: visible objects do not fit on the ${bedWidth} x ${bedDepth} mm build plate`
                    return false
                }
                placements.push({ index: item.index,
                    x: cursorX + item.width * 0.5 - (item.bounds.minX + item.bounds.maxX) * 0.5,
                    y: cursorY + item.depth * 0.5 - (item.bounds.minY + item.bounds.maxY) * 0.5 })
                cursorX += item.width + spacingMm
                shelfDepth = Math.max(shelfDepth, item.depth)
            }
        }

        // Apply only after every item has a valid destination. Keeping this
        // commit in one guarded block makes failed arrangements non-mutating.
        restoringInstanceState = true
        for (const placement of placements) {
            const row = sceneInstances.get(placement.index)
            sceneInstances.setProperty(placement.index, "offsetX", row.offsetX + placement.x)
            sceneInstances.setProperty(placement.index, "offsetY", row.offsetY + placement.y)
        }
        restoringInstanceState = false
        if (selectedInstanceIndex >= 0 && selectedInstanceIndex < sceneInstances.count)
            activateInstanceIndex(selectedInstanceIndex)
        buildPlateWidthMm = bedWidth
        buildPlateDepthMm = bedDepth
        markProjectDirty()
        statusLabel.text = selectedOnly
            ? "Centered selected object on the build plate"
            : `Arranged ${placements.length} visible objects with ${spacingMm} mm spacing`
        return true
    }

    function clearScene() {
        while (sceneInstances.count > 0) {
            setInstanceSelected(sceneInstances.count - 1)
            removeSelectedInstance()
        }
        statusLabel.text = "Scene cleared"
        markProjectDirty()
    }

    function hasProjectState() {
        return !!projectDirectory || (sceneInstances ? sceneInstances.count > 0 : false)
            || (importedGeometry ? importedGeometry.loaded : false)
    }

    function unsavedActionTitle() {
        if (pendingProjectAction === "close")
            return "Save before closing?"
        if (pendingProjectAction === "open")
            return "Save before opening another project?"
        if (pendingProjectAction === "import")
            return "Save before replacing this scene?"
        return "Save project changes?"
    }

    function unsavedActionMessage() {
        let projectName = "this project"
        if (projectDirectory) {
            const path = decodeURIComponent(projectDirectory).replace(/[\\/]+$/, "")
            projectName = path.substring(Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\")) + 1) || projectName
        }
        const source = projectDirectory
            ? `There are unsaved changes to ${projectName}.`
            : "This scene has not been saved as a project yet."
        let message = source
        if (pendingProjectAction === "close")
            message += " Save it before closing the workbench, or close without saving?"
        else if (pendingProjectAction === "open")
            message += " Opening another project will replace the current scene. Save it first, open without saving, or cancel."
        else if (pendingProjectAction === "import")
            message += " Importing this model will replace the current scene. Save it first, replace without saving, or cancel."
        if (projectSaveError)
            message += `\n\nSave failed: ${projectSaveError}`
        return message
    }

    function cancelPendingProjectAction() {
        unsavedProjectDialog.close()
        pendingProjectAction = ""
        pendingProjectImportUrl = ""
        pendingProjectDiscardChanges = false
    }

    function markProjectDirty() {
        if (!restoringProjectGeometry && hasProjectState())
            projectDirty = true
    }

    function requestProjectAction(action, importUrl) {
        pendingProjectAction = action
        pendingProjectImportUrl = importUrl || ""
        pendingProjectDiscardChanges = false
        projectSaveError = ""
        if (projectDirty && hasProjectState()) {
            unsavedProjectDialog.open()
            return
        }
        projectDirty = false
        continuePendingProjectAction()
    }

    function continuePendingProjectAction() {
        const action = pendingProjectAction
        const importUrl = pendingProjectImportUrl
        const discardChanges = pendingProjectDiscardChanges
        pendingProjectAction = ""
        pendingProjectImportUrl = ""
        pendingProjectDiscardChanges = false
        if (action === "open")
            projectOpenDialog.open()
        else if (action === "import")
            performMeshImport(importUrl, discardChanges)
        else if (action === "close")
            window.close()
    }

    function selectedGeometry() {
        if (selectedInstanceIndex < 0 || selectedInstanceIndex >= sceneInstances.count)
            return importedGeometry
        return geometryForKey(sceneInstances.get(selectedInstanceIndex).geometryKey)
    }

    function selectedInstanceIndices() {
        const indices = []
        if (selectedInstanceIndex >= 0 && selectedInstanceIndex < sceneInstances.count
                && isInstanceSelected(selectedInstanceIndex))
            indices.push(selectedInstanceIndex)
        for (let index = 0; index < sceneInstances.count; ++index) {
            if (index !== selectedInstanceIndex && isInstanceSelected(index))
                indices.push(index)
        }
        return indices
    }

    function selectedInstanceCount() {
        return selectedInstanceIndices().length
    }

    function isInstanceSelected(index) {
        if (index < 0 || index >= sceneInstances.count)
            return false
        const id = sceneInstances.get(index).instanceId
        return selectedInstanceIds.indexOf(id) >= 0
    }

    function clearInstanceSelection() {
        selectedInstanceIds = []
        selectionAnchorId = ""
        selectedInstanceIndex = -1
        modelSelected = false
        meshAnalysis = ({})
    }

    function updateInstanceSelection(index, modifiers) {
        if (index < 0 || index >= sceneInstances.count)
            return
        const id = sceneInstances.get(index).instanceId
        const control = (modifiers & Qt.ControlModifier) !== 0
        const shift = (modifiers & Qt.ShiftModifier) !== 0
        if (!control && !shift && isInstanceSelected(index)) {
            activateInstanceIndex(index)
            return
        }
        if (shift && selectionAnchorId) {
            let anchor = -1
            for (let i = 0; i < sceneInstances.count; ++i) {
                if (sceneInstances.get(i).instanceId === selectionAnchorId) {
                    anchor = i
                    break
                }
            }
            if (anchor >= 0) {
                const ids = control ? selectedInstanceIds.slice() : []
                const start = Math.min(anchor, index)
                const end = Math.max(anchor, index)
                for (let i = start; i <= end; ++i) {
                    const rangeId = sceneInstances.get(i).instanceId
                    if (ids.indexOf(rangeId) < 0)
                        ids.push(rangeId)
                }
                selectedInstanceIds = ids
                activateInstanceIndex(index)
                return
            }
        }
        if (control) {
            const ids = selectedInstanceIds.slice()
            const existing = ids.indexOf(id)
            if (existing >= 0)
                ids.splice(existing, 1)
            else
                ids.push(id)
            selectedInstanceIds = ids
            if (ids.length === 0) {
                clearInstanceSelection()
                return
            }
            selectionAnchorId = id
            activateInstanceIndex(ids.indexOf(id) >= 0 ? index : findInstanceIndex(ids[ids.length - 1]))
            return
        }
        setInstanceSelected(index)
    }

    function findInstanceIndex(instanceId) {
        for (let index = 0; index < sceneInstances.count; ++index) {
            if (sceneInstances.get(index).instanceId === instanceId)
                return index
        }
        return -1
    }

    function selectAllInstances() {
        if (sceneInstances.count === 0)
            return
        const ids = []
        for (let i = 0; i < sceneInstances.count; ++i)
            ids.push(sceneInstances.get(i).instanceId)
        selectedInstanceIds = ids
        selectionAnchorId = ids[0]
        activateInstanceIndex(0)
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
            projectSaveError = statusLabel.text
            if (pendingProjectAction)
                unsavedProjectDialog.open()
            return { ok: false, error: statusLabel.text }
        }
        projectDirectory = folderUrl.toString()
        projectDirty = false
        projectSaveError = ""
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
        geometry.loadFailed.connect(function(message) { statusLabel.text = message })
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

    function releaseUnreferencedDerivedGeometry(key) {
        if (!key || key === "source")
            return
        for (let i = 0; i < sceneInstances.count; ++i) {
            if (sceneInstances.get(i).geometryKey === key)
                return
        }
        destroyDerivedGeometry(key)
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
        if (lowerPath.endsWith(".3mf"))
            return geometry.load3mf(url)
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
        markProjectDirty()
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
        markProjectDirty()
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

    function openBooleanDialog() {
        if (selectedInstanceIndex < 0 || selectedInstanceIndex >= sceneInstances.count)
            return
        const options = []
        const hasMultiSelection = selectedInstanceCount() > 1
        for (let index = 0; index < sceneInstances.count; ++index) {
            if (index === selectedInstanceIndex || (hasMultiSelection && !isInstanceSelected(index)))
                continue
            const row = sceneInstances.get(index)
            const geometry = geometryForKey(row.geometryKey)
            if (geometry && geometry.loaded)
                options.push({ label: row.name, instanceIndex: index })
        }
        if (options.length === 0) {
            statusLabel.text = "Load or duplicate another mesh before running a Boolean operation."
            return
        }
        booleanOperandOptions = options
        booleanUsesMultiSelection = hasMultiSelection
        booleanOperand.currentIndex = 0
        booleanDialog.open()
    }

    function applyBooleanOperation() {
        if (selectedInstanceIndex < 0 || selectedInstanceIndex >= sceneInstances.count
                || booleanOperandOptions.length === 0
                || (!booleanUsesMultiSelection && (booleanOperand.currentIndex < 0
                    || booleanOperand.currentIndex >= booleanOperandOptions.length)))
            return false
        const firstIndex = selectedInstanceIndex
        const firstRow = sceneInstances.get(firstIndex)
        const firstInstanceId = firstRow.instanceId
        const operands = booleanUsesMultiSelection
            ? booleanOperandOptions
            : [booleanOperandOptions[booleanOperand.currentIndex]]
        const consumedInstanceIds = operands.map(operand => sceneInstances.get(operand.instanceIndex).instanceId)
        const firstGeometry = geometryForKey(firstRow.geometryKey)
        let currentGeometry = firstGeometry
        let currentOffset = Qt.vector3d(firstRow.offsetX, firstRow.offsetY, firstRow.offsetZ)
        let currentRotation = Qt.vector3d(firstRow.rotationX, firstRow.rotationY, firstRow.rotationZ)
        let currentScale = Qt.vector3d(firstRow.scaleX, firstRow.scaleY, firstRow.scaleZ)
        const intermediateResults = []
        for (const operand of operands) {
            const secondRow = sceneInstances.get(operand.instanceIndex)
            const secondGeometry = geometryForKey(secondRow.geometryKey)
            const resultGeometry = createDerivedGeometry()
            const result = currentGeometry.booleanMesh(secondGeometry, booleanOperation.currentText.toLowerCase(),
                resultGeometry.geometry,
                currentOffset, currentRotation, currentScale,
                Qt.vector3d(secondRow.offsetX, secondRow.offsetY, secondRow.offsetZ),
                Qt.vector3d(secondRow.rotationX, secondRow.rotationY, secondRow.rotationZ),
                Qt.vector3d(secondRow.scaleX, secondRow.scaleY, secondRow.scaleZ))
            if (result.error) {
                destroyDerivedGeometry(resultGeometry.key)
                for (const intermediate of intermediateResults)
                    destroyDerivedGeometry(intermediate.key)
                statusLabel.text = result.error
                return false
            }
            intermediateResults.push(resultGeometry)
            currentGeometry = resultGeometry.geometry
            currentOffset = Qt.vector3d(0, 0, 0)
            currentRotation = Qt.vector3d(0, 0, 0)
            currentScale = Qt.vector3d(1, 1, 1)
        }
        const finalGeometry = intermediateResults[intermediateResults.length - 1]
        const previousGeometryKey = firstRow.geometryKey
        const activeIndex = findInstanceIndex(firstInstanceId)
        if (activeIndex < 0) {
            for (const intermediate of intermediateResults)
                destroyDerivedGeometry(intermediate.key)
            statusLabel.text = "The active input was removed before the operation could be committed."
            return false
        }
        sceneInstances.setProperty(activeIndex, "geometryKey", finalGeometry.key)
        sceneInstances.setProperty(activeIndex, "name", `${firstRow.name} - ${booleanOperation.currentText}`)
        sceneInstances.setProperty(activeIndex, "piece", "derived")
        sceneInstances.setProperty(activeIndex, "offsetX", 0)
        sceneInstances.setProperty(activeIndex, "offsetY", 0)
        sceneInstances.setProperty(activeIndex, "offsetZ", 0)
        sceneInstances.setProperty(activeIndex, "rotationX", 0)
        sceneInstances.setProperty(activeIndex, "rotationY", 0)
        sceneInstances.setProperty(activeIndex, "rotationZ", 0)
        sceneInstances.setProperty(activeIndex, "scaleX", 1)
        sceneInstances.setProperty(activeIndex, "scaleY", 1)
        sceneInstances.setProperty(activeIndex, "scaleZ", 1)
        const removedGeometryKeys = []
        const removeIndices = []
        for (const id of consumedInstanceIds) {
            const index = findInstanceIndex(id)
            if (index >= 0 && id !== firstInstanceId)
                removeIndices.push(index)
        }
        removeIndices.sort((a, b) => b - a)
        for (const index of removeIndices) {
            removedGeometryKeys.push(sceneInstances.get(index).geometryKey)
            sceneInstances.remove(index)
        }
        const updatedActiveIndex = findInstanceIndex(firstInstanceId)
        setInstanceSelected(updatedActiveIndex)
        for (let i = 0; i < intermediateResults.length - 1; ++i)
            destroyDerivedGeometry(intermediateResults[i].key)
        releaseUnreferencedDerivedGeometry(previousGeometryKey)
        for (const key of removedGeometryKeys)
            releaseUnreferencedDerivedGeometry(key)
        refreshMeshAnalysis()
        statusLabel.text = `${booleanOperation.currentText} complete: ${finalGeometry.geometry.triangleCount} triangles. Combined ${operands.length + 1} objects; the input objects were consumed.`
        markProjectDirty()
        return true
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
        if (projectDirty && hasProjectState()) {
            close.accepted = false
            window.requestProjectAction("close")
        } else {
            projectDirty = false
        }
    }

    onModelOffsetChanged: { syncActiveInstance(); if (!restoringInstanceState) markProjectDirty() }
    onModelRotationChanged: { syncActiveInstance(); if (!restoringInstanceState) markProjectDirty() }
    onModelScaleChanged: { syncActiveInstance(); if (!restoringInstanceState) markProjectDirty() }
    onModelVisibleChanged: { syncActiveInstance(); if (!restoringInstanceState) markProjectDirty() }
    onScenePanelVisibleChanged: {
        const shift = -scenePanel.width * 0.125 * (scenePanelVisible ? 1 : -1)
        cameraRig.position = Qt.vector3d(cameraRig.position.x + shift, cameraRig.position.y, cameraRig.position.z)
    }

    ToolBar {
        id: headerBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 58
        z: 100
        background: Rectangle {
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#66343b45" }
                GradientStop { position: 0.48; color: "#661e252d" }
                GradientStop { position: 1.0; color: "#6614191d" }
            }
            border.color: "#626c76"
            border.width: 1
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 18
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#55c5e8ff" }
                    GradientStop { position: 0.55; color: "#26c5e8ff" }
                    GradientStop { position: 1.0; color: "#00c5e8ff" }
                }
            }
            Rectangle {
                x: parent.width * 0.31
                y: -22
                width: 250
                height: 100
                rotation: -8
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#00ffffff" }
                    GradientStop { position: 0.5; color: "#20ffffff" }
                    GradientStop { position: 1.0; color: "#00ffffff" }
                }
            }
        }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            Item {
                Layout.preferredWidth: 32
                Layout.preferredHeight: 34
                Rectangle {
                    x: 2; y: 4; width: 29; height: 29; radius: 4
                    color: "#582e19"
                    border.color: "#8b4d25"
                }
                Rectangle {
                    x: 0; y: 0; width: 29; height: 29; radius: 4
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "#ffb36c" }
                        GradientStop { position: 0.16; color: "#f08b42" }
                        GradientStop { position: 1.0; color: "#c75e29" }
                    }
                    border.color: "#ffc48d"
                    Text { anchors.centerIn: parent; text: "OF"; color: "#17120e"; font.pixelSize: 11; font.weight: Font.Black; font.letterSpacing: -0.5 }
                }
            }
            Label {
                text: "OUTLAW FORGE"
                color: "#f2e9dd"
                font.pixelSize: 13
                font.weight: Font.Bold
                font.letterSpacing: 1.35
            }
            Label {
                text: "NATIVE WORKBENCH"
                color: "#92877c"
                font.pixelSize: 10
                Layout.leftMargin: 12
            }
            Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 26; color: "#343c37"; Layout.leftMargin: 8; Layout.rightMargin: 4 }
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
                    MenuItem { text: "Add model...    Ctrl+O"; onTriggered: meshDialog.open() }
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
                    MenuItem { text: selectedInstanceCount() > 1 ? `Duplicate ${selectedInstanceCount()} objects    Ctrl+D` : "Duplicate instance    Ctrl+D"; enabled: selectedInstanceIndex >= 0; onTriggered: window.duplicateSelectedInstance() }
                    MenuItem { text: selectedInstanceCount() > 1 ? `Remove ${selectedInstanceCount()} objects    Delete` : "Remove instance    Delete"; enabled: selectedInstanceIndex >= 0; onTriggered: window.removeSelectedInstance() }
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
                    MenuSeparator {}
                    MenuItem { text: "Arrange build plate..."; enabled: sceneInstances.count > 0; onTriggered: arrangeDialog.open() }
                    MenuSeparator {}
                    MenuItem { text: "Boolean operation..."; enabled: selectedInstanceIndex >= 0 && sceneInstances.count > 1; onTriggered: window.openBooleanDialog() }
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
                color: "#aab8af"
                font.pixelSize: 10
                font.family: "monospace"
            }
            Label {
                text: window.projectDirty && window.hasProjectState() ? "●  UNSAVED" : (window.projectDirectory ? "SAVED PROJECT" : "LOCAL SESSION")
                color: window.projectDirty && window.hasProjectState() ? "#f29a56" : "#7b8a80"
                font.pixelSize: 9
                font.weight: Font.DemiBold
                font.letterSpacing: 0.7
                Layout.leftMargin: 6
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
                text: "Add Model"
                onClicked: meshDialog.open()
                background: Rectangle {
                    id: importSurface
                    property bool pressed: parent.down
                    anchors.fill: parent
                    anchors.topMargin: pressed ? 2 : 0
                    anchors.bottomMargin: pressed ? 0 : 4
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: importSurface.pressed ? "#f08b42" : "#ffb36c" }
                        GradientStop { position: 0.2; color: importSurface.pressed ? "#df7534" : "#f28c45" }
                        GradientStop { position: 1.0; color: importSurface.pressed ? "#b34d24" : "#d5682d" }
                    }
                    border.color: pressed ? "#d9773e" : "#ffc48d"
                    radius: 4
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        shadowEnabled: !importSurface.pressed
                        shadowColor: "#99000000"
                        shadowBlur: 0.28
                        shadowVerticalOffset: 3
                    }
                }
                contentItem: Text { text: parent.text; color: "#1c130d"; font.pixelSize: 11; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
            }
        }
    }

    Item {
        id: viewportWorkspace
        anchors.fill: parent

        Rectangle {
            id: scenePanel
            width: 258
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.topMargin: headerBar.height
            z: 30
            visible: window.scenePanelVisible
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#662b2e37" }
                GradientStop { position: 0.52; color: "#661c2026" }
                GradientStop { position: 1.0; color: "#66111615" }
            }
            border.color: "#5a626b"
            border.width: 1

            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#32c6e7ff" }
                    GradientStop { position: 0.32; color: "#18c6e7ff" }
                    GradientStop { position: 0.72; color: "#18ffb36c" }
                    GradientStop { position: 1.0; color: "#00ffffff" }
                }
            }
            Rectangle {
                x: -38
                y: 250
                width: 320
                height: 110
                rotation: -16
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#00ffffff" }
                    GradientStop { position: 0.48; color: "#20ffd9ad" }
                    GradientStop { position: 1.0; color: "#00ffffff" }
                }
            }

            ScrollView {
                id: sceneScrollView
                anchors.fill: parent
                anchors.margins: 7
                clip: true
                contentWidth: availableWidth
                ScrollBar.vertical.policy: ScrollBar.AsNeeded

                ColumnLayout {
                x: 7
                width: sceneScrollView.availableWidth - 14
                spacing: 9
                Label { text: "SCENE"; color: "#a9b4ac"; font.pixelSize: 10; font.weight: Font.Bold; font.letterSpacing: 1.35 }
                Label { text: `${sceneInstances.count} ${sceneInstances.count === 1 ? "OBJECT" : "OBJECTS"}${window.selectedInstanceCount() > 1 ? `  /  ${window.selectedInstanceCount()} SELECTED` : ""}`; color: "#657169"; font.pixelSize: 9; font.family: "monospace" }
                Label { visible: sceneInstances.count > 1; text: "Ctrl-click: add or remove  /  Shift-click: range"; color: "#77877d"; font.pixelSize: 9; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                Repeater {
                    model: sceneInstances
                    delegate: Rectangle {
                        id: sceneRow
                        required property int index
                        required property string name
                        Layout.fillWidth: true
                        height: 38
                        radius: 4
                        z: rowHover.hovered ? 2 : 0
                        color: index === window.selectedInstanceIndex
                            ? (rowHover.hovered ? "#3a291d" : "#292018")
                            : window.isInstanceSelected(index)
                                ? (rowHover.hovered ? "#183432" : "#142725")
                            : (rowHover.hovered ? "#242d28" : "#191f1c")
                        border.color: index === window.selectedInstanceIndex ? "#e59456" : window.isInstanceSelected(index) ? "#62c7b3" : "#3b4840"
                        transform: Translate {
                            y: rowHover.hovered ? -2 : 0
                            Behavior on y { NumberAnimation { duration: 110; easing.type: Easing.OutCubic } }
                        }
                        layer.enabled: true
                        layer.effect: MultiEffect {
                            shadowEnabled: rowHover.hovered || window.isInstanceSelected(sceneRow.index)
                            shadowColor: sceneRow.index === window.selectedInstanceIndex ? "#a64b2410" : "#6262c7b3"
                            shadowBlur: 0.28
                            shadowVerticalOffset: 3
                        }
                        HoverHandler { id: rowHover }
                        Rectangle {
                            visible: window.isInstanceSelected(sceneRow.index)
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: 3
                            color: sceneRow.index === window.selectedInstanceIndex ? "#f29a56" : "#62c7b3"
                            radius: 2
                        }
                        MouseArea { anchors.fill: parent; onClicked: function(mouse) { window.updateInstanceSelection(index, mouse.modifiers) } }
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            Label { text: "◆"; color: index === window.selectedInstanceIndex ? "#f29a56" : window.isInstanceSelected(index) ? "#62c7b3" : "#76847a"; font.pixelSize: 10 }
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
                    color: "#a9b5ac"
                    font.pixelSize: 10
                    font.family: "monospace"
                    wrapMode: Text.WordWrap
                }
                Button {
                    text: window.selectedInstanceCount() > 1
                        ? `Duplicate ${window.selectedInstanceCount()} objects` : "Duplicate instance"
                    Layout.fillWidth: true
                    enabled: importedGeometry.loaded && selectedInstanceIndex >= 0
                    onClicked: window.duplicateSelectedInstance()
                    ToolTip.visible: hovered
                    ToolTip.text: "Duplicate selected mesh (Ctrl+D)"
                    contentItem: Text { text: parent.text; color: parent.enabled ? "#e5e2da" : "#746f66"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    background: Rectangle {
                        id: duplicateSurface
                        property bool buttonEnabled: parent.enabled
                        anchors.fill: parent
                        anchors.bottomMargin: parent.enabled ? 4 : 1
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: duplicateSurface.buttonEnabled ? "#68737b" : "#39403f" }
                            GradientStop { position: 0.2; color: duplicateSurface.buttonEnabled ? "#424b52" : "#292e2d" }
                            GradientStop { position: 1.0; color: duplicateSurface.buttonEnabled ? "#242a2d" : "#1d2221" }
                        }
                        border.color: buttonEnabled ? "#89949c" : "#414845"
                        radius: 5
                        layer.enabled: true
                        layer.effect: MultiEffect { shadowEnabled: duplicateSurface.buttonEnabled; shadowColor: "#99000000"; shadowBlur: 0.32; shadowVerticalOffset: 4 }
                    }
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
                    Layout.fillWidth: true
                    onClicked: importedGeometry.loaded ? window.removeSelectedInstance() : meshDialog.open()
                    ToolTip.visible: hovered && importedGeometry.loaded
                    ToolTip.text: "Remove selected scene instance (Delete)"
                    contentItem: Text { text: parent.text; color: importedGeometry.loaded ? "#f0e9e0" : "#24150d"; font.pixelSize: 11; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    background: Rectangle {
                        id: chooseModelSurface
                        property bool pressed: parent.down
                        anchors.fill: parent
                        anchors.topMargin: parent.down ? 3 : 0
                        anchors.bottomMargin: parent.down ? 0 : 5
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: chooseModelSurface.pressed ? "#d66b2c" : "#ffc17a" }
                            GradientStop { position: 0.2; color: importedGeometry.loaded ? "#555f66" : (chooseModelSurface.pressed ? "#e97832" : "#ff9a43") }
                            GradientStop { position: 1.0; color: importedGeometry.loaded ? "#272e31" : (chooseModelSurface.pressed ? "#a74421" : "#d86429") }
                        }
                        border.color: importedGeometry.loaded ? "#818b91" : "#ffd098"
                        radius: 5
                        layer.enabled: true
                        layer.effect: MultiEffect { shadowEnabled: !chooseModelSurface.pressed; shadowColor: "#bb000000"; shadowBlur: 0.42; shadowVerticalOffset: 5 }
                    }
                }
                Button {
                    text: modelVisible ? "Hide instance" : "Show instance"
                    Layout.fillWidth: true
                    enabled: importedGeometry.loaded && selectedInstanceIndex >= 0
                    onClicked: window.modelVisible = !window.modelVisible
                    ToolTip.visible: hovered
                    ToolTip.text: "Toggle selected instance visibility (Ctrl+H)"
                    contentItem: Text { text: parent.text; color: parent.enabled ? "#e5e2da" : "#746f66"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    background: Rectangle {
                        id: visibilitySurface
                        property bool buttonEnabled: parent.enabled
                        anchors.fill: parent
                        anchors.bottomMargin: parent.enabled ? 4 : 1
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: visibilitySurface.buttonEnabled ? "#68737b" : "#39403f" }
                            GradientStop { position: 0.2; color: visibilitySurface.buttonEnabled ? "#424b52" : "#292e2d" }
                            GradientStop { position: 1.0; color: visibilitySurface.buttonEnabled ? "#242a2d" : "#1d2221" }
                        }
                        border.color: buttonEnabled ? "#89949c" : "#414845"
                        radius: 5
                        layer.enabled: true
                        layer.effect: MultiEffect { shadowEnabled: visibilitySurface.buttonEnabled; shadowColor: "#99000000"; shadowBlur: 0.32; shadowVerticalOffset: 4 }
                    }
                }
                Button {
                    text: "Reset transforms"
                    Layout.fillWidth: true
                    enabled: importedGeometry.loaded
                    onClicked: {
                        window.modelOffset = Qt.vector3d(0, 0, 0)
                        window.modelRotation = Qt.vector3d(0, 0, 0)
                        window.modelScale = Qt.vector3d(1, 1, 1)
                        window.modelVisible = true
                        frameImportedModel()
                    }
                    contentItem: Text { text: parent.text; color: parent.enabled ? "#e5e2da" : "#746f66"; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    background: Rectangle {
                        id: resetSurface
                        property bool buttonEnabled: parent.enabled
                        anchors.fill: parent
                        anchors.bottomMargin: parent.enabled ? 4 : 1
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: resetSurface.buttonEnabled ? "#59646a" : "#39403f" }
                            GradientStop { position: 0.2; color: resetSurface.buttonEnabled ? "#3c454b" : "#292e2d" }
                            GradientStop { position: 1.0; color: resetSurface.buttonEnabled ? "#232a2d" : "#1d2221" }
                        }
                        border.color: buttonEnabled ? "#808b91" : "#414845"
                        radius: 5
                        layer.enabled: true
                        layer.effect: MultiEffect { shadowEnabled: resetSurface.buttonEnabled; shadowColor: "#99000000"; shadowBlur: 0.32; shadowVerticalOffset: 4 }
                    }
                }
                Rectangle {
                    visible: importedGeometry.loaded
                    Layout.fillWidth: true
                    Layout.topMargin: 5
                    implicitHeight: meshRepairColumn.implicitHeight + 16
                    color: "#171d19"
                    border.color: "#303b34"
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
                            ? `${window.selectedGeometry().triangleCount} triangles - analyze for edge counts`
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
        }

        Item {
            id: viewportRoot
            anchors.fill: parent

            View3D {
                id: view3d
                anchors.fill: parent
                camera: camera
                environment: SceneEnvironment {
                    clearColor: "#20232b"
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
                        position: Qt.vector3d(window.viewportHorizontalOffset(), 0, 0)

                        PerspectiveCamera {
                            id: camera
                            position: Qt.vector3d(0, 0, 180)
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
                        scale: Qt.vector3d(window.buildPlateWidthMm / 100, window.buildPlateDepthMm / 100, 0.012)
                        materials: PrincipledMaterial {
                            baseColor: "#292c32"
                            roughness: 0.76
                            metalness: 0.14
                        }
                    }

                    // Broad, low-opacity light passes sit just below the crisp
                    // grid strokes to create a restrained colored halo.
                    Repeater3D {
                        model: 23
                        delegate: Model {
                            required property int index
                            visible: window.gridVisible && (index === 0 || index === 11 || index === 22)
                            source: "#Cube"
                            position: Qt.vector3d((index - 11) * window.buildPlateWidthMm / 22, 0, 0.045)
                            scale: Qt.vector3d(index === 11 ? 0.018 : 0.014, window.buildPlateDepthMm / 100, 0.0012)
                            materials: PrincipledMaterial {
                                alphaMode: PrincipledMaterial.Blend
                                opacity: 0.24
                                lighting: PrincipledMaterial.NoLighting
                                baseColor: index === 11 ? "#42d8f4" : "#d98c50"
                                emissiveFactor: index === 11 ? Qt.vector3d(0.08, 0.65, 0.82) : Qt.vector3d(0.4, 0.14, 0.035)
                            }
                        }
                    }
                    Repeater3D {
                        model: 23
                        delegate: Model {
                            required property int index
                            visible: window.gridVisible && (index === 0 || index === 11 || index === 22)
                            source: "#Cube"
                            position: Qt.vector3d(0, (index - 11) * window.buildPlateDepthMm / 22, 0.045)
                            scale: Qt.vector3d(window.buildPlateWidthMm / 100, index === 11 ? 0.018 : 0.014, 0.0012)
                            materials: PrincipledMaterial {
                                alphaMode: PrincipledMaterial.Blend
                                opacity: 0.24
                                lighting: PrincipledMaterial.NoLighting
                                baseColor: index === 11 ? "#42d8f4" : "#d98c50"
                                emissiveFactor: index === 11 ? Qt.vector3d(0.08, 0.65, 0.82) : Qt.vector3d(0.4, 0.14, 0.035)
                            }
                        }
                    }

                    Repeater3D {
                        model: 23
                        delegate: Model {
                            required property int index
                            visible: window.gridVisible
                            source: "#Cube"
                            position: Qt.vector3d((index - 11) * window.buildPlateWidthMm / 22, 0, 0.05)
                            scale: Qt.vector3d(0.003, window.buildPlateDepthMm / 100, 0.001)
                            materials: PrincipledMaterial {
                                baseColor: index === 11 ? "#65c5d3" : ((index === 0 || index === 22) ? "#b78a68" : "#63666b")
                                emissiveFactor: index === 11 ? Qt.vector3d(0.04, 0.38, 0.5) : ((index === 0 || index === 22) ? Qt.vector3d(0.25, 0.09, 0.025) : Qt.vector3d(0.012, 0.016, 0.02))
                                roughness: 0.82
                                metalness: 0.16
                            }
                        }
                    }
                    Repeater3D {
                        model: 23
                        delegate: Model {
                            required property int index
                            visible: window.gridVisible
                            source: "#Cube"
                            position: Qt.vector3d(0, (index - 11) * window.buildPlateDepthMm / 22, 0.05)
                            scale: Qt.vector3d(window.buildPlateWidthMm / 100, 0.003, 0.001)
                            materials: PrincipledMaterial {
                                baseColor: index === 11 ? "#65c5d3" : ((index === 0 || index === 22) ? "#b78a68" : "#63666b")
                                emissiveFactor: index === 11 ? Qt.vector3d(0.04, 0.38, 0.5) : ((index === 0 || index === 22) ? Qt.vector3d(0.25, 0.09, 0.025) : Qt.vector3d(0.012, 0.016, 0.02))
                                roughness: 0.82
                                metalness: 0.16
                            }
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
                            baseColor: index === window.selectedInstanceIndex ? "#f1a35d" : window.isInstanceSelected(index) ? "#61c8b4" : "#bd7840"
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
                            window.updateInstanceSelection(pressedInstanceIndex, mouse.modifiers)
                            if (!window.isInstanceSelected(pressedInstanceIndex)) {
                                pressedInstanceIndex = -1
                                return
                            }
                            pressOffset = window.modelOffset
                            pressRotation = window.modelRotation
                            pressScale = window.modelScale
                            const mode = (mouse.modifiers & Qt.AltModifier) ? 1 : window.viewportTransformMode
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
                        if (viewportContextMenu.instanceIndex >= 0
                                && !window.isInstanceSelected(viewportContextMenu.instanceIndex))
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
                        statusLabel.text = "Model selected - drag to move on the build plate"
                    } else {
                        window.clearInstanceSelection()
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

            Rectangle {
                id: meshHud
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.leftMargin: window.scenePanelVisible ? scenePanel.width + 14 : 14
                anchors.rightMargin: 14
                anchors.topMargin: headerBar.height + 14
                width: 232
                height: importedGeometry.loaded ? 76 : 63
                radius: 4
                color: "#121715"
                border.color: "#343d37"
                opacity: 0.96
                z: meshHudHover.hovered ? 20 : 1
                transform: Rotation {
                    origin.x: meshHud.width / 2
                    origin.y: meshHud.height / 2
                    axis.x: 0.15
                    axis.y: 1
                    axis.z: 0
                    angle: meshHudHover.hovered ? 1.4 : 0
                    Behavior on angle { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                }
                HoverHandler { id: meshHudHover }
                layer.enabled: true
                layer.effect: MultiEffect {
                    shadowEnabled: true
                    shadowColor: "#99000000"
                    shadowBlur: 0.38
                    shadowVerticalOffset: 6
                    shadowHorizontalOffset: 2
                }
                Column {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 5
                    Label {
                        text: importedGeometry.loaded && selectedInstanceIndex >= 0
                            ? sceneInstances.get(selectedInstanceIndex).name : "BUILD PLATE"
                        color: "#e8e8df"
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        elide: Text.ElideMiddle
                        width: parent.width
                    }
                    Label {
                        text: importedGeometry.loaded
                            ? `${window.selectedWorldDimensions().x.toFixed(1)} x ${window.selectedWorldDimensions().y.toFixed(1)} x ${window.selectedWorldDimensions().z.toFixed(1)} mm`
                            : `${window.buildPlateWidthMm} x ${window.buildPlateDepthMm} mm PLATE  /  Z-UP`
                        color: "#c4a07f"
                        font.pixelSize: 10
                        font.family: "monospace"
                    }
                    Label {
                        visible: importedGeometry.loaded
                        text: `${window.selectedGeometry().triangleCount.toLocaleString()} TRIANGLES`
                        color: "#849188"
                        font.pixelSize: 8
                        font.family: "monospace"
                    }
                }
            }

            Row {
                id: viewportDisplayToolbar
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.topMargin: headerBar.height + 14
                anchors.rightMargin: 14
                z: 12
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
                anchors.left: viewportDisplayToolbar.left
                anchors.right: viewportDisplayToolbar.right
                anchors.top: viewportDisplayToolbar.top
                anchors.bottom: viewportDisplayToolbar.bottom
                anchors.margins: -8
                z: 11
                radius: 7
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#69736f" }
                    GradientStop { position: 0.08; color: "#29312e" }
                    GradientStop { position: 1.0; color: "#111715" }
                }
                border.color: "#818a84"
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 7
                    radius: 3
                    color: "#080b0a"
                    border.color: "#202722"
                }
                layer.enabled: true
                layer.effect: MultiEffect {
                    shadowEnabled: true
                    shadowColor: "#dd000000"
                    shadowBlur: 0.55
                    shadowVerticalOffset: 9
                    shadowHorizontalOffset: 3
                }
            }

            Rectangle {
                id: transformToolbar
                anchors.top: parent.top
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.horizontalCenterOffset: window.scenePanelVisible ? scenePanel.width * 0.5 : 0
                anchors.topMargin: headerBar.height + 12
                z: 20
                width: transformControls.implicitWidth + 20
                height: transformControls.implicitHeight + 16
                color: "#68716d"
                border.color: "#aab4ad"
                radius: 7
                transform: Rotation {
                    origin.x: transformToolbar.width / 2
                    origin.y: transformToolbar.height / 2
                    axis.x: 0.42
                    axis.y: -1
                    axis.z: 0
                    angle: transformToolbarHover.hovered ? 6 : 3
                    Behavior on angle { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                }
                HoverHandler { id: transformToolbarHover }
                layer.enabled: true
                layer.effect: MultiEffect {
                    shadowEnabled: true
                    shadowColor: "#f0000000"
                    shadowBlur: 0.62
                    shadowVerticalOffset: 12
                    shadowHorizontalOffset: 5
                }

                Rectangle {
                    anchors.fill: parent
                    anchors.leftMargin: 2
                    anchors.rightMargin: 2
                    anchors.topMargin: 2
                    anchors.bottomMargin: 8
                    radius: 5
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "#24312e" }
                        GradientStop { position: 0.15; color: "#161f1d" }
                        GradientStop { position: 1.0; color: "#101513" }
                    }
                    border.color: "#3d5149"
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 7
                    radius: 3
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "#343a36" }
                        GradientStop { position: 1.0; color: "#151a17" }
                    }
                }

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
                                background: Item {
                                    Rectangle {
                                        anchors.fill: parent
                                        color: "#070a09"
                                        radius: 3
                                    }
                                    Rectangle {
                                        anchors.fill: parent
                                        anchors.bottomMargin: parent.parent.down ? 1 : 3
                                        gradient: Gradient {
                                            GradientStop { position: 0.0; color: parent.parent.parent.checked ? "#557d6d" : "#4b5550" }
                                            GradientStop { position: 0.16; color: parent.parent.parent.checked ? "#285344" : "#333d38" }
                                            GradientStop { position: 1.0; color: parent.parent.parent.checked ? "#172b24" : "#1a211e" }
                                        }
                                        border.color: parent.parent.parent.checked ? "#a0d4b8" : "#68736d"
                                        radius: 3
                                    }
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
                                background: Item {
                                    Rectangle {
                                        anchors.fill: parent
                                        color: "#070a09"
                                        radius: 3
                                    }
                                    Rectangle {
                                        anchors.fill: parent
                                        anchors.bottomMargin: parent.parent.down ? 1 : 3
                                        gradient: Gradient {
                                            GradientStop { position: 0.0; color: parent.parent.parent.checked ? "#557d6d" : "#4b5550" }
                                            GradientStop { position: 0.16; color: parent.parent.parent.checked ? "#285344" : "#333d38" }
                                            GradientStop { position: 1.0; color: parent.parent.parent.checked ? "#172b24" : "#1a211e" }
                                        }
                                        border.color: parent.parent.parent.checked ? "#a0d4b8" : "#68736d"
                                        radius: 3
                                    }
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
                anchors.leftMargin: window.scenePanelVisible ? scenePanel.width + 14 : 14
                width: Math.min(500, parent.width * 0.55)
                height: Math.max(54, statusLabel.implicitHeight + 34)
                radius: 3
                color: "#111614"
                border.color: "#37413a"
                opacity: 0.94
                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: 3
                    color: "#ed8b49"
                    radius: 2
                }
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
                title: sceneInstances.count > 0 ? "Add another model" : "Import a mesh"
                nameFilters: ["Mesh files (*.stl *.obj *.3mf)", "STL mesh (*.stl)", "OBJ mesh (*.obj)", "3MF project (*.3mf)", "All files (*)"]
                onAccepted: window.importMesh(selectedFile)
            }

            Dialog {
                id: arrangeDialog
                parent: Overlay.overlay
                title: "Build Plate Arrangement"
                modal: true
                width: 390
                standardButtons: Dialog.Cancel
                contentItem: ColumnLayout {
                    spacing: 10
                    Label {
                        Layout.fillWidth: true
                        text: "Pack visible objects on a rectangular bed. Orientations stay unchanged. A failed fit leaves all transforms untouched."
                        wrapMode: Text.WordWrap
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: "Width (mm)"; Layout.preferredWidth: 88 }
                        SpinBox {
                            id: arrangementBedWidth
                            Layout.fillWidth: true
                            from: 50
                            to: 1000
                            value: window.buildPlateWidthMm
                            editable: true
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: "Depth (mm)"; Layout.preferredWidth: 88 }
                        SpinBox {
                            id: arrangementBedDepth
                            Layout.fillWidth: true
                            from: 50
                            to: 1000
                            value: window.buildPlateDepthMm
                            editable: true
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: "Spacing (mm)"; Layout.preferredWidth: 88 }
                        SpinBox {
                            id: arrangementSpacing
                            Layout.fillWidth: true
                            from: 0
                            to: 50
                            value: 5
                            editable: true
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        text: "2 mm edge clearance. Models are packed largest-first without rotation."
                        color: "#a8947f"
                        font.pixelSize: 10
                        wrapMode: Text.WordWrap
                    }
                    Label {
                        Layout.fillWidth: true
                        text: statusLabel.text
                        color: "#ffb36c"
                        font.pixelSize: 10
                        wrapMode: Text.WordWrap
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Button {
                            text: "Arrange visible"
                            Layout.fillWidth: true
                            onClicked: {
                                if (window.arrangeInstances(false, arrangementBedWidth.value,
                                                           arrangementBedDepth.value, arrangementSpacing.value))
                                    arrangeDialog.close()
                            }
                        }
                        Button {
                            text: "Center selected"
                            Layout.fillWidth: true
                            enabled: window.selectedInstanceIndex >= 0
                            onClicked: {
                                if (window.arrangeInstances(true, arrangementBedWidth.value,
                                                           arrangementBedDepth.value, arrangementSpacing.value))
                                    arrangeDialog.close()
                            }
                        }
                    }
                }
            }

            FolderDialog {
                id: projectParentDialog
                title: "Choose where to create the native project folder"
                onAccepted: projectNameDialog.open()
                onRejected: if (window.pendingProjectAction) unsavedProjectDialog.open()
            }

            Dialog {
                id: booleanDialog
                parent: Overlay.overlay
                title: "Combine Meshes"
                modal: true
                standardButtons: Dialog.Cancel
                contentItem: ColumnLayout {
                    spacing: 10
                    Label { text: "The selected object is the first input."; color: "#c8c5bd" }
                    Label {
                        visible: window.booleanUsesMultiSelection
                        text: `Using all ${window.booleanOperandOptions.length + 1} selected objects in scene-list order. These inputs will be consumed on success.`
                        color: "#62c7b3"
                    }
                    Label { text: "Operation" }
                    ComboBox {
                        id: booleanOperation
                        Layout.fillWidth: true
                        model: ["Union", "Difference", "Intersection"]
                    }
                    Label { visible: !window.booleanUsesMultiSelection; text: "Second object" }
                    ComboBox {
                        id: booleanOperand
                        visible: !window.booleanUsesMultiSelection
                        Layout.fillWidth: true
                        textRole: "label"
                        valueRole: "instanceIndex"
                        model: window.booleanOperandOptions
                    }
                    Label {
                        Layout.fillWidth: true
                        text: window.booleanUsesMultiSelection
                            ? "All selected objects must be closed solids. The result replaces the active object and removes the other selected inputs."
                            : "Both objects must be closed solids. The result replaces the selected object and removes the second object."
                        wrapMode: Text.WordWrap
                        color: "#aaa69d"
                    }
                    Button {
                        Layout.fillWidth: true
                        text: "Apply operation"
                        highlighted: true
                        onClicked: {
                            if (window.applyBooleanOperation())
                                booleanDialog.close()
                        }
                    }
                }
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
                        Qt.callLater(projectNameDialog.open)
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
                title: window.unsavedActionTitle()
                modal: true
                standardButtons: Dialog.NoButton
                contentItem: ColumnLayout {
                    Label {
                        Layout.fillWidth: true
                        text: window.unsavedActionMessage()
                        wrapMode: Text.WordWrap
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignRight
                        Button {
                            text: window.projectDirectory ? "Save changes" : "Save as project"
                            onClicked: {
                                unsavedProjectDialog.close()
                                window.saveCurrentNativeProject()
                            }
                        }
                        Button {
                            text: window.pendingProjectAction === "close" ? "Close without saving"
                                : (window.pendingProjectAction === "import" ? "Replace without saving" : "Open without saving")
                            onClicked: {
                                unsavedProjectDialog.close()
                                window.pendingProjectDiscardChanges = true
                                if (window.pendingProjectAction === "close")
                                    window.projectDirty = false
                                window.continuePendingProjectAction()
                            }
                        }
                        Button {
                            text: "Cancel"
                            onClicked: window.cancelPendingProjectAction()
                        }
                    }
                }
                onRejected: window.cancelPendingProjectAction()
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
                anchors.leftMargin: window.scenePanelVisible ? scenePanel.width + 12 : 12
                anchors.topMargin: headerBar.height + 12
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
        const modelCenter = activeModel.mapPositionToScene(
            Qt.vector3d(0, 0, geometry.dimensions.z * 0.5))
        cameraRig.position = Qt.vector3d(
            modelCenter.x + window.viewportHorizontalOffset(), modelCenter.y, modelCenter.z)
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
        performMeshImport(url, false)
    }

    function performMeshImport(url, discardChanges) {
        const path = url.toString().toLowerCase()
        if (!path.endsWith(".obj") && !path.endsWith(".3mf") && !path.endsWith(".stl")) {
            statusLabel.text = "Supported mesh files are STL, OBJ, and 3MF"
            return
        }

        // The first mesh uses the stable source slot. Every later import gets
        // its own geometry object so different files can coexist in the scene.
        const replaceScene = discardChanges
        const useSourceSlot = replaceScene || (sceneInstances.count === 0 && !importedGeometry.loaded)
        if (useSourceSlot) {
            const previousProjectDirectory = projectDirectory
            if (replaceScene)
                projectDirectory = ""
            pendingImportUrl = url.toString()
            if (!loadSliceGeometry(importedGeometry, url)) {
                projectDirectory = previousProjectDirectory
                return
            }
            statusLabel.text = `Imported ${importedGeometry.fileName}. The source file remains unchanged.`
            return
        }

        const imported = createDerivedGeometry()
        if (!loadSliceGeometry(imported.geometry, url)) {
            destroyDerivedGeometry(imported.key)
            return
        }
        const dimensions = imported.geometry.dimensions
        let offsetX = 0
        const spacing = Math.max(dimensions.x, 10) + 10
        let foundSlot = false
        for (let attempt = 0; attempt < 256 && !foundSlot; ++attempt) {
            foundSlot = true
            const candidate = { minX: offsetX - dimensions.x * 0.5,
                                maxX: offsetX + dimensions.x * 0.5,
                                minY: -dimensions.y * 0.5, maxY: dimensions.y * 0.5 }
            for (let index = 0; index < sceneInstances.count; ++index) {
                if (!sceneInstances.get(index).instanceVisible)
                    continue
                const other = instanceWorldBounds(index)
                if (!other)
                    continue
                const overlapsX = candidate.minX < other.maxX && candidate.maxX > other.minX
                const overlapsY = candidate.minY < other.maxY && candidate.maxY > other.minY
                if (overlapsX && overlapsY) {
                    offsetX = other.maxX + dimensions.x * 0.5 + 10
                    foundSlot = false
                    break
                }
            }
        }
        if (!foundSlot) {
            destroyDerivedGeometry(imported.key)
            statusLabel.text = "Could not find a clear placement for the imported model. The scene was left unchanged."
            return
        }
        sceneInstances.append({
            instanceId: newSceneInstanceId(), name: imported.geometry.fileName, piece: "main",
            geometryKey: imported.key, sourceUrl: url.toString(),
            offsetX: offsetX, offsetY: 0, offsetZ: 0,
            rotationX: 0, rotationY: 0, rotationZ: 0,
            scaleX: 1, scaleY: 1, scaleZ: 1, instanceVisible: true
        })
        setInstanceSelected(sceneInstances.count - 1)
        refreshMeshAnalysis()
        markProjectDirty()
        Qt.callLater(frameImportedModel)
        statusLabel.text = `Added ${imported.geometry.fileName} as a separate model. ${sceneInstances.count} models are loaded.`
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
        const active = sceneInstances.get(selectedInstanceIndex)
        const deltaOffset = Qt.vector3d(modelOffset.x - active.offsetX,
                                        modelOffset.y - active.offsetY,
                                        modelOffset.z - active.offsetZ)
        const deltaRotation = Qt.vector3d(modelRotation.x - active.rotationX,
                                          modelRotation.y - active.rotationY,
                                          modelRotation.z - active.rotationZ)
        const scaleRatio = Qt.vector3d(modelScale.x / active.scaleX,
                                       modelScale.y / active.scaleY,
                                       modelScale.z / active.scaleZ)
        for (const index of selectedInstanceIndices()) {
            const row = sceneInstances.get(index)
            sceneInstances.setProperty(index, "offsetX", row.offsetX + deltaOffset.x)
            sceneInstances.setProperty(index, "offsetY", row.offsetY + deltaOffset.y)
            sceneInstances.setProperty(index, "offsetZ", row.offsetZ + deltaOffset.z)
            sceneInstances.setProperty(index, "rotationX", row.rotationX + deltaRotation.x)
            sceneInstances.setProperty(index, "rotationY", row.rotationY + deltaRotation.y)
            sceneInstances.setProperty(index, "rotationZ", row.rotationZ + deltaRotation.z)
            sceneInstances.setProperty(index, "scaleX", row.scaleX * scaleRatio.x)
            sceneInstances.setProperty(index, "scaleY", row.scaleY * scaleRatio.y)
            sceneInstances.setProperty(index, "scaleZ", row.scaleZ * scaleRatio.z)
            sceneInstances.setProperty(index, "instanceVisible", modelVisible)
        }
        if (!restoringInstanceState)
            markProjectDirty()
    }

    function setInstanceSelected(index) {
        if (index < 0 || index >= sceneInstances.count)
            return
        selectedInstanceIds = [sceneInstances.get(index).instanceId]
        selectionAnchorId = sceneInstances.get(index).instanceId
        activateInstanceIndex(index)
    }

    function activateInstanceIndex(index) {
        if (index < 0 || index >= sceneInstances.count) {
            clearInstanceSelection()
            return
        }
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
        const sourceIndices = selectedInstanceIndices().sort((a, b) => a - b)
        if (sourceIndices.length === 0)
            return
        const sources = []
        let groupBounds = { minX: Number.POSITIVE_INFINITY, minY: Number.POSITIVE_INFINITY,
                            maxX: Number.NEGATIVE_INFINITY, maxY: Number.NEGATIVE_INFINITY }
        for (const index of sourceIndices) {
            const row = sceneInstances.get(index)
            const bounds = instanceWorldBounds(index)
            if (!bounds) {
                statusLabel.text = `Could not read the bounds for ${row.name}`
                return
            }
            sources.push({
                sourceIndex: index, instanceId: row.instanceId, name: row.name,
                piece: row.piece, geometryKey: row.geometryKey, sourceUrl: row.sourceUrl,
                offsetX: row.offsetX, offsetY: row.offsetY, offsetZ: row.offsetZ,
                rotationX: row.rotationX, rotationY: row.rotationY, rotationZ: row.rotationZ,
                scaleX: row.scaleX, scaleY: row.scaleY, scaleZ: row.scaleZ,
                instanceVisible: row.instanceVisible, bounds: bounds
            })
            groupBounds.minX = Math.min(groupBounds.minX, bounds.minX)
            groupBounds.minY = Math.min(groupBounds.minY, bounds.minY)
            groupBounds.maxX = Math.max(groupBounds.maxX, bounds.maxX)
            groupBounds.maxY = Math.max(groupBounds.maxY, bounds.maxY)
        }

        // Move the copied group as a unit, keeping the source group layout intact.
        const spacing = Math.max(groupBounds.maxX - groupBounds.minX, 10) + 10
        let offsetX = spacing
        let slotFound = false
        for (let attempt = 0; attempt < 256 && !slotFound; ++attempt) {
            slotFound = true
            for (const source of sources) {
                if (!source.instanceVisible)
                    continue
                const candidateMinX = source.bounds.minX + offsetX
                const candidateMaxX = source.bounds.maxX + offsetX
                for (let i = 0; i < sceneInstances.count; ++i) {
                    if (isInstanceSelected(i) || !sceneInstances.get(i).instanceVisible)
                        continue
                    const other = instanceWorldBounds(i)
                    if (!other)
                        continue
                    const overlapsX = candidateMinX < other.maxX && candidateMaxX > other.minX
                    const overlapsY = source.bounds.minY < other.maxY && source.bounds.maxY > other.minY
                    if (overlapsX && overlapsY) {
                        slotFound = false
                        offsetX += spacing
                        break
                    }
                }
                if (!slotFound)
                    break
            }
        }
        if (!slotFound) {
            statusLabel.text = "Could not find a clear placement for the duplicate"
            return
        }
        const copies = []
        for (const source of sources) {
            const instanceId = newSceneInstanceId()
            copies.push({
                instanceId: instanceId,
                name: `${source.name} copy`,
                piece: source.piece, geometryKey: source.geometryKey, sourceUrl: source.sourceUrl,
                offsetX: source.offsetX + offsetX, offsetY: source.offsetY, offsetZ: source.offsetZ,
                rotationX: source.rotationX, rotationY: source.rotationY, rotationZ: source.rotationZ,
                scaleX: source.scaleX, scaleY: source.scaleY, scaleZ: source.scaleZ,
                instanceVisible: source.instanceVisible
            })
        }
        const activeSourceId = sceneInstances.get(selectedInstanceIndex).instanceId
        const activeCopyIndex = sources.findIndex(source => source.instanceId === activeSourceId)
        for (const copy of copies)
            sceneInstances.append(copy)
        selectedInstanceIds = copies.map(copy => copy.instanceId)
        const activeIndex = sceneInstances.count - copies.length + Math.max(0, activeCopyIndex)
        selectionAnchorId = copies[0].instanceId
        activateInstanceIndex(activeIndex)
        markProjectDirty()
        statusLabel.text = copies.length > 1
            ? `Duplicated ${copies.length} objects as a group; relative positions were preserved.`
            : "Duplicated mesh instance"
    }

    function removeSelectedInstance() {
        if (selectedInstanceIndex < 0 || selectedInstanceIndex >= sceneInstances.count)
            return
        const removedIndices = selectedInstanceIndices().sort((a, b) => b - a)
        const removedCount = removedIndices.length
        const nextIndex = Math.min(removedIndices[removedIndices.length - 1], sceneInstances.count - removedCount)
        const removedGeometryKeys = []
        for (const index of removedIndices) {
            const key = sceneInstances.get(index).geometryKey
            if (removedGeometryKeys.indexOf(key) < 0)
                removedGeometryKeys.push(key)
            sceneInstances.remove(index)
        }
        for (const key of removedGeometryKeys)
            releaseUnreferencedDerivedGeometry(key)
        if (sceneInstances.count === 0) {
            clearInstanceSelection()
            modelVisible = true
            for (const key of Object.keys(derivedGeometries))
                destroyDerivedGeometry(key)
            importedGeometry.clearMesh()
            markProjectDirty()
            statusLabel.text = "Scene is empty"
            return
        }
        setInstanceSelected(Math.max(0, Math.min(nextIndex, sceneInstances.count - 1)))
        markProjectDirty()
        statusLabel.text = removedCount > 1 ? `Removed ${removedCount} mesh instances` : "Removed mesh instance"
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
            cameraRig.position = Qt.vector3d(window.viewportHorizontalOffset(), 0, 0)
            camera.position = Qt.vector3d(0, 0, 180)
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
            cameraRig.position = Qt.vector3d(window.viewportHorizontalOffset(), 0, 0)
            camera.position = Qt.vector3d(0, 0, 180)
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
        sequence: "Ctrl+Shift+A"
        context: Qt.WindowShortcut
        onActivated: selectAllInstances()
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
