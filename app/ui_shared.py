"""Shared state, caching, and UI helpers for the staged Streamlit flow."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import (
    analyze_alignment,
    load_pipe_catalog,
    load_pipe_catalog_payload,
    load_reference_library,
    load_reference_library_payload,
)
from src.geo import build_base_dataframe, build_stationing, enrich_elevation, parse_multiple_kml
from src.geo.elevation import ElevationAPIError

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_KML = ROOT / "sample" / "adutora_demo.kml"

STAGE_ORDER = [
    "Tracado",
    "Diagnostico",
    "Regime permanente",
    "Transientes e protecao",
    "Cenarios de tubulacao",
    "Solucao final",
]

DEFAULT_INPUTS = {
    "trace": {
        "case_name": "Estudo de adutora",
        "flow_l_s": 120.0,
        "operation_mode": "Gravidade",
        "station_interval_m": 50.0,
        "elevation_source": "auto",
    },
    "diagnostic": {
        "upstream_head_m": 25.0,
        "minimum_head_m": 8.0,
        "terminal_head_m": 12.0,
        "max_operating_pressure_bar": 16.0,
    },
    "steady": {
        "localized_loss_factor": 0.10,
        "velocity_min_m_s": 0.6,
        "velocity_max_m_s": 2.5,
        "friction_method": "Darcy-Weisbach",
    },
    "transient": {
        "surge_closure_factor": 0.35,
        "surge_trip_factor": 0.45,
        "minimum_transient_pressure_bar": -0.2,
        "block_valve_spacing_m": 1500.0,
        "anchor_min_deflection_deg": 20.0,
    },
    "scenarios": {
        "enabled_materials": [],
        "mix_materials_by_zone": True,
        "shortlist_size": 5,
        "max_zone_length_m": 1500.0,
        "max_zones": 4,
        "recommendation_priority": "Equilibrio",
        "pump_efficiency": 0.72,
        "energy_cost_brl_per_kwh": 0.85,
        "energy_horizon_years": 5.0,
        "operating_hours_per_year": 6000.0,
        "pump_station_base_cost_brl": 250000.0,
        "surge_protection_cost_brl": 120000.0,
        "transition_node_cost_brl": 20000.0,
    },
}


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ink: #1e2a39;
            --sand: #f4eee4;
            --paper: #fffaf3;
            --clay: #c86f4a;
            --ocean: #145da0;
            --night: #213547;
            --sage: #5f7b62;
            --line: #e3d8c6;
        }
        html, body, [class*="css"] {
            font-family: "Trebuchet MS", "Lucida Sans Unicode", sans-serif;
            color: var(--ink);
        }
        h1, h2, h3 {
            font-family: "Palatino Linotype", "Book Antiqua", serif;
            letter-spacing: -0.02em;
        }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(200,111,74,0.12), transparent 32%),
                radial-gradient(circle at top right, rgba(20,93,160,0.10), transparent 28%),
                linear-gradient(180deg, #fff8ef 0%, #f7f0e6 100%);
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #fcf5ea 0%, #f3eadf 100%);
            border-right: 1px solid var(--line);
        }
        .hero {
            background: linear-gradient(135deg, rgba(30,42,57,0.96) 0%, rgba(20,93,160,0.90) 58%, rgba(95,123,98,0.84) 100%);
            color: white;
            padding: 1.7rem 2rem;
            border-radius: 20px;
            margin-bottom: 1.1rem;
            box-shadow: 0 18px 45px rgba(33,53,71,0.18);
        }
        .page-note {
            background: rgba(255,250,243,0.92);
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            margin-bottom: 1rem;
        }
        [data-testid="metric-container"] {
            background: rgba(255,250,243,0.92);
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 0.9rem 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_sample_files() -> tuple[tuple[str, bytes], ...]:
    return ((SAMPLE_KML.name, SAMPLE_KML.read_bytes()),)


@st.cache_data(show_spinner=False)
def parse_files_cached(files_payload: tuple[tuple[str, bytes], ...]) -> list[dict]:
    files = [{"name": name, "content": content} for name, content in files_payload]
    return parse_multiple_kml(files)


@st.cache_data(show_spinner=False)
def _build_profile_cached(
    files_payload: tuple[tuple[str, bytes], ...],
    alignment_id: str,
    station_interval_m: float,
    elevation_source: str,
) -> pd.DataFrame:
    """Builds the interpolated + elevation-enriched base DataFrame.

    Cached independently so both the trace preview and the full analysis
    share the same result, avoiding a redundant Open-Meteo API call.
    """
    alignments = parse_files_cached(files_payload)
    alignment = next(item for item in alignments if item["alignment_id"] == alignment_id)
    station_points = build_stationing(alignment["points"], station_interval_m=float(station_interval_m))
    station_points = enrich_elevation(station_points, source=elevation_source)
    return build_base_dataframe(station_points)


@st.cache_data(show_spinner=False)
def prepare_trace_preview_cached(files_payload: tuple[tuple[str, bytes], ...], alignment_id: str, params_json: str) -> dict:
    alignments = parse_files_cached(files_payload)
    alignment = next(item for item in alignments if item["alignment_id"] == alignment_id)
    params = json.loads(params_json)
    base_df = _build_profile_cached(files_payload, alignment_id, float(params["station_interval_m"]), params["elevation_source"])
    return {
        "alignment_id": alignment_id,
        "base_df": base_df,
        "raw_vertices": len(alignment["points"]),
        "interpolated_points": len(base_df),
        "total_length_m": float(base_df["dist_acum_m"].max()),
        "min_elevation_m": float(base_df["z_terrain_m"].min()),
        "max_elevation_m": float(base_df["z_terrain_m"].max()),
        "elevation_source": str(base_df["elevation_source"].iloc[0]),
    }


@st.cache_data(show_spinner=False)
def run_full_analysis_cached(files_payload: tuple[tuple[str, bytes], ...], alignment_id: str, params_json: str) -> dict:
    alignments = parse_files_cached(files_payload)
    alignment = next(item for item in alignments if item["alignment_id"] == alignment_id)
    params = json.loads(params_json)
    base_df = _build_profile_cached(files_payload, alignment_id, float(params["station_interval_m"]), params["elevation_source"])
    return analyze_alignment(alignment, params, base_df=base_df)


def init_state() -> None:
    defaults = {
        "upload_version": 0,
        "files_payload": tuple(),
        "alignments": [],
        "selected_alignment": None,
        "trace_preview": None,
        "analysis_result": None,
        "stage_status": {stage: False for stage in STAGE_ORDER},
        "trace_inputs": DEFAULT_INPUTS["trace"].copy(),
        "diagnostic_inputs": DEFAULT_INPUTS["diagnostic"].copy(),
        "steady_inputs": DEFAULT_INPUTS["steady"].copy(),
        "transient_inputs": DEFAULT_INPUTS["transient"].copy(),
        "scenario_inputs": DEFAULT_INPUTS["scenarios"].copy(),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if not st.session_state.scenario_inputs["enabled_materials"]:
        st.session_state.scenario_inputs["enabled_materials"] = sorted(load_pipe_catalog()["material"].unique())


def reset_case() -> None:
    upload_version = int(st.session_state.get("upload_version", 0)) + 1
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_state()
    st.session_state.upload_version = upload_version


def invalidate_after(stage_name: str) -> None:
    if stage_name not in STAGE_ORDER:
        return
    start_idx = STAGE_ORDER.index(stage_name)
    for downstream_stage in STAGE_ORDER[start_idx + 1 :]:
        st.session_state.stage_status[downstream_stage] = False
    if stage_name == "Tracado":
        st.session_state.analysis_result = None
    if stage_name in {"Diagnostico", "Regime permanente", "Transientes e protecao", "Cenarios de tubulacao"}:
        st.session_state.analysis_result = None


def update_alignment_cache(files_payload: tuple[tuple[str, bytes], ...]) -> None:
    previous_payload = st.session_state.files_payload
    payload_changed = files_payload != previous_payload
    st.session_state.files_payload = files_payload
    if not files_payload:
        st.session_state.alignments = []
        st.session_state.selected_alignment = None
        st.session_state.trace_preview = None
        st.session_state.analysis_result = None
        st.session_state.stage_status = {stage: False for stage in STAGE_ORDER}
        return
    st.session_state.alignments = parse_files_cached(files_payload)
    alignment_ids = [item["alignment_id"] for item in st.session_state.alignments]
    selection_changed = st.session_state.selected_alignment not in alignment_ids
    if selection_changed:
        st.session_state.selected_alignment = alignment_ids[0]
    if payload_changed or selection_changed:
        st.session_state.trace_preview = None
        st.session_state.analysis_result = None
        st.session_state.stage_status = {stage: False for stage in STAGE_ORDER}


def build_effective_params() -> dict:
    trace = st.session_state.trace_inputs
    diagnostic = st.session_state.diagnostic_inputs
    steady = st.session_state.steady_inputs
    transient = st.session_state.transient_inputs
    scenarios = st.session_state.scenario_inputs

    max_zones = int(scenarios["max_zones"]) if scenarios["mix_materials_by_zone"] else 1
    return {
        "flow_m3_s": float(trace["flow_l_s"]) / 1000.0,
        "station_interval_m": float(trace["station_interval_m"]),
        "elevation_source": trace["elevation_source"],
        "upstream_residual_head_m": float(diagnostic["upstream_head_m"]),
        "minimum_pressure_head_m": float(diagnostic["minimum_head_m"]),
        "terminal_pressure_head_m": float(diagnostic["terminal_head_m"]),
        "max_operating_pressure_bar": float(diagnostic["max_operating_pressure_bar"]),
        "localized_loss_factor": float(steady["localized_loss_factor"]),
        "enabled_materials": list(scenarios["enabled_materials"]),
        "velocity_min_m_s": float(steady["velocity_min_m_s"]),
        "velocity_max_m_s": float(steady["velocity_max_m_s"]),
        "minimum_transient_pressure_bar": float(transient["minimum_transient_pressure_bar"]),
        "pump_efficiency": float(scenarios["pump_efficiency"]),
        "energy_cost_brl_per_kwh": float(scenarios["energy_cost_brl_per_kwh"]),
        "energy_horizon_years": float(scenarios["energy_horizon_years"]),
        "operating_hours_per_year": float(scenarios["operating_hours_per_year"]),
        "surge_closure_factor": float(transient["surge_closure_factor"]),
        "surge_trip_factor": float(transient["surge_trip_factor"]),
        "block_valve_spacing_m": float(transient["block_valve_spacing_m"]),
        "anchor_min_deflection_deg": float(transient["anchor_min_deflection_deg"]),
        "pump_station_base_cost_brl": float(scenarios["pump_station_base_cost_brl"]),
        "surge_protection_cost_brl": float(scenarios["surge_protection_cost_brl"]),
        "shortlist_size": int(scenarios["shortlist_size"]),
        "max_zone_length_m": float(scenarios["max_zone_length_m"]),
        "max_zones": max_zones,
        "transition_node_cost_brl": float(scenarios["transition_node_cost_brl"]),
        "max_combo_evals": 50000,
        "kinematic_viscosity_m2_s": 1.004e-6,
    }


def run_full_analysis() -> dict:
    if not st.session_state.files_payload or not st.session_state.selected_alignment:
        raise RuntimeError("Defina o tracado antes de rodar a analise.")
    params_json = json.dumps(build_effective_params(), sort_keys=True)
    try:
        result = run_full_analysis_cached(st.session_state.files_payload, st.session_state.selected_alignment, params_json)
    except ElevationAPIError as exc:
        st.error(f"Erro ao obter cotas de elevacao: {exc}")
        st.stop()
    st.session_state.analysis_result = result
    return result


def render_page_header(title: str, question: str, note: str | None = None) -> None:
    st.markdown(
        f"""
        <div class="hero">
          <h1>{title}</h1>
          <p>{question}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if note:
        st.markdown(f"<div class='page-note'>{note}</div>", unsafe_allow_html=True)


def stage_is_complete(stage_name: str) -> bool:
    return bool(st.session_state.stage_status.get(stage_name, False))


def require_stage(stage_name: str) -> None:
    if not stage_is_complete(stage_name):
        st.info(f"Conclua a etapa '{stage_name}' para liberar esta página.")
        st.stop()


def render_sidebar(stage_name: str) -> None:
    with st.sidebar:
        st.markdown("### Caso")
        st.caption(st.session_state.trace_inputs["case_name"])
        st.caption(f"Etapa atual: {stage_name}")

        st.markdown("### Status do estudo")
        for stage in STAGE_ORDER:
            status = "Concluida" if st.session_state.stage_status.get(stage) else "Pendente"
            st.write(f"- {stage}: {status}")

        st.markdown("### Premissas ativas")
        st.caption(
            " | ".join(
                [
                    f"Q={st.session_state.trace_inputs['flow_l_s']:.0f} L/s",
                    f"Modo={st.session_state.trace_inputs['operation_mode']}",
                    f"dx={st.session_state.trace_inputs['station_interval_m']:.0f} m",
                    f"Materiais={len(st.session_state.scenario_inputs['enabled_materials'])}",
                ]
            )
        )

        st.markdown("### Acoes globais")
        if st.button("Recalcular estudo", use_container_width=True, disabled=not stage_is_complete("Tracado")):
            with st.spinner("Recalculando..."):
                run_full_analysis()
        if st.button("Reiniciar caso", use_container_width=True):
            reset_case()
            st.rerun()

        st.markdown("---")
        catalog_df = load_pipe_catalog()
        dn_max = int(catalog_df["dn_mm"].max())
        n_items = len(catalog_df)
        st.caption(f"Catalogo: {n_items} tubos | DN max {dn_max} mm")


def preview_profile_figure(base_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=base_df["dist_acum_m"], y=base_df["z_terrain_m"], name="Terreno", line=dict(color="#876445", width=2)))
    fig.update_layout(template="plotly_white", height=320, xaxis_title="Distancia acumulada (m)", yaxis_title="Cota (m)")
    return fig


def preview_plan_figure(base_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scattermapbox(
            lat=base_df["lat"],
            lon=base_df["lon"],
            mode="lines+markers",
            line=dict(color="#145DA0", width=3),
            marker=dict(size=5, color="#C86F4A"),
            name="Eixo",
        )
    )
    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=float(base_df["lat"].mean()), lon=float(base_df["lon"].mean())),
            zoom=12,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=320,
    )
    return fig


def rank_scenarios_for_display(df: pd.DataFrame, priority: str) -> pd.DataFrame:
    ranked = df.copy()
    if ranked.empty:
        return ranked

    def _inverse_score(series: pd.Series) -> pd.Series:
        span = float(series.max() - series.min())
        if span <= 1e-9:
            return pd.Series(100.0, index=series.index)
        return 100.0 * (series.max() - series) / span

    def _direct_score(series: pd.Series) -> pd.Series:
        span = float(series.max() - series.min())
        if span <= 1e-9:
            return pd.Series(100.0, index=series.index)
        return 100.0 * (series - series.min()) / span

    ranked["score_economico"] = _inverse_score(ranked["objective_cost_brl"])
    robustness_base = (
        _direct_score(ranked["min_transient_bar"].astype(float)) * 0.45
        + _inverse_score(ranked["pump_head_required_m"].astype(float)) * 0.25
        + ranked["is_feasible"].astype(float) * 30.0
    )
    robustness_base = robustness_base - ranked["subpressure_risk"].astype(float) * 20.0
    ranked["score_tecnico"] = robustness_base.clip(lower=0.0, upper=100.0)

    if priority == "Custo":
        ranked["score_global"] = ranked["score_economico"] * 0.65 + ranked["score_tecnico"] * 0.35
    elif priority == "Robustez":
        ranked["score_global"] = ranked["score_tecnico"] * 0.70 + ranked["score_economico"] * 0.30
    else:
        ranked["score_global"] = ranked["score_tecnico"] * 0.50 + ranked["score_economico"] * 0.50

    return ranked.sort_values(["score_global", "is_feasible"], ascending=[False, False]).reset_index(drop=True)


def build_solution_summary_text(result: dict) -> str:
    best = result["best_layout"]
    lines = [
        f"Caso: {st.session_state.trace_inputs['case_name']}",
        f"Alinhamento: {result['alignment_id']}",
        f"Vazao de projeto: {st.session_state.trace_inputs['flow_l_s']:.0f} L/s",
        f"Solucao recomendada: {best['zone_signature']}",
        f"Bombeamento requerido: {best['pump_head_required_m']:.2f} m",
        f"Custo proxy: R$ {best['objective_cost_brl']:,.0f}",
        f"Pressao minima operacional: {result['kpis']['min_pressure_bar']:.2f} bar",
        f"Pressao minima em transiente: {result['kpis']['min_transient_bar']:.2f} bar",
        "Warnings:",
    ]
    lines.extend([f"- {warning}" for warning in result["warnings"]] or ["- Nenhum warning relevante registrado."])
    lines.append("Limitacoes: pre-dimensionamento preliminar, transientes simplificados e custos de referencia.")
    return "\n".join(lines)


def get_catalog_assets() -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    return (
        load_pipe_catalog(),
        load_reference_library(),
        load_pipe_catalog_payload(),
        load_reference_library_payload(),
    )
