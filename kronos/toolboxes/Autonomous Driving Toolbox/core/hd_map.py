"""HD map ingestion for OpenDRIVE and Lanelet2 (OSM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np


@dataclass
class HDLane:
    lane_id: str
    centerline: list[tuple[float, float]]
    width: float = 3.6
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class HDMap:
    source_path: str
    source_format: str
    lanes: list[HDLane]
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class LaneProfile:
    lane_id: str
    lane_index: int
    xs: np.ndarray
    ys: np.ndarray
    width: float


def load_hd_map(path: str | Path) -> HDMap:
    map_path = Path(path)
    suffix = map_path.suffix.lower()
    if suffix == ".xodr":
        return _parse_opendrive(map_path)
    if suffix == ".osm":
        return _parse_lanelet2_osm(map_path)
    raise ValueError(f"Unsupported HD map format: {map_path.suffix}")


def build_lane_profiles(hd_map: HDMap) -> list[LaneProfile]:
    if not hd_map.lanes:
        return []

    lanes = [ln for ln in hd_map.lanes if len(ln.centerline) >= 2]
    if not lanes:
        return []

    ref_lane = lanes[len(lanes) // 2]
    p0 = np.array(ref_lane.centerline[0], dtype=float)
    p1 = np.array(ref_lane.centerline[1], dtype=float)
    heading = float(np.arctan2(p1[1] - p0[1], p1[0] - p0[0]))
    c = float(np.cos(heading))
    s = float(np.sin(heading))

    profiles: list[LaneProfile] = []
    for lane in lanes:
        world = np.asarray(lane.centerline, dtype=float)
        rel = world - p0
        # Rotate into a local road-aligned frame for simulation usage.
        x_local = c * rel[:, 0] + s * rel[:, 1]
        y_local = -s * rel[:, 0] + c * rel[:, 1]

        order = np.argsort(x_local)
        x_sorted = x_local[order]
        y_sorted = y_local[order]

        # Remove duplicate x values for stable interpolation.
        uniq_x, uniq_idx = np.unique(np.round(x_sorted, 3), return_index=True)
        x_clean = x_sorted[uniq_idx]
        y_clean = y_sorted[uniq_idx]
        if len(x_clean) < 2:
            continue

        profiles.append(
            LaneProfile(
                lane_id=lane.lane_id,
                lane_index=-1,
                xs=np.asarray(x_clean, dtype=float),
                ys=np.asarray(y_clean, dtype=float),
                width=float(max(2.4, lane.width)),
            )
        )

    profiles.sort(key=lambda p: float(np.mean(p.ys)))
    for idx, profile in enumerate(profiles):
        profile.lane_index = idx

    return profiles


def _parse_opendrive(path: Path) -> HDMap:
    root = ET.parse(path).getroot()
    lanes: list[HDLane] = []

    roads = root.findall("road")
    for road_idx, road in enumerate(roads):
        refline = _sample_opendrive_reference_line(road)
        if refline.shape[0] < 2:
            continue

        lane_section = road.find("./lanes/laneSection")
        if lane_section is None:
            continue

        widths_right, offsets_right = _lane_offsets_for_side(lane_section, side="right")
        widths_left, offsets_left = _lane_offsets_for_side(lane_section, side="left")

        lane_defs: list[tuple[str, float, float]] = []
        lane_defs.extend((lane_id, width, offset) for lane_id, width, offset in offsets_right)
        lane_defs.extend((lane_id, width, offset) for lane_id, width, offset in offsets_left)

        if not lane_defs:
            continue

        headings = _polyline_headings(refline)
        normals = np.column_stack((-np.sin(headings), np.cos(headings)))

        for lane_id, width, offset in lane_defs:
            centerline = refline + normals * offset
            lanes.append(
                HDLane(
                    lane_id=f"road{road_idx}_{lane_id}",
                    centerline=[(float(p[0]), float(p[1])) for p in centerline],
                    width=float(width),
                    attributes={"road": str(road.attrib.get("id", road_idx))},
                )
            )

    return HDMap(
        source_path=str(path),
        source_format="OpenDRIVE",
        lanes=lanes,
        metadata={"roads": str(len(roads))},
    )


def _sample_opendrive_reference_line(road_element: ET.Element, step: float = 2.0) -> np.ndarray:
    plan_view = road_element.find("planView")
    if plan_view is None:
        return np.zeros((0, 2), dtype=float)

    pts: list[tuple[float, float]] = []

    for geom in plan_view.findall("geometry"):
        x0 = float(geom.attrib.get("x", 0.0))
        y0 = float(geom.attrib.get("y", 0.0))
        hdg = float(geom.attrib.get("hdg", 0.0))
        length = max(0.01, float(geom.attrib.get("length", 0.01)))

        n = max(2, int(np.ceil(length / max(0.5, step))) + 1)
        ts = np.linspace(0.0, length, n)

        if geom.find("line") is not None:
            xs = x0 + ts * np.cos(hdg)
            ys = y0 + ts * np.sin(hdg)
        elif geom.find("arc") is not None:
            curvature = float(geom.find("arc").attrib.get("curvature", 0.0))
            if abs(curvature) < 1e-8:
                xs = x0 + ts * np.cos(hdg)
                ys = y0 + ts * np.sin(hdg)
            else:
                xs = x0 + (np.sin(hdg + curvature * ts) - np.sin(hdg)) / curvature
                ys = y0 - (np.cos(hdg + curvature * ts) - np.cos(hdg)) / curvature
        else:
            # Fallback for unsupported primitives (spiral/poly3): linear segment.
            xs = x0 + ts * np.cos(hdg)
            ys = y0 + ts * np.sin(hdg)

        geom_pts = list(zip(xs.tolist(), ys.tolist()))
        if pts and geom_pts:
            geom_pts = geom_pts[1:]
        pts.extend((float(px), float(py)) for px, py in geom_pts)

    if len(pts) < 2:
        return np.zeros((0, 2), dtype=float)
    return np.asarray(pts, dtype=float)


def _lane_offsets_for_side(lane_section: ET.Element, side: str) -> tuple[list[float], list[tuple[str, float, float]]]:
    side_node = lane_section.find(side)
    if side_node is None:
        return [], []

    widths: list[float] = []
    lane_infos: list[tuple[int, float]] = []

    for lane in side_node.findall("lane"):
        lane_id = int(lane.attrib.get("id", "0"))
        width = _extract_lane_width(lane)
        if width <= 0.01:
            continue
        lane_infos.append((lane_id, width))

    if side == "left":
        lane_infos.sort(key=lambda item: abs(item[0]))
        sign = 1.0
    else:
        lane_infos.sort(key=lambda item: abs(item[0]))
        sign = -1.0

    offsets: list[tuple[str, float, float]] = []
    cumulative = 0.0
    for lane_id, width in lane_infos:
        offset = sign * (cumulative + 0.5 * width)
        cumulative += width
        widths.append(width)
        offsets.append((f"lane{lane_id}", width, offset))

    return widths, offsets


def _extract_lane_width(lane_elem: ET.Element) -> float:
    width_nodes = lane_elem.findall("width")
    if not width_nodes:
        return 3.6
    # Evaluate first polynomial at sOffset=0.
    node = width_nodes[0]
    a = float(node.attrib.get("a", 3.6))
    return float(max(2.4, a))


def _polyline_headings(polyline: np.ndarray) -> np.ndarray:
    d = np.diff(polyline, axis=0)
    headings = np.arctan2(d[:, 1], d[:, 0])
    headings = np.concatenate([headings, headings[-1:]], axis=0)
    return headings


def _parse_lanelet2_osm(path: Path) -> HDMap:
    root = ET.parse(path).getroot()

    nodes_xy = _extract_osm_nodes_xy(root)
    ways = _extract_osm_ways(root, nodes_xy)

    lanes: list[HDLane] = []
    for rel in root.findall("relation"):
        tags = {t.attrib.get("k", ""): t.attrib.get("v", "") for t in rel.findall("tag")}
        if tags.get("type") != "lanelet":
            continue

        left_way_id = None
        right_way_id = None
        for mem in rel.findall("member"):
            if mem.attrib.get("type") != "way":
                continue
            role = mem.attrib.get("role", "")
            ref = mem.attrib.get("ref", "")
            if role == "left":
                left_way_id = ref
            elif role == "right":
                right_way_id = ref

        if left_way_id is None or right_way_id is None:
            continue
        if left_way_id not in ways or right_way_id not in ways:
            continue

        left = ways[left_way_id]
        right = ways[right_way_id]
        if left.shape[0] < 2 or right.shape[0] < 2:
            continue

        left_rs = _resample_polyline(left, 60)
        right_rs = _resample_polyline(right, 60)
        center = 0.5 * (left_rs + right_rs)
        width = float(np.mean(np.linalg.norm(left_rs - right_rs, axis=1)))

        lanes.append(
            HDLane(
                lane_id=f"lanelet_{rel.attrib.get('id', str(len(lanes)))}",
                centerline=[(float(p[0]), float(p[1])) for p in center],
                width=float(max(2.4, width)),
                attributes=tags,
            )
        )

    return HDMap(
        source_path=str(path),
        source_format="Lanelet2",
        lanes=lanes,
        metadata={"relations": str(len(root.findall('relation')))},
    )


def _extract_osm_nodes_xy(root: ET.Element) -> dict[str, np.ndarray]:
    nodes_raw: list[tuple[str, float, float, bool]] = []
    for node in root.findall("node"):
        node_id = node.attrib.get("id", "")
        if "x" in node.attrib and "y" in node.attrib:
            x = float(node.attrib["x"])
            y = float(node.attrib["y"])
            nodes_raw.append((node_id, x, y, True))
        elif "lon" in node.attrib and "lat" in node.attrib:
            lon = float(node.attrib["lon"])
            lat = float(node.attrib["lat"])
            nodes_raw.append((node_id, lon, lat, False))

    if not nodes_raw:
        return {}

    if nodes_raw[0][3]:
        return {node_id: np.array([x, y], dtype=float) for node_id, x, y, _ in nodes_raw}

    # Convert lon/lat to local ENU approximation.
    lon0 = nodes_raw[0][1]
    lat0 = nodes_raw[0][2]
    cos_lat = float(np.cos(np.deg2rad(lat0)))

    out: dict[str, np.ndarray] = {}
    for node_id, lon, lat, _ in nodes_raw:
        x = (lon - lon0) * 111320.0 * cos_lat
        y = (lat - lat0) * 110540.0
        out[node_id] = np.array([x, y], dtype=float)
    return out


def _extract_osm_ways(root: ET.Element, nodes_xy: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    ways: dict[str, np.ndarray] = {}
    for way in root.findall("way"):
        way_id = way.attrib.get("id", "")
        points: list[np.ndarray] = []
        for nd in way.findall("nd"):
            ref = nd.attrib.get("ref", "")
            if ref in nodes_xy:
                points.append(nodes_xy[ref])
        if len(points) >= 2:
            ways[way_id] = np.asarray(points, dtype=float)
    return ways


def _resample_polyline(polyline: np.ndarray, samples: int) -> np.ndarray:
    if polyline.shape[0] < 2:
        return polyline
    seg = np.linalg.norm(np.diff(polyline, axis=0), axis=1)
    s = np.concatenate(([0.0], np.cumsum(seg)))
    if s[-1] <= 1e-9:
        return np.repeat(polyline[:1], samples, axis=0)
    sq = np.linspace(0.0, s[-1], max(2, samples))
    xq = np.interp(sq, s, polyline[:, 0])
    yq = np.interp(sq, s, polyline[:, 1])
    return np.column_stack([xq, yq])


__all__ = [
    "HDLane",
    "HDMap",
    "LaneProfile",
    "build_lane_profiles",
    "load_hd_map",
]
