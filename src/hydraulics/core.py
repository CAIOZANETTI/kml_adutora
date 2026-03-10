"""Pure vectorized hydraulic functions built around NumPy arrays."""

from __future__ import annotations

from typing import Dict

import numpy as np

G = 9.80665
M_PER_BAR = 10.1972
RHO = 1000.0


def _broadcast_to_segments(values, n_scenarios: int, n_segments: int) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 0:
        arr = np.full((n_scenarios, 1), float(arr), dtype=float)
    elif arr.ndim == 1:
        if arr.shape[0] == n_scenarios:
            arr = arr[:, None]
        elif arr.shape[0] == n_segments:
            arr = arr[None, :]
        else:
            raise ValueError(f"Shape incompativel para segmentos: {arr.shape}")
    return np.broadcast_to(arr, (n_scenarios, n_segments)).astype(float, copy=False)


def _broadcast_to_points(values, n_scenarios: int, n_points: int) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 0:
        arr = np.full((n_scenarios, 1), float(arr), dtype=float)
    elif arr.ndim == 1:
        if arr.shape[0] == n_scenarios:
            arr = arr[:, None]
        elif arr.shape[0] == n_points:
            arr = arr[None, :]
        else:
            raise ValueError(f"Shape incompativel para pontos: {arr.shape}")
    return np.broadcast_to(arr, (n_scenarios, n_points)).astype(float, copy=False)


def _segment_to_point(values_seg: np.ndarray) -> np.ndarray:
    first_column = values_seg[:, :1]
    return np.concatenate([first_column, values_seg], axis=1)


def calc_area(d_int_m):
    d_int_m = np.asarray(d_int_m, dtype=float)
    return np.pi * np.square(d_int_m) / 4.0


def calc_velocidade(q_m3s, d_int_m):
    return np.asarray(q_m3s, dtype=float) / calc_area(d_int_m)


def calc_reynolds(v_ms, d_int_m, nu_m2s):
    return np.asarray(v_ms, dtype=float) * np.asarray(d_int_m, dtype=float) / float(nu_m2s)


def calc_fator_atrito(re, eps_m, d_int_m):
    re = np.asarray(re, dtype=float)
    eps_m = np.asarray(eps_m, dtype=float)
    d_int_m = np.asarray(d_int_m, dtype=float)
    safe_re = np.maximum(re, 1.0)
    laminar = 64.0 / safe_re
    turbulent = 0.25 / np.square(np.log10(np.maximum(eps_m / np.maximum(d_int_m, 1e-9) / 3.7 + 5.74 / np.power(safe_re, 0.9), 1e-12)))
    return np.where(safe_re < 2300.0, laminar, turbulent)


def calc_perda_darcy(f, dx_m, d_int_m, v_ms, g: float = G):
    return np.asarray(f, dtype=float) * (np.asarray(dx_m, dtype=float) / np.maximum(np.asarray(d_int_m, dtype=float), 1e-9)) * (np.square(np.asarray(v_ms, dtype=float)) / (2.0 * g))


def calc_perda_localizada(k_local, v_ms, g: float = G):
    return np.asarray(k_local, dtype=float) * (np.square(np.asarray(v_ms, dtype=float)) / (2.0 * g))


def calc_hf_acumulada(hf_trecho):
    return np.cumsum(np.asarray(hf_trecho, dtype=float), axis=-1)


def calc_hgl(carga_inicial_m, hf_acum_m):
    return np.asarray(carga_inicial_m, dtype=float)[:, None] - np.asarray(hf_acum_m, dtype=float)


def calc_pressao_mca(hgl_m, cota_terreno_m):
    return np.asarray(hgl_m, dtype=float) - np.asarray(cota_terreno_m, dtype=float)


def calc_required_source_head(z_points_m, hf_points_m, minimum_pressure_head_m: float, terminal_pressure_head_m: float):
    z_points = np.asarray(z_points_m, dtype=float)[None, :]
    residual = np.full(z_points.shape[-1], float(minimum_pressure_head_m), dtype=float)
    residual[-1] = float(terminal_pressure_head_m)
    return np.max(z_points + hf_points_m + residual[None, :], axis=1)


def run_hydraulic_scenarios(base_arrays: Dict[str, np.ndarray], scenario_props: Dict[str, np.ndarray], params: Dict) -> Dict[str, np.ndarray]:
    z_points_m = np.asarray(base_arrays["z_points_m"], dtype=float)
    dx_segments_m = np.asarray(base_arrays["dx_segments_m"], dtype=float)
    n_points = z_points_m.shape[0]
    n_segments = dx_segments_m.shape[0]

    scenario_reference = np.asarray(scenario_props["diameter_m"], dtype=float)
    n_scenarios = scenario_reference.shape[0] if scenario_reference.ndim > 0 else 1

    diameter_seg_m = _broadcast_to_segments(scenario_props["diameter_m"], n_scenarios, n_segments)
    roughness_seg_m = _broadcast_to_segments(scenario_props["roughness_m"], n_scenarios, n_segments)
    cost_seg_brl_m = _broadcast_to_segments(scenario_props["cost_brl_per_m"], n_scenarios, n_segments)
    pressure_class_points_bar = _broadcast_to_points(scenario_props["pressure_class_bar"], n_scenarios, n_points)
    wave_speed_points_m_s = _broadcast_to_points(scenario_props["wave_speed_m_s"], n_scenarios, n_points)

    velocity_seg_m_s = calc_velocidade(float(params["flow_m3_s"]), diameter_seg_m)
    reynolds_seg = calc_reynolds(velocity_seg_m_s, diameter_seg_m, float(params["kinematic_viscosity_m2_s"]))
    friction_seg = calc_fator_atrito(reynolds_seg, roughness_seg_m, diameter_seg_m)
    hf_dist_seg_m = calc_perda_darcy(friction_seg, dx_segments_m[None, :], diameter_seg_m, velocity_seg_m_s)
    hf_local_seg_m = hf_dist_seg_m * float(params["localized_loss_factor"])
    hf_total_seg_m = hf_dist_seg_m + hf_local_seg_m
    hf_cum_seg_m = calc_hf_acumulada(hf_total_seg_m)
    hf_points_m = np.concatenate([np.zeros((n_scenarios, 1)), hf_cum_seg_m], axis=1)

    available_origin_head_m = float(z_points_m[0]) + float(params["upstream_residual_head_m"])
    required_source_head_m = calc_required_source_head(
        z_points_m,
        hf_points_m,
        minimum_pressure_head_m=float(params["minimum_pressure_head_m"]),
        terminal_pressure_head_m=float(params["terminal_pressure_head_m"]),
    )
    pump_head_required_m = np.maximum(0.0, required_source_head_m - available_origin_head_m)

    hgl_points_m = available_origin_head_m + pump_head_required_m[:, None] - hf_points_m
    velocity_head_seg_m = np.square(velocity_seg_m_s) / (2.0 * G)
    velocity_head_points_m = _segment_to_point(velocity_head_seg_m)
    egl_points_m = hgl_points_m + velocity_head_points_m
    pressure_head_points_m = calc_pressao_mca(hgl_points_m, z_points_m[None, :])
    pressure_points_bar = pressure_head_points_m / M_PER_BAR
    pipe_capex_brl = np.sum(cost_seg_brl_m * dx_segments_m[None, :], axis=1)
    total_headloss_m = hf_cum_seg_m[:, -1] if n_segments else np.zeros(n_scenarios, dtype=float)

    return {
        "diameter_seg_m": diameter_seg_m,
        "roughness_seg_m": roughness_seg_m,
        "cost_seg_brl_m": cost_seg_brl_m,
        "pressure_class_points_bar": pressure_class_points_bar,
        "wave_speed_points_m_s": wave_speed_points_m_s,
        "velocity_seg_m_s": velocity_seg_m_s,
        "velocity_points_m_s": velocity_head_points_m * 0.0 + _segment_to_point(velocity_seg_m_s),
        "reynolds_seg": reynolds_seg,
        "friction_seg": friction_seg,
        "hf_dist_seg_m": hf_dist_seg_m,
        "hf_local_seg_m": hf_local_seg_m,
        "hf_total_seg_m": hf_total_seg_m,
        "hf_points_m": hf_points_m,
        "pump_head_required_m": pump_head_required_m,
        "hgl_points_m": hgl_points_m,
        "egl_points_m": egl_points_m,
        "pressure_head_points_m": pressure_head_points_m,
        "pressure_points_bar": pressure_points_bar,
        "pipe_capex_brl": pipe_capex_brl,
        "total_headloss_m": total_headloss_m,
        "available_origin_head_m": np.full(n_scenarios, available_origin_head_m, dtype=float),
    }
