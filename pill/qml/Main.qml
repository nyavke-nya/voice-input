pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import QtQuick.Effects

// «Пилюля» — стеклянный оверлей снизу по центру. Позицию/размер даёт правило
// Hyprland. Тема: тёмное дымчатое стекло, янтарный акцент, глянец, глубина.
// Раскрытие настроек — ЕДИНАЯ поверхность: пилюля физически вырастает вверх в
// карточку и ужимается обратно (без отдельной панели).
Window {
    id: win
    readonly property bool wantVisible: backend.appState !== "idle" || backend.expanded
    visible: wantVisible || hideTimer.running
    onWantVisibleChanged: if (!wantVisible) hideTimer.restart()
    Timer { id: hideTimer; interval: 300 }  // дать поверхности ужаться в пилюлю до unmap

    width: 400
    height: 960   // высокое прозрачное окно: место для карточки без скролла + смещение пилюли
    color: "transparent"
    // Обычно фокус остаётся в исходном поле. Только кнопка «Записать»
    // временно разрешает фокус, чтобы не читать /dev/input на Wayland.
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
           | (backend.capturing ? 0 : Qt.WindowDoesNotAcceptFocus)
    title: "Hyprland Voice Input"

    // ---- вшитые шрифты (кастом, портируемо) ----
    FontLoader { id: sansFont; source: "fonts/AdwaitaSans-Regular.ttf" }
    FontLoader { id: monoFont; source: "fonts/AdwaitaMono-Regular.ttf" }
    readonly property string ui: sansFont.name
    readonly property string mono: monoFont.name

    // ---- палитра (дымчатое стекло) ----
    readonly property color accent: "#ffb877"
    readonly property color accentDim: Qt.rgba(1, 0.72, 0.47, 0.16)
    readonly property color ink: "#f5f2ee"
    readonly property color sub: "#9c96a2"
    readonly property color danger: "#f0908c"
    readonly property color glass: Qt.rgba(0.055, 0.055, 0.075, 0.9)
    readonly property color rim: Qt.rgba(1, 1, 1, 0.10)
    readonly property color fill: Qt.rgba(1, 1, 1, 0.04)
    readonly property color fillHi: Qt.rgba(1, 1, 1, 0.09)

    // ---- кастомные easing (сильнее встроенных, приём Emil) ----
    readonly property var eDrawer: [0.32, 0.72, 0, 1, 1, 1]   // раскрытие/движение

    readonly property bool recording: backend.appState === "recording"
    readonly property bool processing: backend.appState === "processing"
    readonly property bool atTop: backend.pillPosition === "top"   // пилюля сверху/снизу экрана
    // Python передаёт этот rect в QWindow.setMask: прозрачная часть окна не
    // перехватывает клики по приложениям под высокой 960px-поверхностью.
    readonly property rect inputRegion: Qt.rect(
        Math.max(0, surface.x - 18), Math.max(0, surface.y - 18),
        Math.min(width, surface.width + 36), Math.min(height, surface.height + 36))

    // cardOpen отстаёт от expanded на кадр: окно успевает смаппиться (wantVisible
    // уже true), и морф идёт АНИМАЦИЕЙ из пилюли, а не мгновенно.
    property bool cardOpen: false
    Connections {
        target: backend
        function onExpandedChanged() {
            if (backend.expanded) openTimer.restart()
            else { win.cardOpen = false; surface.tab = 0 }
        }
        function onCapturingChanged() {
            if (backend.capturing && backend.isWayland)
                captureFocusTimer.restart()
        }
    }
    Timer { id: openTimer; interval: 16; onTriggered: win.cardOpen = true }
    Timer {
        id: captureFocusTimer
        interval: 50
        onTriggered: {
            win.requestActivate()
            hotkeyCatcher.forceActiveFocus()
        }
    }

    // прогресс раскрытия для стаггера секций (из одного значения)
    property real reveal: cardOpen ? 1 : 0
    Behavior on reveal { NumberAnimation { duration: win.cardOpen ? 280 : 160; easing.type: Easing.OutCubic } }
    function stg(i) {
        var p = (reveal - i * 0.05) / 0.42
        return p < 0 ? 0 : (p > 1 ? 1 : p)
    }

    Item {
        anchors.fill: parent

        Item {
            id: hotkeyCatcher
            anchors.fill: parent
            enabled: backend.capturing && backend.isWayland
            focus: enabled
            Keys.onPressed: function(event) {
                backend.captureQtHotkey(event.key, event.modifiers)
                event.accepted = true
            }
        }

        // ==================== ЕДИНАЯ ПОВЕРХНОСТЬ ====================
        // Свёрнута = пилюля (низ). Развёрнута = карточка: растёт вверх, бок в бок.
        Rectangle {
            id: surface
            property int tab: 0

            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: win.atTop ? parent.top : undefined
            anchors.bottom: win.atTop ? undefined : parent.bottom
            anchors.topMargin: 18
            anchors.bottomMargin: 18

            readonly property real collapsedW: win.recording ? 312 : (win.processing ? 232 : 200)
            // высота развёрнутой карточки = ровно по контенту активной вкладки -> скролла нет
            readonly property real expandedH: 138 + panes.height
            width: win.cardOpen ? (parent.width - 24) : collapsedW
            height: win.cardOpen ? expandedH : 58
            radius: win.cardOpen ? 26 : 29
            antialiasing: true
            color: win.glass
            border.width: win.cardOpen ? 1 : 1.5
            border.color: win.cardOpen ? win.rim
                          : ((win.recording || win.processing) ? Qt.rgba(win.accent.r,win.accent.g,win.accent.b,0.85) : win.rim)
            opacity: (win.recording || win.processing || backend.expanded || win.cardOpen) ? 1 : 0

            Behavior on width { NumberAnimation { duration: win.cardOpen ? 260 : 200; easing.type: Easing.Bezier; easing.bezierCurve: win.eDrawer } }
            Behavior on height { NumberAnimation { duration: win.cardOpen ? 260 : 200; easing.type: Easing.Bezier; easing.bezierCurve: win.eDrawer } }
            Behavior on radius { NumberAnimation { duration: 240; easing.type: Easing.Bezier; easing.bezierCurve: win.eDrawer } }
            Behavior on border.color { ColorAnimation { duration: 220 } }
            Behavior on opacity { NumberAnimation { duration: 260 } }

            // глубина / свечение — один эффект, параметры от состояния
            layer.enabled: win.cardOpen || win.recording || win.processing
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: win.cardOpen ? "#000000" : win.accent
                shadowVerticalOffset: win.cardOpen ? 8 : 0
                shadowBlur: 1.0
                blurMax: win.cardOpen ? 28 : (win.recording ? 44 : 22)
                shadowOpacity: win.cardOpen ? 0.5 : (win.recording ? 0.6 : 0.3)
            }

            // глянцевый верхний блик
            Rectangle {
                anchors.fill: parent; radius: parent.radius
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.06) }
                    GradientStop { position: win.cardOpen ? 0.28 : 0.55; color: Qt.rgba(1, 1, 1, 0.0) }
                    GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, win.cardOpen ? 0.06 : 0.0) }
                }
            }

            // ============ СОДЕРЖИМОЕ КАРТОЧКИ (проявляется) ============
            Item {
                id: cardContent
                anchors.fill: parent
                opacity: win.cardOpen ? 1 : 0
                visible: opacity > 0.01
                Behavior on opacity { NumberAnimation { duration: win.cardOpen ? 240 : 150; easing.type: Easing.OutCubic } }

                // --- заголовок ---
                Item {
                    id: header
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 20 }
                    height: 26
                    Text {
                        id: brand
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Voice Input"; color: win.ink; font.family: win.ui; font.pixelSize: 19; font.weight: Font.DemiBold
                    }
                    Text {
                        anchors.left: brand.right; anchors.leftMargin: 8; anchors.baseline: brand.baseline
                        text: "v" + backend.version; color: win.sub; font.family: win.mono; font.pixelSize: 10
                    }
                    Rectangle {
                        id: closeBtn
                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        width: 28; height: 28; radius: 14
                        color: closeMa.containsMouse ? win.fillHi : "transparent"
                        scale: closeMa.pressed ? 0.9 : 1
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Behavior on scale { NumberAnimation { duration: 120 } }
                        Icon { anchors.centerIn: parent; name: "close"; width: 14; height: 14
                            color: closeMa.containsMouse ? win.ink : win.sub; stroke: 1.6 }
                        MouseArea { id: closeMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: backend.expanded = false }
                    }
                }

                // --- вкладки со скользящим выделителем ---
                Item {
                    id: tabs
                    anchors { left: parent.left; right: parent.right; top: header.bottom; leftMargin: 18; rightMargin: 18; topMargin: 16 }
                    height: 38
                    readonly property real segW: (width - 8) / 3
                    Rectangle { anchors.fill: parent; radius: height / 2; color: win.fill; border.color: Qt.rgba(1,1,1,0.05); border.width: 1 }
                    Rectangle {
                        id: tabHi
                        width: tabs.segW; height: parent.height - 8; y: 4
                        x: 4 + surface.tab * tabs.segW
                        radius: height / 2
                        color: win.accentDim
                        border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.5); border.width: 1
                        Behavior on x { NumberAnimation { duration: 300; easing.type: Easing.Bezier; easing.bezierCurve: win.eDrawer } }
                    }
                    Row {
                        x: 4; width: parent.width - 8; height: parent.height
                        Repeater {
                            model: [{ t: "Настройки", i: 0 }, { t: "Статистика", i: 1 }, { t: "История", i: 2 }]
                            Item {
                                required property var modelData
                                width: tabs.segW; height: tabs.height
                                property bool on: surface.tab === modelData.i
                                Text {
                                    anchors.centerIn: parent; text: modelData.t
                                    font.family: win.ui; font.pixelSize: 13; font.weight: parent.on ? Font.DemiBold : Font.Medium
                                    color: parent.on ? win.accent : win.sub
                                    scale: tabMa.pressed ? 0.95 : 1
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                    Behavior on scale { NumberAnimation { duration: 120 } }
                                }
                                MouseArea { id: tabMa; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: surface.tab = modelData.i }
                            }
                        }
                    }
                }

                // --- панели: высота карточки подстраивается под контент, скролла нет ---
                Column {
                    id: panes
                    anchors { left: parent.left; right: parent.right; top: tabs.bottom
                              leftMargin: 20; rightMargin: 20; topMargin: 18 }

                        // ==================== НАСТРОЙКИ ====================
                        Column {
                            id: settingsPane
                            visible: surface.tab === 0
                            width: parent.width; spacing: 18

                            // Горячая клавиша (idx 0)
                            Column {
                                width: parent.width; spacing: 8
                                opacity: win.stg(0); transform: Translate { y: (1 - win.stg(0)) * 14 }
                                Text { text: "ГОРЯЧАЯ КЛАВИША"; color: win.sub; font.family: win.ui; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 1.5 }
                                Row {
                                    width: parent.width; spacing: 8
                                    Rectangle {
                                        width: parent.width - 108; height: 38; radius: 12
                                        color: win.fill; border.color: backend.capturing ? win.accent : Qt.rgba(1,1,1,0.06); border.width: 1
                                        Behavior on border.color { ColorAnimation { duration: 180 } }
                                        Text {
                                            anchors.fill: parent; anchors.margins: 12; verticalAlignment: Text.AlignVCenter
                                            text: backend.capturing ? "нажмите комбинацию…" : backend.hotkey.toUpperCase()
                                            color: backend.capturing ? win.accent : win.ink; font.family: win.mono; font.pixelSize: 13
                                        }
                                    }
                                    Rectangle {
                                        width: 100; height: 38; radius: 12
                                        color: backend.capturing ? win.accent : win.fillHi
                                        border.color: backend.capturing ? win.accent : Qt.rgba(1,1,1,0.07); border.width: 1
                                        scale: recMa.pressed ? 0.96 : 1
                                        Behavior on color { ColorAnimation { duration: 180 } }
                                        Behavior on scale { NumberAnimation { duration: 120 } }
                                        Text { anchors.centerIn: parent; text: backend.capturing ? "…" : "Записать"; color: backend.capturing ? "#1a1206" : win.ink; font.family: win.ui; font.pixelSize: 13; font.weight: Font.Medium }
                                        MouseArea { id: recMa; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: backend.captureHotkey() }
                                    }
                                }
                                Text { width: parent.width; wrapMode: Text.WordWrap; text: "триггер — нативный bind Hyprland, обновляется автоматически"; color: Qt.rgba(win.sub.r,win.sub.g,win.sub.b,0.75); font.family: win.ui; font.pixelSize: 11 }
                            }

                            // Язык (idx 1)
                            Column {
                                width: parent.width; spacing: 8
                                opacity: win.stg(1); transform: Translate { y: (1 - win.stg(1)) * 14 }
                                Text { text: "ЯЗЫК ВЫВОДА"; color: win.sub; font.family: win.ui; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 1.5 }
                                Segmented {
                                    width: parent.width; accent: win.accent; ink: win.ink; sub: win.sub; fontFamily: win.ui; slide: win.reveal > 0.98
                                    options: [{label: "Русский", value: "ru"}, {label: "English", value: "en"}, {label: "Как в речи", value: "auto"}]
                                    current: backend.language
                                    onSelected: (v) => backend.language = v
                                }
                                Text {
                                    width: parent.width; wrapMode: Text.WordWrap
                                    text: backend.language === "en"
                                          ? "English переводит речь с любого поддерживаемого языка"
                                          : (backend.language === "auto" ? "сохраняет язык исходной речи" : "распознаёт русскую речь без перевода")
                                    color: Qt.rgba(win.sub.r,win.sub.g,win.sub.b,0.75); font.family: win.ui; font.pixelSize: 11
                                }
                            }

                            // Модель (idx 2)
                            Column {
                                width: parent.width; spacing: 8
                                opacity: win.stg(2); transform: Translate { y: (1 - win.stg(2)) * 14 }
                                Text { text: "МОДЕЛЬ  ·  СКОРОСТЬ ↔ ТОЧНОСТЬ"; color: win.sub; font.family: win.ui; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 1.5 }
                                Segmented {
                                    width: parent.width; accent: win.accent; ink: win.ink; sub: win.sub; fontFamily: win.ui; slide: win.reveal > 0.98
                                    options: [{label: "Tiny", value: "tiny"}, {label: "Small", value: "small"}, {label: "Medium", value: "medium"}, {label: "Large", value: "large"}]
                                    current: backend.model
                                    onSelected: (v) => backend.model = v
                                }
                                Text {
                                    visible: backend.model === "large"
                                    text: "Large-v3 — максимум точности; первый запуск качает ~3 ГБ"
                                    color: Qt.rgba(win.sub.r,win.sub.g,win.sub.b,0.75); font.family: win.ui; font.pixelSize: 11; wrapMode: Text.WordWrap; width: parent.width
                                }
                            }

                            // Словарь (idx 3)
                            Column {
                                width: parent.width; spacing: 8
                                opacity: win.stg(3); transform: Translate { y: (1 - win.stg(3)) * 14 }
                                Text { text: "СЛОВАРИ"; color: win.sub; font.family: win.ui; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 1.5 }
                                Row {
                                    width: parent.width; spacing: 8
                                    Repeater {
                                        model: [{ name: "profanity", label: "Мат" }, { name: "it", label: "IT" }]
                                        Rectangle {
                                            id: chip
                                            required property var modelData
                                            width: (parent.width - 8) / 2; height: 38; radius: 12
                                            property bool selected: backend.packs.indexOf(modelData.name) >= 0
                                            color: selected ? win.accentDim : win.fill
                                            border.color: selected ? Qt.rgba(win.accent.r,win.accent.g,win.accent.b,0.5) : Qt.rgba(1,1,1,0.06); border.width: 1
                                            scale: chipMa.pressed ? 0.96 : 1
                                            Behavior on color { ColorAnimation { duration: 180 } }
                                            Behavior on border.color { ColorAnimation { duration: 180 } }
                                            Behavior on scale { NumberAnimation { duration: 120 } }
                                            Row {
                                                anchors.centerIn: parent; spacing: 6
                                                Icon { anchors.verticalCenter: parent.verticalCenter; visible: chip.selected; name: "check"; width: 13; height: 13; color: win.accent; stroke: 1.8 }
                                                Text { anchors.verticalCenter: parent.verticalCenter; text: modelData.label; color: chip.selected ? win.accent : win.sub; font.family: win.ui; font.pixelSize: 13; font.weight: chip.selected ? Font.DemiBold : Font.Medium }
                                            }
                                            MouseArea { id: chipMa; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: backend.togglePack(modelData.name) }
                                        }
                                    }
                                }
                            }

                            // Микрофон (idx 4)
                            Column {
                                width: parent.width; spacing: 11
                                opacity: win.stg(4); transform: Translate { y: (1 - win.stg(4)) * 14 }
                                Text { text: "МИКРОФОН"; color: win.sub; font.family: win.ui; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 1.5 }
                                Row {
                                    width: parent.width; spacing: 8
                                    Rectangle {
                                        width: 38; height: 38; radius: 12; color: win.fill; border.color: Qt.rgba(1,1,1,0.06); border.width: 1
                                        scale: prevMa.pressed ? 0.92 : 1; Behavior on scale { NumberAnimation { duration: 110 } }
                                        Icon { anchors.centerIn: parent; name: "chevronLeft"; width: 16; height: 16; color: win.ink; stroke: 1.7 }
                                        MouseArea { id: prevMa; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: backend.deviceIndex = Math.max(0, backend.deviceIndex - 1) }
                                    }
                                    Rectangle {
                                        width: parent.width - 92; height: 38; radius: 12; color: win.fill; border.color: Qt.rgba(1,1,1,0.06); border.width: 1
                                        Row {
                                            anchors.centerIn: parent; spacing: 7; width: parent.width - 20
                                            Icon { anchors.verticalCenter: parent.verticalCenter; name: "mic"; width: 15; height: 15; color: win.accent; stroke: 1.5 }
                                            Text { width: parent.width - 22; anchors.verticalCenter: parent.verticalCenter; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; text: backend.devices[backend.deviceIndex]; color: win.ink; font.family: win.ui; font.pixelSize: 12 }
                                        }
                                    }
                                    Rectangle {
                                        width: 38; height: 38; radius: 12; color: win.fill; border.color: Qt.rgba(1,1,1,0.06); border.width: 1
                                        scale: nextMa.pressed ? 0.92 : 1; Behavior on scale { NumberAnimation { duration: 110 } }
                                        Icon { anchors.centerIn: parent; name: "chevronRight"; width: 16; height: 16; color: win.ink; stroke: 1.7 }
                                        MouseArea { id: nextMa; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: backend.deviceIndex = Math.min(backend.devices.length - 1, backend.deviceIndex + 1) }
                                    }
                                }
                                Item {
                                    width: parent.width; height: 26
                                    Text { anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; text: "Чувствительность VAD"; color: win.sub; font.family: win.ui; font.pixelSize: 12 }
                                    Slider {
                                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width * 0.46; accent: win.accent
                                        from: 0; to: 1; value: backend.vadSensitivity
                                        onMoved: (v) => backend.vadSensitivity = v
                                    }
                                }
                                Item {
                                    width: parent.width; height: 26
                                    Text { anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; text: "Пауза до вставки"; color: win.sub; font.family: win.ui; font.pixelSize: 12 }
                                    Text { anchors.left: parent.left; anchors.leftMargin: 132; anchors.verticalCenter: parent.verticalCenter; text: backend.silenceMs + " мс"; color: win.accent; font.family: win.mono; font.pixelSize: 11 }
                                    Slider {
                                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width * 0.4; accent: win.accent
                                        from: 200; to: 1000; value: backend.silenceMs
                                        onMoved: (v) => backend.silenceMs = Math.round(v)
                                    }
                                }
                            }

                            // Метод ввода (idx 5)
                            Column {
                                width: parent.width; spacing: 8
                                opacity: win.stg(5); transform: Translate { y: (1 - win.stg(5)) * 14 }
                                Text { text: "МЕТОД ВВОДА"; color: win.sub; font.family: win.ui; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 1.5 }
                                Segmented {
                                    width: parent.width; accent: win.accent; ink: win.ink; sub: win.sub; fontFamily: win.ui; slide: win.reveal > 0.98
                                    options: [{label: "Клавиатура", value: "keyboard"}, {label: "Буфер обмена", value: "clipboard"}]
                                    current: backend.inputMethod
                                    onSelected: (v) => backend.inputMethod = v
                                }
                            }

                            // Положение пилюли по вертикали (idx 6)
                            Column {
                                width: parent.width; spacing: 8
                                opacity: win.stg(6); transform: Translate { y: (1 - win.stg(6)) * 14 }
                                Text { text: "ПОЛОЖЕНИЕ ПИЛЮЛИ"; color: win.sub; font.family: win.ui; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 1.5 }
                                Segmented {
                                    width: parent.width; accent: win.accent; ink: win.ink; sub: win.sub; fontFamily: win.ui; slide: win.reveal > 0.98
                                    options: [{label: "Снизу", value: "bottom"}, {label: "Сверху", value: "top"}]
                                    current: backend.pillPosition
                                    onSelected: (v) => backend.pillPosition = v
                                }
                            }

                            // Выйти (idx 7)
                            Item {
                                width: parent.width; height: 42
                                opacity: win.stg(7); transform: Translate { y: (1 - win.stg(7)) * 14 }
                                Rectangle {
                                    anchors.fill: parent; radius: 12
                                    color: quitMa.containsMouse ? Qt.rgba(0.94,0.56,0.53,0.12) : win.fill
                                    border.color: Qt.rgba(0.94,0.56,0.53,0.28); border.width: 1
                                    scale: quitMa.pressed ? 0.98 : 1
                                    Behavior on color { ColorAnimation { duration: 150 } }
                                    Behavior on scale { NumberAnimation { duration: 120 } }
                                    Row {
                                        anchors.centerIn: parent; spacing: 7
                                        Icon { anchors.verticalCenter: parent.verticalCenter; name: "power"; width: 14; height: 14; color: win.danger; stroke: 1.6 }
                                        Text { anchors.verticalCenter: parent.verticalCenter; text: "Выйти"; color: win.danger; font.family: win.ui; font.pixelSize: 13; font.weight: Font.Medium }
                                    }
                                    MouseArea { id: quitMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: backend.quitApp() }
                                }
                            }
                        }

                        // ==================== СТАТИСТИКА ====================
                        Column {
                            id: statsPane
                            visible: surface.tab === 1
                            width: parent.width; spacing: 14

                            component StatRow: Item {
                                property string label: ""
                                property string value: ""
                                width: parent ? parent.width : 0
                                height: 24
                                Text { anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; text: parent.label; color: win.sub; font.family: win.ui; font.pixelSize: 13 }
                                Text { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; text: parent.value; color: win.ink; font.family: win.mono; font.pixelSize: 14; font.weight: Font.DemiBold }
                            }

                            Text { text: "ПОСЛЕДНЯЯ ДИКТОВКА"; color: win.sub; font.family: win.ui; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 1.5 }
                            StatRow { label: "Время обработки"; value: backend.stats.lastProcMs + " мс" }
                            StatRow { label: "Символов"; value: "" + backend.stats.lastChars }
                            StatRow { label: "Букв"; value: "" + backend.stats.lastLetters }
                            StatRow { label: "Слов"; value: "" + backend.stats.lastWords }
                            StatRow { label: "Длина аудио"; value: (backend.stats.lastAudioMs / 1000).toFixed(1) + " с" }

                            Rectangle { width: parent.width; height: 1; color: Qt.rgba(1,1,1,0.06) }

                            Text { text: "ВСЕГО"; color: win.sub; font.family: win.ui; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 1.5 }
                            StatRow { label: "Диктовок"; value: "" + backend.stats.count }
                            StatRow { label: "Символов"; value: "" + backend.stats.chars }
                            StatRow { label: "Букв"; value: "" + backend.stats.letters }
                            StatRow { label: "Слов"; value: "" + backend.stats.words }
                            StatRow { label: "Аудио"; value: backend.stats.audioSec + " с" }
                            StatRow { label: "Ср. обработка"; value: backend.stats.avgProcMs + " мс" }

                            Item { width: parent.width; height: 2 }
                            Rectangle {
                                width: parent.width; height: 40; radius: 12
                                color: resetMa.containsMouse ? win.fillHi : win.fill; border.color: Qt.rgba(1,1,1,0.06); border.width: 1
                                scale: resetMa.pressed ? 0.98 : 1
                                Behavior on color { ColorAnimation { duration: 150 } }
                                Behavior on scale { NumberAnimation { duration: 120 } }
                                Row {
                                    anchors.centerIn: parent; spacing: 7
                                    Icon { anchors.verticalCenter: parent.verticalCenter; name: "reset"; width: 14; height: 14; color: win.sub; stroke: 1.6 }
                                    Text { anchors.verticalCenter: parent.verticalCenter; text: "Сбросить статистику"; color: win.sub; font.family: win.ui; font.pixelSize: 13 }
                                }
                                MouseArea { id: resetMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: backend.resetStats() }
                            }
                        }

                        // ==================== ИСТОРИЯ ====================
                        Column {
                            id: historyPane
                            visible: surface.tab === 2
                            width: parent.width; spacing: 8

                            Text { text: "ПОСЛЕДНИЕ ДИКТОВКИ  ·  КЛИК КОПИРУЕТ"; color: win.sub; font.family: win.ui; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 1.5 }
                            Text {
                                visible: backend.history.length === 0
                                text: "пока пусто — надиктуй что-нибудь"; color: win.sub; font.family: win.ui; font.pixelSize: 13
                            }
                            Repeater {
                                model: backend.history
                                Rectangle {
                                    required property var modelData
                                    required property int index
                                    width: historyPane.width; height: 34; radius: 11
                                    color: hma.containsMouse ? win.fillHi : win.fill; border.color: Qt.rgba(1,1,1,0.05); border.width: 1
                                    scale: hma.pressed ? 0.98 : 1
                                    Behavior on color { ColorAnimation { duration: 130 } }
                                    Behavior on scale { NumberAnimation { duration: 110 } }
                                    Text {
                                        id: htime
                                        anchors.left: parent.left; anchors.leftMargin: 12; anchors.verticalCenter: parent.verticalCenter
                                        text: modelData.time; color: win.accent; font.family: win.mono; font.pixelSize: 11
                                    }
                                    Text {
                                        anchors.left: htime.right; anchors.leftMargin: 10; anchors.right: parent.right; anchors.rightMargin: 12
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: modelData.text; color: win.ink; font.family: win.ui; font.pixelSize: 12; elide: Text.ElideRight
                                    }
                                    MouseArea { id: hma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: backend.copyHistory(index) }
                                }
                            }
                        }
                }
            }
            // ↑ panes Column / cardContent Item

            // ============ СОДЕРЖИМОЕ ПИЛЮЛИ (низ, гаснет при раскрытии) ============
            Item {
                id: pillContent
                anchors.left: parent.left; anchors.right: parent.right
                anchors.top: win.atTop ? parent.top : undefined
                anchors.bottom: win.atTop ? undefined : parent.bottom
                height: 58
                opacity: win.cardOpen ? 0 : 1
                visible: opacity > 0.01
                Behavior on opacity { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

                // индикатор-точка
                Rectangle {
                    id: dot
                    anchors.left: parent.left; anchors.leftMargin: 22; anchors.verticalCenter: parent.verticalCenter
                    width: 10; height: 10; radius: 5
                    color: win.recording ? win.accent : (win.processing ? "#ffcf99" : Qt.rgba(1,1,1,0.25))
                    Behavior on color { ColorAnimation { duration: 200 } }
                }
                SequentialAnimation {
                    running: win.recording; loops: Animation.Infinite
                    NumberAnimation { target: dot; property: "scale"; to: 1.55; duration: 550; easing.type: Easing.InOutSine }
                    NumberAnimation { target: dot; property: "scale"; to: 1.0; duration: 550; easing.type: Easing.InOutSine }
                    onStopped: dot.scale = 1
                }
                SequentialAnimation {
                    running: win.processing; loops: Animation.Infinite
                    NumberAnimation { target: dot; property: "opacity"; to: 0.3; duration: 420 }
                    NumberAnimation { target: dot; property: "opacity"; to: 1.0; duration: 420 }
                    onStopped: dot.opacity = 1
                }

                // центр: волна / статус
                Item {
                    anchors.left: dot.right; anchors.leftMargin: 12
                    anchors.right: gear.left; anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    height: parent.height
                    Waveform {
                        anchors.centerIn: parent
                        width: Math.min(parent.width, implicitWidth)
                        active: win.recording
                        level: backend.level
                        barColor: win.accent
                        opacity: win.processing ? 0 : 1
                        Behavior on opacity { NumberAnimation { duration: 150 } }
                    }
                    Text {
                        anchors.centerIn: parent
                        text: "Распознаю…"
                        color: win.ink; font.family: win.ui; font.pixelSize: 13
                        opacity: win.processing ? 1 : 0
                        Behavior on opacity { NumberAnimation { duration: 150 } }
                    }
                }

                // шестерёнка
                Rectangle {
                    id: gear
                    anchors.right: parent.right; anchors.rightMargin: 13; anchors.verticalCenter: parent.verticalCenter
                    width: 34; height: 34; radius: 17
                    color: gearMa.containsMouse ? win.fillHi : "transparent"
                    scale: gearMa.pressed ? 0.9 : 1
                    Behavior on color { ColorAnimation { duration: 150 } }
                    Behavior on scale { NumberAnimation { duration: 120 } }
                    Icon {
                        anchors.centerIn: parent; name: "gear"; width: 18; height: 18; stroke: 1.5
                        color: gearMa.containsMouse ? win.ink : win.sub
                    }
                    MouseArea { id: gearMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: backend.expanded = true }
                }

                // клик по телу пилюли — старт/стоп
                MouseArea {
                    id: pillMa
                    anchors.left: parent.left; anchors.right: gear.left
                    anchors.top: parent.top; anchors.bottom: parent.bottom
                    cursorShape: Qt.PointingHandCursor
                    onClicked: backend.toggle()
                }
            }
        }
    }
}
