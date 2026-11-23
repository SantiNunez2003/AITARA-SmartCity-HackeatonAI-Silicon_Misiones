-- =============================================================================
-- AE4 SIG — Fase I: Validación integral de carga, geometrías, integridad y topología
-- Compatibilidad: PostgreSQL 16 + PostGIS 3.4 vía psql
-- Ejecución esperada:
--   docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -f - < ae4_sig/sql/01_validacion.sql
-- =============================================================================

\pset pager off
\pset null '(NULL)'
\set ON_ERROR_STOP on

\echo ============================================================================
\echo 1. CONTEO DE FILAS DE LAS 19 TABLAS DEL ESQUEMA sig_ae4
\echo ============================================================================

SELECT categoria, tabla, filas
FROM (
    -- 1.1 Tablas regionales (6)
    SELECT 1 AS ord_cat, '1_regional'     AS categoria, 'paises'                  AS tabla, COUNT(*) AS filas FROM sig_ae4.paises
    UNION ALL
    SELECT 1,            '1_regional',                  'provincias',                       COUNT(*)          FROM sig_ae4.provincias
    UNION ALL
    SELECT 1,            '1_regional',                  'departamentos',                    COUNT(*)          FROM sig_ae4.departamentos
    UNION ALL
    SELECT 1,            '1_regional',                  'localidades',                      COUNT(*)          FROM sig_ae4.localidades
    UNION ALL
    SELECT 1,            '1_regional',                  'cursos_agua',                      COUNT(*)          FROM sig_ae4.cursos_agua
    UNION ALL
    SELECT 1,            '1_regional',                  'rutas',                            COUNT(*)          FROM sig_ae4.rutas

    -- 1.2 Tablas urbanas Posadas (11)
    UNION ALL
    SELECT 2,            '2_urbana',                    'delegaciones',                     COUNT(*)          FROM sig_ae4.delegaciones
    UNION ALL
    SELECT 2,            '2_urbana',                    'semaforos',                        COUNT(*)          FROM sig_ae4.semaforos
    UNION ALL
    SELECT 2,            '2_urbana',                    'escuelas',                         COUNT(*)          FROM sig_ae4.escuelas
    UNION ALL
    SELECT 2,            '2_urbana',                    'paradas',                          COUNT(*)          FROM sig_ae4.paradas
    UNION ALL
    SELECT 2,            '2_urbana',                    'avenidas_mano_unica',              COUNT(*)          FROM sig_ae4.avenidas_mano_unica
    UNION ALL
    SELECT 2,            '2_urbana',                    'asfalto_sobre_empedrado',          COUNT(*)          FROM sig_ae4.asfalto_sobre_empedrado
    UNION ALL
    SELECT 2,            '2_urbana',                    'ciclovias',                        COUNT(*)          FROM sig_ae4.ciclovias
    UNION ALL
    SELECT 2,            '2_urbana',                    'calles',                           COUNT(*)          FROM sig_ae4.calles
    UNION ALL
    SELECT 2,            '2_urbana',                    'nodos_referencia_aitara',          COUNT(*)          FROM sig_ae4.nodos_referencia_aitara
    UNION ALL
    SELECT 2,            '2_urbana',                    'intersecciones',                   COUNT(*)          FROM sig_ae4.intersecciones
    UNION ALL
    SELECT 2,            '2_urbana',                    'incidentes_viales',                COUNT(*)          FROM sig_ae4.incidentes_viales

    -- 1.3 Tablas alfanuméricas y de auditoría (2)
    UNION ALL
    SELECT 3,            '3_alfanumerica',              'exposicion_clima',                 COUNT(*)          FROM sig_ae4.exposicion_clima
    UNION ALL
    SELECT 3,            '3_alfanumerica',              'auditoria_ediciones',              COUNT(*)          FROM sig_ae4.auditoria_ediciones
) AS conteos
ORDER BY ord_cat, tabla;


\echo ============================================================================
\echo 2. VALIDACION GEOMETRICA (ST_IsValid, SRID 4326 en geom, SRID 5348 en geom_m)
\echo ============================================================================

WITH validacion_espacial AS (
    -- Regionales (solo geom EPSG:4326)
    SELECT 1 AS ord, '1_regional' AS escala, 'paises' AS tabla, FALSE AS requiere_geom_m,
           COUNT(*) AS total_filas,
           COUNT(*) FILTER (WHERE geom IS NULL) AS geom_nulos,
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)) AS invalidos,
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326) AS srid_geom_err,
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ',') AS srids_geom,
           NULL::BIGINT AS geom_m_nulos,
           NULL::BIGINT AS srid_geom_m_err,
           NULL::TEXT   AS srids_geom_m
      FROM sig_ae4.paises
    UNION ALL
    SELECT 1, '1_regional', 'provincias', FALSE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           NULL::BIGINT, NULL::BIGINT, NULL::TEXT
      FROM sig_ae4.provincias
    UNION ALL
    SELECT 1, '1_regional', 'departamentos', FALSE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           NULL::BIGINT, NULL::BIGINT, NULL::TEXT
      FROM sig_ae4.departamentos
    UNION ALL
    SELECT 1, '1_regional', 'localidades', FALSE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           NULL::BIGINT, NULL::BIGINT, NULL::TEXT
      FROM sig_ae4.localidades
    UNION ALL
    SELECT 1, '1_regional', 'cursos_agua', FALSE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           NULL::BIGINT, NULL::BIGINT, NULL::TEXT
      FROM sig_ae4.cursos_agua
    UNION ALL
    SELECT 1, '1_regional', 'rutas', FALSE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           NULL::BIGINT, NULL::BIGINT, NULL::TEXT
      FROM sig_ae4.rutas

    -- Urbanas (geom EPSG:4326 + geom_m EPSG:5348 vía trg_01_sync_geom_m)
    UNION ALL
    SELECT 2, '2_urbana', 'delegaciones', TRUE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           COUNT(*) FILTER (WHERE geom_m IS NULL),
           COUNT(*) FILTER (WHERE ST_SRID(geom_m) <> 5348),
           STRING_AGG(DISTINCT ST_SRID(geom_m)::TEXT, ',')
      FROM sig_ae4.delegaciones
    UNION ALL
    SELECT 2, '2_urbana', 'semaforos', TRUE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           COUNT(*) FILTER (WHERE geom_m IS NULL),
           COUNT(*) FILTER (WHERE ST_SRID(geom_m) <> 5348),
           STRING_AGG(DISTINCT ST_SRID(geom_m)::TEXT, ',')
      FROM sig_ae4.semaforos
    UNION ALL
    SELECT 2, '2_urbana', 'escuelas', TRUE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           COUNT(*) FILTER (WHERE geom_m IS NULL),
           COUNT(*) FILTER (WHERE ST_SRID(geom_m) <> 5348),
           STRING_AGG(DISTINCT ST_SRID(geom_m)::TEXT, ',')
      FROM sig_ae4.escuelas
    UNION ALL
    SELECT 2, '2_urbana', 'paradas', TRUE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           COUNT(*) FILTER (WHERE geom_m IS NULL),
           COUNT(*) FILTER (WHERE ST_SRID(geom_m) <> 5348),
           STRING_AGG(DISTINCT ST_SRID(geom_m)::TEXT, ',')
      FROM sig_ae4.paradas
    UNION ALL
    SELECT 2, '2_urbana', 'avenidas_mano_unica', TRUE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           COUNT(*) FILTER (WHERE geom_m IS NULL),
           COUNT(*) FILTER (WHERE ST_SRID(geom_m) <> 5348),
           STRING_AGG(DISTINCT ST_SRID(geom_m)::TEXT, ',')
      FROM sig_ae4.avenidas_mano_unica
    UNION ALL
    SELECT 2, '2_urbana', 'asfalto_sobre_empedrado', TRUE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           COUNT(*) FILTER (WHERE geom_m IS NULL),
           COUNT(*) FILTER (WHERE ST_SRID(geom_m) <> 5348),
           STRING_AGG(DISTINCT ST_SRID(geom_m)::TEXT, ',')
      FROM sig_ae4.asfalto_sobre_empedrado
    UNION ALL
    SELECT 2, '2_urbana', 'ciclovias', TRUE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           COUNT(*) FILTER (WHERE geom_m IS NULL),
           COUNT(*) FILTER (WHERE ST_SRID(geom_m) <> 5348),
           STRING_AGG(DISTINCT ST_SRID(geom_m)::TEXT, ',')
      FROM sig_ae4.ciclovias
    UNION ALL
    SELECT 2, '2_urbana', 'calles', TRUE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           COUNT(*) FILTER (WHERE geom_m IS NULL),
           COUNT(*) FILTER (WHERE ST_SRID(geom_m) <> 5348),
           STRING_AGG(DISTINCT ST_SRID(geom_m)::TEXT, ',')
      FROM sig_ae4.calles
    UNION ALL
    SELECT 2, '2_urbana', 'nodos_referencia_aitara', TRUE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           COUNT(*) FILTER (WHERE geom_m IS NULL),
           COUNT(*) FILTER (WHERE ST_SRID(geom_m) <> 5348),
           STRING_AGG(DISTINCT ST_SRID(geom_m)::TEXT, ',')
      FROM sig_ae4.nodos_referencia_aitara
    UNION ALL
    SELECT 2, '2_urbana', 'intersecciones', TRUE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           COUNT(*) FILTER (WHERE geom_m IS NULL),
           COUNT(*) FILTER (WHERE ST_SRID(geom_m) <> 5348),
           STRING_AGG(DISTINCT ST_SRID(geom_m)::TEXT, ',')
      FROM sig_ae4.intersecciones
    UNION ALL
    SELECT 2, '2_urbana', 'incidentes_viales', TRUE,
           COUNT(*),
           COUNT(*) FILTER (WHERE geom IS NULL),
           COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)),
           COUNT(*) FILTER (WHERE ST_SRID(geom) <> 4326),
           STRING_AGG(DISTINCT ST_SRID(geom)::TEXT, ','),
           COUNT(*) FILTER (WHERE geom_m IS NULL),
           COUNT(*) FILTER (WHERE ST_SRID(geom_m) <> 5348),
           STRING_AGG(DISTINCT ST_SRID(geom_m)::TEXT, ',')
      FROM sig_ae4.incidentes_viales
)
SELECT
    escala,
    tabla,
    total_filas,
    geom_nulos,
    invalidos,
    srid_geom_err,
    srids_geom,
    geom_m_nulos,
    srid_geom_m_err,
    srids_geom_m,
    CASE
        WHEN total_filas > 0
         AND geom_nulos = 0
         AND invalidos = 0
         AND srid_geom_err = 0
         AND (NOT requiere_geom_m OR (geom_m_nulos = 0 AND srid_geom_m_err = 0))
        THEN 'OK'
        ELSE 'REVISAR'
    END AS estado
FROM validacion_espacial
ORDER BY ord, tabla;


\echo ============================================================================
\echo 3A. INTEGRIDAD REFERENCIAL (HUERFANOS EN JERARQUIA Y VINCULOS)
\echo ============================================================================

SELECT
    relacion,
    huerfanos,
    CASE WHEN huerfanos = 0 THEN 'OK' ELSE 'ERROR' END AS estado
FROM (
    SELECT 1 AS ord, 'provincias -> paises' AS relacion,
           COUNT(*) AS huerfanos
      FROM sig_ae4.provincias pr
      LEFT JOIN sig_ae4.paises pa ON pr.pais_id = pa.id
     WHERE pa.id IS NULL
    UNION ALL
    SELECT 2, 'departamentos -> provincias',
           COUNT(*)
      FROM sig_ae4.departamentos d
      LEFT JOIN sig_ae4.provincias pr ON d.provincia_id = pr.id
     WHERE pr.id IS NULL
    UNION ALL
    SELECT 3, 'localidades -> departamentos',
           COUNT(*)
      FROM sig_ae4.localidades l
      LEFT JOIN sig_ae4.departamentos d ON l.departamento_id = d.id
     WHERE d.id IS NULL
    UNION ALL
    SELECT 4, 'incidentes_viales -> intersecciones (no nulos)',
           COUNT(*)
      FROM sig_ae4.incidentes_viales iv
      LEFT JOIN sig_ae4.intersecciones i ON iv.interseccion_id = i.id
     WHERE iv.interseccion_id IS NOT NULL
       AND i.id IS NULL
    UNION ALL
    SELECT 5, 'incidentes_viales -> nodos_referencia_aitara (no nulos)',
           COUNT(*)
      FROM sig_ae4.incidentes_viales iv
      LEFT JOIN sig_ae4.nodos_referencia_aitara n ON iv.nodo_referencia_id = n.id
     WHERE iv.nodo_referencia_id IS NOT NULL
       AND n.id IS NULL
) AS checks
ORDER BY ord;


\echo ============================================================================
\echo 3B. DESGLOSE DE incidentes_viales POR ORIGEN (TRIGGER trg_02_sync_incidente_nodos)
\echo ============================================================================

SELECT
    COALESCE(iv.origen, 'TOTAL') AS origen,
    COUNT(*) AS total_incidentes,
    COUNT(iv.interseccion_id) AS con_interseccion,
    COUNT(*) FILTER (WHERE iv.interseccion_id IS NULL) AS sin_interseccion,
    ROUND(100.0 * COUNT(iv.interseccion_id) / NULLIF(COUNT(*), 0), 1) AS pct_interseccion,
    COUNT(iv.nodo_referencia_id) AS con_nodo_aitara,
    COUNT(*) FILTER (WHERE iv.nodo_referencia_id IS NULL) AS sin_nodo_aitara,
    ROUND(100.0 * COUNT(iv.nodo_referencia_id) / NULLIF(COUNT(*), 0), 1) AS pct_nodo_aitara,
    COUNT(*) FILTER (WHERE iv.interseccion_id IS NOT NULL OR iv.nodo_referencia_id IS NOT NULL) AS con_algun_vinculo
FROM sig_ae4.incidentes_viales iv
GROUP BY GROUPING SETS ((iv.origen), ())
ORDER BY GROUPING(iv.origen), iv.origen;


\echo ============================================================================
\echo 4A. SANITY CHECK TOPOLOGICO — CAPITALES NACIONALES Y PROVINCIALES
\echo ============================================================================

SELECT
    COUNT(*) FILTER (WHERE es_capital_nacional) AS capitales_nacionales,
    COUNT(*) FILTER (WHERE es_capital_provincial) AS capitales_provinciales,
    COUNT(*) FILTER (WHERE es_capital_nacional AND es_capital_provincial) AS ambas_jerarquias,
    COUNT(*) FILTER (WHERE es_capital_nacional OR es_capital_provincial) AS total_capitales_distintas,
    COUNT(DISTINCT pr.id) FILTER (WHERE l.es_capital_nacional OR l.es_capital_provincial) AS provincias_con_capital
FROM sig_ae4.localidades l
JOIN sig_ae4.departamentos d ON l.departamento_id = d.id
JOIN sig_ae4.provincias pr ON d.provincia_id = pr.id;


\echo ============================================================================
\echo 4B. SANITY CHECK TOPOLOGICO — VECINDAD DE paises (ST_Touches vs ST_Intersects)
\echo ============================================================================

WITH vecinos_touches AS (
    SELECT
        a.id,
        COUNT(b.id) AS cant_touches,
        COALESCE(STRING_AGG(b.nombre, ', ' ORDER BY b.nombre), '(sin vecinos)') AS lista_touches
    FROM sig_ae4.paises a
    LEFT JOIN sig_ae4.paises b
      ON a.id <> b.id
     AND ST_Touches(a.geom, b.geom)
    GROUP BY a.id
),
vecinos_intersects AS (
    SELECT
        a.id,
        COUNT(b.id) AS cant_intersects,
        COALESCE(STRING_AGG(b.nombre, ', ' ORDER BY b.nombre), '(sin vecinos)') AS lista_intersects
    FROM sig_ae4.paises a
    LEFT JOIN sig_ae4.paises b
      ON a.id <> b.id
     AND ST_Intersects(a.geom, b.geom)
    GROUP BY a.id
)
SELECT
    p.codigo_iso3 AS iso3,
    p.nombre AS pais,
    vt.cant_touches,
    vi.cant_intersects,
    (vi.cant_intersects - vt.cant_touches) AS diff_micro_overlap,
    vt.lista_touches,
    CASE
        WHEN vi.cant_intersects <> vt.cant_touches THEN vi.lista_intersects
        ELSE '(identica a ST_Touches)'
    END AS lista_intersects_si_difiere
FROM sig_ae4.paises p
JOIN vecinos_touches vt ON p.id = vt.id
JOIN vecinos_intersects vi ON p.id = vi.id
ORDER BY vi.cant_intersects DESC, vt.cant_touches DESC, p.nombre ASC;

\echo --- Diagnostico de pares de paises donde ST_Intersects = TRUE y ST_Touches = FALSE ---
SELECT
    a.nombre AS pais_a,
    b.nombre AS pais_b,
    ST_Touches(a.geom, b.geom) AS st_touches,
    ST_Overlaps(a.geom, b.geom) AS st_overlaps,
    ST_Dimension(ST_Intersection(a.geom, b.geom)) AS dim_interseccion,
    ROUND(
        (ST_Area(ST_CollectionExtract(ST_Intersection(a.geom, b.geom), 3)::geography) / 1e6)::NUMERIC,
        4
    ) AS area_solapamiento_km2
FROM sig_ae4.paises a
JOIN sig_ae4.paises b
  ON a.id < b.id
 AND ST_Intersects(a.geom, b.geom)
 AND NOT ST_Touches(a.geom, b.geom)
ORDER BY area_solapamiento_km2 DESC, a.nombre, b.nombre;


\echo ============================================================================
\echo 4C. SANITY CHECK TOPOLOGICO — VECINDAD DE provincias VIA ST_Touches (MISIONES)
\echo ============================================================================

WITH prov_touches AS (
    SELECT
        a.id,
        COUNT(b.id) AS cant_vecinos_touches,
        COALESCE(STRING_AGG(b.nombre, ', ' ORDER BY b.nombre), '(sin contiguidad terrestre)') AS vecinos_touches
    FROM sig_ae4.provincias a
    LEFT JOIN sig_ae4.provincias b
      ON a.id <> b.id
     AND ST_Touches(a.geom, b.geom)
    GROUP BY a.id
),
prov_intersects AS (
    SELECT
        a.id,
        COUNT(b.id) AS cant_vecinos_intersects
    FROM sig_ae4.provincias a
    LEFT JOIN sig_ae4.provincias b
      ON a.id <> b.id
     AND ST_Intersects(a.geom, b.geom)
    GROUP BY a.id
)
SELECT
    CASE WHEN pr.nombre = 'Misiones' THEN '>>> MISIONES <<<' ELSE '' END AS destaque,
    pr.codigo_indec,
    pr.nombre AS provincia,
    pr.region,
    pt.cant_vecinos_touches,
    pi.cant_vecinos_intersects - pt.cant_vecinos_touches AS diff_overlap,
    pt.vecinos_touches
FROM sig_ae4.provincias pr
JOIN prov_touches pt ON pr.id = pt.id
JOIN prov_intersects pi ON pr.id = pi.id
ORDER BY (pr.nombre = 'Misiones') DESC, pt.cant_vecinos_touches DESC, pr.nombre ASC;


\echo ============================================================================
\echo 4D. SANITY CHECK TOPOLOGICO — LONGITUD DE RIOS PRINCIPALES EN MISIONES (km)
\echo ============================================================================

WITH rios_principales AS (
    SELECT
        c.nombre AS rio,
        COUNT(*) AS tramos_origen,
        ST_Union(c.geom) AS geom
    FROM sig_ae4.cursos_agua c
    WHERE c.es_principal = TRUE
      AND c.nombre IN ('Río Paraná', 'Río Uruguay', 'Río Iguazú')
    GROUP BY c.nombre
),
inter_misiones AS (
    SELECT
        r.rio,
        r.tramos_origen,
        d.nombre AS departamento,
        ST_Length(
            ST_CollectionExtract(ST_Intersection(r.geom, d.geom), 2)::geography
        ) / 1000.0 AS longitud_km
    FROM rios_principales r
    JOIN sig_ae4.departamentos d
      ON ST_Intersects(r.geom, d.geom)
    JOIN sig_ae4.provincias pr
      ON d.provincia_id = pr.id
    WHERE pr.nombre = 'Misiones'
)
SELECT
    rio,
    tramos_origen,
    departamento,
    ROUND(longitud_km::NUMERIC, 3) AS longitud_km
FROM inter_misiones
WHERE longitud_km > 0
ORDER BY rio ASC, longitud_km DESC, departamento ASC;
