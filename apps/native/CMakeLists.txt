cmake_minimum_required(VERSION 3.21)

project(OutlawForgeNative VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 6.6 REQUIRED COMPONENTS Quick Quick3D QuickControls2 CorePrivate Network)

qt_standard_project_setup(REQUIRES 6.6)

qt_add_executable(outlaw-forge-native
    src/main.cpp
    resources/icons.qrc
    src/MeshGeometry.h
    src/MeshGeometry.cpp
    src/SlicePlaneMapper.h
    src/SlicePlaneMapper.cpp
    src/GeometryCommandClient.h
    src/GeometryCommandClient.cpp
    src/third_party/mapbox/earcut.hpp
)

if(WIN32)
    target_sources(outlaw-forge-native PRIVATE resources/outlaw-forge.rc)
endif()

# MinGW's moc predefines probe fails when CMake is installed under a path with
# spaces. The project headers do not rely on compiler-only preprocessor state.
set_property(TARGET outlaw-forge-native PROPERTY AUTOMOC_COMPILER_PREDEFINES OFF)

qt_add_qml_module(outlaw-forge-native
    URI OutlawForge.Native
    VERSION 1.0
    QML_FILES
        qml/Main.qml
)

target_link_libraries(outlaw-forge-native PRIVATE
    Qt6::Quick
    Qt6::Quick3D
    Qt6::QuickControls2
    Qt6::CorePrivate
    Qt6::Network
)

target_include_directories(outlaw-forge-native PRIVATE src/third_party)

include(CTest)
if(BUILD_TESTING)
    find_package(Qt6 6.6 REQUIRED COMPONENTS Test)
    qt_add_executable(native-mesh-slice-tests
        tests/MeshGeometrySliceTests.cpp
        src/MeshGeometry.h
        src/MeshGeometry.cpp
        src/third_party/mapbox/earcut.hpp
    )
    set_property(TARGET native-mesh-slice-tests PROPERTY AUTOMOC_COMPILER_PREDEFINES OFF)
    target_include_directories(native-mesh-slice-tests PRIVATE src/third_party)
    target_link_libraries(native-mesh-slice-tests PRIVATE
        Qt6::Quick
        Qt6::Quick3D
        Qt6::CorePrivate
        Qt6::Test
    )
    add_test(NAME native-mesh-slice-tests
        COMMAND ${CMAKE_COMMAND} -E env
            "PATH=$<TARGET_FILE_DIR:Qt6::Test>;$ENV{PATH}"
            $<TARGET_FILE:native-mesh-slice-tests>
    )
    set_tests_properties(native-mesh-slice-tests PROPERTIES TIMEOUT 30)

    qt_add_executable(native-slice-plane-tests
        tests/SlicePlaneMapperTests.cpp
        src/SlicePlaneMapper.h
        src/SlicePlaneMapper.cpp
    )
    set_property(TARGET native-slice-plane-tests PROPERTY AUTOMOC_COMPILER_PREDEFINES OFF)
    target_link_libraries(native-slice-plane-tests PRIVATE
        Qt6::Quick
        Qt6::Test
    )
    add_test(NAME native-slice-plane-tests
        COMMAND ${CMAKE_COMMAND} -E env
            "PATH=$<TARGET_FILE_DIR:Qt6::Test>;$ENV{PATH}"
            $<TARGET_FILE:native-slice-plane-tests>
    )
    set_tests_properties(native-slice-plane-tests PROPERTIES TIMEOUT 30)

    qt_add_executable(native-geometry-command-tests
        tests/GeometryCommandClientTests.cpp
        src/SlicePlaneMapper.h
        src/SlicePlaneMapper.cpp
        src/GeometryCommandClient.h
        src/GeometryCommandClient.cpp
    )
    set_property(TARGET native-geometry-command-tests PROPERTY AUTOMOC_COMPILER_PREDEFINES OFF)
    target_link_libraries(native-geometry-command-tests PRIVATE
        Qt6::Quick
        Qt6::Network
        Qt6::Test
    )
    add_test(NAME native-geometry-command-tests
        COMMAND ${CMAKE_COMMAND} -E env
            "PATH=$<TARGET_FILE_DIR:Qt6::Test>;$ENV{PATH}"
            $<TARGET_FILE:native-geometry-command-tests>
    )
    set_tests_properties(native-geometry-command-tests PROPERTIES TIMEOUT 30)
endif()

if(WIN32)
    find_program(QT_WINDEPLOYQT_EXECUTABLE
        NAMES windeployqt windeployqt6
        HINTS "${Qt6_DIR}/../../../bin"
    )
    if(QT_WINDEPLOYQT_EXECUTABLE)
        add_custom_command(TARGET outlaw-forge-native POST_BUILD
            COMMAND "${QT_WINDEPLOYQT_EXECUTABLE}"
                --qmldir "${CMAKE_CURRENT_SOURCE_DIR}/qml"
                --compiler-runtime
                --no-translations
                --verbose 0
                "$<TARGET_FILE:outlaw-forge-native>"
            COMMENT "Deploying Qt runtime and QML dependencies beside outlaw-forge-native"
            VERBATIM
        )
    else()
        message(WARNING "windeployqt was not found. The executable will require Qt runtime DLLs on PATH.")
    endif()
endif()
