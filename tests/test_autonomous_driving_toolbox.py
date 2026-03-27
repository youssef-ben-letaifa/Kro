from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kronos.toolboxes import list_available_toolboxes, load_toolbox


class AutonomousDrivingToolboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.toolbox_names = list_available_toolboxes()
        cls.module = load_toolbox("Autonomous Driving Toolbox")

    def test_toolbox_is_registered(self) -> None:
        self.assertIn("Autonomous Driving Toolbox", self.toolbox_names)

    def test_simulation_pipeline_advances(self) -> None:
        sim = self.module.AutonomousDrivingSimulation(seed=11)
        frame0 = sim.reset()
        frame1 = sim.step()

        self.assertGreater(frame1.time, frame0.time)
        self.assertGreaterEqual(len(frame1.trajectory), 2)
        self.assertGreaterEqual(len(frame1.lidar_points), 0)
        self.assertGreaterEqual(len(frame1.radar_detections), 0)
        self.assertGreaterEqual(len(frame1.camera_detections), 0)
        self.assertIsInstance(frame1.adas, dict)
        self.assertIn("backend_native_active", frame1.metrics)

    def test_adas_collision_warning_emergency(self) -> None:
        sim = self.module.AutonomousDrivingSimulation(seed=13)
        sim.reset()
        sim.force_collision_case(distance=7.0, lead_speed=0.0)

        warning_seen = False
        emergency_seen = False
        for _ in range(20):
            frame = sim.step()
            warning_seen = warning_seen or bool(frame.adas.get("collision_warning"))
            emergency_seen = emergency_seen or bool(frame.adas.get("emergency_brake"))
            if emergency_seen:
                break

        self.assertTrue(warning_seen)
        self.assertTrue(emergency_seen)

    def test_lane_change_path_generation(self) -> None:
        sim = self.module.AutonomousDrivingSimulation(seed=5)
        sim.reset()
        start_lane = sim.ego.lane_index
        target_lane = min(sim.road.config.lane_count - 1, start_lane + 1)

        path = sim.path_planner.plan_global_path(sim.ego.x, start_lane, sim.goal_x, target_lane)
        self.assertGreater(len(path), 10)

        start_y = path[0][1]
        end_y = path[-1][1]
        self.assertLess(abs(start_y - sim.road.lane_center(start_lane)), 1.2)
        self.assertLess(abs(end_y - sim.road.lane_center(target_lane)), 1.2)

    def test_hd_map_ingestion_opendrive(self) -> None:
        xodr = """<?xml version="1.0" standalone="yes"?>
<OpenDRIVE>
  <road name="R0" length="120.0" id="1" junction="-1">
    <planView>
      <geometry s="0.0" x="0.0" y="0.0" hdg="0.0" length="120.0">
        <line/>
      </geometry>
    </planView>
    <lanes>
      <laneSection s="0.0">
        <left>
          <lane id="1" type="driving" level="false">
            <width sOffset="0.0" a="3.5" b="0.0" c="0.0" d="0.0"/>
          </lane>
        </left>
        <center>
          <lane id="0" type="none" level="false"/>
        </center>
        <right>
          <lane id="-1" type="driving" level="false">
            <width sOffset="0.0" a="3.5" b="0.0" c="0.0" d="0.0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
</OpenDRIVE>
"""
        with tempfile.TemporaryDirectory() as tmp:
            map_path = Path(tmp) / "road.xodr"
            map_path.write_text(xodr, encoding="utf-8")

            sim = self.module.AutonomousDrivingSimulation(seed=2)
            info = sim.load_hd_map(map_path)
            frame = sim.step()

            self.assertEqual(info["format"], "OpenDRIVE")
            self.assertGreaterEqual(int(info["lanes"]), 2)
            self.assertGreater(frame.time, 0.0)
            self.assertTrue(sim.road.hd_enabled)

    def test_hd_map_ingestion_lanelet2(self) -> None:
        osm = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="kronos-test">
  <node id="1" x="0.0" y="3.5" />
  <node id="2" x="80.0" y="3.5" />
  <node id="3" x="0.0" y="0.0" />
  <node id="4" x="80.0" y="0.0" />
  <node id="5" x="0.0" y="0.0" />
  <node id="6" x="80.0" y="0.0" />
  <node id="7" x="0.0" y="-3.5" />
  <node id="8" x="80.0" y="-3.5" />
  <way id="10"><nd ref="1"/><nd ref="2"/></way>
  <way id="11"><nd ref="3"/><nd ref="4"/></way>
  <way id="12"><nd ref="5"/><nd ref="6"/></way>
  <way id="13"><nd ref="7"/><nd ref="8"/></way>
  <relation id="100">
    <member type="way" ref="10" role="left"/>
    <member type="way" ref="11" role="right"/>
    <tag k="type" v="lanelet"/>
  </relation>
  <relation id="101">
    <member type="way" ref="12" role="left"/>
    <member type="way" ref="13" role="right"/>
    <tag k="type" v="lanelet"/>
  </relation>
</osm>
"""
        with tempfile.TemporaryDirectory() as tmp:
            map_path = Path(tmp) / "lanelet.osm"
            map_path.write_text(osm, encoding="utf-8")

            sim = self.module.AutonomousDrivingSimulation(seed=3)
            info = sim.load_hd_map(map_path)
            frame = sim.step()

            self.assertEqual(info["format"], "Lanelet2")
            self.assertGreaterEqual(int(info["lanes"]), 2)
            self.assertGreater(frame.time, 0.0)
            self.assertTrue(sim.road.hd_enabled)


if __name__ == "__main__":
    unittest.main()
