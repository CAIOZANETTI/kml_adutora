"""Prepare base DataFrame and NumPy arrays for the hydraulic engine."""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd


def _extrema_flags(z_values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    prev_z = np.roll(z_values, 1)
    next_z = np.roll(z_values, -1)
    is_high = (z_values >= prev_z) & (z_values > next_z)
    is_low = (z_values <= prev_z) & (z_values < next_z)
    is_high[[0, -1]] = False
    is_low[[0, -1]] = False
    return is_high, is_low


def build_base_dataframe(points: List[Dict]) -> pd.DataFrame:
    if len(points) < 2:
        raise ValueError("Perfil insuficiente para analise.")

    df = pd.DataFrame(points).sort_values("station_m").reset_index(drop=True)
    df["dist_trecho_m"] = df["distance_m"].astype(float)
    df["dist_acum_m"] = df["station_m"].astype(float)
    dz = df["z_terrain_m"].diff().fillna(0.0)
    dx = df["dist_trecho_m"].replace(0.0, np.nan)
    df["declividade_geom_pct"] = (dz / dx * 100.0).fillna(0.0)

    high_flags, low_flags = _extrema_flags(df["z_terrain_m"].to_numpy(dtype=float))
    df["is_high_point"] = high_flags
    df["is_low_point"] = low_flags
    return df


def build_profile_arrays(base_df: pd.DataFrame) -> Dict[str, np.ndarray]:
    return {
        "x_points_m": base_df["dist_acum_m"].to_numpy(dtype=float),
        "z_points_m": base_df["z_terrain_m"].to_numpy(dtype=float),
        "dx_segments_m": base_df["dist_trecho_m"].to_numpy(dtype=float)[1:],
        "lat_points": base_df["lat"].to_numpy(dtype=float),
        "lon_points": base_df["lon"].to_numpy(dtype=float),
        "high_point_mask": base_df["is_high_point"].to_numpy(dtype=bool),
        "low_point_mask": base_df["is_low_point"].to_numpy(dtype=bool),
    }
