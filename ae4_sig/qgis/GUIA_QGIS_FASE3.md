# Guía Práctica de QGIS Desktop — Fase III (AE4 SIG)

Guía paso a paso para operar el proyecto nativo **`proyecto_ae4.qgz`** en **`QGIS 4.2.1 'Belém do Pará'`** (`C:\Program Files\QGIS 4.2.1\bin\qgis-bin.exe` y entorno PyQGIS `python-qgis.bat`) conectado a PostgreSQL 16.4 + PostGIS 3.4.3 (`ae4_postgis`), re-ejecutar o verificar las consultas espaciales de autoría en **DB Manager / Navegador SQL**, realizar edición en vivo (**ABM**), validar **restricciones de integridad**, demostrar **bloqueo concurrente MVCC** y reunir las capturas del portafolio AE4.

---

## 1. Configuración de la conexión PostGIS en QGIS (sin guardar contraseña)

> **Regla de seguridad:** Nunca guardes contraseñas en texto plano dentro del archivo `.qgz`/`.qgs`. El proyecto [`proyecto_ae4.qgz`](proyecto_ae4.qgz) (`75,997` bytes, versión XML `4.2.1-Belém do Pará`) fue guardado de forma nativa con **QGIS 4.2.1** mediante [`construir_proyecto_qgis4.py`](../scripts/construir_proyecto_qgis4.py) y sanitizado en su XML interno (`proyecto_ae4.qgs`) para definir sus `datasource` únicamente con `dbname='aitara_ae4_sig' host=localhost port=5433` y **sin** `user=` ni `password=` (`0` tokens de credenciales verificados en [`verificacion_qgis_4_2_1.txt`](../outputs/verificacion_qgis_4_2_1.txt)). Por ello, al abrir el proyecto, QGIS solicita de manera interactiva las credenciales de PostgreSQL (`ae4_user`).

1. Verificar que el contenedor Docker esté activo y saludable:
   ```powershell
   docker ps --filter "name=ae4_postgis"
   ```
2. En **QGIS 4.2.1**, abrir el panel **Navegador** (`Browser`) -> clic derecho sobre **PostgreSQL** -> **Nueva conexión...**
3. Completar los parámetros exactamente así (valores por defecto según `ae4_sig/docker-compose.yml` y `ae4_sig/.env`):
   - **Nombre:** `AITARA_AE4_SIG`
   - **Servicio:** *(vacío)*
   - **Anfitrión (`Host`):** `localhost`
   - **Puerto (`Port`):** `5433`
   - **Base de datos (`Database`):** `aitara_ae4_sig`
   - **Modo SSL (`SSL mode`):** `disable`
4. En la sección **Autenticación**:
   - **Opción recomendada (AuthDB cifrado):** Ir a la pestaña **Configuraciones** -> pulsar **`+`**, ingresar una *contraseña maestra* de QGIS si la solicita por primera vez, crear una configuración **Basic authentication** con Usuario `ae4_user` y la contraseña de `ae4_sig/.env` (`POSTGRES_PASSWORD`).
   - **Opción básica sin almacenamiento en proyecto:** Ingresar Usuario `ae4_user` en la pestaña **Básica** y **NO tildar** *"Guardar"* junto al campo Contraseña (QGIS la solicitará al abrir el proyecto).
5. Tildar las casillas de exploración útiles:
   - **`[x]` Listar también las tablas sin geometría** (permite inspeccionar `sig_ae4.exposicion_clima` y `sig_ae4.auditoria_ediciones`).
   - **`[x]` Usar tablas de metadatos estimadas** *(opcional para mejorar tiempos de carga inicial)*.
6. Pulsar **Probar conexión** -> confirmar mensaje *"La conexión con aitara_ae4_sig fue exitosa"* -> **Aceptar**.

---

## 2. Apertura de `proyecto_ae4.qgz`, 21 capas verificadas y mapas temáticos

1. Lanzar el proyecto directamente desde PowerShell (en la raíz del repositorio) con **QGIS 4.2.1 'Belém do Pará'**:
   ```powershell
   & "C:\Program Files\QGIS 4.2.1\bin\qgis-bin.exe" ae4_sig\qgis\proyecto_ae4.qgz
   ```
   *(También puede abrirse desde **Proyecto -> Abrir...** seleccionando `ae4_sig/qgis/proyecto_ae4.qgz`. Si necesitás regenerar el proyecto y correr la verificación nativa PyQGIS 4.2.1, ejecutar `& "C:\Program Files\QGIS 4.2.1\bin\python-qgis.bat" ae4_sig/scripts/construir_proyecto_qgis4.py`.)*
2. Cuando QGIS muestre el diálogo de credenciales para PostgreSQL (`localhost:5433 / aitara_ae4_sig`), ingresar el usuario **`ae4_user`** y la contraseña definida en `ae4_sig/.env` (el archivo `.qgz` no almacena usuario ni contraseña en texto plano; si configuraste AuthDB, se desbloqueará con la contraseña maestra).
3. Verificar en la esquina inferior derecha de la ventana principal que el **SRC del proyecto** indique:
   - **`EPSG:5348`** (*POSGAR 2007 / Argentina 6*, proyección Transverse Mercator en metros).
   - El lienzo inicial abre centrado sobre Posadas (`xmin = 6600800`, `xmax = 6612400`, `ymin = 6964000`, `ymax = 6975400`).
4. Verificar en el panel **Capas** las **21 capas verificadas** (todas válidas y con conteo `1:1` frente a PostgreSQL según [`verificacion_qgis_4_2_1.txt`](../outputs/verificacion_qgis_4_2_1.txt)):
   - **`Posadas (IDE + OSM + AITARA)`** *(activo por defecto)*:
     - **Subgrupo preconfigurado `Consultas de Autoría (DB Manager / SQL)`** *(3 capas SQL nativas listas para inspeccionar)*:
       - `Autoría 1 — Escuelas sin semáforo` (`104` intersecciones, activa por defecto)
       - `Autoría 2B — Tramos críticos por lluvia` (`30` tramos)
       - `Autoría 3 — Brecha por delegación` (`12` delegaciones)
     - **11 tablas PostGIS urbanas (`sig_ae4`):**
       - Puntos: `incidentes_viales` (`1,429`: diamantes rojos para `origen = 'real'` y círculos ámbar/naranja graduados por `severidad` para `origen = 'simulado'`), `nodos_referencia_aitara` (`7`), `semaforos` (`280`), `escuelas` (`367`), `paradas` (`482`), `intersecciones` (`7,898`).
       - Líneas: `avenidas_mano_unica` (`8`), `asfalto_sobre_empedrado` (`613`), `ciclovias` (`52`), `calles` (`1,286`).
       - Polígonos: `delegaciones` (`12`, relleno azul semitransparente, contorno azul marino y etiquetas con `nombre`).
     - **1 capa WMS externa** *(apagada por defecto)*: `IDE Posadas — Delegaciones (WMS)`.
   - **`Regional (IGN)`** *(apagado por defecto para carga ágil sobre Posadas — **6 tablas PostGIS**)*:
     - `localidades` (`3,528`), `rutas` (`582`), `cursos_agua` (`1,333`), `departamentos` (`529`), `provincias` (`24`), `paises` (`12`).
5. Si deseas contrastar la extensión nacional/provincial, activar temporalmente `Regional (IGN)` y luego volver a hacer clic derecho sobre `delegaciones` -> **Zoom a la(s) capa(s)**.

### 2.1 Mapas temáticos ya renderizados con QGIS 4.2.1 (`QgsMapRendererParallelJob`)

El script [`construir_proyecto_qgis4.py`](../scripts/construir_proyecto_qgis4.py) ya renderizó en alta resolución (`1800×1150 px`) mediante `QgsMapRendererParallelJob` **4 mapas temáticos PNG** en `ae4_sig/outputs/mapas_qgis/` listos para el informe PDF y la defensa oral:

- [`mapa_01_regional_ign.png`](../outputs/mapas_qgis/mapa_01_regional_ign.png) (`550,321` bytes) — Contexto regional NEA, hidrografía y red vial troncal (IGN + Natural Earth 50m).
- [`mapa_02_posadas_infraestructura_y_siniestros.png`](../outputs/mapas_qgis/mapa_02_posadas_infraestructura_y_siniestros.png) (`1,135,961` bytes) — Posadas: infraestructura vial, nodos expertos AITARA y siniestralidad (`real` vs `simulado`).
- [`mapa_03_autoria1_escuelas_sin_semaforo.png`](../outputs/mapas_qgis/mapa_03_autoria1_escuelas_sin_semaforo.png) (`1,102,203` bytes) — **Autoría 1**: `104` intersecciones en zonas escolares (`<= 150 m`) sobre avenidas de mano única (`<= 25 m`) sin semáforo (`<= 30 m`).
- [`mapa_04_autoria3_brecha_delegaciones.png`](../outputs/mapas_qgis/mapa_04_autoria3_brecha_delegaciones.png) (`467,483` bytes) — **Autoría 3**: brecha de infraestructura vial en las `12` delegaciones municipales.

---

## 3. Ejecución y verificación interactiva de consultas de Autoría (1, 2B y 3) en QGIS

El proyecto [`proyecto_ae4.qgz`](proyecto_ae4.qgz) **ya incluye pre-cargadas** las 3 capas SQL dentro del subgrupo **`Consultas de Autoría (DB Manager / SQL)`** (`Autoría 1` = `104`, `Autoría 2B` = `30`, `Autoría 3` = `12`). Si deseás **re-ejecutarlas, inspeccionar sus atributos o cargarlas manualmente desde cero** para capturas de evaluación, seguí este procedimiento usando [`ae4_sig/sql/03_consultas_autoria.sql`](../sql/03_consultas_autoria.sql). Todas calculan métricas espaciales sobre `geom_m` (`EPSG:5348`) y devuelven `id` único y `geom` (`EPSG:4326`).

### 3.1 Abrir la Ventana SQL en QGIS 4.2.1 (DB Manager o Navegador)

En QGIS 4.x / 3.x podés ejecutar SQL sobre PostGIS por cualquiera de estas dos vías equivalentes:

1. **Vía DB Manager (clásica):** ir al menú **Base de datos -> Administrador de BBDD / BD (`DB Manager`)**, expandir **PostGIS -> `AITARA_AE4_SIG` -> `sig_ae4`** y abrir la **Ventana SQL** (icono de hoja SQL o tecla `F2`).
2. **Vía Navegador nativo (QGIS 4.x / 3.x):** en el panel **Navegador (`Browser`) -> PostgreSQL**, hacer clic derecho sobre **`AITARA_AE4_SIG`** (o sobre el esquema `sig_ae4`) -> **Ejecutar SQL...** (*Execute SQL*).

### 3.2 Re-ejecutar / Cargar Autoría 1, Autoría 2B y Autoría 3 como capas

Para cada una de las 3 consultas espaciales, copiar el bloque SQL correspondiente desde `ae4_sig/sql/03_consultas_autoria.sql` (sin los comentarios de separación de bloques ni otras consultas en el mismo buffer), pulsar **Ejecutar** y luego configurar el panel inferior **Cargar como nueva capa**:

1. **Autoría 1 — Incorporación** *(Intersecciones OSM en zona escolar `<=150 m` sobre `avenidas_mano_unica` `<=25 m` sin `semaforos` `<=30 m` — `104` filas)*:
   - Pegar la consulta `AUTORÍA 1 — INCORPORACIÓN` (`WITH candidatas AS (...) SELECT ... FROM candidatas ORDER BY ...;`).
   - Pulsar **Ejecutar**.
   - Tildar **`[x]` Cargar como nueva capa**.
   - **Columna(s) con valores únicos:** `id`
   - **Columna de geometría:** `geom`
   - **Nombre de la capa:** `autoria_1_cruces_escolares_sin_semaforo`
   - Pulsar **Cargar** -> estilizar con marcador estrella/cruz amarillo-rojo (o comparar contra la capa pre-cargada `Autoría 1 — Escuelas sin semáforo`) y revisar la tabla de atributos (`puntaje_prioridad`, `escuela_cercana`, `avenida_mano_unica`).

2. **Autoría 2B — Mantenimiento** *(Top 30 calles OSM con mayor siniestralidad bajo lluvia y marca `tiene_asfalto_sobre_empedrado` — `30` filas)*:
   - Pegar la consulta `AUTORÍA 2 — MANTENIMIENTO (Parte 2B)` (`SELECT c.id, c.nombre, ... FROM sig_ae4.calles c ... LIMIT 30;`).
   - Pulsar **Ejecutar**.
   - Tildar **`[x]` Cargar como nueva capa**.
   - **Columna(s) con valores únicos:** `id`
   - **Columna de geometría:** `geom`
   - **Nombre de la capa:** `autoria_2b_top30_calles_lluvia`
   - Pulsar **Cargar** -> sugerencia: simbolizar por categorías sobre `tiene_asfalto_sobre_empedrado` o graduado por `puntaje_sensibilidad_lluvia` (o activar la capa pre-cargada `Autoría 2B — Tramos críticos por lluvia`).
   - *(Nota: Las partes **2A** y **2C** son tablas resumen alfanuméricas sin `geom`; pueden ejecutarse en la misma Ventana SQL desmarcando "Cargar como nueva capa" para capturar sus tablas de resultados).*

3. **Autoría 3 — Cobertura** *(Brecha de infraestructura vial en las 12 `delegaciones` municipales — `12` filas)*:
   - Pegar la consulta `AUTORÍA 3 — COBERTURA` (`WITH base_delegaciones AS (...) SELECT ... FROM metricas ORDER BY ...;`).
   - Pulsar **Ejecutar**.
   - Tildar **`[x]` Cargar como nueva capa**.
   - **Columna(s) con valores únicos:** `id`
   - **Columna de geometría:** `geom`
   - **Nombre de la capa:** `autoria_3_brecha_delegaciones`
   - Pulsar **Cargar** -> aplicar simbología **Graduado** sobre `indice_brecha_prioridad` (rampa `YlOrRd`, 5 clases) y etiquetas con `nombre` + `semaforos_cada_100_intersecciones` (o activar la capa pre-cargada `Autoría 3 — Brecha por delegación`).

### 3.3 Verificación cruzada de conteos con `psql` y reporte nativo

Ejecutar `03_consultas_autoria.sql` completo en `psql` y comparar el número exacto de filas de cada consulta con las capas cargadas en QGIS (**Propiedades de capa -> Información -> Número de objetos** o tabla de atributos) y con [`verificacion_qgis_4_2_1.txt`](../outputs/verificacion_qgis_4_2_1.txt):

```powershell
docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig < ae4_sig/sql/03_consultas_autoria.sql
```

Confirmar la coincidencia exacta `1:1` (`todas_validas_y_coincidentes=True`):
- **Autoría 1** (`Autoría 1 — Escuelas sin semáforo` / `autoria_1_cruces_escolares_sin_semaforo`): **`104`** intersecciones tanto en `psql` como en QGIS.
- **Autoría 2B** (`Autoría 2B — Tramos críticos por lluvia` / `autoria_2b_top30_calles_lluvia`): **`30`** tramos tanto en `psql` como en QGIS.
- **Autoría 3** (`Autoría 3 — Brecha por delegación` / `autoria_3_brecha_delegaciones`): **`12`** polígonos (las 12 delegaciones de Posadas) tanto en `psql` como en QGIS.

---

## 4. Edición en vivo (ABM) en QGIS y verificación de triggers

Este procedimiento demuestra la edición transaccional desde QGIS Edit Buffer y la ejecución automática de los triggers definidos en `ae4_sig/sql/00_init.sql` (`trg_01_sync_geom_m`, `trg_02_sync_incidente_nodos`, `trg_auditar_semaforos`, `trg_auditar_incidentes`). El script SQL equivalente para validación por consola es [`ae4_sig/sql/05_edicion_transacciones.sql`](../sql/05_edicion_transacciones.sql).

### 4.1 Alta (`INSERT`) de un semáforo de prueba

1. En el panel **Capas**, seleccionar `semaforos`.
2. Hacer zoom sobre la intersección **Av. Mitre y Av. Uruguay** (centro de Posadas, aprox. `lon -55.8961, lat -27.3671`).
3. Pulsar **Conmutar edición** (lápiz amarillo) y luego **Añadir objeto espacial punto**.
4. Hacer clic en la esquina y completar el formulario de atributos (dejar `id` y `geom_m` en blanco/autogenerados):
   - `id_ide`: `TEST_QGIS_01`
   - `nombre`: `Semáforo Prueba Fase III (Av. Mitre y Av. Uruguay)`
   - `calle_1`: `Av. Mitre`
   - `calle_2`: `Av. Uruguay`
   - `estado`: `Activo`
   - `centralizado`: `SI`
   - `peatonales`: `SI`
   - `fuente`: `Prueba Fase III QGIS`
5. Pulsar **Aceptar** y luego **Guardar cambios de la capa** (disquete). Desactivar edición o continuar al paso 4.3.
6. Verificar en `psql` que el trigger `trg_01_sync_geom_m` pobló `geom_m` en `EPSG:5348` y `trg_auditar_semaforos` registró el `INSERT`:
   ```powershell
   docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -c "
   SELECT id, id_ide, ST_SRID(geom) AS srid_geom, ST_SRID(geom_m) AS srid_geom_m,
          ROUND(ST_X(geom_m)::numeric, 2) AS este_5348, ROUND(ST_Y(geom_m)::numeric, 2) AS norte_5348
     FROM sig_ae4.semaforos WHERE id_ide = 'TEST_QGIS_01';
   SELECT id, tabla_nombre, operacion, registro_id, usuario, fecha_hora, detalle->>'nombre' AS entidad
     FROM sig_ae4.auditoria_ediciones
    WHERE tabla_nombre = 'semaforos' ORDER BY id DESC LIMIT 3;"
   ```

### 4.2 Modificación (`UPDATE`) de un incidente vial

1. Antes de editar, anotar los valores originales de un registro de prueba (por ejemplo el primer incidente simulado) ejecutando en `psql`:
   ```powershell
   docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -c "
   SELECT id, id_origen, origen, severidad, interseccion_id, nodo_referencia_id, ST_AsText(geom) AS wkt_orig
     FROM sig_ae4.incidentes_viales
    WHERE origen = 'simulado' ORDER BY id LIMIT 1;"
   ```
2. En QGIS, seleccionar `incidentes_viales` -> activar **Conmutar edición**.
3. Localizar ese `id` con **Seleccionar por valor** (`id = <id_elegido>`) y pulsar **Zoom a la selección**.
4. Usar la **Herramienta de vértices** para desplazar el punto unos ~100–300 m hacia otra esquina/corredor cercano, y con **Identificar objetos espaciales** (con el formulario abierto) cambiar `severidad` a `3` (u otro valor distinto al original).
5. Pulsar **Guardar cambios de la capa**.
6. Verificar en `psql` que:
   - `geom_m` se recalculó automáticamente en `EPSG:5348`.
   - `trg_02_sync_incidente_nodos` actualizó `interseccion_id` (<= 150 m) y/o `nodo_referencia_id` (<= 500 m) según la nueva ubicación.
   - `trg_auditar_incidentes` registró la fila `UPDATE` con `detalle->'anterior'` y `detalle->'nuevo'` en `sig_ae4.auditoria_ediciones`.
   ```powershell
   docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -c "
   SELECT id, severidad, interseccion_id, nodo_referencia_id, ST_SRID(geom_m) AS srid_m
     FROM sig_ae4.incidentes_viales WHERE id = <id_elegido>;
   SELECT id, operacion, registro_id, fecha_hora,
          detalle->'anterior'->>'severidad' AS sev_antes,
          detalle->'nuevo'->>'severidad' AS sev_despues,
          detalle->'anterior'->>'nodo_referencia_id' AS nodo_antes,
          detalle->'nuevo'->>'nodo_referencia_id' AS nodo_despues
     FROM sig_ae4.auditoria_ediciones
    WHERE tabla_nombre = 'incidentes_viales' AND registro_id = <id_elegido>
    ORDER BY id DESC LIMIT 1;"
   ```
7. **Restaurar el incidente original** para mantener intacto el dataset productivo (desde QGIS con *Deshacer* antes de cerrar la sesión o con `UPDATE sig_ae4.incidentes_viales SET severidad = <sev_orig>, geom = ST_GeomFromText('<wkt_orig>', 4326) WHERE id = <id_elegido>;`).

### 4.3 Baja (`DELETE`) del semáforo de prueba

1. Seleccionar `semaforos` en QGIS -> **Conmutar edición** -> seleccionar `TEST_QGIS_01` (vía tabla de atributos o herramienta de selección).
2. Pulsar **Borrar lo seleccionado** (icono papelera roja) -> **Guardar cambios de la capa** -> desactivar edición.
3. Confirmar en `psql` que el registro ya no existe en `semaforos` y que figura la operación `DELETE` en `sig_ae4.auditoria_ediciones`:
   ```powershell
   docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -c "
   SELECT COUNT(*) AS restantes FROM sig_ae4.semaforos WHERE id_ide = 'TEST_QGIS_01';
   SELECT id, tabla_nombre, operacion, registro_id, fecha_hora, detalle->>'nombre' AS entidad
     FROM sig_ae4.auditoria_ediciones
    WHERE tabla_nombre = 'semaforos' ORDER BY id DESC LIMIT 5;"
   ```

---

## 5. Rechazos por restricciones DB y bloqueo concurrente MVCC

### 5.1 Demostración de 3 rechazos de integridad desde QGIS

En los tres casos siguientes, QGIS permite dibujar/escribir en memoria temporal (edit buffer), pero al pulsar **Guardar cambios de la capa**, PostgreSQL/PostGIS rechaza el `COMMIT` y QGIS muestra el diálogo **"Errores al consignar los cambios"**:

1. **Geometría inválida auto-intersectada (moño / *bowtie*) en `delegaciones`:**
   - Activar edición sobre `delegaciones` -> **Añadir polígono**.
   - Digitalizar 4 vértices formando un moño cruzado en X (por ejemplo en cruz alrededor de Posadas) y cerrar con clic derecho (`id_ide = 'TEST_BOWTIE'`, `nombre = 'Prueba Bowtie'`).
   - Pulsar **Guardar cambios**.
   - **Resultado esperado:** PostGIS rechaza con `SQLSTATE 23514` (`check_violation` — `CHECK (ST_IsValid(geom))`). Capturar el mensaje de error y luego **Descartar modificaciones** (*Conmutar edición -> Descartar*).

2. **Violación de dominio (`origen = 'otro'`) en `incidentes_viales`:**
   - Activar edición sobre `incidentes_viales` -> **Añadir punto**.
   - Completar campos obligatorios (`nombre = 'Prueba Origen'`, `origen = 'otro'`, `fuente = 'Prueba'`, `fecha_evento = '2026-01-15 10:30:00'`, `tipo_incidente = 'colision'`, `severidad = 2`) y pulsar **Guardar cambios**.
   - **Resultado esperado:** PostGIS rechaza con `SQLSTATE 23514` (`CHECK (origen IN ('real', 'simulado'))`). Capturar el error y descartar cambios.

3. **Violación de clave foránea (`departamento_id = 999999`) en `localidades`:**
   - Activar temporalmente el grupo `Regional (IGN)` -> seleccionar `localidades` -> **Conmutar edición** -> **Añadir punto**.
   - Completar `codigo_bahra = 'TEST_FK_999999'`, `nombre = 'Localidad Huérfana'`, **`departamento_id = 999999`**, `fuente = 'Prueba'` y pulsar **Guardar cambios**.
   - **Resultado esperado:** PostGIS rechaza con `SQLSTATE 23503` (`foreign_key_violation` — `REFERENCES sig_ae4.departamentos(id)`). Capturar el error y descartar cambios.

### 5.2 Bloqueo concurrente MVCC entre `psql` y QGIS

Demuestra aislamiento a nivel de fila (*row-level lock*) entre una transacción abierta en `psql` y el guardado de QGIS:

1. **Terminal 1 (`psql` — Sesión bloqueadora):** Consultar el primer `id` de `semaforos` e iniciar un `UPDATE` **sin `COMMIT`**:
   ```powershell
   docker exec -it ae4_postgis psql -U ae4_user -d aitara_ae4_sig
   ```
   ```sql
   BEGIN;
   SELECT id, id_ide, nombre, estado FROM sig_ae4.semaforos ORDER BY id LIMIT 1;
   -- Reemplazar <id_1> por el id obtenido (ej. 1):
   UPDATE sig_ae4.semaforos
      SET estado = 'Mantenimiento (bloqueo MVCC)'
    WHERE id = <id_1>;
   -- NO ejecutar COMMIT ni ROLLBACK todavía.
   ```
2. **QGIS Desktop (Sesión bloqueada):**
   - Activar edición sobre `semaforos`, abrir la tabla de atributos, localizar el **mismo `id = <id_1>`**, cambiar el campo `estado` a `'Revisión QGIS'` y pulsar **Guardar cambios de la capa**.
   - Observar que QGIS queda en espera (cursor de ocupado) esperando que la transacción de la Terminal 1 libere el lock de tupla.
3. **Terminal 2 (`psql` — Observador de locks):** Mientras QGIS espera, inspeccionar `pg_stat_activity` y `pg_locks`:
   ```powershell
   docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -c "
   SELECT a.pid, a.application_name, a.state, a.wait_event_type, a.wait_event,
          pg_blocking_pids(a.pid) AS bloqueado_por_pids, LEFT(a.query, 85) AS consulta
     FROM pg_stat_activity AS a
    WHERE a.datname = 'aitara_ae4_sig' AND a.wait_event_type = 'Lock';
   SELECT l.pid, l.locktype, l.relation::regclass, l.mode, l.granted
     FROM pg_locks AS l
    WHERE l.pid <> pg_backend_pid() AND l.relation = 'sig_ae4.semaforos'::regclass;"
   ```
4. **Terminal 1 (`psql` — Liberación):** Ejecutar `ROLLBACK;` (libera la fila sin alterar el dato desde `psql`) -> observar que **QGIS se desbloquea de inmediato** y finaliza el guardado. Luego, si deseas restaurar el campo `estado` original de `<id_1>`, vuelve a editarlo en QGIS o deshaz el cambio de prueba.
   - *(Referencia automatizada en consola: `python ae4_sig/scripts/test_bloqueo_concurrente.py`.)*

---

## 6. Checklist de capturas requeridas para el portfolio Google Drive AE4

> Además de las capturas interactivas en QGIS 4.2.1 detalladas abajo, ya se encuentran renderizados los **4 mapas temáticos PNG (`1800×1150 px`)** en `ae4_sig/outputs/mapas_qgis/` ([`mapa_01_regional_ign.png`](../outputs/mapas_qgis/mapa_01_regional_ign.png), [`mapa_02_posadas_infraestructura_y_siniestros.png`](../outputs/mapas_qgis/mapa_02_posadas_infraestructura_y_siniestros.png), [`mapa_03_autoria1_escuelas_sin_semaforo.png`](../outputs/mapas_qgis/mapa_03_autoria1_escuelas_sin_semaforo.png) y [`mapa_04_autoria3_brecha_delegaciones.png`](../outputs/mapas_qgis/mapa_04_autoria3_brecha_delegaciones.png)) junto con el reporte [`verificacion_qgis_4_2_1.txt`](../outputs/verificacion_qgis_4_2_1.txt).

- [ ] **`01_qgis_proyecto_crs_capas.png`**: Ventana completa de QGIS 4.2.1 con `proyecto_ae4.qgz` abierto, grupos `Posadas (IDE + OSM + AITARA)` (incluido el subgrupo `Consultas de Autoría (DB Manager / SQL)`) y `Regional (IGN)` visibles en el panel Capas, simbología de `incidentes_viales` (`real` vs `simulado`) y barra inferior mostrando **`EPSG:5348`**.
- [ ] **`02_qgis_sin_password_conexion.png`**: Diálogo de credenciales al abrir `proyecto_ae4.qgz` o propiedades de conexión PostgreSQL/AuthDB mostrando `localhost:5433` / `aitara_ae4_sig` sin contraseña guardada en texto plano en el proyecto (`0` tokens en `.qgz`).
- [ ] **`03_db_manager_autoria1_cruces.png`**: Ventana SQL de QGIS (`DB Manager` o `Navegador -> Ejecutar SQL`) con la consulta **Autoría 1** ejecutada (`104` filas), opciones `id` + `geom` marcadas y la capa resultante superpuesta en el mapa sobre escuelas y avenidas de mano única.
- [ ] **`04_db_manager_autoria2b_lluvia.png`**: Capa `Autoría 2B` (`30` tramos) cargada en QGIS junto a la tabla de resultados (y opcionalmente tabla 2A/2C en Ventana SQL).
- [ ] **`05_db_manager_autoria3_delegaciones.png`**: Mapa temático graduado de las `12` delegaciones (`indice_brecha_prioridad`) con etiquetas de cobertura semafórica y tabla ordenada.
- [ ] **`06_abm_insert_update_delete_auditoria.png`**: Evidencia de edición en vivo en QGIS (`semaforos` / `incidentes_viales`) + salida `psql` mostrando `SRID(geom_m) = 5348`, recálculo de `nodo_referencia_id` y filas `INSERT`/`UPDATE`/`DELETE` en `sig_ae4.auditoria_ediciones`.
- [ ] **`07_rechazos_integridad_qgis.png`**: Diálogos de error en QGIS (o captura combinada + consola `05_edicion_transacciones.sql`) evidenciando el rechazo de geometría bowtie (`ST_IsValid`), `origen = 'otro'` (`CHECK`) y `departamento_id = 999999` (`FOREIGN KEY`).
- [ ] **`08_bloqueo_mvcc_psql_qgis.png`**: Captura simultánea con QGIS bloqueado al guardar y la terminal `psql` mostrando `wait_event_type = 'Lock'` y `pg_blocking_pids` en `pg_stat_activity`, seguida del desbloqueo tras `ROLLBACK;`.
- [ ] **`09_der_sig_ae4.png`**: Incluir el diagrama [`ae4_sig/outputs/der_sig_ae4.png`](../outputs/der_sig_ae4.png) y la referencia a [`ae4_sig/docs/DER_sig_ae4.md`](../docs/DER_sig_ae4.md).
