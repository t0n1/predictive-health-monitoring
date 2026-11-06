"""
Telemetría e historial de incidentes reales — Razberi / 3VR.
En modo real: analiza el historial completo de incidentes del Excel.
En modo simulado: exploración de telemetría sintética.
"""
import os

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import pandas as pd

import dashboard_helpers as dh

st.set_page_config(page_title="Telemetría e Incidentes", page_icon="📡", layout="wide")

EXCEL_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "MasterVsJuanitaV4.xlsx")
REAL_MODE = os.path.exists(EXCEL_FILE)

# modo con datos del Excel
if REAL_MODE:
    import real_data as rd

    st.title("📡 Historial de incidentes reales — Razberi / 3VR")
    st.caption("Grupo Salinas · Dialogus · 333 incidentes reales (dic 2020 – oct 2021)")

    with st.spinner("Cargando datos…"):
        sheets = rd.load_excel()
        inc_raw = sheets["incidentes"].copy()
        summary = rd.full_network_summary()

    # filtrar fechas válidas
    inc = inc_raw[inc_raw["fecha"] > "2019-01-01"].copy()
    inc["mes"] = inc["fecha"].dt.to_period("M").astype(str)
    inc["semana"] = inc["fecha"].dt.to_period("W").astype(str)
    inc["dia_semana"] = inc["fecha"].dt.day_name()

    # kPIs
    n_inc = len(inc)
    n_altos = int((inc["impacto"].str.strip().str.lower() == "alto").sum())
    n_abiertos = int(inc["status"].str.lower().isin(
        ["monitorear", "en proceso", "por asignar", "envio a soporte"]).sum())
    suc_afectadas = int(inc["eco"].nunique())
    resolucion = (inc["fecha_de_cierre"] - inc["fecha"]).dt.days
    med_dias = round(resolucion.dropna().median(), 1)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total incidentes", n_inc)
    c2.metric("Impacto Alto", n_altos, delta_color="inverse")
    c3.metric("Sin cerrar", n_abiertos, delta_color="inverse")
    c4.metric("Sucursales afectadas", suc_afectadas)
    c5.metric("Mediana resolución", f"{med_dias} días" if med_dias == med_dias else "N/D")
    st.divider()

    # filtros
    colF1, colF2, colF3 = st.columns(3)
    with colF1:
        impactos_sel = st.multiselect(
            "Impacto", ["Alto", "alto", "Medio", "medio", "Bajo"],
            default=["Alto", "alto", "Medio", "medio", "Bajo"])
    with colF2:
        status_sel = st.multiselect(
            "Status", inc["status"].dropna().unique().tolist(),
            default=inc["status"].dropna().unique().tolist())
    with colF3:
        tipo_sel = st.multiselect(
            "Tipo de falla", inc["tipo_falla"].dropna().unique().tolist(),
            default=inc["tipo_falla"].dropna().unique().tolist())

    filt = inc[
        inc["impacto"].isin(impactos_sel) &
        inc["status"].isin(status_sel) &
        inc["tipo_falla"].isin(tipo_sel)
    ]

    # gráficas de análisis
    st.subheader("Evolución de incidentes por mes")
    by_month = filt.groupby("mes").size().reset_index(name="n")
    by_month_imp = filt.groupby(["mes", "impacto"]).size().reset_index(name="n")
    fig_time = go.Figure()
    for imp, color in [("Alto", dh.BAD), ("alto", dh.BAD),
                        ("Medio", dh.WARN), ("medio", dh.WARN),
                        ("Bajo", dh.OK)]:
        sub = by_month_imp[by_month_imp["impacto"] == imp]
        if len(sub):
            fig_time.add_trace(go.Bar(x=sub["mes"], y=sub["n"],
                                       name=f"Impacto {imp.title()}",
                                       marker_color=color))
    fig_time.update_layout(height=300, barmode="stack",
                           margin=dict(l=10, r=10, t=10, b=10),
                           xaxis=dict(title="Mes"),
                           yaxis=dict(title="Incidentes"),
                           plot_bgcolor="white", paper_bgcolor="white",
                           legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig_time, use_container_width=False)

    # donut tipo de falla + barras ingeniero
    colA, colB = st.columns(2)
    with colA:
        st.subheader("Tipos de falla más frecuentes")
        tipo_cnt = filt["tipo_falla"].value_counts().head(10)
        fig_tipo = go.Figure(go.Pie(
            labels=tipo_cnt.index, values=tipo_cnt.values,
            hole=0.38,
            marker_colors=[dh.BAD, dh.WARN, dh.ACC, dh.OK,
                            "#7030a0", "#c55a11", "#2e9d57",
                            "#a6a6a6", "#7f6000", "#1f4e79"]))
        fig_tipo.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_tipo, use_container_width=False)

    with colB:
        st.subheader("Incidentes por ingeniero")
        if "ingeniero" in filt.columns:
            ing_cnt = filt["ingeniero"].value_counts().head(8)
            fig_ing = go.Figure(go.Bar(
                y=ing_cnt.index, x=ing_cnt.values,
                orientation="h", marker_color=dh.ACC,
                text=ing_cnt.values, textposition="outside"))
            fig_ing.update_layout(height=300,
                                   margin=dict(l=10, r=40, t=10, b=10),
                                   xaxis=dict(title="Incidentes"),
                                   plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig_ing, use_container_width=False)

    # mapa de calor: tipo de falla × impacto
    st.subheader("Matriz: tipo de falla × impacto")
    heatmap_data = (filt.groupby(["tipo_falla", "impacto"])
                        .size().reset_index(name="n"))
    pivot = heatmap_data.pivot(index="tipo_falla",
                                columns="impacto", values="n").fillna(0)
    fig_heat = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale="Reds",
        text=pivot.values.astype(int),
        texttemplate="%{text}",
        hovertemplate="%{y} × %{x}: %{z}<extra></extra>"))
    fig_heat.update_layout(height=max(300, 28 * len(pivot)),
                           margin=dict(l=10, r=10, t=10, b=10),
                           plot_bgcolor="white", paper_bgcolor="white",
                           xaxis=dict(title="Impacto"),
                           yaxis=dict(title="Tipo de falla"))
    st.plotly_chart(fig_heat, use_container_width=False)

    # sucursales con más incidentes
    st.subheader("Top 15 sucursales con más incidentes")
    top_suc = (filt.groupby("eco")
                   .agg(n_inc=("score_impacto", "count"),
                        score=("score_impacto", "sum"))
                   .reset_index()
                   .sort_values("score", ascending=False)
                   .head(15))
    # enriquecer con nombre e IP
    top_suc = top_suc.merge(
        summary[["eco", "ip", "sucursal", "health"]].drop_duplicates("eco"),
        on="eco", how="left")
    fig_top = go.Figure(go.Bar(
        x=top_suc["score"],
        y=top_suc.apply(lambda r: f"{r['sucursal'][:30]} ({r['eco']})"
                         if pd.notna(r["sucursal"]) else str(r["eco"]), axis=1),
        orientation="h",
        marker_color=[dh.health_color(h) if pd.notna(h) else dh.GRAY
                       for h in top_suc["health"]],
        customdata=top_suc[["ip", "n_inc", "health"]].values,
        hovertemplate="<b>%{y}</b><br>IP: %{customdata[0]}<br>"
                       "Incidentes: %{customdata[1]}<br>"
                       "Salud: %{customdata[2]}<extra></extra>",
        text=top_suc["n_inc"].astype(int),
        textposition="outside"))
    fig_top.update_layout(height=420,
                           margin=dict(l=10, r=50, t=10, b=10),
                           xaxis=dict(title="Score de incidentes acumulado"),
                           plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig_top, use_container_width=False)

    # tabla detallada
    st.divider()
    st.subheader("Detalle de incidentes")
    show_cols = [c for c in ["fecha", "eco", "ip", "tipo_falla", "impacto",
                              "obs", "status", "fecha_de_cierre", "ingeniero"]
                 if c in filt.columns]
    st.dataframe(
        filt[show_cols].sort_values("fecha", ascending=False),
        use_container_width=False,
        hide_index=True,
        column_config={
            "obs": st.column_config.TextColumn("Observaciones", width="large"),
            "impacto": st.column_config.TextColumn("Impacto", width="small"),
        })

    # exportar
    csv = filt[show_cols].to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exportar incidentes filtrados (CSV)", csv,
                        file_name="incidentes_reales.csv", mime="text/csv")

    # detalle por sucursal
    st.divider()
    st.subheader("🔍 Detalle de incidentes por sucursal")
    all_ecos = sorted(filt["eco"].dropna().unique().tolist())
    eco_sel = st.selectbox(
        "Selecciona sucursal (ECO)",
        all_ecos,
        format_func=lambda e: f"{int(e)} — {summary[summary['eco']==e]['sucursal'].values[0] if len(summary[summary['eco']==e]) else ''}")
    if eco_sel:
        branch_inc = filt[filt["eco"] == eco_sel]
        branch_row = summary[summary["eco"] == eco_sel]
        if len(branch_row):
            br = branch_row.iloc[0]
            st.markdown(
                f"**{br['sucursal']}** · IP `{br['ip']}` · "
                f"Salud: **{br['health']:.0f}** · Estado: `{br['estado']}`")
        st.dataframe(branch_inc[show_cols].sort_values("fecha", ascending=False),
                     use_container_width=False, hide_index=True)
    st.stop()


# modo simulado
branch = st.session_state.get("branch")
pipe = st.session_state.get("pipe")
if pipe is None:
    st.warning("Primero conéctate a una sucursal desde la pantalla principal.")
    st.page_link("app.py", label="➡️ Ir a la conexión", icon="🛰️")
    st.stop()

st.title("📡 Telemetría (simulado)")
st.caption(f"{branch['nombre']} · `{branch['ip']}`")

raw = pipe.raw
NOW = pipe.now_hour
devs = sorted(raw["device"].unique().tolist())
metrics = ["latencia_ms", "cpu_pct", "mem_pct", "temp_c", "perdida_pct", "reinicios"]
metric_labels = {"latencia_ms": "Latencia (ms)", "cpu_pct": "CPU (%)",
                 "mem_pct": "Memoria (%)", "temp_c": "Temperatura (°C)",
                 "perdida_pct": "Pérdida (%)", "reinicios": "Reinicios"}

colF1, colF2 = st.columns(2)
with colF1:
    sel_devs = st.multiselect("Equipos", devs, default=devs[:3])
with colF2:
    metric = st.selectbox("Métrica", metrics, format_func=lambda x: metric_labels[x])
dias = st.select_slider("Días recientes", [7, 14, 30, 60, 90, 120], value=30)

if sel_devs:
    sub = raw[(raw["device"].isin(sel_devs)) &
              (raw["hour"] >= NOW - dias * 24 + 1) &
              (raw["hour"] <= NOW)]
    fig = go.Figure()
    for dev in sel_devs:
        g = sub[sub["device"] == dev].sort_values("hour")
        fig.add_trace(go.Scatter(x=g["hour"], y=g[metric],
                                  mode="lines", name=dev, line=dict(width=1.4)))
    falls = sub[sub["falla"] == 1]
    if len(falls):
        fig.add_trace(go.Scatter(x=falls["hour"],
                                  y=[sub[metric].max()] * len(falls),
                                  mode="markers",
                                  marker=dict(symbol="triangle-down", size=9, color=dh.BAD),
                                  name="Falla"))
    fig.update_layout(height=380, plot_bgcolor="white", paper_bgcolor="white",
                      margin=dict(l=10, r=10, t=10, b=10),
                      xaxis=dict(title="Hora"), yaxis=dict(title=metric_labels[metric]))
    st.plotly_chart(fig, use_container_width=False)

show = raw[(raw["device"].isin(sel_devs)) & (raw["hour"] <= NOW)] if sel_devs else raw
show = show.sort_values(["device", "hour"])
st.dataframe(show.head(500), use_container_width=False, hide_index=True)
csv = show.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Exportar CSV", csv,
                    file_name=f"telemetria_{branch['ip'].replace('.','_')}.csv",
                    mime="text/csv")
