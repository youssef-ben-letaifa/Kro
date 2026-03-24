// Kronos IDE — Native Aeon canvas renderer
#pragma once

#include <QColor>
#include <QImage>
#include <QObject>
#include <QString>
#include <QVector>

#include <cstdint>
#include <string>

class CanvasRenderer final : public QObject {
public:
    CanvasRenderer();

    void clear();
    void render_block(
        const std::string& id,
        double x,
        double y,
        double w,
        double h,
        const std::string& label,
        const std::string& color);
    void render_wire(double x1, double y1, double x2, double y2, bool animated);

    void setAnimationPhase(double phase);
    QImage rasterize(int width, int height, const QString& background) const;

private:
    struct BlockCmd {
        QString id;
        double x;
        double y;
        double w;
        double h;
        QString label;
        QColor color;
    };

    struct WireCmd {
        double x1;
        double y1;
        double x2;
        double y2;
        bool animated;
    };

    QVector<BlockCmd> blocks_;
    QVector<WireCmd> wires_;
    double animationPhase_ = 0.0;
};
