import sqlite3
import threading
from fastapi.testclient import TestClient
import api
from src.contracts import ParametrosEscenario
from src.engine.risk_model import ExplainableRiskEngine
from src.ingesta.generador_sintetico import generar, estimar_efecto_lluvia
from src.warehouse.db import DBWrapper, init_schema, seed_reference_data

TOLERANCIA_LLUVIA = 0.25


def base():
    db = DBWrapper.__new__(DBWrapper)
    db.use_duckdb = False
    db._lock = threading.RLock()
    db.con = sqlite3.connect(":memory:")
    init_schema(db)
    seed_reference_data(db)
    return db


def test_recuperacion_y_origen():
    eventos, exposicion = generar(multiplicador_lluvia=1.8)
    assert abs(estimar_efecto_lluvia(eventos, exposicion) - 1.8) < TOLERANCIA_LLUVIA
    assert all(e["origen"] == "simulado" and e["fuente"] in ("911", "parte_policial") and (e["precipitacion_mm_h"] > 0) == e["llovia"] for e in eventos)


def test_ranking_cambia_y_campos_eliminados():
    db = base()
    campos = {r[1] for r in db.con.execute("PRAGMA table_info(gold_node_risk_features)")}
    assert not campos.intersection({"historical_incident_score", "school_vulnerability_weight", "rain_sensitivity_factor", "base_capacity_veh_hour"})
    def agregar(prefijo, lat, lon):
        for i in range(100):
            db.execute("INSERT INTO silver_incident_history (id, fuente, fecha_publicacion, tipo_incidente, severidad, confianza, lat, lon, origen) VALUES (?, '911', '2025-01-01', 'choque', 2, 1, ?, ?, 'simulado')", (f"{prefijo}{i}", lat, lon))
    agregar("a", -27.4038, -55.9028)
    _, primero = ExplainableRiskEngine(db).evaluate_all_nodes(ParametrosEscenario())
    assert max(primero, key=lambda p: p.riesgo_estructural).nodo.nodo_id.startswith("N2")
    db.execute("DELETE FROM silver_incident_history")
    agregar("b", -27.401150, -55.917214)
    _, segundo = ExplainableRiskEngine(db).evaluate_all_nodes(ParametrosEscenario())
    assert max(segundo, key=lambda p: p.riesgo_estructural).nodo.nodo_id.startswith("N3")
    assert max(segundo, key=lambda p: p.riesgo_estructural).total_evidencia == 100
    assert len(max(segundo, key=lambda p: p.riesgo_estructural).evidencia) == 5
    for p in segundo:
        assert abs(sum(a.aporte for a in p.aportes) - p.riesgo_escenario) < 1e-10
        assert p.variacion_escenario == 0


def test_api_filtra_origen():
    with TestClient(api.app) as client:
        reales = client.get("/api/incidents").json()
        simulados = client.get("/api/incidents?origen=simulado").json()
        todos = client.get("/api/incidents?origen=todos").json()
        assert reales and simulados
        assert all(e["origen"] == "real" for e in reales)
        assert all(e["origen"] == "simulado" for e in simulados)
        assert len(todos) == len(reales) + len(simulados)
