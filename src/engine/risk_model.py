"""AITARA - Explainable AI (XAI) Spatiotemporal Risk Engine.

Implements the 4-dimensional risk model from Joaquín's technical specification:
1. Dimensión Temporal y Demanda (Event-Driven)
2. Dimensión Meteorológica de Calzada (Context-Driven)
3. Dimensión Topológica y Capacidad Vial (Network-Driven - IDE Posadas)
4. Dimensión de Riesgo Siniestral (Safety-Driven - Lector News History)

Calculates:
- Riesgo Estructural (Línea base histórica)
- Variación por Escenario (Cociente vs día habitual)
- Prioridades y evidencia
"""

from typing import List, Any, Tuple
from math import radians, sin, cos, asin, sqrt, isfinite

from src.contracts import EvaluacionNodo, ParametrosEscenario, Prioridad, AporteFactor, Evidencia
from src.warehouse.db import get_db_connection, DBWrapper


UMBRAL_CRITICO = 0.65
DISTANCIA_EVIDENCIA_METROS = 500
RADIO_TIERRA_METROS = 6371000


def distancia_metros(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * RADIO_TIERRA_METROS * asin(min(1, sqrt(a)))


class ExplainableRiskEngine:
    def __init__(self, db: DBWrapper = None):
        self.db = db or get_db_connection()

    def evaluate_all_nodes(self, params: ParametrosEscenario) -> Tuple[List[EvaluacionNodo], List[Prioridad]]:
        """Eval?a nodos y devuelve prioridades ordenadas por riesgo."""
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
        prioridades = []

        # Parse requested hour (e.g. '07:00' -> 7.0)
        try:
            parts = params.franja_horaria.split(":")
            hour_float = float(parts[0]) + float(parts[1]) / 60.0
        except Exception:
            hour_float = 7.0

        for _, row in df_nodes.iterrows():
            eval_node, aportes = self._evaluate_single_node(row, hour_float, params)
            evaluations.append(eval_node)
            prioridades.append(Prioridad(nodo=eval_node, nivel="critico" if eval_node.es_critico else "no_critico", riesgo_estructural=eval_node.riesgo_estructural, variacion_escenario=eval_node.variacion_escenario, riesgo_escenario=eval_node.riesgo_final, aportes=aportes, evidencia=[]))

        # Sort by final risk descending
        evaluations.sort(key=lambda x: x.riesgo_final, reverse=True)

        prioridades.sort(key=lambda x: x.riesgo_escenario, reverse=True)
        incidentes = self.db.df("SELECT * FROM silver_incident_history")
        for _, incidente in incidentes.iterrows():
            try:
                lat, lon = float(incidente["lat"]), float(incidente["lon"])
                if not isfinite(lat) or not isfinite(lon):
                    continue
                prioridad = min(prioridades, key=lambda p: distancia_metros(lat, lon, p.nodo.lat, p.nodo.lon))
                if distancia_metros(lat, lon, prioridad.nodo.lat, prioridad.nodo.lon) > DISTANCIA_EVIDENCIA_METROS:
                    continue
                fecha = incidente.get("fecha_evento")
                if fecha is None or str(fecha) in ("NaT", "nan", ""):
                    fecha = incidente["fecha_publicacion"]
                url = incidente.get("url")
                if url is None or str(url) in ("nan", "None"):
                    url = None
                origen = incidente.get("origen")
                if origen is None or str(origen) in ("nan", "None", ""):
                    origen = "real"
                prioridad.evidencia.append(Evidencia(id=str(incidente["id"]), fecha=fecha, tipo=str(incidente["tipo_incidente"]), fuente=str(incidente["fuente"]), url=url, origen=origen))
            except (TypeError, ValueError):
                continue
        return evaluations, prioridades

    def _evaluate_single_node(self, row: Any, hour_float: float, params: ParametrosEscenario) -> Tuple[EvaluacionNodo, List[AporteFactor]]:
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

        aportes = [
            AporteFactor(nombre="temporal", aporte=dim_temporal * 0.35, descripcion=f"Franja {params.franja_horaria}; actividad escolar: {is_school}; dimensi?n {dim_temporal:.2f}"),
            AporteFactor(nombre="clima", aporte=dim_clima * 0.30, descripcion=f"Precipitaci?n ingresada: {rain_mm} mm/h; drenaje: {drainage}; dimensi?n {dim_clima:.2f}"),
            AporteFactor(nombre="topologia", aporte=dim_topologia * 0.20, descripcion=f"Carriles: {lanes}; parada de colectivo: {has_bus}; dimensi?n {dim_topologia:.2f}"),
            AporteFactor(nombre="siniestralidad", aporte=dim_siniestral * 0.15, descripcion=f"Puntaje hist?rico: {dim_siniestral:.2f}"),
        ]
        factores = [a.descripcion for a in aportes]
        evaluacion = EvaluacionNodo(
            nodo_id=str(row["node_id"]), nombre=str(row["name"]),
            lat=float(row["lat"]), lon=float(row["lon"]),
            riesgo_estructural=riesgo_estructural, variacion_escenario=variacion_pct,
            riesgo_final=riesgo_final, es_critico=riesgo_final >= UMBRAL_CRITICO,
            factores=factores,
        )
        return evaluacion, aportes
