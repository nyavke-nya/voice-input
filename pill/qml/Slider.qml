pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects

// Слайдер под стекло: тонкий трек, акцентная заливка со свечением, ручка растёт
// при захвате (тактильный фидбек). Drag по X + клик по треку.
Item {
    id: root
    property real from: 0
    property real to: 1
    property real value: 0.5
    property color accent: "#ffb877"
    signal moved(real v)
    implicitHeight: 26

    function _valueAt(x) {
        const usable = Math.max(1, root.width - handle.width)
        const ratio = Math.min(1, Math.max(0, (x - handle.width / 2) / usable))
        return root.from + ratio * (root.to - root.from)
    }

    // трек
    Rectangle {
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width
        height: 4
        radius: 2
        color: Qt.rgba(1, 1, 1, 0.08)
        // заливка + свечение
        Rectangle {
            height: parent.height
            radius: 2
            width: handle.x + handle.width / 2
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.7) }
                GradientStop { position: 1.0; color: root.accent }
            }
        }
    }

    Rectangle {
        id: handle
        width: 16
        height: 16
        radius: 8
        color: "#ffe6cc"
        border.color: root.accent
        border.width: 2
        scale: ma.pressed ? 1.18 : 1
        anchors.verticalCenter: parent.verticalCenter
        x: {
            const span = root.to - root.from
            const ratio = span === 0 ? 0 : Math.min(1, Math.max(0, (root.value - root.from) / span))
            return ratio * (root.width - width)
        }
        Behavior on x { enabled: !ma.pressed; NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }
        Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack } }
        layer.enabled: ma.pressed
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: root.accent
            shadowBlur: 0.8
            blurMax: 24
        }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onPositionChanged: (mouse) => { if (pressed) root.moved(root._valueAt(mouse.x)) }
        onPressed: (mouse) => root.moved(root._valueAt(mouse.x))
    }
}
