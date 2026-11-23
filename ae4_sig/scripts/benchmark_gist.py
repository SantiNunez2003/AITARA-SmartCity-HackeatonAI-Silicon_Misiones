"""Benchmark reproducible de índices GiST y trampa geom::geography (AE4 SIG).

Mide con EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) sobre la base PostgreSQL/PostGIS:
  1. Consultas espaciales reales (5 corridas, mediana de Execution Time y buffers):
       - intersecciones × calles: ST_DWithin(i.geom_m, c.geom_m, 30)
       - incidentes_viales × delegaciones: ST_Within(inc.geom_m, d.geom_m)
       - localidades × cursos_agua: KNN <-> mediante CROSS JOIN LATERAL
     Comparando estado Sin GiST (tras DROP INDEX + VACUUM ANALYZE) vs. Con GiST.
  2. Trampa del cast geom::geography en localidades × cursos_agua
     (ST_DWithin(l.geom::geography, r.geom::geography, 200000)):
       - Con solo índice GiST sobre geom (4326) -> Seq Scan
       - Con índice GiST funcional sobre (geom::geography) -> Index Scan
  3. Escalamiento sintético en sig_ae4.bench_puntos_sinteticos (10k, 100k, 1M puntos
     aleatorios en bbox de Posadas) evaluando ST_DWithin(p.geom_m, c.geom_m, 50)
     contra Av. Quaranta (o calle principal de sig_ae4.calles), 5 corridas Sin GiST
     vs. 5 corridas Con GiST + VACUUM ANALYZE.
  4. Limpieza de la tabla temporal y restauración integral de todos los índices
     ejecutando ae4_sig/sql/04_indices_benchmark.sql.

Salidas generadas:
  - ae4_sig/outputs/benchmark_resultados.md
  - ae4_sig/outputs/benchmark_gist_volumen.png
"""

from __future__ import annotations

import json
import os
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import psycopg2
from psycopg2 import sql

AE4_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = AE4_ROOT / ".env"
SQL_INDICES_PATH = AE4_ROOT / "sql" / "04_indices_benchmark.sql"
OUTPUT_DIR = AE4_ROOT / "outputs"
REPORT_PATH = OUTPUT_DIR / "benchmark_resultados.md"
CHART_PATH = OUTPUT_DIR / "benchmark_gist_volumen.png"

ITERATIONS = 5
SYNTHETIC_SCALES = (10_000, 100_000, 1_000_000)

# Posadas bounding box en WGS84 (cubre área urbana y periurbana)
POSADAS_BBOX = {
    "lon_min": -55.96,
    "lon_span": 0.10,
    "lat_min": -27.44,
    "lat_span": 0.10,
}

# Índices temporales creados durante las fases del benchmark
BENCH_GEOM_INDEXES: List[Tuple[str, str, str]] = [
    ("idx_bench_intersecciones_geom_m", "intersecciones", "geom_m"),
    ("idx_bench_calles_geom_m", "calles", "geom_m"),
    ("idx_bench_incidentes_geom_m", "incidentes_viales", "geom_m"),
    ("idx_bench_delegaciones_geom_m", "delegaciones", "geom_m"),
    ("idx_bench_localidades_geom", "localidades", "geom"),
    ("idx_bench_cursos_agua_geom", "cursos_agua", "geom"),
]

BENCH_GEOGRAPHY_INDEXES: List[Tuple[str, str]] = [
    ("idx_bench_localidades_geog", "localidades"),
    ("idx_bench_cursos_agua_geog", "cursos_agua"),
]

# Nombres candidatos estándar por si 04_indices_benchmark.sql ya creó índices GiST
KNOWN_GIST_INDEX_NAMES = [
    "idx_paises_geom",
    "idx_paises_geog",
    "idx_provincias_geom",
    "idx_provincias_geog",
    "idx_departamentos_geom",
    "idx_departamentos_geog",
    "idx_localidades_geom",
    "idx_localidades_geog",
    "idx_cursos_agua_geom",
    "idx_cursos_agua_geog",
    "idx_rutas_geom",
    "idx_rutas_geog",
    "idx_delegaciones_geom",
    "idx_delegaciones_geom_m",
    "idx_semaforos_geom",
    "idx_semaforos_geom_m",
    "idx_escuelas_geom",
    "idx_escuelas_geom_m",
    "idx_paradas_geom",
    "idx_paradas_geom_m",
    "idx_avenidas_mano_unica_geom",
    "idx_avenidas_mano_unica_geom_m",
    "idx_asfalto_sobre_empedrado_geom",
    "idx_asfalto_sobre_empedrado_geom_m",
    "idx_ciclovias_geom",
    "idx_ciclovias_geom_m",
    "idx_calles_geom",
    "idx_calles_geom_m",
    "idx_nodos_referencia_aitara_geom",
    "idx_nodos_referencia_aitara_geom_m",
    "idx_intersecciones_geom",
    "idx_intersecciones_geom_m",
    "idx_incidentes_viales_geom",
    "idx_incidentes_viales_geom_m",
    "idx_bench_puntos_sinteticos_geom_m",
]


@dataclass
class QueryBenchmarkResult:
    """Resumen estadístico de 5 ejecuciones con EXPLAIN (ANALYZE, BUFFERS)."""

    label: str
    scenario: str
    rows_returned: int
    median_ms: float
    min_ms: float
    max_ms: float
    median_hit_blocks: int
    median_read_blocks: int
    plan_summary: str
    raw_times_ms: List[float]


def load_dotenv(env_path: Path) -> None:
    """Carga variables KEY=VALUE desde ae4_sig/.env sin sobrescribir entorno."""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def get_connection() -> psycopg2.extensions.connection:
    """Abre conexión psycopg2 en autocommit usando variables de ae4_sig/.env."""
    load_dotenv(ENV_PATH)
    conn = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5433")),
        dbname=os.environ.get("POSTGRES_DB", "aitara_ae4_sig"),
        user=os.environ.get("POSTGRES_USER", "ae4_user"),
        password=os.environ.get("POSTGRES_PASSWORD", "ae4_sig_2026_local"),
    )
    conn.autocommit = True
    return conn


def list_sig_gist_indexes(cur: psycopg2.extensions.cursor) -> List[Tuple[str, str]]:
    """Lista todos los índices GiST actuales en el esquema sig_ae4."""
    cur.execute(
        """
        SELECT indexname, indexdef
          FROM pg_indexes
         WHERE schemaname = 'sig_ae4'
           AND indexdef ~* 'USING\\s+gist'
         ORDER BY indexname;
        """
    )
    return [(row[0], row[1]) for row in cur.fetchall()]


def drop_all_gist_indexes(cur: psycopg2.extensions.cursor) -> None:
    """Elimina temporalmente todos los índices GiST del esquema sig_ae4."""
    discovered = {name for name, _ in list_sig_gist_indexes(cur)}
    candidates = sorted(
        discovered
        | set(KNOWN_GIST_INDEX_NAMES)
        | {name for name, _, _ in BENCH_GEOM_INDEXES}
        | {name for name, _ in BENCH_GEOGRAPHY_INDEXES}
    )
    for idx_name in candidates:
        cur.execute(
            sql.SQL("DROP INDEX IF EXISTS sig_ae4.{};").format(sql.Identifier(idx_name))
        )

    remaining = list_sig_gist_indexes(cur)
    if remaining:
        raise RuntimeError(f"Quedaron índices GiST sin eliminar: {remaining}")


def run_vacuum_analyze(cur: psycopg2.extensions.cursor, tables: Sequence[str] | None = None) -> None:
    """Ejecuta VACUUM ANALYZE global o sobre una lista de tablas en sig_ae4."""
    if not tables:
        cur.execute("VACUUM ANALYZE;")
        return
    for tbl in tables:
        cur.execute(
            sql.SQL("VACUUM ANALYZE sig_ae4.{};").format(sql.Identifier(tbl))
        )


def describe_plan(plan_node: Dict[str, Any]) -> str:
    """Resume de forma compacta los operadores e índices de un árbol EXPLAIN JSON."""
    parts: List[str] = []

    def _walk(node: Dict[str, Any]) -> None:
        node_type = node.get("Node Type", "Unknown")
        idx_name = node.get("Index Name")
        rel_name = node.get("Relation Name")
        if idx_name:
            label = f"{node_type} ({idx_name})"
        elif rel_name:
            label = f"{node_type} ({rel_name})"
        else:
            label = node_type
        if label not in parts:
            parts.append(label)
        for child in node.get("Plans", []):
            _walk(child)

    _walk(plan_node)
    return " -> ".join(parts)


def explain_once(
    cur: psycopg2.extensions.cursor,
    query: str,
    params: Sequence[Any] | None = None,
) -> Tuple[float, int, int, int, str]:
    """Ejecuta EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) y extrae métricas."""
    explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
    cur.execute(explain_sql, params)
    payload = cur.fetchone()[0]
    if isinstance(payload, str):
        payload = json.loads(payload)
    root = payload[0]
    plan = root["Plan"]
    exec_ms = float(root["Execution Time"])
    actual_rows = int(plan.get("Actual Rows", 0))
    hit_blocks = int(plan.get("Shared Hit Blocks", 0))
    read_blocks = int(plan.get("Shared Read Blocks", 0))
    summary = describe_plan(plan)
    return exec_ms, actual_rows, hit_blocks, read_blocks, summary


def benchmark_query(
    cur: psycopg2.extensions.cursor,
    label: str,
    scenario: str,
    query: str,
    params: Sequence[Any] | None = None,
    iterations: int = ITERATIONS,
) -> QueryBenchmarkResult:
    """Ejecuta `iterations` corridas de una consulta y calcula medianas."""
    times: List[float] = []
    hits: List[int] = []
    reads: List[int] = []
    rows_list: List[int] = []
    summaries: List[str] = []

    for _ in range(iterations):
        exec_ms, actual_rows, hit_b, read_b, summary = explain_once(cur, query, params)
        times.append(exec_ms)
        hits.append(hit_b)
        reads.append(read_b)
        rows_list.append(actual_rows)
        summaries.append(summary)

    median_ms = float(statistics.median(times))
    # Tomar el plan del último run (estable tras warm-up / estadísticas vigentes)
    return QueryBenchmarkResult(
        label=label,
        scenario=scenario,
        rows_returned=rows_list[-1],
        median_ms=median_ms,
        min_ms=min(times),
        max_ms=max(times),
        median_hit_blocks=int(statistics.median(hits)),
        median_read_blocks=int(statistics.median(reads)),
        plan_summary=summaries[-1],
        raw_times_ms=times,
    )


def create_benchmark_geom_indexes(cur: psycopg2.extensions.cursor) -> None:
    """Crea índices GiST geométricos (sin índices funcionales geography)."""
    for idx_name, table_name, col_name in BENCH_GEOM_INDEXES:
        cur.execute(
            sql.SQL("CREATE INDEX IF NOT EXISTS {} ON sig_ae4.{} USING GIST ({});").format(
                sql.Identifier(idx_name),
                sql.Identifier(table_name),
                sql.Identifier(col_name),
            )
        )


def create_benchmark_geography_indexes(cur: psycopg2.extensions.cursor) -> None:
    """Crea índices GiST funcionales sobre (geom::geography)."""
    for idx_name, table_name in BENCH_GEOGRAPHY_INDEXES:
        cur.execute(
            sql.SQL(
                "CREATE INDEX IF NOT EXISTS {} ON sig_ae4.{} USING GIST ((geom::geography));"
            ).format(
                sql.Identifier(idx_name),
                sql.Identifier(table_name),
            )
        )


def pick_target_street(cur: psycopg2.extensions.cursor) -> Tuple[int, str]:
    """Selecciona Av. Quaranta o la calle más extensa disponible en sig_ae4.calles."""
    cur.execute(
        """
        SELECT id, nombre
          FROM sig_ae4.calles
         WHERE geom_m IS NOT NULL
           AND (nombre_normalizado ILIKE '%QUARANTA%' OR nombre ILIKE '%Quaranta%')
         ORDER BY ST_Length(geom_m) DESC, id ASC
         LIMIT 1;
        """
    )
    row = cur.fetchone()
    if row:
        return int(row[0]), str(row[1])

    cur.execute(
        """
        SELECT id, nombre
          FROM sig_ae4.calles
         WHERE geom_m IS NOT NULL
         ORDER BY ST_Length(geom_m) DESC, id ASC
         LIMIT 1;
        """
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("No existen calles con geom_m en sig_ae4.calles para el benchmark sintético.")
    return int(row[0]), str(row[1])


def populate_synthetic_points(cur: psycopg2.extensions.cursor, n_points: int) -> None:
    """Crea sig_ae4.bench_puntos_sinteticos con n_points puntos en Posadas (EPSG:5348)."""
    cur.execute("DROP TABLE IF EXISTS sig_ae4.bench_puntos_sinteticos;")
    cur.execute(
        """
        CREATE TABLE sig_ae4.bench_puntos_sinteticos (
            id     INTEGER PRIMARY KEY,
            geom_m GEOMETRY(Point, 5348) NOT NULL
        );
        """
    )
    cur.execute("SELECT setseed(0.42);")
    cur.execute(
        """
        INSERT INTO sig_ae4.bench_puntos_sinteticos (id, geom_m)
        SELECT gs,
               ST_Transform(
                   ST_SetSRID(
                       ST_MakePoint(
                           %s + random() * %s,
                           %s + random() * %s
                       ),
                       4326
                   ),
                   5348
               )
          FROM generate_series(1, %s) AS gs;
        """,
        (
            POSADAS_BBOX["lon_min"],
            POSADAS_BBOX["lon_span"],
            POSADAS_BBOX["lat_min"],
            POSADAS_BBOX["lat_span"],
            n_points,
        ),
    )


def strip_sql_comments(stmt: str) -> str:
    """Elimina comentarios SQL (-- y /* */) para detectar sentencias vacías."""
    no_block = re.sub(r"/\*.*?\*/", "", stmt, flags=re.DOTALL)
    no_line = re.sub(r"--[^\n]*", "", no_block)
    return no_line.strip()


def split_sql_statements(sql_text: str) -> List[str]:
    """Divide un script SQL en sentencias respetando comillas, $$ y comentarios."""
    # Filtrar metacomandos de psql (\echo, \pset, etc.)
    cleaned_lines = [
        line for line in sql_text.splitlines() if not line.lstrip().startswith("\\")
    ]
    text = "\n".join(cleaned_lines)

    statements: List[str] = []
    buf: List[str] = []
    i = 0
    n = len(text)
    in_single = False
    in_double = False
    in_line_comment = False
    block_comment_depth = 0
    dollar_tag: str | None = None
    dollar_re = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$")

    while i < n:
        ch = text[i]
        nxt = text[i : i + 2]

        if in_line_comment:
            buf.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if block_comment_depth > 0:
            if nxt == "/*":
                buf.append(nxt)
                block_comment_depth += 1
                i += 2
            elif nxt == "*/":
                buf.append(nxt)
                block_comment_depth -= 1
                i += 2
            else:
                buf.append(ch)
                i += 1
            continue

        if dollar_tag is not None:
            if text.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
            else:
                buf.append(ch)
                i += 1
            continue

        if in_single:
            buf.append(ch)
            if ch == "'":
                if nxt == "''":
                    buf.append("'")
                    i += 2
                else:
                    in_single = False
                    i += 1
            else:
                i += 1
            continue

        if in_double:
            buf.append(ch)
            if ch == '"':
                if nxt == '""':
                    buf.append('"')
                    i += 2
                else:
                    in_double = False
                    i += 1
            else:
                i += 1
            continue

        # Estado normal
        if nxt == "--":
            buf.append(nxt)
            in_line_comment = True
            i += 2
        elif nxt == "/*":
            buf.append(nxt)
            block_comment_depth = 1
            i += 2
        elif ch == "'":
            buf.append(ch)
            in_single = True
            i += 1
        elif ch == '"':
            buf.append(ch)
            in_double = True
            i += 1
        elif ch == "$":
            m = dollar_re.match(text, i)
            if m:
                dollar_tag = m.group(0)
                buf.append(dollar_tag)
                i += len(dollar_tag)
            else:
                buf.append(ch)
                i += 1
        elif ch == ";":
            stmt = "".join(buf).strip()
            if strip_sql_comments(stmt):
                statements.append(stmt)
            buf = []
            i += 1
        else:
            buf.append(ch)
            i += 1

    tail = "".join(buf).strip()
    if strip_sql_comments(tail):
        statements.append(tail)

    return statements


def restore_all_gist_indexes(cur: psycopg2.extensions.cursor) -> int:
    """Restaura todos los índices ejecutando ae4_sig/sql/04_indices_benchmark.sql."""
    cur.execute("DROP TABLE IF EXISTS sig_ae4.bench_puntos_sinteticos;")
    drop_all_gist_indexes(cur)

    if not SQL_INDICES_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró el script de restauración de índices: {SQL_INDICES_PATH}"
        )

    sql_text = SQL_INDICES_PATH.read_text(encoding="utf-8")
    for stmt in split_sql_statements(sql_text):
        cur.execute(stmt)

    restored = list_sig_gist_indexes(cur)
    return len(restored)


def get_env_metadata(cur: psycopg2.extensions.cursor) -> Dict[str, Any]:
    """Obtiene versión PostgreSQL/PostGIS y conteos reales de tablas evaluadas."""
    cur.execute("SELECT version(), PostGIS_Full_Version();")
    pg_ver, postgis_ver = cur.fetchone()

    tables = [
        "intersecciones",
        "calles",
        "incidentes_viales",
        "delegaciones",
        "localidades",
        "cursos_agua",
    ]
    counts: Dict[str, int] = {}
    for tbl in tables:
        cur.execute(sql.SQL("SELECT COUNT(*) FROM sig_ae4.{};").format(sql.Identifier(tbl)))
        counts[tbl] = int(cur.fetchone()[0])

    return {
        "pg_version": pg_ver,
        "postgis_version": postgis_ver,
        "counts": counts,
    }


def format_speedup(without_ms: float, with_ms: float) -> str:
    if with_ms <= 0:
        return "N/A"
    return f"{without_ms / with_ms:.2f}×"


def write_markdown_report(
    meta: Dict[str, Any],
    real_pairs: List[Tuple[QueryBenchmarkResult, QueryBenchmarkResult]],
    geog_no_func: QueryBenchmarkResult,
    geog_with_func: QueryBenchmarkResult,
    synthetic_pairs: List[Tuple[int, QueryBenchmarkResult, QueryBenchmarkResult]],
    street_id: int,
    street_name: str,
    restored_index_count: int,
) -> None:
    """Escribe el reporte técnico en ae4_sig/outputs/benchmark_resultados.md."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines: List[str] = [
        "# Benchmark Espacial GiST & Geography — AE4 SIG",
        "",
        f"- **Fecha de ejecución**: `{ts}`",
        f"- **PostgreSQL**: `{meta['pg_version'].split(' on ')[0]}`",
        f"- **PostGIS**: `{meta['postgis_version'].split(' USE_GEOS')[0]}`",
        f"- **Iteraciones por escenario**: `{ITERATIONS}` (reportando la **mediana** de `Execution Time` y buffers desde `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`)",
        f"- **Índices GiST restaurados al finalizar (`04_indices_benchmark.sql`)**: `{restored_index_count}`",
        "",
        "## Conteos de tablas evaluadas",
        "",
        "| Tabla (`sig_ae4`) | Registros |",
        "| --- | ---: |",
    ]
    for tbl, cnt in meta["counts"].items():
        lines.append(f"| `{tbl}` | {cnt:,} |")

    lines.extend(
        [
            "",
            "## 1. Consultas espaciales reales: Sin GiST vs. Con GiST",
            "",
            "| Consulta | Filas | Sin GiST (ms) | Con GiST (ms) | Speedup | Buffers Sin GiST (hit / read) | Buffers Con GiST (hit / read) | Plan observado (Sin → Con) |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for res_sin, res_con in real_pairs:
        speedup = format_speedup(res_sin.median_ms, res_con.median_ms)
        buf_sin = f"{res_sin.median_hit_blocks:,} / {res_sin.median_read_blocks:,}"
        buf_con = f"{res_con.median_hit_blocks:,} / {res_con.median_read_blocks:,}"
        lines.append(
            f"| {res_sin.label} | {res_con.rows_returned:,} | "
            f"{res_sin.median_ms:.3f} | {res_con.median_ms:.3f} | **{speedup}** | "
            f"{buf_sin} | {buf_con} | `{res_sin.plan_summary}` → `{res_con.plan_summary}` |"
        )

    geog_speedup = format_speedup(geog_no_func.median_ms, geog_with_func.median_ms)
    lines.extend(
        [
            "",
            "## 2. Trampa del cast `geom::geography` (`localidades × cursos_agua`, `ST_DWithin(..., 200000)`)",
            "",
            "Un índice GiST estándar sobre `geom` (tipo `geometry`, SRID 4326) **no** es utilizable cuando la consulta castea en tiempo de ejecución a `geom::geography`; se requiere un índice funcional `USING GIST ((geom::geography))`.",
            "",
            "| Escenario | Filas | Mediana (ms) | Min / Max (ms) | Buffers (hit / read) | Plan observado |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
            (
                f"| {geog_no_func.scenario} | {geog_no_func.rows_returned:,} | "
                f"{geog_no_func.median_ms:.3f} | {geog_no_func.min_ms:.3f} / {geog_no_func.max_ms:.3f} | "
                f"{geog_no_func.median_hit_blocks:,} / {geog_no_func.median_read_blocks:,} | "
                f"`{geog_no_func.plan_summary}` |"
            ),
            (
                f"| {geog_with_func.scenario} | {geog_with_func.rows_returned:,} | "
                f"{geog_with_func.median_ms:.3f} | {geog_with_func.min_ms:.3f} / {geog_with_func.max_ms:.3f} | "
                f"{geog_with_func.median_hit_blocks:,} / {geog_with_func.median_read_blocks:,} | "
                f"`{geog_with_func.plan_summary}` |"
            ),
            "",
            f"- **Speedup al crear el índice funcional `(geom::geography)`**: **{geog_speedup}**.",
            "",
            f"## 3. Escalamiento sintético (`sig_ae4.bench_puntos_sinteticos` × `{street_name}` [id={street_id}], `ST_DWithin(..., 50)`)",
            "",
            "| Puntos sintéticos | Coincidencias (≤50 m) | Sin GiST (ms) | Con GiST (ms) | Speedup | Buffers Sin GiST (hit / read) | Buffers Con GiST (hit / read) |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for n_pts, res_sin, res_con in synthetic_pairs:
        speedup = format_speedup(res_sin.median_ms, res_con.median_ms)
        buf_sin = f"{res_sin.median_hit_blocks:,} / {res_sin.median_read_blocks:,}"
        buf_con = f"{res_con.median_hit_blocks:,} / {res_con.median_read_blocks:,}"
        lines.append(
            f"| {n_pts:,} | {res_con.rows_returned:,} | "
            f"{res_sin.median_ms:.3f} | {res_con.median_ms:.3f} | **{speedup}** | "
            f"{buf_sin} | {buf_con} |"
        )

    lines.extend(
        [
            "",
            "![Escalamiento GiST en puntos sintéticos](benchmark_gist_volumen.png)",
            "",
        ]
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def generate_scaling_chart(
    synthetic_pairs: List[Tuple[int, QueryBenchmarkResult, QueryBenchmarkResult]],
    street_name: str,
) -> None:
    """Genera gráfico comparativo Sin GiST vs. Con GiST para 10k, 100k y 1M puntos."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    labels = [f"{n:,}".replace(",", ".") + "\npuntos" for n, _, _ in synthetic_pairs]
    sin_times = [max(res_sin.median_ms, 0.001) for _, res_sin, _ in synthetic_pairs]
    con_times = [max(res_con.median_ms, 0.001) for _, _, res_con in synthetic_pairs]

    x = list(range(len(labels)))
    width = 0.36

    fig, ax = plt.subplots(figsize=(9.5, 5.6), dpi=180)
    bars_sin = ax.bar(
        [xi - width / 2 for xi in x],
        sin_times,
        width=width,
        label="Sin índice GiST (Seq Scan)",
        color="#D95F02",
        edgecolor="#8C3B00",
        linewidth=0.8,
        zorder=3,
    )
    bars_con = ax.bar(
        [xi + width / 2 for xi in x],
        con_times,
        width=width,
        label="Con índice GiST (Index / Bitmap Scan)",
        color="#1B9E77",
        edgecolor="#0E5A43",
        linewidth=0.8,
        zorder=3,
    )

    ax.set_yscale("log")
    max_y = max(sin_times + con_times)
    min_y = min(sin_times + con_times)
    ax.set_ylim(max(0.05, min_y * 0.45), max_y * 5.0)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10, fontweight="bold")
    ax.set_ylabel("Tiempo de ejecución — mediana de 5 corridas (ms, escala log)", fontsize=10)
    ax.set_title(
        "Escalamiento espacial: ST_DWithin(geom_m, calle, 50 m) — Sin GiST vs. Con GiST",
        fontsize=12,
        fontweight="bold",
        pad=18,
    )
    ax.text(
        0.5,
        1.02,
        f"Posadas (EPSG:5348) · Calle objetivo: {street_name} · Puntos sintéticos en sig_ae4.bench_puntos_sinteticos",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=8.8,
        color="#444444",
    )

    ax.grid(axis="y", which="major", linestyle="--", alpha=0.45, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper left", frameon=True, framealpha=0.95)

    for idx, (b_sin, b_con) in enumerate(zip(bars_sin, bars_con)):
        v_sin = sin_times[idx]
        v_con = con_times[idx]
        ax.annotate(
            f"{v_sin:.2f} ms",
            xy=(b_sin.get_x() + b_sin.get_width() / 2, v_sin),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
            color="#8C3B00",
        )
        ax.annotate(
            f"{v_con:.2f} ms",
            xy=(b_con.get_x() + b_con.get_width() / 2, v_con),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
            color="#0E5A43",
        )
        speedup = v_sin / v_con if v_con > 0 else 0.0
        top_pair = max(v_sin, v_con)
        ax.annotate(
            f"Speedup: {speedup:.1f}×",
            xy=(x[idx], top_pair),
            xytext=(0, 22),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="#1F2937",
            bbox={"boxstyle": "round,pad=0.25", "fc": "#EEF2FF", "ec": "#6366F1", "lw": 0.8},
        )

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    """Orquesta el benchmark completo y garantiza la restauración de índices GiST."""
    real_queries: List[Tuple[str, str]] = [
        (
            "1) intersecciones × calles (`ST_DWithin(..., 30 m)`)",
            """
            SELECT i.id AS interseccion_id,
                   i.nombre AS interseccion,
                   c.id AS calle_id,
                   c.nombre AS calle,
                   ST_Distance(i.geom_m, c.geom_m) AS dist_m
              FROM sig_ae4.intersecciones AS i
              JOIN sig_ae4.calles AS c
                ON ST_DWithin(i.geom_m, c.geom_m, 30.0)
            """,
        ),
        (
            "2) incidentes_viales × delegaciones (`ST_Within`)",
            """
            SELECT inc.id AS incidente_id,
                   inc.tipo_incidente,
                   d.id AS delegacion_id,
                   d.nombre AS delegacion
              FROM sig_ae4.incidentes_viales AS inc
              JOIN sig_ae4.delegaciones AS d
                ON ST_Within(inc.geom_m, d.geom_m)
            """,
        ),
        (
            "3) localidades × cursos_agua (KNN `<->` `CROSS JOIN LATERAL`)",
            """
            SELECT l.id AS localidad_id,
                   l.nombre AS localidad,
                   r.id AS curso_agua_id,
                   r.nombre AS curso_agua,
                   r.dist_deg
              FROM sig_ae4.localidades AS l
             CROSS JOIN LATERAL (
                   SELECT c.id,
                          c.nombre,
                          c.geom <-> l.geom AS dist_deg
                     FROM sig_ae4.cursos_agua AS c
                    ORDER BY c.geom <-> l.geom
                    LIMIT 1
             ) AS r
            """,
        ),
    ]

    geog_pitfall_query = """
        SELECT l.id AS localidad_id,
               l.nombre AS localidad,
               r.id AS curso_agua_id,
               r.nombre AS curso_agua
          FROM sig_ae4.localidades AS l
          JOIN sig_ae4.cursos_agua AS r
            ON ST_DWithin(l.geom::geography, r.geom::geography, 200000)
    """

    conn = get_connection()
    restored_count = 0
    try:
        with conn.cursor() as cur:
            meta = get_env_metadata(cur)
            print("[1/5] Eliminando índices GiST temporalmente y ejecutando VACUUM ANALYZE...")
            drop_all_gist_indexes(cur)
            run_vacuum_analyze(cur)

            print("[2/5] Midiendo consultas reales SIN GiST (5 corridas c/u)...")
            sin_results: List[QueryBenchmarkResult] = []
            for label, qry in real_queries:
                res = benchmark_query(cur, label, "Sin GiST", qry)
                sin_results.append(res)
                print(f"  - {label}: {res.median_ms:.3f} ms [{res.plan_summary}]")

            print("[3/5] Creando índices GiST geométricos y midiendo CON GiST...")
            create_benchmark_geom_indexes(cur)
            run_vacuum_analyze(
                cur,
                [
                    "intersecciones",
                    "calles",
                    "incidentes_viales",
                    "delegaciones",
                    "localidades",
                    "cursos_agua",
                ],
            )
            con_results: List[QueryBenchmarkResult] = []
            for label, qry in real_queries:
                res = benchmark_query(cur, label, "Con GiST", qry)
                con_results.append(res)
                print(f"  - {label}: {res.median_ms:.3f} ms [{res.plan_summary}]")

            print("[4/5] Midiendo trampa geom::geography (solo GiST geom vs. funcional geography)...")
            geog_no_func = benchmark_query(
                cur,
                "localidades × cursos_agua (geography)",
                "Solo índice GiST en `geom` (4326)",
                geog_pitfall_query,
            )
            print(f"  - Sin índice funcional: {geog_no_func.median_ms:.3f} ms [{geog_no_func.plan_summary}]")

            create_benchmark_geography_indexes(cur)
            run_vacuum_analyze(cur, ["localidades", "cursos_agua"])
            geog_with_func = benchmark_query(
                cur,
                "localidades × cursos_agua (geography)",
                "Con índice GiST funcional `(geom::geography)`",
                geog_pitfall_query,
            )
            print(f"  - Con índice funcional: {geog_with_func.median_ms:.3f} ms [{geog_with_func.plan_summary}]")

            print("[5/5] Ejecutando benchmark sintético (10k, 100k, 1M puntos)...")
            street_id, street_name = pick_target_street(cur)
            synthetic_query = """
                SELECT p.id
                  FROM sig_ae4.bench_puntos_sinteticos AS p
                  JOIN sig_ae4.calles AS c
                    ON c.id = %s
                   AND ST_DWithin(p.geom_m, c.geom_m, 50.0)
            """
            synthetic_pairs: List[Tuple[int, QueryBenchmarkResult, QueryBenchmarkResult]] = []

            for n_pts in SYNTHETIC_SCALES:
                populate_synthetic_points(cur, n_pts)
                run_vacuum_analyze(cur, ["bench_puntos_sinteticos"])
                res_sin = benchmark_query(
                    cur,
                    f"Sintético {n_pts:,}",
                    "Sin GiST",
                    synthetic_query,
                    params=(street_id,),
                )

                cur.execute(
                    "CREATE INDEX idx_bench_puntos_sinteticos_geom_m "
                    "ON sig_ae4.bench_puntos_sinteticos USING GIST (geom_m);"
                )
                run_vacuum_analyze(cur, ["bench_puntos_sinteticos"])
                res_con = benchmark_query(
                    cur,
                    f"Sintético {n_pts:,}",
                    "Con GiST",
                    synthetic_query,
                    params=(street_id,),
                )
                synthetic_pairs.append((n_pts, res_sin, res_con))
                print(
                    f"  - {n_pts:>10,} pts -> Sin GiST: {res_sin.median_ms:.3f} ms | "
                    f"Con GiST: {res_con.median_ms:.3f} ms "
                    f"({format_speedup(res_sin.median_ms, res_con.median_ms)})"
                )
    finally:
        with conn.cursor() as cur_cleanup:
            print("[Limpieza] Eliminando tabla sintética y restaurando índices desde 04_indices_benchmark.sql...")
            restored_count = restore_all_gist_indexes(cur_cleanup)
        conn.close()

    real_pairs = list(zip(sin_results, con_results))
    write_markdown_report(
        meta=meta,
        real_pairs=real_pairs,
        geog_no_func=geog_no_func,
        geog_with_func=geog_with_func,
        synthetic_pairs=synthetic_pairs,
        street_id=street_id,
        street_name=street_name,
        restored_index_count=restored_count,
    )
    generate_scaling_chart(synthetic_pairs, street_name)

    print(f"[OK] Reporte guardado en: {REPORT_PATH}")
    print(f"[OK] Gráfico guardado en: {CHART_PATH}")
    print(f"[OK] Índices GiST activos en sig_ae4: {restored_count}")


if __name__ == "__main__":
    main()
