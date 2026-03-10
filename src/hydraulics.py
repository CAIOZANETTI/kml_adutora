"""Permanent-flow hydraulic screening and pipe option ranking."""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from .transients import estimate_transient

G = 9.80665
RHO = 1000.0
M_TO_BAR = 1.0 / 10.1972


def _friction_factor(reynolds: float, roughness_m: float, diameter_m: float) -> float:
    if reynolds <= 0:
        return 0.0
    if reynolds < 2300.0:
        return 64.0 / reynolds
    rel_roughness = roughness_m / max(diameter_m, 1e-9)
    return 0.25 / (
        math.log10(rel_roughness / 3.7 + 5.74 / (reynolds ** 0.9)) ** 2
    )


def _assign_pressure_classes(required_bars: Iterable[float], available_classes: List[float]) -> Tuple[List[float], bool]:
    assignments: List[float] = []
    feasible = True
    ordered_classes = sorted(float(value) for value in available_classes)
    for required in required_bars:
        assigned = next((value for value in ordered_classes if value >= float(required)), None)
        if assigned is None:
            feasible = False
            assigned = float(ordered_classes[-1]) if ordered_classes else math.nan
        assignments.append(round(float(assigned), 2))
    return assignments, feasible


def run_hydraulic_profile(profile_df: pd.DataFrame, pipe_row: Dict, params: Dict, pump_head_m: float) -> pd.DataFrame:
    df = profile_df.copy().sort_values("station_m").reset_index(drop=True)

    flow_m3_s = float(params["flow_m3_s"])
    diameter_m = float(pipe_row["inner_diameter_m"])
    roughness_m = float(pipe_row["roughness_mm"]) / 1000.0
    local_factor = float(params["localized_loss_factor"])
    kinematic_viscosity = float(params["kinematic_viscosity_m2_s"])
    start_hgl_m = float(df.loc[0, "z_terrain_m"]) + float(params["upstream_residual_head_m"]) + float(pump_head_m)

    area_m2 = math.pi * diameter_m ** 2 / 4.0
    velocity_m_s = flow_m3_s / area_m2
    reynolds = velocity_m_s * diameter_m / kinematic_viscosity
    friction_factor = _friction_factor(reynolds, roughness_m, diameter_m)
    velocity_head_m = velocity_m_s ** 2 / (2.0 * G)

    head_losses: List[float] = [0.0]
    cumulative_losses: List[float] = [0.0]
    hgl_values: List[float] = [start_hgl_m]
    egl_values: List[float] = [start_hgl_m + velocity_head_m]
    pressure_head_values: List[float] = [start_hgl_m - float(df.loc[0, "z_terrain_m"])]

    for idx in range(1, len(df)):
        length_m = float(df.loc[idx, "distance_m"])
        hf_dist = friction_factor * (length_m / diameter_m) * velocity_head_m
        hf_local = hf_dist * local_factor
        hf_total = hf_dist + hf_local
        cumulative = cumulative_losses[-1] + hf_total
        hgl = start_hgl_m - cumulative
        egl = hgl + velocity_head_m
        pressure_head = hgl - float(df.loc[idx, "z_terrain_m"])

        head_losses.append(hf_total)
        cumulative_losses.append(cumulative)
        hgl_values.append(hgl)
        egl_values.append(egl)
        pressure_head_values.append(pressure_head)

    transient = estimate_transient(
        velocity_m_s=velocity_m_s,
        wave_speed_m_s=float(pipe_row["wave_speed_m_s"]),
        event_factor=float(params["surge_event_factor"]),
    )

    pressure_bar = np.asarray(pressure_head_values, dtype=float) * M_TO_BAR
    required_class_bar = (
        np.maximum(0.0, pressure_bar + transient["surge_bar"]) * float(params["pressure_safety_factor"])
    )
    class_assignments, class_feasible = _assign_pressure_classes(
        required_class_bar,
        pipe_row["pressure_classes_bar"],
    )

    df["material"] = pipe_row["material"]
    df["dn_mm"] = int(pipe_row["dn_mm"])
    df["inner_diameter_m"] = diameter_m
    df["velocity_m_s"] = round(velocity_m_s, 4)
    df["reynolds"] = round(reynolds, 0)
    df["friction_factor"] = round(friction_factor, 5)
    df["head_loss_segment_m"] = np.round(head_losses, 4)
    df["head_loss_cumulative_m"] = np.round(cumulative_losses, 4)
    df["hgl_m"] = np.round(hgl_values, 3)
    df["egl_m"] = np.round(egl_values, 3)
    df["pressure_head_m"] = np.round(pressure_head_values, 3)
    df["pressure_bar"] = np.round(pressure_bar, 3)
    df["transient_positive_bar"] = round(transient["surge_bar"], 3)
    df["transient_negative_bar"] = round(-transient["surge_bar"], 3)
    df["pressure_max_transient_bar"] = np.round(pressure_bar + transient["surge_bar"], 3)
    df["pressure_min_transient_bar"] = np.round(pressure_bar - transient["surge_bar"], 3)
    df["required_pressure_class_bar"] = np.round(required_class_bar, 2)
    df["suggested_pressure_class_bar"] = class_assignments
    df["pump_head_m"] = round(float(pump_head_m), 3)
    df["wave_speed_m_s"] = float(pipe_row["wave_speed_m_s"])
    df["surge_head_m"] = transient["surge_head_m"]
    df["pressure_class_feasible"] = bool(class_feasible)
    return df


def required_pump_head(profile_df: pd.DataFrame, pipe_row: Dict, params: Dict) -> float:
    preview = run_hydraulic_profile(profile_df, pipe_row, params, pump_head_m=0.0)
    min_head = float(params["minimum_pressure_head_m"])
    terminal_head = float(params["terminal_pressure_head_m"])

    required_origin_head = []
    last_index = len(preview) - 1
    for idx, row in preview.iterrows():
        residual = terminal_head if idx == last_index else min_head
        required_origin_head.append(
            float(row["z_terrain_m"]) + float(row["head_loss_cumulative_m"]) + residual
        )

    available_origin_head = float(preview.loc[0, "z_terrain_m"]) + float(params["upstream_residual_head_m"])
    return round(max(0.0, max(required_origin_head) - available_origin_head), 3)


def evaluate_catalog(profile_df: pd.DataFrame, catalog_df: pd.DataFrame, params: Dict) -> pd.DataFrame:
    rows: List[Dict] = []
    total_length_m = float(profile_df["distance_m"].sum())

    for _, pipe_row in catalog_df.iterrows():
        pipe_data = pipe_row.to_dict()
        pump_head_m = required_pump_head(profile_df, pipe_data, params)
        detailed = run_hydraulic_profile(profile_df, pipe_data, params, pump_head_m=pump_head_m)

        velocity_m_s = float(detailed.loc[0, "velocity_m_s"])
        surge_bar = float(detailed.loc[0, "transient_positive_bar"])
        max_pressure_bar = float(detailed["pressure_bar"].max())
        min_pressure_bar = float(detailed["pressure_bar"].min())
        min_transient_bar = float(detailed["pressure_min_transient_bar"].min())
        max_transient_bar = float(detailed["pressure_max_transient_bar"].max())
        friction_total_m = float(detailed["head_loss_cumulative_m"].iloc[-1])

        available_classes = sorted(float(value) for value in pipe_data["pressure_classes_bar"])
        class_ok = bool(detailed["pressure_class_feasible"].all())
        class_governing_bar = float(detailed["required_pressure_class_bar"].max())
        selected_class_bar = next((value for value in available_classes if value >= class_governing_bar), available_classes[-1])

        velocity_ok = float(params["velocity_min_m_s"]) <= velocity_m_s <= float(params["velocity_max_m_s"])
        subpressure_risk = min_transient_bar < float(params["minimum_transient_pressure_bar"])
        max_pressure_risk = max_transient_bar > selected_class_bar

        pipe_capex_brl = total_length_m * float(pipe_data["cost_brl_per_m"])
        pump_power_kw = (RHO * G * float(params["flow_m3_s"]) * pump_head_m) / max(
            float(params["pump_efficiency"]), 1e-6
        ) / 1000.0
        annual_energy_cost_brl = (
            pump_power_kw
            * float(params["operating_hours_per_year"])
            * float(params["energy_cost_brl_per_kwh"])
        )
        energy_horizon_brl = annual_energy_cost_brl * float(params["energy_horizon_years"])
        device_penalty_brl = 0.0
        if subpressure_risk:
            device_penalty_brl += float(params["surge_protection_cost_brl"])
        if pump_head_m > 0.01:
            device_penalty_brl += float(params["pump_station_base_cost_brl"])
        objective_cost_brl = pipe_capex_brl + energy_horizon_brl + device_penalty_brl

        rows.append(
            {
                "material": pipe_data["material"],
                "dn_mm": int(pipe_data["dn_mm"]),
                "inner_diameter_m": float(pipe_data["inner_diameter_m"]),
                "roughness_mm": float(pipe_data["roughness_mm"]),
                "wave_speed_m_s": float(pipe_data["wave_speed_m_s"]),
                "pressure_classes_bar": pipe_data["pressure_classes_bar"],
                "cost_brl_per_m": float(pipe_data["cost_brl_per_m"]),
                "velocity_m_s": round(velocity_m_s, 3),
                "friction_total_m": round(friction_total_m, 2),
                "pump_head_required_m": round(pump_head_m, 2),
                "pump_power_kw": round(pump_power_kw, 2),
                "annual_energy_cost_brl": round(annual_energy_cost_brl, 2),
                "pipe_capex_brl": round(pipe_capex_brl, 2),
                "device_penalty_brl": round(device_penalty_brl, 2),
                "objective_cost_brl": round(objective_cost_brl, 2),
                "surge_bar": round(surge_bar, 3),
                "min_pressure_bar": round(min_pressure_bar, 3),
                "max_pressure_bar": round(max_pressure_bar, 3),
                "min_transient_bar": round(min_transient_bar, 3),
                "max_transient_bar": round(max_transient_bar, 3),
                "required_pressure_class_bar": round(class_governing_bar, 2),
                "selected_pressure_class_bar": round(selected_class_bar, 2),
                "velocity_ok": bool(velocity_ok),
                "pressure_class_ok": bool(class_ok),
                "subpressure_risk": bool(subpressure_risk),
                "max_pressure_risk": bool(max_pressure_risk),
                "is_feasible": bool(velocity_ok and class_ok and not max_pressure_risk),
            }
        )

    result = pd.DataFrame(rows)
    result = result.sort_values(
        by=["is_feasible", "subpressure_risk", "objective_cost_brl", "dn_mm"],
        ascending=[False, True, True, True],
    ).reset_index(drop=True)
    return result


def select_best_alternative(alternatives_df: pd.DataFrame) -> Dict:
    feasible = alternatives_df[alternatives_df["is_feasible"]].copy()
    if not feasible.empty:
        return feasible.iloc[0].to_dict()
    return alternatives_df.iloc[0].to_dict()


def build_pressure_segments(detail_df: pd.DataFrame) -> pd.DataFrame:
    records: List[Dict] = []
    current = None

    for _, row in detail_df.iterrows():
        klass = float(row["suggested_pressure_class_bar"])
        if current is None:
            current = {
                "material": row["material"],
                "dn_mm": int(row["dn_mm"]),
                "pressure_class_bar": klass,
                "start_station_m": float(row["station_m"]),
                "end_station_m": float(row["station_m"]),
            }
            continue

        if klass == current["pressure_class_bar"]:
            current["end_station_m"] = float(row["station_m"])
        else:
            current["length_m"] = round(current["end_station_m"] - current["start_station_m"], 2)
            records.append(current)
            current = {
                "material": row["material"],
                "dn_mm": int(row["dn_mm"]),
                "pressure_class_bar": klass,
                "start_station_m": float(row["station_m"]),
                "end_station_m": float(row["station_m"]),
            }

    if current is not None:
        current["length_m"] = round(current["end_station_m"] - current["start_station_m"], 2)
        records.append(current)

    return pd.DataFrame(records)


def build_material_summary(pressure_segments_df: pd.DataFrame) -> pd.DataFrame:
    if pressure_segments_df.empty:
        return pd.DataFrame(columns=["material", "dn_mm", "pressure_class_bar", "length_m"])
    summary = (
        pressure_segments_df.groupby(["material", "dn_mm", "pressure_class_bar"], as_index=False)["length_m"]
        .sum()
        .sort_values(["material", "dn_mm", "pressure_class_bar"])
        .reset_index(drop=True)
    )
    summary["length_m"] = summary["length_m"].round(2)
    return summary


def summarize_kpis(detail_df: pd.DataFrame, best_option: Dict, devices_df: pd.DataFrame) -> Dict:
    return {
        "total_length_m": round(float(detail_df["distance_m"].sum()), 2),
        "max_elevation_m": round(float(detail_df["z_terrain_m"].max()), 2),
        "min_pressure_bar": round(float(detail_df["pressure_bar"].min()), 2),
        "max_pressure_bar": round(float(detail_df["pressure_bar"].max()), 2),
        "pump_head_m": round(float(best_option["pump_head_required_m"]), 2),
        "velocity_m_s": round(float(best_option["velocity_m_s"]), 2),
        "objective_cost_brl": round(float(best_option["objective_cost_brl"]), 2),
        "critical_devices": int(len(devices_df)),
    }
