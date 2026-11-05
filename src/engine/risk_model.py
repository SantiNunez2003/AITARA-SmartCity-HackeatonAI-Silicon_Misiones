"""AITARA - Explainable AI (XAI) Spatiotemporal Risk Engine.

Evaluates 4 urban mobility dimensions without requiring micro-traffic simulation:
1. Dimensión Temporal y Demanda (Event-Driven)
2. Dimensión Meteorológica de Calzada (Context-Driven)
3. Dimensión Topológica y Capacidad Vial (Network-Driven)
4. Dimensión de Riesgo Siniestral (Safety-Driven)
"""

from dataclasses import dataclass
from typing import Dict, Any, List
import datetime


@dataclass
class NodeEvaluation:
    node_id: str
    name: str
    lat: float
    lon: float
    corridor_type: str
    risk_score: float # 0.0 to 1.0
    risk_level: str   # 'BAJO', 'MEDIO', 'ALTO', 'CRÍTICO'
    dim_temporal: float
    dim_clima: float
    dim_topologia: float
    dim_siniestral: float
    dominant_factor: str
    explanation: str
    dispatch_recommendation: Dict[str, Any]


class ExplainableRiskEngine:
    def __init__(self):
        pass

    def evaluate_node(
        self,
        node_row: Dict[str, Any],
        simulated_time: datetime.time,
        rain_mm_h: float,
        horizon_minutes: int = 30
    ) -> NodeEvaluation:
        # Effective time taking horizon into account
        eval_dt = datetime.datetime.combine(datetime.date.today(), simulated_time) + datetime.timedelta(minutes=horizon_minutes)
        eval_time = eval_dt.time()

        # 1. Dimensión Temporal y Demanda (Event-Driven)
        hour_val = eval_time.hour + eval_time.minute / 60.0
        is_school = node_row.get("is_school_zone", False)

        dim_temporal = 0.2 # baseline
        school_explanation = ""
        # Peak windows: 06:45 - 07:45 (morning school), 12:00 - 13:15 (noon), 17:15 - 18:30 (evening)
        if 6.75 <= hour_val <= 7.75:
            dim_temporal = 0.95 if is_school else 0.70
            school_explanation = "Horario pico escolar matutino (ingreso 07:00-07:30)"
        elif 12.0 <= hour_val <= 13.25:
            dim_temporal = 0.90 if is_school else 0.75
            school_explanation = "Horario pico mediodía (egreso escolar y cambio de turno comercial)"
        elif 17.25 <= hour_val <= 18.5:
            dim_temporal = 0.85 if is_school else 0.80
            school_explanation = "Horario pico vespertino (salida laboral y turno tarde)"
        else:
            dim_temporal = 0.30

        # 2. Dimensión Meteorológica (Context-Driven)
        drainage = node_row.get("drainage_risk_level", "BAJO")
        drain_mult = 1.3 if drainage == "ALTO" else (1.1 if drainage == "MEDIO" else 0.9)
        rain_factor = min(1.0, (rain_mm_h / 25.0)) * drain_mult
        dim_clima = min(1.0, max(0.1, rain_factor))

        # 3. Dimensión Topológica y Capacidad Vial (Network-Driven)
        lanes = node_row.get("lanes", 2)
        has_bus = node_row.get("has_bus_stop", False)
        # Narrow streets with bus stop = higher bottleneck friction
        dim_topologia = 0.4
        if lanes <= 2:
            dim_topologia += 0.3
        if has_bus:
            dim_topologia += 0.2
        dim_topologia = min(1.0, dim_topologia)

        # 4. Dimensión de Riesgo Siniestral (Safety-Driven)
        dim_siniestral = float(node_row.get("historical_incident_score", 0.5))

        # Composite Weighted Risk Score
        # Weights: Temporal (35%), Clima (25%), Topología (20%), Siniestral (20%)
        composite_score = (
            dim_temporal * 0.35 +
            dim_clima * 0.25 +
            dim_topologia * 0.20 +
            dim_siniestral * 0.20
        )
        composite_score = round(min(1.0, max(0.0, composite_score)), 2)

        # Determine Risk Level
        if composite_score >= 0.75:
            risk_level = "CRÍTICO"
        elif composite_score >= 0.55:
            risk_level = "ALTO"
        elif composite_score >= 0.35:
            risk_level = "MEDIO"
        else:
            risk_level = "BAJO"

        # Determine Dominant Factor & Human Explanation (XAI)
        factors = [
            ("Demanda Programada / Escolar", dim_temporal),
            ("Condición Meteorológica / Lluvia", dim_clima),
            ("Capacidad Vial y Fricción de Carril", dim_topologia),
            ("Histórico de Siniestralidad", dim_siniestral),
        ]
        factors.sort(key=lambda x: x[1], reverse=True)
        dominant_factor = factors[0][0]

        reasons = []
        if dim_temporal >= 0.7:
            reasons.append(school_explanation or "Alta concentración horaria de flujo vehicular")
        if rain_mm_h > 5.0:
            reasons.append(f"Calzada resbaladiza por lluvia ({rain_mm_h} mm/h) y drenaje {drainage}")
        if lanes <= 2 and has_bus:
            reasons.append("Estrangulamiento físico (2 carriles con parada de transporte)")
        if dim_siniestral >= 0.7:
            reasons.append("Punto caliente histórico de colisiones reiteradas")

        explanation = " | ".join(reasons) if reasons else "Condiciones normales de circulación."

        # Dispatch Matrix Recommendation
        dispatch = self._compute_dispatch(risk_level, node_row, horizon_minutes)

        return NodeEvaluation(
            node_id=node_row["node_id"],
            name=node_row["name"],
            lat=node_row["lat"],
            lon=node_row["lon"],
            corridor_type=node_row["corridor_type"],
            risk_score=composite_score,
            risk_level=risk_level,
            dim_temporal=round(dim_temporal, 2),
            dim_clima=round(dim_clima, 2),
            dim_topologia=round(dim_topologia, 2),
            dim_siniestral=round(dim_siniestral, 2),
            dominant_factor=dominant_factor,
            explanation=explanation,
            dispatch_recommendation=dispatch
        )

    def _compute_dispatch(self, risk_level: str, node: Dict[str, Any], horizon: int) -> Dict[str, Any]:
        if risk_level == "CRÍTICO":
            return {
                "inspectors_count": 2,
                "motorcycles_count": 1,
                "cones_count": 6,
                "priority": "MÁXIMA (Inmediata)",
                "action": f"Despachar balizamiento preventivo y 2 inspectores para encauzar dársena {horizon} min antes del horario pico.",
                "suggested_diversion": "Habilitar giro asistido hacia arteria paralela si cola excede 80m."
            }
        elif risk_level == "ALTO":
            return {
                "inspectors_count": 1,
                "motorcycles_count": 1,
                "cones_count": 4,
                "priority": "ALTA",
                "action": f"Posicionar móvil de patrulla preventiva {horizon} min antes para disuadir doble fila.",
                "suggested_diversion": "Monitoreo visual continuo."
            }
        elif risk_level == "MEDIO":
            return {
                "inspectors_count": 0,
                "motorcycles_count": 0,
                "cones_count": 0,
                "priority": "MONITOREO",
                "action": "Mantener guardia en Centro de Monitoreo sin requerir desplazamiento de móvil.",
                "suggested_diversion": "Ninguno."
            }
        else:
            return {
                "inspectors_count": 0,
                "motorcycles_count": 0,
                "cones_count": 0,
                "priority": "NORMAL",
                "action": "Sin intervención requerida. Circulación fluida.",
                "suggested_diversion": "Ninguno."
            }
