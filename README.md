# Monitoreo de salud predictivo (Predictive Health Monitoring)

Proyecto de residencia profesional · Delfino Antonio López Sosa (19390017)
Sistema predictivo de fallas en cámaras, servidores y equipos de red · Grupo Salinas – Dialogus

El sistema genera telemetría (simulada o importable de datos reales) de servidores,
**cámaras de reconocimiento facial** y equipos de red, entrena un modelo que estima la
probabilidad de falla en las próximas 24 horas, calcula un puntaje de salud de 0 a 100
por equipo y lo presenta en un **dashboard interactivo** con alertamiento temprano
priorizado por nivel de riesgo. Se conecta por **IP de sucursal** y compara el esquema
predictivo contra un monitoreo reactivo por umbrales fijos.

## Cobertura de los objetivos de la residencia

| # | Objetivo | Dónde se resuelve |
|---|---|---|
| 1 | Recopilar y analizar datos históricos de servidores, cámaras y red | `health_model.py` (simulación de telemetría + ingeniería de variables) |
| 2 | Modelo predictivo con puntaje de salud y probabilidad de falla | `health_model.py` (Gradient Boosting, etiqueta de falla a 24 h, salud = 100·(1−P)) |
| 3 | Dashboard de monitoreo con alertas priorizadas por riesgo | `app.py` + `pages/` + `dashboard_helpers.py` (Streamlit + Plotly) |
| 4 | Integración por sucursal (IP) con datos reales o simulados | Pantalla de conexión de `app.py` (IP → semilla → equipos) |

## Contenido

```
predictive-health-monitoring/
├── app.py                      Dashboard web (Streamlit): conexión por IP de sucursal
├── health_model.py             Núcleo: simulación, variables, modelo y métricas
├── dashboard_helpers.py        Gráficas y componentes visuales (Plotly)
├── predictive_health.py        Análisis en lote (genera PNG + results.json)
├── requirements.txt            Librerías necesarias
├── .streamlit/
│   └── config.toml             Tema y configuración de Streamlit
├── pages/                      Páginas del dashboard multipágina
│   ├── 1_📊_Panel_de_monitoreo.py    Estado y tendencia de salud por equipo
│   ├── 2_🚨_Alertas_tempranas.py      Alertas priorizadas por nivel de riesgo
│   ├── 3_🧠_Modelo_predictivo.py     Métricas, curvas ROC/PR e importancia
│   └── 4_📡_Telemetría.py             Exploración y exportación de datos
├── demo/
│   └── demo_monitoreo_predictivo.html   Demo sencilla en navegador (sin servidor)
├── .vscode/                    Configuración lista para Visual Studio Code
└── out/                        Se crea al ejecutar el lote (resultados y gráficas)
```

## Requisitos

- Python 3.10 o superior (https://www.python.org/downloads/). En Windows marca la casilla
  **"Add Python to PATH"** al instalarlo.
- Visual Studio Code con la extensión **Python** (VS Code te la sugerirá al abrir la carpeta).

## Cómo ejecutarlo en Visual Studio Code

1. Abre la carpeta: **Archivo → Abrir carpeta…** → `predictive-health-monitoring`.
2. Abre una terminal: **Terminal → Nueva terminal**.
3. Crea el entorno virtual e instala las librerías.

   **Windows (PowerShell):**
   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
   Si PowerShell bloquea la activación, ejecuta una vez
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a intentar,
   o usa `.venv\Scripts\activate.bat` en una terminal "Command Prompt".

   **macOS / Linux:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. Selecciona el intérprete: `Ctrl+Shift+P` → **Python: Select Interpreter** → elige el de `.venv`.

## A) Dashboard interactivo (lo principal para la presentación)

Desde la terminal (con `.venv` activo):

```powershell
streamlit run app.py
```

Se abre el navegador en `http://localhost:8501`. También puedes iniciarlo desde VS Code
con el botón ▶ (arriba a la izquierda) eligiendo **"Dashboard interactivo (Streamlit)"** o
pulsando **F5**.

### Conexión por sucursal

1. En la pantalla principal ingresa la **IP de la sucursal** (formato `X.X.X.X`, por
   ejemplo `10.20.30.5`), el nombre, la región y la cantidad de equipos a monitorear
   (servidores, cámaras de reconocimiento facial y equipos de red).
2. Pulsa **Conectar y monitorear**. El sistema descubre los equipos de esa sucursal,
   recopila la telemetría histórica y entrena el modelo predictivo (tarda unos segundos).
3. La misma IP siempre genera los mismos equipos y datos (la IP se convierte en una
   semilla determinista), de modo que la sucursal es reproducible. Conectar otra IP
   muestra una sucursal distinta.

### Páginas del dashboard

- **Panel de monitoreo** — KPIs generales, cuadrícula de equipos con su salud y tendencia,
  y al seleccionar un equipo: medidor de salud, evolución con bandas semáforo, telemetría
  (latencia, temperatura, pérdida, CPU) y ranking de salud.
- **Alertas tempranas** — equipos en alerta ordenados por prioridad (riesgo crítico, alto,
  medio), con salud, probabilidad de falla, ventana estimada de actuación y recomendación;
  comparación del modelo vs. umbrales fijos y bitácora de fallas del periodo.
- **Modelo predictivo** — ROC-AUC, PR-AUC, precisión, exhaustividad, F1, matriz de
  confusión, curvas ROC/PR e importancia de variables.
- **Telemetría** — exploración de las métricas por equipo y exportación a CSV.

> Verde ≥ 70, amarillo 40–69, rojo < 40. Alerta del modelo: probabilidad ≥ 0.5 durante
> 2 horas consecutivas. Alerta por umbrales: latencia > 90 ms, temperatura > 70 °C,
> pérdida > 6 % o CPU > 90 %, también 2 horas consecutivas.

## B) Análisis en lote (figuras y métricas)

```powershell
python predictive_health.py
```

Genera en la carpeta `out/` las gráficas PNG, `results.json` y `importance.json`.

## C) Demo sencilla en navegador

Abre `demo/demo_monitoreo_predictivo.html` con doble clic o con la extensión **Live
Server**. Selecciona un equipo y provoca una degradación o falla súbita para comparar
el aviso del modelo contra el de umbrales fijos. *Nota:* usa una regla de riesgo
simplificada, no el modelo entrenado en Python.

## Qué obtendrás en `out/` (análisis en lote)

| Archivo | Descripción |
|---|---|
| `results.json` | Métricas del modelo y comparación contra umbrales fijos |
| `fig_health_timeline.png` | Puntaje de salud de un equipo antes de una falla |
| `fig_roc_pr.png` | Curvas ROC y precisión–exhaustividad |
| `fig_comparison.png` | Modelo predictivo contra umbrales fijos |
| `fig_importance.png` | Variables más influyentes |
| `fig_architecture.png` | Diagrama de la arquitectura |
| `importance.json` | Importancia numérica de las variables |
| `muestra_telemetria.csv` | Muestra de 2,000 registros de la telemetría simulada |

Resultados esperados (semilla fija, reproducibles):
ROC-AUC ≈ 0.786; el modelo anticipa ≈ 76.9 % de las fallas contra ≈ 41.0 % de los umbrales fijos.

## Personalización rápida (parte superior de `health_model.py`)

| Constante | Significado |
|---|---|
| `N_SERVERS`, `N_CAMERAS`, `N_NET` | Cantidad de servidores, cámaras y equipos de red |
| `HOURS` | Horas de telemetría por equipo (por defecto 120 días) |
| `HORIZON` | Horizonte de predicción en horas (24) |
| `ALERT_THRESHOLD` | Probabilidad que dispara la alerta del modelo (0.5) |
| `SEED` | Semilla base; el dashboard deriva la suya de la IP |

Para usar **datos reales**, sustituye la función `build_dataset()` por la lectura de tus
métricas con las columnas: `device, tipo, hour, latencia_ms, cpu_pct, mem_pct, temp_c,
perdida_pct, reinicios, falla`, y conserva la separación temporal entre entrenamiento y prueba.

## Problemas frecuentes

- **`python` no se reconoce:** en Windows usa `py` en lugar de `python`, o reinstala Python con "Add to PATH".
- **`ModuleNotFoundError`:** el entorno virtual no está activo o no instalaste las librerías
  (`pip install -r requirements.txt`). Verifica que la terminal muestre `(.venv)`.
- **VS Code usa otro Python:** `Ctrl+Shift+P` → *Python: Select Interpreter* → elige `.venv`.
- **El dashboard no abre el navegador:** abre manualmente `http://localhost:8501`.

## Aviso

Los datos son sintéticos. Los resultados muestran el funcionamiento del método y no
representan el desempeño sobre la infraestructura real de la empresa.
