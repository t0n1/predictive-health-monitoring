"""
Prototipo de Monitoreo de Salud Predictivo (Predictive Health Monitoring)
Proyecto de residencia profesional - Delfino Antonio López Sosa (19390017)

Genera telemetría SINTÉTICA de servidores y cámaras, entrena un modelo para
estimar la probabilidad de falla en las próximas 24 h, calcula un puntaje de
salud (0-100) y compara contra un monitoreo reactivo por umbrales fijos.

La lógica de simulación, variables, modelo y métricas vive en ``health_model``
y se comparte con el dashboard visual (``app.py``). Este script es el modo
lote: produce figuras PNG y ``results.json`` en la carpeta "out".

Uso:  python predictive_health.py
Salida: figuras PNG y results.json en la carpeta "out" junto a este archivo
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import health_model as hm

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)


def main():
    r = hm.run_pipeline()
    df, full_test = r.df, r.full_test
    model, feats = r.model, r.feats
    y, p = r.y, r.p
    res, m_ml, m_th = r.results, r.m_ml, r.m_th

    with open(f"{OUT}/results.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False})

    # 1) salud de un equipo con falla en el periodo de prueba
    cand = full_test[full_test["falla"] == 1]["device"].iloc[0]
    g = full_test[full_test["device"] == cand].sort_values("hour")
    f_h = int(g.loc[g["falla"] == 1, "hour"].iloc[0])
    gg = g[(g["hour"] >= f_h - 96) & (g["hour"] <= f_h + 12)]
    fig, ax = plt.subplots(2, 1, figsize=(8, 5.2), sharex=True)
    ax[0].plot(gg["hour"] - f_h, gg["health"], color="#1f4e79", lw=2)
    ax[0].axhspan(70, 100, color="#c6e0b4", alpha=.35)
    ax[0].axhspan(40, 70, color="#ffe699", alpha=.45)
    ax[0].axhspan(0, 40, color="#f4b183", alpha=.45)
    ax[0].axvline(0, color="red", ls="--"); ax[0].set_ylim(0, 100)
    ax[0].set_ylabel("Puntaje de salud"); ax[0].set_title(f"Evolución del puntaje de salud — {cand}")
    ax[1].plot(gg["hour"] - f_h, gg["latencia_ms"], label="Latencia (ms)", color="#7f6000")
    ax[1].plot(gg["hour"] - f_h, gg["temp_c"], label="Temperatura (°C)", color="#c55a11")
    ax[1].axvline(0, color="red", ls="--", label="Falla")
    ax[1].set_xlabel("Horas respecto a la falla"); ax[1].legend(frameon=False, ncol=3)
    plt.tight_layout(); plt.savefig(f"{OUT}/fig_health_timeline.png", dpi=170); plt.close()

    # 2) ROC y PR
    fpr, tpr, pr, rc = hm.roc_pr_curves(y, p)
    fig, ax = plt.subplots(1, 2, figsize=(8, 3.6))
    ax[0].plot(fpr, tpr, color="#1f4e79", lw=2, label=f"AUC = {res['modelo_nivel_hora']['roc_auc']}")
    ax[0].plot([0, 1], [0, 1], "k--", lw=1); ax[0].set_xlabel("Tasa de falsos positivos")
    ax[0].set_ylabel("Tasa de verdaderos positivos"); ax[0].set_title("Curva ROC"); ax[0].legend(frameon=False)
    ax[1].plot(rc, pr, color="#c55a11", lw=2, label=f"AP = {res['modelo_nivel_hora']['pr_auc']}")
    ax[1].set_xlabel("Recall"); ax[1].set_ylabel("Precisión"); ax[1].set_title("Curva Precisión–Recall"); ax[1].legend(frameon=False)
    plt.tight_layout(); plt.savefig(f"{OUT}/fig_roc_pr.png", dpi=170); plt.close()

    # 3) importancia de variables
    imp = r.importance.tail(10)
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.barh(imp.index, imp.values, color="#1f4e79"); ax.set_xlabel("Importancia relativa")
    ax.set_title("Variables más influyentes en la predicción")
    plt.tight_layout(); plt.savefig(f"{OUT}/fig_importance.png", dpi=170); plt.close()
    r.importance[::-1].round(4).to_json(f"{OUT}/importance.json")

    # 4) comparación de esquemas
    fig, ax = plt.subplots(1, 2, figsize=(8, 3.4))
    names = ["Umbrales fijos\n(reactivo)", "Modelo\npredictivo"]
    ax[0].bar(names, [m_th["pct_anticipadas"], m_ml["pct_anticipadas"]], color=["#a6a6a6", "#1f4e79"])
    ax[0].set_ylabel("% de fallas anticipadas"); ax[0].set_title("Fallas anticipadas (≤ 24 h)")
    ax[1].bar(names, [m_th["falsas_por_equipo_semana"], m_ml["falsas_por_equipo_semana"]], color=["#a6a6a6", "#1f4e79"])
    ax[1].set_ylabel("Falsas alertas / equipo / semana"); ax[1].set_title("Falsas alertas")
    plt.tight_layout(); plt.savefig(f"{OUT}/fig_comparison.png", dpi=170); plt.close()

    # 5) arquitectura
    fig, ax = plt.subplots(figsize=(9, 2.9)); ax.axis("off")
    boxes = [("Equipos:\nservidores,\ncámaras, red", 0.02), ("Recolección\nde métricas\n(SNMP / agentes)", 0.215),
             ("Almacén de\nseries de tiempo", 0.41), ("Variables y\nmodelo\npredictivo", 0.605),
             ("Dashboard y\nalertamiento\ntemprano", 0.80)]
    for txt, x in boxes:
        ax.add_patch(plt.Rectangle((x, 0.25), 0.17, 0.5, fc="#dae3f3", ec="#1f4e79", lw=1.5, transform=ax.transAxes))
        ax.text(x + 0.085, 0.5, txt, ha="center", va="center", fontsize=8.5, transform=ax.transAxes)
    for x in [0.19, 0.385, 0.58, 0.775]:
        ax.annotate("", xy=(x + 0.025, 0.5), xytext=(x, 0.5), xycoords="axes fraction",
                    arrowprops=dict(arrowstyle="->", color="#1f4e79", lw=1.8))
    plt.savefig(f"{OUT}/fig_architecture.png", dpi=170, bbox_inches="tight"); plt.close()

    r.raw.sample(2000, random_state=hm.SEED).to_csv(f"{OUT}/muestra_telemetria.csv", index=False)
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
