"""Gráficas Plotly y componentes visuales del dashboard."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Re-exportar utilidades de salud que viven en el núcleo (evita import extra en páginas)
from health_model import risk_level, time_to_failure  # noqa: E402,F401

# paleta
ACC = "#1f4e79"
OK = "#2e9d57"
WARN = "#d99a00"
BAD = "#d64545"
GRAY = "#a6a6a6"
GRID = "#d9dee7"

TIPO_LABEL = {"servidor": "Servidor", "camara": "Cámara (reconocimiento facial)",
              "red": "Equipo de red"}
TIPO_ICON = {"servidor": "🖥️", "camara": "📹", "red": "🌐"}


def tipo_label(t: str) -> str:
    return TIPO_LABEL.get(t, t)


def health_color(h: float) -> str:
    if h is None or (isinstance(h, float) and np.isnan(h)):
        return BAD
    if h >= 70:
        return OK
    if h >= 40:
        return WARN
    return BAD


# sparkline SVG
def sparkline_svg(values, color: str = ACC, w: int = 150, h: int = 34) -> str:
    """Genera un sparkline SVG ligero a partir de una serie (None = hueco)."""
    vals = [v for v in values if v is not None and not (isinstance(v, float) and np.isnan(v))]
    if not vals:
        return ""
    n = len(values)
    pts, run = [], []
    for i, v in enumerate(values):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            if run:
                pts.append("M" + "L".join(run)); run = []
            continue
        x = (i / max(n - 1, 1)) * w
        y = h - (v / 100) * h
        run.append(f"{x:.1f},{y:.1f}")
    if run:
        pts.append("M" + "L".join(run))
    d = "".join(pts)
    last = vals[-1]
    lx = ((n - 1) / max(n - 1, 1)) * w
    ly = h - (last / 100) * h
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
            f'style="width:100%;height:{h}px;display:block">'
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.8"/>'
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.2" fill="{color}"/></svg>')


# gráficas plotly
def fig_health_timeline(g: pd.DataFrame, hours_back: int = 168) -> go.Figure:
    """Puntaje de salud con bandas semáforo, fallas y alertas."""
    g = g.sort_values("hour")
    last_h = int(g["hour"].max())
    gg = g[g["hour"] >= last_h - hours_back].copy()
    fig = go.Figure()
    # bandas
    for lo, hi, c in [(70, 100, OK), (40, 70, WARN), (0, 40, BAD)]:
        fig.add_hrect(y0=lo, y1=hi, fillcolor=c, opacity=0.10, line_width=0)
    fig.add_trace(go.Scatter(x=gg["hour"], y=gg["health"], mode="lines",
                            line=dict(color=ACC, width=2.2), name="Salud"))
    # fallas
    fall = gg[gg["falla"] == 1]
    if len(fall):
        fig.add_trace(go.Scatter(x=fall["hour"], y=[100] * len(fall), mode="markers",
                                 marker=dict(symbol="triangle-down", size=12, color=BAD),
                                 name="Falla", hovertemplate="Falla<br>hora %{x}<extra></extra>"))
    # alertas modelo (solo existen en full_test; el guard evita KeyError en df)
    if "alerta_ml" in gg.columns:
        al = gg[gg["alerta_ml"]]
        if len(al):
            fig.add_trace(go.Scatter(x=al["hour"], y=al["health"], mode="markers",
                                     marker=dict(symbol="diamond", size=9, color=WARN,
                                                  line=dict(width=1, color="white")),
                                     name="Alerta modelo"))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                      yaxis=dict(range=[0, 100], title="Salud"),
                      xaxis=dict(title="Hora"), legend=dict(orientation="h", y=1.12),
                      plot_bgcolor="white", paper_bgcolor="white")
    return fig


def fig_telemetry(g: pd.DataFrame, hours_back: int = 168) -> go.Figure:
    """Cuatro métricas de telemetría en subgráficas."""
    g = g.sort_values("hour")
    last_h = int(g["hour"].max())
    gg = g[g["hour"] >= last_h - hours_back].copy()
    x = gg["hour"]
    fig = make_subplots(rows=2, cols=2, shared_xaxes=True,
                       subplot_titles=("Latencia (ms)", "Temperatura (°C)",
                                       "Pérdida (%)", "CPU (%)"))
    specs = [
        (gg["latencia_ms"], "#7f6000"),
        (gg["temp_c"], "#c55a11"),
        (gg["perdida_pct"], "#7030a0"),
        (gg["cpu_pct"], "#2e9d57"),
    ]
    for i, (s, c) in enumerate(specs, start=1):
        row, col = ((i - 1) // 2) + 1, ((i - 1) % 2) + 1
        fig.add_trace(go.Scatter(x=x, y=s, mode="lines", line=dict(color=c, width=1.8),
                                 showlegend=False), row=row, col=col)
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=26, b=10),
                      plot_bgcolor="white", paper_bgcolor="white")
    fig.update_xaxes(showgrid=True, gridcolor=GRID)
    fig.update_yaxes(showgrid=True, gridcolor=GRID)
    return fig


def fig_gauge(health: float) -> go.Figure:
    """Medidor del puntaje de salud actual."""
    color = health_color(health)
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=float(health),
        number={"font": {"size": 40, "color": color}},
        gauge=dict(axis=dict(range=[0, 100]), bar=dict(color=color, thickness=0.28),
                   bgcolor="#eef2f7", borderwidth=0,
                   steps=[dict(range=[0, 40], color="#f8c9c9"),
                          dict(range=[40, 70], color="#ffe9b3"),
                          dict(range=[70, 100], color="#cde9d4")],
                   threshold=dict(line=dict(color="#1b2330", width=2), value=float(health)))))
    fig.update_layout(height=170, margin=dict(l=10, r=10, t=0, b=0))
    return fig


def fig_roc(fpr, tpr, auc) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=fpr, y=tpr, mode="lines", line=dict(color=ACC, width=2.5),
                             name=f"AUC = {auc}"))
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines",
                             line=dict(color=GRAY, dash="dash"), showlegend=False))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                      xaxis=dict(title="Tasa de falsos positivos"),
                      yaxis=dict(title="Tasa de verdaderos positivos"),
                      plot_bgcolor="white", paper_bgcolor="white",
                      legend=dict(x=0.4, y=0.05))
    return fig


def fig_pr(rc, pr, ap) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rc, y=pr, mode="lines", line=dict(color="#c55a11", width=2.5),
                             name=f"AP = {ap}"))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                      xaxis=dict(title="Recall (exhaustividad)"),
                      yaxis=dict(title="Precisión"),
                      plot_bgcolor="white", paper_bgcolor="white",
                      legend=dict(x=0.55, y=0.05))
    return fig


def fig_importance(imp: pd.Series, top: int = 15) -> go.Figure:
    s = imp.sort_values().tail(top)
    fig = go.Figure(go.Bar(x=s.values, y=s.index, orientation="h", marker_color=ACC))
    fig.update_layout(height=max(320, 22 * top), margin=dict(l=10, r=10, t=10, b=10),
                      xaxis=dict(title="Importancia relativa"),
                      plot_bgcolor="white", paper_bgcolor="white")
    return fig


def fig_comparison(m_ml: dict, m_th: dict) -> go.Figure:
    cats = ["Umbrales fijos<br>(reactivo)", "Modelo<br>predictivo"]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Fallas anticipadas (≤24 h)",
                                                       "Falsas alertas / equipo / semana"))
    fig.add_trace(go.Bar(x=cats, y=[m_th["pct_anticipadas"], m_ml["pct_anticipadas"]],
                         marker_color=[GRAY, ACC], showlegend=False,
                         text=[f'{m_th["pct_anticipadas"]}%', f'{m_ml["pct_anticipadas"]}%%'],
                         textposition="outside"), row=1, col=1)
    fig.add_trace(go.Bar(x=cats, y=[m_th["falsas_por_equipo_semana"], m_ml["falsas_por_equipo_semana"]],
                         marker_color=[GRAY, ACC], showlegend=False,
                         text=[m_th["falsas_por_equipo_semana"], m_ml["falsas_por_equipo_semana"]],
                         textposition="outside"), row=1, col=2)
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=36, b=10),
                      plot_bgcolor="white", paper_bgcolor="white")
    return fig


def fig_confusion(cm) -> go.Figure:
    cm = np.array(cm)
    fig = go.Figure(go.Heatmap(z=cm, x=["Predicho sano", "Predicho falla"],
                               y=["Real sano", "Real falla"], colorscale="Blues",
                               text=cm, texttemplate="%{text}", hovertemplate=""))
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10),
                      yaxis=dict(autorange="reversed"),
                      plot_bgcolor="white", paper_bgcolor="white")
    return fig


def fig_health_per_device(summary: pd.DataFrame) -> go.Figure:
    """Barras horizontales: salud actual de todos los equipos, coloreadas por riesgo."""
    s = summary.sort_values("health")
    colors = [health_color(h) for h in s["health"]]
    fig = go.Figure(go.Bar(x=s["health"], y=s["device"], orientation="h",
                           marker_color=colors, text=s["health"], textposition="outside",
                           texttemplate="%{text}", showlegend=False))
    fig.update_layout(height=max(300, 22 * len(s)), margin=dict(l=10, r=40, t=10, b=10),
                      xaxis=dict(title="Puntaje de salud", range=[0, 105]),
                      plot_bgcolor="white", paper_bgcolor="white")
    return fig


# estado de conexión
def connected_pipe():
    """Devuelve (branch, pipe) desde session_state o (None, None) si no hay."""
    import streamlit as st
    branch = st.session_state.get("branch")
    pipe = st.session_state.get("pipe")
    return branch, pipe
