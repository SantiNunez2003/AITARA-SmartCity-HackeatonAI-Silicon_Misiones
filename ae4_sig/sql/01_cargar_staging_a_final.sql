-- =============================================================================
-- AE4 SIG — Fase I: Normalización e inserción desde `staging.*` hacia `sig_ae4.*`
-- Compatibilidad: PostgreSQL 16 + PostGIS 3.4 (vía psycopg2 o psql)
-- Prerrequisito: `ae4_sig/scripts/cargar_ign_ide.py` cargó las tablas `staging.*`.
--
-- Transformaciones espaciales aplicadas en SQL:
--   - ST_SetSRID(ST_GeomFromGeoJSON(geom_json), 4326) : GeoJSON -> Geometría WGS84
--   - ST_Force2D                                       : elimina coordenada Z si existe
--   - ST_MakeValid                                     : repara autointersecciones
--   - ST_CollectionExtract(..., 2 | 3)                 : extrae líneas (2) o polígonos (3)
--   - ST_Multi                                         : promueve a Multi*
--   - ST_GeometryN(..., 1)                             : extrae Point desde MultiPoint
--   - ST_Transform(..., 5348)                          : reproyecta a POSGAR 2007 Faja 6
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 0. LIMPIEZA IDEMPOTENTE DE TABLAS DESTINO
-- -----------------------------------------------------------------------------
TRUNCATE sig_ae4.incidentes_viales,
         sig_ae4.localidades,
         sig_ae4.departamentos,
         sig_ae4.provincias,
         sig_ae4.paises,
         sig_ae4.cursos_agua,
         sig_ae4.rutas,
         sig_ae4.delegaciones,
         sig_ae4.semaforos,
         sig_ae4.escuelas,
         sig_ae4.paradas,
         sig_ae4.avenidas_mano_unica,
         sig_ae4.asfalto_sobre_empedrado,
         sig_ae4.ciclovias
RESTART IDENTITY CASCADE;

-- -----------------------------------------------------------------------------
-- 1. PAÍSES DE SUDAMÉRICA (Natural Earth 50m -> sig_ae4.paises)
-- -----------------------------------------------------------------------------
INSERT INTO sig_ae4.paises (
    codigo_iso3,
    nombre,
    subregion,
    poblacion,
    geom
)
SELECT
    TRIM(s.codigo_iso3) AS codigo_iso3,
    CASE TRIM(s.nombre)
        WHEN 'Brazil'   THEN 'Brasil'
        WHEN 'Peru'     THEN 'Perú'
        WHEN 'Suriname' THEN 'Surinam'
        ELSE TRIM(s.nombre)
    END AS nombre,
    NULLIF(TRIM(s.subregion), '') AS subregion,
    s.poblacion,
    ST_Multi(
        ST_CollectionExtract(
            ST_MakeValid(
                ST_Force2D(
                    ST_SetSRID(ST_GeomFromGeoJSON(s.geom_json), 4326)
                )
            ),
            3
        )
    ) AS geom
FROM staging.ne_paises s;

-- -----------------------------------------------------------------------------
-- 2. PROVINCIAS ARGENTINAS (IGN + INDEC Censo 2022 -> sig_ae4.provincias)
-- -----------------------------------------------------------------------------
INSERT INTO sig_ae4.provincias (
    codigo_indec,
    nombre,
    nombre_completo,
    region,
    poblacion,
    pais_id,
    geom
)
SELECT
    TRIM(s.in1) AS codigo_indec,
    TRIM(s.nam) AS nombre,
    NULLIF(TRIM(s.fna), '') AS nombre_completo,
    CASE TRIM(s.in1)
        WHEN '02' THEN 'AMBA'
        WHEN '06' THEN 'Centro / Pampeana'
        WHEN '10' THEN 'NOA'
        WHEN '14' THEN 'Centro / Pampeana'
        WHEN '18' THEN 'NEA'
        WHEN '22' THEN 'NEA'
        WHEN '26' THEN 'Patagonia'
        WHEN '30' THEN 'Centro / Pampeana'
        WHEN '34' THEN 'NEA'
        WHEN '38' THEN 'NOA'
        WHEN '42' THEN 'Centro / Pampeana'
        WHEN '46' THEN 'NOA'
        WHEN '50' THEN 'Cuyo'
        WHEN '54' THEN 'NEA'
        WHEN '58' THEN 'Patagonia'
        WHEN '62' THEN 'Patagonia'
        WHEN '66' THEN 'NOA'
        WHEN '70' THEN 'Cuyo'
        WHEN '74' THEN 'Cuyo'
        WHEN '78' THEN 'Patagonia'
        WHEN '82' THEN 'Centro / Pampeana'
        WHEN '86' THEN 'NOA'
        WHEN '90' THEN 'NOA'
        WHEN '94' THEN 'Patagonia'
        ELSE 'Sin clasificar'
    END AS region,
    CASE TRIM(s.in1)
        WHEN '02' THEN 3121707::BIGINT
        WHEN '06' THEN 17523996::BIGINT
        WHEN '10' THEN 429562::BIGINT
        WHEN '14' THEN 3840905::BIGINT
        WHEN '18' THEN 1197553::BIGINT
        WHEN '22' THEN 1142963::BIGINT
        WHEN '26' THEN 603120::BIGINT
        WHEN '30' THEN 1425578::BIGINT
        WHEN '34' THEN 606041::BIGINT
        WHEN '38' THEN 797955::BIGINT
        WHEN '42' THEN 361859::BIGINT
        WHEN '46' THEN 383865::BIGINT
        WHEN '50' THEN 2043540::BIGINT
        WHEN '54' THEN 1278873::BIGINT
        WHEN '58' THEN 726590::BIGINT
        WHEN '62' THEN 762067::BIGINT
        WHEN '66' THEN 1440672::BIGINT
        WHEN '70' THEN 818234::BIGINT
        WHEN '74' THEN 540905::BIGINT
        WHEN '78' THEN 337226::BIGINT
        WHEN '82' THEN 3544908::BIGINT
        WHEN '86' THEN 1054028::BIGINT
        WHEN '90' THEN 1731820::BIGINT
        WHEN '94' THEN 185732::BIGINT
        ELSE NULL::BIGINT
    END AS poblacion,
    p.id AS pais_id,
    ST_Multi(
        ST_CollectionExtract(
            ST_MakeValid(
                ST_Force2D(
                    ST_SetSRID(ST_GeomFromGeoJSON(s.geom_json), 4326)
                )
            ),
            3
        )
    ) AS geom
FROM staging.ign_provincias s
JOIN sig_ae4.paises p
  ON p.codigo_iso3 = 'ARG';

-- -----------------------------------------------------------------------------
-- 3. DEPARTAMENTOS / PARTIDOS / COMUNAS (IGN + INDEC 2022 Misiones)
-- -----------------------------------------------------------------------------
INSERT INTO sig_ae4.departamentos (
    codigo_indec,
    nombre,
    nombre_completo,
    poblacion,
    provincia_id,
    geom
)
SELECT
    TRIM(s.in1) AS codigo_indec,
    TRIM(s.nam) AS nombre,
    NULLIF(TRIM(s.fna), '') AS nombre_completo,
    CASE TRIM(s.in1)
        WHEN '54007' THEN 50597::BIGINT   -- Apóstoles
        WHEN '54014' THEN 59953::BIGINT   -- Cainguás
        WHEN '54021' THEN 35318::BIGINT   -- Candelaria
        WHEN '54028' THEN 392919::BIGINT  -- Capital
        WHEN '54035' THEN 10348::BIGINT   -- Concepción
        WHEN '54042' THEN 91728::BIGINT   -- Eldorado
        WHEN '54049' THEN 45570::BIGINT   -- General Manuel Belgrano
        WHEN '54056' THEN 77160::BIGINT   -- Guaraní
        WHEN '54063' THEN 100096::BIGINT  -- Iguazú
        WHEN '54070' THEN 49797::BIGINT   -- Leandro N. Alem
        WHEN '54077' THEN 52428::BIGINT   -- Libertador General San Martín
        WHEN '54084' THEN 38669::BIGINT   -- Montecarlo
        WHEN '54091' THEN 121701::BIGINT  -- Oberá
        WHEN '54098' THEN 63394::BIGINT   -- San Ignacio
        WHEN '54105' THEN 23503::BIGINT   -- San Javier
        WHEN '54112' THEN 34801::BIGINT   -- San Pedro
        WHEN '54119' THEN 30891::BIGINT   -- 25 de Mayo
        ELSE NULL::BIGINT
    END AS poblacion,
    pr.id AS provincia_id,
    ST_Multi(
        ST_CollectionExtract(
            ST_MakeValid(
                ST_Force2D(
                    ST_SetSRID(ST_GeomFromGeoJSON(s.geom_json), 4326)
                )
            ),
            3
        )
    ) AS geom
FROM staging.ign_departamentos s
JOIN sig_ae4.provincias pr
  ON LEFT(TRIM(s.in1), 2) = pr.codigo_indec;

-- -----------------------------------------------------------------------------
-- 4. LOCALIDADES BAHRA (IGN -> sig_ae4.localidades)
--    Resolución de departamento_id sin huérfanos:
--      1) Coincidencia exacta s.cod_depto = d.codigo_indec
--      2) Contención espacial ST_Within(pt, d.geom) (CABA / códigos actualizados)
--      3) Respaldo por departamento más cercano dentro de la misma provincia
-- -----------------------------------------------------------------------------
WITH loc_pts AS (
    SELECT
        TRIM(s.cod_ase) AS cod_ase,
        TRIM(s.fna) AS fna,
        NULLIF(TRIM(s.tipo_asent), '') AS tipo_asent,
        TRIM(s.cod_pcia) AS cod_pcia,
        TRIM(BOTH E' \t\r\n' FROM COALESCE(s.cod_depto, '')) AS cod_depto,
        ST_GeometryN(
            ST_MakeValid(
                ST_Force2D(
                    ST_SetSRID(ST_GeomFromGeoJSON(s.geom_json), 4326)
                )
            ),
            1
        ) AS pt
    FROM staging.ign_localidades s
)
INSERT INTO sig_ae4.localidades (
    codigo_bahra,
    nombre,
    tipo_asentamiento,
    es_capital_nacional,
    es_capital_provincial,
    departamento_id,
    geom
)
SELECT
    lp.cod_ase AS codigo_bahra,
    lp.fna AS nombre,
    lp.tipo_asent AS tipo_asentamiento,
    (lp.cod_ase = '02002010') AS es_capital_nacional,
    (lp.cod_ase IN (
        '06441030', '10049030', '14014010', '18021020', '22140060',
        '26077030', '30084160', '34014020', '38021060', '42021020',
        '46014010', '50007010', '54028030', '58035070', '62007090',
        '66028050', '70028010', '74056150', '78021040', '82063170',
        '86049110', '90084010', '94014020'
    )) AS es_capital_provincial,
    COALESCE(
        (
            SELECT d.id
            FROM sig_ae4.departamentos d
            WHERE d.codigo_indec = lp.cod_depto
            LIMIT 1
        ),
        (
            SELECT d.id
            FROM sig_ae4.departamentos d
            WHERE ST_Within(lp.pt, d.geom)
            ORDER BY d.codigo_indec
            LIMIT 1
        ),
        (
            SELECT d.id
            FROM sig_ae4.departamentos d
            WHERE d.codigo_indec LIKE lp.cod_pcia || '%'
            ORDER BY d.geom <-> lp.pt
            LIMIT 1
        )
    ) AS departamento_id,
    lp.pt AS geom
FROM loc_pts lp;

-- -----------------------------------------------------------------------------
-- 5. CURSOS DE AGUA (IGN -> sig_ae4.cursos_agua)
-- -----------------------------------------------------------------------------
INSERT INTO sig_ae4.cursos_agua (
    id_origen,
    nombre,
    nombre_corto,
    categoria,
    es_principal,
    geom
)
SELECT
    TRIM(s.gid) AS id_origen,
    COALESCE(NULLIF(TRIM(s.fna), ''), NULLIF(TRIM(s.nam), ''), TRIM(s.gid)) AS nombre,
    NULLIF(TRIM(s.nam), '') AS nombre_corto,
    COALESCE(NULLIF(TRIM(s.gna), ''), NULLIF(TRIM(s.objeto), '')) AS categoria,
    COALESCE(s.es_principal, FALSE) AS es_principal,
    ST_Multi(
        ST_CollectionExtract(
            ST_MakeValid(
                ST_Force2D(
                    ST_SetSRID(ST_GeomFromGeoJSON(s.geom_json), 4326)
                )
            ),
            2
        )
    ) AS geom
FROM staging.ign_cursos_agua s;

-- -----------------------------------------------------------------------------
-- 6. RED VIAL NACIONAL Y PROVINCIAL (IGN -> sig_ae4.rutas)
-- -----------------------------------------------------------------------------
INSERT INTO sig_ae4.rutas (
    id_origen,
    nombre,
    numero_ruta,
    jurisdiccion,
    superficie_calzada,
    geom
)
SELECT
    TRIM(s.id_origen) AS id_origen,
    CASE
        WHEN TRIM(s.jurisdiccion) = 'nacional'
            THEN 'RN ' || COALESCE(NULLIF(TRIM(s.numero_ruta), ''), 'S/N')
        ELSE 'RP ' || COALESCE(NULLIF(TRIM(s.numero_ruta), ''), 'S/N')
    END AS nombre,
    NULLIF(TRIM(s.numero_ruta), '') AS numero_ruta,
    TRIM(s.jurisdiccion) AS jurisdiccion,
    s.superficie_calzada,
    ST_Multi(
        ST_CollectionExtract(
            ST_MakeValid(
                ST_Force2D(
                    ST_SetSRID(ST_GeomFromGeoJSON(s.geom_json), 4326)
                )
            ),
            2
        )
    ) AS geom
FROM staging.ign_rutas s;

-- -----------------------------------------------------------------------------
-- 7. DELEGACIONES MUNICIPALES DE POSADAS + POBLACIÓN 2022 (IDE Posadas)
--    Nota: los IDs WFS superan 40 chars ('DELEGACIONES_MUNICIPALES_POSADAS_20250.10')
--    por lo que se compacta el prefijo manteniendo unicidad en VARCHAR(40).
-- -----------------------------------------------------------------------------
WITH deleg_clean AS (
    SELECT
        REPLACE(TRIM(d.id_ide), 'DELEGACIONES_MUNICIPALES_POSADAS_', 'DELEG_POSADAS_') AS id_ide,
        COALESCE(NULLIF(TRIM(d.nombre), ''), NULLIF(TRIM(d.descripcion), ''), TRIM(d.id_ide)) AS nombre,
        NULLIF(TRIM(d.descripcion), '') AS descripcion,
        ST_Multi(
            ST_CollectionExtract(
                ST_MakeValid(
                    ST_Force2D(
                        ST_SetSRID(ST_GeomFromGeoJSON(d.geom_json), 4326)
                    )
                ),
                3
            )
        ) AS geom
    FROM staging.ide_delegaciones d
),
radios_pts AS (
    SELECT
        COALESCE(r.poblacion_n, 0) AS poblacion_n,
        ST_PointOnSurface(
            ST_Multi(
                ST_CollectionExtract(
                    ST_MakeValid(
                        ST_Force2D(
                            ST_SetSRID(ST_GeomFromGeoJSON(r.geom_json), 4326)
                        )
                    ),
                    3
                )
            )
        ) AS pt
    FROM staging.ide_radios_censales r
)
INSERT INTO sig_ae4.delegaciones (
    id_ide,
    nombre,
    descripcion,
    poblacion_2022,
    geom,
    geom_m
)
SELECT
    dc.id_ide,
    dc.nombre,
    dc.descripcion,
    COALESCE(SUM(rp.poblacion_n), 0)::INTEGER AS poblacion_2022,
    dc.geom,
    ST_Transform(dc.geom, 5348) AS geom_m
FROM deleg_clean dc
LEFT JOIN radios_pts rp
  ON ST_Within(rp.pt, dc.geom)
GROUP BY dc.id_ide, dc.nombre, dc.descripcion, dc.geom;

-- -----------------------------------------------------------------------------
-- 8. SEMÁFOROS (IDE Posadas -> sig_ae4.semaforos)
-- -----------------------------------------------------------------------------
WITH sem_pts AS (
    SELECT
        TRIM(s.id_ide) AS id_ide,
        NULLIF(TRIM(s.calle_1), '') AS calle_1,
        NULLIF(TRIM(s.calle_2), '') AS calle_2,
        NULLIF(TRIM(s.estado), '') AS estado,
        NULLIF(TRIM(s.centralizado), '') AS centralizado,
        NULLIF(TRIM(s.peatonales), '') AS peatonales,
        ST_GeometryN(
            ST_MakeValid(
                ST_Force2D(
                    ST_SetSRID(ST_GeomFromGeoJSON(s.geom_json), 4326)
                )
            ),
            1
        ) AS geom
    FROM staging.ide_semaforos s
)
INSERT INTO sig_ae4.semaforos (
    id_ide,
    nombre,
    calle_1,
    calle_2,
    estado,
    centralizado,
    peatonales,
    geom,
    geom_m
)
SELECT
    id_ide,
    COALESCE(NULLIF(CONCAT_WS(' y ', calle_1, calle_2), ''), id_ide) AS nombre,
    calle_1,
    calle_2,
    estado,
    centralizado,
    peatonales,
    geom,
    ST_Transform(geom, 5348) AS geom_m
FROM sem_pts;

-- -----------------------------------------------------------------------------
-- 9. UNIDADES EDUCATIVAS / ESCUELAS (IDE Posadas -> sig_ae4.escuelas)
-- -----------------------------------------------------------------------------
WITH esc_pts AS (
    SELECT
        TRIM(s.id_ide) AS id_ide,
        NULLIF(TRIM(s.cueanexo), '') AS cueanexo,
        COALESCE(NULLIF(TRIM(s.nombre), ''), NULLIF(TRIM(s.nombrecort), ''), TRIM(s.id_ide)) AS nombre,
        NULLIF(TRIM(s.sector), '') AS sector,
        NULLIF(TRIM(s.calle), '') AS calle,
        NULLIF(TRIM(s.barrio), '') AS barrio,
        ST_GeometryN(
            ST_MakeValid(
                ST_Force2D(
                    ST_SetSRID(ST_GeomFromGeoJSON(s.geom_json), 4326)
                )
            ),
            1
        ) AS geom
    FROM staging.ide_escuelas s
)
INSERT INTO sig_ae4.escuelas (
    id_ide,
    cueanexo,
    nombre,
    sector,
    calle,
    barrio,
    geom,
    geom_m
)
SELECT
    id_ide,
    cueanexo,
    nombre,
    sector,
    calle,
    barrio,
    geom,
    ST_Transform(geom, 5348) AS geom_m
FROM esc_pts;

-- -----------------------------------------------------------------------------
-- 10. PARADAS Y REFUGIOS DE TRANSPORTE (IDE Posadas -> sig_ae4.paradas)
-- -----------------------------------------------------------------------------
WITH par_pts AS (
    SELECT
        TRIM(s.id_ide) AS id_ide,
        NULLIF(TRIM(s.codigo), '') AS codigo,
        COALESCE(
            NULLIF(TRIM(s.ubicacion), ''),
            NULLIF(CONCAT_WS(' y ', NULLIF(TRIM(s.ubi_calle), ''), NULLIF(TRIM(s.ubi_casi), '')), ''),
            NULLIF(TRIM(s.codigo), ''),
            TRIM(s.id_ide)
        ) AS nombre,
        NULLIF(TRIM(s.barrio), '') AS barrio,
        NULLIF(TRIM(s.activo), '') AS activo,
        NULLIF(TRIM(s.darsena), '') AS darsena,
        ST_GeometryN(
            ST_MakeValid(
                ST_Force2D(
                    ST_SetSRID(ST_GeomFromGeoJSON(s.geom_json), 4326)
                )
            ),
            1
        ) AS geom
    FROM staging.ide_paradas s
)
INSERT INTO sig_ae4.paradas (
    id_ide,
    codigo,
    nombre,
    barrio,
    activo,
    darsena,
    geom,
    geom_m
)
SELECT
    id_ide,
    codigo,
    nombre,
    barrio,
    activo,
    darsena,
    geom,
    ST_Transform(geom, 5348) AS geom_m
FROM par_pts;

-- -----------------------------------------------------------------------------
-- 11. AVENIDAS DE MANO ÚNICA (IDE Posadas -> sig_ae4.avenidas_mano_unica)
-- -----------------------------------------------------------------------------
WITH mu_lines AS (
    SELECT
        TRIM(s.id_ide) AS id_ide,
        COALESCE(NULLIF(TRIM(s.nombre), ''), TRIM(s.id_ide)) AS nombre,
        NULLIF(TRIM(s.sentido), '') AS sentido,
        NULLIF(TRIM(s.vigente), '') AS vigente,
        ST_Multi(
            ST_CollectionExtract(
                ST_MakeValid(
                    ST_Force2D(
                        ST_SetSRID(ST_GeomFromGeoJSON(s.geom_json), 4326)
                    )
                ),
                2
            )
        ) AS geom
    FROM staging.ide_manos_unicas s
)
INSERT INTO sig_ae4.avenidas_mano_unica (
    id_ide,
    nombre,
    sentido,
    vigente,
    geom,
    geom_m
)
SELECT
    id_ide,
    nombre,
    sentido,
    vigente,
    geom,
    ST_Transform(geom, 5348) AS geom_m
FROM mu_lines;

-- -----------------------------------------------------------------------------
-- 12. ASFALTO SOBRE EMPEDRADO (IDE Posadas -> sig_ae4.asfalto_sobre_empedrado)
-- -----------------------------------------------------------------------------
WITH asf_lines AS (
    SELECT
        TRIM(s.id_ide) AS id_ide,
        COALESCE(NULLIF(TRIM(s.nombre), ''), NULLIF(TRIM(s.tipo_obra), ''), TRIM(s.id_ide)) AS nombre,
        NULLIF(TRIM(s.anio), '') AS anio,
        NULLIF(TRIM(s.tipo_obra), '') AS tipo_obra,
        ST_Multi(
            ST_CollectionExtract(
                ST_MakeValid(
                    ST_Force2D(
                        ST_SetSRID(ST_GeomFromGeoJSON(s.geom_json), 4326)
                    )
                ),
                2
            )
        ) AS geom
    FROM staging.ide_asfalto s
)
INSERT INTO sig_ae4.asfalto_sobre_empedrado (
    id_ide,
    nombre,
    anio,
    tipo_obra,
    geom,
    geom_m
)
SELECT
    id_ide,
    nombre,
    anio,
    tipo_obra,
    geom,
    ST_Transform(geom, 5348) AS geom_m
FROM asf_lines;

-- -----------------------------------------------------------------------------
-- 13. CICLOVÍAS Y BICISENDAS (IDE Posadas -> sig_ae4.ciclovias)
-- -----------------------------------------------------------------------------
WITH cic_lines AS (
    SELECT
        TRIM(s.id_ide) AS id_ide,
        COALESCE(NULLIF(TRIM(s.nombre), ''), NULLIF(TRIM(s.tramo), ''), TRIM(s.id_ide)) AS nombre,
        NULLIF(TRIM(s.tramo), '') AS tramo,
        CASE
            WHEN TRIM(s.anio) ~ '^\d{1,4}$' THEN TRIM(s.anio)::INTEGER
            ELSE NULL
        END AS anio,
        ST_Multi(
            ST_CollectionExtract(
                ST_MakeValid(
                    ST_Force2D(
                        ST_SetSRID(ST_GeomFromGeoJSON(s.geom_json), 4326)
                    )
                ),
                2
            )
        ) AS geom
    FROM staging.ide_ciclovias s
)
INSERT INTO sig_ae4.ciclovias (
    id_ide,
    nombre,
    tramo,
    anio,
    geom,
    geom_m
)
SELECT
    id_ide,
    nombre,
    tramo,
    anio,
    geom,
    ST_Transform(geom, 5348) AS geom_m
FROM cic_lines;

-- Limpiar registros de auditoría generados por la carga inicial masiva en semaforos
TRUNCATE sig_ae4.auditoria_ediciones RESTART IDENTITY;
