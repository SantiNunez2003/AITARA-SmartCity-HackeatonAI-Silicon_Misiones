from datetime import datetime
import sqlite3
import threading
from types import SimpleNamespace

from fastapi.testclient import TestClient

import api
from src.contracts import AporteFactor, EvaluacionNodo, Evidencia, ParametrosEscenario, Prioridad
from src.warehouse.db import DBWrapper, get_pipeline_status, init_schema


def test_status_fuentes_desde_base():
    db = DBWrapper.__new__(DBWrapper)
    db.use_duckdb = False
    db._lock = threading.RLock()
    db.con = sqlite3.connect(':memory:')
    init_schema(db)
    assert get_pipeline_status(db)['fuentes_activas'] == []
    for ident, fuente in [('1', 'Medio B'), ('2', 'Medio A'), ('3', 'Medio B'), ('4', None)]:
        db.execute('INSERT INTO silver_incident_history (id, fuente) VALUES (?, ?)', (ident, fuente))
    estado = get_pipeline_status(db)
    assert estado['fuentes_activas'] == ['Medio A', 'Medio B']
    assert estado['total_incidentes'] == 4


def test_respuestas_y_cambios_en_strategic(monkeypatch):
    nodo = EvaluacionNodo(nodo_id='n', nombre='Nodo', lat=-27, lon=-55,
                          riesgo_estructural=0.3, variacion_escenario=1,
                          riesgo_final=0.7, es_critico=True, factores=[])
    prioridad = Prioridad(nodo=nodo, nivel='critico', riesgo_estructural=0.3,
                          variacion_escenario=1, riesgo_escenario=0.7,
                          aportes=[AporteFactor(nombre='clima', aporte=0.7, descripcion='aporte')],
                          evidencia=[])
    with TestClient(api.app) as client:
        estado = {'total_incidentes': 2, 'total_nodos_monitoreados': 1, 'fuentes_activas': ['fuente']}
        conexion = sqlite3.connect(':memory:', check_same_thread=False)
        conexion.execute('CREATE TABLE gold_node_risk_features (node_id TEXT, intensidad REAL)')
        conexion.execute("INSERT INTO gold_node_risk_features VALUES ('n', 0.3)")
        base = DBWrapper.__new__(DBWrapper)
        base.con = conexion
        base._lock = threading.RLock()
        base.use_duckdb = False
        monkeypatch.setattr(api, 'db', base)
        monkeypatch.setattr(api, 'get_pipeline_status', lambda db: estado)
        monkeypatch.setattr(api.risk_engine, 'evaluate_all_nodes', lambda params: ([nodo], [prioridad]))
        primera = client.get('/api/strategic').json()
        assert primera['escenario_referencia'] == ParametrosEscenario().model_dump()
        assert [k['value'] for k in primera['kpis']] == [2, 1, 1]
        assert primera['ranking_infraestructura'][0]['factor_mayor_aporte']['nombre'] == 'clima'
        estado['total_incidentes'] = 3
        prioridad.nivel = 'no_critico'
        conexion.execute('UPDATE gold_node_risk_features SET intensidad = 0')
        prioridad.evidencia.append(Evidencia(id='i', fecha=datetime(2025, 1, 1), tipo='choque', fuente='fuente', origen='simulado'))
        prioridad.total_evidencia = 1
        prioridad.evidencia_simulada = 1
        segunda = client.get('/api/strategic').json()
        assert [k['value'] for k in segunda['kpis']] == [3, 1, 0]
        assert segunda['ranking_infraestructura'][0]['cantidad_incidentes_evidencia'] == 1
        for respuesta in [client.get('/api/status'), client.get('/api/strategic'), client.post('/api/evaluate', json={})]:
            assert respuesta.status_code == 200
            for clave in ('latencia_consulta_ms', 'corredor_desvio', 'causa_raiz', 'obra_recomendada'):
                assert clave not in respuesta.text
