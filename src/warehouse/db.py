"""AITARA - Data Warehouse Engine.

Maintains Bronze (Raw Lake), Silver (Normalized/Validated), and Gold (Analytical / Feature Store).
Supports DuckDB when installed, with seamless built-in SQLite fallback.
"""

from pathlib import Path
import sqlite3
import pandas as pd

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False

DB_PATH_DUCKDB = Path(__file__).resolve().parent.parent.parent / "data" / "aitara.duckdb"
DB_PATH_SQLITE = Path(__file__).resolve().parent.parent.parent / "data" / "aitara.sqlite"


class DBWrapper:
    def __init__(self, use_duckdb: bool = HAS_DUCKDB):
        self.use_duckdb = use_duckdb
        if self.use_duckdb:
            DB_PATH_DUCKDB.parent.mkdir(parents=True, exist_ok=True)
            self.con = duckdb.connect(str(DB_PATH_DUCKDB))
        else:
            DB_PATH_SQLITE.parent.mkdir(parents=True, exist_ok=True)
            self.con = sqlite3.connect(str(DB_PATH_SQLITE))

    def execute(self, query: str, params: tuple = ()):
        if self.use_duckdb:
            return self.con.execute(query, params)
        else:
            cur = self.con.cursor()
            # Replace 'INSERT OR REPLACE INTO' standard SQLite
            cur.execute(query, params)
            self.con.commit()
            return cur

    def df(self, query: str) -> pd.DataFrame:
        if self.use_duckdb:
            return self.con.execute(query).df()
        else:
            return pd.read_sql_query(query, self.con)


def get_db_connection() -> DBWrapper:
    return DBWrapper()


def init_schema(db: DBWrapper) -> None:
    """Initialize Bronze, Silver, and Gold relational tables."""
    # Bronze: Raw extracted JSON-like payloads
    db.execute("""
        CREATE TABLE IF NOT EXISTS bronze_raw_events (
            event_id TEXT PRIMARY KEY,
            source TEXT,
            payload_json TEXT,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Silver: Clean, structured entities
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

    db.execute("""
        CREATE TABLE IF NOT EXISTS silver_incident_history (
            incident_id TEXT PRIMARY KEY,
            node_id TEXT,
            source TEXT,
            incident_date TIMESTAMP,
            severity TEXT,
            vehicle_type TEXT,
            description TEXT
        );
    """)

    # Gold: Features for real-time inference (Aggregated spatiotemporal risk factors)
    db.execute("""
        CREATE TABLE IF NOT EXISTS gold_node_risk_features (
            node_id TEXT PRIMARY KEY,
            base_capacity_veh_hour INTEGER,
            historical_incident_score REAL,
            school_vulnerability_weight REAL,
            rain_sensitivity_factor REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)


def seed_reference_data(db: DBWrapper) -> None:
    """Seed verified Posadas nodes and historical incident baselines."""
    intersections = [
        ("N1_CORRIENTES_TUCUMAN", "Av. Corrientes y Tucumán", -27.3695, -55.8952, "ESCOLAR", 2, 1, 1, 1, "Colegio San Basilio Magno", "ALTO"),
        ("N2_QUARANTA_JAURETCHE", "Av. Quaranta y Av. Jauretche", -27.4042, -55.9325, "ACCESO_PERIFERICO", 4, 1, 0, 0, None, "MEDIO"),
        ("N3_URUGUAY_MITRE", "Av. Uruguay y Av. Mitre", -27.3731, -55.9015, "TRONCAL", 4, 1, 1, 0, None, "BAJO"),
        ("N4_LAVALLE_TACUARI", "Av. Lavalle y Av. Tambor de Tacuarí", -27.3820, -55.9180, "TRONCAL", 2, 1, 1, 1, "Escuela N° 42", "MEDIO"),
        ("N5_RADEMACHER_MONTEAGUDO", "Av. Rademacher y Av. Monteagudo", -27.3885, -55.9080, "TRONCAL", 3, 1, 0, 0, None, "BAJO"),
    ]

    for node in intersections:
        db.execute("""
            INSERT OR REPLACE INTO silver_intersections 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, node)

    gold_features = [
        ("N1_CORRIENTES_TUCUMAN", 1200, 0.78, 0.95, 0.85),
        ("N2_QUARANTA_JAURETCHE", 2800, 0.90, 0.10, 0.70),
        ("N3_URUGUAY_MITRE", 3200, 0.65, 0.20, 0.40),
        ("N4_LAVALLE_TACUARI", 1400, 0.55, 0.80, 0.60),
        ("N5_RADEMACHER_MONTEAGUDO", 2200, 0.40, 0.15, 0.35),
    ]

    for feat in gold_features:
        db.execute("""
            INSERT OR REPLACE INTO gold_node_risk_features (node_id, base_capacity_veh_hour, historical_incident_score, school_vulnerability_weight, rain_sensitivity_factor)
            VALUES (?, ?, ?, ?, ?);
        """, feat)


if __name__ == "__main__":
    db = get_db_connection()
    init_schema(db)
    seed_reference_data(db)
    print(f"Database initialized and seeded successfully (Engine: {'DuckDB' if db.use_duckdb else 'SQLite'}).")

