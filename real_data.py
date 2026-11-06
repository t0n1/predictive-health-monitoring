"""
Conector de datos reales — MasterVsJuanitaV4.xlsx
Proyecto de residencia profesional · Delfino Antonio López Sosa (19390017)

Lee el Excel de monitoreo real de la empresa (Grupo Salinas / Dialogus) y
construye el mismo formato de datos que health_model.run_pipeline espera,
pero con información real de las sucursales Razberi/3VR.

Fuentes usadas:
  - Hoja '04_11_2026____03_08' : estatus actual de 1,797 sucursales
  - Hoja 'Monitoreo_No_Grabando': historial de incidentes activos
  - Hoja 'Terminado'            : incidentes resueltos
  - Hoja 'Camaras '             : número estimado de cámaras por ECO
  - Hoja 'Estatus General '     : configuración técnica por equipo
  - Hoja 'Planchado'            : sucursales re-instaladas (riesgo alto)
"""
from __future__ import annotations

import os
from functools import lru_cache

import numpy as np
import pandas as pd

EXCEL_NAME = "MasterVsJuanitaV4.xlsx"
PROJ = os.path.dirname(os.path.abspath(__file__))
EXCEL_PATH = os.path.join(PROJ, EXCEL_NAME)

# -------------------------------------------------- pesos de riesgo por tipo de falla
IMPACT_SCORE = {"Alto": 3, "alto": 3, "ALTO": 3,
                "Medio": 2, "medio": 2, "MEDIO": 2,
                "Bajo": 1, "bajo": 1, "BAJO": 1}
FAULT_SCORES = {
    "sin conexión": 3, "sin remoto": 2, "planchado": 3,
    "no graba": 3, "no grabando": 3, "falla 3vr": 3,
    "falla proxy": 2, "reinstalación": 2, "actualización": 1,
    "borrado de media": 1, "alta en enterprise": 1,
}


@lru_cache(maxsize=1)
def load_excel() -> dict[str, pd.DataFrame]:
    """Carga todas las hojas relevantes del Excel (cacheado)."""
    xl = pd.ExcelFile(EXCEL_PATH)

    # --- estatus actual (hoja con fecha en el nombre) ---
    main_sheet = xl.sheet_names[0]
    df_main = pd.read_excel(xl, sheet_name=main_sheet, header=1)
    df_main.columns = ["eco", "ip", "sucursal", "estatus_camaras",
                       "camaras_fuera", "vacias", "estado_ayer",
                       "estado_hoy", "comentarios", "status"]
    df_main = df_main[
        df_main["ip"].notna() &
        df_main["ip"].astype(str).str.match(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
    ].copy()
    df_main["eco"] = pd.to_numeric(df_main["eco"], errors="coerce")
    df_main["camaras_fuera"] = pd.to_numeric(df_main["camaras_fuera"], errors="coerce").fillna(0)
    df_main["estatus_camaras"] = pd.to_numeric(df_main["estatus_camaras"], errors="coerce").fillna(0)
    df_main["grabando"] = (df_main["estado_hoy"].astype(str).str.lower().str.strip() == "grabando")
    df_main["ip"] = df_main["ip"].astype(str).str.strip()
    df_main["sucursal"] = df_main["sucursal"].astype(str).str.strip()
    df_main = df_main.reset_index(drop=True)

    # --- historial de incidentes ---
    inc = pd.read_excel(xl, sheet_name="Monitoreo_No_Grabando")
    term = pd.read_excel(xl, sheet_name="Terminado")
    df_inc = pd.concat([inc, term], ignore_index=True)
    df_inc.columns = [c.strip().lower().replace(" ", "_") for c in df_inc.columns]
    df_inc = df_inc.rename(columns={"fecha_de_revisión": "fecha", "sucursal": "eco",
                            "ip": "ip", "impacto": "impacto",
                            "nivel_1": "tipo_falla", "observaciones": "obs",
                            "status": "status"})
    df_inc["ip"] = df_inc["ip"].astype(str).str.strip()
    df_inc["eco"] = pd.to_numeric(df_inc["eco"], errors="coerce")
    df_inc["score_impacto"] = df_inc["impacto"].map(IMPACT_SCORE).fillna(1)
    df_inc["fecha"] = pd.to_datetime(df_inc["fecha"], errors="coerce")

    # --- cámaras estimadas por ECO ---
    df_cam = pd.read_excel(xl, sheet_name="Camaras ")
    df_cam.columns = ["eco", "eco2", "n_camaras"]
    df_cam["eco"] = pd.to_numeric(df_cam["eco"], errors="coerce")
    df_cam = df_cam[["eco", "n_camaras"]].dropna(subset=["eco"])

    # --- estatus técnico general ---
    df_est = pd.read_excel(xl, sheet_name="Estatus General ", header=0)
    df_est.columns = [str(c).strip() for c in df_est.columns]
    # fila 0 es la cabecera real
    df_est = df_est.iloc[1:].copy()
    df_est.columns = [str(c) for c in df_est.columns]
    # buscar columnas clave por posición
    cols = list(df_est.columns)
    # Ecco=cols[1], IP=cols[2], Hostname=cols[3], Estatus=cols[4]
    if len(cols) >= 5:
        df_est = df_est.rename(columns={cols[1]: "eco", cols[2]: "ip_est",
                                         cols[3]: "hostname", cols[4]: "estatus_gen"})
        df_est["eco"] = pd.to_numeric(df_est["eco"], errors="coerce")
    else:
        df_est = pd.DataFrame(columns=["eco", "ip_est", "hostname", "estatus_gen"])

    # --- planchados (alto riesgo) ---
    df_planch = pd.read_excel(xl, sheet_name="Planchado")
    df_planch.columns = [c.strip().lower() for c in df_planch.columns]
    df_planch["ecco"] = pd.to_numeric(df_planch["ecco"], errors="coerce")
    df_planch["ip"] = df_planch["ip"].astype(str).str.strip()

    return {
        "main": df_main,
        "incidentes": df_inc,
        "camaras": df_cam,
        "estatus_gen": df_est,
        "planchados": df_planch,
    }


# -------------------------------------------------- búsqueda por IP
def find_branch(ip: str) -> dict | None:
    """Busca una sucursal por IP exacta en todas las hojas relevantes."""
    ip = ip.strip()
    sheets = load_excel()
    main = sheets["main"]

    row = main[main["ip"] == ip]
    if len(row) == 0:
        return None

    row = row.iloc[0]
    eco = int(row["eco"]) if not pd.isna(row["eco"]) else None

    # número de cámaras estimado
    cam_df = sheets["camaras"]
    n_cam_row = cam_df[cam_df["eco"] == eco] if eco else pd.DataFrame()
    n_cam = int(n_cam_row["n_camaras"].iloc[0]) if len(n_cam_row) else int(row["estatus_camaras"])

    # historial de incidentes de esta sucursal (por IP o ECO)
    inc = sheets["incidentes"]
    inc_branch = inc[(inc["ip"] == ip) | (inc["eco"] == eco)].copy() if eco else inc[inc["ip"] == ip].copy()

    # ¿está planchada?
    planch = sheets["planchados"]
    planchado = len(planch[(planch["ip"] == ip) | (planch["ecco"] == eco)]) > 0

    # hostname
    est = sheets["estatus_gen"]
    est_row = est[est["eco"] == eco] if eco and "eco" in est.columns else pd.DataFrame()
    hostname = est_row["hostname"].iloc[0] if len(est_row) else row["sucursal"]

    return {
        "ip": ip, "eco": eco,
        "nombre": str(row["sucursal"]),
        "hostname": str(hostname),
        "grabando": bool(row["grabando"]),
        "camaras_total": n_cam,
        "camaras_fuera": int(row["camaras_fuera"]),
        "vacias": str(row["vacias"]),
        "estado_ayer": str(row["estado_ayer"]),
        "estado_hoy": str(row["estado_hoy"]),
        "comentarios": str(row["comentarios"]) if not pd.isna(row["comentarios"]) else "",
        "planchado": planchado,
        "incidentes": inc_branch.reset_index(drop=True),
        "n_incidentes": len(inc_branch),
    }


# -------------------------------------------------- score de riesgo real
def compute_risk_score(branch: dict) -> dict:
    """
    Calcula el puntaje de salud y probabilidad de falla a partir de
    los datos reales del Excel:
      - Estado de grabación (no graba = crítico)
      - Cámaras fuera de línea
      - Historial de incidentes (frecuencia, impacto, tiempo sin resolver)
      - Si el equipo fue planchado recientemente
    """
    inc = branch["incidentes"]
    n_cam = max(branch["camaras_total"], 1)
    camaras_fuera = branch["camaras_fuera"]

    # --- factor 1: estado de grabación ---
    if not branch["grabando"]:
        f_grab = 1.0   # crítico
    elif str(branch["estado_ayer"]).lower() != str(branch["estado_hoy"]).lower():
        f_grab = 0.4   # cambió de estado
    else:
        f_grab = 0.0

    # --- factor 2: cámaras fuera de línea ---
    pct_fuera = camaras_fuera / n_cam
    f_cam = min(1.0, pct_fuera * 2.5)

    # --- factor 3: historial de incidentes ---
    if len(inc) == 0:
        f_hist = 0.0
    else:
        # incidentes sin cerrar = mayor riesgo
        abiertos = inc[inc["status"].astype(str).str.lower().isin(
            ["monitorear", "en proceso", "por asignar", "envio a soporte",
             "envio a seguridad", "nan"])]
        score_abiertos = abiertos["score_impacto"].sum()
        score_total = inc["score_impacto"].sum()
        # frecuencia: más incidentes = más riesgo (normalizado a max 30)
        freq = min(1.0, len(inc) / 30)
        f_hist = min(1.0, (score_abiertos * 0.6 + score_total * 0.3 + freq * 0.5) / 5)

    # --- factor 4: planchado ---
    f_planch = 0.35 if branch["planchado"] else 0.0

    # --- probabilidad compuesta ---
    prob = min(0.98, f_grab * 0.45 + f_cam * 0.25 + f_hist * 0.20 + f_planch * 0.10)
    health = round(100 * (1 - prob), 1)

    # nivel de riesgo
    if health >= 70:
        nivel, color = "Bajo", "#2e9d57"
    elif health >= 40:
        nivel, color = "Medio", "#d99a00"
    else:
        nivel, color = "Alto", "#d64545"

    # ventana estimada
    if health < 25:
        ventana = "inminente (< 6 h)"
    elif health < 40:
        ventana = "6–12 h"
    elif health < 60:
        ventana = "12–24 h"
    else:
        ventana = "estable (> 24 h)"

    # acción recomendada
    if nivel == "Alto":
        accion = "Intervenir: verificar conexión 3VR y estado de cámaras."
    elif nivel == "Medio":
        accion = "Revisar en próximas 12–24 h. Monitorear tendencia."
    else:
        accion = "Sin acción inmediata. Mantener monitoreo rutinario."

    return {
        "prob": round(prob, 3),
        "health": health,
        "nivel_riesgo": nivel,
        "color_riesgo": color,
        "ventana": ventana,
        "accion": accion,
        "factores": {
            "grabacion": round(f_grab, 3),
            "camaras_fuera": round(f_cam, 3),
            "historial": round(f_hist, 3),
            "planchado": round(f_planch, 3),
        },
    }


# -------------------------------------------------- resumen de toda la red
@lru_cache(maxsize=1)
def full_network_summary() -> pd.DataFrame:
    """
    Resumen de todas las sucursales: salud, riesgo y estado.
    Devuelve un DataFrame con una fila por sucursal.
    """
    sheets = load_excel()
    main = sheets["main"].copy()
    inc = sheets["incidentes"]
    cam = sheets["camaras"]
    planch = sheets["planchados"]

    # merge cámaras estimadas
    main = main.merge(cam.rename(columns={"eco": "eco"}), on="eco", how="left")
    main["n_camaras"] = pd.to_numeric(
        main["n_camaras"].fillna(main["estatus_camaras"]), errors="coerce"
    ).fillna(0)

    # merge planchados
    planch_ecos = set(planch["ecco"].dropna().astype(int).tolist())
    main["planchado"] = main["eco"].isin(planch_ecos)

    # incidentes por ECO
    inc_count = (inc.groupby("eco")
                    .agg(n_inc=("score_impacto", "count"),
                         score_total=("score_impacto", "sum"))
                    .reset_index())
    inc_open = (inc[inc["status"].astype(str).str.lower().isin(
                    ["monitorear", "en proceso", "por asignar",
                     "envio a soporte", "envio a seguridad"])]
                .groupby("eco")["score_impacto"].sum()
                .reset_index()
                .rename(columns={"score_impacto": "score_abiertos"}))
    main = main.merge(inc_count, on="eco", how="left")
    main = main.merge(inc_open, on="eco", how="left")
    main["n_inc"] = main["n_inc"].fillna(0)
    main["score_total"] = main["score_total"].fillna(0)
    main["score_abiertos"] = main["score_abiertos"].fillna(0)

    # calcular prob y health vectorizados
    pct_fuera = (main["camaras_fuera"] / main["n_camaras"].clip(lower=1)).clip(upper=1)
    f_grab = np.where(~main["grabando"], 1.0,
              np.where(main["estado_ayer"].astype(str).str.lower() !=
                       main["estado_hoy"].astype(str).str.lower(), 0.4, 0.0))
    f_cam = (pct_fuera * 2.5).clip(upper=1.0)
    freq = (main["n_inc"] / 30).clip(upper=1.0)
    f_hist = ((main["score_abiertos"] * 0.6 + main["score_total"] * 0.3 + freq * 0.5) / 5).clip(upper=1.0)
    f_planch = np.where(main["planchado"], 0.35, 0.0)

    main["prob"] = (f_grab * 0.45 + f_cam * 0.25 + f_hist * 0.20 + f_planch * 0.10).clip(upper=0.98)
    main["health"] = (100 * (1 - main["prob"])).round(1)
    main["nivel_riesgo"] = pd.cut(main["health"], bins=[0, 40, 70, 100],
                                   labels=["Alto", "Medio", "Bajo"], right=True)
    main["estado"] = np.where(~main["grabando"], "no grabando",
                     np.where(main["camaras_fuera"] > 0, "cámaras fuera", "operando"))

    return main[[
        "eco", "ip", "sucursal", "grabando", "camaras_fuera", "n_camaras",
        "estado", "health", "prob", "nivel_riesgo", "n_inc", "planchado",
        "estado_hoy", "estado_ayer", "comentarios"
    ]].reset_index(drop=True)


def search_by_ip(ip: str):
    """Busca en el resumen completo por IP. Devuelve (branch_dict, risk_dict) o None."""
    b = find_branch(ip)
    if b is None:
        return None, None
    r = compute_risk_score(b)
    return b, r


def all_ips() -> list[str]:
    """Lista todas las IPs registradas en el Excel."""
    return load_excel()["main"]["ip"].tolist()


if __name__ == "__main__":
    summary = full_network_summary()
    print(f"Total sucursales: {len(summary)}")
    print(f"No grabando: {(~summary['grabando']).sum()}")
    print(f"Riesgo Alto: {(summary['nivel_riesgo'] == 'Alto').sum()}")
    print(f"Riesgo Medio: {(summary['nivel_riesgo'] == 'Medio').sum()}")
    print(f"Riesgo Bajo: {(summary['nivel_riesgo'] == 'Bajo').sum()}")
    print("\nTop 10 mayor riesgo:")
    print(summary.sort_values("health").head(10)[
        ["eco", "ip", "sucursal", "health", "nivel_riesgo", "estado"]
    ].to_string())
