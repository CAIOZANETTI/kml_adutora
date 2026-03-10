"""Elevation enrichment using embedded KML Z values or Open-Meteo."""

from __future__ import annotations

from typing import Dict, List, Optional

import requests

_API_URL = "https://api.open-meteo.com/v1/elevation"
_BATCH_SIZE = 100
_TIMEOUT = (4, 12)


def _fetch_batch(lats: List[float], lons: List[float], session: Optional[requests.Session] = None) -> List[float]:
    http = session or requests
    response = http.get(
        _API_URL,
        params={
            "latitude": ",".join(str(value) for value in lats),
            "longitude": ",".join(str(value) for value in lons),
        },
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    elevations = payload.get("elevation", [])
    if len(elevations) != len(lats):
        raise RuntimeError(
            f"Resposta de elevacao inconsistente: {len(elevations)} cotas para {len(lats)} pontos."
        )
    return [float(value) for value in elevations]


def enrich_elevation(points: List[Dict], source: str = "auto", progress_callback=None) -> List[Dict]:
    if source not in {"auto", "kml", "open-meteo"}:
        raise ValueError("Fonte de elevacao invalida.")

    hints = [point.get("z_hint_m") for point in points]
    can_use_kml = all(value is not None for value in hints)

    if source in {"auto", "kml"} and can_use_kml:
        for point in points:
            point["z_terrain_m"] = float(point["z_hint_m"])
            point["elevation_source"] = "kml"
        if progress_callback:
            progress_callback(len(points), len(points))
        return points

    if source == "kml" and not can_use_kml:
        raise RuntimeError("O KML nao possui cotas em todos os pontos necessarios.")

    with requests.Session() as session:
        all_elevations: List[float] = []
        total = len(points)
        for start in range(0, total, _BATCH_SIZE):
            batch = points[start : start + _BATCH_SIZE]
            lats = [point["lat"] for point in batch]
            lons = [point["lon"] for point in batch]
            all_elevations.extend(_fetch_batch(lats, lons, session=session))
            if progress_callback:
                progress_callback(min(start + _BATCH_SIZE, total), total)

    for point, elevation in zip(points, all_elevations):
        point["z_terrain_m"] = float(elevation)
        point["elevation_source"] = "open-meteo"
    return points
