-- =============================================================================
-- AE4 SIG — Fase III: Edición en vivo, validación de integridad y transacciones
-- Script compatible con psql:
--   docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig \
--     < ae4_sig/sql/05_edicion_transacciones.sql
--
-- Verifica sobre el esquema sig_ae4 (00_init.sql):
--   1. INSERT en sig_ae4.semaforos -> disparo de trg_01_sync_geom_m (EPSG:5348)
--      y registro 'INSERT' en sig_ae4.auditoria_ediciones.
--   2. UPDATE en sig_ae4.incidentes_viales -> recálculo de geom_m,
--      interseccion_id, nodo_referencia_id y auditoría 'UPDATE', con
--      restauración posterior del registro original.
--   3. DELETE del semáforo de prueba -> registro 'DELETE' en auditoría.
--   4. Rechazo controlado de 3 violaciones de integridad (CHECK ST_IsValid,
--      CHECK origen, FOREIGN KEY departamento_id) capturando SQLSTATE/SQLERRM.
--   5. Instrucciones comentadas para demostrar bloqueo MVCC entre psql y QGIS.
--   6. Consulta final de auditoría ordenada por id.
-- =============================================================================

\pset pager off
SET client_min_messages TO NOTICE;

-- -----------------------------------------------------------------------------
-- PASO 1: INSERT en sig_ae4.semaforos y verificación de SRID 5348 + auditoría
-- -----------------------------------------------------------------------------
\echo '=== PASO 1: INSERT en sig_ae4.semaforos (TEST_QGIS_01) ==='

-- Limpieza preventiva por si quedó una ejecución previa incompleta
DELETE FROM sig_ae4.semaforos WHERE id_ide = 'TEST_QGIS_01';

INSERT INTO sig_ae4.semaforos (
    id_ide,
    nombre,
    calle_1,
    calle_2,
    estado,
    centralizado,
    peatonales,
    fuente,
    geom
)
VALUES (
    'TEST_QGIS_01',
    'Semáforo Prueba Fase III (Av. Mitre y Av. Uruguay)',
    'Av. Mitre',
    'Av. Uruguay',
    'Activo',
    'SI',
    'SI',
    'Prueba Fase III',
    ST_SetSRID(ST_MakePoint(-55.8961, -27.3671), 4326)
)
RETURNING id,
          id_ide,
          nombre,
          ST_SRID(geom)   AS srid_geom,
          ST_SRID(geom_m) AS srid_geom_m;

-- Verificar que trg_01_sync_geom_m pobló geom_m en EPSG:5348 (POSGAR 2007 Faja 6)
SELECT id,
       id_ide,
       ST_SRID(geom)                  AS srid_geom,
       ST_SRID(geom_m)                AS srid_geom_m,
       (ST_SRID(geom_m) = 5348)       AS es_epsg_5348,
       ROUND(ST_X(geom_m)::NUMERIC, 2) AS este_5348_m,
       ROUND(ST_Y(geom_m)::NUMERIC, 2) AS norte_5348_m
  FROM sig_ae4.semaforos
 WHERE id_ide = 'TEST_QGIS_01';

-- Verificar entrada 'INSERT' registrada por trg_auditar_semaforos
SELECT id,
       tabla_nombre,
       operacion,
       registro_id,
       usuario,
       fecha_hora,
       detalle->>'nombre'          AS entidad,
       detalle->'nuevo'->>'id_ide' AS id_ide_nuevo,
       detalle->>'geom_wkt'        AS geom_wkt
  FROM sig_ae4.auditoria_ediciones
 WHERE tabla_nombre = 'semaforos'
   AND operacion = 'INSERT'
   AND detalle->'nuevo'->>'id_ide' = 'TEST_QGIS_01'
 ORDER BY id DESC
 LIMIT 1;

-- -----------------------------------------------------------------------------
-- PASO 2: UPDATE de severidad y geometría en un incidente de prueba + restore
-- -----------------------------------------------------------------------------
\echo '=== PASO 2: UPDATE en sig_ae4.incidentes_viales y restauración ==='

DROP TABLE IF EXISTS tmp_incidente_backup;
CREATE TEMP TABLE tmp_incidente_backup AS
SELECT id,
       id_origen,
       nombre,
       origen,
       severidad,
       interseccion_id,
       nodo_referencia_id,
       geom,
       geom_m
  FROM sig_ae4.incidentes_viales
 ORDER BY (origen = 'simulado') DESC,
          (severidad <> 3) DESC,
          id ASC
 LIMIT 1;

-- Estado original guardado antes del UPDATE
SELECT id,
       id_origen,
       origen,
       severidad          AS severidad_original,
       interseccion_id    AS interseccion_original,
       nodo_referencia_id AS nodo_original,
       ST_SRID(geom_m)    AS srid_geom_m_original,
       ST_AsText(geom)    AS geom_original
  FROM tmp_incidente_backup;

-- Actualizar severidad = 3 y desplazar geom hacia otra referencia urbana
UPDATE sig_ae4.incidentes_viales AS inc
   SET severidad = 3,
       geom = COALESCE(
           (
               SELECT ST_SetSRID(
                          ST_MakePoint(ST_X(n.geom) + 0.0002, ST_Y(n.geom) + 0.0002),
                          4326
                      )
                 FROM sig_ae4.nodos_referencia_aitara AS n
                WHERE n.id IS DISTINCT FROM b.nodo_referencia_id
                ORDER BY n.id
                LIMIT 1
           ),
           ST_SetSRID(
               ST_MakePoint(ST_X(b.geom) + 0.0005, ST_Y(b.geom) + 0.0005),
               4326
           )
       )
  FROM tmp_incidente_backup AS b
 WHERE inc.id = b.id;

-- Verificar recálculo de geom_m, interseccion_id y nodo_referencia_id por triggers
SELECT inc.id,
       b.severidad                              AS severidad_antes,
       inc.severidad                            AS severidad_despues,
       ST_SRID(inc.geom_m)                      AS srid_geom_m_despues,
       ROUND(ST_Distance(b.geom_m, inc.geom_m)::NUMERIC, 2) AS desplazamiento_m,
       b.interseccion_id                        AS interseccion_antes,
       inc.interseccion_id                      AS interseccion_despues,
       b.nodo_referencia_id                     AS nodo_antes,
       inc.nodo_referencia_id                   AS nodo_despues
  FROM sig_ae4.incidentes_viales AS inc
  JOIN tmp_incidente_backup AS b ON b.id = inc.id;

-- Verificar registro 'UPDATE' en sig_ae4.auditoria_ediciones
SELECT a.id,
       a.tabla_nombre,
       a.operacion,
       a.registro_id,
       a.fecha_hora,
       a.detalle->'anterior'->>'severidad'          AS sev_anterior,
       a.detalle->'nuevo'->>'severidad'             AS sev_nueva,
       a.detalle->'anterior'->>'interseccion_id'    AS intersec_anterior,
       a.detalle->'nuevo'->>'interseccion_id'       AS intersec_nueva,
       a.detalle->'anterior'->>'nodo_referencia_id' AS nodo_anterior,
       a.detalle->'nuevo'->>'nodo_referencia_id'    AS nodo_nuevo
  FROM sig_ae4.auditoria_ediciones AS a
  JOIN tmp_incidente_backup AS b ON b.id = a.registro_id
 WHERE a.tabla_nombre = 'incidentes_viales'
   AND a.operacion = 'UPDATE'
 ORDER BY a.id DESC
 LIMIT 1;

-- Restaurar severidad y geometría originales para dejar el dataset limpio
UPDATE sig_ae4.incidentes_viales AS inc
   SET severidad = b.severidad,
       geom      = b.geom
  FROM tmp_incidente_backup AS b
 WHERE inc.id = b.id;

-- Confirmar restauración exacta contra el respaldo temporal
SELECT inc.id,
       (inc.severidad = b.severidad)                       AS severidad_restaurada,
       ST_Equals(inc.geom, b.geom)                         AS geom_restaurada,
       (inc.interseccion_id IS NOT DISTINCT FROM b.interseccion_id)       AS interseccion_restaurada,
       (inc.nodo_referencia_id IS NOT DISTINCT FROM b.nodo_referencia_id) AS nodo_restaurado
  FROM sig_ae4.incidentes_viales AS inc
  JOIN tmp_incidente_backup AS b ON b.id = inc.id;

DROP TABLE tmp_incidente_backup;

-- -----------------------------------------------------------------------------
-- PASO 3: DELETE del semáforo TEST_QGIS_01 y verificación de auditoría
-- -----------------------------------------------------------------------------
\echo '=== PASO 3: DELETE en sig_ae4.semaforos (TEST_QGIS_01) ==='

DELETE FROM sig_ae4.semaforos
 WHERE id_ide = 'TEST_QGIS_01'
RETURNING id, id_ide, nombre;

SELECT COUNT(*) AS semaforos_test_restantes
  FROM sig_ae4.semaforos
 WHERE id_ide = 'TEST_QGIS_01';

SELECT id,
       tabla_nombre,
       operacion,
       registro_id,
       usuario,
       fecha_hora,
       detalle->>'nombre'             AS entidad,
       detalle->'anterior'->>'id_ide' AS id_ide_eliminado
  FROM sig_ae4.auditoria_ediciones
 WHERE tabla_nombre = 'semaforos'
   AND operacion = 'DELETE'
   AND detalle->'anterior'->>'id_ide' = 'TEST_QGIS_01'
 ORDER BY id DESC
 LIMIT 1;

-- -----------------------------------------------------------------------------
-- PASO 4: Tres rechazos de integridad capturando SQLSTATE y SQLERRM
-- -----------------------------------------------------------------------------
\echo '=== PASO 4: Pruebas de rechazo por restricciones espaciales y relacionales ==='

-- 4a) Polígono auto-intersectado (bowtie / moño) en sig_ae4.delegaciones
DO $$
BEGIN
    INSERT INTO sig_ae4.delegaciones (
        id_ide,
        nombre,
        fuente,
        geom
    )
    VALUES (
        'TEST_INVALID_BOWTIE',
        'Delegación Inválida Bowtie',
        'Prueba Integridad',
        ST_GeomFromText(
            'MULTIPOLYGON(((-55.90 -27.37, -55.89 -27.36, -55.89 -27.37, -55.90 -27.36, -55.90 -27.37)))',
            4326
        )
    );
    RAISE EXCEPTION 'ERROR: La geometría inválida no fue rechazada por CHECK (ST_IsValid(geom))';
EXCEPTION
    WHEN check_violation THEN
        RAISE NOTICE '[RECHAZADO OK - 4a ST_IsValid] SQLSTATE=%, SQLERRM=%', SQLSTATE, SQLERRM;
END $$;

-- 4b) Incidente con origen = 'otro' en sig_ae4.incidentes_viales
DO $$
BEGIN
    INSERT INTO sig_ae4.incidentes_viales (
        id_origen,
        nombre,
        origen,
        fuente,
        fecha_evento,
        tipo_incidente,
        severidad,
        geom
    )
    VALUES (
        'TEST_INVALID_ORIGEN',
        'Incidente con Origen Inválido',
        'otro',
        'Prueba Integridad',
        TIMESTAMP '2026-01-15 10:30:00',
        'colision',
        2,
        ST_SetSRID(ST_MakePoint(-55.8961, -27.3671), 4326)
    );
    RAISE EXCEPTION 'ERROR: origen=''otro'' no fue rechazado por CHECK (origen IN (''real'', ''simulado''))';
EXCEPTION
    WHEN check_violation THEN
        RAISE NOTICE '[RECHAZADO OK - 4b CHECK origen] SQLSTATE=%, SQLERRM=%', SQLSTATE, SQLERRM;
END $$;

-- 4c) Localidad con departamento_id = 999999 inexistente en sig_ae4.localidades
DO $$
BEGIN
    INSERT INTO sig_ae4.localidades (
        codigo_bahra,
        nombre,
        departamento_id,
        fuente,
        geom
    )
    VALUES (
        'TEST_FK_999999',
        'Localidad Huérfana Prueba FK',
        999999,
        'Prueba Integridad',
        ST_SetSRID(ST_MakePoint(-55.8961, -27.3671), 4326)
    );
    RAISE EXCEPTION 'ERROR: departamento_id=999999 no fue rechazado por FOREIGN KEY';
EXCEPTION
    WHEN foreign_key_violation THEN
        RAISE NOTICE '[RECHAZADO OK - 4c FOREIGN KEY] SQLSTATE=%, SQLERRM=%', SQLSTATE, SQLERRM;
END $$;

-- -----------------------------------------------------------------------------
-- PASO 5: Guía documentada para bloqueo MVCC a nivel de fila (psql <-> QGIS)
-- -----------------------------------------------------------------------------
-- Para demostrar concurrencia real y bloqueo MVCC entre psql y QGIS Edit Buffer
-- (o reproducirlo de forma automatizada con scripts/test_bloqueo_concurrente.py):
--
-- [Sesión 1 - psql] Iniciar transacción sin hacer COMMIT para retener el lock:
--   BEGIN;
--   SELECT id, id_ide, nombre, estado
--     FROM sig_ae4.semaforos
--    ORDER BY id
--    LIMIT 1;
--   -- Suponiendo id = 1:
--   UPDATE sig_ae4.semaforos
--      SET estado = 'Mantenimiento (bloqueo MVCC)'
--    WHERE id = 1;
--   -- NO ejecutar COMMIT ni ROLLBACK todavía.
--
-- [Sesión 2 - QGIS Desktop]
--   1. Cargar la capa sig_ae4.semaforos desde la conexión PostgreSQL/PostGIS.
--   2. Activar "Conmutar edición" (Toggle Editing) sobre sig_ae4.semaforos.
--   3. Modificar el atributo "estado" (o mover el punto) del MISMO registro id = 1.
--   4. Hacer clic en "Guardar cambios de la capa" (Save Layer Edits).
--   -> QGIS enviará BEGIN; UPDATE sig_ae4.semaforos ... WHERE id = 1; y quedará
--      en espera bloqueado por el lock de tupla/transacción de la Sesión 1.
--
-- [Sesión 3 - psql monitoreo de locks]
--   SELECT a.pid,
--          a.application_name,
--          a.state,
--          a.wait_event_type,
--          a.wait_event,
--          pg_blocking_pids(a.pid) AS bloqueado_por_pids,
--          LEFT(a.query, 90)       AS consulta
--     FROM pg_stat_activity AS a
--    WHERE a.datname = 'aitara_ae4_sig'
--      AND a.wait_event_type = 'Lock';
--
--   SELECT l.pid, l.locktype, l.relation::regclass, l.mode, l.granted
--     FROM pg_locks AS l
--    WHERE l.pid <> pg_backend_pid()
--      AND l.relation = 'sig_ae4.semaforos'::regclass;
--
-- [Sesión 1 - psql] Liberar el bloqueo:
--   ROLLBACK;   -- Libera la fila; QGIS se desbloquea de inmediato y confirma su UPDATE.
--   -- (O COMMIT; para confirmar el cambio de psql antes de que QGIS continúe.)

-- -----------------------------------------------------------------------------
-- PASO 6: Consulta final de auditoría de ediciones
-- -----------------------------------------------------------------------------
\echo '=== PASO 6: Historial completo en sig_ae4.auditoria_ediciones ==='

SELECT id,
       tabla_nombre,
       operacion,
       registro_id,
       usuario,
       fecha_hora,
       detalle->>'nombre' AS entidad
  FROM sig_ae4.auditoria_ediciones
 ORDER BY id;
