// Kronos IDE — Native Aeon canvas renderer

#include "canvas_renderer.h"

#include <QPainter>
#include <QPainterPath>
#include <QPen>

#include <algorithm>
#include <cmath>

CanvasRenderer::CanvasRenderer() = default;

void CanvasRenderer::clear() {
    blocks_.clear();
    wires_.clear();
}

void CanvasRenderer::render_block(
    const std::string& id,
    double x,
    double y,
    double w,
    double h,
    const std::string& label,
    const std::string& color) {
    BlockCmd cmd;
    cmd.id = QString::fromStdString(id);
    cmd.x = x;
    cmd.y = y;
    cmd.w = w;
    cmd.h = h;
    cmd.label = QString::fromStdString(label);
    cmd.color = QColor(QString::fromStdString(color));
    if (!cmd.color.isValid()) {
        cmd.color = QColor("#58A6FF");
    }
    blocks_.append(cmd);
}

void CanvasRenderer::render_wire(double x1, double y1, double x2, double y2, bool animated) {
    wires_.append({x1, y1, x2, y2, animated});
}

void CanvasRenderer::setAnimationPhase(double phase) {
    animationPhase_ = phase;
}

QImage CanvasRenderer::rasterize(int width, int height, const QString& background) const {
    const int w = std::max(1, width);
    const int h = std::max(1, height);

    QImage image(w, h, QImage::Format_ARGB32_Premultiplied);
    image.fill(QColor(background));

    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);

    // Draw wires first so blocks stay on top.
    for (const WireCmd& wire : wires_) {
        const QPointF start(wire.x1, wire.y1);
        const QPointF end(wire.x2, wire.y2);

        QPainterPath path(start);
        path.cubicTo(
            QPointF(start.x() + 60.0, start.y()),
            QPointF(end.x() - 60.0, end.y()),
            end);

        painter.setPen(QPen(QColor("#4A7AAA"), 1.5));
        painter.drawPath(path);

        if (wire.animated) {
            constexpr int kDots = 4;
            painter.setPen(Qt::NoPen);
            painter.setBrush(QColor("#79B8FF"));
            for (int i = 0; i < kDots; ++i) {
                const double t = std::fmod(animationPhase_ + (i * 0.22), 1.0);
                const QPointF p = path.pointAtPercent(t);
                painter.drawEllipse(p, 2.1, 2.1);
            }
        }
    }

    for (const BlockCmd& block : blocks_) {
        const QRectF rect(block.x, block.y, block.w, block.h);

        QColor fill = block.color;
        fill.setAlpha(190);

        painter.setPen(QPen(block.color.lighter(120), 1.2));
        painter.setBrush(fill);
        painter.drawRoundedRect(rect, 6.0, 6.0);

        painter.setPen(QColor("#E6EDF3"));
        painter.setBrush(QColor("#E6EDF3"));
        painter.drawEllipse(QPointF(rect.left(), rect.center().y()), 2.0, 2.0);
        painter.drawEllipse(QPointF(rect.right(), rect.center().y()), 2.0, 2.0);

        painter.setPen(QColor("#E6EDF3"));
        painter.drawText(rect.adjusted(6.0, 2.0, -6.0, -2.0), Qt::AlignCenter, block.label);
    }

    painter.end();
    return image;
}
