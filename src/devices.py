"""Rule-based preliminary recommendations for auxiliary devices."""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from .geospatial import find_bends


def recommend_devices(detail_df: pd.DataFrame, raw_points: List[Dict], params: Dict) -> pd.DataFrame:
    records: List[Dict] = []

    for _, row in detail_df[detail_df["is_high_point"]].iterrows():
        records.append(
            {
                "type": "Ventosa",
                "station_m": round(float(row["station_m"]), 2),
                "lat": row["lat"],
                "lon": row["lon"],
                "reason": "Ponto alto geometrico do perfil.",
            }
        )

    for _, row in detail_df[detail_df["is_low_point"]].iterrows():
        records.append(
            {
                "type": "Descarga",
                "station_m": round(float(row["station_m"]), 2),
                "lat": row["lat"],
                "lon": row["lon"],
                "reason": "Ponto baixo geometrico com potencial de drenagem e limpeza.",
            }
        )

    spacing = float(params["block_valve_spacing_m"])
    next_station = spacing
    total_length = float(detail_df["station_m"].max())
    while next_station < total_length:
        idx = (detail_df["station_m"] - next_station).abs().idxmin()
        row = detail_df.loc[idx]
        records.append(
            {
                "type": "Valvula de bloqueio",
                "station_m": round(float(row["station_m"]), 2),
                "lat": row["lat"],
                "lon": row["lon"],
                "reason": f"Setorizacao preliminar a cada {int(spacing)} m.",
            }
        )
        next_station += spacing

    bends = find_bends(raw_points, min_deflection_deg=float(params["anchor_min_deflection_deg"]))
    for bend in bends:
        records.append(
            {
                "type": "Bloco de ancoragem",
                "station_m": bend["station_m"],
                "lat": bend["lat"],
                "lon": bend["lon"],
                "reason": f"Mudanca de direcao aproximada de {bend['deflection_deg']} graus.",
            }
        )

    if float(detail_df["pump_head_m"].max()) > 0.01:
        first = detail_df.iloc[0]
        records.append(
            {
                "type": "Estacao de bombeamento",
                "station_m": 0.0,
                "lat": first["lat"],
                "lon": first["lon"],
                "reason": "Carga adicional necessaria para garantir as pressoes minimas ao longo da linha.",
            }
        )
        records.append(
            {
                "type": "Valvula de retencao",
                "station_m": 0.0,
                "lat": first["lat"],
                "lon": first["lon"],
                "reason": "Protecao operacional associada ao trecho com bombeamento.",
            }
        )

    if float(detail_df["pressure_min_transient_bar"].min()) < float(params["minimum_transient_pressure_bar"]):
        critical_idx = detail_df["pressure_min_transient_bar"].idxmin()
        critical = detail_df.loc[critical_idx]
        records.append(
            {
                "type": "RHO / protecao contra transientes",
                "station_m": round(float(critical["station_m"]), 2),
                "lat": critical["lat"],
                "lon": critical["lon"],
                "reason": "Envelope transitorio indica subpressao relevante e necessidade de amortecimento.",
            }
        )

    if float(detail_df["pressure_max_transient_bar"].max()) > float(detail_df["suggested_pressure_class_bar"].max()):
        critical_idx = detail_df["pressure_max_transient_bar"].idxmax()
        critical = detail_df.loc[critical_idx]
        records.append(
            {
                "type": "Valvula de alivio / protecao",
                "station_m": round(float(critical["station_m"]), 2),
                "lat": critical["lat"],
                "lon": critical["lon"],
                "reason": "Envelope transitorio acima da classe sugerida no ponto critico.",
            }
        )

    devices_df = pd.DataFrame(records)
    if devices_df.empty:
        return pd.DataFrame(columns=["type", "station_m", "lat", "lon", "reason"])
    devices_df = devices_df.sort_values(["station_m", "type"]).drop_duplicates(
        subset=["type", "station_m"],
        keep="first",
    )
    return devices_df.reset_index(drop=True)
