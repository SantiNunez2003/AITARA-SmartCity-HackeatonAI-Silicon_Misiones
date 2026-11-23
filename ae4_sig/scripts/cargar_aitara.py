"""Carga capas territoriales e incidentes viales de AITARA en PostgreSQL/PostGIS.

Lee en modo solo lectura los archivos fuente del repositorio raíz:
  - data/territorio/calles.json
  - src/warehouse/db.py (nodos expertos vía ast, sin importar duckdb)
  - data/territorio/intersecciones.json
  - data/silver/incidentes_posadas.jsonl
  - data/simulado/incidentes.jsonl
  - data/simulado/exposicion.json

Inserta de forma idempotente en el esquema `sig_ae4` definido en `ae4_sig/sql/00_init.sql`.
"""

from __future__ import annotations

import ast
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values
from shapely.geometry import MultiLineString
from shapely.validation import explain_validity

SIG_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = SIG_DIR / ".env"

CALLES_PATH = REPO_ROOT / "data" / "territorio" / "calles.json"
INTERSECCIONES_PATH = REPO_ROOT / "data" / "territorio" / "intersecciones.json"
WAREHOUSE_DB_PATH = REPO_ROOT / "src" / "warehouse" / "db.py"
INCIDENTES_REAL_PATH = REPO_ROOT / "data" / "silver" / "incidentes_posadas.jsonl"
INCIDENTES_SIM_PATH = REPO_ROOT / "data" / "simulado" / "incidentes.jsonl"
EXPOSICION_PATH = REPO_ROOT / "data" / "simulado" / "exposicion.json"

MAX_SEGMENT_GAP_M = 300.0
MICRO_SEGMENT_HALF_SPAN_DEG = 5e-6  # ~0.5 m por lado (~1 m total) en latitud -27.4


def get_pg_connection() -> psycopg2.extensions.connection:
    """Carga ae4_sig/.env y abre conexión a PostgreSQL."""
    load_dotenv(ENV_PATH)
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        dbname=os.getenv("POSTGRES_DB", "aitara_ae4_sig"),
        user=os.getenv("POSTGRES_USER", "ae4_user"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calcula distancia geodésica aproximada en metros entre dos coordenadas WGS84."""
    earth_radius_m = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    return 2.0 * earth_radius_m * math.asin(math.sqrt(a))


def build_street_multilinestring(street: Dict[str, Any]) -> MultiLineString:
    """Reconstruye un MultiLineString válido desde nodos OSM desordenados.

    `nodos` contiene vértices `[lat, lon, osm_node_id]` provenientes de múltiples
    ways desconectados. Se encadena por vecino más cercano desde un nodo extremo
    cortando en un nuevo tramo cuando el salto supera 300 m.
    """
    seen: set[Tuple[float, float]] = set()
    pts: List[Tuple[float, float]] = []
    for node in street.get("nodos", []):
        pt = (float(node[1]), float(node[0]))  # (lon, lat)
        if pt not in seen:
            seen.add(pt)
            pts.append(pt)

    if not pts:
        pts = [(float(street["lon"]), float(street["lat"]))]

    if len(pts) == 1:
        lon, lat = pts[0]
        segments: List[List[Tuple[float, float]]] = [
            [(lon - MICRO_SEGMENT_HALF_SPAN_DEG, lat), (lon + MICRO_SEGMENT_HALF_SPAN_DEG, lat)]
        ]
    else:
        start_idx = min(range(len(pts)), key=lambda i: (pts[i][0], pts[i][1]))
        unvisited = set(range(len(pts)))
        unvisited.remove(start_idx)
        curr = start_idx
        raw_segments: List[List[Tuple[float, float]]] = [[pts[curr]]]

        while unvisited:
            curr_lon, curr_lat = pts[curr]
            best_idx = min(
                unvisited,
                key=lambda i: haversine_m(curr_lon, curr_lat, pts[i][0], pts[i][1]),
            )
            dist_m = haversine_m(curr_lon, curr_lat, pts[best_idx][0], pts[best_idx][1])
            unvisited.remove(best_idx)

            if dist_m > MAX_SEGMENT_GAP_M:
                raw_segments.append([pts[best_idx]])
            else:
                raw_segments[-1].append(pts[best_idx])
            curr = best_idx

        segments = [seg for seg in raw_segments if len(seg) >= 2]
        if not segments:
            # Si todos los vértices están aislados (>300 m), crear micro-segmentos válidos de ~1 m
            segments = [
                [(lon - MICRO_SEGMENT_HALF_SPAN_DEG, lat), (lon + MICRO_SEGMENT_HALF_SPAN_DEG, lat)]
                for lon, lat in pts
            ]

    geom = MultiLineString(segments)
    if geom.is_empty or not geom.is_valid:
        raise ValueError(
            f"Geometría MultiLineString inválida para calle osm_id={street.get('osm_id')}: "
            f"{explain_validity(geom)}"
        )
    return geom


def extract_reference_nodes_ast(db_py_path: Path) -> List[Tuple[Any, ...]]:
    """Extrae la lista literal de nodos de `seed_reference_data` vía AST sin importar duckdb."""
    source = db_py_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(db_py_path))

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "seed_reference_data":
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    target_names = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
                    if any(name in ("nodes", "intersections") for name in target_names):
                        extracted = ast.literal_eval(stmt.value)
                        if isinstance(extracted, list) and extracted:
                            return [tuple(row) for row in extracted]

    raise RuntimeError(
        f"No se encontró la lista literal de nodos en seed_reference_data dentro de {db_py_path}"
    )


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Lee un archivo JSONL en modo solo lectura ignorando líneas vacías."""
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def load_calles(cur: psycopg2.extensions.cursor) -> int:
    """Carga las 1,286 calles OSM en sig_ae4.calles."""
    calles = json.loads(CALLES_PATH.read_text(encoding="utf-8"))
    rows: List[Tuple[Any, ...]] = []
    for item in calles:
        geom = build_street_multilinestring(item)
        aliases = list(item.get("aliases") or [])
        rows.append(
            (
                int(item["osm_id"]),
                item["nombre_oficial"],
                item["nombre_normalizado"],
                aliases,
                geom.wkt,
            )
        )

    execute_values(
        cur,
        """
        INSERT INTO sig_ae4.calles
            (osm_id, nombre, nombre_normalizado, aliases, geom)
        VALUES %s
        """,
        rows,
        template="(%s, %s, %s, %s::TEXT[], ST_GeomFromText(%s, 4326))",
        page_size=250,
    )
    return len(rows)


def load_nodos_referencia(cur: psycopg2.extensions.cursor) -> int:
    """Carga los 7 nodos de referencia AITARA en sig_ae4.nodos_referencia_aitara."""
    raw_nodes = extract_reference_nodes_ast(WAREHOUSE_DB_PATH)
    rows: List[Tuple[Any, ...]] = []
    for (
        node_id,
        nombre,
        lat,
        lon,
        corridor_type,
        lanes,
        has_traffic_light,
        has_bus_stop,
        is_school_zone,
        school_name,
        nivel_drenaje,
    ) in raw_nodes:
        rows.append(
            (
                node_id,
                nombre,
                corridor_type,
                int(lanes),
                bool(has_traffic_light),
                bool(has_bus_stop),
                bool(is_school_zone),
                school_name,
                nivel_drenaje,
                float(lon),
                float(lat),
            )
        )

    execute_values(
        cur,
        """
        INSERT INTO sig_ae4.nodos_referencia_aitara
            (node_id, nombre, corridor_type, lanes,
             has_traffic_light, has_bus_stop, is_school_zone,
             school_name, nivel_drenaje, geom)
        VALUES %s
        """,
        rows,
        template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))",
    )
    return len(rows)


def load_intersecciones(cur: psycopg2.extensions.cursor) -> Tuple[int, int]:
    """Carga intersecciones OSM y propaga nivel_drenaje desde nodos expertos (<=150 m)."""
    intersecciones = json.loads(INTERSECCIONES_PATH.read_text(encoding="utf-8"))
    rows: List[Tuple[Any, ...]] = []
    for item in intersecciones:
        rows.append(
            (
                int(item["osm_id"]),
                item["nombre_oficial"],
                item["calle_1_oficial"],
                item["calle_2_oficial"],
                item["calle_1_norm"],
                item["calle_2_norm"],
                item["subtipo"],
                float(item["lon"]),
                float(item["lat"]),
            )
        )

    execute_values(
        cur,
        """
        INSERT INTO sig_ae4.intersecciones
            (osm_id, nombre, calle_1, calle_2,
             calle_1_norm, calle_2_norm, subtipo, geom)
        VALUES %s
        ON CONFLICT (calle_1_norm, calle_2_norm)
        DO UPDATE SET osm_id = EXCLUDED.osm_id
        """,
        rows,
        template="(%s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))",
        page_size=500,
    )

    cur.execute(
        """
        UPDATE sig_ae4.intersecciones i
           SET nivel_drenaje = sub.nivel_drenaje
          FROM (
                SELECT DISTINCT ON (i2.id)
                       i2.id,
                       n.nivel_drenaje
                  FROM sig_ae4.intersecciones i2
                  JOIN sig_ae4.nodos_referencia_aitara n
                    ON ST_DWithin(i2.geom_m, n.geom_m, 150.0)
                 ORDER BY i2.id, i2.geom_m <-> n.geom_m
               ) sub
         WHERE i.id = sub.id;
        """
    )
    updated_drainage = cur.rowcount
    return len(rows), updated_drainage


def build_incident_rows(
    records: Sequence[Dict[str, Any]],
    *,
    origen: str,
    force_null_weather: bool,
) -> List[Tuple[Any, ...]]:
    """Prepara tuplas normalizadas para inserción en sig_ae4.incidentes_viales."""
    rows: List[Tuple[Any, ...]] = []
    for rec in records:
        fecha_evento = rec.get("fecha_evento") or rec["fecha_publicacion"]
        nombre = rec["titulo"][:260]
        vehiculos = list(rec.get("vehiculos") or [])
        llovia = None if force_null_weather else rec.get("llovia")
        precipitacion = None if force_null_weather else rec.get("precipitacion_mm_h")
        rows.append(
            (
                rec["id"],
                nombre,
                origen,
                rec["fuente"],
                fecha_evento,
                rec["tipo_incidente"],
                int(rec["severidad"]),
                vehiculos,
                rec.get("ubicacion_texto"),
                llovia,
                precipitacion,
                rec.get("confianza"),
                float(rec["lon"]),
                float(rec["lat"]),
            )
        )
    return rows


def load_incidentes(cur: psycopg2.extensions.cursor) -> int:
    """Carga incidentes reales y simulados; los triggers asignan geom_m e IDs espaciales."""
    reales = read_jsonl(INCIDENTES_REAL_PATH)
    simulados = read_jsonl(INCIDENTES_SIM_PATH)

    rows = build_incident_rows(reales, origen="real", force_null_weather=True)
    rows.extend(build_incident_rows(simulados, origen="simulado", force_null_weather=False))

    execute_values(
        cur,
        """
        INSERT INTO sig_ae4.incidentes_viales
            (id_origen, nombre, origen, fuente, fecha_evento,
             tipo_incidente, severidad, vehiculos, ubicacion_texto,
             llovia, precipitacion_mm_h, confianza, geom)
        VALUES %s
        """,
        rows,
        template="(%s, %s, %s, %s, %s, %s, %s, %s::TEXT[], %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))",
        page_size=250,
    )
    return len(rows)


def load_exposicion_clima(cur: psycopg2.extensions.cursor) -> int:
    """Carga exposición climática ('lluvia' y 'seco') sobre los 7 nodos observados."""
    exposicion = json.loads(EXPOSICION_PATH.read_text(encoding="utf-8"))
    rows = [
        ("lluvia", int(exposicion["lluvia"]), 7),
        ("seco", int(exposicion["seco"]), 7),
    ]
    execute_values(
        cur,
        """
        INSERT INTO sig_ae4.exposicion_clima
            (condicion, horas_nodo_totales, nodos_observados)
        VALUES %s
        """,
        rows,
    )
    return len(rows)


def print_row_counts(cur: psycopg2.extensions.cursor) -> None:
    """Consulta e imprime los conteos exactos cargados en PostgreSQL."""
    queries = [
        ("calles", "SELECT COUNT(*) FROM sig_ae4.calles"),
        ("nodos_referencia_aitara", "SELECT COUNT(*) FROM sig_ae4.nodos_referencia_aitara"),
        ("intersecciones", "SELECT COUNT(*) FROM sig_ae4.intersecciones"),
        (
            "intersecciones (con nivel_drenaje)",
            "SELECT COUNT(*) FROM sig_ae4.intersecciones WHERE nivel_drenaje IS NOT NULL",
        ),
        ("incidentes_viales (total)", "SELECT COUNT(*) FROM sig_ae4.incidentes_viales"),
        (
            "incidentes_viales (real)",
            "SELECT COUNT(*) FROM sig_ae4.incidentes_viales WHERE origen = 'real'",
        ),
        (
            "incidentes_viales (simulado)",
            "SELECT COUNT(*) FROM sig_ae4.incidentes_viales WHERE origen = 'simulado'",
        ),
        (
            "incidentes_viales (con interseccion_id)",
            "SELECT COUNT(*) FROM sig_ae4.incidentes_viales WHERE interseccion_id IS NOT NULL",
        ),
        (
            "incidentes_viales (con nodo_referencia_id)",
            "SELECT COUNT(*) FROM sig_ae4.incidentes_viales WHERE nodo_referencia_id IS NOT NULL",
        ),
        ("exposicion_clima", "SELECT COUNT(*) FROM sig_ae4.exposicion_clima"),
        ("auditoria_ediciones", "SELECT COUNT(*) FROM sig_ae4.auditoria_ediciones"),
    ]
    print("\n=== Conteos verificados en PostgreSQL (sig_ae4) ===")
    for label, sql in queries:
        cur.execute(sql)
        count = cur.fetchone()[0]
        print(f"  {label:<42}: {count}")


def main() -> None:
    conn = get_pg_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    TRUNCATE sig_ae4.incidentes_viales,
                             sig_ae4.intersecciones,
                             sig_ae4.nodos_referencia_aitara,
                             sig_ae4.calles,
                             sig_ae4.exposicion_clima
                    RESTART IDENTITY CASCADE;
                    """
                )

                n_calles = load_calles(cur)
                print(f"[OK] calles procesadas: {n_calles}")

                n_nodos = load_nodos_referencia(cur)
                print(f"[OK] nodos_referencia_aitara insertados: {n_nodos}")

                n_inter, n_drenaje = load_intersecciones(cur)
                print(
                    f"[OK] intersecciones procesadas: {n_inter} "
                    f"(nivel_drenaje propagado en {n_drenaje})"
                )

                n_incidentes = load_incidentes(cur)
                print(f"[OK] incidentes_viales insertados: {n_incidentes}")

                n_expo = load_exposicion_clima(cur)
                print(f"[OK] exposicion_clima insertados: {n_expo}")

                # Limpiar auditoría generada por la carga inicial masiva
                cur.execute("TRUNCATE sig_ae4.auditoria_ediciones RESTART IDENTITY;")
                print_row_counts(cur)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
