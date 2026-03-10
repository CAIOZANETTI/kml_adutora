"""End-to-end orchestration for the vectorized hydraulic engine."""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from src.assets import filter_catalog, load_pipe_catalog
from src.geo import build_base_dataframe, build_profile_arrays, build_stationing, enrich_elevation
from .rules import (
    build_detail_dataframe,
    build_material_summary,
    build_zone_solution_df,
    critical_points,
    recommend_devices,
)
from .scenarios import evaluate_uniform_catalog, optimize_zoned_layout, shortlist_uniform_scenarios
from .zoning import build_zones


def _warnings(best_layout: pd.Series, uniform_best: pd.Series) -> List[str]:
    warnings: List[str] = []
    if not bool(best_layout["is_feasible"]):
        warnings.append("Nenhuma combinacao por trechos atendeu integralmente aos criterios. A melhor solucao abaixo e indicativa.")
    if bool(best_layout["subpressure_risk"]):
        warnings.append("A solucao otimizada por trechos ainda apresenta risco de subpressao em transientes e pede protecao complementar.")
    if float(best_layout["pump_head_required_m"]) > 0.01:
        warnings.append("Foi identificada necessidade preliminar de bombeamento para garantir as pressoes minimas configuradas.")
    if float(best_layout["objective_cost_brl"]) < float(uniform_best["objective_cost_brl"]):
        warnings.append("A otimiza\u00e7\u00e3o por trechos melhorou o custo tecnico-economico em relacao \u00e0 melhor solucao uniforme.")
    return warnings


def analyze_alignment(alignment: Dict, params: Dict, catalog_df: pd.DataFrame | None = None) -> Dict:
    station_points = build_stationing(alignment["points"], station_interval_m=float(params["station_interval_m"]))
    station_points = enrich_elevation(station_points, source=params["elevation_source"])
    base_df = build_base_dataframe(station_points)
    base_arrays = build_profile_arrays(base_df)

    catalog = load_pipe_catalog() if catalog_df is None else catalog_df.copy()
    catalog = filter_catalog(catalog, params["enabled_materials"])

    uniform_eval = evaluate_uniform_catalog(base_arrays, catalog, params)
    uniform_df = uniform_eval["summary_df"]
    uniform_best = uniform_df.iloc[0]
    shortlist_df = shortlist_uniform_scenarios(uniform_df, shortlist_size=int(params["shortlist_size"]))

    zoning = build_zones(
        base_df,
        max_zone_length_m=float(params["max_zone_length_m"]),
        max_zones=int(params["max_zones"]),
    )
    zoned_eval = optimize_zoned_layout(base_arrays, shortlist_df, zoning, params)
    zoned_df = zoned_eval["summary_df"]
    best_layout = zoned_df.iloc[0]

    best_combo_position = int(best_layout["combo_id"])
    best_combo = zoned_eval["best_combo"]
    zone_solution_df = build_zone_solution_df(zoning["zones_df"], best_combo, shortlist_df)
    detail_df = build_detail_dataframe(
        base_df=base_df,
        zoning=zoning,
        shortlist_df=shortlist_df,
        combo_idx=best_combo,
        hydraulic=zoned_eval["hydraulic"],
        transient=zoned_eval["transient"],
        combo_position=best_combo_position,
    )
    materials_df = build_material_summary(zone_solution_df)
    devices_df = recommend_devices(detail_df, alignment["points"], params)
    critical_points_df = critical_points(detail_df)

    kpis = {
        "total_length_m": round(float(detail_df["dist_trecho_m"].sum()), 2),
        "min_pressure_bar": round(float(detail_df["pressure_bar"].min()), 2),
        "max_pressure_bar": round(float(detail_df["pressure_bar"].max()), 2),
        "min_transient_bar": round(float(detail_df["pressure_min_transient_bar"].min()), 2),
        "max_transient_bar": round(float(detail_df["pressure_max_transient_bar"].max()), 2),
        "pump_head_m": round(float(best_layout["pump_head_required_m"]), 2),
        "objective_cost_brl": round(float(best_layout["objective_cost_brl"]), 2),
        "zone_count": int(len(zone_solution_df)),
    }

    return {
        "alignment_id": alignment["alignment_id"],
        "base_df": base_df,
        "detail_df": detail_df,
        "uniform_df": uniform_df,
        "shortlist_df": shortlist_df,
        "zoned_df": zoned_df,
        "zone_solution_df": zone_solution_df,
        "materials_df": materials_df,
        "devices_df": devices_df,
        "critical_points_df": critical_points_df,
        "catalog_df": catalog,
        "kpis": kpis,
        "best_layout": best_layout.to_dict(),
        "uniform_best": uniform_best.to_dict(),
        "warnings": _warnings(best_layout, uniform_best),
        "zoning": zoning,
        "elevation_source": detail_df["elevation_source"].iloc[0],
    }
