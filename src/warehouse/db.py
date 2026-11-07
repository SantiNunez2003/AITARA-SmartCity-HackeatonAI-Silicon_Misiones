"""AITARA - Data Warehouse & Persistence Engine.

Maintains Bronze (Raw Lake), Silver (Normalized/Curated), and Gold (Analytical / Feature Store).
Supports DuckDB with automatic SQLite fallback.
Includes offline dataset loader and pipeline status monitoring.
"""

from pathlib import Path
import json
import sqlite3
import threading
import pandas as pd
from typing import Dict, Any, List

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH_DUCKDB = BASE_DIR / "data" / "aitara.duckdb"
DB_PATH_SQLITE = BASE_DIR / "data" / "aitara.sqlite"
SIMULADO_JSONL_PATH = BASE_DIR / "data" / "simulado" / "incidentes.jsonl"
SILVER_JSONL_PATH = BASE_DIR / "data" / "silver" / "incidentes_posadas.jsonl"


class DBWrapper:
    def __init__(self, use_duckdb: bool = HAS_DUCKDB):
        self.use_duckdb = use_duckdb
        self._lock = threading.RLock()
        if self.use_duckdb:
            DB_PATH_DUCKDB.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.con = duckdb.connect(str(DB_PATH_DUCKDB))
            except Exception:
                # Si otro proceso (ej. Streamlit activo) tiene el lock de archivo en Windows, usar instancia in-memory resiliente
                self.con = duckdb.connect(":memory:")
        else:
            DB_PATH_SQLITE.parent.mkdir(parents=True, exist_ok=True)
            self.con = sqlite3.connect(str(DB_PATH_SQLITE), check_same_thread=False)

    def execute(self, query: str, params: tuple = ()):
        if self.use_duckdb:
            return self.con.cursor().execute(query, params)
        else:
            with self._lock:
                cur = self.con.cursor()
                cur.execute(query, params)
                self.con.commit()
                return cur

    def df(self, query: str, params: tuple = ()) -> pd.DataFrame:
        if self.use_duckdb:
            return self.con.cursor().execute(query, params).df()
        else:
            with self._lock:
                return pd.read_sql_query(query, self.con, params=params if params else None)


def get_db_connection() -> DBWrapper:
    return DBWrapper()


def init_schema(db: DBWrapper) -> None:
    """Initialize Bronze, Silver, and Gold tables."""
    # Bronze: Raw incoming events
    db.execute("""
        CREATE TABLE IF NOT EXISTS bronze_raw_events (
            event_id TEXT PRIMARY KEY,
            source TEXT,
            payload_json TEXT,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Silver: Clean, structured intersections
    db.execute("""
        CREATE TABLE IF NOT EXISTS silver_intersections (
            node_id TEXT PRIMARY KEY,
            name TEXT,
            lat REAL,
            lon REAL,
            corridor_type TEXT,
            lanes INTEGER,
            has_traffic_light BOOLEAN,
            has_bus_stop BOOLEAN,
            is_school_zone BOOLEAN,
            school_name TEXT,
            drainage_risk_level TEXT
        );
    """)

    # Silver: Normalized incident history (from Lector / Scraper)
    db.execute("""
        CREATE TABLE IF NOT EXISTS silver_incident_history (
            id TEXT PRIMARY KEY,
            fuente TEXT,
            titulo TEXT,
            url TEXT,
            fecha_publicacion TIMESTAMP,
            fecha_evento TIMESTAMP,
            tipo_incidente TEXT,
            severidad INTEGER,
            vehiculos TEXT,
            calle_1 TEXT,
            calle_2 TEXT,
            ubicacion_texto TEXT,
            lat REAL,
            lon REAL,
            confianza REAL,
            resumen TEXT,
            origen TEXT,
            llovia BOOLEAN,
            precipitacion_mm_h DOUBLE
        );
    """)
    try:
        db.execute("ALTER TABLE silver_incident_history ADD COLUMN fecha_evento TIMESTAMP;")
    except Exception:
        pass

    try:
        db.execute("ALTER TABLE silver_incident_history ADD COLUMN origen TEXT;")
    except Exception:
        pass

    for columna, tipo in (("llovia", "BOOLEAN"), ("precipitacion_mm_h", "DOUBLE")):
        try:
            db.execute(f"ALTER TABLE silver_incident_history ADD COLUMN {columna} {tipo}")
        except Exception:
            pass

    # La tabla anterior contenía atributos sin fuente; se reemplaza al iniciar.
    db.execute("DROP TABLE IF EXISTS gold_node_risk_features")
    db.execute("""CREATE TABLE gold_node_risk_features (
        node_id TEXT PRIMARY KEY, intensidad REAL, cantidad_incidentes INTEGER
    )""")
    db.execute("DROP TABLE IF EXISTS gold_incident_nodes")
    db.execute("CREATE TABLE gold_incident_nodes (incident_id TEXT PRIMARY KEY, node_id TEXT)")


def seed_reference_data(db: DBWrapper) -> None:
    """Carga los nodos de referencia de Posadas con sus atributos territoriales."""
    intersections = [
        ("N1_CORRIENTES_TUCUMAN", "Av. Corrientes y Tucumán", -27.372758, -55.901911, "ESCOLAR", 2, 1, 1, 1, "Colegio San Basilio Magno", "ALTO"),
        ("N2_ROTONDA_URUGUAY", "Rotonda Av. Uruguay y Quaranta", -27.403800, -55.902800, "ACCESO_TRONCAL", 4, 1, 1, 0, None, "MEDIO"),
        ("N3_QUARANTA_GUIDO", "Av. Quaranta y Tomás Guido", -27.401150, -55.917214, "TRAVESIA_URBANA", 4, 1, 0, 0, None, "BAJO"),
        ("N4_SAN_MARTIN_ANDRESITO", "Av. San Martín y Av. Andresito", -27.397231, -55.920662, "CUENCA_BAJA", 2, 0, 1, 0, None, "ALTO"),
        ("N5_CABRED_LOPEZ_TORRES", "Av. Cabred y Av. López Torres", -27.385123, -55.892459, "SANITARIO_HOSPITAL", 2, 1, 1, 0, "Hospital Madariaga", "BAJO"),
        ("N6_CENTENARIO_LAVALLE", "Av. Centenario y Av. Lavalle", -27.365137, -55.904835, "MANO_UNICA_TRANSPORTE", 3, 1, 1, 0, None, "MEDIO"),
        ("N7_URQUIZA_SAN_MARTIN", "Av. Urquiza y Av. San Martín", -27.358844, -55.915393, "COSTANERA_CONEXION", 3, 1, 0, 0, None, "BAJO"),
    ]

    for node in intersections:
        db.execute("""
            INSERT OR REPLACE INTO silver_intersections 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, node)



def load_silver_incidents_from_jsonl(db: DBWrapper) -> int:
    """Loads curated incidents from data/silver/incidentes_posadas.jsonl into DuckDB/SQLite."""
    rows = []
    for path in (SILVER_JSONL_PATH, SIMULADO_JSONL_PATH):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                rows.append((item.get("id"), item.get("fuente"), item.get("titulo"), item.get("url"),
                    item.get("fecha_publicacion"), item.get("fecha_evento") or item.get("fecha_publicacion"),
                    item.get("tipo_incidente"), item.get("severidad"), ", ".join(item.get("vehiculos", [])),
                    item.get("calle_1"), item.get("calle_2"), item.get("ubicacion_texto"), item.get("lat"),
                    item.get("lon"), item.get("confianza"), item.get("resumen"), item.get("origen", "real"), item.get("llovia"), item.get("precipitacion_mm_h")))
    query = """INSERT OR REPLACE INTO silver_incident_history
        (id, fuente, titulo, url, fecha_publicacion, fecha_evento, tipo_incidente, severidad,
         vehiculos, calle_1, calle_2, ubicacion_texto, lat, lon, confianza, resumen, origen, llovia, precipitacion_mm_h)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
    with db._lock:
        db.con.execute("BEGIN TRANSACTION")
        try:
            if db.use_duckdb and rows:
                columnas = ["id", "fuente", "titulo", "url", "fecha_publicacion", "fecha_evento", "tipo_incidente", "severidad", "vehiculos", "calle_1", "calle_2", "ubicacion_texto", "lat", "lon", "confianza", "resumen", "origen", "llovia", "precipitacion_mm_h"]
                db.con.register("lote_incidentes", pd.DataFrame(rows, columns=columnas))
                db.con.execute(f"INSERT OR REPLACE INTO silver_incident_history ({', '.join(columnas)}) SELECT {', '.join(columnas)} FROM lote_incidentes")
                db.con.unregister("lote_incidentes")
            else:
                db.con.executemany(query, rows)
            db.con.commit()
        except Exception:
            db.con.rollback()
            raise
    return len(rows)


def get_pipeline_status(db: DBWrapper) -> Dict[str, Any]:
    """Returns the operational status of the data pipeline for offline/online monitoring."""
    try:
        incident_count = db.df("SELECT COUNT(*) as c FROM silver_incident_history")["c"][0]
    except Exception:
        incident_count = 0

    try:
        node_count = db.df("SELECT COUNT(*) as c FROM silver_intersections")["c"][0]
    except Exception:
        node_count = 0

    try:
        fuentes = db.df("SELECT DISTINCT fuente FROM silver_incident_history WHERE fuente IS NOT NULL AND TRIM(fuente) <> '' ORDER BY fuente")["fuente"].tolist()
    except Exception:
        fuentes = []

    return {
        "total_incidentes": int(incident_count),
        "incidentes_por_origen": {str(r.origen): int(r.c) for r in db.df("SELECT COALESCE(origen, 'real') AS origen, COUNT(*) AS c FROM silver_incident_history GROUP BY 1").itertuples()},
        "total_nodos_monitoreados": int(node_count),
        "fuentes_activas": fuentes,
    }


def get_all_incidents(db: DBWrapper) -> pd.DataFrame:
    """Fetch all curated incidents for visualization."""
    try:
        return db.df("SELECT * FROM silver_incident_history ORDER BY fecha_publicacion DESC")
    except Exception as e:
        print("Error fetching incidents:", e)
        return pd.DataFrame()


if __name__ == "__main__":
    db = get_db_connection()
    init_schema(db)
    seed_reference_data(db)
    loaded = load_silver_incidents_from_jsonl(db)
    status = get_pipeline_status(db)
    print(f"Base de datos lista. Incidentes cargados: {loaded}. Estado: {status}")
