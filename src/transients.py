"""Preliminary transient screening based on a simplified Joukowsky envelope."""

from __future__ import annotations

from typing import Dict

G = 9.80665


def estimate_transient(velocity_m_s: float, wave_speed_m_s: float, event_factor: float = 0.35) -> Dict[str, float]:
    delta_v = max(0.0, float(velocity_m_s) * float(event_factor))
    surge_head_m = float(wave_speed_m_s) * delta_v / G
    surge_bar = surge_head_m / 10.1972
    return {
        "delta_v_m_s": round(delta_v, 3),
        "surge_head_m": round(surge_head_m, 3),
        "surge_bar": round(surge_bar, 3),
    }
