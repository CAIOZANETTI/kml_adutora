"""Plotly figures for the Gradiente Hidraulico app."""

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
            name="Eixo",
            line=dict(color=_THEME["egl"], width=3),
            marker=dict(size=5, color=detail_df["pressure_bar"], colorscale="Turbo", showscale=True),
            customdata=detail_df[["station_m", "z_terrain_m", "pressure_bar"]],
            hovertemplate=(
                "Estaca %{customdata[0]:.0f} m<br>"
                "Cota: %{customdata[1]:.1f} m<br>"
                "Pressao: %{customdata[2]:.2f} bar<extra></extra>"
            ),
        )
    )

    if devices_df is not None and not devices_df.empty:
        fig.add_trace(
            go.Scattermapbox(
                lat=devices_df["lat"],
                lon=devices_df["lon"],
                mode="markers",
                name="Dispositivos",
                marker=dict(size=10, color=_THEME["surge"], symbol="circle"),
                text=devices_df["type"],
                customdata=devices_df[["station_m", "reason"]],
                hovertemplate="%{text}<br>Estaca %{customdata[0]:.0f} m<br>%{customdata[1]}<extra></extra>",
            )
        )

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=float(detail_df["lat"].mean()), lon=float(detail_df["lon"].mean())),
            zoom=12,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=460,
        legend=dict(bgcolor="rgba(255,255,255,0.85)"),
    )
    return fig


def fig_profile(detail_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=detail_df["station_m"],
            y=detail_df["z_terrain_m"],
            name="Terreno",
            line=dict(color=_THEME["terrain"], width=2, dash="dot"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=detail_df["station_m"],
            y=detail_df["hgl_m"],
            name="Linha piezometrica",
            line=dict(color=_THEME["hgl"], width=3),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=detail_df["station_m"],
            y=detail_df["egl_m"],
            name="Linha de energia",
            line=dict(color=_THEME["egl"], width=2),
        )
    )
    fig.update_layout(
        template="plotly_white",
        height=420,
        hovermode="x unified",
        xaxis_title="Distancia acumulada (m)",
        yaxis_title="Cota / carga (m)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def fig_pressure(detail_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=detail_df["station_m"],
            y=detail_df["pressure_bar"],
            name="Pressao operacional",
            line=dict(color=_THEME["pressure"], width=3),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=detail_df["station_m"],
            y=detail_df["pressure_max_transient_bar"],
            name="Envelope transitorio maximo",
            line=dict(color=_THEME["surge"], width=2, dash="dash"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=detail_df["station_m"],
            y=detail_df["pressure_min_transient_bar"],
            name="Envelope transitorio minimo",
            line=dict(color=_THEME["warn"], width=2, dash="dash"),
        )
    )
    fig.update_layout(
        template="plotly_white",
        height=360,
        hovermode="x unified",
        xaxis_title="Distancia acumulada (m)",
        yaxis_title="Pressao (bar)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def fig_alternatives(alternatives_df: pd.DataFrame) -> go.Figure:
    plot_df = alternatives_df.copy()
    plot_df["label"] = plot_df["material"] + " DN " + plot_df["dn_mm"].astype(str)
    plot_df["status"] = plot_df["is_feasible"].map({True: "Atende", False: "Nao atende"})
    fig = px.scatter(
        plot_df,
        x="velocity_m_s",
        y="objective_cost_brl",
        color="status",
        size="pump_head_required_m",
        hover_name="label",
        hover_data={
            "required_pressure_class_bar": True,
            "subpressure_risk": True,
            "objective_cost_brl": ":.0f",
        },
        color_discrete_map={"Atende": _THEME["ok"], "Nao atende": _THEME["surge"]},
    )
    fig.update_layout(
        template="plotly_white",
        height=380,
        xaxis_title="Velocidade (m/s)",
        yaxis_title="Custo tecnico-economico proxy (R$)",
        legend_title="Status",
    )
    return fig
