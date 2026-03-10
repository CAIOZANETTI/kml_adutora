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
    uniform_plot = uniform_df.copy()
    uniform_plot["kind"] = "Uniforme"
    zoned_plot = zoned_df.copy()
    zoned_plot["kind"] = "Por trechos"
    plot_df = pd.concat([uniform_plot, zoned_plot], ignore_index=True, sort=False)

    feasible = plot_df[plot_df["is_feasible"]]
    infeasible = plot_df[~plot_df["is_feasible"]]

    fig = go.Figure()

    # Reprovados como fundo suave
    for kind, symbol in [("Uniforme", "circle"), ("Por trechos", "diamond")]:
        grp = infeasible[infeasible["kind"] == kind]
        if grp.empty:
            continue
        fig.add_trace(go.Scatter(
            x=grp["pump_head_required_m"],
            y=grp["objective_cost_brl"],
            mode="markers",
            name=f"Reprovado — {kind}",
            marker=dict(color=_THEME["surge"], symbol=symbol, size=6, opacity=0.2),
            hovertemplate=f"<b>Reprovado — {kind}</b><br>Bomb.: %{{x:.1f}} m<br>Custo: R$ %{{y:,.0f}}<extra></extra>",
        ))

    # Viaveis em destaque
    _color_ok = {"Uniforme": _THEME["ok"], "Por trechos": "#1e8449"}
    for kind, symbol in [("Uniforme", "circle"), ("Por trechos", "diamond")]:
        grp = feasible[feasible["kind"] == kind]
        if grp.empty:
            continue
        has_vel = "velocity_m_s" in grp.columns
        has_label = "scenario_label" in grp.columns
        customdata = grp[["velocity_m_s"]].values if has_vel else None
        label_extra = "Vel.: %{customdata[0]:.2f} m/s<br>" if has_vel else ""
        fig.add_trace(go.Scatter(
            x=grp["pump_head_required_m"],
            y=grp["objective_cost_brl"],
            mode="markers",
            name=f"Viavel — {kind}",
            marker=dict(
                color=_color_ok[kind],
                symbol=symbol,
                size=11,
                opacity=0.9,
                line=dict(color="white", width=1),
            ),
            customdata=customdata,
            text=grp["scenario_label"].fillna("") if has_label else None,
            hovertemplate=(
                f"<b>Viavel — {kind}</b><br>"
                "%{text}<br>"
                "Bomb.: %{x:.1f} m<br>"
                "Custo: R$ %{y:,.0f}<br>"
                + label_extra
                + "<extra></extra>"
            ),
        ))

    fig.update_layout(
        template="plotly_white",
        height=440,
        xaxis_title="Bombeamento requerido (m)",
        yaxis_title="Custo proxy (R$)",
        yaxis_tickformat=",.2s",
        legend=dict(orientation="v", x=1.01, y=1, xanchor="left"),
        margin=dict(r=10, t=20),
        hovermode="closest",
    )
    return fig


def fig_catalog(catalog_df: pd.DataFrame) -> go.Figure:
    hover_name = "product_id" if "product_id" in catalog_df.columns else catalog_df.columns[0]
    fig = px.scatter(
        catalog_df,
        x="inner_diameter_m",
        y="cost_brl_per_m",
        color="material",
        symbol="pressure_class_bar",
        hover_name=hover_name,
        hover_data={
            "material": True,
            "pressure_class_bar": True,
            "inner_diameter_m": ":.3f",
            "cost_brl_per_m": True,
        },
        labels={
            "pressure_class_bar": "PN (bar)",
            "material": "Material",
            "inner_diameter_m": "Diam. int. (m)",
            "cost_brl_per_m": "R$/m",
        },
    )
    fig.update_traces(marker=dict(size=9, opacity=0.85))
    fig.update_layout(
        template="plotly_white",
        height=440,
        xaxis_title="Diametro interno (m)",
        yaxis_title="Custo base (R$/m)",
        legend_title="Material / PN",
        hovermode="closest",
    )
    return fig
