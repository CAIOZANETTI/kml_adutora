"""Geospatial helpers for stationing, distances, and bend detection."""

from __future__ import annotations

import math
from typing import Dict, Iterable, List

import numpy as np

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_M * 2 * math.asin(math.sqrt(a))


def cumulative_distances(points: Iterable[Dict]) -> np.ndarray:
    points = list(points)
    cumulative = [0.0]
    for idx in range(1, len(points)):
        prev = points[idx - 1]
        curr = points[idx]
        cumulative.append(
            cumulative[-1] + haversine_m(prev["lat"], prev["lon"], curr["lat"], curr["lon"])
        )
    return np.asarray(cumulative, dtype=float)


def build_stationing(points: List[Dict], station_interval_m: float = 50.0) -> List[Dict]:
    if len(points) < 2:
        raise ValueError("Sao necessarios pelo menos dois pontos para construir o estaqueamento.")
    if station_interval_m <= 0:
        raise ValueError("O intervalo de estaqueamento deve ser positivo.")

    raw_x = cumulative_distances(points)
    raw_lats = np.asarray([p["lat"] for p in points], dtype=float)
    raw_lons = np.asarray([p["lon"] for p in points], dtype=float)

    raw_z = np.asarray([
        np.nan if p.get("z_kml_m") is None else float(p["z_kml_m"])
        for p in points
    ])

    unique_x, unique_idx = np.unique(raw_x, return_index=True)
    raw_x = unique_x
    raw_lats = raw_lats[unique_idx]
    raw_lons = raw_lons[unique_idx]
    raw_z = raw_z[unique_idx]

    total_length = float(raw_x[-1])
    stations = np.arange(0.0, total_length, station_interval_m, dtype=float)
    if stations.size == 0 or stations[-1] < total_length:
        stations = np.append(stations, total_length)

    lat_interp = np.interp(stations, raw_x, raw_lats)
    lon_interp = np.interp(stations, raw_x, raw_lons)

    if np.all(np.isnan(raw_z)):
        z_interp = np.full_like(stations, np.nan, dtype=float)
    else:
        valid = ~np.isnan(raw_z)
        z_interp = np.interp(stations, raw_x[valid], raw_z[valid])

    station_points: List[Dict] = []
    for idx, station_m in enumerate(stations):
        distance_m = 0.0 if idx == 0 else float(stations[idx] - stations[idx - 1])
        station_points.append(
            {
                "station_m": round(float(station_m), 2),
                "distance_m": round(distance_m, 2),
                "lat": round(float(lat_interp[idx]), 8),
                "lon": round(float(lon_interp[idx]), 8),
                "z_hint_m": None if np.isnan(z_interp[idx]) else round(float(z_interp[idx]), 2),
            }
        )
    return station_points


def _bearing_deg(p1: Dict, p2: Dict) -> float:
    lat1 = math.radians(p1["lat"])
    lat2 = math.radians(p2["lat"])
    dlon = math.radians(p2["lon"] - p1["lon"])
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def find_bends(points: List[Dict], min_deflection_deg: float = 20.0) -> List[Dict]:
    bends: List[Dict] = []
    if len(points) < 3:
        return bends

    raw_x = cumulative_distances(points)
    for idx in range(1, len(points) - 1):
        b1 = _bearing_deg(points[idx - 1], points[idx])
        b2 = _bearing_deg(points[idx], points[idx + 1])
        delta = abs((b2 - b1 + 180.0) % 360.0 - 180.0)
        if delta >= min_deflection_deg:
            bends.append(
                {
                    "point_index": idx,
                    "station_m": round(float(raw_x[idx]), 2),
                    "lat": points[idx]["lat"],
                    "lon": points[idx]["lon"],
                    "deflection_deg": round(delta, 1),
                }
            )
    return bends
