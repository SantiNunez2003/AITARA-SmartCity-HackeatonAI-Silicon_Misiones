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


# Parámetros iniciales definidos por criterio experto, no calibrados.
PESOS = {"temporal": 0.35, "clima": 0.30, "topologia": 0.20, "siniestralidad": 0.15}
LLUVIA_SATURACION_MM_H = 25.0
LLUVIA_HABITUAL_MM_H = 0.0
PESO_ORIGEN = {"real": 1.0, "simulado": 1.0}
ANIOS_EXPOSICION = 3.0
SUAVIZADO_ANIOS = 1.0
# La intensidad suavizada se divide por esta referencia y se limita a [0, 1].
INTENSIDAD_REFERENCIA_ANUAL = 180.0
MAX_EVIDENCIA = 5


class ExplainableRiskEngine:
    def __init__(self, db: DBWrapper = None):
        self.db = db or get_db_connection()
        self._preparar_datos()

    def _preparar_datos(self):
        import pandas as pd
        nodos = self.db.df("SELECT * FROM silver_intersections").to_dict("records")
        incidentes = self.db.df("SELECT * FROM silver_incident_history").to_dict("records")
        grupos = {n["node_id"]: [] for n in nodos}
        for inc in incidentes:
            try:
                lat, lon = float(inc["lat"]), float(inc["lon"])
                if not isfinite(lat) or not isfinite(lon) or not nodos:
                    continue
                nodo = min(nodos, key=lambda n: distancia_metros(lat, lon, n["lat"], n["lon"]))
                if distancia_metros(lat, lon, nodo["lat"], nodo["lon"]) <= DISTANCIA_EVIDENCIA_METROS:
                    grupos[nodo["node_id"]].append(inc)
            except (ValueError, TypeError):
                continue
        intensidades = {}
        for nodo, lista in grupos.items():
            total = 0.0
            for inc in lista:
                try:
                    gravedad, confianza = float(inc["severidad"]), float(inc["confianza"])
                    origen = inc["origen"] if inc["origen"] in PESO_ORIGEN else "real"
                    if isfinite(gravedad) and isfinite(confianza):
                        total += gravedad * confianza * PESO_ORIGEN[origen]
                except (TypeError, ValueError):
                    continue
            intensidades[nodo] = total / ANIOS_EXPOSICION
        media = sum(intensidades.values()) / len(intensidades) if intensidades else 0
        self.db.execute("DELETE FROM gold_node_risk_features")
        self.db.execute("DELETE FROM gold_incident_nodes")
        self.evidencias = {}
        asignaciones = []
        for nodo, lista in grupos.items():
            suavizada = (intensidades[nodo] * ANIOS_EXPOSICION + media * SUAVIZADO_ANIOS) / (ANIOS_EXPOSICION + SUAVIZADO_ANIOS)
            self.db.execute("INSERT INTO gold_node_risk_features VALUES (?, ?, ?)", (nodo, min(1.0, suavizada / INTENSIDAD_REFERENCIA_ANUAL), len(lista)))
            asignaciones.extend((inc["id"], nodo) for inc in lista)
            lista.sort(key=lambda i: (i.get("origen") != "simulado", float(i["severidad"]) if pd.notna(i.get("severidad")) else -1, str(i.get("fecha_evento") or i.get("fecha_publicacion"))), reverse=True)
            self.evidencias[nodo] = lista
        if asignaciones:
            self.db.con.execute("BEGIN TRANSACTION")
            if self.db.use_duckdb:
                self.db.con.register("lote_asignaciones", pd.DataFrame(asignaciones, columns=["incident_id", "node_id"]))
                self.db.con.execute("INSERT INTO gold_incident_nodes SELECT * FROM lote_asignaciones")
                self.db.con.unregister("lote_asignaciones")
            else:
                self.db.con.executemany("INSERT INTO gold_incident_nodes VALUES (?, ?)", asignaciones)
            self.db.con.commit()

    def evaluate_all_nodes(self, params: ParametrosEscenario) -> Tuple[List[EvaluacionNodo], List[Prioridad]]:
        nodos = self.db.df("SELECT i.*, f.intensidad, f.cantidad_incidentes FROM silver_intersections i JOIN gold_node_risk_features f ON i.node_id = f.node_id").to_dict("records")
        partes = params.franja_horaria.split(":")
        hora = int(partes[0]) + int(partes[1]) / 60
        prioridades = []
        for row in nodos:
            escolar = bool(row["is_school_zone"]) and params.actividad_escolar
            temporal = 0.25
            if 6.75 <= hora <= 7.75: temporal = 0.95 if escolar else 0.70
            elif 11.75 <= hora <= 13.25: temporal = 0.90 if escolar else 0.75
            elif 17.25 <= hora <= 18.75: temporal = 0.85 if escolar else 0.80
            clima = max(0.0, min(1.0, params.precipitacion_mm_h / LLUVIA_SATURACION_MM_H))
            carriles = row["lanes"]
            topologia = 0.35 + (0.30 if carriles is not None and carriles <= 2 else 0) + (0.20 if row["has_bus_stop"] else 0)
            intensidad = float(row["intensidad"])
            valores = {"temporal": temporal, "clima": clima, "topologia": topologia, "siniestralidad": intensidad}
            descripciones = {"temporal": f"Franja {params.franja_horaria}; actividad escolar: {'sí' if escolar else 'no'}", "clima": f"Precipitación: {params.precipitacion_mm_h:.2f} mm/h", "topologia": f"Carriles: {carriles if carriles is not None else 'sin dato'}; parada de colectivo: {'sí' if row['has_bus_stop'] else 'no'}", "siniestralidad": f"Intensidad calculada: {intensidad:.3f}; {row['cantidad_incidentes']} incidentes"}
            aportes = [AporteFactor(nombre=k, aporte=valores[k] * PESOS[k], descripcion=descripciones[k]) for k in PESOS]
            riesgo = sum(a.aporte for a in aportes)
            habitual = riesgo - clima * PESOS["clima"] + LLUVIA_HABITUAL_MM_H / LLUVIA_SATURACION_MM_H * PESOS["clima"]
            variacion = (riesgo / habitual - 1) * 100 if habitual else 0.0
            evaluacion = EvaluacionNodo(nodo_id=row["node_id"], nombre=row["name"], lat=row["lat"], lon=row["lon"], riesgo_estructural=intensidad, variacion_escenario=variacion, riesgo_final=riesgo, es_critico=riesgo >= UMBRAL_CRITICO, factores=list(descripciones.values()))
            lista = self.evidencias[row["node_id"]]
            evidencia = []
            for inc in lista[:MAX_EVIDENCIA]:
                fecha = inc.get("fecha_evento")
                if fecha is None or str(fecha) in ("NaT", "nan", ""):
                    fecha = inc["fecha_publicacion"]
                url = inc.get("url")
                if url is None or str(url) in ("nan", "None"): url = None
                evidencia.append(Evidencia(id=str(inc["id"]), fecha=fecha, tipo=str(inc["tipo_incidente"]), fuente=str(inc["fuente"]), url=url, origen="simulado" if inc.get("origen") == "simulado" else "real"))
            real = sum(i.get("origen") != "simulado" for i in lista)
            prioridades.append(Prioridad(nodo=evaluacion, nivel="critico" if evaluacion.es_critico else "no_critico", riesgo_estructural=intensidad, variacion_escenario=variacion, riesgo_escenario=riesgo, aportes=aportes, evidencia=evidencia, total_evidencia=len(lista), evidencia_real=real, evidencia_simulada=len(lista)-real))
        prioridades.sort(key=lambda p: p.riesgo_escenario, reverse=True)
        return [p.nodo for p in prioridades], prioridades
