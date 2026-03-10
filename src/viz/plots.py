"""Plotly visuals for terrain, hydraulics, and scenario comparison."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

_THEME = {
    "terrain": "#876445",
    "hgl": "#145DA0",
    "egl": "#1F2A44",
    "pressure": "#D97D54",
    "surge": "#B33A3A",
    "ok": "#3E7C59",
    "warn": "#C78B2A",
}


def fig_plan_view(detail_df: pd.DataFrame, devices_df: pd.DataFrame | None = None) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scattermapbox(
            lat=detail_df["lat"],
            lon=detail_df["lon"],
            mode="lines+markers",
            name="Adutora",
            line=dict(color=_THEME["hgl"], width=4),
            marker=dict(size=6, color=detail_df["zone_id"], colorscale="Sunsetdark"),
            customdata=detail_df[["dist_acum_m", "pressure_bar", "zone_id"]],
            hovertemplate="Estaca %{customdata[0]:.0f} m<br>Pressao %{customdata[1]:.2f} bar<br>Zona %{customdata[2]}<extra></extra>",
        )
    )
    if devices_df is not None and not devices_df.empty:
        fig.add_trace(
            go.Scattermapbox(
                lat=devices_df["lat"],
                lon=devices_df["lon"],
                mode="markers",
                name="Dispositivos",
                marker=dict(size=10, color=_THEME["surge"]),
                text=devices_df["type"],
                hovertemplate="%{text}<extra></extra>",
            )
        )
    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=float(detail_df["lat"].mean()), lon=float(detail_df["lon"].mean())),
            zoom=12,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=470,
        legend=dict(bgcolor="rgba(255,255,255,0.85)"),
    )
    return fig


def fig_profile(detail_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=detail_df["dist_acum_m"], y=detail_df["z_terrain_m"], name="Terreno", line=dict(color=_THEME["terrain"], width=2, dash="dot")))
    fig.add_trace(go.Scatter(x=detail_df["dist_acum_m"], y=detail_df["hgl_m"], name="Linha piezometrica", line=dict(color=_THEME["hgl"], width=3)))
    fig.add_trace(go.Scatter(x=detail_df["dist_acum_m"], y=detail_df["egl_m"], name="Linha de energia", line=dict(color=_THEME["egl"], width=2)))
    fig.update_layout(template="plotly_white", height=420, hovermode="x unified", xaxis_title="Distancia acumulada (m)", yaxis_title="Cota / carga (m)")
    return fig


def fig_pressure(detail_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=detail_df["dist_acum_m"], y=detail_df["pressure_bar"], name="Operacao", line=dict(color=_THEME["pressure"], width=3)))
    fig.add_trace(go.Scatter(x=detail_df["dist_acum_m"], y=detail_df["pressure_max_transient_bar"], name="Transiente max.", line=dict(color=_THEME["surge"], width=2, dash="dash")))
    fig.add_trace(go.Scatter(x=detail_df["dist_acum_m"], y=detail_df["pressure_min_transient_bar"], name="Transiente min.", line=dict(color=_THEME["warn"], width=2, dash="dash")))
    fig.update_layout(template="plotly_white", height=360, hovermode="x unified", xaxis_title="Distancia acumulada (m)", yaxis_title="Pressao (bar)")
    return fig


def fig_alternatives(uniform_df: pd.DataFrame, zoned_df: pd.DataFrame) -> go.Figure:
    uniform_plot = uniform_df.copy().head(20)
    uniform_plot["kind"] = "Uniforme"
    zoned_plot = zoned_df.copy().head(20)
    zoned_plot["kind"] = "Por trechos"
    plot_df = pd.concat([uniform_plot, zoned_plot], ignore_index=True, sort=False)
    plot_df["status"] = plot_df["is_feasible"].map({True: "Atende", False: "Nao atende"})
    fig = px.scatter(
        plot_df,
        x="pump_head_required_m",
        y="objective_cost_brl",
        color="status",
        symbol="kind",
        hover_name="kind",
        hover_data={"velocity_m_s": True, "min_transient_bar": True, "max_transient_bar": True},
        color_discrete_map={"Atende": _THEME["ok"], "Nao atende": _THEME["surge"]},
    )
    fig.update_layout(template="plotly_white", height=380, xaxis_title="Bombeamento requerido (m)", yaxis_title="Custo tecnico-economico proxy (R$)")
    return fig


def fig_catalog(catalog_df: pd.DataFrame) -> go.Figure:
    fig = px.scatter(
        catalog_df,
        x="inner_diameter_m",
        y="cost_brl_per_m",
        color="material",
        symbol="pressure_class_bar",
        hover_name="scenario_label",
        size="pressure_class_bar",
    )
    fig.update_layout(template="plotly_white", height=380, xaxis_title="Diametro interno (m)", yaxis_title="Custo base (R$/m)")
    return fig
