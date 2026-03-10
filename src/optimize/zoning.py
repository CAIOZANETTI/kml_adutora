"""Hydraulic zoning helpers for segment-level optimization."""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd


def _candidate_breakpoints(base_df: pd.DataFrame, max_zone_length_m: float) -> np.ndarray:
    x = base_df["dist_acum_m"].to_numpy(dtype=float)
    slope = base_df["declividade_geom_pct"].to_numpy(dtype=float)
    sign = np.sign(slope)
    sign_change_idx = np.where(sign[1:] * sign[:-1] < 0.0)[0] + 1
    spacing_targets = np.arange(max_zone_length_m, x[-1], max_zone_length_m, dtype=float)
    spacing_idx = np.searchsorted(x, spacing_targets)
    return np.unique(np.concatenate(([0], sign_change_idx, spacing_idx, [len(base_df) - 1]))).astype(int)


def _compress_breakpoints(candidate_idx: np.ndarray, x: np.ndarray, max_zones: int) -> np.ndarray:
    if len(candidate_idx) - 1 <= max_zones:
        return candidate_idx
    target_positions = np.linspace(0.0, x[-1], max_zones + 1)
    target_idx = np.searchsorted(x, target_positions)
    compressed = np.unique(np.concatenate(([0], target_idx, [len(x) - 1]))).astype(int)
    if compressed[0] != 0:
        compressed = np.insert(compressed, 0, 0)
    if compressed[-1] != len(x) - 1:
        compressed = np.append(compressed, len(x) - 1)
    return compressed


def build_zones(base_df: pd.DataFrame, max_zone_length_m: float = 1500.0, max_zones: int = 4) -> Dict:
    x = base_df["dist_acum_m"].to_numpy(dtype=float)
    candidate_idx = _candidate_breakpoints(base_df, max_zone_length_m=float(max_zone_length_m))
    break_idx = _compress_breakpoints(candidate_idx, x, max_zones=max(1, int(max_zones)))

    if len(break_idx) < 2:
        break_idx = np.asarray([0, len(base_df) - 1], dtype=int)

    zone_rows: List[Dict] = []
    point_zone_ids = np.zeros(len(base_df), dtype=int)
    segment_zone_ids = np.zeros(len(base_df) - 1, dtype=int)

    for zone_id in range(len(break_idx) - 1):
        start_idx = int(break_idx[zone_id])
        end_idx = int(break_idx[zone_id + 1])
        point_zone_ids[start_idx : end_idx + 1] = zone_id
        if end_idx > start_idx:
            segment_zone_ids[start_idx:end_idx] = zone_id
        zone_rows.append(
            {
                "zone_id": zone_id,
                "start_index": start_idx,
                "end_index": end_idx,
                "start_station_m": float(base_df.loc[start_idx, "dist_acum_m"]),
                "end_station_m": float(base_df.loc[end_idx, "dist_acum_m"]),
                "length_m": float(base_df.loc[end_idx, "dist_acum_m"] - base_df.loc[start_idx, "dist_acum_m"]),
            }
        )

    return {
        "zones_df": pd.DataFrame(zone_rows),
        "point_zone_ids": point_zone_ids,
        "segment_zone_ids": segment_zone_ids,
        "zone_count": len(zone_rows),
    }
