"""Panel de monitoreo: estado de toda la red de sucursales (modo real) o por equipo (simulado)."""
import os

import plotly.graph_objects as go
import streamlit as st

import dashboard_helpers as dh

st.set_page_config(page_title="Panel de monitoreo", page_icon="📊", layout="wide")

EXCEL_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "MasterVsJuanitaV4.xlsx")
REAL_MODE = os.path.exists(EXCEL_FILE)

branch = st.session_state.get("branch")

# modo con datos del Excel
if REAL_MODE:
    import real_data as rd

    st.title("📊 Panel de monitoreo — Red completa")
    st.caption("Grupo Salinas · Razberi / 3VR OpCenter · datos reales del Excel")

    with st.spinner("Cargando resumen de 1,797 sucursales…"):
        summary = rd.full_network_summary()

    # kPIs
    n_total = len(summary)
    grabando = int(summary["grabando"].sum())
    no_grab = n_total - grabando
    riesgo_alto = int((summary["nivel_riesgo"] == "Alto").sum())
    riesgo_medio = int((summary["nivel_riesgo"] == "Medio").sum())
    cam_fuera = int(summary["camaras_fuera"].sum())
    salud_prom = round(float(summary["health"].mean()), 1)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total sucursales", f"{n_total:,}")
    c2.metric("Grabando", f"{grabando:,}", delta_color="off")
    c3.metric("No grabando", f"{no_grab:,}",
              delta=f"⚠ {no_grab}" if no_grab > 0 else None, delta_color="inverse")
    c4.metric("Riesgo Alto", riesgo_alto, delta_color="inverse")
    c5.metric("Cámaras fuera", f"{cam_fuera:,}", delta_color="inverse")
    c6.metric("Salud promedio", salud_prom)
    st.divider()

    # filtros
    colF1, colF2, colF3 = st.columns(3)
    with colF1:
        filtro_riesgo = st.multiselect("Filtrar por riesgo",
                                        ["Alto", "Medio", "Bajo"],
                                        default=["Alto", "Medio", "Bajo"])
    with colF2:
        filtro_estado = st.multiselect("Filtrar por estado",
                                        ["operando", "cámaras fuera", "no grabando"],
                                        default=["operando", "cámaras fuera", "no grabando"])
    with colF3:
        buscar = st.text_input("Buscar sucursal / IP / ECO", placeholder="ej. NOGALES o 10.41")

    filtered = summary[
        summary["nivel_riesgo"].isin(filtro_riesgo) &
        summary["estado"].isin(filtro_estado)
    ]
    if buscar.strip():
        q = buscar.strip().lower()
        filtered = filtered[
            filtered["sucursal"].str.lower().str.contains(q, na=False) |
            filtered["ip"].str.contains(q, na=False) |
            filtered["eco"].astype(str).str.contains(q, na=False)
        ]

    st.caption(f"Mostrando {len(filtered):,} de {n_total:,} sucursales")

    # tabla principal
    show = filtered[["eco", "ip", "sucursal", "health", "nivel_riesgo",
                      "estado", "camaras_fuera", "n_camaras", "n_inc"]].copy()
    show.columns = ["ECO", "IP", "Sucursal", "Salud", "Riesgo",
                    "Estado", "Cámaras fuera", "Cámaras total", "Incidentes"]
    st.dataframe(
        show.sort_values("Salud"),
        use_container_width=False,
        hide_index=True,
        column_config={
            "Salud": st.column_config.ProgressColumn(
                "Salud", min_value=0, max_value=100, format="%d"),
            "IP": st.column_config.TextColumn("IP", width="medium"),
        }
    )

    # distribución de salud
    st.divider()
    st.subheader("Distribución de salud en toda la red")
    colH, colP = st.columns(2)
    with colH:
        fig_hist = go.Figure(go.Histogram(
            x=summary["health"], nbinsx=30,
            marker_color=dh.ACC, opacity=0.8))
        fig_hist.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10),
                               xaxis=dict(title="Puntaje de salud (0–100)"),
                               yaxis=dict(title="Sucursales"),
                               plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_hist, use_container_width=False)
    with colP:
        counts = summary["nivel_riesgo"].value_counts()
        fig_pie = go.Figure(go.Pie(
            labels=counts.index, values=counts.values,
            marker_colors=[dh.BAD, dh.WARN, dh.OK],
            hole=0.4))
        fig_pie.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_pie, use_container_width=False)

    # sucursales con mayor riesgo
    st.subheader("Top 20 sucursales con mayor riesgo")
    top20 = summary.sort_values("health").head(20)
    colors = [dh.health_color(h) for h in top20["health"]]
    fig_top = go.Figure(go.Bar(
        x=top20["health"],
        y=top20["sucursal"].str[:35],
        orientation="h",
        marker_color=colors,
        text=top20["health"].astype(int),
        textposition="outside",
        customdata=top20[["ip", "camaras_fuera", "estado"]].values,
        hovertemplate="<b>%{y}</b><br>IP: %{customdata[0]}<br>"
                      "Salud: %{x}<br>Cámaras fuera: %{customdata[1]}<br>"
                      "Estado: %{customdata[2]}<extra></extra>",
    ))
    fig_top.update_layout(height=480, margin=dict(l=10, r=50, t=10, b=10),
                          xaxis=dict(title="Salud", range=[0, 105]),
                          plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig_top, use_container_width=False)

    # exportar
    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exportar tabla filtrada (CSV)", csv,
                       file_name="red_sucursales.csv", mime="text/csv")
    st.stop()


# modo simulado
pipe = st.session_state.get("pipe")
if pipe is None:
    st.warning("Primero conéctate a una sucursal desde la pantalla principal.")
    st.page_link("app.py", label="➡️ Ir a la conexión", icon="🛰️")
    st.stop()

st.title("📊 Panel de monitoreo (simulado)")
st.caption(f"{branch['nombre']} · `{branch['ip']}`")

df = pipe.df
s = pipe.summary
NOW = pipe.now_hour

operando = int((s["estado"] == "operando").sum())
alerta = int((s["estado"] == "en alerta").sum())
fuera = int((s["estado"] == "fuera de servicio").sum())
salud_prom = round(float(s["health"].mean()), 1)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Equipos", len(s))
c2.metric("Operando", operando)
c3.metric("En alerta", alerta)
c4.metric("Fuera de servicio", fuera)
c5.metric("Salud promedio", salud_prom)
st.divider()

devs = sorted(s["device"].tolist())
default_dev = s.loc[s["health"].idxmin(), "device"]
sel = st.selectbox("Selecciona un equipo", devs, index=devs.index(default_dev))

st.subheader("Estado de los equipos")
cols = st.columns(5)
for i, (_, row) in enumerate(s.iterrows()):
    dev = row["device"]
    h = row["health"]
    color = dh.health_color(h)
    g = df[(df["device"] == dev) & (df["hour"] <= NOW)].sort_values("hour").tail(168)
    spark = dh.sparkline_svg(g["health"].tolist(), color)
    estado = row["estado"]
    chip = ("ok" if estado == "operando" else "warn" if estado == "en alerta"
            else "bad" if "fuera" in estado else "info")
    icon = dh.TIPO_ICON.get(row["tipo"], "▪")
    with cols[i % 5]:
        st.markdown(f"""<div class="devcard">
        <div style="display:flex;justify-content:space-between;align-items:center">
        <b>{icon} {dev}</b><span class="chip {chip}" style="font-size:10px">{estado}</span>
        </div>
        <div style="font-size:30px;font-weight:700;color:{color};text-align:center">{int(h)}</div>
        <div style="color:#667085;font-size:11px;text-align:center">{dh.tipo_label(row['tipo'])}</div>
        {spark}</div>""", unsafe_allow_html=True)
st.write("")

st.subheader(f"Detalle: {sel}")
g = df[(df["device"] == sel) & (df["hour"] <= NOW)].sort_values("hour")
row = s[s["device"] == sel].iloc[0]
h = row["health"]

colL, colR = st.columns([1, 2.2])
with colL:
    st.plotly_chart(dh.fig_gauge(h), use_container_width=False)
    nivel, _, accion = dh.risk_level(h)
    nchip = "ok" if nivel == "Bajo" else "warn" if nivel == "Medio" else "bad"
    st.markdown(f"**Nivel de riesgo:** <span class='chip {nchip}'>{nivel}</span>",
                unsafe_allow_html=True)
    st.markdown(f"**Ventana:** {dh.time_to_failure(h, row['prob'])}")
    st.markdown(f"**Recomendación:** {accion}")
with colR:
    st.plotly_chart(dh.fig_health_timeline(g, 168), use_container_width=False)

st.markdown("**Telemetría (últimos 7 días)**")
st.plotly_chart(dh.fig_telemetry(g, 168), use_container_width=False)

with st.expander("Salud de todos los equipos (ranking)"):
    st.plotly_chart(dh.fig_health_per_device(s), use_container_width=False)
