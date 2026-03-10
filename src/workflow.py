"""High-level orchestration for one alignment analysis."""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from .catalog import default_pipe_catalog, filter_catalog
from .devices import recommend_devices
from .elevation import enrich_elevation
from .hydraulics import (
    build_material_summary,
    build_pressure_segments,
    evaluate_catalog,
    run_hydraulic_profile,
    select_best_alternative,
    summarize_kpis,
)
from .profile import enrich_profile_attributes
from .geospatial import build_stationing


def _critical_points(detail_df: pd.DataFrame) -> pd.DataFrame:
    candidates = [
        ("Menor pressao operacional", detail_df["pressure_bar"].idxmin(), "pressure_bar"),
        ("Maior pressao operacional", detail_df["pressure_bar"].idxmax(), "pressure_bar"),
        ("Menor pressao transitoria", detail_df["pressure_min_transient_bar"].idxmin(), "pressure_min_transient_bar"),
        ("Maior pressao transitoria", detail_df["pressure_max_transient_bar"].idxmax(), "pressure_max_transient_bar"),
        ("Ponto mais alto", detail_df["z_terrain_m"].idxmax(), "z_terrain_m"),
    ]
    rows = []
    seen = set()
    for label, idx, metric in candidates:
        idx = int(idx)
        if idx in seen:
            continue
        seen.add(idx)
        row = detail_df.loc[idx]
        rows.append(
            {
                "event": label,
                "station_m": round(float(row["station_m"]), 2),
                "lat": row["lat"],
                "lon": row["lon"],
                "metric": metric,
                "value": round(float(row[metric]), 3),
            }
        )
    return pd.DataFrame(rows)


def analyze_alignment(alignment: Dict, params: Dict, catalog_df: pd.DataFrame | None = None) -> Dict:
    station_points = build_stationing(
        alignment["points"],
        station_interval_m=float(params["station_interval_m"]),
    )
    station_points = enrich_elevation(station_points, source=params["elevation_source"])
    profile_points = enrich_profile_attributes(station_points)
    profile_df = pd.DataFrame(profile_points)

    catalog = default_pipe_catalog() if catalog_df is None else catalog_df.copy()
    catalog = filter_catalog(catalog, params["enabled_materials"])
    alternatives_df = evaluate_catalog(profile_df, catalog, params)
    best_option = select_best_alternative(alternatives_df)
    detail_df = run_hydraulic_profile(profile_df, best_option, params, pump_head_m=float(best_option["pump_head_required_m"]))
    pressure_segments_df = build_pressure_segments(detail_df)
    materials_df = build_material_summary(pressure_segments_df)
    devices_df = recommend_devices(detail_df, alignment["points"], params)
    critical_points_df = _critical_points(detail_df)
    kpis = summarize_kpis(detail_df, best_option, devices_df)

    warnings: List[str] = []
    if not bool(best_option["is_feasible"]):
        warnings.append("Nenhuma alternativa atendeu integralmente aos criterios configurados. A melhor opcao abaixo e apenas indicativa.")
    if bool(best_option["subpressure_risk"]):
        warnings.append("A alternativa selecionada apresenta risco de subpressao em transientes e pede protecao complementar.")
    if float(best_option["pump_head_required_m"]) > 0.01:
        warnings.append("Foi identificada necessidade preliminar de bombeamento para garantir as pressoes minimas configuradas.")

    return {
        "alignment_id": alignment["alignment_id"],
        "detail_df": detail_df,
        "alternatives_df": alternatives_df,
        "pressure_segments_df": pressure_segments_df,
        "materials_df": materials_df,
        "devices_df": devices_df,
        "critical_points_df": critical_points_df,
        "best_option": best_option,
        "kpis": kpis,
        "warnings": warnings,
        "elevation_source": detail_df["elevation_source"].iloc[0],
    }
