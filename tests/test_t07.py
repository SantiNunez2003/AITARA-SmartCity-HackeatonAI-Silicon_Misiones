import sqlite3
import threading
import json
import pytest
from fastapi.testclient import TestClient
import api
from src.contracts import ParametrosEscenario
from src.engine.risk_model import ExplainableRiskEngine, estimar_efecto_lluvia
from src.ingesta.generador_sintetico import generar
from src.warehouse.db import DBWrapper, init_schema, seed_reference_data, load_silver_incidents_from_jsonl
import src.warehouse.db as warehouse

TOLERANCIA_LLUVIA = 0.25


def base():
    db = DBWrapper.__new__(DBWrapper)
    db.use_duckdb = False
    db._lock = threading.RLock()
    db.con = sqlite3.connect(":memory:")
    init_schema(db)
    seed_reference_data(db)
    return db


@pytest.mark.parametrize('multiplicador', [1.8, 1.2])
def test_recuperacion_y_origen(multiplicador, tmp_path, monkeypatch):
    eventos, exposicion = generar(multiplicador_lluvia=multiplicador)
    archivo = tmp_path / 'incidentes.jsonl'
    archivo.write_text(''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in eventos), encoding='utf-8')
    archivo_exposicion = tmp_path / 'exposicion.json'
    archivo_exposicion.write_text(json.dumps(exposicion), encoding='utf-8')
    monkeypatch.setattr(warehouse, 'SIMULADO_JSONL_PATH', archivo)
    monkeypatch.setattr(warehouse, 'SILVER_JSONL_PATH', tmp_path / 'ausente')
    db = base()
    load_silver_incidents_from_jsonl(db)
    load_silver_incidents_from_jsonl(db)
    assert db.con.execute('SELECT COUNT(*) FROM silver_incident_history').fetchone()[0] == len(eventos)
    assert abs(estimar_efecto_lluvia(db, json.loads(archivo_exposicion.read_text(encoding='utf-8'))) - multiplicador) < TOLERANCIA_LLUVIA
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
        assert abs(sum(a.aporte for a in p.aportes) - p.riesgo_escenario) <= 0.0051
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


def test_varios_leves_superan_un_grave():
    db = base()
    for ident, lat, lon, gravedad in [('grave', -27.4038, -55.9028, 3)] + [(f'leve{i}', -27.40115, -55.917214, 1) for i in range(8)]:
        db.execute("INSERT INTO silver_incident_history (id, severidad, confianza, lat, lon, origen) VALUES (?, ?, 1, ?, ?, 'simulado')", (ident, gravedad, lat, lon))
    ExplainableRiskEngine(db)
    riesgos = dict(db.con.execute('SELECT node_id, intensidad FROM gold_node_risk_features').fetchall())
    assert riesgos['N3_QUARANTA_GUIDO'] > riesgos['N2_ROTONDA_URUGUAY']
    assert all(0 <= riesgo <= 1 for riesgo in riesgos.values())
