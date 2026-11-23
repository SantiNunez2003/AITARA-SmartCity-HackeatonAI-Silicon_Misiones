-- =============================================================================
-- AE4 SIG — Fase IV: Índices Espaciales GiST, VACUUM ANALYZE y Benchmark
-- Stack: PostgreSQL 16 + PostGIS 3.4
-- Esquema: sig_ae4 (según ae4_sig/sql/00_init.sql)
--
-- Nota de ejecución:
--   Este script ejecuta VACUUM ANALYZE, por lo que NO debe envolverse en una
--   única transacción (no usar psql --single-transaction / -1).
--   Ejecutar con:
--     docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig < ae4_sig/sql/04_indices_benchmark.sql
-- =============================================================================


-- =============================================================================
-- 1. RESUMEN TEÓRICO: B-tree vs. GiST (R-Tree/MBR) vs. SP-GiST vs. BRIN
-- =============================================================================
-- * B-tree:
--     Árbol balanceado para tipos unidimensionales con orden total (<, =, >).
--     Excelente para PKs, FKs, timestamps (`fecha_evento`) y filtros exactos
--     (`origen`, `codigo_indec`), pero incapaz de indexar vecindad o solapamiento
--     2D (`ST_Intersects`, `ST_DWithin`), ya que las coordenadas (X, Y) no
--     preservan localidad espacial al proyectarse en un orden lineal 1D.
--
-- * GiST (Generalized Search Tree — R-Tree sobre MBR):
--     Estructura estándar de PostGIS para columnas geometry y geography.
--     Almacena en cada nodo el Rectángulo Mínimo Envolvente (MBR / box2df) que
--     cubre a sus hijos y opera en dos fases:
--       1) Filtro grueso (lossy) por MBR mediante operadores && o <-> (KNN).
--       2) Verificación exacta geométrica (Recheck / GEOS) solo sobre candidatos.
--     Soporta puntos, líneas y polígonos heterogéneos y búsquedas KNN (<->).
--
-- * SP-GiST (Space-Partitioned GiST):
--     Árboles no balanceados por partición disjunta del espacio (Quadtree,
--     k-d tree, radix tree). No duplica objetos entre particiones. Puede
--     superar a GiST en tablas masivas exclusivamente puntuales con alta
--     asimetría espacial (millones de puntos GPS/IoT), aunque GiST sigue siendo
--     más versátil para líneas/polígonos y operaciones geography/KNN estándar.
--
-- * BRIN (Block Range Index):
--     Guarda únicamente el MBR mínimo/máximo por rango contiguo de páginas de
--     disco (por defecto 128 bloques). Ocupa kilobytes frente a megabytes de
--     GiST, pero solo es selectivo si la tabla está físicamente ordenada/
--     clusterizada por espacio (o tiempo). En capas espacialmente mezcladas
--     de unos miles de filas (`localidades`, `incidentes_viales`), cada bloque
--     abarca casi todo el territorio y el índice pierde selectividad.
--
-- * La trampa clásica del casteo `geom::geography`:
--     Si una tabla regional tiene únicamente un índice GiST sobre `geom`
--     (`geometry(Point, 4326)`, clase `gist_geometry_ops_2d`) y la consulta
--     evalúa `ST_DWithin(geom::geography, ref_geog, 50000)`, PostgreSQL NO
--     puede usar el índice de `geom` porque el tipo y la familia de operadores
--     difieren (`geography` usa `gist_geography_ops` sobre esfera/esferoide).
--     Resultado sin índice funcional: **Seq Scan** completo.
--     Solución: crear un índice GiST funcional `USING GIST ((geom::geography))`
--     para habilitar **Index Scan / Bitmap Index Scan** en consultas métricas
--     regionales sobre EPSG:4326.
-- =============================================================================


-- =============================================================================
-- 2. CREACIÓN DE ÍNDICES GiST — ESCALA URBANA POSADAS (geom 4326 + geom_m 5348)
-- =============================================================================

-- 2.1 delegaciones
CREATE INDEX IF NOT EXISTS idx_delegaciones_geom_gist
    ON sig_ae4.delegaciones USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_delegaciones_geom_m_gist
    ON sig_ae4.delegaciones USING GIST (geom_m);

-- 2.2 semaforos
CREATE INDEX IF NOT EXISTS idx_semaforos_geom_gist
    ON sig_ae4.semaforos USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_semaforos_geom_m_gist
    ON sig_ae4.semaforos USING GIST (geom_m);

-- 2.3 escuelas
CREATE INDEX IF NOT EXISTS idx_escuelas_geom_gist
    ON sig_ae4.escuelas USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_escuelas_geom_m_gist
    ON sig_ae4.escuelas USING GIST (geom_m);

-- 2.4 paradas
CREATE INDEX IF NOT EXISTS idx_paradas_geom_gist
    ON sig_ae4.paradas USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_paradas_geom_m_gist
    ON sig_ae4.paradas USING GIST (geom_m);

-- 2.5 avenidas_mano_unica
CREATE INDEX IF NOT EXISTS idx_avenidas_mano_unica_geom_gist
    ON sig_ae4.avenidas_mano_unica USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_avenidas_mano_unica_geom_m_gist
    ON sig_ae4.avenidas_mano_unica USING GIST (geom_m);

-- 2.6 asfalto_sobre_empedrado
CREATE INDEX IF NOT EXISTS idx_asfalto_sobre_empedrado_geom_gist
    ON sig_ae4.asfalto_sobre_empedrado USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_asfalto_sobre_empedrado_geom_m_gist
    ON sig_ae4.asfalto_sobre_empedrado USING GIST (geom_m);

-- 2.7 ciclovias
CREATE INDEX IF NOT EXISTS idx_ciclovias_geom_gist
    ON sig_ae4.ciclovias USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_ciclovias_geom_m_gist
    ON sig_ae4.ciclovias USING GIST (geom_m);

-- 2.8 calles
CREATE INDEX IF NOT EXISTS idx_calles_geom_gist
    ON sig_ae4.calles USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_calles_geom_m_gist
    ON sig_ae4.calles USING GIST (geom_m);

-- 2.9 nodos_referencia_aitara
CREATE INDEX IF NOT EXISTS idx_nodos_referencia_aitara_geom_gist
    ON sig_ae4.nodos_referencia_aitara USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_nodos_referencia_aitara_geom_m_gist
    ON sig_ae4.nodos_referencia_aitara USING GIST (geom_m);

-- 2.10 intersecciones
CREATE INDEX IF NOT EXISTS idx_intersecciones_geom_gist
    ON sig_ae4.intersecciones USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_intersecciones_geom_m_gist
    ON sig_ae4.intersecciones USING GIST (geom_m);

-- 2.11 incidentes_viales
CREATE INDEX IF NOT EXISTS idx_incidentes_viales_geom_gist
    ON sig_ae4.incidentes_viales USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_incidentes_viales_geom_m_gist
    ON sig_ae4.incidentes_viales USING GIST (geom_m);


-- =============================================================================
-- 3. CREACIÓN DE ÍNDICES GiST — ESCALA REGIONAL (geom 4326 + funcional geography)
-- =============================================================================

-- 3.1 paises
CREATE INDEX IF NOT EXISTS idx_paises_geom_gist
    ON sig_ae4.paises USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_paises_geog_gist
    ON sig_ae4.paises USING GIST ((geom::geography));

-- 3.2 provincias
CREATE INDEX IF NOT EXISTS idx_provincias_geom_gist
    ON sig_ae4.provincias USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_provincias_geog_gist
    ON sig_ae4.provincias USING GIST ((geom::geography));

-- 3.3 departamentos
CREATE INDEX IF NOT EXISTS idx_departamentos_geom_gist
    ON sig_ae4.departamentos USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_departamentos_geog_gist
    ON sig_ae4.departamentos USING GIST ((geom::geography));

-- 3.4 localidades
CREATE INDEX IF NOT EXISTS idx_localidades_geom_gist
    ON sig_ae4.localidades USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_localidades_geog_gist
    ON sig_ae4.localidades USING GIST ((geom::geography));

-- 3.5 cursos_agua
CREATE INDEX IF NOT EXISTS idx_cursos_agua_geom_gist
    ON sig_ae4.cursos_agua USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_cursos_agua_geog_gist
    ON sig_ae4.cursos_agua USING GIST ((geom::geography));

-- 3.6 rutas
CREATE INDEX IF NOT EXISTS idx_rutas_geom_gist
    ON sig_ae4.rutas USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_rutas_geog_gist
    ON sig_ae4.rutas USING GIST ((geom::geography));


-- =============================================================================
-- 4. VACUUM ANALYZE SOBRE TODAS LAS TABLAS DE sig_ae4
--    Actualiza mapas de visibilidad y estadísticas del planificador (pg_statistic).
--    Se especifica cada tabla de sig_ae4 para evitar advertencias sobre tablas
--    de sistema/extensión como public.spatial_ref_sys.
-- =============================================================================

VACUUM ANALYZE sig_ae4.paises;
VACUUM ANALYZE sig_ae4.provincias;
VACUUM ANALYZE sig_ae4.departamentos;
VACUUM ANALYZE sig_ae4.localidades;
VACUUM ANALYZE sig_ae4.cursos_agua;
VACUUM ANALYZE sig_ae4.rutas;
VACUUM ANALYZE sig_ae4.delegaciones;
VACUUM ANALYZE sig_ae4.semaforos;
VACUUM ANALYZE sig_ae4.escuelas;
VACUUM ANALYZE sig_ae4.paradas;
VACUUM ANALYZE sig_ae4.avenidas_mano_unica;
VACUUM ANALYZE sig_ae4.asfalto_sobre_empedrado;
VACUUM ANALYZE sig_ae4.ciclovias;
VACUUM ANALYZE sig_ae4.calles;
VACUUM ANALYZE sig_ae4.nodos_referencia_aitara;
VACUUM ANALYZE sig_ae4.intersecciones;
VACUUM ANALYZE sig_ae4.incidentes_viales;
VACUUM ANALYZE sig_ae4.exposicion_clima;
VACUUM ANALYZE sig_ae4.auditoria_ediciones;


-- =============================================================================
-- 5. BENCHMARK EXPLAIN (ANALYZE, BUFFERS) — DEMOSTRACIÓN DE LA TRAMPA geography
-- =============================================================================
-- Escenario A (Trampa del casteo `geom::geography` sin índice funcional):
--   Dentro de una transacción con ROLLBACK al final, se oculta temporalmente
--   `idx_localidades_geog_gist` dejando activo ÚNICAMENTE `idx_localidades_geom_gist`
--   (sobre geometry 4326). Observar que el planificador cae en **Seq Scan**
--   al no coincidir `geometry` con el casteo `(geom::geography)`.
--   Luego, ROLLBACK restaura el índice intacto sin reconstruirlo.
-- =============================================================================

BEGIN;
DROP INDEX IF EXISTS sig_ae4.idx_localidades_geog_gist;

EXPLAIN (ANALYZE, BUFFERS)
SELECT id, nombre, tipo_asentamiento
FROM sig_ae4.localidades
WHERE ST_DWithin(
    geom::geography,
    ST_SetSRID(ST_MakePoint(-55.8961, -27.3621), 4326)::geography,
    50000.0
);
ROLLBACK;

-- =============================================================================
-- Escenario B (Con índice funcional GiST `(geom::geography)` activo):
--   Misma consulta exacta ahora resuelta mediante `idx_localidades_geog_gist`
--   (Bitmap Index Scan / Index Scan), con menor lectura de buffers y latencia.
-- =============================================================================

EXPLAIN (ANALYZE, BUFFERS)
SELECT id, nombre, tipo_asentamiento
FROM sig_ae4.localidades
WHERE ST_DWithin(
    geom::geography,
    ST_SetSRID(ST_MakePoint(-55.8961, -27.3621), 4326)::geography,
    50000.0
);

-- =============================================================================
-- Escenario C (Anti-patrón clásico incluso con índice funcional):
--   Usar `ST_Distance(...) <= 50000` en lugar de `ST_DWithin(...)` impide que
--   PostGIS inyecte el operador de bounding box `&&`, forzando **Seq Scan**.
-- =============================================================================

EXPLAIN (ANALYZE, BUFFERS)
SELECT id, nombre, tipo_asentamiento
FROM sig_ae4.localidades
WHERE ST_Distance(
    geom::geography,
    ST_SetSRID(ST_MakePoint(-55.8961, -27.3621), 4326)::geography
) <= 50000.0;

-- =============================================================================
-- Escenario D (Benchmark urbano proyectado EPSG:5348 — `geom_m`):
--   Cruce espacial métrico usando índices GiST `idx_escuelas_geom_m_gist` e
--   `idx_intersecciones_geom_m_gist` (ST_DWithin en metros sobre POSGAR 2007).
-- =============================================================================

EXPLAIN (ANALYZE, BUFFERS)
SELECT i.id, i.nombre, e.nombre AS escuela_cercana
FROM sig_ae4.intersecciones i
JOIN sig_ae4.escuelas e
  ON ST_DWithin(i.geom_m, e.geom_m, 150.0)
WHERE i.geom_m IS NOT NULL
  AND e.geom_m IS NOT NULL;


-- =============================================================================
-- 6. VERIFICACIÓN DE ÍNDICES CREADOS EN sig_ae4
-- =============================================================================

SELECT
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(format('%I.%I', schemaname, indexname)::regclass)) AS index_size,
    indexdef
FROM pg_indexes
WHERE schemaname = 'sig_ae4'
  AND indexdef ILIKE '%USING gist%'
ORDER BY tablename, indexname;
