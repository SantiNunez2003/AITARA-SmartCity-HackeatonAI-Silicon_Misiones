"""Automated tests for AITARA core modules.

Validates:
1. Pydantic contracts.
2. DuckDB / SQLite data warehouse loading.
3. 4-dimensional risk model and capacity triage.
4. Analista agent report generation.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.contracts import IncidenteSilver, ParametrosEscenario
from src.warehouse.db import get_db_connection, init_schema, seed_reference_data, load_silver_incidents_from_jsonl, get_pipeline_status
from src.engine.risk_model import ExplainableRiskEngine
from src.engine.analista import AgenteAnalista


def test_contracts_and_warehouse():
    db = get_db_connection()
    init_schema(db)
    seed_reference_data(db)
    loaded = load_silver_incidents_from_jsonl(db)
    assert loaded >= 10, f"Expected at least 10 incidents, got {loaded}"
    
    status = get_pipeline_status(db)
    assert status["total_incidentes"] >= 10
    assert status["total_nodos_monitoreados"] >= 5
    print("Warehouse test passed successfully.")


def test_risk_model_and_analista():
    db = get_db_connection()
    params = ParametrosEscenario(franja_horaria="07:00", precipitacion_mm_h=15.0)
    
    engine = ExplainableRiskEngine(db)
    nodes, prioridades = engine.evaluate_all_nodes(params)
    assert len(nodes) >= 5, "Expected at least 5 evaluated nodes"
    assert len(prioridades) == len(nodes)
    for prioridad in prioridades:
        assert {a.nombre for a in prioridad.aportes} == {"temporal", "clima", "topologia", "siniestralidad"}
        assert abs(sum(a.aporte for a in prioridad.aportes) - prioridad.riesgo_escenario) <= 0.0051
    
    analista = AgenteAnalista(db)
    informe = analista.generar_informe_turno(params)
    assert len(informe.prioridades) == len(nodes)
    print("Risk model and Analista test passed successfully.")


if __name__ == "__main__":
    test_contracts_and_warehouse()
    test_risk_model_and_analista()
    print("All automated tests PASSED.")


def test_evidencia_nodo_mas_cercano_y_limite():
    import sqlite3
    import threading
    from src.warehouse.db import DBWrapper
    from src.engine.risk_model import DISTANCIA_EVIDENCIA_METROS

    db = DBWrapper.__new__(DBWrapper)
    db.use_duckdb = False
    db._lock = threading.RLock()
    db.con = sqlite3.connect(":memory:")
    init_schema(db)
    init_schema(db)
    seed_reference_data(db)
    for ident, lat, lon, origen in [
        ("cercano", -27.372758, -55.901911, "simulado"),
        ("lejano", -25.0, -55.0, "real"),
    ]:
        db.execute("INSERT INTO silver_incident_history (id, fuente, fecha_publicacion, tipo_incidente, lat, lon, origen) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (ident, "fuente", "2025-01-01", "choque", lat, lon, origen))
    _, prioridades = ExplainableRiskEngine(db).evaluate_all_nodes(ParametrosEscenario())
    evidencia = [(p.nodo.nodo_id, e) for p in prioridades for e in p.evidencia]
    assert DISTANCIA_EVIDENCIA_METROS > 0
    assert len(evidencia) == 1
    assert evidencia[0][0] == "N1_CORRIENTES_TUCUMAN"
    assert evidencia[0][1].id == "cercano"
    assert evidencia[0][1].origen == "simulado"
    assert any(not p.evidencia for p in prioridades)
