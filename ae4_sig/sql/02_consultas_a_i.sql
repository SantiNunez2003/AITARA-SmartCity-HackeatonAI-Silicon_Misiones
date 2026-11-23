-- =============================================================================
-- AE4 SIG — Fase II: Consultas espaciales obligatorias (Incisos a – i)
-- Capas regionales IGN / BAHRA / Natural Earth 50m en esquema sig_ae4
-- Criterio métrico regional: geography (WGS84 esferoidal)
-- Ejecución esperada:
--   docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -f - < ae4_sig/sql/02_consultas_a_i.sql
-- =============================================================================

\pset pager off
\pset null '(NULL)'
\set ON_ERROR_STOP on

-- =============================================================================
-- Inciso a: Uniones relacionales (JOIN)
-- Localidades unidas con departamentos, provincias y países, ordenadas
-- alfabéticamente. Se muestra una vista nacional acotada (LIMIT 50) y el
-- detalle completo para la provincia de Misiones.
-- =============================================================================

\echo ============================================================================
\echo INCISO a1: LOCALIDADES CON DEPARTAMENTO, PROVINCIA Y PAIS (MUESTRA 50 ALFABETICA)
\echo ============================================================================

-- Inciso a1 (vista nacional ordenada alfabéticamente; quitar LIMIT para ver todas)
SELECT
    l.codigo_bahra,
    l.nombre            AS localidad,
    l.tipo_asentamiento,
    d.nombre            AS departamento,
    pr.nombre           AS provincia,
    pr.region,
    pa.nombre           AS pais
FROM sig_ae4.localidades l
JOIN sig_ae4.departamentos d ON l.departamento_id = d.id
JOIN sig_ae4.provincias pr   ON d.provincia_id = pr.id
JOIN sig_ae4.paises pa       ON pr.pais_id = pa.id
ORDER BY pa.nombre ASC, pr.nombre ASC, d.nombre ASC, l.nombre ASC
LIMIT 50;

\echo ============================================================================
\echo INCISO a2: DETALLE COMPLETO DE LOCALIDADES DE MISIONES (ORDEN ALFABETICO)
\echo ============================================================================

-- Inciso a2 (detalle completo Misiones)
SELECT
    l.codigo_bahra,
    l.nombre            AS localidad,
    l.tipo_asentamiento,
    d.nombre            AS departamento,
    pr.nombre           AS provincia,
    pa.nombre           AS pais
FROM sig_ae4.localidades l
JOIN sig_ae4.departamentos d ON l.departamento_id = d.id
JOIN sig_ae4.provincias pr   ON d.provincia_id = pr.id
JOIN sig_ae4.paises pa       ON pr.pais_id = pa.id
WHERE pr.nombre = 'Misiones'
ORDER BY l.nombre ASC, d.nombre ASC;


-- =============================================================================
-- Inciso b: Filtrado de jerarquías geopolíticas
-- Capitales nacionales y provinciales indicando su jerarquía administrativa.
-- =============================================================================

\echo ============================================================================
\echo INCISO b: CAPITALES NACIONALES Y PROVINCIALES
\echo ============================================================================

-- Inciso b
SELECT
    l.nombre AS ciudad,
    CASE
        WHEN l.es_capital_nacional AND l.es_capital_provincial THEN 'Capital Nacional y Provincial'
        WHEN l.es_capital_nacional                             THEN 'Capital Nacional'
        WHEN l.es_capital_provincial                           THEN 'Capital Provincial'
    END      AS tipo_capital,
    d.nombre AS departamento,
    pr.nombre AS provincia,
    pr.region,
    pa.nombre AS pais
FROM sig_ae4.localidades l
JOIN sig_ae4.departamentos d ON l.departamento_id = d.id
JOIN sig_ae4.provincias pr   ON d.provincia_id = pr.id
JOIN sig_ae4.paises pa       ON pr.pais_id = pa.id
WHERE l.es_capital_nacional
   OR l.es_capital_provincial
ORDER BY l.es_capital_nacional DESC, pr.nombre ASC, l.nombre ASC;


-- =============================================================================
-- Inciso c: Estadísticas de superficie y demografía
-- Superficie geodésica en km² (ST_Area(geom::geography) / 1e6) y población.
-- =============================================================================

\echo ============================================================================
\echo INCISO c1: PAISES DE SUDAMERICA — SUPERFICIE (km2) Y POBLACION (DESC)
\echo ============================================================================

-- Inciso c1: Países sudamericanos
SELECT
    pa.codigo_iso3 AS iso3,
    pa.nombre      AS pais,
    pa.subregion,
    ROUND((ST_Area(pa.geom::geography) / 1e6)::NUMERIC, 2) AS superficie_km2,
    pa.poblacion,
    ROUND(
        (pa.poblacion / NULLIF(ST_Area(pa.geom::geography) / 1e6, 0))::NUMERIC,
        2
    ) AS densidad_hab_km2
FROM sig_ae4.paises pa
WHERE COALESCE(pa.subregion, 'South America') = 'South America'
ORDER BY superficie_km2 DESC, pa.poblacion DESC NULLS LAST;

\echo ============================================================================
\echo INCISO c2: 17 DEPARTAMENTOS DE MISIONES — SUPERFICIE (km2) Y POBLACION (DESC)
\echo ============================================================================

-- Inciso c2: Departamentos de Misiones
SELECT
    d.codigo_indec,
    d.nombre       AS departamento,
    pr.nombre      AS provincia,
    ROUND((ST_Area(d.geom::geography) / 1e6)::NUMERIC, 2) AS superficie_km2,
    d.poblacion,
    ROUND(
        (d.poblacion / NULLIF(ST_Area(d.geom::geography) / 1e6, 0))::NUMERIC,
        2
    ) AS densidad_hab_km2
FROM sig_ae4.departamentos d
JOIN sig_ae4.provincias pr ON d.provincia_id = pr.id
WHERE pr.nombre = 'Misiones'
ORDER BY superficie_km2 DESC, d.poblacion DESC NULLS LAST, d.nombre ASC;


-- =============================================================================
-- Inciso d: Adyacencia y fronteras (ST_Touches + diagnóstico de solapamiento NE 50m)
-- =============================================================================

\echo ============================================================================
\echo INCISO d1: ADYACENCIA DE PAISES DE SUDAMERICA (ST_Touches vs ST_Intersects)
\echo ============================================================================

-- Inciso d1: Países vecinos con ST_Touches y contraste frente a ST_Intersects
-- (Natural Earth 50m puede presentar micro-solapamientos en fronteras generalizadas
-- que hacen que ST_Touches sea FALSE aun siendo países limítrofes).
WITH vecinos_touches AS (
    SELECT
        a.id,
        COUNT(b.id) AS cant_vecinos_touches,
        COALESCE(STRING_AGG(b.nombre, ', ' ORDER BY b.nombre), '(sin vecinos)') AS vecinos_touches
    FROM sig_ae4.paises a
    LEFT JOIN sig_ae4.paises b
      ON a.id <> b.id
     AND ST_Touches(a.geom, b.geom)
    GROUP BY a.id
),
vecinos_intersects AS (
    SELECT
        a.id,
        COUNT(b.id) AS cant_vecinos_intersects,
        COALESCE(STRING_AGG(b.nombre, ', ' ORDER BY b.nombre), '(sin vecinos)') AS vecinos_intersects
    FROM sig_ae4.paises a
    LEFT JOIN sig_ae4.paises b
      ON a.id <> b.id
     AND ST_Intersects(a.geom, b.geom)
    GROUP BY a.id
)
SELECT
    pa.codigo_iso3 AS iso3,
    pa.nombre      AS pais,
    vt.cant_vecinos_touches,
    vt.vecinos_touches,
    vi.cant_vecinos_intersects,
    vi.vecinos_intersects,
    CASE
        WHEN vi.cant_vecinos_intersects > vt.cant_vecinos_touches
            THEN 'Micro-solapamiento NE 50m en ' || (vi.cant_vecinos_intersects - vt.cant_vecinos_touches) || ' frontera(s)'
        ELSE 'Topologia limpia (ST_Touches = ST_Intersects)'
    END AS diagnostico_frontera
FROM sig_ae4.paises pa
JOIN vecinos_touches vt    ON pa.id = vt.id
JOIN vecinos_intersects vi ON pa.id = vi.id
WHERE COALESCE(pa.subregion, 'South America') = 'South America'
ORDER BY vt.cant_vecinos_touches DESC, vi.cant_vecinos_intersects DESC, pa.nombre ASC;

\echo ============================================================================
\echo INCISO d2: ADYACENCIA DE PROVINCIAS ARGENTINAS (ST_Touches)
\echo ============================================================================

-- Inciso d2: Provincias vecinas mediante ST_Touches
SELECT
    pr_a.codigo_indec,
    pr_a.nombre AS provincia,
    pr_a.region,
    COUNT(pr_b.id) AS cant_vecinos,
    COALESCE(
        STRING_AGG(pr_b.nombre, ', ' ORDER BY pr_b.nombre),
        '(sin contiguidad terrestre)'
    ) AS provincias_vecinas
FROM sig_ae4.provincias pr_a
LEFT JOIN sig_ae4.provincias pr_b
  ON pr_a.id <> pr_b.id
 AND ST_Touches(pr_a.geom, pr_b.geom)
GROUP BY pr_a.id, pr_a.codigo_indec, pr_a.nombre, pr_a.region
ORDER BY cant_vecinos DESC, pr_a.nombre ASC;


-- =============================================================================
-- Inciso e: Intersecciones espaciales (Overlays)
-- Se agrega cada curso principal con ST_Union por nombre para evitar doble
-- conteo en ríos multi-tramo (ej. Río Paraná).
-- =============================================================================

\echo ============================================================================
\echo INCISO e1: DEPARTAMENTOS DE MISIONES INTERSECTADOS POR RIOS PRINCIPALES
\echo ============================================================================

-- Inciso e1: Departamentos de Misiones intersectados (agrupado por río)
WITH rios_principales AS (
    SELECT
        c.nombre AS rio,
        ST_Union(c.geom) AS geom
    FROM sig_ae4.cursos_agua c
    WHERE c.es_principal = TRUE
      AND c.nombre IN ('Río Paraná', 'Río Uruguay', 'Río Iguazú')
    GROUP BY c.nombre
)
SELECT
    r.rio,
    COUNT(d.id) AS cant_departamentos_misiones,
    STRING_AGG(d.nombre, ', ' ORDER BY d.nombre) AS departamentos_intersectados
FROM rios_principales r
JOIN sig_ae4.departamentos d ON ST_Intersects(r.geom, d.geom)
JOIN sig_ae4.provincias pr   ON d.provincia_id = pr.id
WHERE pr.nombre = 'Misiones'
GROUP BY r.rio
ORDER BY cant_departamentos_misiones DESC, r.rio ASC;

\echo ============================================================================
\echo INCISO e2: PAISES INTERSECTADOS POR RIOS PRINCIPALES
\echo ============================================================================

-- Inciso e2: Países intersectados por Río Paraná, Río Uruguay y Río Iguazú
WITH rios_principales AS (
    SELECT
        c.nombre AS rio,
        ST_Union(c.geom) AS geom
    FROM sig_ae4.cursos_agua c
    WHERE c.es_principal = TRUE
      AND c.nombre IN ('Río Paraná', 'Río Uruguay', 'Río Iguazú')
    GROUP BY c.nombre
)
SELECT
    r.rio,
    COUNT(pa.id) AS cant_paises,
    STRING_AGG(pa.nombre, ', ' ORDER BY pa.nombre) AS paises_intersectados
FROM rios_principales r
JOIN sig_ae4.paises pa ON ST_Intersects(r.geom, pa.geom)
GROUP BY r.rio
ORDER BY cant_paises DESC, r.rio ASC;


-- =============================================================================
-- Inciso f: Segmentación y métricas de recorrido
-- Longitud en km mediante ST_Length(ST_CollectionExtract(ST_Intersection(...), 2)::geography) / 1000.0
-- sobre geometrías de ríos previamente unificadas con ST_Union.
-- =============================================================================

\echo ============================================================================
\echo INCISO f1: LONGITUD DE RIOS PRINCIPALES POR DEPARTAMENTO DE MISIONES (km)
\echo ============================================================================

-- Inciso f1: Segmentación por departamento de Misiones
WITH rios_principales AS (
    SELECT
        c.nombre AS rio,
        ST_Union(c.geom) AS geom
    FROM sig_ae4.cursos_agua c
    WHERE c.es_principal = TRUE
      AND c.nombre IN ('Río Paraná', 'Río Uruguay', 'Río Iguazú')
    GROUP BY c.nombre
),
tramos_depto AS (
    SELECT
        r.rio,
        d.nombre AS departamento,
        ST_Length(
            ST_CollectionExtract(ST_Intersection(r.geom, d.geom), 2)::geography
        ) / 1000.0 AS longitud_km
    FROM rios_principales r
    JOIN sig_ae4.departamentos d ON ST_Intersects(r.geom, d.geom)
    JOIN sig_ae4.provincias pr   ON d.provincia_id = pr.id
    WHERE pr.nombre = 'Misiones'
)
SELECT
    rio,
    departamento,
    ROUND(longitud_km::NUMERIC, 3) AS longitud_km,
    ROUND((SUM(longitud_km) OVER (PARTITION BY rio))::NUMERIC, 3) AS total_en_misiones_km,
    ROUND(
        (100.0 * longitud_km / NULLIF(SUM(longitud_km) OVER (PARTITION BY rio), 0))::NUMERIC,
        2
    ) AS pct_recorrido_misiones
FROM tramos_depto
WHERE longitud_km > 0
ORDER BY rio ASC, longitud_km DESC, departamento ASC;

\echo ============================================================================
\echo INCISO f2: LONGITUD DE RIOS PRINCIPALES POR PAIS (km)
\echo ============================================================================

-- Inciso f2: Segmentación por país (tramos IGN dentro de polígonos Natural Earth 50m)
WITH rios_principales AS (
    SELECT
        c.nombre AS rio,
        ST_Union(c.geom) AS geom
    FROM sig_ae4.cursos_agua c
    WHERE c.es_principal = TRUE
      AND c.nombre IN ('Río Paraná', 'Río Uruguay', 'Río Iguazú')
    GROUP BY c.nombre
),
tramos_pais AS (
    SELECT
        r.rio,
        pa.nombre AS pais,
        ST_Length(
            ST_CollectionExtract(ST_Intersection(r.geom, pa.geom), 2)::geography
        ) / 1000.0 AS longitud_km
    FROM rios_principales r
    JOIN sig_ae4.paises pa ON ST_Intersects(r.geom, pa.geom)
)
SELECT
    rio,
    pais,
    ROUND(longitud_km::NUMERIC, 3) AS longitud_km,
    ROUND((SUM(longitud_km) OVER (PARTITION BY rio))::NUMERIC, 3) AS total_medido_km,
    ROUND(
        (100.0 * longitud_km / NULLIF(SUM(longitud_km) OVER (PARTITION BY rio), 0))::NUMERIC,
        2
    ) AS pct_recorrido
FROM tramos_pais
WHERE longitud_km > 0
ORDER BY rio ASC, longitud_km DESC, pais ASC;


-- =============================================================================
-- Inciso g: Máxima distancia y alejamiento extremo
-- Localidad de Misiones más alejada del Río Paraná (y Top 5 de contexto).
-- =============================================================================

\echo ============================================================================
\echo INCISO g1: LOCALIDAD DE MISIONES MAS ALEJADA DEL RIO PARANA
\echo ============================================================================

-- Inciso g1: Máximo alejamiento (LIMIT 1)
WITH rio_parana AS (
    SELECT ST_Union(c.geom)::geography AS geom_geog
    FROM sig_ae4.cursos_agua c
    WHERE c.es_principal = TRUE
      AND c.nombre = 'Río Paraná'
)
SELECT
    l.codigo_bahra,
    l.nombre  AS localidad,
    d.nombre  AS departamento,
    pr.nombre AS provincia,
    ROUND((ST_Distance(l.geom::geography, rp.geom_geog) / 1000.0)::NUMERIC, 3) AS distancia_parana_km
FROM sig_ae4.localidades l
JOIN sig_ae4.departamentos d ON l.departamento_id = d.id
JOIN sig_ae4.provincias pr   ON d.provincia_id = pr.id
CROSS JOIN rio_parana rp
WHERE pr.nombre = 'Misiones'
ORDER BY ST_Distance(l.geom::geography, rp.geom_geog) DESC
LIMIT 1;

\echo ============================================================================
\echo INCISO g2: TOP 5 LOCALIDADES DE MISIONES MAS ALEJADAS DEL RIO PARANA
\echo ============================================================================

-- Inciso g2: Top 5 localidades más alejadas para contexto espacial
WITH rio_parana AS (
    SELECT ST_Union(c.geom)::geography AS geom_geog
    FROM sig_ae4.cursos_agua c
    WHERE c.es_principal = TRUE
      AND c.nombre = 'Río Paraná'
)
SELECT
    ROW_NUMBER() OVER (ORDER BY ST_Distance(l.geom::geography, rp.geom_geog) DESC) AS ranking,
    l.codigo_bahra,
    l.nombre  AS localidad,
    d.nombre  AS departamento,
    ROUND((ST_Distance(l.geom::geography, rp.geom_geog) / 1000.0)::NUMERIC, 3) AS distancia_parana_km
FROM sig_ae4.localidades l
JOIN sig_ae4.departamentos d ON l.departamento_id = d.id
JOIN sig_ae4.provincias pr   ON d.provincia_id = pr.id
CROSS JOIN rio_parana rp
WHERE pr.nombre = 'Misiones'
ORDER BY distancia_parana_km DESC, l.nombre ASC
LIMIT 5;


-- =============================================================================
-- Inciso h: Proximidad a infraestructura lineal (transporte)
-- Distancia mínima en km desde cada localidad de Misiones hasta la Ruta Nacional
-- más cercana (RN12, RN14, RN101, RN105) usando CROSS JOIN LATERAL + <-> KNN +
-- ST_Distance(geography).
-- =============================================================================

\echo ============================================================================
\echo INCISO h1: DISTANCIA DE CADA LOCALIDAD DE MISIONES A RUTA NACIONAL MAS CERCANA
\echo ============================================================================

-- Inciso h1: KNN lateral con operador <-> sobre geography
SELECT
    l.codigo_bahra,
    l.nombre AS localidad,
    d.nombre AS departamento,
    COALESCE(NULLIF(rn.numero_ruta, ''), rn.nombre) AS ruta_nacional,
    rn.nombre AS nombre_ruta,
    ROUND((ST_Distance(l.geom::geography, rn.geom::geography) / 1000.0)::NUMERIC, 3) AS distancia_ruta_km
FROM sig_ae4.localidades l
JOIN sig_ae4.departamentos d ON l.departamento_id = d.id
JOIN sig_ae4.provincias pr   ON d.provincia_id = pr.id
CROSS JOIN LATERAL (
    SELECT
        r.id,
        r.nombre,
        r.numero_ruta,
        r.geom
    FROM sig_ae4.rutas r
    WHERE r.jurisdiccion = 'nacional'
      AND (
          r.numero_ruta IN ('12', '14', '101', '105', 'RN12', 'RN14', 'RN101', 'RN105')
          OR r.nombre IN (
              'RN12', 'RN14', 'RN101', 'RN105',
              'Ruta Nacional 12', 'Ruta Nacional 14', 'Ruta Nacional 101', 'Ruta Nacional 105'
          )
      )
    ORDER BY r.geom::geography <-> l.geom::geography
    LIMIT 1
) AS rn
WHERE pr.nombre = 'Misiones'
ORDER BY distancia_ruta_km ASC, l.nombre ASC;

\echo ============================================================================
\echo INCISO h2: RESUMEN DE ACCESIBILIDAD POR RUTA NACIONAL MAS CERCANA (MISIONES)
\echo ============================================================================

-- Inciso h2: Resumen estadístico por Ruta Nacional más cercana
WITH knn_misiones AS (
    SELECT
        l.id AS localidad_id,
        COALESCE(NULLIF(rn.numero_ruta, ''), rn.nombre) AS ruta_nacional,
        ST_Distance(l.geom::geography, rn.geom::geography) / 1000.0 AS distancia_km
    FROM sig_ae4.localidades l
    JOIN sig_ae4.departamentos d ON l.departamento_id = d.id
    JOIN sig_ae4.provincias pr   ON d.provincia_id = pr.id
    CROSS JOIN LATERAL (
        SELECT
            r.nombre,
            r.numero_ruta,
            r.geom
        FROM sig_ae4.rutas r
        WHERE r.jurisdiccion = 'nacional'
          AND (
              r.numero_ruta IN ('12', '14', '101', '105', 'RN12', 'RN14', 'RN101', 'RN105')
              OR r.nombre IN (
                  'RN12', 'RN14', 'RN101', 'RN105',
                  'Ruta Nacional 12', 'Ruta Nacional 14', 'Ruta Nacional 101', 'Ruta Nacional 105'
              )
          )
        ORDER BY r.geom::geography <-> l.geom::geography
        LIMIT 1
    ) AS rn
    WHERE pr.nombre = 'Misiones'
)
SELECT
    ruta_nacional,
    COUNT(*) AS cant_localidades,
    ROUND(MIN(distancia_km)::NUMERIC, 3) AS dist_min_km,
    ROUND(AVG(distancia_km)::NUMERIC, 3) AS dist_prom_km,
    ROUND(MAX(distancia_km)::NUMERIC, 3) AS dist_max_km
FROM knn_misiones
GROUP BY ruta_nacional
ORDER BY cant_localidades DESC, ruta_nacional ASC;


-- =============================================================================
-- Inciso i: Filtrado por umbral métrico (< 200 km)
-- Localidades dentro de 200 km (200000 m) del Río Paraná mediante ST_DWithin
-- sobre geography.
-- =============================================================================

\echo ============================================================================
\echo INCISO i1: LOCALIDADES DE MISIONES A MENOS DE 200 KM DEL RIO PARANA
\echo ============================================================================

-- Inciso i1: Detalle en Misiones con ST_DWithin(..., 200000)
WITH rio_parana AS (
    SELECT ST_Union(c.geom)::geography AS geom_geog
    FROM sig_ae4.cursos_agua c
    WHERE c.es_principal = TRUE
      AND c.nombre = 'Río Paraná'
)
SELECT
    l.codigo_bahra,
    l.nombre AS localidad,
    d.nombre AS departamento,
    ROUND((ST_Distance(l.geom::geography, rp.geom_geog) / 1000.0)::NUMERIC, 3) AS distancia_parana_km
FROM sig_ae4.localidades l
JOIN sig_ae4.departamentos d ON l.departamento_id = d.id
JOIN sig_ae4.provincias pr   ON d.provincia_id = pr.id
CROSS JOIN rio_parana rp
WHERE pr.nombre = 'Misiones'
  AND ST_DWithin(l.geom::geography, rp.geom_geog, 200000.0)
ORDER BY distancia_parana_km ASC, l.nombre ASC;

\echo ============================================================================
\echo INCISO i2: RESUMEN PROVINCIAL EN ARGENTINA (LOCALIDADES < 200 KM DEL RIO PARANA)
\echo ============================================================================

-- Inciso i2: Resumen por provincia argentina utilizando ST_DWithin(..., 200000)
WITH rio_parana AS (
    SELECT ST_Union(c.geom)::geography AS geom_geog
    FROM sig_ae4.cursos_agua c
    WHERE c.es_principal = TRUE
      AND c.nombre = 'Río Paraná'
)
SELECT
    pr.nombre AS provincia,
    pr.region,
    COUNT(*) AS total_localidades_provincia,
    COUNT(*) FILTER (
        WHERE ST_DWithin(l.geom::geography, rp.geom_geog, 200000.0)
    ) AS localidades_menor_200km,
    ROUND(
        (100.0 * COUNT(*) FILTER (WHERE ST_DWithin(l.geom::geography, rp.geom_geog, 200000.0))
         / NULLIF(COUNT(*), 0))::NUMERIC,
        2
    ) AS pct_provincia_en_200km,
    ROUND(
        (MIN(ST_Distance(l.geom::geography, rp.geom_geog)) FILTER (
            WHERE ST_DWithin(l.geom::geography, rp.geom_geog, 200000.0)
        ) / 1000.0)::NUMERIC,
        3
    ) AS dist_min_km,
    ROUND(
        (MAX(ST_Distance(l.geom::geography, rp.geom_geog)) FILTER (
            WHERE ST_DWithin(l.geom::geography, rp.geom_geog, 200000.0)
        ) / 1000.0)::NUMERIC,
        3
    ) AS dist_max_dentro_200km_km
FROM sig_ae4.localidades l
JOIN sig_ae4.departamentos d ON l.departamento_id = d.id
JOIN sig_ae4.provincias pr   ON d.provincia_id = pr.id
CROSS JOIN rio_parana rp
GROUP BY pr.id, pr.nombre, pr.region
HAVING COUNT(*) FILTER (WHERE ST_DWithin(l.geom::geography, rp.geom_geog, 200000.0)) > 0
ORDER BY localidades_menor_200km DESC, dist_min_km ASC;
