"""Carga capas externas IGN, Natural Earth e IDE Posadas hacia PostGIS.

Flujo de ingesta:
  1. Lee variables de conexión desde `ae4_sig/.env`.
  2. Crea/recrea las 14 tablas `staging.*` y carga todos los GeoJSON de
     `ae4_sig/datos_externos/` almacenando `geom_json` como texto crudo.
  3. Extrae `ide_delegaciones_shp.zip` hacia `datos_externos/ide_delegaciones_shp/`
     e ingesta `staging.ide_delegaciones_shp_demo` vía `shp2pgsql` (por `docker exec`
     sobre `ae4_postgis` o binario local como respaldo).
  4. Ejecuta `ae4_sig/sql/01_cargar_staging_a_final.sql` para validar, limpiar y
     normalizar geometrías/atributos hacia el esquema productivo `sig_ae4.*`.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence, Tuple

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

SIG_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = SIG_DIR / ".env"
DATOS_DIR = SIG_DIR / "datos_externos"
SQL_NORMALIZAR_PATH = SIG_DIR / "sql" / "01_cargar_staging_a_final.sql"
SHP_ZIP_PATH = DATOS_DIR / "ide_delegaciones_shp.zip"
SHP_EXTRACT_DIR = DATOS_DIR / "ide_delegaciones_shp"
DEFAULT_CONTAINER = "ae4_postgis"


@dataclass(frozen=True)
class GeoJsonSource:
    """Archivo GeoJSON origen junto con un tag opcional (ej. jurisdicción vial)."""

    filename: str
    tag: str = ""


@dataclass(frozen=True)
class StagingLayerSpec:
    """Definición declarativa de una tabla `staging.*` y su extractor de filas."""

    table: str
    columns_ddl: str
    insert_cols: Tuple[str, ...]
    sources: Tuple[GeoJsonSource, ...]
    extractor: Callable[[Dict[str, Any], str], Tuple[Any, ...]]


def get_pg_connection() -> psycopg2.extensions.connection:
    """Carga `ae4_sig/.env` y abre conexión a PostgreSQL."""
    load_dotenv(ENV_PATH)
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        dbname=os.getenv("POSTGRES_DB", "aitara_ae4_sig"),
        user=os.getenv("POSTGRES_USER", "ae4_user"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def to_clean_str(value: Any) -> str | None:
    """Convierte valores JSON a string limpio preservando enteros serializados como float."""
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text if text else None


def to_int_or_none(value: Any) -> int | None:
    """Convierte valores numéricos o strings numéricos a entero seguro."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(round(value))
    text = str(value).strip()
    return int(float(text)) if text else None


def serialize_geom_json(feature: Dict[str, Any], source_name: str) -> str:
    """Serializa la geometría GeoJSON de un feature para convertirla luego en SQL."""
    geom = feature.get("geometry")
    if not geom:
        raise ValueError(f"Feature sin geometría en {source_name}: id={feature.get('id')}")
    return json.dumps(geom, ensure_ascii=False)


def build_staging_specs() -> List[StagingLayerSpec]:
    """Retorna el catálogo completo de capas GeoJSON hacia `staging.*`."""

    def extract_ne_paises(feat: Dict[str, Any], src: str) -> Tuple[Any, ...]:
        props = feat.get("properties", {})
        return (
            to_clean_str(props.get("ISO_A3")),
            to_clean_str(props.get("ADMIN")),
            to_clean_str(props.get("SUBREGION")),
            to_int_or_none(props.get("POP_EST")),
            serialize_geom_json(feat, src),
        )

    def extract_ign_admin(feat: Dict[str, Any], src: str) -> Tuple[Any, ...]:
        props = feat.get("properties", {})
        return (
            to_clean_str(props.get("in1")),
            to_clean_str(props.get("nam")),
            to_clean_str(props.get("fna")),
            serialize_geom_json(feat, src),
        )

    def extract_ign_localidades(feat: Dict[str, Any], src: str) -> Tuple[Any, ...]:
        props = feat.get("properties", {})
        return (
            to_clean_str(props.get("cod_ase")),
            to_clean_str(props.get("fna")),
            to_clean_str(props.get("tipo_asent")),
            to_clean_str(props.get("cod_pcia")),
            to_clean_str(props.get("cod_depto")),
            serialize_geom_json(feat, src),
        )

    def extract_ign_cursos_agua(feat: Dict[str, Any], src: str) -> Tuple[Any, ...]:
        props = feat.get("properties", {})
        return (
            to_clean_str(props.get("gid")),
            to_clean_str(props.get("fna")),
            to_clean_str(props.get("nam")),
            to_clean_str(props.get("gna")),
            to_clean_str(props.get("objeto")),
            bool(props.get("_es_principal", False)),
            serialize_geom_json(feat, src),
        )

    def extract_ign_rutas(feat: Dict[str, Any], jurisdiccion: str) -> Tuple[Any, ...]:
        props = feat.get("properties", {})
        prefix = "nac" if jurisdiccion == "nacional" else "prov"
        gid = to_clean_str(props.get("gid")) or to_clean_str(feat.get("id"))
        return (
            f"{prefix}_{gid}",
            to_clean_str(props.get("rtn")),
            jurisdiccion,
            to_int_or_none(props.get("rst")),
            serialize_geom_json(feat, jurisdiccion),
        )

    def extract_ide_delegaciones(feat: Dict[str, Any], src: str) -> Tuple[Any, ...]:
        props = feat.get("properties", {})
        return (
            to_clean_str(feat.get("id")),
            to_clean_str(props.get("Layer")),
            to_clean_str(props.get("Text")),
            serialize_geom_json(feat, src),
        )

    def extract_ide_semaforos(feat: Dict[str, Any], src: str) -> Tuple[Any, ...]:
        props = feat.get("properties", {})
        return (
            to_clean_str(feat.get("id")),
            to_clean_str(props.get("Calle_Avenida1")),
            to_clean_str(props.get("Calle_Avenida2")),
            to_clean_str(props.get("Estado")),
            to_clean_str(props.get("Centralizado")),
            to_clean_str(props.get("Peatonales")),
            serialize_geom_json(feat, src),
        )

    def extract_ide_escuelas(feat: Dict[str, Any], src: str) -> Tuple[Any, ...]:
        props = feat.get("properties", {})
        return (
            to_clean_str(feat.get("id")),
            to_clean_str(props.get("cueanexo")),
            to_clean_str(props.get("nombre")),
            to_clean_str(props.get("nombrecort")),
            to_clean_str(props.get("sector")),
            to_clean_str(props.get("calle")),
            to_clean_str(props.get("barrio")),
            serialize_geom_json(feat, src),
        )

    def extract_ide_paradas(feat: Dict[str, Any], src: str) -> Tuple[Any, ...]:
        props = feat.get("properties", {})
        return (
            to_clean_str(feat.get("id")),
            to_clean_str(props.get("codigo")),
            to_clean_str(props.get("Ubicaci_n")),
            to_clean_str(props.get("ubi_calle")),
            to_clean_str(props.get("ubi_casi")),
            to_clean_str(props.get("barrio")),
            to_clean_str(props.get("Activo")),
            to_clean_str(props.get("darsena")),
            serialize_geom_json(feat, src),
        )

    def extract_ide_manos_unicas(feat: Dict[str, Any], src: str) -> Tuple[Any, ...]:
        props = feat.get("properties", {})
        return (
            to_clean_str(feat.get("id")),
            to_clean_str(props.get("NOMB_")),
            to_clean_str(props.get("SENTIDO")),
            to_clean_str(props.get("vigente")),
            serialize_geom_json(feat, src),
        )

    def extract_ide_asfalto(feat: Dict[str, Any], src: str) -> Tuple[Any, ...]:
        props = feat.get("properties", {})
        return (
            to_clean_str(feat.get("id")),
            to_clean_str(props.get("nombre")),
            to_clean_str(props.get("ano")),
            to_clean_str(props.get("tipo_obra")),
            serialize_geom_json(feat, src),
        )

    def extract_ide_ciclovias(feat: Dict[str, Any], src: str) -> Tuple[Any, ...]:
        props = feat.get("properties", {})
        return (
            to_clean_str(feat.get("id")),
            to_clean_str(props.get("Nombre")),
            to_clean_str(props.get("Tramo")),
            to_clean_str(props.get("A_o")),
            serialize_geom_json(feat, src),
        )

    def extract_ide_radios_censales(feat: Dict[str, Any], src: str) -> Tuple[Any, ...]:
        props = feat.get("properties", {})
        return (
            to_clean_str(feat.get("id")),
            to_clean_str(props.get("LINK")),
            to_int_or_none(props.get("poblacion_n")),
            serialize_geom_json(feat, src),
        )

    return [
        StagingLayerSpec(
            table="staging.ne_paises",
            columns_ddl="codigo_iso3 TEXT, nombre TEXT, subregion TEXT, poblacion BIGINT, geom_json TEXT NOT NULL",
            insert_cols=("codigo_iso3", "nombre", "subregion", "poblacion", "geom_json"),
            sources=(GeoJsonSource("ne_paises_sudamerica.geojson"),),
            extractor=extract_ne_paises,
        ),
        StagingLayerSpec(
            table="staging.ign_provincias",
            columns_ddl="in1 TEXT, nam TEXT, fna TEXT, geom_json TEXT NOT NULL",
            insert_cols=("in1", "nam", "fna", "geom_json"),
            sources=(GeoJsonSource("ign_provincias.geojson"),),
            extractor=extract_ign_admin,
        ),
        StagingLayerSpec(
            table="staging.ign_departamentos",
            columns_ddl="in1 TEXT, nam TEXT, fna TEXT, geom_json TEXT NOT NULL",
            insert_cols=("in1", "nam", "fna", "geom_json"),
            sources=(GeoJsonSource("ign_departamentos.geojson"),),
            extractor=extract_ign_admin,
        ),
        StagingLayerSpec(
            table="staging.ign_localidades",
            columns_ddl="cod_ase TEXT, fna TEXT, tipo_asent TEXT, cod_pcia TEXT, cod_depto TEXT, geom_json TEXT NOT NULL",
            insert_cols=("cod_ase", "fna", "tipo_asent", "cod_pcia", "cod_depto", "geom_json"),
            sources=(GeoJsonSource("ign_localidades.geojson"),),
            extractor=extract_ign_localidades,
        ),
        StagingLayerSpec(
            table="staging.ign_cursos_agua",
            columns_ddl="gid TEXT, fna TEXT, nam TEXT, gna TEXT, objeto TEXT, es_principal BOOLEAN, geom_json TEXT NOT NULL",
            insert_cols=("gid", "fna", "nam", "gna", "objeto", "es_principal", "geom_json"),
            sources=(GeoJsonSource("ign_cursos_agua.geojson"),),
            extractor=extract_ign_cursos_agua,
        ),
        StagingLayerSpec(
            table="staging.ign_rutas",
            columns_ddl="id_origen TEXT, numero_ruta TEXT, jurisdiccion TEXT, superficie_calzada INTEGER, geom_json TEXT NOT NULL",
            insert_cols=("id_origen", "numero_ruta", "jurisdiccion", "superficie_calzada", "geom_json"),
            sources=(
                GeoJsonSource("ign_vial_nacional.geojson", tag="nacional"),
                GeoJsonSource("ign_vial_provincial.geojson", tag="provincial"),
            ),
            extractor=extract_ign_rutas,
        ),
        StagingLayerSpec(
            table="staging.ide_delegaciones",
            columns_ddl="id_ide TEXT, nombre TEXT, descripcion TEXT, geom_json TEXT NOT NULL",
            insert_cols=("id_ide", "nombre", "descripcion", "geom_json"),
            sources=(GeoJsonSource("ide_delegaciones.geojson"),),
            extractor=extract_ide_delegaciones,
        ),
        StagingLayerSpec(
            table="staging.ide_semaforos",
            columns_ddl="id_ide TEXT, calle_1 TEXT, calle_2 TEXT, estado TEXT, centralizado TEXT, peatonales TEXT, geom_json TEXT NOT NULL",
            insert_cols=("id_ide", "calle_1", "calle_2", "estado", "centralizado", "peatonales", "geom_json"),
            sources=(GeoJsonSource("ide_semaforos.geojson"),),
            extractor=extract_ide_semaforos,
        ),
        StagingLayerSpec(
            table="staging.ide_escuelas",
            columns_ddl="id_ide TEXT, cueanexo TEXT, nombre TEXT, nombrecort TEXT, sector TEXT, calle TEXT, barrio TEXT, geom_json TEXT NOT NULL",
            insert_cols=("id_ide", "cueanexo", "nombre", "nombrecort", "sector", "calle", "barrio", "geom_json"),
            sources=(GeoJsonSource("ide_escuelas.geojson"),),
            extractor=extract_ide_escuelas,
        ),
        StagingLayerSpec(
            table="staging.ide_paradas",
            columns_ddl="id_ide TEXT, codigo TEXT, ubicacion TEXT, ubi_calle TEXT, ubi_casi TEXT, barrio TEXT, activo TEXT, darsena TEXT, geom_json TEXT NOT NULL",
            insert_cols=("id_ide", "codigo", "ubicacion", "ubi_calle", "ubi_casi", "barrio", "activo", "darsena", "geom_json"),
            sources=(GeoJsonSource("ide_paradas.geojson"),),
            extractor=extract_ide_paradas,
        ),
        StagingLayerSpec(
            table="staging.ide_manos_unicas",
            columns_ddl="id_ide TEXT, nombre TEXT, sentido TEXT, vigente TEXT, geom_json TEXT NOT NULL",
            insert_cols=("id_ide", "nombre", "sentido", "vigente", "geom_json"),
            sources=(GeoJsonSource("ide_manos_unicas.geojson"),),
            extractor=extract_ide_manos_unicas,
        ),
        StagingLayerSpec(
            table="staging.ide_asfalto",
            columns_ddl="id_ide TEXT, nombre TEXT, anio TEXT, tipo_obra TEXT, geom_json TEXT NOT NULL",
            insert_cols=("id_ide", "nombre", "anio", "tipo_obra", "geom_json"),
            sources=(GeoJsonSource("ide_asfalto_sobre_empedrado.geojson"),),
            extractor=extract_ide_asfalto,
        ),
        StagingLayerSpec(
            table="staging.ide_ciclovias",
            columns_ddl="id_ide TEXT, nombre TEXT, tramo TEXT, anio TEXT, geom_json TEXT NOT NULL",
            insert_cols=("id_ide", "nombre", "tramo", "anio", "geom_json"),
            sources=(GeoJsonSource("ide_ciclovias.geojson"),),
            extractor=extract_ide_ciclovias,
        ),
        StagingLayerSpec(
            table="staging.ide_radios_censales",
            columns_ddl="id_ide TEXT, link TEXT, poblacion_n INTEGER, geom_json TEXT NOT NULL",
            insert_cols=("id_ide", "link", "poblacion_n", "geom_json"),
            sources=(GeoJsonSource("ide_radios_censales_2022.geojson"),),
            extractor=extract_ide_radios_censales,
        ),
    ]


def load_geojson_layer(cur: psycopg2.extensions.cursor, spec: StagingLayerSpec) -> int:
    """Recrea una tabla `staging.*` y carga sus archivos GeoJSON origen."""
    cur.execute(f"DROP TABLE IF EXISTS {spec.table} CASCADE;")
    cur.execute(f"CREATE TABLE {spec.table} ({spec.columns_ddl});")

    rows: List[Tuple[Any, ...]] = []
    for src in spec.sources:
        path = DATOS_DIR / src.filename
        if not path.exists():
            raise FileNotFoundError(f"Archivo GeoJSON requerido no encontrado: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        tag = src.tag or src.filename
        for feat in payload.get("features", []):
            rows.append(spec.extractor(feat, tag))

    cols_sql = ", ".join(spec.insert_cols)
    execute_values(
        cur,
        f"INSERT INTO {spec.table} ({cols_sql}) VALUES %s",
        rows,
        page_size=500,
    )
    return len(rows)


def run_shp2pgsql_command(shp_file: Path, container_name: str | None) -> Tuple[str, str]:
    """Genera SQL desde un Shapefile usando `shp2pgsql` vía Docker o binario local."""
    target_table = "staging.ide_delegaciones_shp_demo"
    candidates: List[Tuple[str, Sequence[str]]] = []

    if container_name:
        container_shp = f"/datos_externos/ide_delegaciones_shp/{shp_file.name}"
        candidates.append(
            (
                f"docker exec {container_name} shp2pgsql",
                [
                    "docker",
                    "exec",
                    container_name,
                    "shp2pgsql",
                    "-I",
                    "-s",
                    "4326",
                    "-c",
                    "-W",
                    "UTF-8",
                    container_shp,
                    target_table,
                ],
            )
        )

    local_bin = shutil.which("shp2pgsql")
    if local_bin:
        candidates.append(
            (
                "shp2pgsql local",
                [
                    local_bin,
                    "-I",
                    "-s",
                    "4326",
                    "-c",
                    "-W",
                    "UTF-8",
                    str(shp_file),
                    target_table,
                ],
            )
        )

    errors: List[str] = []
    for label, cmd in candidates:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
        except OSError as exc:
            errors.append(f"{label}: {exc}")
            continue

        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.lstrip("\ufeff"), label
        stderr = (proc.stderr or "").strip()
        errors.append(f"{label} (exit={proc.returncode}): {stderr}")

    raise RuntimeError(" | ".join(errors) if errors else "No hay ejecutable shp2pgsql disponible.")


def load_delegaciones_shp_demo(
    conn: psycopg2.extensions.connection,
    container_name: str | None,
) -> bool:
    """Extrae `ide_delegaciones_shp.zip` y carga evidencia en `staging.ide_delegaciones_shp_demo`."""
    if not SHP_ZIP_PATH.exists():
        print(f"[WARN] No se encontró {SHP_ZIP_PATH}; se omite demo shp2pgsql.")
        return False

    SHP_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(SHP_ZIP_PATH, "r") as zf:
        zf.extractall(SHP_EXTRACT_DIR)

    preferred = SHP_EXTRACT_DIR / "DELEGACIONES_MUNICIPALES_POSADAS_20250.shp"
    shp_file = preferred if preferred.exists() else next(SHP_EXTRACT_DIR.glob("*.shp"), None)
    if shp_file is None:
        print(f"[WARN] No se encontró ningún .shp dentro de {SHP_EXTRACT_DIR}.")
        return False

    with conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS staging.ide_delegaciones_shp_demo CASCADE;")

    try:
        shp_sql, method = run_shp2pgsql_command(shp_file, container_name)
    except RuntimeError as exc:
        print(f"[WARN] No se pudo ejecutar shp2pgsql ({exc}). Se continúa con GeoJSON.")
        return False

    # shp2pgsql emite transacciones propias (BEGIN/COMMIT), por lo que requiere autocommit
    prev_autocommit = conn.autocommit
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(shp_sql)
            cur.execute("SELECT COUNT(*) FROM staging.ide_delegaciones_shp_demo;")
            count = cur.fetchone()[0]
    finally:
        conn.autocommit = prev_autocommit

    print(f"[OK] staging.ide_delegaciones_shp_demo ({method}): {count} filas")
    return True


def print_final_counts(cur: psycopg2.extensions.cursor) -> None:
    """Consulta e imprime los conteos cargados en `sig_ae4` tras normalizar."""
    tables = [
        "paises",
        "provincias",
        "departamentos",
        "localidades",
        "cursos_agua",
        "rutas",
        "delegaciones",
        "semaforos",
        "escuelas",
        "paradas",
        "avenidas_mano_unica",
        "asfalto_sobre_empedrado",
        "ciclovias",
    ]
    print("\n=== Conteos verificados en PostgreSQL (sig_ae4) ===")
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM sig_ae4.{table};")
        count = cur.fetchone()[0]
        print(f"  {table:<28}: {count}")

    cur.execute("SELECT COALESCE(SUM(poblacion_2022), 0) FROM sig_ae4.delegaciones;")
    pop_posadas = cur.fetchone()[0]
    print(f"  {'delegaciones (pob. 2022)':<28}: {pop_posadas}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Carga capas GeoJSON/Shapefile IGN, Natural Earth e IDE Posadas hacia PostGIS."
    )
    parser.add_argument(
        "--container",
        default=os.getenv("DOCKER_CONTAINER", DEFAULT_CONTAINER),
        help=(
            "Nombre del contenedor Docker PostGIS para shp2pgsql "
            f"(default: {DEFAULT_CONTAINER}; pase '' para usar binario local si existe)."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    container_name = args.container.strip() or None
    specs = build_staging_specs()

    conn = get_pg_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("CREATE SCHEMA IF NOT EXISTS staging;")
                for spec in specs:
                    n_rows = load_geojson_layer(cur, spec)
                    print(f"[OK] {spec.table:<34}: {n_rows} filas")

        load_delegaciones_shp_demo(conn, container_name=container_name)

        sql_text = SQL_NORMALIZAR_PATH.read_text(encoding="utf-8")
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql_text)
                print(f"[OK] Normalización ejecutada: {SQL_NORMALIZAR_PATH.name}")
                print_final_counts(cur)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
