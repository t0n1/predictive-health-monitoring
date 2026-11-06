"""
Núcleo del sistema de Monitoreo de Salud Predictivo.

Contiene toda la lógica reutilizable: simulación de telemetría, ingeniería de
variables, entrenamiento del modelo predictivo, métricas a nivel hora y a
nivel evento, y construcción del resumen por equipo / alertas priorizadas.

Lo usan dos front-ends:
  * ``predictive_health.py``  -> genera figuras PNG y results.json (modo lote)
  * ``app.py`` (Streamlit)     -> dashboard visual interactivo

El objetivo de la residencia profesional (Delfino Antonio López Sosa, 19390017)
cubre cuatro puntos:
  1. Recopilar y analizar datos históricos de servidores, cámaras y red.
  2. Diseñar y entrenar un modelo predictivo (puntaje de salud + prob. de falla).
  3. Dashboard de monitoreo con alertamiento temprano priorizado por riesgo.
  4. Integración por sucursal (IP) con datos reales o simulados.

Este módulo resuelve los puntos 1 y 2 y provee los datos para el 3 y el 4.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (average_precision_score, confusion_matrix, f1_score,
                             precision_recall_curve, precision_score, recall_score,
                             roc_auc_score, roc_curve)

# ----------------------------------------------------------------- constantes
SEED = 42
HOURS = 24 * 120            # 120 días de telemetría por hora
HORIZON = 24                # se predice falla en las próximas 24 h
TRAIN_FRAC = 0.7
DOWNTIME = 4                # horas fuera de servicio tras una falla
N_SERVERS, N_CAMERAS = 10, 20
N_NET = 0                   # equipos de red se modelan como servidores ligeros

BASE = ["latencia_ms", "cpu_pct", "mem_pct", "temp_c", "perdida_pct"]
ALERT_THRESHOLD = 0.5       # probabilidad que dispara la alerta del modelo


# ----------------------------------------------------------------- simulación
def simulate_device(dev_id: str, kind: str, rng: np.random.Generator) -> pd.DataFrame:
    """Genera la telemetría horaria de un equipo (servidor / cámara / red)."""
    t = np.arange(HOURS)
    daily = np.sin(2 * np.pi * (t % 24) / 24)
    if kind == "servidor":
        lat = 20 + 3 * daily + rng.normal(0, 2, HOURS)
        cpu = 45 + 12 * daily + rng.normal(0, 5, HOURS)
        mem = 60 + 5 * daily + rng.normal(0, 3, HOURS)
        temp = 52 + 4 * daily + rng.normal(0, 1.5, HOURS)
        loss = np.abs(rng.normal(0.1, 0.1, HOURS))
    elif kind == "camara":
        lat = 35 + 5 * daily + rng.normal(0, 4, HOURS)
        cpu = 30 + 6 * daily + rng.normal(0, 4, HOURS)
        mem = 40 + 3 * daily + rng.normal(0, 3, HOURS)
        temp = 45 + 6 * daily + rng.normal(0, 2, HOURS)
        loss = np.abs(rng.normal(0.4, 0.3, HOURS))
    else:  # red (switch/router de la sucursal)
        lat = 18 + 2 * daily + rng.normal(0, 1.5, HOURS)
        cpu = 35 + 8 * daily + rng.normal(0, 4, HOURS)
        mem = 55 + 4 * daily + rng.normal(0, 3, HOURS)
        temp = 48 + 3 * daily + rng.normal(0, 1.2, HOURS)
        loss = np.abs(rng.normal(0.15, 0.12, HOURS))
    reboots = (rng.random(HOURS) < 0.004).astype(float)
    failure = np.zeros(HOURS, dtype=int)

    # picos espurios (generan falsos positivos en un esquema por umbrales)
    for _ in range(rng.integers(8, 15)):
        s = rng.integers(0, HOURS - 3)
        lat[s:s + 2] += rng.uniform(40, 120)
        cpu[s:s + 2] += rng.uniform(20, 40)
        loss[s:s + 2] += rng.uniform(2, 6)

    # fallas con degradación progresiva previa (precursores)
    n_fail = rng.integers(3, 7)
    starts = np.sort(rng.choice(np.arange(100, HOURS - 60, 70), size=n_fail, replace=False))
    for f in starts:
        lead = rng.integers(10, 40)                      # horas de degradación
        sev = 0.0 if rng.random() < 0.25 else rng.uniform(0.7, 1.3)  # ~25 % súbitas
        ramp = np.linspace(0, 1, lead) ** 1.5
        sl = slice(f - lead, f)
        lat[sl] += ramp * 60 * sev
        temp[sl] += ramp * 14 * sev
        loss[sl] += ramp * 4.5 * sev
        cpu[sl] += ramp * 22 * sev
        mem[sl] += ramp * 15 * sev
        reboots[sl] += (rng.random(lead) < 0.25 * ramp * sev)
        failure[f] = 1
    return pd.DataFrame({
        "device": dev_id, "tipo": kind, "hour": t,
        "latencia_ms": lat, "cpu_pct": np.clip(cpu, 0, 100),
        "mem_pct": np.clip(mem, 0, 100), "temp_c": temp,
        "perdida_pct": np.clip(loss, 0, 100), "reinicios": reboots,
        "falla": failure,
    })


def build_dataset(n_servers: int = N_SERVERS, n_cameras: int = N_CAMERAS,
                  n_net: int = N_NET, seed: int = SEED) -> pd.DataFrame:
    """Construye el conjunto completo de telemetría de todos los equipos."""
    rng = np.random.default_rng(seed)
    frames = []
    for i in range(n_servers):
        frames.append(simulate_device(f"SRV-{i + 1:02d}", "servidor", rng))
    for i in range(n_cameras):
        frames.append(simulate_device(f"CAM-{i + 1:02d}", "camara", rng))
    for i in range(n_net):
        frames.append(simulate_device(f"NET-{i + 1:02d}", "red", rng))
    return pd.concat(frames, ignore_index=True)


# ------------------------------------------------------ ingeniería de variables
def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Añade medias móviles, desviaciones, derivados y la etiqueta de falla futura."""
    out = []
    for _, g in df.groupby("device", sort=False):
        g = g.sort_values("hour").copy()
        for c in BASE:
            g[f"{c}_m6"] = g[c].rolling(6, min_periods=1).mean()
            g[f"{c}_m24"] = g[c].rolling(24, min_periods=1).mean()
            g[f"{c}_sd12"] = g[c].rolling(12, min_periods=2).std().fillna(0)
            g[f"{c}_d12"] = g[c] - g[c].shift(12).bfill()
        g["reinicios_24h"] = g["reinicios"].rolling(24, min_periods=1).sum()
        g["es_camara"] = int(g["tipo"].iloc[0] == "camara")
        # etiqueta: ¿habrá falla en las próximas HORIZON horas?
        fut = g["falla"][::-1].rolling(HORIZON, min_periods=1).max()[::-1].shift(-1).fillna(0)
        g["y"] = fut.astype(int)
        down = g["falla"].rolling(DOWNTIME, min_periods=1).max().shift(1).fillna(0)
        g["down"] = down.astype(int) | g["falla"]
        out.append(g)
    return pd.concat(out, ignore_index=True)


# ------------------------------------------------------------ evaluación eventos
def debounce(flag, k: int = 2):
    """Alerta solo si la condición se cumple k horas consecutivas."""
    s = pd.Series(flag.astype(int))
    return (s.rolling(k, min_periods=k).sum() >= k).to_numpy()


def event_metrics(df: pd.DataFrame, alert_col: str) -> dict:
    """Métricas a nivel evento: fallas anticipadas, anticipación y falsas alertas."""
    anticipated, leads, false_eps = 0, [], 0
    total_failures = int(df["falla"].sum())
    device_hours = 0
    for _, g in df.groupby("device", sort=False):
        g = g.sort_values("hour")
        a = g[alert_col].to_numpy().astype(bool)
        f_idx = np.where(g["falla"].to_numpy() == 1)[0]
        covered = np.zeros(len(g), dtype=bool)
        for f in f_idx:
            lo = max(0, f - HORIZON)
            w = np.where(a[lo:f])[0]
            covered[lo:f + 1] = True
            if len(w):
                anticipated += 1
                leads.append(f - (lo + w[0]))
        start = a & ~np.r_[False, a[:-1]]
        false_eps += int((start & ~covered & (g["down"].to_numpy() == 0)).sum())
        device_hours += int((g["down"].to_numpy() == 0).sum())
    weeks = device_hours / (24 * 7)
    return {
        "fallas_totales": total_failures,
        "fallas_anticipadas": anticipated,
        "pct_anticipadas": round(100 * anticipated / max(total_failures, 1), 1),
        "anticipacion_mediana_h": float(np.median(leads)) if leads else 0.0,
        "falsas_alertas": false_eps,
        "falsas_por_equipo_semana": round(false_eps / weeks, 3),
    }


# ------------------------------------------------------------- resumen / alertas
RISK_BANDS = [  # (lim_inf_health, nivel, color_hex, accion)
    (70, "Bajo", "#2e9d57", "Mantener monitoreo rutinario."),
    (40, "Medio", "#d99a00", "Revisar tendencia; programar inspección."),
    (0, "Alto", "#d64545", "Intervenir: verificar servicio y prestar atención prioritaria."),
]
CRITICAL_HEALTH = 40  # por debajo -> crítico / intervención inminente


def risk_level(health: float) -> tuple[str, str, str]:
    """Devuelve (nivel, color, acción) según el puntaje de salud."""
    for lim, nivel, color, accion in RISK_BANDS:
        if health >= lim:
            return nivel, color, accion
    return "Alto", "#d64545", "Intervenir: verificar servicio y prestar atención prioritaria."


def time_to_failure(health: float, prob: float) -> str:
    """Estimación cualitativa de la ventana de actuación."""
    if health < 25 or prob > 0.8:
        return "inminente (< 6 h)"
    if health < 40:
        return "6–12 h"
    if health < 60:
        return "12–24 h"
    return "estable (> 24 h)"


def compute_now_hour(full_test: pd.DataFrame) -> int:
    """Instante de referencia ('ahora') = momento de mayor actividad de alertas.

    Se elige la hora con más alertas predictivas simultáneas (empate -> la más
    reciente). Si nunca hubo alertas, se usa la última hora disponible. Así el
    dashboard muestra un instante con incidentes reales en lugar de un momento
    de calma; es una instantánea legítima del periodo monitoreado.
    """
    sub = full_test[full_test["down"] == 0]
    if sub["alerta_ml"].any():
        cnt = sub.groupby("hour")["alerta_ml"].sum()
        mx = cnt.max()
        return int(cnt[cnt == mx].index.max())
    return int(full_test["hour"].max())


def device_summary(df: pd.DataFrame, now_hour: int | None = None) -> pd.DataFrame:
    """Estado 'actual' de cada equipo en el instante de referencia (now_hour)."""
    if now_hour is None:
        now_hour = int(df["hour"].max())
    last = df[df["hour"] == now_hour].reset_index(drop=True)
    last["estado"] = np.where(last["down"] == 1, "fuera de servicio",
                      np.where(last["alerta_ml"], "en alerta",
                       np.where(last["falla"] == 1, "falla", "operando")))
    level = last["health"].apply(risk_level)
    last["nivel_riesgo"] = [l[0] for l in level]
    last["color_riesgo"] = [l[1] for l in level]
    return last


def active_alerts(df: pd.DataFrame, now_hour: int | None = None) -> pd.DataFrame:
    """Equipos con alerta predictiva activa en now_hour, ordenados por mayor riesgo."""
    last = device_summary(df, now_hour)
    al = last[(last["alerta_ml"]) & (last["down"] == 0)].copy()
    if al.empty:
        return al
    al["ventana"] = al.apply(lambda r: time_to_failure(r["health"], r["prob"]), axis=1)
    return al.sort_values(["health"]).reset_index(drop=True)


# ----------------------------------------------------------------- pipeline
def ip_to_seed(ip: str) -> int:
    """Convierte una IP en una semilla determinista (misma IP -> mismos datos)."""
    h = hashlib.md5(ip.strip().encode("utf-8")).hexdigest()
    return int(h[:8], 16) % (2 ** 31)


@dataclass
class PipelineResult:
    raw: pd.DataFrame
    df: pd.DataFrame              # con prob, health, alerta_ml, alerta_umbral
    test: pd.DataFrame
    full_test: pd.DataFrame
    model: object
    feats: list
    train_end: int
    y: pd.Series
    p: pd.Series
    m_ml: dict
    m_th: dict
    results: dict
    importance: pd.Series
    summary: pd.DataFrame
    alerts: pd.DataFrame
    now_hour: int = 0
    config: dict = field(default_factory=dict)


def run_pipeline(n_servers: int = N_SERVERS, n_cameras: int = N_CAMERAS,
                 n_net: int = N_NET, seed: int = SEED, hours: int = HOURS,
                 horizon: int = HORIZON) -> PipelineResult:
    """Ejecuta todo el flujo: datos -> variables -> modelo -> métricas -> alertas."""
    global HOURS, HORIZON
    HOURS = hours
    HORIZON = horizon

    raw = build_dataset(n_servers, n_cameras, n_net, seed)
    df = add_features(raw)
    feats = [c for c in df.columns if c not in
             ("device", "tipo", "hour", "falla", "y", "down", "reinicios")]

    train_end = int(HOURS * TRAIN_FRAC)
    usable = df[df["down"] == 0]
    train = usable[usable["hour"] < train_end]

    model = GradientBoostingClassifier(n_estimators=200, max_depth=3,
                                       learning_rate=0.08, subsample=0.8,
                                       random_state=SEED)
    model.fit(train[feats], train["y"])
    df["prob"] = model.predict_proba(df[feats])[:, 1]
    df["health"] = (100 * (1 - df["prob"])).round(1)

    test = df[(df["down"] == 0) & (df["hour"] >= train_end)].copy()
    y, p = test["y"], test["prob"]

    test["alerta_ml"] = debounce(p.to_numpy() >= ALERT_THRESHOLD, 2)
    react = ((test["latencia_ms"] > 90) | (test["temp_c"] > 70) |
             (test["perdida_pct"] > 6) | (test["cpu_pct"] > 90))
    test["alerta_umbral"] = debounce(react.to_numpy(), 2)

    full_test = df[df["hour"] >= train_end].copy()
    full_test["alerta_ml"] = False
    full_test["alerta_umbral"] = False
    full_test.loc[test.index, "alerta_ml"] = test["alerta_ml"].to_numpy()
    full_test.loc[test.index, "alerta_umbral"] = test["alerta_umbral"].to_numpy()

    m_ml = event_metrics(full_test, "alerta_ml")
    m_th = event_metrics(full_test, "alerta_umbral")

    pred = (p >= ALERT_THRESHOLD).astype(int)
    res = {
        "dataset": {
            "equipos": n_servers + n_cameras + n_net, "servidores": n_servers,
            "camaras": n_cameras, "red": n_net, "horas_por_equipo": hours,
            "registros": int(len(raw)), "fallas_totales": int(raw["falla"].sum()),
            "horas_entrenamiento": train_end, "horas_prueba": hours - train_end,
            "variables_modelo": len(feats),
        },
        "modelo_nivel_hora": {
            "roc_auc": round(roc_auc_score(y, p), 3),
            "pr_auc": round(average_precision_score(y, p), 3),
            "precision": round(precision_score(y, pred), 3),
            "recall": round(recall_score(y, pred), 3),
            "f1": round(f1_score(y, pred), 3),
            "umbral": ALERT_THRESHOLD,
            "matriz_confusion": confusion_matrix(y, pred).tolist(),
            "prevalencia_pos": round(float(y.mean()), 3),
        },
        "eventos_modelo_predictivo": m_ml,
        "eventos_umbrales_fijos": m_th,
    }
    importance = pd.Series(model.feature_importances_, index=feats).sort_values()

    now_hour = compute_now_hour(full_test)
    summary = device_summary(full_test, now_hour)
    alerts = active_alerts(full_test, now_hour)

    return PipelineResult(
        raw=raw, df=df, test=test, full_test=full_test, model=model, feats=feats,
        train_end=train_end, y=y, p=p, m_ml=m_ml, m_th=m_th, results=res,
        importance=importance, summary=summary, alerts=alerts, now_hour=now_hour,
        config={"n_servers": n_servers, "n_cameras": n_cameras, "n_net": n_net,
                "seed": seed, "hours": hours, "horizon": horizon},
    )


def roc_pr_curves(y, p):
    """Devuelve (fpr, tpr, precision_points, recall_points) para graficar."""
    fpr, tpr, _ = roc_curve(y, p)
    pr, rc, _ = precision_recall_curve(y, p)
    return fpr, tpr, pr, rc


if __name__ == "__main__":
    r = run_pipeline()
    import json
    print(json.dumps(r.results, indent=2, ensure_ascii=False))


def failure_log(df: pd.DataFrame) -> pd.DataFrame:
    """Bitácora de cada falla del periodo: si fue anticipada y con cuántas horas."""
    rows = []
    for dev, g in df.groupby("device", sort=False):
        g = g.sort_values("hour")
        a_ml = g["alerta_ml"].to_numpy().astype(bool) if "alerta_ml" in g else np.zeros(len(g), bool)
        a_th = g["alerta_umbral"].to_numpy().astype(bool) if "alerta_umbral" in g else np.zeros(len(g), bool)
        f_idx = np.where(g["falla"].to_numpy() == 1)[0]
        for f in f_idx:
            lo = max(0, f - HORIZON)
            wml = np.where(a_ml[lo:f])[0]
            wth = np.where(a_th[lo:f])[0]
            rows.append({
                "equipo": dev, "hora_falla": int(g["hour"].iloc[f]),
                "modelo_anticipo_h": int(f - (lo + wml[0])) if len(wml) else None,
                "umbrales_anticipo_h": int(f - (lo + wth[0])) if len(wth) else None,
            })
    return pd.DataFrame(rows)
