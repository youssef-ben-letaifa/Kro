// Kronos IDE — Native waveform renderer widget

#include "waveform_renderer.h"

#include <QColor>
#include <QMouseEvent>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QWheelEvent>
#include <QWidget>

#include <algorithm>
#include <limits>

namespace {
constexpr const char* kBgPrimary = "#0D1117";
constexpr const char* kBgSecondary = "#161B22";
constexpr const char* kBorder = "#30363D";
constexpr const char* kTextSecondary = "#8B949E";
constexpr const char* kAccent = "#58A6FF";
}  // namespace

WaveformView::WaveformView(std::uintptr_t parentPtr)
    : QOpenGLWidget(reinterpret_cast<QWidget*>(parentPtr)) {
    setMouseTracking(true);
    setAutoFillBackground(false);
}

void WaveformView::setData(const std::vector<double>& x, const std::vector<double>& y) {
    const auto count = std::min(x.size(), y.size());
    xData_.resize(static_cast<int>(count));
    yData_.resize(static_cast<int>(count));
    for (std::size_t i = 0; i < count; ++i) {
        xData_[static_cast<int>(i)] = x[i];
        yData_[static_cast<int>(i)] = y[i];
    }
    autoScale();
    update();
}

void WaveformView::clearData() {
    xData_.clear();
    yData_.clear();
    xMin_ = 0.0;
    xMax_ = 1.0;
    yMin_ = -1.0;
    yMax_ = 1.0;
    zoomX_ = 1.0;
    zoomY_ = 1.0;
    panX_ = 0.0;
    panY_ = 0.0;
    update();
}

void WaveformView::autoScale() {
    if (xData_.isEmpty() || yData_.isEmpty()) {
        xMin_ = 0.0;
        xMax_ = 1.0;
        yMin_ = -1.0;
        yMax_ = 1.0;
        return;
    }

    xMin_ = std::numeric_limits<double>::max();
    xMax_ = std::numeric_limits<double>::lowest();
    yMin_ = std::numeric_limits<double>::max();
    yMax_ = std::numeric_limits<double>::lowest();

    const int count = std::min(xData_.size(), yData_.size());
    for (int i = 0; i < count; ++i) {
        xMin_ = std::min(xMin_, xData_[i]);
        xMax_ = std::max(xMax_, xData_[i]);
        yMin_ = std::min(yMin_, yData_[i]);
        yMax_ = std::max(yMax_, yData_[i]);
    }

    if (xMax_ <= xMin_) {
        xMax_ = xMin_ + 1.0;
    }
    if (yMax_ <= yMin_) {
        yMax_ = yMin_ + 1.0;
    }

    const double xPad = (xMax_ - xMin_) * 0.05;
    const double yPad = (yMax_ - yMin_) * 0.08;
    xMin_ -= xPad;
    xMax_ += xPad;
    yMin_ -= yPad;
    yMax_ += yPad;

    zoomX_ = 1.0;
    zoomY_ = 1.0;
    panX_ = 0.0;
    panY_ = 0.0;
}

void WaveformView::setGridEnabled(bool enabled) {
    gridEnabled_ = enabled;
    update();
}

std::uintptr_t WaveformView::widgetPtr() const {
    return reinterpret_cast<std::uintptr_t>(const_cast<WaveformView*>(this));
}

QRectF WaveformView::plotRect() const {
    return QRectF(48.0, 20.0, std::max(1, width() - 64), std::max(1, height() - 48));
}

QPointF WaveformView::mapToPixel(double x, double y, const QRectF& rect) const {
    const double xCenter = (xMin_ + xMax_) * 0.5 + panX_;
    const double yCenter = (yMin_ + yMax_) * 0.5 + panY_;
    const double xHalf = ((xMax_ - xMin_) * 0.5) / zoomX_;
    const double yHalf = ((yMax_ - yMin_) * 0.5) / zoomY_;

    const double viewMinX = xCenter - xHalf;
    const double viewMaxX = xCenter + xHalf;
    const double viewMinY = yCenter - yHalf;
    const double viewMaxY = yCenter + yHalf;

    const double nx = (x - viewMinX) / std::max(1e-12, viewMaxX - viewMinX);
    const double ny = (y - viewMinY) / std::max(1e-12, viewMaxY - viewMinY);

    return QPointF(
        rect.left() + nx * rect.width(),
        rect.bottom() - ny * rect.height());
}

void WaveformView::paintEvent(QPaintEvent* event) {
    Q_UNUSED(event);

    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.fillRect(rect(), QColor(kBgPrimary));

    const QRectF rectArea = plotRect();
    painter.fillRect(rectArea, QColor(kBgSecondary));
    painter.setPen(QPen(QColor(kBorder), 1.0));
    painter.drawRect(rectArea);

    if (gridEnabled_) {
        painter.setPen(QPen(QColor(kBorder), 0.8, Qt::DashLine));
        constexpr int kGridLines = 10;
        for (int i = 1; i < kGridLines; ++i) {
            const double tx = rectArea.left() + (rectArea.width() * i) / kGridLines;
            const double ty = rectArea.top() + (rectArea.height() * i) / kGridLines;
            painter.drawLine(QPointF(tx, rectArea.top()), QPointF(tx, rectArea.bottom()));
            painter.drawLine(QPointF(rectArea.left(), ty), QPointF(rectArea.right(), ty));
        }
    }

    if (xData_.size() > 1 && yData_.size() > 1) {
        QPainterPath path;
        const int count = std::min(xData_.size(), yData_.size());
        path.moveTo(mapToPixel(xData_[0], yData_[0], rectArea));
        for (int i = 1; i < count; ++i) {
            path.lineTo(mapToPixel(xData_[i], yData_[i], rectArea));
        }

        painter.setPen(QPen(QColor(kAccent), 1.8));
        painter.drawPath(path);
    }

    painter.setPen(QColor(kTextSecondary));
    painter.drawText(QPointF(rectArea.left(), rectArea.top() - 4.0), "Waveform");
    painter.drawText(QPointF(rectArea.right() - 70.0, rectArea.bottom() + 18.0), "Time");
}

void WaveformView::wheelEvent(QWheelEvent* event) {
    const double factor = event->angleDelta().y() > 0 ? 1.12 : 0.9;
    zoomX_ = std::clamp(zoomX_ * factor, 0.2, 30.0);
    zoomY_ = std::clamp(zoomY_ * factor, 0.2, 30.0);
    update();
}

void WaveformView::mousePressEvent(QMouseEvent* event) {
    if (event->button() == Qt::LeftButton) {
        dragging_ = true;
        lastMousePos_ = event->pos();
    }
    QOpenGLWidget::mousePressEvent(event);
}

void WaveformView::mouseMoveEvent(QMouseEvent* event) {
    if (!dragging_) {
        QOpenGLWidget::mouseMoveEvent(event);
        return;
    }

    const QPoint delta = event->pos() - lastMousePos_;
    lastMousePos_ = event->pos();

    const QRectF area = plotRect();
    if (area.width() <= 0.0 || area.height() <= 0.0) {
        return;
    }

    const double xSpan = (xMax_ - xMin_) / std::max(1e-12, zoomX_);
    const double ySpan = (yMax_ - yMin_) / std::max(1e-12, zoomY_);
    panX_ -= (delta.x() / area.width()) * xSpan;
    panY_ += (delta.y() / area.height()) * ySpan;
    update();
}

void WaveformView::mouseReleaseEvent(QMouseEvent* event) {
    if (event->button() == Qt::LeftButton) {
        dragging_ = false;
    }
    QOpenGLWidget::mouseReleaseEvent(event);
}
