"""Default preliminary pipe catalog for adutora screening."""

from __future__ import annotations

from typing import Iterable, List

import pandas as pd


def default_pipe_catalog() -> pd.DataFrame:
    rows = [
        {
            "material": "PVC-O",
            "dn_mm": 150,
            "inner_diameter_m": 0.146,
            "roughness_mm": 0.010,
            "wave_speed_m_s": 340.0,
            "cost_brl_per_m": 160.0,
            "pressure_classes_bar": [10.0, 12.5, 16.0, 20.0],
        },
        {
            "material": "PVC-O",
            "dn_mm": 200,
            "inner_diameter_m": 0.194,
            "roughness_mm": 0.010,
            "wave_speed_m_s": 340.0,
            "cost_brl_per_m": 215.0,
            "pressure_classes_bar": [10.0, 12.5, 16.0, 20.0],
        },
        {
            "material": "PVC-O",
            "dn_mm": 250,
            "inner_diameter_m": 0.242,
            "roughness_mm": 0.010,
            "wave_speed_m_s": 340.0,
            "cost_brl_per_m": 295.0,
            "pressure_classes_bar": [10.0, 12.5, 16.0, 20.0],
        },
        {
            "material": "PVC-O",
            "dn_mm": 300,
            "inner_diameter_m": 0.290,
            "roughness_mm": 0.010,
            "wave_speed_m_s": 340.0,
            "cost_brl_per_m": 395.0,
            "pressure_classes_bar": [10.0, 12.5, 16.0, 20.0],
        },
        {
            "material": "FoFo",
            "dn_mm": 150,
            "inner_diameter_m": 0.154,
            "roughness_mm": 0.260,
            "wave_speed_m_s": 980.0,
            "cost_brl_per_m": 320.0,
            "pressure_classes_bar": [20.0, 25.0, 40.0],
        },
        {
            "material": "FoFo",
            "dn_mm": 200,
            "inner_diameter_m": 0.203,
            "roughness_mm": 0.260,
            "wave_speed_m_s": 980.0,
            "cost_brl_per_m": 415.0,
            "pressure_classes_bar": [20.0, 25.0, 40.0],
        },
        {
            "material": "FoFo",
            "dn_mm": 250,
            "inner_diameter_m": 0.254,
            "roughness_mm": 0.260,
            "wave_speed_m_s": 980.0,
            "cost_brl_per_m": 560.0,
            "pressure_classes_bar": [20.0, 25.0, 40.0],
        },
        {
            "material": "FoFo",
            "dn_mm": 300,
            "inner_diameter_m": 0.305,
            "roughness_mm": 0.260,
            "wave_speed_m_s": 980.0,
            "cost_brl_per_m": 720.0,
            "pressure_classes_bar": [20.0, 25.0, 40.0],
        },
        {
            "material": "Aco carbono",
            "dn_mm": 150,
            "inner_diameter_m": 0.152,
            "roughness_mm": 0.045,
            "wave_speed_m_s": 1100.0,
            "cost_brl_per_m": 355.0,
            "pressure_classes_bar": [16.0, 20.0, 25.0, 40.0],
        },
        {
            "material": "Aco carbono",
            "dn_mm": 200,
            "inner_diameter_m": 0.202,
            "roughness_mm": 0.045,
            "wave_speed_m_s": 1100.0,
            "cost_brl_per_m": 470.0,
            "pressure_classes_bar": [16.0, 20.0, 25.0, 40.0],
        },
        {
            "material": "Aco carbono",
            "dn_mm": 250,
            "inner_diameter_m": 0.252,
            "roughness_mm": 0.045,
            "wave_speed_m_s": 1100.0,
            "cost_brl_per_m": 630.0,
            "pressure_classes_bar": [16.0, 20.0, 25.0, 40.0],
        },
        {
            "material": "Aco carbono",
            "dn_mm": 300,
            "inner_diameter_m": 0.302,
            "roughness_mm": 0.045,
            "wave_speed_m_s": 1100.0,
            "cost_brl_per_m": 815.0,
            "pressure_classes_bar": [16.0, 20.0, 25.0, 40.0],
        },
    ]
    return pd.DataFrame(rows)


def filter_catalog(catalog: pd.DataFrame, enabled_materials: Iterable[str]) -> pd.DataFrame:
    enabled_materials = list(enabled_materials)
    if not enabled_materials:
        return catalog.copy()
    return catalog[catalog["material"].isin(enabled_materials)].reset_index(drop=True)
