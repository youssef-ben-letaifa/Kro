"""Autonomous Driving Toolbox window (Aeon-aligned design language)."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np


def _ensure_matplotlib_config_dir() -> None:
    if os.environ.get("MPLCONFIGDIR"):
        return
    candidates = [Path.home() / ".cache" / "matplotlib", Path("/tmp") / "kronos-mpl"]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            os.environ["MPLCONFIGDIR"] = str(candidate)
            return
        except OSError:
            continue


_ensure_matplotlib_config_dir()
import matplotlib

matplotlib.use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from kronos.ui.theme.design_tokens import get_colors
from kronos.ui.theme.fluent_icons import icon_for
from kronos.ui.theme.mpl_defaults import apply_mpl_defaults

from .core import AutonomousDrivingSimulation
from .core.common import SimulationFrame, VehicleState
from .opengl_view import OpenGLHighwayView

apply_mpl_defaults()


class _RibbonGroup(QFrame):
    """Simple ribbon-like section used in the toolbox header."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("ribbon_group")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 4)
        layout.setSpacing(2)

        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(4)
        self.grid.setVerticalSpacing(4)
        layout.addLayout(self.grid, 1)
        self._has_primary = False
        self._secondary_index = 0
        self._max_col = 0

        label = QLabel(title)
        label.setObjectName("ribbon_group_title")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

    @staticmethod
    def _compactify(button: QToolButton) -> None:
        button.setObjectName("ribbon_action_compact")
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIconSize(QSize(16, 16))
        button.setMinimumSize(116, 28)
        button.setMaximumHeight(28)

    def add_widget(self, widget: QWidget) -> None:
        if isinstance(widget, QToolButton):
            if widget.objectName() == "ribbon_action_primary" and not self._has_primary:
                self.grid.addWidget(widget, 0, 0, 2, 1)
                self._has_primary = True
                self._max_col = max(self._max_col, 0)
                return
            if widget.objectName() == "ribbon_action_primary":
                self._compactify(widget)

        start_col = 1 if self._has_primary else 0
        row = self._secondary_index % 2
        col = start_col + (self._secondary_index // 2)
        self.grid.addWidget(widget, row, col)
        self._secondary_index += 1
        self._max_col = max(self._max_col, col)

    def finalize(self) -> None:
        self.grid.setColumnStretch(self._max_col + 1, 1)


class AutonomousDrivingToolboxWindow(QMainWindow):
    """Main autonomous-driving design and simulation environment."""

    closed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Autonomous Driving Toolbox")
        self.setMinimumSize(1380, 860)

        self._theme = "dark"
        self._colors = get_colors(self._theme)
        self._icon_buttons: list[tuple[QToolButton, str]] = []

        self.sim = AutonomousDrivingSimulation()
        self.frame = self.sim.reset()
        self._last_log_message = ""

        self._timer = QTimer(self)
        self._timer.setInterval(max(20, int(round(self.sim.dt * 1000.0))))
        self._timer.timeout.connect(self._advance_once)

        self._build_ui()
        self.set_theme("dark")
        self._render(self.frame)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 8, 12, 8)
        root_layout.setSpacing(0)

        self._name_bar = QWidget()
        name_layout = QHBoxLayout(self._name_bar)
        name_layout.setContentsMargins(12, 8, 12, 8)
        name_layout.setSpacing(8)

        self._title_label = QLabel("Autonomous Driving Toolbox | Scenario: Highway Lane Following")
        self._title_label.setObjectName("adt_title")
        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("adt_status")
        name_layout.addWidget(self._title_label)
        name_layout.addStretch(1)
        name_layout.addWidget(self._status_label)

        root_layout.addWidget(self._name_bar)
        root_layout.addWidget(self._build_ribbon())

        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setChildrenCollapsible(False)

        self._left_panel = self._build_left_panel()
        self._main_splitter.addWidget(self._left_panel)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("adt_tabs")

        self._fig2d = Figure(figsize=(8.0, 4.5), dpi=100)
        self._ax2d = self._fig2d.add_subplot(111)
        self._canvas2d = FigureCanvas(self._fig2d)

        self._gl_view = OpenGLHighwayView()

        self._fig_sensor = Figure(figsize=(8.0, 4.5), dpi=100)
        self._ax_camera = self._fig_sensor.add_subplot(121)
        self._ax_sensor = self._fig_sensor.add_subplot(122)
        self._canvas_sensor = FigureCanvas(self._fig_sensor)

        self._tabs.addTab(self._wrap_widget(self._canvas2d), "Bird's-Eye 2D")
        self._tabs.addTab(self._wrap_widget(self._gl_view), "OpenGL 3D")
        self._tabs.addTab(self._wrap_widget(self._canvas_sensor), "Sensors & Perception")

        self._main_splitter.addWidget(self._tabs)
        self._main_splitter.setSizes([360, 1020])

        root_layout.addWidget(self._main_splitter, 1)

        self._bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(self._bottom_bar)
        bottom_layout.setContentsMargins(12, 8, 12, 8)
        self._time_label = QLabel("t = 0.00 s")
        self._speed_label = QLabel("v = 0.00 m/s")
        self._lane_label = QLabel("lane offset = 0.00 m")
        self._ttc_label = QLabel("TTC = --")
        bottom_layout.addWidget(self._time_label)
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(self._speed_label)
        bottom_layout.addWidget(self._lane_label)
        bottom_layout.addWidget(self._ttc_label)

        root_layout.addWidget(self._bottom_bar)

        self.setCentralWidget(root)

    def _build_ribbon(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("ribbon")
        panel.setMinimumHeight(172)
        panel.setMaximumHeight(214)
        row = QHBoxLayout(panel)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(6)

        sim_group = _RibbonGroup("SIMULATE")
        self._reset_btn = self._action_button("Reset", "reset", "Reset scenario")
        self._step_btn = self._action_button("Step", "forward", "Run one simulation step")
        self._run_btn = self._action_button("Run", "run", "Start continuous simulation")
        self._pause_btn = self._action_button("Pause", "stop", "Pause simulation")
        sim_group.add_widget(self._run_btn)
        sim_group.add_widget(self._pause_btn)
        sim_group.add_widget(self._step_btn)
        sim_group.add_widget(self._reset_btn)
        sim_group.finalize()
        row.addWidget(sim_group)

        map_group = _RibbonGroup("HD MAP")
        self._load_map_btn = self._action_button("Load Map", "open", "Load OpenDRIVE or Lanelet2 map")
        map_group.add_widget(self._load_map_btn)
        map_group.finalize()
        row.addWidget(map_group)

        scenario_group = _RibbonGroup("SCENARIO")
        self._replan_btn = self._action_button("Replan", "analysis", "Recompute route plan")
        self._speed_spin = QDoubleSpinBox()
        self._speed_spin.setRange(0.0, 45.0)
        self._speed_spin.setDecimals(1)
        self._speed_spin.setSuffix(" m/s")
        self._speed_spin.setValue(self.sim.ego.desired_speed)
        self._speed_spin.setToolTip("Ego desired cruise speed")
        scenario_group.add_widget(self._replan_btn)
        scenario_group.add_widget(QLabel("Cruise:"))
        scenario_group.add_widget(self._speed_spin)
        scenario_group.finalize()
        row.addWidget(scenario_group)

        adas_group = _RibbonGroup("ADAS")
        self._lka_check = QCheckBox("Lane Keeping Assist")
        self._lka_check.setChecked(True)
        self._cw_check = QCheckBox("Collision Warning")
        self._cw_check.setChecked(True)
        adas_group.add_widget(self._lka_check)
        adas_group.add_widget(self._cw_check)
        adas_group.finalize()
        row.addWidget(adas_group)

        sensor_group = _RibbonGroup("SENSORS")
        self._lidar_check = QCheckBox("LiDAR")
        self._lidar_check.setChecked(True)
        self._radar_check = QCheckBox("Radar")
        self._radar_check.setChecked(True)
        self._camera_check = QCheckBox("Camera")
        self._camera_check.setChecked(True)
        sensor_group.add_widget(self._lidar_check)
        sensor_group.add_widget(self._radar_check)
        sensor_group.add_widget(self._camera_check)
        sensor_group.finalize()
        row.addWidget(sensor_group)

        row.addStretch(1)

        self._reset_btn.clicked.connect(self._on_reset)
        self._step_btn.clicked.connect(self._advance_once)
        self._run_btn.clicked.connect(self._on_run)
        self._pause_btn.clicked.connect(self._on_pause)
        self._load_map_btn.clicked.connect(self._on_load_map)
        self._replan_btn.clicked.connect(self._on_replan)
        self._speed_spin.valueChanged.connect(self._on_cruise_speed_changed)
        for checkbox in (
            self._lidar_check,
            self._radar_check,
            self._camera_check,
            self._lka_check,
            self._cw_check,
        ):
            checkbox.toggled.connect(self._sync_feature_flags)

        return panel

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        metrics = QGroupBox("Live Metrics")
        m_layout = QVBoxLayout(metrics)
        self._metric_speed = QLabel("Speed: --")
        self._metric_accel = QLabel("Acceleration: --")
        self._metric_steer = QLabel("Steering: --")
        self._metric_lane = QLabel("Lane: --")
        self._metric_backend = QLabel("Physics backend: --")
        self._metric_warn = QLabel("Warnings: none")
        for label in (
            self._metric_speed,
            self._metric_accel,
            self._metric_steer,
            self._metric_lane,
            self._metric_backend,
            self._metric_warn,
        ):
            label.setObjectName("adt_metric")
            m_layout.addWidget(label)

        detections = QGroupBox("Perception Summary")
        d_layout = QVBoxLayout(detections)
        self._metric_lidar = QLabel("LiDAR points: 0")
        self._metric_radar = QLabel("Radar detections: 0")
        self._metric_camera = QLabel("Camera detections: 0")
        self._metric_tracks = QLabel("Tracked objects: 0")
        for label in (
            self._metric_lidar,
            self._metric_radar,
            self._metric_camera,
            self._metric_tracks,
        ):
            label.setObjectName("adt_metric")
            d_layout.addWidget(label)

        log_group = QGroupBox("Event Log")
        log_layout = QVBoxLayout(log_group)
        self._event_log = QListWidget()
        self._event_log.setAlternatingRowColors(True)
        log_layout.addWidget(self._event_log)

        layout.addWidget(metrics)
        layout.addWidget(detections)
        layout.addWidget(log_group, 1)

        return panel

    def _wrap_widget(self, widget: QWidget) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(widget)
        return wrap

    def _action_button(self, text: str, icon_name: str, tooltip: str) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("ribbon_action_primary")
        btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        btn.setIconSize(QSize(22, 22))
        btn.setMinimumSize(52, 56)
        self._icon_buttons.append((btn, icon_name))
        return btn

    def set_theme(self, theme: str) -> None:
        del theme
        self._theme = "dark"
        self._colors = get_colors(self._theme)
        c = self._colors

        self._name_bar.setStyleSheet(
            f"background: {c['bg_secondary']};"
            f"border-bottom: 1px solid {c['border']};"
        )
        self._bottom_bar.setStyleSheet(
            f"background: {c['bg_secondary']};"
            f"border-top: 1px solid {c['border']};"
        )

        self.setStyleSheet(
            "QLabel#adt_title {"
            f" color: {c['text_primary']};"
            " font-size: 12px;"
            " font-weight: 600;"
            "}"
            "QLabel#adt_status {"
            f" color: {c['text_secondary']};"
            " font-size: 10px;"
            "}"
            "QLabel#adt_metric {"
            f" color: {c['text_secondary']};"
            "}"
            "QCheckBox {"
            f" color: {c['text_secondary']};"
            " spacing: 5px;"
            "}"
            "QCheckBox::indicator {"
            " width: 14px;"
            " height: 14px;"
            f" border: 1px solid {c['border']};"
            " border-radius: 3px;"
            f" background: {c['bg_primary']};"
            "}"
            "QCheckBox::indicator:checked {"
            f" background: {c['accent']};"
            f" border-color: {c['accent_hover']};"
            "}"
            "QTabWidget#adt_tabs::pane {"
            f" border: 1px solid {c['border']};"
            " border-radius: 5px;"
            "}"
        )

        icon_color = c["text_primary"]
        for btn, icon_name in self._icon_buttons:
            icon_size = 22 if btn.objectName() == "ribbon_action_primary" else 16
            btn.setIcon(icon_for(icon_name, size=icon_size, color=icon_color))

        self._gl_view.set_theme(self._theme)
        self._render(self.frame)

    def _sync_feature_flags(self) -> None:
        self.sim.set_feature_flags(
            lidar=self._lidar_check.isChecked(),
            radar=self._radar_check.isChecked(),
            camera=self._camera_check.isChecked(),
            lane_keeping_assist=self._lka_check.isChecked(),
            collision_warning=self._cw_check.isChecked(),
        )

    def _on_cruise_speed_changed(self, value: float) -> None:
        self.sim.ego.desired_speed = float(value)

    def _on_load_map(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load HD Map",
            str(Path.home()),
            "HD Maps (*.xodr *.osm)",
        )
        if not path:
            return
        try:
            info = self.sim.load_hd_map(path)
        except Exception as exc:
            self._status_label.setText("Map load failed")
            self._push_log(f"Map load failed: {exc}")
            return

        self.frame = self.sim.reset()
        self.sim.ego.desired_speed = float(self._speed_spin.value())
        map_name = Path(path).name
        self._title_label.setText(f"Autonomous Driving Toolbox | Map: {map_name}")
        self._status_label.setText("HD map loaded")
        self._push_log(
            f"Loaded {info['format']} map: {map_name} | lanes={info['lanes']} length={float(info['road_length']):.1f}m"
        )
        self._render(self.frame)

    def _on_reset(self) -> None:
        self._timer.stop()
        self.frame = self.sim.reset()
        self.sim.ego.desired_speed = float(self._speed_spin.value())
        self._status_label.setText("Scenario reset")
        self._event_log.clear()
        self._last_log_message = ""
        self._render(self.frame)

    def _on_replan(self) -> None:
        self.sim.replan()
        self._status_label.setText("Route replanned")
        self._render(self.frame)

    def _on_run(self) -> None:
        if not self._timer.isActive():
            self._sync_feature_flags()
            self._timer.start()
            self._status_label.setText("Simulation running")

    def _on_pause(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self._status_label.setText("Simulation paused")

    def _advance_once(self) -> None:
        self._sync_feature_flags()
        self.sim.ego.desired_speed = float(self._speed_spin.value())
        self.frame = self.sim.step()
        self._render(self.frame)

    def _render(self, frame: SimulationFrame) -> None:
        self._render_2d(frame)
        self._gl_view.update_scene(frame, self.sim.road)
        self._render_sensors(frame)
        self._update_metrics(frame)

    def _render_2d(self, frame: SimulationFrame) -> None:
        ax = self._ax2d
        ax.clear()

        ego = frame.ego
        x_min = max(0.0, ego.x - 20.0)
        x_max = ego.x + 100.0
        xs = np.linspace(x_min, x_max, 220)

        lane_colors = ("#1e1e2e", "#181825")
        for lane_idx in range(len(self.sim.road.lane_centers)):
            yc = np.array([self.sim.road.lane_center(lane_idx, float(x)) for x in xs], dtype=float)
            half = 0.5 * self.sim.road.lane_width(lane_idx)
            ax.fill_between(xs, yc - half, yc + half, color=lane_colors[lane_idx % 2], alpha=0.65, linewidth=0)

        first_marks = self.sim.road.lane_markings(float(xs[0]))
        for mark_idx in range(len(first_marks)):
            ys = [self.sim.road.lane_markings(float(x))[mark_idx] for x in xs]
            ls = "-" if mark_idx in {0, len(first_marks) - 1} else "--"
            lw = 1.6 if ls == "-" else 1.0
            ax.plot(xs, ys, linestyle=ls, linewidth=lw, color="#f9e2af", alpha=0.85)

        if frame.global_path:
            gp = np.asarray(frame.global_path, dtype=float)
            ax.plot(gp[:, 0], gp[:, 1], color="#94e2d5", linewidth=1.2, alpha=0.72, label="Global path")

        if frame.trajectory:
            tr = np.asarray(frame.trajectory, dtype=float)
            ax.plot(tr[:, 0], tr[:, 1], color="#89b4fa", linewidth=2.0, label="Local trajectory")

        for veh in frame.vehicles:
            self._draw_vehicle_2d(ax, veh, "#f38ba8")
        self._draw_vehicle_2d(ax, frame.ego, "#89b4fa")

        if frame.lidar_points:
            pts = np.array(
                [
                    self.sim.road.to_global_frame(ego.x, ego.y, ego.yaw, p.x_rel, p.y_rel)
                    for p in frame.lidar_points
                ],
                dtype=float,
            )
            if pts.size:
                ax.scatter(pts[:, 0], pts[:, 1], s=5.0, c="#89dceb", alpha=0.5, label="LiDAR")

        for det in frame.radar_detections:
            x_rel = det.depth * np.cos(det.azimuth)
            y_rel = det.depth * np.sin(det.azimuth)
            gx, gy = self.sim.road.to_global_frame(ego.x, ego.y, ego.yaw, x_rel, y_rel)
            ax.plot([ego.x, gx], [ego.y, gy], color="#fab387", linewidth=0.9, alpha=0.55)

        if frame.fused_objects:
            for obj in frame.fused_objects:
                ax.scatter(obj.x, obj.y, s=22.0, c="#a6e3a1", edgecolors="#94e2d5", linewidths=0.6)
                ax.text(obj.x + 0.6, obj.y + 0.35, f"T{obj.track_id}", fontsize=7, color="#a6e3a1")

        bounds = self.sim.road.lane_bounds(ego.x)
        y_lo = min(b[0] for b in bounds) - 2.0
        y_hi = max(b[1] for b in bounds) + 2.0
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_lo, y_hi)
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_title("Bird's-Eye Simulation")
        ax.grid(True, color="#45475a", linewidth=0.35, alpha=0.35)
        ax.set_facecolor("#1e1e2e")
        self._fig2d.tight_layout(pad=1.0)
        self._canvas2d.draw_idle()

    def _render_sensors(self, frame: SimulationFrame) -> None:
        self._ax_camera.clear()
        self._ax_sensor.clear()

        cam_ax = self._ax_camera
        local_ax = self._ax_sensor

        cam_bg = "#1e1e2e"
        fg = "#cdd6f4"
        local_bg = "#181825"

        cam_w = float(self.sim.sensor_config.camera_width)
        cam_h = float(self.sim.sensor_config.camera_height)
        cam_ax.set_facecolor(cam_bg)
        cam_ax.set_xlim(0.0, cam_w)
        cam_ax.set_ylim(cam_h, 0.0)
        cam_ax.set_title("Camera Detections")
        cam_ax.set_xlabel("u (px)")
        cam_ax.set_ylabel("v (px)")

        for det in frame.camera_detections:
            u0 = det.bbox_u - 0.5 * det.bbox_w
            v0 = det.bbox_v - 0.5 * det.bbox_h
            rect = matplotlib.patches.Rectangle(
                (u0, v0),
                det.bbox_w,
                det.bbox_h,
                linewidth=1.2,
                edgecolor="#89b4fa",
                facecolor="none",
            )
            cam_ax.add_patch(rect)
            cam_ax.text(u0, max(12.0, v0 - 4.0), det.actor_id, color="#89dceb", fontsize=7)

        local_ax.set_facecolor(local_bg)
        local_ax.set_title("LiDAR / Radar / Tracks (ego frame)")
        local_ax.set_xlabel("Forward X (m)")
        local_ax.set_ylabel("Lateral Y (m)")
        local_ax.set_xlim(-5.0, 85.0)
        local_ax.set_ylim(-30.0, 30.0)
        local_ax.grid(True, alpha=0.35)

        if frame.lidar_points:
            x = [p.x_rel for p in frame.lidar_points]
            y = [p.y_rel for p in frame.lidar_points]
            local_ax.scatter(x, y, s=4.0, c="#89dceb", alpha=0.55, label="LiDAR")

        if frame.radar_detections:
            rx = [d.depth * np.cos(d.azimuth) for d in frame.radar_detections]
            ry = [d.depth * np.sin(d.azimuth) for d in frame.radar_detections]
            local_ax.scatter(rx, ry, s=24.0, marker="x", c="#fab387", label="Radar")

        ego = frame.ego
        for obj in frame.fused_objects:
            x_rel, y_rel = self.sim.road.to_local_frame(ego.x, ego.y, ego.yaw, obj.x, obj.y)
            local_ax.scatter([x_rel], [y_rel], s=26.0, c="#a6e3a1", edgecolors="#94e2d5", linewidths=0.6)

        local_ax.plot([0.0], [0.0], marker=(3, 0, -90), markersize=11, color="#89b4fa", label="Ego")
        local_ax.legend(loc="upper right", fontsize=8)

        for axis in (cam_ax, local_ax):
            for spine in axis.spines.values():
                spine.set_color("#45475a")
            axis.tick_params(colors=fg)
            axis.title.set_color(fg)
            axis.xaxis.label.set_color(fg)
            axis.yaxis.label.set_color(fg)

        self._fig_sensor.tight_layout(pad=1.0)
        self._canvas_sensor.draw_idle()

    def _update_metrics(self, frame: SimulationFrame) -> None:
        adas = frame.adas
        lane_offset = float(adas.get("lane_offset", frame.metrics.get("lane_offset", 0.0)))
        min_ttc = adas.get("min_ttc")

        self._time_label.setText(f"t = {frame.time:6.2f} s")
        self._speed_label.setText(f"v = {frame.ego.speed:5.2f} m/s")
        self._lane_label.setText(f"lane offset = {lane_offset:+.2f} m")
        self._ttc_label.setText("TTC = --" if min_ttc is None else f"TTC = {float(min_ttc):.2f} s")

        backend_name = self.sim.physics.info.backend_name

        self._metric_speed.setText(f"Speed: {frame.ego.speed:.2f} m/s")
        self._metric_accel.setText(f"Acceleration: {frame.ego.accel:+.2f} m/s^2")
        self._metric_steer.setText(f"Steering: {np.rad2deg(frame.ego.steer):+.2f} deg")
        self._metric_lane.setText(f"Lane index: {frame.ego.lane_index} | Goal lane: {self.sim.goal_lane}")
        self._metric_backend.setText(f"Physics backend: {backend_name}")

        warning_txt = "none"
        if adas.get("emergency_brake"):
            warning_txt = "EMERGENCY BRAKE"
        elif adas.get("collision_warning"):
            warning_txt = "Collision warning"
        self._metric_warn.setText(f"Warnings: {warning_txt}")

        self._metric_lidar.setText(f"LiDAR points: {len(frame.lidar_points)}")
        self._metric_radar.setText(f"Radar detections: {len(frame.radar_detections)}")
        self._metric_camera.setText(f"Camera detections: {len(frame.camera_detections)}")
        self._metric_tracks.setText(f"Tracked objects: {len(frame.fused_objects)}")

        if adas.get("emergency_brake"):
            self._status_label.setText("Emergency braking")
            self._push_log(f"{frame.time:6.2f}s | Emergency brake trigger")
        elif adas.get("collision_warning"):
            self._status_label.setText("Collision warning")
            self._push_log(f"{frame.time:6.2f}s | Forward collision warning")
        elif self._timer.isActive():
            self._status_label.setText("Simulation running")

    def _push_log(self, message: str) -> None:
        if message == self._last_log_message:
            return
        self._last_log_message = message
        self._event_log.addItem(message)
        self._event_log.scrollToBottom()

    @staticmethod
    def _vehicle_corners(vehicle: VehicleState) -> np.ndarray:
        c = float(np.cos(vehicle.yaw))
        s = float(np.sin(vehicle.yaw))
        hl = 0.5 * float(vehicle.length)
        hw = 0.5 * float(vehicle.width)
        local = np.array(
            [
                [hl, hw],
                [hl, -hw],
                [-hl, -hw],
                [-hl, hw],
            ],
            dtype=float,
        )
        rot = np.array([[c, -s], [s, c]], dtype=float)
        return local @ rot.T + np.array([vehicle.x, vehicle.y], dtype=float)

    def _draw_vehicle_2d(self, ax, vehicle: VehicleState, color: str) -> None:
        corners = self._vehicle_corners(vehicle)
        patch = matplotlib.patches.Polygon(
            corners,
            closed=True,
            facecolor=color,
            edgecolor="#111827",
            linewidth=0.9,
            alpha=0.88,
            zorder=3,
        )
        ax.add_patch(patch)

        nose = np.array(
            [
                vehicle.x + 0.55 * vehicle.length * np.cos(vehicle.yaw),
                vehicle.y + 0.55 * vehicle.length * np.sin(vehicle.yaw),
            ]
        )
        ax.plot([vehicle.x, nose[0]], [vehicle.y, nose[1]], color="#ffffff", linewidth=0.9, zorder=4)

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        self._timer.stop()
        self.closed.emit()
        super().closeEvent(event)


__all__ = ["AutonomousDrivingToolboxWindow"]
