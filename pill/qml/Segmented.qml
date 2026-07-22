pragma ComponentBehavior: Bound

import QtQuick

// Сегментированный переключатель со скользящим выделителем (морфинг выбора, а не
// резкая перекраска). Стекло: тонкий трек, выделитель — акцентная стеклянная
// пилюля со свечением. Press даёт scale-фидбек. options: [{label, value}].
Item {
    id: root
    property var options: []
    property var current
    property color accent: "#ffb877"
    property color ink: "#f5f2ee"
    property color sub: "#9c96a2"
    property string fontFamily: ""
    property bool slide: true   // false -> выделитель встаёт сразу (без слайда на раскрытии)
    signal selected(var value)
    implicitHeight: 38

    readonly property int pad: 4
    readonly property real segW: (width - 2 * pad) / Math.max(1, options.length)
    readonly property int curIndex: {
        for (let i = 0; i < options.length; i++)
            if (options[i].value === current) return i
        return 0
    }

    // трек
    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: Qt.rgba(1, 1, 1, 0.035)
        border.color: Qt.rgba(1, 1, 1, 0.06)
        border.width: 1
    }

    // скользящий выделитель
    Rectangle {
        id: highlight
        width: root.segW
        height: parent.height - 8
        y: 4
        x: root.pad + root.curIndex * root.segW
        radius: height / 2
        color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.16)
        border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.55)
        border.width: 1
        Behavior on x { enabled: root.slide; NumberAnimation { duration: 300; easing.type: Easing.Bezier; easing.bezierCurve: [0.32, 0.72, 0, 1, 1, 1] } }
    }
    // мягкое акцентное свечение под выделителем (тонкое кольцо — дёшево)
    Rectangle {
        width: highlight.width + 6; height: highlight.height + 6
        x: highlight.x - 3; y: highlight.y - 3
        radius: height / 2; color: "transparent"
        border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.10)
        border.width: 2
        Behavior on x { enabled: root.slide; NumberAnimation { duration: 300; easing.type: Easing.Bezier; easing.bezierCurve: [0.32, 0.72, 0, 1, 1, 1] } }
    }

    Row {
        x: root.pad
        width: root.width - 2 * root.pad
        height: parent.height
        Repeater {
            model: root.options
            Item {
                required property var modelData
                width: root.segW
                height: root.height
                property bool on: modelData.value === root.current
                Text {
                    anchors.centerIn: parent
                    text: modelData.label
                    font.family: root.fontFamily
                    font.pixelSize: 13
                    font.weight: parent.on ? Font.DemiBold : Font.Medium
                    color: parent.on ? root.accent : root.sub
                    scale: ma.pressed ? 0.94 : 1
                    Behavior on color { ColorAnimation { duration: 180 } }
                    Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
                }
                MouseArea {
                    id: ma
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.selected(modelData.value)
                }
            }
        }
    }
}
