"""
Dashboard de Monitoreo de Salud Predictivo — Grupo Salinas / Dialogus
Proyecto de residencia profesional · Delfino Antonio López Sosa (19390017)

Modo REAL: si existe MasterVsJuanitaV4.xlsx en la carpeta del proyecto,
el dashboard usa los datos reales de la empresa (1,797 sucursales Razberi/3VR).
Al ingresar la IP de una sucursal se obtienen los datos reales del Excel.

Modo SIMULADO: si no hay Excel, genera telemetría sintética reproducible.

Ejecutar:  .venv\\Scripts\\python.exe -m streamlit run app.py
"""
import os
import re
import time

import pandas as pd
import streamlit as st

import dashboard_helpers as dh

EXCEL_FILE = os.path.join(os.path.dirname(__file__), "MasterVsJuanitaV4.xlsx")
REAL_MODE = os.path.exists(EXCEL_FILE)

st.set_page_config(page_title="Monitoreo Salud Predictivo — Grupo Salinas",
                   page_icon="🛰️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.kpi{background:#fff;border:1px solid #d9dee7;border-radius:12px;
     padding:14px 16px;text-align:center}
.kpi .v{font-size:30px;font-weight:700;line-height:1.1}
.kpi .l{color:#667085;font-size:12px;margin-top:2px}
.chip{display:inline-block;padding:2px 10px;border-radius:999px;
      font-size:12px;font-weight:600}
.ok{background:#e3f4ea;color:#2e9d57}
.warn{background:#fdf2db;color:#b97d00}
.bad{background:#fbe1e1;color:#d64545}
.info{background:#eaf0f8;color:#1f4e79}
.devcard{border:1px solid #d9dee7;border-radius:12px;
         padding:10px;background:#fff;margin-bottom:6px}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────── helpers
def valid_ip(ip: str) -> bool:
    return (bool(re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", ip.strip()))
            and all(0 <= int(o) <= 255 for o in ip.strip().split(".")))


def kpi(value, label, color=dh.ACC):
    st.markdown(
        f'<div class="kpi"><div class="v" style="color:{color}">{value}</div>'
        f'<div class="l">{label}</div></div>',
        unsafe_allow_html=True)


def chip(text, cls="info"):
    return f'<span class="chip {cls}">{text}</span>'


# ─────────────────────────────── sidebar
with st.sidebar:
    st.markdown("### 🛰️ Salud Predictiva")
    if REAL_MODE:
        st.success("📂 Datos reales cargados", icon="✅")
        st.caption("MasterVsJuanitaV4.xlsx detectado")
    else:
        st.info("Modo simulación activo")
        st.caption("Coloca MasterVsJuanitaV4.xlsx en la carpeta del proyecto para usar datos reales.")

    branch = st.session_state.get("branch")
    if branch:
        st.markdown(f"**Conectado:**  \n{branch['nombre']}  \n`{branch['ip']}`")
        if branch.get("eco"):
            st.caption(f"ECO {branch['eco']} · {branch.get('camaras_total',0)} cámaras")
        if st.button("Desconectar", key="btn_desconectar"):
            for k in ("branch", "pipe", "real_branch", "real_risk"):
                st.session_state.pop(k, None)
            st.rerun()
    else:
        st.caption("Sin conexión. Ingresa la IP de una sucursal.")
    st.divider()
    st.caption("Residencia profesional · D. A. López Sosa (19390017)")


# ─────────────────────────────── cabecera
col_logo, col_title = st.columns([1, 6])
with col_logo:
    st.markdown("## 🛰️")
with col_title:
    st.title("Monitoreo de Salud Predictivo")
    st.caption("Sistema predictivo de fallas · Razberi / 3VR OpCenter · Grupo Salinas")


# ══════════════════════════════ YA CONECTADO ══════════════════════════════════
branch = st.session_state.get("branch")
real_branch = st.session_state.get("real_branch")
real_risk = st.session_state.get("real_risk")
pipe = st.session_state.get("pipe")

if branch and REAL_MODE and real_branch:
    # ── estado de la sucursal ────────────────────────────────────────────────
    rb, rr = real_branch, real_risk
    grabando = rb["grabando"]
    camaras_fuera = rb["camaras_fuera"]
    n_cam = rb["camaras_total"]
    h = rr["health"]
    color = dh.health_color(h)
    nivel = rr["nivel_riesgo"]
    chip_cls = "ok" if nivel == "Bajo" else "warn" if nivel == "Medio" else "bad"

    st.success(f"✅ Conectado a **{rb['nombre']}**  ({branch['ip']})")
    st.markdown(
        f"ECO `{rb['eco']}` · Hostname: `{rb['hostname']}` · "
        f"Producto: **Razberi / 3VR OpCenter** · "
        f"Estado: {chip('Grabando' if grabando else '⚠ NO Grabando', 'ok' if grabando else 'bad')}",
        unsafe_allow_html=True)
    st.write("")

    # ── KPIs principales ────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: kpi(f"{h:.0f}", "Puntaje de salud", color)
    with c2: kpi(f"{rr['prob']:.0%}", "P(falla próx. 24 h)",
                 dh.BAD if rr["prob"] > 0.5 else dh.WARN if rr["prob"] > 0.2 else dh.OK)
    with c3: kpi(n_cam, "Cámaras totales")
    with c4: kpi(camaras_fuera, "Cámaras fuera", dh.BAD if camaras_fuera > 0 else dh.OK)
    with c5: kpi(rb["n_incidentes"], "Incidentes históricos",
                 dh.BAD if rb["n_incidentes"] > 5 else dh.WARN if rb["n_incidentes"] > 0 else dh.OK)
    st.write("")

    # ── medidor + detalle ────────────────────────────────────────────────────
    colG, colD = st.columns([1, 2])
    with colG:
        st.plotly_chart(dh.fig_gauge(h), use_container_width=False)
        st.markdown(
            f"**Riesgo:** {chip(nivel, chip_cls)}  \n"
            f"**Ventana:** {rr['ventana']}  \n"
            f"**Recomendación:** {rr['accion']}",
            unsafe_allow_html=True)
    with colD:
        st.subheader("Factores de riesgo")
        factores = rr["factores"]
        f_names = {
            "grabacion": "No está grabando",
            "camaras_fuera": "Cámaras fuera de línea",
            "historial": "Historial de incidentes",
            "planchado": "Re-instalación reciente",
        }
        import plotly.graph_objects as go
        fig_f = go.Figure(go.Bar(
            x=list(factores.values()),
            y=[f_names[k] for k in factores],
            orientation="h",
            marker_color=[dh.BAD if v > 0.5 else dh.WARN if v > 0.1 else dh.OK
                          for v in factores.values()],
            text=[f"{v:.0%}" for v in factores.values()],
            textposition="outside",
        ))
        fig_f.update_layout(height=220, margin=dict(l=10, r=40, t=10, b=10),
                            xaxis=dict(range=[0, 1.1], title="Contribución al riesgo"),
                            plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_f, use_container_width=False)

        # estado de grabación comparado ayer/hoy
        st.markdown(
            f"**Estado ayer:** `{rb['estado_ayer']}`  \n"
            f"**Estado hoy:** `{rb['estado_hoy']}`  \n"
            + (f"**Comentarios:** {rb['comentarios']}" if rb["comentarios"] else ""))
        if rb["planchado"]:
            st.warning("⚠️ Esta sucursal tiene registro de re-instalación (planchado).")

    # ── incidentes históricos ────────────────────────────────────────────────
    st.divider()
    st.subheader(f"📋 Historial de incidentes — {rb['nombre']}")
    inc = rb["incidentes"]
    if len(inc) == 0:
        st.success("Sin incidentes registrados para esta sucursal.")
    else:
        show_cols = [c for c in ["fecha", "tipo_falla", "impacto", "obs", "status",
                                  "fecha_de_cierre"] if c in inc.columns]
        st.dataframe(inc[show_cols].sort_values("fecha", ascending=False)
                       if "fecha" in show_cols else inc[show_cols],
                     use_container_width=False, hide_index=True)

    # ── enlace a red completa ────────────────────────────────────────────────
    st.divider()
    st.page_link("pages/1_📊_Panel_de_monitoreo.py",
                 label="📊 Ver panel de toda la red (1,797 sucursales)", icon="➡️")
    st.page_link("pages/2_🚨_Alertas_tempranas.py",
                 label="🚨 Ver alertas tempranas de toda la red", icon="➡️")
    st.stop()

elif branch and not REAL_MODE and pipe:
    # ── modo simulado (sin Excel) ────────────────────────────────────────────
    st.success(f"Conectado (simulado) a **{branch['nombre']}** ({branch['ip']})")
    s = pipe.summary
    n = len(s)
    operando = int((s["estado"] == "operando").sum())
    alerta = int((s["estado"] == "en alerta").sum())
    fuera = int((s["estado"] == "fuera de servicio").sum())
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi(n, "Equipos monitoreados")
    with c2: kpi(operando, "Operando", dh.OK)
    with c3: kpi(alerta, "En alerta", dh.WARN)
    with c4: kpi(fuera, "Fuera de servicio", dh.BAD)
    st.page_link("pages/1_📊_Panel_de_monitoreo.py",
                 label="📊 Ir al panel de monitoreo", icon="➡️")
    st.stop()


# ══════════════════════════════ FORMULARIO DE CONEXIÓN ════════════════════════
st.subheader("🔌 Conexión a sucursal")

if REAL_MODE:
    st.write(
        "Ingresa la **IP del NVR Razberi** de la sucursal. "
        "El sistema la buscará en el registro real de la empresa y "
        "calculará su puntaje de salud con los datos reales del Excel."
    )
    # sugerencia de IPs conocidas para demo
    import real_data as rd
    summary_all = rd.full_network_summary()
    # IPs más interesantes: con cámaras fuera o incidentes
    demo_ips = summary_all[summary_all["camaras_fuera"] > 0]["ip"].head(5).tolist()
    if demo_ips:
        st.caption(f"💡 IPs con incidencias detectadas para probar: `{'` · `'.join(demo_ips[:3])}`")
else:
    st.write(
        "Ingresa la IP de la sucursal a monitorear. "
        "El sistema generará telemetría reproducible basada en la IP."
    )

with st.form("conexion"):
    colA, colB = st.columns(2)
    with colA:
        default_ip = demo_ips[0] if REAL_MODE and demo_ips else "10.20.30.5"
        ip = st.text_input("IP del NVR Razberi / Sucursal", value=default_ip,
                           help="Dirección IPv4 del servidor Razberi de la sucursal")
        nombre_manual = st.text_input(
            "Nombre de la sucursal (opcional — se detecta automáticamente si hay Excel)",
            value="")
    with colB:
        region = st.selectbox("Región", ["CDMX", "Norte", "Sur", "Bajío", "Occidente",
                                          "Noroeste", "Noreste", "Occidente", "Sureste"])
        if not REAL_MODE:
            dias = st.select_slider("Historial disponible (días)",
                                    options=[30, 60, 90, 120], value=120)
        else:
            st.info("El historial proviene del Excel de la empresa.")

    if not REAL_MODE:
        st.markdown("**Equipos a simular**")
        cn1, cn2, cn3 = st.columns(3)
        with cn1: n_srv = st.number_input("Servidores", 2, 40, 8, 1)
        with cn2: n_cam = st.number_input("Cámaras", 2, 80, 16, 1)
        with cn3: n_net = st.number_input("Equipos de red", 0, 20, 2, 1)

    submitted = st.form_submit_button("🔗 Conectar y monitorear",
                                      key="btn_conectar",
                                      use_container_width=True,
                                      type="primary")

if submitted:
    if not valid_ip(ip):
        st.error("La IP no es válida. Usa el formato X.X.X.X (ej. 10.41.199.112).")
        st.stop()

    if REAL_MODE:
        with st.spinner(f"Buscando `{ip}` en el registro de sucursales…"):
            time.sleep(0.4)
            rb, rr = rd.search_by_ip(ip)

        if rb is None:
            st.error(
                f"La IP `{ip}` no está registrada en el Excel de la empresa. "
                "Verifica que sea la IP del NVR Razberi de la sucursal."
            )
            st.info(
                "Puedes buscar la IP correcta en la hoja `04_11_2026____03_08` "
                "del archivo `MasterVsJuanitaV4.xlsx`."
            )
            st.stop()

        nombre = rb["nombre"] if not nombre_manual.strip() else nombre_manual.strip()
        st.session_state["real_branch"] = rb
        st.session_state["real_risk"] = rr
        st.session_state["branch"] = {
            "ip": ip.strip(), "nombre": nombre, "region": region,
            "eco": rb.get("eco"),
            "camaras_total": rb.get("camaras_total", 0),
        }
        st.success(f"✅ Conectado a **{nombre}** ({ip})")
        st.balloons()
        st.rerun()

    else:
        import health_model as hm
        seed = hm.ip_to_seed(ip)
        hours = dias * 24
        with st.spinner(f"Conectando a {ip} y descubriendo equipos…"):
            time.sleep(0.6)
        with st.spinner("Entrenando modelo predictivo…"):
            def get_pipe(ns, nc, nn, s, h, hz):
                cache = st.session_state.setdefault("_pipe_cache", {})
                key = (ns, nc, nn, s, h, hz)
                if key not in cache:
                    cache[key] = hm.run_pipeline(ns, nc, nn, s, h, hz)
                return cache[key]
            pipe_obj = get_pipe(int(n_srv), int(n_cam), int(n_net),
                                int(seed), int(hours), hm.HORIZON)
        nombre = nombre_manual.strip() or f"Sucursal {ip}"
        st.session_state["branch"] = {
            "ip": ip.strip(), "nombre": nombre, "region": region,
            "n_servers": int(n_srv), "n_cameras": int(n_cam),
            "n_net": int(n_net), "dias": dias, "seed": seed,
        }
        st.session_state["pipe"] = pipe_obj
        st.success(f"✅ Conectado (simulado) a **{nombre}** ({ip})")
        st.balloons()
        st.rerun()
