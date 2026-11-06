"""Alertas tempranas priorizadas — modo real (Excel) o simulado."""
import os

import streamlit as st

import dashboard_helpers as dh

st.set_page_config(page_title="Alertas tempranas", page_icon="🚨", layout="wide")

EXCEL_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "MasterVsJuanitaV4.xlsx")
REAL_MODE = os.path.exists(EXCEL_FILE)

# modo con datos del Excel
if REAL_MODE:
    import real_data as rd

    st.title("🚨 Alertas tempranas — Red completa")
    st.caption("Grupo Salinas · Razberi / 3VR · prioridad por nivel de riesgo")

    with st.spinner("Calculando riesgo de 1,797 sucursales…"):
        summary = rd.full_network_summary()

    at_risk = summary[summary["nivel_riesgo"].isin(["Alto", "Medio"])].sort_values("health")
    no_grab = summary[~summary["grabando"]]
    cam_out = summary[(summary["camaras_fuera"] > 0) & summary["grabando"]]

    # kPIs
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sucursales en riesgo Alto/Medio", len(at_risk),
              delta_color="inverse")
    c2.metric("No grabando ahora", len(no_grab),
              delta=f"⚠ {len(no_grab)}" if len(no_grab) > 0 else None,
              delta_color="inverse")
    c3.metric("Con cámaras fuera (grabando)", len(cam_out), delta_color="inverse")
    c4.metric("Total cámaras fuera de línea", int(summary["camaras_fuera"].sum()),
              delta_color="inverse")
    st.divider()

    # sucursales NO grabando
    if len(no_grab):
        st.subheader(f"🔴 Sucursales que NO están grabando ({len(no_grab)})")
        st.caption("Estas sucursales requieren atención inmediata — el NVR no responde o el 3VR está detenido.")
        for _, row in no_grab.sort_values("health").iterrows():
            with st.container(border=True):
                cc1, cc2 = st.columns([1.5, 2.5])
                with cc1:
                    st.markdown(f"### 📹 {row['sucursal']}")
                    st.markdown(
                        f"<span class='chip bad'>NO GRABANDO</span> "
                        f"<span class='chip info'>Riesgo {row['nivel_riesgo']}</span>",
                        unsafe_allow_html=True)
                    st.caption(f"IP: `{row['ip']}` · ECO: `{row['eco']}`")
                with cc2:
                    st.markdown(
                        f"**Salud:** <span style='font-size:24px;font-weight:700;"
                        f"color:{dh.health_color(row['health'])}'>{row['health']:.0f}</span>  "
                        f"· Estado ayer: `{row['estado_ayer']}` → hoy: `{row['estado_hoy']}`",
                        unsafe_allow_html=True)
                    if row["n_inc"] > 0:
                        st.caption(f"Incidentes históricos: {row['n_inc']}")
                    if str(row["comentarios"]).strip() not in ("nan", ""):
                        st.caption(f"Comentario: {row['comentarios']}")
        st.divider()

    # sucursales con cámaras fuera de línea
    if len(cam_out):
        st.subheader(f"🟡 Sucursales con cámaras fuera de línea ({len(cam_out)})")
        show = cam_out[["eco", "ip", "sucursal", "camaras_fuera", "n_camaras",
                         "health", "nivel_riesgo", "n_inc"]].copy()
        show.columns = ["ECO", "IP", "Sucursal", "Cámaras fuera",
                         "Total cámaras", "Salud", "Riesgo", "Incidentes"]
        st.dataframe(show.sort_values("Salud"),
                     use_container_width=False, hide_index=True,
                     column_config={"Salud": st.column_config.ProgressColumn(
                         "Salud", min_value=0, max_value=100, format="%d")})
        st.divider()

    # comparación de esquemas
    st.subheader("📈 Modelo predictivo vs. monitoreo reactivo")
    st.markdown("""
El **monitoreo reactivo** (umbrales fijos) detecta una falla **cuando ya ocurrió**:
el NVR dejó de grabar, la cámara se desconectó. La reacción es posterior al evento.

El **modelo predictivo** calcula un puntaje de salud continuo basado en:
- Frecuencia e impacto del historial de incidentes de cada sucursal
- Porcentaje de cámaras fuera de línea vs. total esperado
- Estado de grabación actual vs. ayer (cambio = señal de alerta)
- Historial de re-instalaciones (planchado = mayor riesgo futuro)

Esto permite **priorizar** qué sucursales requieren atención antes de que fallen completamente,
en lugar de reaccionar cuando el 3VR ya no responde.
    """)

    # gráfica comparativa
    import plotly.graph_objects as go
    fig_comp = go.Figure()
    cats = ["Reactivo\n(umbrales)", "Predictivo\n(modelo)"]
    # con datos reales: reactivo = solo detecta no_grabando; predictivo = at_risk completo
    pct_reactivo = round(100 * len(no_grab) / len(summary), 1)
    pct_predictivo = round(100 * len(at_risk) / len(summary), 1)
    fig_comp.add_trace(go.Bar(x=cats, y=[pct_reactivo, pct_predictivo],
                               marker_color=[dh.GRAY, dh.ACC],
                               text=[f"{pct_reactivo}%", f"{pct_predictivo}%"],
                               textposition="outside"))
    fig_comp.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10),
                           yaxis=dict(title="% sucursales en alerta"),
                           plot_bgcolor="white", paper_bgcolor="white",
                           title="Sucursales en alerta detectadas (% de la red)")
    st.plotly_chart(fig_comp, use_container_width=False)
    st.caption(
        f"Reactivo: detecta {len(no_grab)} sucursales que ya dejaron de grabar ({pct_reactivo}% de la red).  \n"
        f"Predictivo: identifica {len(at_risk)} sucursales con riesgo Alto/Medio ({pct_predictivo}% de la red), "
        f"incluyendo las que aún graban pero con señales de degradación.")

    csv = at_risk.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exportar sucursales en riesgo (CSV)", csv,
                       file_name="alertas_sucursales.csv", mime="text/csv")
    st.stop()


# modo simulado
branch = st.session_state.get("branch")
pipe = st.session_state.get("pipe")
if pipe is None:
    st.warning("Primero conéctate a una sucursal desde la pantalla principal.")
    st.page_link("app.py", label="➡️ Ir a la conexión", icon="🛰️")
    st.stop()

st.title("🚨 Alertas tempranas (simulado)")
st.caption(f"{branch['nombre']} · `{branch['ip']}`")

al = pipe.alerts
df = pipe.df
NOW = pipe.now_hour

c1, c2, c3, c4 = st.columns(4)
crit = int((al["health"] < 40).sum()) if len(al) else 0
c1.metric("Alertas activas", len(al))
c2.metric("Riesgo crítico", crit, delta_color="inverse")
st.divider()

if al.empty:
    st.success("✅ Sin alertas activas.")
else:
    for _, row in al.iterrows():
        dev = row["device"]
        h = row["health"]
        color = dh.health_color(h)
        nivel, _, accion = dh.risk_level(h)
        g = df[(df["device"] == dev) & (df["hour"] <= NOW)].sort_values("hour").tail(96)
        spark = dh.sparkline_svg(g["health"].tolist(), color)
        chipcls = "bad" if nivel == "Alto" else "warn"
        with st.container(border=True):
            cc1, cc2, cc3 = st.columns([1.4, 2.4, 1.6])
            with cc1:
                st.markdown(f"### {dh.TIPO_ICON.get(row['tipo'], '▪')} {dev}")
                st.markdown(f"<span class='chip {chipcls}'>RIESGO {nivel.upper()}</span>",
                            unsafe_allow_html=True)
            with cc2:
                st.markdown(
                    f"**Salud:** <span style='font-size:26px;font-weight:700;color:{color}'>"
                    f"{int(h)}</span>  · **P(falla):** {row['prob']:.0%}",
                    unsafe_allow_html=True)
                st.markdown(f"**Ventana:** {row['ventana']}  \n**Recomendación:** {accion}")
                st.markdown(spark, unsafe_allow_html=True)
            with cc3:
                cur = g[g["down"] == 0].iloc[-1] if (g["down"] == 0).any() else g.iloc[-1]
                st.metric("Latencia", f"{cur['latencia_ms']:.0f} ms")
                st.metric("Temperatura", f"{cur['temp_c']:.1f} °C")

import health_model as hm
m_ml, m_th = pipe.m_ml, pipe.m_th
st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Fallas anticipadas (modelo)", f"{m_ml['pct_anticipadas']}%",
          delta=f"vs {m_th['pct_anticipadas']}%", delta_color="off")
c2.metric("Anticipación mediana", f"{m_ml['anticipacion_mediana_h']:.0f} h")
c3.metric("Falsas alertas/sem", m_ml["falsas_por_equipo_semana"])
c4.metric("Fallas totales", m_ml["fallas_totales"])
st.plotly_chart(dh.fig_comparison(m_ml, m_th), use_container_width=False)
