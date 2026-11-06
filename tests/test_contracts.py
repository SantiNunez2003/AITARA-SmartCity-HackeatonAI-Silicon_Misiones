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
    params = ParametrosEscenario(franja_horaria="07:00", precipitacion_mm_h=15.0, dotacion_patrullas=4)
    
    engine = ExplainableRiskEngine(db)
    nodes, ordenes = engine.evaluate_all_nodes(params)
    assert len(nodes) >= 5, "Expected at least 5 evaluated nodes"
    assert len(ordenes) <= 4, "Patrol triage exceeded available dotacion"
    
    analista = AgenteAnalista(db)
    informe = analista.generar_informe_turno(params)
    assert len(informe.ordenes_despacho) <= 4
    assert "Corrientes" in informe.ordenes_despacho[0].nodo_objetivo or "Uruguay" in informe.ordenes_despacho[0].nodo_objetivo
    print("Risk model and Analista test passed successfully.")


if __name__ == "__main__":
    test_contracts_and_warehouse()
    test_risk_model_and_analista()
    print("All automated tests PASSED.")
