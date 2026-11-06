"""AITARA - Explainable AI (XAI) Spatiotemporal Risk Engine.

Implements the 4-dimensional risk model from Joaquín's technical specification:
1. Dimensión Temporal y Demanda (Event-Driven)
2. Dimensión Meteorológica de Calzada (Context-Driven - OPAD)
3. Dimensión Topológica y Capacidad Vial (Network-Driven - IDE Posadas)
4. Dimensión de Riesgo Siniestral (Safety-Driven - Lector News History)

Calculates:
- Riesgo Estructural (Línea base histórica)
- Variación por Escenario (Cociente vs día habitual)
- Triaje por dotación disponible de patrullas
"""

from typing import List, Dict, Any, Tuple
from datetime import datetime, time, timedelta

from src.contracts import EvaluacionNodo, OrdenDespacho, ParametrosEscenario
from src.warehouse.db import get_db_connection, DBWrapper


class ExplainableRiskEngine:
    def __init__(self, db: DBWrapper = None):
        self.db = db or get_db_connection()

    def evaluate_all_nodes(self, params: ParametrosEscenario) -> Tuple[List[EvaluacionNodo], List[OrdenDespacho]]:
        """Evaluates all monitored nodes under the given scenario parameters,

        applying capacity triage according to dotacion_patrullas.
        """
        # Fetch nodes joined with features
        query = """
            SELECT 
                i.node_id, i.name, i.lat, i.lon, i.corridor_type, i.lanes,
                i.has_traffic_light, i.has_bus_stop, i.is_school_zone, i.school_name,
                i.drainage_risk_level,
                f.base_capacity_veh_hour, f.historical_incident_score,
                f.school_vulnerability_weight, f.rain_sensitivity_factor
            FROM silver_intersections i
            LEFT JOIN gold_node_risk_features f ON i.node_id = f.node_id;
        """
        df_nodes = self.db.df(query)
        if df_nodes is None or not hasattr(df_nodes, "iterrows") or df_nodes.empty:
            return [], []
        evaluations = []

        # Parse requested hour (e.g. '07:00' -> 7.0)
        try:
            parts = params.franja_horaria.split(":")
            hour_float = float(parts[0]) + float(parts[1]) / 60.0
        except Exception:
            hour_float = 7.0

        for _, row in df_nodes.iterrows():
            eval_node = self._evaluate_single_node(row, hour_float, params)
            evaluations.append(eval_node)

        # Sort by final risk descending
        evaluations.sort(key=lambda x: x.riesgo_final, reverse=True)

        # Generate dispatch orders for Top N nodes based on available patrols
        dotacion = max(1, params.dotacion_patrullas)
        top_critical = [n for n in evaluations if n.es_critico][:dotacion]
        
        # If fewer critical than patrols, take highest risk available
        if len(top_critical) < dotacion:
            top_critical = evaluations[:dotacion]

        ordenes = []
        for i, node in enumerate(top_critical, 1):
            hora_str = params.franja_horaria
            if node.nodo_id == "N1_CORRIENTES_TUCUMAN":
                instruccion = f"Posicionarse en Av. Corrientes y Catamarca 15 min antes ({hora_str} hs). Colocar 4 conos para encauzar carril izquierdo de flujo continuo y evitar detención en doble fila."
                desvio = "Sugerir a líneas de colectivos giro preventivo en calle San Lorenzo."
            elif node.nodo_id == "N2_ROTONDA_URUGUAY":
                instruccion = f"Ubicar móvil con baliza encendida sobre colectora Sur de Av. Quaranta ({hora_str} hs) para forzar reducción de velocidad de motociclistas ante asfalto mojado."
                desvio = "Monitoreo visual continuo de incorporación desde Travesía Urbana."
            elif node.nodo_id == "N4_SAN_MARTIN_ANDRESITO":
                instruccion = f"Puesto preventivo en Av. San Martín y Andresito ({hora_str} hs) para encauzar vehículos livianos ante acumulación de agua en cota baja."
                desvio = "Desvío de vehículos bajos por Av. Urquiza."
            elif node.nodo_id == "N5_CABRED_LOPEZ_TORRES":
                instruccion = f"Mantener despejado carril de emergencias del Hospital Madariaga sobre Av. López Torres ({hora_str} hs)."
                desvio = "Desviar transporte pesado por Av. Rademacher."
            else:
                instruccion = f"Móvil {i} en puesto fijo de disuasión y control de fluidez en {node.nombre} ({hora_str} hs)."
                desvio = "Mantener despejada calzada principal."

            ordenes.append(OrdenDespacho(
                movil_id=f"Móvil {i}",
                nodo_objetivo=node.nombre,
                hora_presentacion=hora_str,
                instruccion_tactica=instruccion,
                desvio_transporte=desvio
            ))

        return evaluations, ordenes

    def _evaluate_single_node(self, row: Any, hour_float: float, params: ParametrosEscenario) -> EvaluacionNodo:
        is_school = bool(row["is_school_zone"]) and params.actividad_escolar
        rain_mm = params.precipitacion_mm_h
        historical_score = float(row["historical_incident_score"] or 0.5)

        # 1. Dimensión Temporal y Demanda
        dim_temporal = 0.25
        if 6.75 <= hour_float <= 7.75:
            dim_temporal = 0.95 if is_school else 0.70
        elif 11.75 <= hour_float <= 13.25:
            dim_temporal = 0.90 if is_school else 0.75
        elif 17.25 <= hour_float <= 18.75:
            dim_temporal = 0.85 if is_school else 0.80

        # 2. Dimensión Meteorológica (OPAD)
        drainage = str(row["drainage_risk_level"] or "BAJO")
        drain_mult = 1.35 if drainage == "ALTO" else (1.15 if drainage == "MEDIO" else 0.90)
        dim_clima = min(1.0, (rain_mm / 25.0) * drain_mult)
        dim_clima = max(0.1, dim_clima)

        # 3. Dimensión Topológica (IDE Posadas)
        lanes = int(row["lanes"] or 2)
        has_bus = bool(row["has_bus_stop"])
        dim_topologia = 0.35
        if lanes <= 2:
            dim_topologia += 0.30
        if has_bus:
            dim_topologia += 0.20
        dim_topologia = min(1.0, dim_topologia)

        # 4. Dimensión Siniestral
        dim_siniestral = historical_score

        # Cálculo de Riesgo Estructural (Base histórica sin eventos excepcionales)
        riesgo_estructural = round(0.40 * dim_topologia + 0.60 * dim_siniestral, 2)

        # Cálculo de Riesgo con Escenario Activo
        # Ponderación: Temporal (35%), Clima (30%), Topología (20%), Siniestral (15%)
        riesgo_activo = (
            dim_temporal * 0.35 +
            dim_clima * 0.30 +
            dim_topologia * 0.20 +
            dim_siniestral * 0.15
        )
        riesgo_final = round(min(1.0, max(0.05, riesgo_activo)), 2)

        # Variación por Escenario (Cociente vs habitual)
        variacion_pct = round(((riesgo_final / max(0.20, riesgo_estructural)) - 1.0) * 100, 1)

        # Factores dominantes
        factores = []
        if dim_temporal >= 0.75:
            factores.append("Concurrencia horaria escolar / laboral")
        if rain_mm >= 10.0:
            factores.append(f"Calzada resbaladiza por lluvia OPAD ({rain_mm} mm/h)")
        if lanes <= 2 and has_bus:
            factores.append("Estrangulamiento de calzada (2 carriles con parada de colectivo)")
        if dim_siniestral >= 0.75:
            factores.append("Concentración histórica de siniestros de motovehículos")

        if not factores:
            factores.append("Tránsito habitual sin fricciones atípicas")

        desvio = None
        if row["node_id"] == "N1_CORRIENTES_TUCUMAN":
            desvio = "Calle San Lorenzo (64% capacidad remanente)"
        elif row["node_id"] == "N4_SAN_MARTIN_ANDRESITO":
            desvio = "Av. Urquiza / Av. Tambor de Tacuarí"

        return EvaluacionNodo(
            nodo_id=str(row["node_id"]),
            nombre=str(row["name"]),
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            riesgo_estructural=riesgo_estructural,
            variacion_escenario=variacion_pct,
            riesgo_final=riesgo_final,
            es_critico=riesgo_final >= 0.65,
            factores=factores,
            desvio_sugerido=desvio
        )


if __name__ == "__main__":
    engine = ExplainableRiskEngine()
    params = ParametrosEscenario(franja_horaria="07:00", precipitacion_mm_h=15.0, dotacion_patrullas=4)
    nodes, ordenes = engine.evaluate_all_nodes(params)
    print(f"Evaluados {len(nodes)} nodos. Órdenes generadas: {len(ordenes)}")
    for o in ordenes:
        print(f"- {o.movil_id} -> {o.nodo_objetivo}: {o.instruccion_tactica}")
