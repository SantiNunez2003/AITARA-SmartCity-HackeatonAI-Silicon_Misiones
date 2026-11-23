-- =============================================================================
-- AE4 SIG — Fase II: Consultas Espaciales de Autoría (Escala Urbana — Posadas)
-- Stack: PostgreSQL 16 + PostGIS 3.4
-- Esquema: sig_ae4 (según ae4_sig/sql/00_init.sql)
--
-- Convenciones generales:
--   1. Todas las distancias y áreas se calculan sobre geom_m (EPSG:5348,
--      POSGAR 2007 / Argentina Faja 6, unidades en metros).
--   2. Las capas para visualización directa en QGIS DB Manager exponen un `id`
--      único y la geometría `geom` en EPSG:4326 (WGS84).
--   3. Separación estricta de origen de siniestros:
--      - origen = 'real'     : siniestros reales relevados (sin dato llovia).
--      - origen = 'simulado' : simulaciones sintéticas AITARA (con llovia).
-- =============================================================================


-- =============================================================================
-- AUTORÍA 1 — INCORPORACIÓN
-- Intersecciones OSM en zona escolar sobre avenidas de mano única sin semáforo
-- =============================================================================
-- Planteamiento del problema:
--   Identificar cruces viales críticos en entornos escolares sobre avenidas de
--   sentido único (mayor velocidad de flujo vehicular y maniobras de cruce
--   complejas) que actualmente carecen de semaforización oficial (IDE Posadas).
--
-- Decisión municipal que respalda:
--   Priorizar dónde instalar nuevos semáforos, sendas peatonales elevadas o
--   desplegar agentes de tránsito durante horarios escolares de entrada/salida
--   (06:45-07:45, 11:45-13:15 y 17:15-18:45).
--
-- Reglas espaciales y de calidad:
--   - Intersección OSM <= 150 m de al menos una escuela IDE (geom_m, EPSG:5348).
--   - Intersección OSM <= 25 m de una avenida de mano única IDE (geom_m).
--   - Ausencia de semáforo IDE dentro de 30 m (NOT EXISTS + ST_DWithin).
--   - JOIN LATERAL (... LIMIT 1) garantiza unicidad de i.id y geom para QGIS
--     DB Manager aun cuando existan múltiples escuelas o tramos cercanos.
-- =============================================================================

WITH candidatas AS (
    SELECT
        i.id,
        i.nombre,
        i.subtipo,
        esc.escuela_cercana,
        esc.sector_escuela,
        esc.dist_escuela_m,
        ave.avenida_mano_unica,
        ave.sentido_avenida,
        stats.siniestros_pico_real,
        stats.siniestros_pico_simulado,
        stats.siniestros_totales_50m_real,
        stats.siniestros_totales_50m_simulado,
        stats.siniestros_corredor_250m_real,
        stats.siniestros_corredor_250m_simulado,
        i.geom
    FROM sig_ae4.intersecciones i
    JOIN LATERAL (
        SELECT
            e.nombre AS escuela_cercana,
            e.sector AS sector_escuela,
            ROUND(ST_Distance(i.geom_m, e.geom_m)::numeric, 1) AS dist_escuela_m
        FROM sig_ae4.escuelas e
        WHERE e.geom_m IS NOT NULL
          AND ST_DWithin(i.geom_m, e.geom_m, 150.0)
        ORDER BY i.geom_m <-> e.geom_m
        LIMIT 1
    ) esc ON TRUE
    JOIN LATERAL (
        SELECT
            a.nombre  AS avenida_mano_unica,
            a.sentido AS sentido_avenida
        FROM sig_ae4.avenidas_mano_unica a
        WHERE a.geom_m IS NOT NULL
          AND ST_DWithin(i.geom_m, a.geom_m, 25.0)
        ORDER BY i.geom_m <-> a.geom_m
        LIMIT 1
    ) ave ON TRUE
    CROSS JOIN LATERAL (
        SELECT
            COUNT(*) FILTER (
                WHERE inc.origen = 'real'
                  AND ST_DWithin(i.geom_m, inc.geom_m, 50.0)
                  AND (
                      inc.fecha_evento::time BETWEEN TIME '06:45:00' AND TIME '07:45:00'
                   OR inc.fecha_evento::time BETWEEN TIME '11:45:00' AND TIME '13:15:00'
                   OR inc.fecha_evento::time BETWEEN TIME '17:15:00' AND TIME '18:45:00'
                  )
            ) AS siniestros_pico_real,
            COUNT(*) FILTER (
                WHERE inc.origen = 'simulado'
                  AND ST_DWithin(i.geom_m, inc.geom_m, 50.0)
                  AND (
                      inc.fecha_evento::time BETWEEN TIME '06:45:00' AND TIME '07:45:00'
                   OR inc.fecha_evento::time BETWEEN TIME '11:45:00' AND TIME '13:15:00'
                   OR inc.fecha_evento::time BETWEEN TIME '17:15:00' AND TIME '18:45:00'
                  )
            ) AS siniestros_pico_simulado,
            COUNT(*) FILTER (WHERE inc.origen = 'real' AND ST_DWithin(i.geom_m, inc.geom_m, 50.0))     AS siniestros_totales_50m_real,
            COUNT(*) FILTER (WHERE inc.origen = 'simulado' AND ST_DWithin(i.geom_m, inc.geom_m, 50.0)) AS siniestros_totales_50m_simulado,
            COUNT(*) FILTER (WHERE inc.origen = 'real')     AS siniestros_corredor_250m_real,
            COUNT(*) FILTER (WHERE inc.origen = 'simulado') AS siniestros_corredor_250m_simulado
        FROM sig_ae4.incidentes_viales inc
        WHERE inc.geom_m IS NOT NULL
          AND ST_DWithin(i.geom_m, inc.geom_m, 250.0)
          AND (
              ST_DWithin(i.geom_m, inc.geom_m, 50.0)
              OR ST_DWithin(i.geom_m, inc.geom_m, 250.0)
          )
    ) stats
    WHERE i.geom_m IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM sig_ae4.semaforos s
          WHERE s.geom_m IS NOT NULL
            AND ST_DWithin(i.geom_m, s.geom_m, 30.0)
      )
)
SELECT
    id,
    nombre,
    subtipo,
    escuela_cercana,
    sector_escuela,
    dist_escuela_m,
    avenida_mano_unica,
    sentido_avenida,
    siniestros_pico_real,
    siniestros_pico_simulado,
    siniestros_totales_50m_real,
    siniestros_totales_50m_simulado,
    siniestros_corredor_250m_real,
    siniestros_corredor_250m_simulado,
    (siniestros_pico_real * 10 + siniestros_pico_simulado) AS puntaje_prioridad,
    geom
FROM candidatas
ORDER BY
    (siniestros_pico_real * 10 + siniestros_pico_simulado) DESC,
    siniestros_totales_50m_simulado DESC,
    siniestros_corredor_250m_real DESC,
    siniestros_corredor_250m_simulado DESC,
    dist_escuela_m ASC;


-- =============================================================================
-- AUTORÍA 2 — MANTENIMIENTO (Parte 2A)
-- Sensibilidad a lluvia por nivel de drenaje experto (AITARA) y origen
-- =============================================================================
-- Planteamiento del problema:
--   Evaluar si los corredores con menor capacidad de drenaje concentran una
--   tasa desproporcionada de siniestros bajo condiciones de lluvia respecto a
--   condiciones secas, normalizando por horas de exposición climática.
--
-- Decisión municipal que respalda:
--   Planificar limpieza preventiva de sumideros, obras de desagüe pluvial y
--   bacheo hidráulico según prioridad de riesgo bajo lluvia.
--
-- Notas metodológicas explícitas:
--   1. `nivel_drenaje` ('ALTO', 'MEDIO', 'BAJO') es un atributo experto
--      proveniente de `nodos_referencia_aitara` (no proviene de IDE Posadas).
--   2. Los incidentes reales (`origen = 'real'`) carecen de indicador de lluvia
--      (`llovia IS NULL`), por lo cual sus conteos de lluvia/seco resultan 0 y
--      las tasas/razón de riesgo se separan estrictamente de los simulados.
--   3. Se utiliza `nodo_referencia_id` asignado por trigger y, como respaldo si
--      fuera NULL, el nodo más cercano dentro de 500 m (sin duplicar conteos).
-- =============================================================================

WITH origenes AS (
    SELECT unnest(ARRAY['real', 'simulado']) AS origen
),
inc_resueltos AS (
    SELECT
        inc.id,
        inc.origen,
        inc.llovia,
        inc.severidad,
        COALESCE(
            inc.nodo_referencia_id,
            (
                SELECT n_fb.id
                FROM sig_ae4.nodos_referencia_aitara n_fb
                WHERE n_fb.geom_m IS NOT NULL
                  AND inc.geom_m IS NOT NULL
                  AND ST_DWithin(inc.geom_m, n_fb.geom_m, 500.0)
                ORDER BY inc.geom_m <-> n_fb.geom_m
                LIMIT 1
            )
        ) AS nodo_id
    FROM sig_ae4.incidentes_viales inc
),
clima AS (
    SELECT
        MAX(horas_por_nodo) FILTER (WHERE condicion = 'lluvia') AS horas_lluvia_por_nodo,
        MAX(horas_por_nodo) FILTER (WHERE condicion = 'seco')   AS horas_seco_por_nodo
    FROM sig_ae4.exposicion_clima
),
agregado AS (
    SELECT
        n.nivel_drenaje,
        o.origen,
        COUNT(DISTINCT n.id)                                             AS nodos_en_nivel,
        COUNT(ir.id)                                                     AS total_siniestros,
        COUNT(ir.id) FILTER (WHERE ir.llovia IS TRUE)                    AS siniestros_lluvia,
        COUNT(ir.id) FILTER (WHERE ir.llovia IS FALSE)                   AS siniestros_seco,
        COUNT(ir.id) FILTER (WHERE ir.llovia IS NULL)                    AS siniestros_sin_dato_lluvia,
        ROUND(AVG(ir.severidad) FILTER (WHERE ir.llovia IS TRUE)::numeric, 2)  AS severidad_prom_lluvia,
        ROUND(AVG(ir.severidad) FILTER (WHERE ir.llovia IS FALSE)::numeric, 2) AS severidad_prom_seco,
        (c.horas_lluvia_por_nodo * COUNT(DISTINCT n.id))                 AS exposicion_lluvia_horas_nodo,
        (c.horas_seco_por_nodo   * COUNT(DISTINCT n.id))                 AS exposicion_seco_horas_nodo
    FROM sig_ae4.nodos_referencia_aitara n
    CROSS JOIN origenes o
    CROSS JOIN clima c
    LEFT JOIN inc_resueltos ir
      ON ir.nodo_id = n.id
     AND ir.origen  = o.origen
    GROUP BY
        n.nivel_drenaje,
        o.origen,
        c.horas_lluvia_por_nodo,
        c.horas_seco_por_nodo
)
SELECT
    nivel_drenaje,
    origen,
    nodos_en_nivel,
    total_siniestros,
    siniestros_lluvia,
    siniestros_seco,
    siniestros_sin_dato_lluvia,
    exposicion_lluvia_horas_nodo,
    exposicion_seco_horas_nodo,
    ROUND((siniestros_lluvia * 1000.0 / NULLIF(exposicion_lluvia_horas_nodo, 0))::numeric, 3) AS tasa_lluvia_1000h,
    ROUND((siniestros_seco   * 1000.0 / NULLIF(exposicion_seco_horas_nodo,   0))::numeric, 3) AS tasa_seco_1000h,
    ROUND(
        (
            (siniestros_lluvia * 1000.0 / NULLIF(exposicion_lluvia_horas_nodo, 0))
            / NULLIF(siniestros_seco * 1000.0 / NULLIF(exposicion_seco_horas_nodo, 0), 0)
        )::numeric,
        2
    ) AS razon_riesgo_lluvia_vs_seco,
    severidad_prom_lluvia,
    severidad_prom_seco
FROM agregado
ORDER BY
    origen ASC,
    CASE nivel_drenaje
        WHEN 'BAJO'  THEN 1
        WHEN 'MEDIO' THEN 2
        WHEN 'ALTO'  THEN 3
        ELSE 4
    END;


-- =============================================================================
-- AUTORÍA 2 — MANTENIMIENTO (Parte 2B: Capa visualizable por tramo de calle)
-- Ranking de calles OSM con marca de obra IDE `asfalto_sobre_empedrado`
-- =============================================================================
-- Planteamiento del problema:
--   Detectar tramos viales (calles OSM) con mayor concentración y severidad de
--   siniestros en condiciones húmedas, identificando si cuentan o no con obra
--   de repavimentación (`asfalto_sobre_empedrado` IDE Posadas dentro de 25 m).
--
-- Decisión municipal que respalda:
--   Priorizar mantenimiento de calzada, fresado/repavimentación o mejora de
--   adherencia y señalización horizontal en los 30 corredores más críticos.
--
-- Nota de visualización QGIS DB Manager:
--   Devuelve `c.id` único y `c.geom` (MultiLineString, EPSG:4326).
--   El puntaje `puntaje_sensibilidad_lluvia` pondera la severidad acumulada en
--   lluvia por la proporción de siniestros ocurridos con lluvia sobre aquellos
--   que poseen dato climático (`llovia IS NOT NULL`, es decir, simulados).
-- =============================================================================

SELECT
    c.id,
    c.nombre,
    ROUND((ST_Length(c.geom_m) / 1000.0)::numeric, 2) AS longitud_km,
    EXISTS (
        SELECT 1
        FROM sig_ae4.asfalto_sobre_empedrado ase
        WHERE ase.geom_m IS NOT NULL
          AND ST_DWithin(c.geom_m, ase.geom_m, 25.0)
    ) AS tiene_asfalto_sobre_empedrado,
    stats.siniestros_real_sin_clima,
    stats.siniestros_real_lluvia,
    stats.siniestros_real_seco,
    stats.siniestros_real_total,
    stats.siniestros_sim_lluvia,
    stats.siniestros_sim_seco,
    stats.siniestros_sim_total,
    stats.siniestros_lluvia,
    stats.siniestros_totales_40m,
    stats.severidad_acumulada_lluvia,
    stats.severidad_prom_lluvia,
    stats.puntaje_sensibilidad_lluvia,
    c.geom
FROM sig_ae4.calles c
CROSS JOIN LATERAL (
    SELECT
        COUNT(*) FILTER (WHERE inc.origen = 'real'     AND inc.llovia IS NULL)  AS siniestros_real_sin_clima,
        COUNT(*) FILTER (WHERE inc.origen = 'real'     AND inc.llovia IS TRUE)  AS siniestros_real_lluvia,
        COUNT(*) FILTER (WHERE inc.origen = 'real'     AND inc.llovia IS FALSE) AS siniestros_real_seco,
        COUNT(*) FILTER (WHERE inc.origen = 'real')                             AS siniestros_real_total,
        COUNT(*) FILTER (WHERE inc.origen = 'simulado' AND inc.llovia IS TRUE)  AS siniestros_sim_lluvia,
        COUNT(*) FILTER (WHERE inc.origen = 'simulado' AND inc.llovia IS FALSE) AS siniestros_sim_seco,
        COUNT(*) FILTER (WHERE inc.origen = 'simulado')                         AS siniestros_sim_total,
        COUNT(*) FILTER (WHERE inc.llovia IS TRUE)                              AS siniestros_lluvia,
        COUNT(*)                                                                AS siniestros_totales_40m,
        COALESCE(SUM(inc.severidad) FILTER (WHERE inc.llovia IS TRUE), 0)       AS severidad_acumulada_lluvia,
        ROUND(AVG(inc.severidad) FILTER (WHERE inc.llovia IS TRUE)::numeric, 2) AS severidad_prom_lluvia,
        ROUND(
            (
                COALESCE(SUM(inc.severidad) FILTER (WHERE inc.llovia IS TRUE), 0)
                * COALESCE(
                    COUNT(*) FILTER (WHERE inc.llovia IS TRUE)::numeric
                    / NULLIF(COUNT(*) FILTER (WHERE inc.llovia IS NOT NULL), 0),
                    0
                )
            )::numeric,
            2
        ) AS puntaje_sensibilidad_lluvia
    FROM sig_ae4.incidentes_viales inc
    WHERE inc.geom_m IS NOT NULL
      AND ST_DWithin(c.geom_m, inc.geom_m, 40.0)
) stats
WHERE c.geom_m IS NOT NULL
  AND stats.siniestros_totales_40m > 0
ORDER BY
    stats.siniestros_lluvia DESC,
    stats.siniestros_totales_40m DESC,
    stats.puntaje_sensibilidad_lluvia DESC
LIMIT 30;


-- =============================================================================
-- AUTORÍA 2 — MANTENIMIENTO (Parte 2C: Resumen comparativo de repavimentación)
-- Comparación global: corredores con `asfalto_sobre_empedrado` vs. sin obra
-- =============================================================================
-- Planteamiento:
--   Comparar sobre la totalidad de `sig_ae4.calles` (sin sesgo de LIMIT 30) la
--   densidad de siniestros por km y el comportamiento bajo lluvia entre tramos
--   repavimentados (`asfalto_sobre_empedrado` <= 25 m) y el resto de la red.
--   Nota: Un incidente próximo a una esquina puede contabilizarse dentro del
--   buffer de 40 m de ambas calles concurrentes, por lo que los indicadores se
--   interpretan de forma relativa entre ambos grupos de corredores.
-- =============================================================================

WITH clima AS (
    SELECT
        MAX(horas_por_nodo) FILTER (WHERE condicion = 'lluvia') AS horas_lluvia,
        MAX(horas_por_nodo) FILTER (WHERE condicion = 'seco')   AS horas_seco
    FROM sig_ae4.exposicion_clima
),
calles_evaluadas AS (
    SELECT
        c.id,
        ST_Length(c.geom_m) / 1000.0 AS longitud_km,
        EXISTS (
            SELECT 1
            FROM sig_ae4.asfalto_sobre_empedrado ase
            WHERE ase.geom_m IS NOT NULL
              AND ST_DWithin(c.geom_m, ase.geom_m, 25.0)
        ) AS tiene_asfalto_sobre_empedrado,
        stats.siniestros_real,
        stats.siniestros_sim_lluvia,
        stats.siniestros_sim_seco,
        stats.siniestros_sim_total,
        stats.siniestros_totales,
        stats.suma_sev_lluvia,
        stats.cnt_sev_lluvia,
        stats.suma_sev_seco,
        stats.cnt_sev_seco
    FROM sig_ae4.calles c
    CROSS JOIN LATERAL (
        SELECT
            COUNT(*) FILTER (WHERE inc.origen = 'real')                             AS siniestros_real,
            COUNT(*) FILTER (WHERE inc.origen = 'simulado' AND inc.llovia IS TRUE)  AS siniestros_sim_lluvia,
            COUNT(*) FILTER (WHERE inc.origen = 'simulado' AND inc.llovia IS FALSE) AS siniestros_sim_seco,
            COUNT(*) FILTER (WHERE inc.origen = 'simulado')                         AS siniestros_sim_total,
            COUNT(*)                                                                AS siniestros_totales,
            COALESCE(SUM(inc.severidad) FILTER (WHERE inc.llovia IS TRUE), 0)       AS suma_sev_lluvia,
            COUNT(*) FILTER (WHERE inc.llovia IS TRUE AND inc.severidad IS NOT NULL)  AS cnt_sev_lluvia,
            COALESCE(SUM(inc.severidad) FILTER (WHERE inc.llovia IS FALSE), 0)      AS suma_sev_seco,
            COUNT(*) FILTER (WHERE inc.llovia IS FALSE AND inc.severidad IS NOT NULL) AS cnt_sev_seco
        FROM sig_ae4.incidentes_viales inc
        WHERE inc.geom_m IS NOT NULL
          AND ST_DWithin(c.geom_m, inc.geom_m, 40.0)
    ) stats
    WHERE c.geom_m IS NOT NULL
)
SELECT
    ce.tiene_asfalto_sobre_empedrado,
    COUNT(*)                                                                    AS cantidad_calles,
    ROUND(SUM(ce.longitud_km)::numeric, 2)                                      AS longitud_total_km,
    SUM(ce.siniestros_real)                                                     AS siniestros_real,
    SUM(ce.siniestros_sim_lluvia)                                               AS siniestros_sim_lluvia,
    SUM(ce.siniestros_sim_seco)                                                 AS siniestros_sim_seco,
    SUM(ce.siniestros_totales)                                                  AS siniestros_totales,
    ROUND((SUM(ce.siniestros_real)       / NULLIF(SUM(ce.longitud_km), 0))::numeric, 2) AS siniestros_real_por_km,
    ROUND((SUM(ce.siniestros_sim_lluvia) / NULLIF(SUM(ce.longitud_km), 0))::numeric, 2) AS siniestros_sim_lluvia_por_km,
    ROUND((SUM(ce.siniestros_sim_seco)   / NULLIF(SUM(ce.longitud_km), 0))::numeric, 2) AS siniestros_sim_seco_por_km,
    ROUND((SUM(ce.siniestros_sim_lluvia) * 100.0 / NULLIF(SUM(ce.siniestros_sim_total), 0))::numeric, 1) AS pct_lluvia_en_simulados,
    ROUND(
        (
            (SUM(ce.siniestros_sim_lluvia) / NULLIF(MAX(cl.horas_lluvia), 0))
            / NULLIF(SUM(ce.siniestros_sim_seco) / NULLIF(MAX(cl.horas_seco), 0), 0)
        )::numeric,
        2
    ) AS razon_riesgo_sim_lluvia_vs_seco,
    ROUND((SUM(ce.suma_sev_lluvia)::numeric / NULLIF(SUM(ce.cnt_sev_lluvia), 0)), 2) AS severidad_prom_lluvia,
    ROUND((SUM(ce.suma_sev_seco)::numeric   / NULLIF(SUM(ce.cnt_sev_seco),   0)), 2) AS severidad_prom_seco
FROM calles_evaluadas ce
CROSS JOIN clima cl
GROUP BY ce.tiene_asfalto_sobre_empedrado
ORDER BY ce.tiene_asfalto_sobre_empedrado DESC;


-- =============================================================================
-- AUTORÍA 3 — COBERTURA
-- Brecha de infraestructura vial por delegación municipal de Posadas
-- =============================================================================
-- Planteamiento del problema:
--   Medir la inequidad territorial entre las 12 delegaciones municipales de
--   Posadas comparando la oferta de infraestructura vial (semáforos IDE,
--   paradas con refugio IDE, intersecciones OSM y establecimientos educativos)
--   frente a la densidad de siniestralidad real y simulada.
--
-- Decisión municipal que respalda:
--   Asignar presupuesto de obra pública vial (semaforización y refugios) hacia
--   delegaciones con alta siniestralidad y déficit relativo de control vial.
--
-- Métrica transparente de brecha (`indice_brecha_prioridad`):
--   indice_brecha_prioridad = densidad_ponderada_km2 * factor_deficit_semaforos
--   donde:
--     - densidad_ponderada_km2 = (siniestros_real * 3.0 + siniestros_simulado) / area_km2
--       (pondera 3x los siniestros reales observados respecto a los simulados).
--     - factor_deficit_semaforos = 1 / (1 + semaforos_cada_100_intersecciones / 10.0)
--       (vale 1.0 si hay 0 semáforos/100 intersecciones y decrece conforme mejora
--        la cobertura de semaforización).
--   Cada conteo espacial se evalúa en subconsulta independiente para evitar
--   producto cartesiano entre capas de puntos y garantizar los 12 polígonos.
-- =============================================================================

WITH base_delegaciones AS (
    SELECT
        d.id,
        d.nombre,
        (ST_Area(d.geom_m) / 1000000.0) AS area_km2_raw,
        d.poblacion_2022,
        (
            SELECT COUNT(*)
            FROM sig_ae4.intersecciones i
            WHERE i.geom_m IS NOT NULL
              AND ST_Within(i.geom_m, d.geom_m)
        ) AS intersecciones_osm,
        (
            SELECT COUNT(*)
            FROM sig_ae4.semaforos s
            WHERE s.geom_m IS NOT NULL
              AND ST_Within(s.geom_m, d.geom_m)
        ) AS semaforos_ide,
        (
            SELECT COUNT(*)
            FROM sig_ae4.paradas p
            WHERE p.geom_m IS NOT NULL
              AND ST_Within(p.geom_m, d.geom_m)
        ) AS paradas_con_refugio,
        (
            SELECT COUNT(*)
            FROM sig_ae4.escuelas e
            WHERE e.geom_m IS NOT NULL
              AND ST_Within(e.geom_m, d.geom_m)
        ) AS escuelas_ide,
        inc_stats.siniestros_real,
        inc_stats.siniestros_simulado,
        d.geom
    FROM sig_ae4.delegaciones d
    CROSS JOIN LATERAL (
        SELECT
            COUNT(*) FILTER (WHERE inc.origen = 'real')     AS siniestros_real,
            COUNT(*) FILTER (WHERE inc.origen = 'simulado') AS siniestros_simulado
        FROM sig_ae4.incidentes_viales inc
        WHERE inc.geom_m IS NOT NULL
          AND ST_Within(inc.geom_m, d.geom_m)
    ) inc_stats
    WHERE d.geom_m IS NOT NULL
),
metricas AS (
    SELECT
        id,
        nombre,
        ROUND(area_km2_raw::numeric, 2) AS area_km2,
        poblacion_2022,
        intersecciones_osm,
        semaforos_ide,
        ROUND((semaforos_ide * 100.0 / NULLIF(intersecciones_osm, 0))::numeric, 2) AS semaforos_cada_100_intersecciones,
        paradas_con_refugio,
        escuelas_ide,
        siniestros_real,
        siniestros_simulado,
        ROUND((siniestros_real     / NULLIF(area_km2_raw, 0))::numeric, 2) AS densidad_siniestros_km2_real,
        ROUND((siniestros_simulado / NULLIF(area_km2_raw, 0))::numeric, 2) AS densidad_siniestros_km2_simulado,
        ROUND(
            (
                ((siniestros_real * 3.0 + siniestros_simulado) / NULLIF(area_km2_raw, 0))
                * (1.0 / (1.0 + COALESCE((semaforos_ide * 100.0 / NULLIF(intersecciones_osm, 0)) / 10.0, 0)))
            )::numeric,
            2
        ) AS indice_brecha_prioridad,
        geom
    FROM base_delegaciones
)
SELECT
    id,
    nombre,
    area_km2,
    poblacion_2022,
    intersecciones_osm,
    semaforos_ide,
    semaforos_cada_100_intersecciones,
    paradas_con_refugio,
    escuelas_ide,
    siniestros_real,
    siniestros_simulado,
    densidad_siniestros_km2_real,
    densidad_siniestros_km2_simulado,
    indice_brecha_prioridad,
    geom
FROM metricas
ORDER BY
    densidad_siniestros_km2_real DESC,
    densidad_siniestros_km2_simulado DESC,
    semaforos_cada_100_intersecciones ASC;
