"""API de soporte a decisiones para la movilidad urbana de Posadas."""

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import List, Dict, Any
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, risk_engine, analista, investigador
    db = get_db_connection()
    init_schema(db)
    seed_reference_data(db)
    load_silver_incidents_from_jsonl(db)
    risk_engine = ExplainableRiskEngine(db)
    analista = AgenteAnalista(db)
    investigador = AgenteInvestigador()
    yield


app = FastAPI(
    title="AITARA — Copiloto Táctico de Movilidad Urbana API",
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
def api_incidents() -> List[Dict[str, Any]]:
    try:
        df = get_all_incidents(db)
        if df is None or not hasattr(df, "to_dict") or df.empty:
            return []
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


@app.get("/api/strategic")
def api_strategic() -> Dict[str, Any]:
    status = get_pipeline_status(db)
    _, prioridades = risk_engine.evaluate_all_nodes(ESCENARIO_REFERENCIA)
    ranking = []
    for prioridad in prioridades:
        nodo = prioridad.nodo
        factor = max(prioridad.aportes, key=lambda aporte: aporte.aporte, default=None)
        ranking.append({
            "nodo_id": nodo.nodo_id,
            "interseccion": nodo.nombre,
            "coordenadas": [nodo.lat, nodo.lon],
            "nivel": prioridad.nivel,
            "riesgo_estructural": prioridad.riesgo_estructural,
            "factor_mayor_aporte": factor.model_dump() if factor else None,
            "cantidad_incidentes_evidencia": len(prioridad.evidencia),
        })
    return {
        "escenario_referencia": ESCENARIO_REFERENCIA.model_dump(),
        "kpis": [
            {"label": "Incidentes registrados", "value": status["total_incidentes"]},
            {"label": "Nodos", "value": status["total_nodos_monitoreados"]},
            {"label": "Prioridades críticas", "value": sum(p.nivel == "critico" for p in prioridades)},
        ],
        "ranking_infraestructura": ranking,
    }


frontend_dist = Path(__file__).resolve().parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
