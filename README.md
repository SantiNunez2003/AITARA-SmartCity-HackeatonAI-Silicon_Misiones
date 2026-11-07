# AITARA — Soporte a decisiones para la movilidad urbana

**Hackathon IA en Acción, Silicon Misiones 2026 · Track Smart City · Desafío 1**

AITARA reúne información dispersa sobre la movilidad de Posadas en una memoria común y prioriza dónde y cuándo aumenta el riesgo vial, explicando cada resultado. **El sistema recomienda y explica; la decisión es siempre humana.** No controla semáforos, no interviene infraestructura, no asigna responsabilidades en siniestros ni realiza peritajes.

## Probar la demo

**[Abrir AITARA](https://aitara-smartcity-hackeatonai-silicon.onrender.com/)**

> [!IMPORTANT]
> **La primera carga puede tardar cerca de 1 minuto.** La demo está en un plan gratuito que se duerme tras 15 minutos sin uso. Si ves una pantalla de carga de Render, no es un error: esperá a que abra sola y no cierres la pestaña. Después funciona con normalidad.

Un recorrido sugerido:

1. En **Mapa de prioridades**, tocá **Realizar Análisis de Corredores**.
2. Elegí **07:00 hs** y **15 mm/h (Lluvia)** para ver el escenario de lluvia en horario escolar.
3. Revisá cada prioridad: su nivel, el aporte de cada factor, la variación frente a un día sin lluvia y los incidentes que la respaldan.
4. Consultá al **Asistente AITARA**, por ejemplo: «¿Cuáles son las prioridades del escenario?».
5. Mirá el ranking en **Análisis estratégico** y las noticias originales en **Centro de Información y Fuentes**.

## Sobre los datos

> [!NOTE]
> **La demo usa sobre todo datos simulados.** Sirven para demostrar el sistema y validar el método, no para afirmar resultados sobre la ciudad.

| Origen | Qué incluye | Cómo se ve |
|---|---|---|
| Real | Noticias locales de siniestros, con enlace a la nota | Sin marca |
| Simulado | Partes policiales y del 911 generados con reglas y parámetros declarados | Marca **SIMULADO** |
| A gestionar | Registros oficiales, aforos, Waze for Cities y agenda municipal | Todavía no están en el sistema |

Los pesos del riesgo son parámetros iniciales por criterio experto, no están calibrados con datos reales. Esa validación se haría en un piloto con datos oficiales.

## Estado del prototipo

| Componente | Estado |
|---|---|
| Memoria de incidentes, reales y simulados | Disponible |
| Riesgo estructural calculado desde los incidentes | Disponible |
| Escenarios por horario, lluvia y actividad escolar, con aporte por factor | Disponible |
| Ranking de zonas críticas con evidencia | Disponible |
| Analista, con Gemini y respaldo sin conexión que usa los mismos datos calculados | Disponible |
| Generador sintético y prueba de recuperación del efecto de lluvia | Disponible |
| Lector de noticias con IA | Pendiente: las noticias actuales ya están estructuradas |
| Investigador de ubicaciones dudosas | Módulo inicial, sin conectar a la API |
| Eje de fluidez, avisos y rutas alternativas | Pendiente |

## Puesta en marcha local

Requiere Python 3.12 y Node 22. Sin clave de Gemini, el Analista responde con su respaldo.

```bash
pip install -r requirements.txt
uvicorn api:app --reload
```

La API queda en <http://127.0.0.1:8000>. En otra terminal, levantá la interfaz en <http://localhost:5173>:

```bash
cd frontend
npm ci
npm run dev
```

Para usar Gemini, copiá `.env.example` como `.env` y completá `GEMINI_API_KEY`. Nunca subas ese archivo al repositorio.

### Otros comandos

```bash
python -m pytest -q tests                # tests
python -m src.ingesta.generador_sintetico # regenerar los datos simulados
docker build -t aitara .                 # imagen con API e interfaz
docker run -p 8000:8000 -e PORT=8000 aitara
```

## Estructura

| Ruta | Contenido |
|---|---|
| `api.py` | API FastAPI; también sirve la interfaz compilada |
| `frontend/` | Interfaz React, Vite y Leaflet |
| `src/contracts.py` | Contratos de datos compartidos |
| `src/ingesta/` | Generador de datos simulados |
| `src/warehouse/` | Base de datos DuckDB |
| `src/engine/` | Motor de riesgo, Analista e Investigador |
| `data/` | Noticias estructuradas y datos simulados |
| `docs/` | Propuesta técnica y documentación |

## Despliegue en Render

La demo corre en un único servicio de Render, en plan gratuito, con Docker.

**Crear el servicio**

1. Crear un **Web Service** desde **Public Git Repository** con `https://github.com/SantiNunez2003/AITARA-SmartCity-HackeatonAI-Silicon_Misiones`, en la rama `master`.
2. Elegir runtime **Docker** y plan **Free**.
3. Definir el health check en `/api/status`.
4. Opcionalmente, cargar `GEMINI_API_KEY` como variable del servicio.

**Publicar cambios**

Render no se actualiza solo. Después de cada merge a `master`, usar **Manual Deploy → Deploy latest commit** y esperar a que aparezca **Live**. Mientras tanto, sigue en línea la versión anterior.

**Antes de presentar**

Abrí la demo unos 5 minutos antes para que ya esté despierta.

## Equipo AITARA

- **Santiago Agustín Nuñez** — Lead Architect & ML Engineer
- **Joaquin Sanchez** — Backend & Data Engineer
- **Facundo Fraga** — Data Analyst & GIS Specialist
- **Ana Florencia Zayas** — Product Owner & Referente del Equipo (`zayasflorenciaana@gmail.com`)

**Mentores asignados:** Enzo Mereles, Ulises.
