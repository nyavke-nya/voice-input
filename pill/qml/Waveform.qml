pragma ComponentBehavior: Bound

import QtQuick

// Живая волна: фиксированные бары масштабируются по Y от уровня микрофона.
// Transform не пересчитывает layout на каждом аудиокадре, поэтому волна остаётся
// плавной даже во время тяжёлого распознавания.
Item {
    id: root
    property real level: 0
    property bool active: false
    property color barColor: "#ffb878"
    property int bars: 18
    implicitHeight: 18
    implicitWidth: bars * 4 - 2

    Row {
        anchors.centerIn: parent
        spacing: 2
        Repeater {
            id: rep
            model: root.bars
            Rectangle {
                id: bar
                property real amplitude: 0.22
                width: 2
                radius: 1
                height: 16
                color: root.barColor
                anchors.verticalCenter: parent.verticalCenter
                opacity: root.active ? 1.0 : 0.22
                transform: Scale {
                    origin.x: bar.width / 2
                    origin.y: bar.height / 2
                    xScale: 1
                    yScale: bar.amplitude
                }
                Behavior on amplitude { NumberAnimation { duration: 70; easing.type: Easing.OutCubic } }
                Behavior on opacity { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
            }
        }
    }

    Timer {
        interval: 65
        running: root.active
        repeat: true
        onTriggered: {
            var mid = (root.bars - 1) / 2
            for (var i = 0; i < rep.count; i++) {
                var b = rep.itemAt(i)
                if (!b) continue
                var center = root.bars === 1 ? 1 : 1 - Math.abs(i - mid) / mid
                var energy = root.level * (0.35 + 0.65 * Math.random()) * (0.45 + 0.55 * center)
                b.amplitude = Math.max(0.22, Math.min(1, 0.22 + energy))
            }
        }
    }

    onActiveChanged: if (!active) {
        for (var i = 0; i < rep.count; i++) {
            var b = rep.itemAt(i)
            if (b) b.amplitude = 0.22
        }
    }
}
