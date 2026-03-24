// Kronos IDE — Native waveform renderer widget
#pragma once

#include <QOpenGLWidget>
#include <QPoint>
#include <QRectF>
#include <QVector>

#include <cstdint>
#include <vector>

class WaveformView final : public QOpenGLWidget {
public:
    explicit WaveformView(std::uintptr_t parentPtr = 0);

    void setData(const std::vector<double>& x, const std::vector<double>& y);
    void clearData();
    void autoScale();
    void setGridEnabled(bool enabled);

    std::uintptr_t widgetPtr() const;

protected:
    void paintEvent(QPaintEvent* event) override;
    void wheelEvent(QWheelEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;

private:
    QVector<double> xData_;
    QVector<double> yData_;
    bool gridEnabled_ = true;

    double xMin_ = 0.0;
    double xMax_ = 1.0;
    double yMin_ = -1.0;
    double yMax_ = 1.0;

    double zoomX_ = 1.0;
    double zoomY_ = 1.0;
    double panX_ = 0.0;
    double panY_ = 0.0;

    bool dragging_ = false;
    QPoint lastMousePos_;

    QRectF plotRect() const;
    QPointF mapToPixel(double x, double y, const QRectF& rect) const;
};
