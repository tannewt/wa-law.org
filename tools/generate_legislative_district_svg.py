#!/usr/bin/env python3
"""Generate an SVG map of Washington legislative districts.

This script reads the 2022 amended legislative district shapefile and writes an SVG
that includes:
- An outline of Washington state (dissolved from district polygons)
- One dot per district (point-on-surface)
- District number labels centered in each dot

The output is styled with CSS classes so districts can be colored individually.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

DEFAULT_SHAPEFILE = Path(
    "/home/tannewt/Downloads/AMENDED FINAL DISTRICTS 2022_GIS-Ready/"
    "Final District Shapes 2022_NAD_83/Final District Shapes 2022/Legislative/"
    "LEG_AMEND_FINAL_GCS_NAD83.shp"
)
DEFAULT_OUTPUT = Path("site/wa-legislative-districts.svg")


class CommandError(RuntimeError):
    pass


def run_command(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise CommandError(
            f"Command failed ({result.returncode}): {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def run_command_output(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise CommandError(
            f"Command failed ({result.returncode}): {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result.stdout


def load_geojson(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def iter_rings(geometry: dict) -> Iterable[list[list[float]]]:
    geom_type = geometry["type"]
    coords = geometry["coordinates"]
    if geom_type == "Polygon":
        for ring in coords:
            yield ring
    elif geom_type == "MultiPolygon":
        for polygon in coords:
            for ring in polygon:
                yield ring
    else:
        raise ValueError(f"Unsupported geometry type for path rendering: {geom_type}")


def extract_bounds_from_rings(rings: Iterable[list[list[float]]]) -> tuple[float, float, float, float]:
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")

    for ring in rings:
        for x, y in ring:
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

    if min_x == float("inf"):
        raise ValueError("No coordinates found in geometry")

    return min_x, min_y, max_x, max_y


def svg_path_from_geometry(geometry: dict, project) -> str:
    parts: list[str] = []
    for ring in iter_rings(geometry):
        if not ring:
            continue
        start_x, start_y = project(ring[0][0], ring[0][1])
        parts.append(f"M {start_x:.2f} {start_y:.2f}")
        for x, y in ring[1:]:
            px, py = project(x, y)
            parts.append(f"L {px:.2f} {py:.2f}")
        parts.append("Z")
    return " ".join(parts)


def _point_line_distance(point, start, end) -> float:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    # Perpendicular distance to the infinite line.
    return abs(dy * px - dx * py + x2 * y1 - y2 * x1) / (dx * dx + dy * dy) ** 0.5


def _rdp(points, epsilon: float):
    if len(points) < 3:
        return points
    start = points[0]
    end = points[-1]
    max_distance = -1.0
    index = -1
    for i in range(1, len(points) - 1):
        distance = _point_line_distance(points[i], start, end)
        if distance > max_distance:
            max_distance = distance
            index = i
    if max_distance > epsilon:
        left = _rdp(points[: index + 1], epsilon)
        right = _rdp(points[index:], epsilon)
        return left[:-1] + right
    return [start, end]


def simplify_ring(ring: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    if epsilon <= 0 or len(ring) < 5:
        return ring
    closed = ring[0] == ring[-1]
    work = ring[:-1] if closed else ring[:]
    simplified = _rdp(work, epsilon)
    if len(simplified) < 3:
        simplified = work[:3]
    if closed:
        simplified.append(simplified[0])
    return simplified


def district_number(properties: dict) -> int:
    for key in ("district", "DISTRICT", "DISTRICTN", "ID"):
        if key in properties and properties[key] not in (None, ""):
            value = properties[key]
            if isinstance(value, str):
                value = value.strip()
            return int(float(value))
    raise ValueError(f"Could not infer district number from properties: {properties}")


def detect_layer_name(dataset_path: Path) -> str:
    output = run_command_output(["ogrinfo", "-ro", "-q", str(dataset_path)])
    for line in output.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        # Example: 1: LEG_AMEND_FINAL_GCS_NAD83 (Polygon)
        if line[0].isdigit():
            _, remainder = line.split(":", 1)
            return remainder.strip().split(" (", 1)[0].strip()
    raise ValueError(f"Could not detect layer name from {dataset_path}")


def nudge_points_to_avoid_overlap(
    anchors: list[tuple[float, float]],
    dot_radius: float,
    width: int,
    height: int,
    padding: int,
) -> list[tuple[float, float]]:
    """Nudge points with a simple anchored spring model so circles do not overlap."""
    points = [[ax, ay] for ax, ay in anchors]
    min_distance = (dot_radius * 2.0) + 0.8
    max_offset = max(dot_radius * 14.0, min_distance * 3.0)
    min_x = padding + dot_radius
    max_x = width - padding - dot_radius
    min_y = padding + dot_radius
    max_y = height - padding - dot_radius

    for _ in range(800):
        forces = [[0.0, 0.0] for _ in points]

        # Repel overlapping points.
        for i in range(len(points)):
            xi, yi = points[i]
            for j in range(i + 1, len(points)):
                xj, yj = points[j]
                dx = xj - xi
                dy = yj - yi
                dist = math.hypot(dx, dy)
                if dist < min_distance:
                    if dist < 1e-6:
                        angle = ((i * 37 + j * 17) % 360) * math.pi / 180.0
                        ux = math.cos(angle)
                        uy = math.sin(angle)
                    else:
                        ux = dx / dist
                        uy = dy / dist
                    overlap = min_distance - max(dist, 1e-6)
                    push = overlap * 0.72
                    fx = ux * push
                    fy = uy * push
                    forces[i][0] -= fx
                    forces[i][1] -= fy
                    forces[j][0] += fx
                    forces[j][1] += fy

        # Pull points back to their district anchor.
        for i, (ax, ay) in enumerate(anchors):
            px, py = points[i]
            forces[i][0] += (ax - px) * 0.08
            forces[i][1] += (ay - py) * 0.08

        max_move = 0.0
        for i, (ax, ay) in enumerate(anchors):
            px, py = points[i]
            px += forces[i][0] * 0.60
            py += forces[i][1] * 0.60

            # Keep each point near its district anchor.
            off_x = px - ax
            off_y = py - ay
            off_d = math.hypot(off_x, off_y)
            if off_d > max_offset:
                scale = max_offset / off_d
                px = ax + (off_x * scale)
                py = ay + (off_y * scale)

            # Keep points inside the drawable area.
            px = min(max(px, min_x), max_x)
            py = min(max(py, min_y), max_y)

            move = math.hypot(px - points[i][0], py - points[i][1])
            if move > max_move:
                max_move = move

            points[i][0] = px
            points[i][1] = py

        if max_move < 0.02:
            break

    # Final hard pass: separate any remaining overlaps deterministically.
    for _ in range(600):
        changed = False
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                xi, yi = points[i]
                xj, yj = points[j]
                dx = xj - xi
                dy = yj - yi
                dist = math.hypot(dx, dy)
                if dist + 1e-6 < min_distance:
                    if dist < 1e-6:
                        angle = ((i * 53 + j * 29) % 360) * math.pi / 180.0
                        ux = math.cos(angle)
                        uy = math.sin(angle)
                    else:
                        ux = dx / dist
                        uy = dy / dist
                    push = (min_distance - max(dist, 1e-6)) * 0.52
                    points[i][0] -= ux * push
                    points[i][1] -= uy * push
                    points[j][0] += ux * push
                    points[j][1] += uy * push
                    changed = True

        for i, (ax, ay) in enumerate(anchors):
            px, py = points[i]
            # A tiny anchor pull so points still hug their district.
            px += (ax - px) * 0.02
            py += (ay - py) * 0.02

            off_x = px - ax
            off_y = py - ay
            off_d = math.hypot(off_x, off_y)
            if off_d > max_offset:
                scale = max_offset / off_d
                px = ax + (off_x * scale)
                py = ay + (off_y * scale)

            px = min(max(px, min_x), max_x)
            py = min(max(py, min_y), max_y)
            points[i][0] = px
            points[i][1] = py

        if not changed:
            break

    return [(x, y) for x, y in points]


def build_svg(
    state_geometry: dict,
    district_points: list[dict],
    width: int,
    height: int,
    padding: int,
    dot_radius: float,
    font_size: float,
    outline_simplify_px: float,
) -> str:
    state_rings = list(iter_rings(state_geometry))
    min_x, min_y, max_x, max_y = extract_bounds_from_rings(state_rings)

    span_x = max_x - min_x
    span_y = max_y - min_y
    if span_x <= 0 or span_y <= 0:
        raise ValueError("Invalid map bounds")

    inner_w = max(1.0, width - 2 * padding)
    inner_h = max(1.0, height - 2 * padding)
    scale = min(inner_w / span_x, inner_h / span_y)

    used_w = span_x * scale
    used_h = span_y * scale
    offset_x = (width - used_w) / 2.0
    offset_y = (height - used_h) / 2.0

    def project(x: float, y: float) -> tuple[float, float]:
        px = offset_x + (x - min_x) * scale
        py = offset_y + (max_y - y) * scale
        return px, py

    # Build the outline path with optional simplification in pixel units.
    outline_parts: list[str] = []
    for ring in iter_rings(state_geometry):
        projected_ring = [project(x, y) for x, y in ring]
        simplified_ring = simplify_ring(projected_ring, outline_simplify_px)
        if not simplified_ring:
            continue
        start_x, start_y = simplified_ring[0]
        outline_parts.append(f"M {start_x:.2f} {start_y:.2f}")
        for x, y in simplified_ring[1:]:
            outline_parts.append(f"L {x:.2f} {y:.2f}")
        outline_parts.append("Z")
    outline_path = " ".join(outline_parts)

    sorted_features = sorted(district_points, key=lambda f: district_number(f["properties"]))
    anchor_positions: list[tuple[float, float]] = []
    district_numbers: list[int] = []
    for feature in sorted_features:
        props = feature["properties"]
        number = district_number(props)
        geom = feature["geometry"]
        if geom["type"] != "Point":
            raise ValueError(f"Expected Point geometry for district {number}, got {geom['type']}")
        x, y = geom["coordinates"]
        px, py = project(x, y)
        district_numbers.append(number)
        anchor_positions.append((px, py))

    placed_positions = nudge_points_to_avoid_overlap(
        anchors=anchor_positions,
        dot_radius=dot_radius,
        width=width,
        height=height,
        padding=padding,
    )

    district_groups: list[str] = []
    for idx, number in enumerate(district_numbers):
        px, py = placed_positions[idx]
        ax, ay = anchor_positions[idx]
        moved = math.hypot(px - ax, py - ay) > 0.25
        link_svg = ""
        if moved:
            link_svg = (
                f'    <line class="district-link" x1="{ax:.2f}" y1="{ay:.2f}" '
                f'x2="{px:.2f}" y2="{py:.2f}" />\n'
            )
        district_groups.append(
            f'  <g id="district-{number}" class="district district-{number}">\n'
            f"{link_svg}"
            f'    <circle class="district-dot" cx="{px:.2f}" cy="{py:.2f}" r="{dot_radius:.2f}" />\n'
            f'    <text class="district-label" x="{px:.2f}" y="{py:.2f}">{number}</text>\n'
            f"  </g>"
        )

    css = """
  :root {
    --outline-fill: #f3f4f6;
    --outline-stroke: #1f2937;
    --outline-width: 2;
    --district-link-stroke: #6b7280;
    --district-link-width: 1;
    --district-dot-fill: #2563eb;
    --district-dot-stroke: #ffffff;
    --district-dot-stroke-width: 1.5;
    --district-label-fill: #ffffff;
  }

  .state-outline {
    fill: var(--outline-fill);
    stroke: var(--outline-stroke);
    stroke-width: var(--outline-width);
    stroke-linejoin: round;
    stroke-linecap: round;
  }

  .district-dot {
    fill: var(--district-dot-fill);
    stroke: var(--district-dot-stroke);
    stroke-width: var(--district-dot-stroke-width);
  }

  .district-link {
    stroke: var(--district-link-stroke);
    stroke-width: var(--district-link-width);
    stroke-linecap: round;
    opacity: 0.8;
  }

  .district-label {
    fill: var(--district-label-fill);
    font-family: "Noto Sans", "Liberation Sans", sans-serif;
    font-size: %0.2fpx;
    font-weight: 700;
    text-anchor: middle;
    dominant-baseline: central;
    pointer-events: none;
  }
""" % (
        font_size,
    )

    svg = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        "  <title id=\"title\">Washington State Legislative Districts</title>",
        "  <desc id=\"desc\">Washington outline with labeled dots for legislative districts 1 through 49.</desc>",
        "  <style>",
        css.rstrip("\n"),
        "  </style>",
        f'  <path id="state-outline" class="state-outline" d="{outline_path}" />',
        "  <g id=\"district-points\">",
        *district_groups,
        "  </g>",
        "</svg>",
        "",
    ]
    return "\n".join(svg)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shapefile", type=Path, default=DEFAULT_SHAPEFILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--width", type=int, default=300)
    parser.add_argument("--height", type=int, default=0, help="Output height in px; 0 means auto")
    parser.add_argument("--padding", type=int, default=24)
    parser.add_argument("--dot-radius", type=float, default=None)
    parser.add_argument("--font-size", type=float, default=None)
    parser.add_argument(
        "--outline-simplify-px",
        type=float,
        default=1.5,
        help="Simplify state outline path by this many pixels (Douglas-Peucker).",
    )
    args = parser.parse_args()

    if shutil.which("ogr2ogr") is None:
        raise SystemExit("ogr2ogr is required but was not found in PATH")

    if not args.shapefile.exists():
        raise SystemExit(f"Shapefile not found: {args.shapefile}")

    layer_name = detect_layer_name(args.shapefile)

    with tempfile.TemporaryDirectory(prefix="wa_ld_svg_") as tmpdir:
        tmpdir_path = Path(tmpdir)
        state_geojson = tmpdir_path / "state.geojson"
        points_geojson = tmpdir_path / "district_points.geojson"

        # Dissolve districts into one statewide outline.
        run_command(
            [
                "ogr2ogr",
                "-f",
                "GeoJSON",
                str(state_geojson),
                str(args.shapefile),
                "-t_srs",
                "EPSG:3857",
                "-dialect",
                "sqlite",
                "-sql",
                f"SELECT ST_Union(geometry) AS geometry FROM {layer_name}",
            ]
        )

        # Compute one interior point per district and keep district id for labels/classes.
        run_command(
            [
                "ogr2ogr",
                "-f",
                "GeoJSON",
                str(points_geojson),
                str(args.shapefile),
                "-t_srs",
                "EPSG:3857",
                "-dialect",
                "sqlite",
                "-sql",
                f"SELECT CAST(DISTRICT AS INTEGER) AS district, ST_PointOnSurface(geometry) AS geometry FROM {layer_name}",
            ]
        )

        state_fc = load_geojson(state_geojson)
        points_fc = load_geojson(points_geojson)

        if not state_fc.get("features"):
            raise SystemExit("State outline query returned no features")
        if not points_fc.get("features"):
            raise SystemExit("District point query returned no features")

        state_geometry = state_fc["features"][0]["geometry"]
        point_features = points_fc["features"]

    if args.height > 0:
        height = args.height
    else:
        # Auto-height from outline aspect ratio.
        rings = list(iter_rings(state_geometry))
        min_x, min_y, max_x, max_y = extract_bounds_from_rings(rings)
        span_x = max_x - min_x
        span_y = max_y - min_y
        inner_w = max(1.0, args.width - 2 * args.padding)
        height = int(round((span_y / span_x) * inner_w + 2 * args.padding))

    dot_radius = (
        args.dot_radius
        if args.dot_radius is not None
        else max(3.0, round((args.width / 1200.0) * 11.0, 2))
    )
    font_size = (
        args.font_size
        if args.font_size is not None
        else max(4.0, round((args.width / 1200.0) * 10.0, 2))
    )

    svg = build_svg(
        state_geometry=state_geometry,
        district_points=point_features,
        width=args.width,
        height=height,
        padding=args.padding,
        dot_radius=dot_radius,
        font_size=font_size,
        outline_simplify_px=args.outline_simplify_px,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    print(f"Wrote {args.output} ({len(point_features)} districts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
