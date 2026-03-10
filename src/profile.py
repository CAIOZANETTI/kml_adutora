"""Terrain profile preparation and geometric feature extraction."""

from __future__ import annotations

from typing import Dict, List


def enrich_profile_attributes(points: List[Dict]) -> List[Dict]:
    if len(points) < 2:
        raise ValueError("Perfil insuficiente para analise.")

    enriched: List[Dict] = []
    for idx, point in enumerate(points):
        prev_point = points[idx - 1] if idx > 0 else point
        next_point = points[idx + 1] if idx < len(points) - 1 else point

        if idx == 0:
            slope_pct = 0.0
        else:
            dz = float(point["z_terrain_m"]) - float(prev_point["z_terrain_m"])
            dx = float(point["distance_m"])
            slope_pct = (dz / dx * 100.0) if dx > 0 else 0.0

        is_high = idx not in {0, len(points) - 1} and (
            point["z_terrain_m"] >= prev_point["z_terrain_m"]
            and point["z_terrain_m"] > next_point["z_terrain_m"]
        )
        is_low = idx not in {0, len(points) - 1} and (
            point["z_terrain_m"] <= prev_point["z_terrain_m"]
            and point["z_terrain_m"] < next_point["z_terrain_m"]
        )

        enriched.append(
            {
                **point,
                "slope_geom_pct": round(float(slope_pct), 3),
                "is_high_point": bool(is_high),
                "is_low_point": bool(is_low),
            }
        )
    return enriched
