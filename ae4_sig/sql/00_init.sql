-- =============================================================================
-- AE4 SIG — Fase I: Inicialización, esquema espacial, integridad y triggers
-- Stack: PostgreSQL 16 + PostGIS 3.4 (Docker)
-- Caso de estudio: AITARA + IGN (escala regional) + IDE Posadas (escala urbana)
-- Sistemas de referencia:
--   - geom   : EPSG:4326 (WGS84 geográfico — intercambio, WFS y visualización QGIS)
--   - geom_m : EPSG:5348 (POSGAR 2007 / Argentina Faja 6 — distancias/áreas en m)
--   - Regional (a–i): uso de geography e índice funcional GiST (geom::geography)
-- Nota: Los índices GiST se crean posteriormente en 04_indices_benchmark.sql
--       para poder medir el rendimiento sin índice vs. con índice.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

DROP SCHEMA IF EXISTS sig_ae4 CASCADE;
DROP SCHEMA IF EXISTS staging CASCADE;

CREATE SCHEMA staging;
CREATE SCHEMA sig_ae4;

COMMENT ON SCHEMA sig_ae4 IS 'Esquema productivo AE4 SIG: capas regionales IGN/NE y capas urbanas IDE Posadas + OSM/AITARA';
COMMENT ON SCHEMA staging IS 'Esquema intermedio para carga cruda desde WFS/ogr2ogr/shp2pgsql antes de normalizar';

-- -----------------------------------------------------------------------------
-- 1. TABLAS DE ESCALA REGIONAL (EPSG:4326)
-- -----------------------------------------------------------------------------

CREATE TABLE sig_ae4.paises (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_iso3 VARCHAR(3)   NOT NULL UNIQUE,
    nombre      VARCHAR(120) NOT NULL,
    subregion   VARCHAR(80),
    poblacion   BIGINT       CHECK (poblacion >= 0),
    fuente      VARCHAR(80)  NOT NULL DEFAULT 'Natural Earth 50m (complemento IGN)',
    geom        GEOMETRY(MultiPolygon, 4326) NOT NULL CHECK (ST_IsValid(geom))
);

CREATE TABLE sig_ae4.provincias (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_indec    VARCHAR(10)  NOT NULL UNIQUE,
    nombre          VARCHAR(120) NOT NULL,
    nombre_completo VARCHAR(180),
    region          VARCHAR(60)  NOT NULL,
    poblacion       BIGINT       CHECK (poblacion >= 0),
    pais_id         INTEGER      NOT NULL REFERENCES sig_ae4.paises(id),
    fuente          VARCHAR(80)  NOT NULL DEFAULT 'IGN',
    geom            GEOMETRY(MultiPolygon, 4326) NOT NULL CHECK (ST_IsValid(geom))
);

CREATE TABLE sig_ae4.departamentos (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_indec    VARCHAR(10)  NOT NULL UNIQUE,
    nombre          VARCHAR(120) NOT NULL,
    nombre_completo VARCHAR(180),
    poblacion       BIGINT       CHECK (poblacion >= 0),
    provincia_id    INTEGER      NOT NULL REFERENCES sig_ae4.provincias(id),
    fuente          VARCHAR(80)  NOT NULL DEFAULT 'IGN',
    geom            GEOMETRY(MultiPolygon, 4326) NOT NULL CHECK (ST_IsValid(geom))
);

CREATE TABLE sig_ae4.localidades (
    id                    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_bahra          VARCHAR(30)  NOT NULL UNIQUE,
    nombre                VARCHAR(150) NOT NULL,
    tipo_asentamiento     VARCHAR(80),
    es_capital_nacional   BOOLEAN      NOT NULL DEFAULT FALSE,
    es_capital_provincial BOOLEAN      NOT NULL DEFAULT FALSE,
    departamento_id       INTEGER      NOT NULL REFERENCES sig_ae4.departamentos(id),
    fuente                VARCHAR(80)  NOT NULL DEFAULT 'IGN-BAHRA',
    geom                  GEOMETRY(Point, 4326) NOT NULL CHECK (ST_IsValid(geom))
);

CREATE TABLE sig_ae4.cursos_agua (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_origen    VARCHAR(50)  NOT NULL UNIQUE,
    nombre       VARCHAR(150) NOT NULL,
    nombre_corto VARCHAR(120),
    categoria    VARCHAR(60),
    es_principal BOOLEAN      NOT NULL DEFAULT FALSE,
    fuente       VARCHAR(80)  NOT NULL DEFAULT 'IGN',
    geom         GEOMETRY(MultiLineString, 4326) NOT NULL CHECK (ST_IsValid(geom))
);

CREATE TABLE sig_ae4.rutas (
    id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_origen          VARCHAR(50)  NOT NULL UNIQUE,
    nombre             VARCHAR(120) NOT NULL,
    numero_ruta        VARCHAR(30),
    jurisdiccion       VARCHAR(20)  NOT NULL CHECK (jurisdiccion IN ('nacional', 'provincial')),
    superficie_calzada INTEGER,
    fuente             VARCHAR(80)  NOT NULL DEFAULT 'IGN',
    geom               GEOMETRY(MultiLineString, 4326) NOT NULL CHECK (ST_IsValid(geom))
);

-- -----------------------------------------------------------------------------
-- 2. TABLAS DE ESCALA URBANA — POSADAS (EPSG:4326 + geom_m EPSG:5348)
-- -----------------------------------------------------------------------------

CREATE TABLE sig_ae4.delegaciones (
    id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_ide         VARCHAR(40)  UNIQUE,
    nombre         VARCHAR(120) NOT NULL,
    descripcion    VARCHAR(180),
    poblacion_2022 INTEGER      CHECK (poblacion_2022 >= 0),
    fuente         VARCHAR(80)  NOT NULL DEFAULT 'IDE Posadas',
    geom           GEOMETRY(MultiPolygon, 4326) NOT NULL CHECK (ST_IsValid(geom)),
    geom_m         GEOMETRY(MultiPolygon, 5348)
);

CREATE TABLE sig_ae4.semaforos (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_ide       VARCHAR(40)  UNIQUE,
    nombre       VARCHAR(200) NOT NULL,
    calle_1      VARCHAR(120),
    calle_2      VARCHAR(120),
    estado       VARCHAR(60),
    centralizado VARCHAR(20),
    peatonales   VARCHAR(20),
    fuente       VARCHAR(80)  NOT NULL DEFAULT 'IDE Posadas',
    geom         GEOMETRY(Point, 4326) NOT NULL CHECK (ST_IsValid(geom)),
    geom_m       GEOMETRY(Point, 5348)
);

CREATE TABLE sig_ae4.escuelas (
    id       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_ide   VARCHAR(40)  UNIQUE,
    cueanexo VARCHAR(30),
    nombre   VARCHAR(220) NOT NULL,
    sector   VARCHAR(40),
    calle    VARCHAR(150),
    barrio   VARCHAR(120),
    fuente   VARCHAR(80)  NOT NULL DEFAULT 'IDE Posadas',
    geom     GEOMETRY(Point, 4326) NOT NULL CHECK (ST_IsValid(geom)),
    geom_m   GEOMETRY(Point, 5348)
);

CREATE TABLE sig_ae4.paradas (
    id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_ide  VARCHAR(40)  UNIQUE,
    codigo  VARCHAR(60),
    nombre  VARCHAR(220) NOT NULL,
    barrio  VARCHAR(120),
    activo  VARCHAR(20),
    darsena VARCHAR(20),
    fuente  VARCHAR(80)  NOT NULL DEFAULT 'IDE Posadas',
    geom    GEOMETRY(Point, 4326) NOT NULL CHECK (ST_IsValid(geom)),
    geom_m  GEOMETRY(Point, 5348)
);

CREATE TABLE sig_ae4.avenidas_mano_unica (
    id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_ide  VARCHAR(40)  UNIQUE,
    nombre  VARCHAR(150) NOT NULL,
    sentido VARCHAR(60),
    vigente VARCHAR(10),
    fuente  VARCHAR(80)  NOT NULL DEFAULT 'IDE Posadas',
    geom    GEOMETRY(MultiLineString, 4326) NOT NULL CHECK (ST_IsValid(geom)),
    geom_m  GEOMETRY(MultiLineString, 5348)
);

CREATE TABLE sig_ae4.asfalto_sobre_empedrado (
    id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_ide    VARCHAR(40)  UNIQUE,
    nombre    VARCHAR(180) NOT NULL,
    anio      VARCHAR(20),
    tipo_obra VARCHAR(120),
    fuente    VARCHAR(80)  NOT NULL DEFAULT 'IDE Posadas',
    geom      GEOMETRY(MultiLineString, 4326) NOT NULL CHECK (ST_IsValid(geom)),
    geom_m    GEOMETRY(MultiLineString, 5348)
);

CREATE TABLE sig_ae4.ciclovias (
    id     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_ide VARCHAR(40)  UNIQUE,
    nombre VARCHAR(180) NOT NULL,
    tramo  TEXT,
    anio   INTEGER,
    fuente VARCHAR(80)  NOT NULL DEFAULT 'IDE Posadas',
    geom   GEOMETRY(MultiLineString, 4326) NOT NULL CHECK (ST_IsValid(geom)),
    geom_m GEOMETRY(MultiLineString, 5348)
);

CREATE TABLE sig_ae4.calles (
    id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    osm_id             BIGINT       NOT NULL UNIQUE,
    nombre             VARCHAR(180) NOT NULL,
    nombre_normalizado VARCHAR(180) NOT NULL UNIQUE,
    aliases            TEXT[],
    fuente             VARCHAR(80)  NOT NULL DEFAULT 'OSM vía AITARA',
    geom               GEOMETRY(MultiLineString, 4326) NOT NULL CHECK (ST_IsValid(geom)),
    geom_m             GEOMETRY(MultiLineString, 5348)
);

CREATE TABLE sig_ae4.nodos_referencia_aitara (
    id                INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    node_id           VARCHAR(60)  NOT NULL UNIQUE,
    nombre            VARCHAR(180) NOT NULL,
    corridor_type     VARCHAR(60)  NOT NULL,
    lanes             INTEGER      CHECK (lanes > 0),
    has_traffic_light BOOLEAN,
    has_bus_stop      BOOLEAN,
    is_school_zone    BOOLEAN,
    school_name       VARCHAR(150),
    nivel_drenaje     VARCHAR(10)  NOT NULL CHECK (nivel_drenaje IN ('ALTO', 'MEDIO', 'BAJO')),
    fuente            VARCHAR(80)  NOT NULL DEFAULT 'AITARA (atributo experto)',
    geom              GEOMETRY(Point, 4326) NOT NULL CHECK (ST_IsValid(geom)),
    geom_m            GEOMETRY(Point, 5348)
);

CREATE TABLE sig_ae4.intersecciones (
    id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    osm_id        BIGINT       NOT NULL,
    nombre        VARCHAR(240) NOT NULL,
    calle_1       VARCHAR(140) NOT NULL,
    calle_2       VARCHAR(140) NOT NULL,
    calle_1_norm  VARCHAR(140) NOT NULL,
    calle_2_norm  VARCHAR(140) NOT NULL,
    subtipo       VARCHAR(20)  NOT NULL CHECK (subtipo IN ('nodo', 'rotonda')),
    nivel_drenaje VARCHAR(10)  CHECK (nivel_drenaje IN ('ALTO', 'MEDIO', 'BAJO')),
    fuente        VARCHAR(80)  NOT NULL DEFAULT 'OSM vía AITARA',
    geom          GEOMETRY(Point, 4326) NOT NULL CHECK (ST_IsValid(geom)),
    geom_m        GEOMETRY(Point, 5348),
    CONSTRAINT uq_intersecciones_par UNIQUE (calle_1_norm, calle_2_norm)
);

CREATE TABLE sig_ae4.incidentes_viales (
    id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_origen          VARCHAR(60)  UNIQUE,
    nombre             VARCHAR(260) NOT NULL,
    origen             VARCHAR(15)  NOT NULL CHECK (origen IN ('real', 'simulado')),
    fuente             VARCHAR(80)  NOT NULL,
    fecha_evento       TIMESTAMP    NOT NULL,
    tipo_incidente     VARCHAR(40)  NOT NULL,
    severidad          INTEGER      NOT NULL CHECK (severidad BETWEEN 1 AND 5),
    vehiculos          TEXT[],
    ubicacion_texto    TEXT,
    llovia             BOOLEAN,
    precipitacion_mm_h NUMERIC(6,2) CHECK (precipitacion_mm_h >= 0),
    confianza          NUMERIC(4,3) CHECK (confianza BETWEEN 0 AND 1),
    interseccion_id    INTEGER      REFERENCES sig_ae4.intersecciones(id),
    nodo_referencia_id INTEGER      REFERENCES sig_ae4.nodos_referencia_aitara(id),
    geom               GEOMETRY(Point, 4326) NOT NULL CHECK (ST_IsValid(geom)),
    geom_m             GEOMETRY(Point, 5348)
);

-- -----------------------------------------------------------------------------
-- 3. TABLAS ALFANUMÉRICAS Y DE AUDITORÍA
-- -----------------------------------------------------------------------------

CREATE TABLE sig_ae4.exposicion_clima (
    id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    condicion          VARCHAR(20) NOT NULL UNIQUE CHECK (condicion IN ('lluvia', 'seco')),
    horas_nodo_totales INTEGER     NOT NULL CHECK (horas_nodo_totales > 0),
    nodos_observados   INTEGER     NOT NULL DEFAULT 7 CHECK (nodos_observados > 0),
    horas_por_nodo     NUMERIC(10,2) GENERATED ALWAYS AS (horas_nodo_totales::NUMERIC / nodos_observados) STORED,
    periodo_inicio     DATE        NOT NULL DEFAULT DATE '2023-01-01',
    periodo_fin        DATE        NOT NULL DEFAULT DATE '2025-12-31'
);

CREATE TABLE sig_ae4.auditoria_ediciones (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tabla_nombre VARCHAR(80) NOT NULL,
    operacion    VARCHAR(10) NOT NULL CHECK (operacion IN ('INSERT', 'UPDATE', 'DELETE')),
    registro_id  INTEGER,
    usuario      VARCHAR(80) NOT NULL DEFAULT current_user,
    fecha_hora   TIMESTAMPTZ NOT NULL DEFAULT now(),
    detalle      JSONB
);

-- -----------------------------------------------------------------------------
-- 4. FUNCIONES Y TRIGGERS (geom_m 5348, vínculo espacial y auditoría)
-- -----------------------------------------------------------------------------

-- 4.1 Mantiene geom_m en EPSG:5348 cada vez que se inserta o edita geom (4326)
CREATE OR REPLACE FUNCTION sig_ae4.fn_sync_geom_m()
RETURNS TRIGGER AS $$
BEGIN
    NEW.geom_m := ST_Transform(NEW.geom, 5348);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 4.2 Asigna intersección OSM (<=150 m) y nodo experto AITARA (<=500 m) más cercanos
CREATE OR REPLACE FUNCTION sig_ae4.fn_sync_incidente_nodos()
RETURNS TRIGGER AS $$
BEGIN
    SELECT i.id
      INTO NEW.interseccion_id
      FROM sig_ae4.intersecciones i
     WHERE i.geom_m IS NOT NULL
       AND ST_DWithin(i.geom_m, NEW.geom_m, 150.0)
     ORDER BY i.geom_m <-> NEW.geom_m
     LIMIT 1;

    SELECT n.id
      INTO NEW.nodo_referencia_id
      FROM sig_ae4.nodos_referencia_aitara n
     WHERE n.geom_m IS NOT NULL
       AND ST_DWithin(n.geom_m, NEW.geom_m, 500.0)
     ORDER BY n.geom_m <-> NEW.geom_m
     LIMIT 1;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 4.3 Registra operaciones DML en auditoria_ediciones (evidencia Fase III)
CREATE OR REPLACE FUNCTION sig_ae4.fn_auditar_edicion()
RETURNS TRIGGER AS $$
DECLARE
    v_id      INTEGER;
    v_nombre  TEXT;
    v_detalle JSONB;
BEGIN
    v_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END;
    v_nombre := CASE WHEN TG_OP = 'DELETE' THEN OLD.nombre ELSE NEW.nombre END;

    v_detalle := jsonb_build_object(
        'nombre', v_nombre,
        'geom_wkt', ST_AsText(CASE WHEN TG_OP = 'DELETE' THEN OLD.geom ELSE NEW.geom END),
        'anterior', CASE WHEN TG_OP IN ('UPDATE', 'DELETE') THEN to_jsonb(OLD) - 'geom' - 'geom_m' ELSE NULL END,
        'nuevo', CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN to_jsonb(NEW) - 'geom' - 'geom_m' ELSE NULL END
    );

    INSERT INTO sig_ae4.auditoria_ediciones (tabla_nombre, operacion, registro_id, detalle)
    VALUES (TG_TABLE_NAME, TG_OP, v_id, v_detalle);

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Adjuntar trigger trg_01_sync_geom_m a todas las tablas urbanas de Posadas
DO $$
DECLARE
    t TEXT;
    urban_tables TEXT[] := ARRAY[
        'delegaciones',
        'semaforos',
        'escuelas',
        'paradas',
        'avenidas_mano_unica',
        'asfalto_sobre_empedrado',
        'ciclovias',
        'calles',
        'nodos_referencia_aitara',
        'intersecciones',
        'incidentes_viales'
    ];
BEGIN
    FOREACH t IN ARRAY urban_tables LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_01_sync_geom_m
             BEFORE INSERT OR UPDATE OF geom ON sig_ae4.%I
             FOR EACH ROW EXECUTE FUNCTION sig_ae4.fn_sync_geom_m();',
            t
        );
    END LOOP;
END $$;

-- Orden alfabético garantiza que trg_01_sync_geom_m corra antes que trg_02_sync_incidente_nodos
CREATE TRIGGER trg_02_sync_incidente_nodos
    BEFORE INSERT OR UPDATE OF geom ON sig_ae4.incidentes_viales
    FOR EACH ROW EXECUTE FUNCTION sig_ae4.fn_sync_incidente_nodos();

CREATE TRIGGER trg_auditar_semaforos
    AFTER INSERT OR UPDATE OR DELETE ON sig_ae4.semaforos
    FOR EACH ROW EXECUTE FUNCTION sig_ae4.fn_auditar_edicion();

CREATE TRIGGER trg_auditar_incidentes
    AFTER INSERT OR UPDATE OR DELETE ON sig_ae4.incidentes_viales
    FOR EACH ROW EXECUTE FUNCTION sig_ae4.fn_auditar_edicion();
