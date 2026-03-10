"""Multipage Streamlit app for the vectorized Gradiente Hidraulico engine."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import (
    analyze_alignment,
    load_pipe_catalog,
    load_pipe_catalog_payload,
    load_reference_library,
    load_reference_library_payload,
)
from src.export import dataframe_to_csv_bytes, to_excel_bytes
from src.geo import parse_multiple_kml
from src.viz import fig_alternatives, fig_catalog, fig_plan_view, fig_pressure, fig_profile

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_KML = ROOT / "sample" / "adutora_demo.kml"

st.set_page_config(page_title="Gradiente Hidraulico", page_icon="GH", layout="wide", initial_sidebar_state="expanded")

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
        padding: 2rem 2.2rem;
        border-radius: 20px;
        margin-bottom: 1.25rem;
        box-shadow: 0 18px 45px rgba(33,53,71,0.18);
    }
    [data-testid="metric-container"] {
        background: rgba(255,250,243,0.92);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 0.9rem 1rem;
        box-shadow: 0 8px 20px rgba(33,53,71,0.05);
    }
    .card {
        background: rgba(255,250,243,0.88);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 1rem 1.1rem;
        box-shadow: 0 8px 20px rgba(33,53,71,0.05);
    }
    .note {
        background: rgba(200,111,74,0.10);
        border: 1px solid rgba(200,111,74,0.25);
        border-radius: 14px;
        padding: 0.9rem 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def _sample_files() -> list[dict]:
    return [{"name": SAMPLE_KML.name, "content": SAMPLE_KML.read_bytes()}]


@st.cache_data(show_spinner=False)
def _parse_files(files_payload: tuple[tuple[str, bytes], ...]) -> list[dict]:
    files = [{"name": name, "content": content} for name, content in files_payload]
    return parse_multiple_kml(files)


@st.cache_data(show_spinner=False)
def _run_analysis_cached(files_payload: tuple[tuple[str, bytes], ...], alignment_id: str, params_json: str) -> dict:
    alignments = _parse_files(files_payload)
    alignment = next(item for item in alignments if item["alignment_id"] == alignment_id)
    params = json.loads(params_json)
    return analyze_alignment(alignment, params)


st.markdown(
    """
    <div class="hero">
      <h1>Gradiente Hidraulico</h1>
      <p>
        Motor hidraulico vetorizado em NumPy para comparar cenarios de tubos, otimizar por trechos,
        estimar bombeamento e triar riscos de transientes a partir de um eixo em KML.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "last_alignment_id" not in st.session_state:
    st.session_state.last_alignment_id = None
if "last_params_json" not in st.session_state:
    st.session_state.last_params_json = None

catalog_df = load_pipe_catalog()
reference_df = load_reference_library()
catalog_payload = load_pipe_catalog_payload()
reference_payload = load_reference_library_payload()
page = st.sidebar.radio("Area", ["Entrada", "Resultados", "Catalogo"], index=0)

source_mode = st.radio("Origem do KML", ["Exemplo do projeto", "Upload de arquivo"], horizontal=True)
if source_mode == "Upload de arquivo":
    uploaded_files = st.file_uploader("KML da adutora", type=["kml"], accept_multiple_files=True)
    files_payload = tuple((file.name, file.getvalue()) for file in (uploaded_files or []))
else:
    files_payload = tuple((item["name"], item["content"]) for item in _sample_files())
    st.caption(f"Exemplo carregado: {SAMPLE_KML.name}")

if files_payload:
    try:
        alignments = _parse_files(files_payload)
    except Exception as exc:
        st.error(f"Falha ao ler o KML: {exc}")
        st.stop()
    alignment_names = [alignment["alignment_id"] for alignment in alignments]
    selected_alignment = st.selectbox("Alinhamento para analise", alignment_names)
else:
    alignments = []
    selected_alignment = None


def _build_params(materials: list[str], elevation_source_label: str, form_values: dict) -> dict:
    elevation_source_map = {
        "Auto (usa Z do KML e recorre a API se necessario)": "auto",
        "Somente Z do KML": "kml",
        "Somente Open-Meteo": "open-meteo",
    }
    return {
        "flow_m3_s": form_values["flow_l_s"] / 1000.0,
        "station_interval_m": form_values["station_interval_m"],
        "elevation_source": elevation_source_map[elevation_source_label],
        "upstream_residual_head_m": form_values["upstream_head_m"],
        "minimum_pressure_head_m": form_values["minimum_head_m"],
        "terminal_pressure_head_m": form_values["terminal_head_m"],
        "localized_loss_factor": form_values["localized_loss_factor"],
        "enabled_materials": materials,
        "velocity_min_m_s": form_values["velocity_min_m_s"],
        "velocity_max_m_s": form_values["velocity_max_m_s"],
        "minimum_transient_pressure_bar": form_values["minimum_transient_pressure_bar"],
        "pump_efficiency": form_values["pump_efficiency"],
        "energy_cost_brl_per_kwh": form_values["energy_cost_brl_per_kwh"],
        "energy_horizon_years": form_values["energy_horizon_years"],
        "operating_hours_per_year": form_values["operating_hours_per_year"],
        "surge_closure_factor": form_values["surge_closure_factor"],
        "surge_trip_factor": form_values["surge_trip_factor"],
        "block_valve_spacing_m": form_values["block_valve_spacing_m"],
        "anchor_min_deflection_deg": form_values["anchor_min_deflection_deg"],
        "pump_station_base_cost_brl": form_values["pump_station_base_cost_brl"],
        "surge_protection_cost_brl": form_values["surge_protection_cost_brl"],
        "shortlist_size": form_values["shortlist_size"],
        "max_zone_length_m": form_values["max_zone_length_m"],
        "max_zones": form_values["max_zones"],
        "transition_node_cost_brl": form_values["transition_node_cost_brl"],
        "max_combo_evals": 50000,
        "kinematic_viscosity_m2_s": 1.004e-6,
    }


with st.sidebar:
    st.markdown("### Parametros de projeto")
    with st.form("analysis_form"):
        flow_l_s = st.number_input("Vazao de projeto (L/s)", min_value=1.0, value=120.0, step=5.0)
        station_interval_m = st.number_input("Passo de discretizacao (m)", min_value=10.0, value=50.0, step=10.0)
        elevation_source_label = st.selectbox(
            "Fonte de elevacao",
            ["Auto (usa Z do KML e recorre a API se necessario)", "Somente Z do KML", "Somente Open-Meteo"],
            index=0,
        )
        upstream_head_m = st.number_input("Carga disponivel na origem (m)", min_value=0.0, value=25.0, step=1.0)
        minimum_head_m = st.number_input("Pressao minima ao longo da linha (mca)", min_value=0.0, value=8.0, step=1.0)
        terminal_head_m = st.number_input("Pressao minima no ponto final (mca)", min_value=0.0, value=12.0, step=1.0)
        localized_loss_factor = st.slider("Perdas localizadas simplificadas", min_value=0.0, max_value=0.5, value=0.10, step=0.01)

        st.markdown("### Filtros e catalogo")
        materials = st.multiselect(
            "Materiais habilitados",
            options=sorted(catalog_df["material"].unique()),
            default=sorted(catalog_df["material"].unique()),
        )
        velocity_min_m_s = st.number_input("Velocidade minima (m/s)", min_value=0.1, value=0.6, step=0.1)
        velocity_max_m_s = st.number_input("Velocidade maxima (m/s)", min_value=0.5, value=2.5, step=0.1)
        shortlist_size = st.slider("Top cenarios para otimizar por trechos", min_value=2, max_value=8, value=5)

        st.markdown("### Zonas e transientes")
        max_zone_length_m = st.number_input("Comprimento maximo por zona (m)", min_value=300.0, value=1500.0, step=100.0)
        max_zones = st.slider("Numero maximo de zonas", min_value=2, max_value=6, value=4)
        surge_closure_factor = st.slider("Severidade de sobrepressao", min_value=0.10, max_value=1.00, value=0.35, step=0.05)
        surge_trip_factor = st.slider("Severidade de subpressao", min_value=0.10, max_value=1.00, value=0.45, step=0.05)
        minimum_transient_pressure_bar = st.number_input("Limite minimo transitorio (bar)", value=-0.2, step=0.1)

        st.markdown("### Custos proxy")
        pump_efficiency = st.slider("Rendimento estimado de bombeamento", min_value=0.40, max_value=0.90, value=0.72, step=0.01)
        energy_cost_brl_per_kwh = st.number_input("Custo de energia (R$/kWh)", min_value=0.0, value=0.85, step=0.05)
        energy_horizon_years = st.number_input("Horizonte energetico (anos)", min_value=1.0, value=5.0, step=1.0)
        operating_hours_per_year = st.number_input("Horas equivalentes por ano", min_value=100.0, value=6000.0, step=100.0)
        pump_station_base_cost_brl = st.number_input("Base de custo para bombeamento (R$)", min_value=0.0, value=250000.0, step=10000.0)
        surge_protection_cost_brl = st.number_input("Base de custo para protecao transitoria (R$)", min_value=0.0, value=120000.0, step=5000.0)
        transition_node_cost_brl = st.number_input("Custo por transicao entre zonas (R$)", min_value=0.0, value=20000.0, step=1000.0)
        block_valve_spacing_m = st.number_input("Espacamento preliminar de bloqueio (m)", min_value=200.0, value=1500.0, step=100.0)
        anchor_min_deflection_deg = st.number_input("Deflexao minima para ancoragem (graus)", min_value=5.0, value=20.0, step=1.0)

        submitted = st.form_submit_button("Rodar analise", use_container_width=True, type="primary")

if submitted:
    if not files_payload or not selected_alignment:
        st.error("Carregue um KML valido antes de rodar a analise.")
    else:
        params = _build_params(materials, elevation_source_label, {
            "flow_l_s": flow_l_s,
            "station_interval_m": station_interval_m,
            "upstream_head_m": upstream_head_m,
            "minimum_head_m": minimum_head_m,
            "terminal_head_m": terminal_head_m,
            "localized_loss_factor": localized_loss_factor,
            "velocity_min_m_s": velocity_min_m_s,
            "velocity_max_m_s": velocity_max_m_s,
            "minimum_transient_pressure_bar": minimum_transient_pressure_bar,
            "pump_efficiency": pump_efficiency,
            "energy_cost_brl_per_kwh": energy_cost_brl_per_kwh,
            "energy_horizon_years": energy_horizon_years,
            "operating_hours_per_year": operating_hours_per_year,
            "surge_closure_factor": surge_closure_factor,
            "surge_trip_factor": surge_trip_factor,
            "block_valve_spacing_m": block_valve_spacing_m,
            "anchor_min_deflection_deg": anchor_min_deflection_deg,
            "pump_station_base_cost_brl": pump_station_base_cost_brl,
            "surge_protection_cost_brl": surge_protection_cost_brl,
            "shortlist_size": shortlist_size,
            "max_zone_length_m": max_zone_length_m,
            "max_zones": max_zones,
            "transition_node_cost_brl": transition_node_cost_brl,
        })
        params_json = json.dumps(params, sort_keys=True)
        with st.spinner("Executando motor vetorizado e otimizacao por trechos..."):
            st.session_state.analysis_result = _run_analysis_cached(files_payload, selected_alignment, params_json)
            st.session_state.last_alignment_id = selected_alignment
            st.session_state.last_params_json = params_json

if page == "Entrada":
    st.markdown(
        """
        <div class="note">
          Regra de arquitetura aplicada neste app: Pandas organiza, NumPy calcula, Plotly mostra e Streamlit orquestra.
          O motor numerico trabalha em lote com cenarios e usa comparacao uniforme + combinacao por zonas para chegar na solucao preliminar.
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.session_state.analysis_result is not None:
        result = st.session_state.analysis_result
        st.markdown("### Ultima execucao")
        st.markdown(
            f"""
            <div class="card">
              <strong>{result['alignment_id']}</strong><br>
              Melhor uniforme: {result['uniform_best']['scenario_label']}<br>
              Melhor por trechos: {result['best_layout']['zone_signature']}<br>
              Fonte de elevacao: {result['elevation_source']}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.info("Configure os parametros no formulario lateral e rode a primeira analise.")

elif page == "Resultados":
    result = st.session_state.analysis_result
    if result is None:
        st.info("Ainda nao ha resultado em memoria. Rode a analise na pagina Entrada.")
        st.stop()

    for warning in result["warnings"]:
        st.warning(warning)

    left, right = st.columns([1.6, 1.0])
    with left:
        st.markdown("### Solucao otimizada por trechos")
        st.markdown(
            f"""
            <div class="card">
              <strong>{result['best_layout']['zone_signature']}</strong><br>
              Melhor uniforme de referencia: {result['uniform_best']['scenario_label']}<br>
              Bombeamento requerido: {result['best_layout']['pump_head_required_m']:.2f} m<br>
              Custo proxy: R$ {result['best_layout']['objective_cost_brl']:,.0f}<br>
              Fonte de elevacao: {result['elevation_source']}
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        tables = {
            "Perfil": result["detail_df"],
            "Uniforme": result["uniform_df"],
            "Zonado": result["zoned_df"],
            "Zonas": result["zone_solution_df"],
            "Materiais": result["materials_df"],
            "Dispositivos": result["devices_df"],
            "PontosCriticos": result["critical_points_df"],
        }
        st.download_button(
            "Baixar XLSX consolidado",
            data=to_excel_bytes(tables),
            file_name=f"gradiente_hidraulico_{result['alignment_id']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.download_button(
            "Baixar perfil CSV",
            data=dataframe_to_csv_bytes(result["detail_df"]),
            file_name=f"perfil_{result['alignment_id']}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    metric_cols = st.columns(6)
    metric_cols[0].metric("Extensao", f"{result['kpis']['total_length_m']:.0f} m")
    metric_cols[1].metric("Zona(s)", f"{result['kpis']['zone_count']}")
    metric_cols[2].metric("Pressao min.", f"{result['kpis']['min_pressure_bar']:.2f} bar")
    metric_cols[3].metric("Transiente min.", f"{result['kpis']['min_transient_bar']:.2f} bar")
    metric_cols[4].metric("Bombeamento", f"{result['kpis']['pump_head_m']:.1f} m")
    metric_cols[5].metric("Custo proxy", f"R$ {result['kpis']['objective_cost_brl']:,.0f}")

    profile_tab, options_tab, devices_tab, data_tab = st.tabs(["Perfil", "Alternativas", "Dispositivos", "Dados"])
    with profile_tab:
        c1, c2 = st.columns([1.15, 1.0])
        with c1:
            st.plotly_chart(fig_plan_view(result["detail_df"], result["devices_df"]), use_container_width=True)
        with c2:
            st.plotly_chart(fig_pressure(result["detail_df"]), use_container_width=True)
        st.plotly_chart(fig_profile(result["detail_df"]), use_container_width=True)

    with options_tab:
        st.plotly_chart(fig_alternatives(result["uniform_df"], result["zoned_df"]), use_container_width=True)
        st.markdown("#### Top cenarios uniformes")
        st.dataframe(result["uniform_df"].head(12), use_container_width=True, hide_index=True)
        st.markdown("#### Top combinacoes por trechos")
        st.dataframe(result["zoned_df"].head(12), use_container_width=True, hide_index=True)
        st.markdown("#### Solucao final por zona")
        st.dataframe(result["zone_solution_df"], use_container_width=True, hide_index=True)

    with devices_tab:
        d1, d2 = st.columns(2)
        with d1:
            st.markdown("#### Lista preliminar de materiais")
            st.dataframe(result["materials_df"], use_container_width=True, hide_index=True)
            st.markdown("#### Dispositivos recomendados")
            st.dataframe(result["devices_df"], use_container_width=True, hide_index=True)
        with d2:
            st.markdown("#### Pontos criticos")
            st.dataframe(result["critical_points_df"], use_container_width=True, hide_index=True)
            st.markdown("#### Dataset vetorizado consolidado")
            st.dataframe(result["detail_df"].head(40), use_container_width=True, hide_index=True)

    with data_tab:
        st.markdown("#### Perfil completo")
        st.dataframe(result["detail_df"], use_container_width=True, hide_index=True)

else:
    st.markdown("### Catalogo rastreavel")
    dl1, dl2 = st.columns(2)
    with dl1:
        st.download_button(
            "Baixar pipe_catalog.json",
            data=json.dumps(catalog_payload, indent=2, ensure_ascii=True),
            file_name="pipe_catalog.json",
            mime="application/json",
            use_container_width=True,
        )
    with dl2:
        st.download_button(
            "Baixar reference_documents.json",
            data=json.dumps(reference_payload, indent=2, ensure_ascii=True),
            file_name="reference_documents.json",
            mime="application/json",
            use_container_width=True,
        )
    st.plotly_chart(fig_catalog(catalog_df), use_container_width=True)
    st.dataframe(
        catalog_df[[
            "scenario_label",
            "manufacturer",
            "product_line",
            "material",
            "dn_mm",
            "pressure_class_bar",
            "inner_diameter_m",
            "cost_brl_per_m",
            "spec_reference_ids",
            "cost_reference_ids",
            "spec_source",
            "cost_source",
            "cost_reference_date",
        ]],
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("#### Biblioteca de referencias JSON")
    st.dataframe(reference_df, use_container_width=True, hide_index=True)
    st.caption(
        "Catalogo e referencias agora sao mantidos em JSON, com ids rastreaveis por item e uma biblioteca separada de documentos-base."
    )
