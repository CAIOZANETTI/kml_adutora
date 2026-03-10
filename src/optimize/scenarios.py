"""Vectorized scenario evaluation for uniform and zoned pipe layouts."""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from src.hydraulics import run_hydraulic_scenarios
from src.transients import calc_transient_envelope


def _energy_cost_brl(flow_m3_s: float, pump_head_m: np.ndarray, params: Dict) -> np.ndarray:
    pump_power_kw = (
        1000.0 * 9.80665 * float(flow_m3_s) * np.asarray(pump_head_m, dtype=float)
    ) / max(float(params["pump_efficiency"]), 1e-6) / 1000.0
    annual_energy_cost = pump_power_kw * float(params["operating_hours_per_year"]) * float(params["energy_cost_brl_per_kwh"])
    return annual_energy_cost * float(params["energy_horizon_years"])


def _transition_cost(combo_idx: np.ndarray, transition_node_cost_brl: float) -> np.ndarray:
    if combo_idx.shape[1] <= 1:
        return np.zeros(combo_idx.shape[0], dtype=float)
    transitions = np.sum(combo_idx[:, 1:] != combo_idx[:, :-1], axis=1)
    return transitions.astype(float) * float(transition_node_cost_brl)


def _scenario_summary(
    labels_df: pd.DataFrame,
    hydraulic: Dict[str, np.ndarray],
    transient: Dict[str, np.ndarray],
    params: Dict,
    pipe_capex_brl: np.ndarray,
    extra_cost_brl: np.ndarray,
) -> pd.DataFrame:
    velocity_ok = np.all(
        (hydraulic["velocity_seg_m_s"] >= float(params["velocity_min_m_s"]))
        & (hydraulic["velocity_seg_m_s"] <= float(params["velocity_max_m_s"])),
        axis=1,
    )
    class_ok = np.all(
        transient["pressure_max_bar"] <= hydraulic["pressure_class_points_bar"] + 1e-9,
        axis=1,
    )
    subpressure_risk = np.min(transient["pressure_min_bar"], axis=1) < float(params["minimum_transient_pressure_bar"])
    pump_mask = hydraulic["pump_head_required_m"] > 0.01

    energy_cost_brl = _energy_cost_brl(params["flow_m3_s"], hydraulic["pump_head_required_m"], params)
    device_penalty_brl = np.where(subpressure_risk, float(params["surge_protection_cost_brl"]), 0.0)
    device_penalty_brl += np.where(pump_mask, float(params["pump_station_base_cost_brl"]), 0.0)
    total_cost_brl = pipe_capex_brl + energy_cost_brl + device_penalty_brl + extra_cost_brl

    summary = labels_df.copy().reset_index(drop=True)
    summary["velocity_m_s"] = np.round(np.max(hydraulic["velocity_seg_m_s"], axis=1), 3)
    summary["velocity_min_seg_m_s"] = np.round(np.min(hydraulic["velocity_seg_m_s"], axis=1), 3)
    summary["velocity_max_seg_m_s"] = np.round(np.max(hydraulic["velocity_seg_m_s"], axis=1), 3)
    summary["friction_total_m"] = np.round(hydraulic["total_headloss_m"], 3)
    summary["pump_head_required_m"] = np.round(hydraulic["pump_head_required_m"], 3)
    summary["pipe_capex_brl"] = np.round(pipe_capex_brl, 2)
    summary["energy_cost_brl"] = np.round(energy_cost_brl, 2)
    summary["device_penalty_brl"] = np.round(device_penalty_brl + extra_cost_brl, 2)
    summary["objective_cost_brl"] = np.round(total_cost_brl, 2)
    summary["min_pressure_bar"] = np.round(np.min(hydraulic["pressure_points_bar"], axis=1), 3)
    summary["max_pressure_bar"] = np.round(np.max(hydraulic["pressure_points_bar"], axis=1), 3)
    summary["min_transient_bar"] = np.round(np.min(transient["pressure_min_bar"], axis=1), 3)
    summary["max_transient_bar"] = np.round(np.max(transient["pressure_max_bar"], axis=1), 3)
    summary["velocity_ok"] = velocity_ok
    summary["pressure_class_ok"] = class_ok
    summary["subpressure_risk"] = subpressure_risk
    summary["is_feasible"] = velocity_ok & class_ok
    return summary.sort_values(
        by=["is_feasible", "subpressure_risk", "objective_cost_brl"],
        ascending=[False, True, True],
    ).reset_index(drop=True)


def evaluate_uniform_catalog(base_arrays: Dict[str, np.ndarray], catalog_df: pd.DataFrame, params: Dict) -> Dict:
    props = {
        "diameter_m": catalog_df["inner_diameter_m"].to_numpy(dtype=float),
        "roughness_m": catalog_df["roughness_mm"].to_numpy(dtype=float) / 1000.0,
        "cost_brl_per_m": catalog_df["cost_brl_per_m"].to_numpy(dtype=float),
        "pressure_class_bar": catalog_df["pressure_class_bar"].to_numpy(dtype=float),
        "wave_speed_m_s": catalog_df["wave_speed_m_s"].to_numpy(dtype=float),
    }
    hydraulic = run_hydraulic_scenarios(base_arrays, props, params)
    pumped_mask = hydraulic["pump_head_required_m"] > 0.01
    transient = calc_transient_envelope(
        pressure_points_bar=hydraulic["pressure_points_bar"],
        wave_speed_points_m_s=hydraulic["wave_speed_points_m_s"],
        velocity_points_m_s=hydraulic["velocity_points_m_s"],
        closure_factor=float(params["surge_closure_factor"]),
        trip_factor=float(params["surge_trip_factor"]),
        pumped_mask=pumped_mask,
    )
    summary = _scenario_summary(
        labels_df=catalog_df[[
            "product_id",
            "manufacturer",
            "product_line",
            "material",
            "series_label",
            "dn_mm",
            "pressure_class_bar",
            "inner_diameter_m",
            "roughness_mm",
            "wave_speed_m_s",
            "cost_brl_per_m",
            "scenario_label",
            "spec_source",
            "cost_source",
            "cost_reference_date",
        ]],
        hydraulic=hydraulic,
        transient=transient,
        params=params,
        pipe_capex_brl=hydraulic["pipe_capex_brl"],
        extra_cost_brl=np.zeros(len(catalog_df), dtype=float),
    )
    return {"summary_df": summary, "hydraulic": hydraulic, "transient": transient}


def shortlist_uniform_scenarios(summary_df: pd.DataFrame, shortlist_size: int) -> pd.DataFrame:
    shortlist_size = max(2, int(shortlist_size))
    feasible = summary_df[summary_df["is_feasible"]].copy()
    if len(feasible) >= shortlist_size:
        return feasible.head(shortlist_size).reset_index(drop=True)
    return summary_df.head(shortlist_size).reset_index(drop=True)


def optimize_zoned_layout(
    base_arrays: Dict[str, np.ndarray],
    shortlist_df: pd.DataFrame,
    zoning: Dict,
    params: Dict,
) -> Dict:
    zone_count = int(zoning["zone_count"])
    max_combo_evals = int(params.get("max_combo_evals", 50000))
    n_candidates = len(shortlist_df)
    while zone_count > 0 and (n_candidates ** zone_count) > max_combo_evals and n_candidates > 2:
        n_candidates -= 1
    shortlist_df = shortlist_df.head(n_candidates).reset_index(drop=True)
    grid = np.indices((n_candidates,) * zone_count).reshape(zone_count, -1).T
    segment_zone_ids = zoning["segment_zone_ids"]
    point_zone_ids = zoning["point_zone_ids"]

    product_ids = shortlist_df["product_id"].to_numpy()
    segment_choice_idx = grid[:, segment_zone_ids]
    point_choice_idx = grid[:, point_zone_ids]

    props = {
        "diameter_m": shortlist_df["inner_diameter_m"].to_numpy(dtype=float)[segment_choice_idx],
        "roughness_m": shortlist_df["roughness_mm"].to_numpy(dtype=float)[segment_choice_idx] / 1000.0,
        "cost_brl_per_m": shortlist_df["cost_brl_per_m"].to_numpy(dtype=float)[segment_choice_idx],
        "pressure_class_bar": shortlist_df["pressure_class_bar"].to_numpy(dtype=float)[point_choice_idx],
        "wave_speed_m_s": shortlist_df["wave_speed_m_s"].to_numpy(dtype=float)[point_choice_idx],
    }
    hydraulic = run_hydraulic_scenarios(base_arrays, props, params)
    pumped_mask = hydraulic["pump_head_required_m"] > 0.01
    transient = calc_transient_envelope(
        pressure_points_bar=hydraulic["pressure_points_bar"],
        wave_speed_points_m_s=hydraulic["wave_speed_points_m_s"],
        velocity_points_m_s=hydraulic["velocity_points_m_s"],
        closure_factor=float(params["surge_closure_factor"]),
        trip_factor=float(params["surge_trip_factor"]),
        pumped_mask=pumped_mask,
    )

    combo_labels = pd.DataFrame({
        "combo_id": np.arange(grid.shape[0], dtype=int),
        "product_ids": [" | ".join(product_ids[idx] for idx in combo) for combo in grid],
        "zone_signature": [" | ".join(shortlist_df.loc[idx, "scenario_label"] for idx in combo) for combo in grid],
    })
    dx_seg = base_arrays["dx_segments_m"]
    pipe_capex = np.sum(props["cost_brl_per_m"] * dx_seg[None, :], axis=1)
    extra_cost = _transition_cost(grid, float(params["transition_node_cost_brl"]))
    summary = _scenario_summary(combo_labels, hydraulic, transient, params, pipe_capex, extra_cost)
    summary["zone_count"] = zone_count

    best_row = summary.iloc[0]
    best_combo = grid[int(best_row["combo_id"])]
    return {
        "summary_df": summary,
        "hydraulic": hydraulic,
        "transient": transient,
        "best_combo": best_combo,
        "grid": grid,
    }
