"""Technical rules for devices, alerts, and result consolidation."""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from src.geo import find_bends


def build_zone_solution_df(zones_df: pd.DataFrame, combo_idx: np.ndarray, shortlist_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for zone_id, shortlist_pos in enumerate(combo_idx.tolist()):
        zone_row = zones_df.iloc[zone_id]
        product_row = shortlist_df.iloc[int(shortlist_pos)]
        rows.append(
            {
                "zone_id": int(zone_id),
                "start_station_m": float(zone_row["start_station_m"]),
                "end_station_m": float(zone_row["end_station_m"]),
                "length_m": float(zone_row["length_m"]),
                "product_id": product_row["product_id"],
                "material": product_row["material"],
                "product_line": product_row["product_line"],
                "series_label": product_row["series_label"],
                "dn_mm": int(product_row["dn_mm"]),
                "pressure_class_bar": float(product_row["pressure_class_bar"]),
                "cost_brl_per_m": float(product_row["cost_brl_per_m"]),
            }
        )
    zone_solution_df = pd.DataFrame(rows)
    if zone_solution_df.empty:
        return zone_solution_df

    merged_rows = []
    current = zone_solution_df.iloc[0].to_dict()
    for _, row in zone_solution_df.iloc[1:].iterrows():
        same_product = (
            row["product_id"] == current["product_id"]
            and int(row["dn_mm"]) == int(current["dn_mm"])
            and float(row["pressure_class_bar"]) == float(current["pressure_class_bar"])
        )
        if same_product:
            current["end_station_m"] = float(row["end_station_m"])
            current["length_m"] = float(current["end_station_m"]) - float(current["start_station_m"])
        else:
            merged_rows.append(current)
            current = row.to_dict()
    merged_rows.append(current)
    merged_df = pd.DataFrame(merged_rows)
    merged_df["zone_id"] = np.arange(len(merged_df), dtype=int)
    return merged_df.reset_index(drop=True)


def build_material_summary(zone_solution_df: pd.DataFrame) -> pd.DataFrame:
    if zone_solution_df.empty:
        return pd.DataFrame(columns=["material", "product_line", "dn_mm", "pressure_class_bar", "length_m"])
    summary = (
        zone_solution_df.groupby(["material", "product_line", "dn_mm", "pressure_class_bar"], as_index=False)["length_m"]
        .sum()
        .sort_values(["material", "dn_mm", "pressure_class_bar"])
        .reset_index(drop=True)
    )
    summary["length_m"] = summary["length_m"].round(2)
    return summary


def build_detail_dataframe(
    base_df: pd.DataFrame,
    zoning: Dict,
    shortlist_df: pd.DataFrame,
    combo_idx: np.ndarray,
    hydraulic: Dict[str, np.ndarray],
    transient: Dict[str, np.ndarray],
    combo_position: int,
) -> pd.DataFrame:
    detail_df = base_df.copy()
    point_choice_idx = combo_idx[zoning["point_zone_ids"]]
    segment_choice_idx = combo_idx[zoning["segment_zone_ids"]]
    point_products = shortlist_df.iloc[point_choice_idx].reset_index(drop=True)
    segment_products = shortlist_df.iloc[segment_choice_idx].reset_index(drop=True)

    velocity_points = hydraulic["velocity_points_m_s"][combo_position]
    velocity_seg = hydraulic["velocity_seg_m_s"][combo_position]
    hf_seg = hydraulic["hf_total_seg_m"][combo_position]

    detail_df["zone_id"] = zoning["point_zone_ids"]
    detail_df["product_id"] = point_products["product_id"].to_numpy()
    detail_df["material"] = point_products["material"].to_numpy()
    detail_df["product_line"] = point_products["product_line"].to_numpy()
    detail_df["series_label"] = point_products["series_label"].to_numpy()
    detail_df["dn_mm"] = point_products["dn_mm"].to_numpy(dtype=int)
    detail_df["pressure_class_bar"] = point_products["pressure_class_bar"].to_numpy(dtype=float)
    detail_df["wave_speed_m_s"] = hydraulic["wave_speed_points_m_s"][combo_position]
    detail_df["velocity_m_s"] = velocity_points
    detail_df["reynolds"] = np.concatenate([[hydraulic["reynolds_seg"][combo_position, 0]], hydraulic["reynolds_seg"][combo_position]])
    detail_df["friction_factor"] = np.concatenate([[hydraulic["friction_seg"][combo_position, 0]], hydraulic["friction_seg"][combo_position]])
    detail_df["head_loss_segment_m"] = np.concatenate([[0.0], hf_seg])
    detail_df["head_loss_cumulative_m"] = hydraulic["hf_points_m"][combo_position]
    detail_df["hgl_m"] = hydraulic["hgl_points_m"][combo_position]
    detail_df["egl_m"] = hydraulic["egl_points_m"][combo_position]
    detail_df["pressure_head_m"] = hydraulic["pressure_head_points_m"][combo_position]
    detail_df["pressure_bar"] = hydraulic["pressure_points_bar"][combo_position]
    detail_df["pressure_max_transient_bar"] = transient["pressure_max_bar"][combo_position]
    detail_df["pressure_min_transient_bar"] = transient["pressure_min_bar"][combo_position]
    detail_df["positive_surge_bar"] = transient["positive_surge_bar"][combo_position]
    detail_df["negative_surge_bar"] = transient["negative_surge_bar"][combo_position]
    detail_df["pump_head_required_m"] = hydraulic["pump_head_required_m"][combo_position]
    detail_df["segment_material_upstream"] = np.concatenate([[segment_products.iloc[0]["material"]], segment_products["material"].to_numpy()])
    detail_df["segment_dn_upstream"] = np.concatenate([[segment_products.iloc[0]["dn_mm"]], segment_products["dn_mm"].to_numpy()])
    return detail_df


def recommend_devices(detail_df: pd.DataFrame, raw_points: List[Dict], params: Dict) -> pd.DataFrame:
    records: List[Dict] = []

    for _, row in detail_df[detail_df["is_high_point"]].iterrows():
        records.append({
            "type": "Ventosa",
            "station_m": round(float(row["dist_acum_m"]), 2),
            "lat": row["lat"],
            "lon": row["lon"],
            "reason": "Ponto alto do perfil altimetrico.",
        })
    for _, row in detail_df[detail_df["is_low_point"]].iterrows():
        records.append({
            "type": "Descarga",
            "station_m": round(float(row["dist_acum_m"]), 2),
            "lat": row["lat"],
            "lon": row["lon"],
            "reason": "Ponto baixo com potencial de drenagem operacional.",
        })

    spacing = float(params["block_valve_spacing_m"])
    next_station = spacing
    total_length = float(detail_df["dist_acum_m"].max())
    while next_station < total_length:
        idx = (detail_df["dist_acum_m"] - next_station).abs().idxmin()
        row = detail_df.loc[idx]
        records.append({
            "type": "Valvula de bloqueio",
            "station_m": round(float(row["dist_acum_m"]), 2),
            "lat": row["lat"],
            "lon": row["lon"],
            "reason": f"Setorizacao preliminar a cada {int(spacing)} m.",
        })
        next_station += spacing

    bends = find_bends(raw_points, min_deflection_deg=float(params["anchor_min_deflection_deg"]))
    for bend in bends:
        records.append({
            "type": "Bloco de ancoragem",
            "station_m": bend["station_m"],
            "lat": bend["lat"],
            "lon": bend["lon"],
            "reason": f"Mudanca de direcao aproximada de {bend['deflection_deg']} graus.",
        })

    if float(detail_df["pump_head_required_m"].max()) > 0.01:
        first = detail_df.iloc[0]
        records.append({
            "type": "Estacao de bombeamento",
            "station_m": 0.0,
            "lat": first["lat"],
            "lon": first["lon"],
            "reason": "Carga suplementar necessaria para atender as pressoes minimas.",
        })
        records.append({
            "type": "Valvula de retencao",
            "station_m": 0.0,
            "lat": first["lat"],
            "lon": first["lon"],
            "reason": "Protecao associada ao trecho com bombeamento.",
        })

    if float(detail_df["pressure_min_transient_bar"].min()) < float(params["minimum_transient_pressure_bar"]):
        critical = detail_df.loc[detail_df["pressure_min_transient_bar"].idxmin()]
        records.append({
            "type": "RHO / amortecimento transitorio",
            "station_m": round(float(critical["dist_acum_m"]), 2),
            "lat": critical["lat"],
            "lon": critical["lon"],
            "reason": "Envelope transitorio indica subpressao relevante.",
        })

    static_vacuum_mask = detail_df["pressure_bar"] < 0.0
    if static_vacuum_mask.any():
        critical = detail_df.loc[detail_df["pressure_bar"].idxmin()]
        records.append({
            "type": "Subpressao estatica / vacuo",
            "station_m": round(float(critical["dist_acum_m"]), 2),
            "lat": critical["lat"],
            "lon": critical["lon"],
            "reason": (
                f"Pressao estatica negativa ({critical['pressure_bar']:.2f} bar) em regime permanente. "
                "Revisar carga de montante, acrescentar bombeamento ou instalar ventosa anti-vacuo."
            ),
        })

    if float(detail_df["pressure_max_transient_bar"].max()) > float(detail_df["pressure_class_bar"].max()):
        critical = detail_df.loc[detail_df["pressure_max_transient_bar"].idxmax()]
        records.append({
            "type": "Valvula de alivio / protecao",
            "station_m": round(float(critical["dist_acum_m"]), 2),
            "lat": critical["lat"],
            "lon": critical["lon"],
            "reason": "Sobrepressao transitoria acima da classe local do tubo.",
        })

    devices_df = pd.DataFrame(records)
    if devices_df.empty:
        return pd.DataFrame(columns=["type", "station_m", "lat", "lon", "reason"])
    return devices_df.sort_values(["station_m", "type"]).drop_duplicates(["type", "station_m"]).reset_index(drop=True)


def critical_points(detail_df: pd.DataFrame) -> pd.DataFrame:
    events = [
        ("Menor pressao operacional", "pressure_bar", "idxmin"),
        ("Maior pressao operacional", "pressure_bar", "idxmax"),
        ("Menor pressao transitoria", "pressure_min_transient_bar", "idxmin"),
        ("Maior pressao transitoria", "pressure_max_transient_bar", "idxmax"),
        ("Ponto mais alto", "z_terrain_m", "idxmax"),
    ]
    rows = []
    seen = set()
    for label, column, reducer in events:
        idx = int(getattr(detail_df[column], reducer)())
        if idx in seen:
            continue
        seen.add(idx)
        row = detail_df.loc[idx]
        rows.append({
            "event": label,
            "station_m": round(float(row["dist_acum_m"]), 2),
            "lat": row["lat"],
            "lon": row["lon"],
            "metric": column,
            "value": round(float(row[column]), 3),
        })
    return pd.DataFrame(rows)
