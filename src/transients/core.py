"""Preliminary transient screening using simplified Joukowsky envelopes."""

from __future__ import annotations

import numpy as np

G = 9.80665
M_PER_BAR = 10.1972


def calc_delta_joukowsky(a_ms, delta_v_ms, g: float = G):
    return np.asarray(a_ms, dtype=float) * np.asarray(delta_v_ms, dtype=float) / float(g)


def calc_transient_envelope(
    pressure_points_bar,
    wave_speed_points_m_s,
    velocity_points_m_s,
    closure_factor: float = 0.35,
    trip_factor: float = 0.45,
    pumped_mask=None,
):
    pressure_points_bar = np.asarray(pressure_points_bar, dtype=float)
    wave_speed_points_m_s = np.asarray(wave_speed_points_m_s, dtype=float)
    velocity_points_m_s = np.asarray(velocity_points_m_s, dtype=float)
    if pumped_mask is None:
        pumped_mask = np.zeros(pressure_points_bar.shape[0], dtype=bool)
    pumped_mask = np.asarray(pumped_mask, dtype=bool).reshape(-1, 1)

    positive_delta_v = velocity_points_m_s * float(closure_factor)
    negative_multiplier = np.where(pumped_mask, 1.20, 0.90)
    negative_delta_v = velocity_points_m_s * float(trip_factor) * negative_multiplier

    positive_head_m = calc_delta_joukowsky(wave_speed_points_m_s, positive_delta_v)
    negative_head_m = calc_delta_joukowsky(wave_speed_points_m_s, negative_delta_v)
    positive_bar = positive_head_m / M_PER_BAR
    negative_bar = negative_head_m / M_PER_BAR

    return {
        "positive_surge_head_m": positive_head_m,
        "negative_surge_head_m": negative_head_m,
        "positive_surge_bar": positive_bar,
        "negative_surge_bar": negative_bar,
        "pressure_max_bar": pressure_points_bar + positive_bar,
        "pressure_min_bar": pressure_points_bar - negative_bar,
    }
