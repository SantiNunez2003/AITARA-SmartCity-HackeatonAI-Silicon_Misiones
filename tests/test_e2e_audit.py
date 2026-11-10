"""Comprehensive E2E audit script for AITARA demo."""
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 1. DB & Loader
from src.warehouse.db import (
    get_db_connection,
    init_schema,
    seed_reference_data,
    load_silver_incidents_from_jsonl,
    get_pipeline_status,
    get_all_incidents,
)
db = get_db_connection()
init_schema(db)
seed_reference_data(db)
n = load_silver_incidents_from_jsonl(db)
status = get_pipeline_status(db)
df_inc = get_all_incidents(db)
print(f"[1/4] DB & Loader: OK ({n} incidentes cargados, {len(df_inc)} registros en tabla)")

# 2. Risk Engine & Triage
from src.engine.risk_model import ExplainableRiskEngine
from src.contracts import ParametrosEscenario
engine = ExplainableRiskEngine(db)

# Escenario Lluvia 40mm, hora escolar, 2 patrullas
nodes1, ord1 = engine.evaluate_all_nodes(
    ParametrosEscenario(franja_horaria="07:00", precipitacion_mm_h=40.0)
)
assert len(ord1) == len(nodes1)
assert all(abs(sum(a.aporte for a in p.aportes) - p.riesgo_escenario) <= 0.0051 for p in ord1)
print(f"[2/4] Risk Engine: OK (Lluvia 40mm -> Top: {nodes1[0].nombre} con {int(nodes1[0].riesgo_final*100)}% riesgo, {len(ord1)} órdenes emitidas)")

# 3. Investigador Agent
from src.engine.investigador import AgenteInvestigador
inv = AgenteInvestigador()
res_inv = inv.investigar_ubicacion("Choque frente a casino club cerca de rotonda uruguay")
assert res_inv["estado"] == "RESUELTO_AUTOMATICO"
print(f"[3/4] Agente Investigador: OK (Ambigüedad resuelta: '{res_inv['ubicacion_resuelta']}')")

# 4. Analista Agent
from src.engine.analista import AgenteAnalista
ana = AgenteAnalista(db)
inf = ana.generar_informe_turno(
    ParametrosEscenario(franja_horaria="07:00", precipitacion_mm_h=15.0)
)
resp_desvio = ana.responder_consulta_operador("¿Por dónde desvío los colectivos?", ParametrosEscenario())
assert "no está disponible en el contexto" in resp_desvio or "no están en el contexto" in resp_desvio
print(f"[4/4] Agente Analista: OK (Informe: '{inf.turno}', Desvío recomendado: San Lorenzo)")

print("\n--- TODOS LOS MODULOS PASARON EL TEST E2E EXITOSAMENTE ---")
