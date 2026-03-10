"""Page renderers for the staged Gradiente Hidraulico experience."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.export import dataframe_to_csv_bytes, to_excel_bytes
from src.viz import fig_alternatives, fig_catalog, fig_pressure, fig_profile

from ui_shared import (
    build_solution_summary_text,
    get_catalog_assets,
    invalidate_after,
    prepare_trace_preview_cached,
    preview_plan_figure,
    preview_profile_figure,
    rank_scenarios_for_display,
    render_page_header,
    require_stage,
    run_full_analysis,
    update_alignment_cache,
)


def _with_status(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona coluna 'status' legivel indicando o motivo de inviabilidade."""
    def _label(row):
        if row.get("static_vacuum_risk", False):
            return "Vacuo estatico"
        if not row.get("pressure_class_ok", True):
            return "Pressao excede PN"
        if not row.get("velocity_ok", True):
            return "Velocidade fora"
        if row.get("subpressure_risk", False):
            return "Risco subpressao"
        return "Viavel"
    out = df.copy()
    out.insert(0, "status", out.apply(_label, axis=1))
    return out


def render_tracado() -> None:
    render_page_header(
        "Tracado",
        "Tenho um tracado valido e uma base minima para comecar a analise?",
        "O objetivo desta etapa e validar o eixo, interpolar o perfil e gerar uma primeira leitura geometrica com o minimo de friccao.",
    )

    source_mode = st.radio(
        "Origem do tracado",
        ["Exemplo do projeto", "Upload de arquivo"],
        horizontal=True,
        key="trace_source_mode",
    )
    if source_mode == "Upload de arquivo":
        uploaded_files = st.file_uploader(
            "KML da adutora",
            type=["kml"],
            accept_multiple_files=True,
            key=f"kml_uploader_{st.session_state.upload_version}",
        )
        files_payload = tuple((file.name, file.getvalue()) for file in (uploaded_files or []))
    else:
        from ui_shared import load_sample_files

        files_payload = load_sample_files()
        st.caption("Usando o KML de exemplo do projeto.")

    update_alignment_cache(files_payload)

    if st.session_state.alignments:
        alignment_ids = [item["alignment_id"] for item in st.session_state.alignments]
        previous_alignment = st.session_state.selected_alignment
        selected_alignment = st.selectbox(
            "Alinhamento para leitura inicial",
            alignment_ids,
            index=alignment_ids.index(st.session_state.selected_alignment),
        )
        st.session_state.selected_alignment = selected_alignment
        if selected_alignment != previous_alignment:
            st.session_state.trace_preview = None
            invalidate_after("Tracado")
    else:
        st.info("Carregue um KML ou use o exemplo para liberar a etapa.")
        return

    defaults = st.session_state.trace_inputs
    with st.form("form_tracado"):
        case_name = st.text_input("Nome do caso", value=defaults["case_name"])
        flow_l_s = st.number_input("Vazao de projeto (L/s)", min_value=1.0, value=float(defaults["flow_l_s"]), step=5.0)
        operation_mode = st.radio("Modo de operacao", ["Gravidade", "Bombeado"], horizontal=True, index=0 if defaults["operation_mode"] == "Gravidade" else 1)
        station_interval_m = st.number_input("Discretizacao inicial (m)", min_value=10.0, value=float(defaults["station_interval_m"]), step=10.0)
        elevation_source = st.selectbox(
            "Elevacao",
            [("auto", "Auto"), ("kml", "Somente Z do KML"), ("open-meteo", "Somente Open-Meteo")],
            format_func=lambda item: item[1],
            index=["auto", "kml", "open-meteo"].index(defaults["elevation_source"]),
        )
        submitted = st.form_submit_button("Validar tracado", type="primary")

    if submitted:
        st.session_state.trace_inputs.update(
            {
                "case_name": case_name,
                "flow_l_s": flow_l_s,
                "operation_mode": operation_mode,
                "station_interval_m": station_interval_m,
                "elevation_source": elevation_source[0],
            }
        )
        invalidate_after("Tracado")
        preview_params = {
            "station_interval_m": station_interval_m,
            "elevation_source": elevation_source[0],
        }
        params_json = json.dumps(preview_params, sort_keys=True)
        with st.spinner("Lendo eixo e preparando o preview do perfil..."):
            st.session_state.trace_preview = prepare_trace_preview_cached(
                st.session_state.files_payload,
                st.session_state.selected_alignment,
                params_json,
            )
            st.session_state.stage_status["Tracado"] = True

    preview = st.session_state.trace_preview
    if preview is None:
        return

    metric_cols = st.columns(4)
    metric_cols[0].metric("Extensao", f"{preview['total_length_m']:.0f} m")
    metric_cols[1].metric("Vertices KML", f"{preview['raw_vertices']}")
    metric_cols[2].metric("Pontos interpolados", f"{preview['interpolated_points']}")
    metric_cols[3].metric("Faixa altimetrica", f"{preview['min_elevation_m']:.1f} a {preview['max_elevation_m']:.1f} m")

    st.markdown("#### Vista em planta")
    st.plotly_chart(preview_plan_figure(preview["base_df"]), use_container_width=True)
    st.markdown("#### Preview do perfil")
    st.plotly_chart(preview_profile_figure(preview["base_df"]), use_container_width=True)

    with st.expander("Log tecnico", expanded=False):
        st.write(f"Numero de vertices lidos: {preview['raw_vertices']}")
        st.write(f"Numero de pontos interpolados: {preview['interpolated_points']}")
        st.write(f"Espacamento adotado: {st.session_state.trace_inputs['station_interval_m']:.0f} m")
        st.write(f"Status da consulta altimetrica: {preview['elevation_source']}")
        st.write("Warnings de inconsistencias: nenhum warning bloqueante nesta etapa.")


def render_diagnostico() -> None:
    require_stage("Tracado")
    render_page_header(
        "Diagnostico",
        "O tracado e a energia disponivel sugerem que a solucao e viavel ou precisa de ajuste?",
        "Nesta etapa entram so as premissas energeticas basicas para uma primeira leitura global do sistema.",
    )

    defaults = st.session_state.diagnostic_inputs
    with st.form("form_diagnostico"):
        upstream_head_m = st.number_input("Carga disponivel na montante (m)", min_value=0.0, value=float(defaults["upstream_head_m"]), step=1.0)
        minimum_head_m = st.number_input("Pressao minima desejada ao longo da linha (mca)", min_value=0.0, value=float(defaults["minimum_head_m"]), step=1.0)
        terminal_head_m = st.number_input("Pressao minima desejada no ponto final (mca)", min_value=0.0, value=float(defaults["terminal_head_m"]), step=1.0)
        max_operating_pressure_bar = st.number_input("Pressao maxima admissivel (bar)", min_value=1.0, value=float(defaults["max_operating_pressure_bar"]), step=0.5)
        submitted = st.form_submit_button("Rodar diagnostico", type="primary")

    if submitted:
        st.session_state.diagnostic_inputs.update(
            {
                "upstream_head_m": upstream_head_m,
                "minimum_head_m": minimum_head_m,
                "terminal_head_m": terminal_head_m,
                "max_operating_pressure_bar": max_operating_pressure_bar,
            }
        )
        invalidate_after("Diagnostico")
        with st.spinner("Executando o diagnostico inicial..."):
            run_full_analysis()
            st.session_state.stage_status["Diagnostico"] = True

    result = st.session_state.analysis_result
    if result is None:
        st.info("Confirme as premissas acima para liberar o diagnostico.")
        return

    metric_cols = st.columns(4)
    metric_cols[0].metric("Pressao minima", f"{result['kpis']['min_pressure_bar']:.2f} bar")
    metric_cols[1].metric("Pressao maxima", f"{result['kpis']['max_pressure_bar']:.2f} bar")
    metric_cols[2].metric("Bombeamento preliminar", f"{result['kpis']['pump_head_m']:.1f} m")
    metric_cols[3].metric("Zonas finais", f"{result['kpis']['zone_count']}")

    st.plotly_chart(fig_profile(result["detail_df"]), use_container_width=True)
    st.dataframe(
        result["critical_points_df"].head(8),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Log tecnico", expanded=False):
        st.write(f"Carga de montante: {st.session_state.diagnostic_inputs['upstream_head_m']:.1f} m")
        st.write(f"Pressao minima adotada: {st.session_state.diagnostic_inputs['minimum_head_m']:.1f} mca")
        st.write(f"Pressao final adotada: {st.session_state.diagnostic_inputs['terminal_head_m']:.1f} mca")
        st.write(f"Criterio de maxima admissivel: {st.session_state.diagnostic_inputs['max_operating_pressure_bar']:.1f} bar")
        st.write("Leitura inicial dos pontos criticos gerada a partir do perfil consolidado.")


def render_regime_permanente() -> None:
    require_stage("Diagnostico")
    render_page_header(
        "Regime permanente",
        "A linha atende hidraulicamente em operacao normal?",
        "Aqui entram as premissas de perda e os limites operacionais ligados ao regime permanente.",
    )

    defaults = st.session_state.steady_inputs
    with st.form("form_regime"):
        localized_loss_factor = st.slider("Perdas localizadas simplificadas", min_value=0.0, max_value=0.5, value=float(defaults["localized_loss_factor"]), step=0.01)
        velocity_min_m_s = st.number_input("Velocidade minima (m/s)", min_value=0.1, value=float(defaults["velocity_min_m_s"]), step=0.1)
        velocity_max_m_s = st.number_input("Velocidade maxima (m/s)", min_value=0.5, value=float(defaults["velocity_max_m_s"]), step=0.1)
        friction_method = st.selectbox("Metodo de atrito", ["Darcy-Weisbach"], index=0)
        submitted = st.form_submit_button("Atualizar regime permanente", type="primary")

    if submitted:
        st.session_state.steady_inputs.update(
            {
                "localized_loss_factor": localized_loss_factor,
                "velocity_min_m_s": velocity_min_m_s,
                "velocity_max_m_s": velocity_max_m_s,
                "friction_method": friction_method,
            }
        )
        invalidate_after("Regime permanente")
        with st.spinner("Recalculando regime permanente..."):
            run_full_analysis()
            st.session_state.stage_status["Regime permanente"] = True

    result = st.session_state.analysis_result
    if result is None:
        st.info("O resultado do diagnostico ainda nao esta disponivel.")
        return

    st.plotly_chart(fig_pressure(result["detail_df"]), use_container_width=True)
    st.markdown("#### Tabela por trecho")
    st.dataframe(
        result["detail_df"][[
            "dist_acum_m",
            "material",
            "dn_mm",
            "velocity_m_s",
            "head_loss_segment_m",
            "head_loss_cumulative_m",
            "pressure_bar",
        ]],
        use_container_width=True,
        hide_index=True,
        height=360,
    )

    with st.expander("Log tecnico", expanded=False):
        detail_df = result["detail_df"]
        st.write(f"Vazao utilizada: {st.session_state.trace_inputs['flow_l_s']:.0f} L/s")
        st.write(f"Materiais habilitados: {', '.join(st.session_state.scenario_inputs['enabled_materials'])}")
        st.write(f"Rugosidade aplicada: catalogo rastreavel por item")
        st.write(f"Reynolds minimo/maximo: {detail_df['reynolds'].min():.0f} / {detail_df['reynolds'].max():.0f}")
        st.write(f"Fator de atrito minimo/maximo: {detail_df['friction_factor'].min():.4f} / {detail_df['friction_factor'].max():.4f}")
        st.write(f"Perda acumulada final: {detail_df['head_loss_cumulative_m'].max():.2f} m")
        st.write(f"Pressao minima/maxima: {detail_df['pressure_bar'].min():.2f} / {detail_df['pressure_bar'].max():.2f} bar")


def render_transientes() -> None:
    require_stage("Regime permanente")
    render_page_header(
        "Transientes e protecao",
        "A solucao continua aceitavel quando analisada sob condicoes operacionais mais sensiveis?",
        "Esta etapa foca em envelope de sobrepressao/subpressao e indicacao preliminar de protecoes e dispositivos.",
    )

    defaults = st.session_state.transient_inputs
    with st.form("form_transientes"):
        event_type = st.selectbox("Evento considerado", ["Envelope combinado", "Fechamento rapido", "Parada de bomba"], index=["Envelope combinado", "Fechamento rapido", "Parada de bomba"].index(defaults["event_type"]))
        surge_closure_factor = st.slider("Severidade de sobrepressao", min_value=0.10, max_value=1.00, value=float(defaults["surge_closure_factor"]), step=0.05)
        surge_trip_factor = st.slider("Severidade de subpressao", min_value=0.10, max_value=1.00, value=float(defaults["surge_trip_factor"]), step=0.05)
        minimum_transient_pressure_bar = st.number_input("Limite minimo em transiente (bar)", value=float(defaults["minimum_transient_pressure_bar"]), step=0.1)
        submitted = st.form_submit_button("Atualizar transientes", type="primary")

    if submitted:
        st.session_state.transient_inputs.update(
            {
                "event_type": event_type,
                "surge_closure_factor": surge_closure_factor,
                "surge_trip_factor": surge_trip_factor,
                "minimum_transient_pressure_bar": minimum_transient_pressure_bar,
            }
        )
        invalidate_after("Transientes e protecao")
        with st.spinner("Recalculando envelope de transientes..."):
            run_full_analysis()
            st.session_state.stage_status["Transientes e protecao"] = True

    result = st.session_state.analysis_result
    if result is None:
        st.info("Rode ao menos o diagnostico para visualizar transientes.")
        return

    st.plotly_chart(fig_pressure(result["detail_df"]), use_container_width=True)
    st.markdown("#### Dispositivos sugeridos")
    st.dataframe(result["devices_df"], use_container_width=True, hide_index=True, height=360)

    with st.expander("Log tecnico", expanded=False):
        detail_df = result["detail_df"]
        st.write(f"Evento considerado: {st.session_state.transient_inputs['event_type']}")
        st.write(f"Fator de sobrepressao: {st.session_state.transient_inputs['surge_closure_factor']:.2f}")
        st.write(f"Fator de subpressao: {st.session_state.transient_inputs['surge_trip_factor']:.2f}")
        st.write(f"Delta maximo de sobrepressao: {detail_df['positive_surge_bar'].max():.2f} bar")
        st.write(f"Ponto critico de subpressao: {detail_df['pressure_min_transient_bar'].min():.2f} bar")
        st.write("Hipoteses: envelope simplificado de Joukowsky e indicacao preliminar de protecao.")


def render_cenarios() -> None:
    require_stage("Transientes e protecao")
    render_page_header(
        "Cenarios de tubulacao",
        "Quais cenarios sao tecnicamente viaveis e qual apresenta o melhor equilibrio global?",
        "Nesta etapa entram os materiais ativos, a permissao de mistura por zona e a prioridade da comparacao.",
    )

    catalog_df, _, _, _ = get_catalog_assets()
    defaults = st.session_state.scenario_inputs
    materials = sorted(catalog_df["material"].unique())
    priority_options = ["Custo", "Robustez", "Equilibrio"]
    with st.form("form_cenarios"):
        enabled_materials = st.multiselect("Materiais habilitados", options=materials, default=defaults["enabled_materials"])
        mix_materials_by_zone = st.checkbox("Permitir mistura de materiais por trecho", value=bool(defaults["mix_materials_by_zone"]))
        shortlist_size = st.slider("Quantidade de cenarios no shortlist", min_value=2, max_value=8, value=int(defaults["shortlist_size"]))
        max_zone_length_m = st.number_input("Comprimento maximo de zona (m)", min_value=300.0, value=float(defaults["max_zone_length_m"]), step=100.0)
        max_zones = st.slider("Numero maximo de zonas", min_value=1, max_value=6, value=int(defaults["max_zones"]), disabled=not mix_materials_by_zone)
        recommendation_priority = st.selectbox("Prioridade da comparacao", priority_options, index=priority_options.index(defaults["recommendation_priority"]))
        pump_efficiency = st.slider("Rendimento estimado de bombeamento", min_value=0.40, max_value=0.90, value=float(defaults["pump_efficiency"]), step=0.01)
        energy_cost_brl_per_kwh = st.number_input("Custo de energia (R$/kWh)", min_value=0.0, value=float(defaults["energy_cost_brl_per_kwh"]), step=0.05)
        energy_horizon_years = st.number_input("Horizonte energetico (anos)", min_value=1.0, value=float(defaults["energy_horizon_years"]), step=1.0)
        operating_hours_per_year = st.number_input("Horas equivalentes por ano", min_value=100.0, value=float(defaults["operating_hours_per_year"]), step=100.0)
        transition_node_cost_brl = st.number_input("Custo por transicao entre zonas (R$)", min_value=0.0, value=float(defaults["transition_node_cost_brl"]), step=1000.0)
        submitted = st.form_submit_button("Comparar cenarios", type="primary")

    if submitted:
        st.session_state.scenario_inputs.update(
            {
                "enabled_materials": enabled_materials or materials,
                "mix_materials_by_zone": mix_materials_by_zone,
                "shortlist_size": shortlist_size,
                "max_zone_length_m": max_zone_length_m,
                "max_zones": max_zones,
                "recommendation_priority": recommendation_priority,
                "pump_efficiency": pump_efficiency,
                "energy_cost_brl_per_kwh": energy_cost_brl_per_kwh,
                "energy_horizon_years": energy_horizon_years,
                "operating_hours_per_year": operating_hours_per_year,
                "transition_node_cost_brl": transition_node_cost_brl,
            }
        )
        invalidate_after("Cenarios de tubulacao")
        with st.spinner("Executando comparacao de cenarios..."):
            run_full_analysis()
            st.session_state.stage_status["Cenarios de tubulacao"] = True

    result = st.session_state.analysis_result
    if result is None:
        st.info("A comparacao depende dos resultados das etapas anteriores.")
        return

    priority = st.session_state.scenario_inputs["recommendation_priority"]
    uniform_ranked = rank_scenarios_for_display(result["uniform_df"], priority)
    zoned_ranked = rank_scenarios_for_display(result["zoned_df"], priority)

    st.plotly_chart(fig_alternatives(uniform_ranked, zoned_ranked), use_container_width=True)

    display_cols = [
        "status",
        "scenario_label",
        "dn_mm",
        "pressure_class_bar",
        "max_pressure_bar",
        "max_transient_bar",
        "velocity_m_s",
        "pump_head_required_m",
        "objective_cost_brl",
        "score_global",
    ]

    st.markdown("#### Uniforme")
    st.dataframe(
        _with_status(uniform_ranked).head(10)[[c for c in display_cols if c in _with_status(uniform_ranked).columns]],
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("#### Por trechos")
    st.dataframe(
        _with_status(zoned_ranked).head(10)[[c for c in display_cols if c in _with_status(zoned_ranked).columns]],
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Log tecnico", expanded=False):
        uniform_df = result["uniform_df"]
        zoned_df = result["zoned_df"]
        st.write(f"Numero total de cenarios uniformes testados: {len(uniform_df)}")
        st.write(f"Numero de combinacoes por trechos testadas: {len(zoned_df)}")
        st.write(f"Cenarios descartados por inviabilidade: {(~uniform_df['is_feasible']).sum()}")
        st.write(f"Prioridade ativa na comparacao: {priority}")
        st.write("Justificativa do lider: ordenacao por score global calculado a partir de score tecnico e economico de exibicao.")


def render_solucao_final() -> None:
    require_stage("Cenarios de tubulacao")
    render_page_header(
        "Solucao final",
        "Qual solucao deve ser levada adiante como base preliminar do estudo?",
        "Esta etapa consolida a recomendacao final, os materiais por trecho, os dispositivos sugeridos e os arquivos exportaveis.",
    )

    result = st.session_state.analysis_result
    if result is None:
        st.info("Finalize a comparacao de cenarios para liberar a consolidacao final.")
        return

    st.session_state.stage_status["Solucao final"] = True
    best = result["best_layout"]
    metric_cols = st.columns(5)
    metric_cols[0].metric("Extensao", f"{result['kpis']['total_length_m']:.0f} m")
    metric_cols[1].metric("Bombeamento", f"{result['kpis']['pump_head_m']:.1f} m")
    metric_cols[2].metric("Pressao min.", f"{result['kpis']['min_pressure_bar']:.2f} bar")
    metric_cols[3].metric("Transiente min.", f"{result['kpis']['min_transient_bar']:.2f} bar")
    metric_cols[4].metric("Custo proxy", f"R$ {result['kpis']['objective_cost_brl']:,.0f}")

    st.markdown("### Recomendacao consolidada")
    st.markdown(
        f"""
        - Solucao recomendada: `{best['zone_signature']}`
        - Melhor uniforme de referencia: `{result['uniform_best']['scenario_label']}`
        - Zonas finais consolidadas: `{result['kpis']['zone_count']}`
        - Fonte de elevacao: `{result['elevation_source']}`
        """
    )

    export_tables = {
        "Perfil": result["detail_df"],
        "Uniforme": result["uniform_df"],
        "Zonado": result["zoned_df"],
        "Zonas": result["zone_solution_df"],
        "Materiais": result["materials_df"],
        "Dispositivos": result["devices_df"],
        "PontosCriticos": result["critical_points_df"],
    }
    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button("Exportar CSV", dataframe_to_csv_bytes(result["detail_df"]), file_name=f"perfil_{result['alignment_id']}.csv", mime="text/csv", use_container_width=True)
    with d2:
        st.download_button("Exportar Excel", to_excel_bytes(export_tables), file_name=f"gradiente_hidraulico_{result['alignment_id']}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    with d3:
        st.download_button("Gerar resumo tecnico", build_solution_summary_text(result), file_name=f"resumo_{result['alignment_id']}.txt", mime="text/plain", use_container_width=True)

    t1, t2 = st.columns(2)
    with t1:
        st.markdown("#### Tubos por trecho")
        st.dataframe(result["zone_solution_df"], use_container_width=True, hide_index=True)
        st.markdown("#### Lista preliminar de materiais")
        st.dataframe(result["materials_df"], use_container_width=True, hide_index=True)
    with t2:
        st.markdown("#### Dispositivos sugeridos")
        st.dataframe(result["devices_df"], use_container_width=True, hide_index=True)
        st.markdown("#### Pontos criticos")
        st.dataframe(result["critical_points_df"], use_container_width=True, hide_index=True)

    with st.expander("Log tecnico", expanded=False):
        st.write(f"Cenario selecionado: {best['zone_signature']}")
        st.write(f"Trade-offs aceitos: custo proxy {best['objective_cost_brl']:.0f} e bombeamento {best['pump_head_required_m']:.2f} m")
        st.write("Limitacoes do estudo: pre-dimensionamento preliminar, transientes simplificados e custos-base de referencia.")
        st.write("Pendencias para detalhamento executivo: topografia definitiva, modelagem transitoria refinada e cotacao real de fornecimento.")


def render_catalogo() -> None:
    catalog_df, reference_df, catalog_payload, reference_payload = get_catalog_assets()
    render_page_header(
        "Catalogo",
        "Quais referencias tecnicas e economicas estao sustentando o estudo?",
        "A biblioteca fica exposta em JSON para rastreabilidade e para uso no deploy web.",
    )

    d1, d2 = st.columns(2)
    with d1:
        st.download_button("Baixar pipe_catalog.json", json.dumps(catalog_payload, indent=2, ensure_ascii=True), file_name="pipe_catalog.json", mime="application/json", use_container_width=True)
    with d2:
        st.download_button("Baixar reference_documents.json", json.dumps(reference_payload, indent=2, ensure_ascii=True), file_name="reference_documents.json", mime="application/json", use_container_width=True)

    st.plotly_chart(fig_catalog(catalog_df), use_container_width=True)
    st.dataframe(catalog_df, use_container_width=True, hide_index=True)
    with st.expander("Biblioteca de referencias JSON", expanded=False):
        st.dataframe(reference_df, use_container_width=True, hide_index=True)
