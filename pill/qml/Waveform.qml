pragma ComponentBehavior: Bound

import QtQuick

// Живая волна: строка баров, высоты гоняются от уровня входного сигнала.
// active=false -> ровная тусклая линия. Реального FFT нет — уровень + рандом
// с подъёмом к центру дают убедительную «речевую» волну почти даром.
Item {
    id: root
    property real level: 0
    property bool active: false
    property color barColor: "#ffb878"
    property int bars: 18
    implicitHeight: 40
    implicitWidth: bars * 6

    Row {
        anchors.centerIn: parent
        spacing: 3
        Repeater {
            id: rep
            model: root.bars
            Rectangle {
                width: 3
                radius: 1.5
                height: 4
                color: root.barColor
                anchors.verticalCenter: parent.verticalCenter
                opacity: root.active ? 1.0 : 0.22
                Behavior on height { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }
                Behavior on opacity { NumberAnimation { duration: 200 } }
            }
        }
    }

    Timer {
        interval: 55
        running: root.active
        repeat: true
        onTriggered: {
            var mid = (root.bars - 1) / 2
            for (var i = 0; i < rep.count; i++) {
                var b = rep.itemAt(i)
                if (!b) continue
                var center = 1 - Math.abs(i - mid) / mid       // выше к центру
                var t = 4 + root.level * 34 * (0.35 + 0.65 * Math.random()) * (0.4 + 0.6 * center)
                b.height = Math.max(4, t)
            }
        }
    }

    onActiveChanged: if (!active) {
        for (var i = 0; i < rep.count; i++) {
            var b = rep.itemAt(i)
            if (b) b.height = 4
        }
    }
}
