"""API de soporte a decisiones para la movilidad urbana de Posadas."""

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import List, Dict, Any, Literal
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.contracts import ParametrosEscenario
from src.warehouse.db import (
    get_db_connection,
    init_schema,
    seed_reference_data,
    load_silver_incidents_from_jsonl,
    get_pipeline_status,
    get_all_incidents,
)
from src.engine.risk_model import ExplainableRiskEngine
from src.engine.analista import AgenteAnalista
from src.engine.investigador import AgenteInvestigador
from src.ingesta.recolector import recolectar_noticias_recientes, extraer_articulo_por_url
from src.ingesta.lector import AgenteLector, procesar_noticia

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, risk_engine, analista, investigador, lector
    db = get_db_connection()
    init_schema(db)
    seed_reference_data(db)
    load_silver_incidents_from_jsonl(db)
    risk_engine = ExplainableRiskEngine(db)
    analista = AgenteAnalista(db, risk_engine)
    investigador = AgenteInvestigador()
    lector = AgenteLector(investigador)
    yield


app = FastAPI(
    title="AITARA — Soporte a decisiones de movilidad urbana API",
    version="2.1.0",
    description="Backend Analítico Geoespacial (DuckDB + Modelos XAI + Agentes Lector, Investigador y Analista)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
    pregunta: str
    franja_horaria: str = "07:00"
    precipitacion_mm_h: float = 15.0


ESCENARIO_REFERENCIA = ParametrosEscenario()


@app.get("/api/status")
def api_status() -> Dict[str, Any]:
    return get_pipeline_status(db)


@app.get("/api/incidents")
def api_incidents(origen: Literal["real", "simulado", "todos"] = "real") -> List[Dict[str, Any]]:
    try:
        df = get_all_incidents(db)
        if df is None or not hasattr(df, "to_dict") or df.empty:
            return []
        if origen != "todos":
            df = df[df["origen"].fillna("real") == origen]
        records = df.to_dict(orient="records")
        for r in records:
            r["fecha_publicacion"] = str(r.get("fecha_publicacion") or "")
            r["fecha_evento"] = str(r.get("fecha_evento") or r["fecha_publicacion"])
            veh_raw = r.get("vehiculos", "")
            if isinstance(veh_raw, str):
                r["vehiculos_lista"] = [v.strip() for v in veh_raw.split(",") if v.strip()]
            else:
                r["vehiculos_lista"] = list(veh_raw or [])
        return records
    except Exception as e:
        print(f"Error procesando /api/incidents: {e}")
        return []


@app.post("/api/evaluate")
def api_evaluate(params: ParametrosEscenario) -> Dict[str, Any]:
    try:
        evaluaciones, prioridades = risk_engine.evaluate_all_nodes(params)
    except Exception as e:
        print(f"Error evaluando nodos: {e}")
        evaluaciones, prioridades = [], []

    try:
        informe = analista.generar_informe_turno(params)
    except Exception as e:
        print(f"Error generando informe de turno: {e}")
        informe = SimpleNamespace(
            turno=f"Guardia Operativa ({params.franja_horaria} hs)",
            alerta_meteorologica="No disponible",
            recomendacion_estrategica="Informe no disponible. Consultar los resultados por nodo.",
        )

    return {
        "escenario": params.model_dump(),
        "nodos": [n.model_dump() for n in evaluaciones],
        "prioridades": [p.model_dump() for p in prioridades],
        "resumen_turno": {
            "turno": informe.turno,
            "alerta_meteorologica": informe.alerta_meteorologica,
            "recomendacion_estrategica": informe.recomendacion_estrategica,
        },
    }


@app.post("/api/ask")
def api_ask(req: AskRequest) -> Dict[str, Any]:
    params = ParametrosEscenario(
        franja_horaria=req.franja_horaria,
        precipitacion_mm_h=req.precipitacion_mm_h,
    )
    respuesta = analista.responder_consulta_operador(req.pregunta, params)
    return {
        "pregunta": req.pregunta,
        "respuesta": respuesta,
        "motor": "Asistente de Movilidad AITARA",
    }


# Percentil 75 de los riesgos estructurales de los nodos con incidentes.
UMBRAL_ZONA_CRITICA = 0.75


@app.get("/api/strategic")
def api_strategic() -> Dict[str, Any]:
    status = get_pipeline_status(db)
    _, prioridades = risk_engine.evaluate_all_nodes(ESCENARIO_REFERENCIA)
    riesgos = dict(db.df("SELECT node_id, intensidad FROM gold_node_risk_features").itertuples(index=False, name=None))
    distribucion = sorted(riesgos[p.nodo.nodo_id] for p in prioridades if riesgos.get(p.nodo.nodo_id, 0) > 0)
    from math import ceil
    umbral = distribucion[ceil(UMBRAL_ZONA_CRITICA * len(distribucion)) - 1] if distribucion else None
    ranking = []
    for prioridad in sorted(prioridades, key=lambda p: riesgos.get(p.nodo.nodo_id, p.riesgo_estructural), reverse=True):
        nodo = prioridad.nodo
        factor = max(prioridad.aportes, key=lambda aporte: aporte.aporte, default=None)
        ranking.append({
            "nodo_id": nodo.nodo_id,
            "interseccion": nodo.nombre,
            "coordenadas": [nodo.lat, nodo.lon],
            "nivel": "critico" if umbral is not None and riesgos.get(nodo.nodo_id, prioridad.riesgo_estructural) >= umbral else "no_critico",
            "riesgo_estructural": prioridad.riesgo_estructural,
            "factor_mayor_aporte": factor.model_dump() if factor else None,
            "cantidad_incidentes_evidencia": prioridad.total_evidencia,
            "evidencia_real": prioridad.evidencia_real,
            "evidencia_simulada": prioridad.evidencia_simulada,
        })
    return {
        "escenario_referencia": ESCENARIO_REFERENCIA.model_dump(),
        "kpis": [
            {"label": "Incidentes registrados", "value": status["total_incidentes"], "reales": status.get("incidentes_por_origen", {}).get("real", 0), "simulados": status.get("incidentes_por_origen", {}).get("simulado", 0)},
            {"label": "Nodos", "value": status["total_nodos_monitoreados"]},
            {"label": "Zonas críticas", "value": sum(r["nivel"] == "critico" for r in ranking)},
        ],
        "ranking_infraestructura": ranking,
    }


class IngestUrlRequest(BaseModel):
    url: str


@app.post("/api/ingest/scan")
def api_ingest_scan(limite: int = 8) -> Dict[str, Any]:
    """Escanea portales de noticias locales de Posadas y agrega incidentes viales nuevos."""
    try:
        articulos = recolectar_noticias_recientes(limite=limite)
    except Exception as e:
        articulos = []
    nuevos, mismo_hecho = [], []
    for art in articulos:
        try:
            estado, inc = procesar_noticia(art, db, lector=lector)
        except Exception:
            continue
        if estado == "nuevo":
            nuevos.append(inc)
        elif estado == "duplicado_medio":
            mismo_hecho.append({"incidente_id": inc["id"], "fuente": art.get("fuente"), "url": art.get("url")})
    return {
        "articulos_analizados": len(articulos),
        "nuevos_ingestados": len(nuevos),
        "duplicados_entre_medios": len(mismo_hecho),
        "incidentes": nuevos,
        "fuentes_relacionadas_agregadas": mismo_hecho,
        "total_actual": get_pipeline_status(db)["total_incidentes"]
    }


@app.post("/api/ingest/url")
def api_ingest_url(req: IngestUrlRequest) -> Dict[str, Any]:
    """Descarga y extrae una noticia vial bajo demanda a partir de una URL."""
    url = req.url.strip()
    if not url:
        return {"status": "error", "mensaje": "URL vacía."}
    art = extraer_articulo_por_url(url)
    if not art:
        return {"status": "error", "mensaje": f"No se pudo descargar o extraer la noticia de {url}."}
    estado, inc = procesar_noticia(art, db, lector=lector)
    if estado == "duplicado_medio":
        return {
            "status": "duplicado",
            "mensaje": f"Otro medio ya había reportado este hecho ({inc['id']}). La nota se agregó como fuente relacionada.",
            "incidente": inc,
        }
    if estado != "nuevo":
        return {"status": "omitido", "mensaje": "La noticia ya se encuentra en la base de datos o fue descartada."}
    return {
        "status": "ok",
        "mensaje": "Incidente georreferenciado e indexado exitosamente.",
        "incidente": inc,
        "total_actual": get_pipeline_status(db)["total_incidentes"]
    }


frontend_dist = Path(__file__).resolve().parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
