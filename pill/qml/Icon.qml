pragma ComponentBehavior: Bound

import QtQuick

// Кастомные векторные иконки, нарисованные штрихом на Canvas (QtQuick.Shapes нет
// в этой сборке PySide6). Тонкие, скруглённые концы — под glass-стиль. Один
// компонент, имя иконки в `name`. Перерисовка на смене цвета/размера/имени.
Canvas {
    id: root
    property string name: ""
    property color color: "#ffffff"
    property real stroke: 1.6
    width: 18
    height: 18
    antialiasing: true
    renderStrategy: Canvas.Cooperative

    onColorChanged: requestPaint()
    onNameChanged: requestPaint()
    onStrokeChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onVisibleChanged: if (visible) requestPaint()   // Canvas красится асинхронно — не оставлять пустым при показе
    Component.onCompleted: requestPaint()

    onPaint: {
        const ctx = getContext("2d")
        ctx.reset()
        ctx.strokeStyle = root.color
        ctx.fillStyle = root.color
        ctx.lineWidth = root.stroke
        ctx.lineCap = "round"
        ctx.lineJoin = "round"
        const w = width, h = height, cx = w / 2, cy = h / 2
        const m = Math.max(3, w * 0.28)

        if (name === "close") {
            ctx.beginPath()
            ctx.moveTo(m, m); ctx.lineTo(w - m, h - m)
            ctx.moveTo(w - m, m); ctx.lineTo(m, h - m)
            ctx.stroke()

        } else if (name === "gear") {
            const teeth = 8, ro = w * 0.42, ri = w * 0.30, hole = w * 0.15
            ctx.beginPath()
            for (let i = 0; i <= teeth * 2; i++) {
                const a = (i / (teeth * 2)) * Math.PI * 2 - Math.PI / 2
                const r = (i % 2 === 0) ? ro : ri
                const x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r
                i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
            }
            ctx.closePath(); ctx.stroke()
            ctx.beginPath(); ctx.arc(cx, cy, hole, 0, Math.PI * 2); ctx.stroke()

        } else if (name === "chevronLeft" || name === "chevronRight") {
            const dir = name === "chevronLeft" ? -1 : 1
            ctx.beginPath()
            ctx.moveTo(cx - dir * w * 0.12, m)
            ctx.lineTo(cx + dir * w * 0.16, cy)
            ctx.lineTo(cx - dir * w * 0.12, h - m)
            ctx.stroke()

        } else if (name === "mic") {
            const bw = w * 0.22
            ctx.beginPath()  // капсула микрофона
            ctx.moveTo(cx - bw, h * 0.20 + bw)
            ctx.arc(cx, h * 0.20 + bw, bw, Math.PI, 0)
            ctx.lineTo(cx + bw, h * 0.46)
            ctx.arc(cx, h * 0.46, bw, 0, Math.PI)
            ctx.closePath(); ctx.stroke()
            ctx.beginPath()  // дужка + стойка
            ctx.arc(cx, h * 0.46, w * 0.34, 0.15 * Math.PI, 0.85 * Math.PI)
            ctx.stroke()
            ctx.beginPath()
            ctx.moveTo(cx, h * 0.46 + w * 0.34); ctx.lineTo(cx, h - m * 0.7)
            ctx.moveTo(cx - w * 0.16, h - m * 0.7); ctx.lineTo(cx + w * 0.16, h - m * 0.7)
            ctx.stroke()

        } else if (name === "check") {
            ctx.beginPath()
            ctx.moveTo(m, cy + h * 0.02)
            ctx.lineTo(cx - w * 0.06, h - m)
            ctx.lineTo(w - m, m + h * 0.04)
            ctx.stroke()

        } else if (name === "reset") {  // круговая стрелка
            ctx.beginPath()
            ctx.arc(cx, cy, w * 0.32, -0.4 * Math.PI, 1.35 * Math.PI)
            ctx.stroke()
            const ax = cx + Math.cos(-0.4 * Math.PI) * w * 0.32
            const ay = cy + Math.sin(-0.4 * Math.PI) * w * 0.32
            ctx.beginPath()
            ctx.moveTo(ax - w * 0.14, ay - w * 0.02)
            ctx.lineTo(ax, ay); ctx.lineTo(ax + w * 0.02, ay - w * 0.16)
            ctx.stroke()

        } else if (name === "power") {  // выход
            ctx.beginPath()
            ctx.arc(cx, cy + h * 0.03, w * 0.30, -0.35 * Math.PI, 1.35 * Math.PI)
            ctx.stroke()
            ctx.beginPath()
            ctx.moveTo(cx, m * 0.7); ctx.lineTo(cx, cy - h * 0.04)
            ctx.stroke()
        }
    }
}
