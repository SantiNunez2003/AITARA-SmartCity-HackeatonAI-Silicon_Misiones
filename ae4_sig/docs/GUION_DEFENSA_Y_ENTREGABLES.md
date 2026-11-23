# Guion de Defensa Oral (2 min + 3 min Coloquio) y Checklist de Entregables — AE4 SIG

**Caso de estudio:** Movilidad urbana y siniestralidad vial en Posadas (Misiones) integrada con marco territorial regional argentino y sudamericano  
**Stack técnico:** PostgreSQL 16.4 + PostGIS 3.4.3 (Docker `ae4_postgis`), Python (`psycopg2`), **`QGIS 4.2.1 'Belém do Pará'`** + **`GDAL 3.13.2 "Iowa City"`** (`ogr2ogr.exe`)  
**Esquema:** `sig_ae4` (`19` tablas: `6` regionales, `11` urbanas, `2` alfanuméricas/auditoría)

---

## Parte I — Guion Cronometrado de Defensa Oral (2:00 exactos)

> **Ritmo objetivo:** ~155 palabras/minuto (~310 palabras habladas = **2:00 exactos**). Debajo de cada segmento figuran las **láminas cartográficas ya renderizadas en QGIS 4.2.1 (`outputs/mapas_qgis/`)** y salidas listas para proyectar en pantalla.

### Segmento 1 (`0:00 – 0:20`, ~48 palabras) — Problemática vial, doble escala y transparencia de origen
> *"Abordamos la problemática vial de **Posadas** integrando dos escalas en **PostGIS**: una regional con **IGN, BAHRA y Natural Earth 50m** (`a–i`), y otra urbana con **IDE Posadas, OSM y AITARA**. Por rigor científico separamos estrictamente el origen de los **1.429 incidentes**: **12 reales** y **1.417 simulados**."*

- **Apoyo visual en pantalla (láminas listas):** [`outputs/mapas_qgis/mapa_01_regional_ign.png`](../outputs/mapas_qgis/mapa_01_regional_ign.png) (marco regional IGN + Natural Earth) y [`outputs/mapas_qgis/mapa_02_posadas_infraestructura_y_siniestros.png`](../outputs/mapas_qgis/mapa_02_posadas_infraestructura_y_siniestros.png) (Posadas con `incidentes_viales` en diamantes rojos `real` y círculos ámbar `simulado`), o vista en vivo de `proyecto_ae4.qgz` en QGIS 4.2.1 (`21` capas verificadas).

### Segmento 2 (`0:20 – 0:50`, ~76 palabras) — Arquitectura PostGIS (`sig_ae4`), dual SRID e integridad
> *"Diseñamos el esquema `sig_ae4` con **19 tablas** normalizadas y **doble SRC**: `geom` en **EPSG:4326** para WFS y QGIS, y `geom_m` en **EPSG:5348** (POSGAR 2007 Faja 6, metros) sincronizada por **`trg_01_sync_geom_m`**, usando `geom::geography` en la escala regional. La integridad se garantiza con **claves foráneas** jerárquicas y espaciales —enlazadas por `trg_02_sync_incidente_nodos`— y restricciones **`CHECK`** de validez (`ST_IsValid`), severidad y origen."*

- **Apoyo visual en pantalla:** Diagrama [`outputs/der_sig_ae4.png`](../outputs/der_sig_ae4.png), fragmento de [`sql/00_init.sql`](../sql/00_init.sql) y evidencia de saneamiento topológico tras carga GDAL 3.13.2 (`staging.ide_delegaciones_ogr_demo` con `ISO-8859-1` y `todas_validas = f` reparado vía `ST_MakeValid`, [`outputs/verificacion_ogr2ogr.txt`](../outputs/verificacion_ogr2ogr.txt)).

### Segmento 3 (`0:50 – 1:20`, ~84 palabras) — Hallazgos verificados de las 3 consultas de autoría
> *"En las 3 consultas de autoría destacamos:*  
> *1. **Incorporación:** **104 intersecciones** escolares en mano única sin semáforo, encabezadas por **Beethoven y Av. Centenario**, **Av. Centenario y Derqui** y **Av. Lavalle y Neumann**.*  
> *2. **Mantenimiento:** en simulados, la razón lluvia/seco es **`1,74×`** en drenaje **BAJO y MEDIO** vs **`1,59×`** en **ALTO**; y **`1,66×`** con **asfalto sobre empedrado** vs **`1,82×`** sin obra.*  
> *3. **Cobertura:** en **12 delegaciones**, **Itaembé Guazú** e **Itaembé Miní Este** tienen **0 semáforos** frente a **Sede Central** con **`44,31`** cada 100 intersecciones."*

- **Apoyo visual en pantalla (láminas listas):** [`outputs/mapas_qgis/mapa_03_autoria1_escuelas_sin_semaforo.png`](../outputs/mapas_qgis/mapa_03_autoria1_escuelas_sin_semaforo.png) (`104` cruces escolares) y [`outputs/mapas_qgis/mapa_04_autoria3_brecha_delegaciones.png`](../outputs/mapas_qgis/mapa_04_autoria3_brecha_delegaciones.png) (`12` delegaciones por brecha), junto al subgrupo `Consultas de Autoría (DB Manager / SQL)` en QGIS 4.2.1 ([`outputs/verificacion_qgis_4_2_1.txt`](../outputs/verificacion_qgis_4_2_1.txt)).

### Segmento 4 (`1:20 – 1:40`, ~52 palabras) — Optimización con índices GiST / R-Tree y trampa `geography`
> *"Con **34 índices GiST**, medimos **`11,87×`** en `intersecciones × calles` y **`47,80×`** en KNN `localidades × cursos_agua`. Resolviendo la trampa `geom::geography` con índice funcional bajamos de **`240.178,937 ms`** a **`4.078,849 ms`** (**`58,88×`**), tendencia confirmada en la curva sintética de **10 mil, 100 mil y 1 millón** de puntos."*

- **Apoyo visual en pantalla:** Gráfico [`outputs/benchmark_gist_volumen.png`](../outputs/benchmark_gist_volumen.png) y tabla resumen de [`outputs/benchmark_resultados.md`](../outputs/benchmark_resultados.md).

### Segmento 5 (`1:40 – 2:00`, ~50 palabras) — Fase III en QGIS 4.2.1, integridad y concurrencia MVCC
> *"En Fase III validamos en **QGIS 4.2.1 y `psql`** el alta y baja de un semáforo, el movimiento de un incidente disparando el trigger de reasignación hacia **`auditoria_ediciones`**, **3 rechazos** (`SQLSTATE 23514` y `23503`) y el **bloqueo MVCC** a nivel de fila entre `psql` y QGIS."*

- **Apoyo visual en pantalla:** Salida de `sig_ae4.auditoria_ediciones` ([`outputs/edicion_transacciones_resultados.txt`](../outputs/edicion_transacciones_resultados.txt)) y captura de bloqueo concurrente ([`outputs/bloqueo_concurrente_resultados.txt`](../outputs/bloqueo_concurrente_resultados.txt)).

---

## Parte II — Preguntas Probables del Coloquio Técnico (3:00)

### Pregunta 1: ¿Cómo funciona un índice GiST y la estructura R-Tree (MBR, nodos internos/hoja, filtro y refinamiento)?

- **Respuesta técnica concisa (~35–40 s):**
  - **GiST (*Generalized Search Tree*)** es una infraestructura extensible de árboles balanceados en PostgreSQL sobre la cual PostGIS implementa un **R-Tree 2D** basado en **MBR (*Minimum Bounding Rectangle* / `box2df`)**.
  - **Estructura:**
    - Los **nodos internos** almacenan un conjunto de `(MBR_envolvente, puntero_a_hijo)`, donde cada MBR cubre espacialmente todos los rectángulos de su subárbol.
    - Los **nodos hoja** almacenan `(MBR_de_la_geometría, TID)` apuntando a la página física de la tabla (*heap*).
    - A diferencia de **B-tree** (orden total 1D incapaz de preservar vecindad 2D), **SP-GiST** (particiones disjuntas no balanceadas como Quadtree/k-d tree, óptimo para millones de puntos homogéneos) o **BRIN** (resumen por rango físico de bloques, que pierde selectividad si la tabla no está clusterizada espacialmente), GiST soporta puntos, líneas y polígonos heterogéneos y búsquedas **KNN (`<->`)** con cola de prioridad en el árbol.
  - **Ejecución en dos etapas:**
    1. **Filtro grueso (*lossy*):** usando el operador de cajas `&&` (inyectado automáticamente por `ST_Intersects`, `ST_Within`, `ST_DWithin`) o `<->`, el motor descarta subárboles enteros cuyos MBR no intersectan el área de búsqueda.
    2. **Refinamiento exacto (*Recheck*):** solo sobre los `TID` candidatos leídos del *heap*, la librería GEOS evalúa la geometría exacta vértice por vértice. Si se escribiera `ST_Distance(...) <= d` en vez de `ST_DWithin(..., d)`, no se inyecta `&&` y el motor cae en `Seq Scan`.

---

### Pregunta 2: ¿Por qué usar `EPSG:5348` para Posadas y `geography` para `a–i`, y qué pasa al castear `geom::geography` sin índice funcional?

- **Respuesta técnica concisa (~35–40 s):**
  - **`EPSG:4326` (WGS84 geográfico)** mide en grados sexagesimales; es el estándar de intercambio (WFS, GeoJSON, visualización QGIS), pero no sirve para medir metros o $\text{m}^2$ de forma directa porque la longitud de un grado de longitud varía con $\cos(\text{latitud})$.
  - **Escala urbana — `EPSG:5348` (*POSGAR 2007 / Argentina Faja 6*):** Posadas está en longitud $\approx -55.9^\circ$, dentro de la Faja 6 (meridiano central $-57^\circ$, proyección Transverse Mercator en metros, elipsoide GRS80, falso este `6.500.000 m`). Proyectar `geom` hacia `geom_m` (mantenida automáticamente por `trg_01_sync_geom_m`) permite aplicar `ST_DWithin`, `ST_Distance`, `ST_Area` y `ST_Length` en metros exactos con aritmética plana mucho más rápida en GEOS.
  - **Escala regional (`a–i`) — `geom::geography`:** Argentina abarca 7 fajas POSGAR (`EPSG:5343–5349`) y Sudamérica excede cualquier proyección plana local; usar una sola faja distorsionaría áreas y distancias continentales. Por eso `02_consultas_a_i.sql` evalúa `geography` (cálculo geodésico directo sobre el elipsoide WGS84).
  - **La trampa del casteo `geom::geography`:** Un índice GiST estándar `USING GIST (geom)` indexa el tipo `geometry` con la familia de operadores `gist_geometry_ops_2d` (cajas 2D planas). Al consultar `ST_DWithin(geom::geography, ...)`, la expresión casteada es de tipo `geography` (`gist_geography_ops`, cajas 3D sobre esfera unitaria). El planificador **no puede usar el índice de `geom`** y ejecuta **`Seq Scan`**. En nuestro benchmark (`localidades × cursos_agua`), eso tardó **`240.178,937 ms` (`282.565` buffers)** frente a **`4.078,849 ms` (`45.853` buffers)** tras crear el índice funcional `USING GIST ((geom::geography))` — un speedup de **`58,88×`**.

---

### Pregunta 3: ¿Qué ocurre si dos clientes (ej. `psql` y QGIS) editan la misma fila a la vez (MVCC, `RowExclusiveLock`, `transactionid ShareLock`, búfer de edición de QGIS)?

- **Respuesta técnica concisa (~35–40 s):**
  - PostgreSQL usa **MVCC (*Multi-Version Concurrency Control*)**: las lecturas nunca bloquean escrituras ni las escrituras a las lecturas, porque cada transacción opera sobre versiones de tuplas (*snapshots*) gobernadas por `xmin`/`xmax`.
  - **Papel del búfer de edición de QGIS:** Cuando en QGIS se activa *Conmutar edición* y se modifica un atributo o vértice, los cambios viven **solo en memoria local** (sin transacción abierta en PostgreSQL). El bloqueo recién ocurre al pulsar **Guardar cambios de la capa**, momento en que QGIS envía `BEGIN; UPDATE ... WHERE id = ...`.
  - **Mecánica observada del bloqueo (`outputs/bloqueo_concurrente_resultados.txt`):**
    1. La Sesión A (`psql`, `pid_A=3616`) ejecuta `UPDATE` sobre `semaforos` `id=1` sin `COMMIT`: adquiere `RowExclusiveLock` en la tabla y `ExclusiveLock` sobre su propio `transactionid` (marcado en el `xmax` de la tupla).
    2. Cuando la Sesión B (`QGIS` / `pid_B=3617`) intenta actualizar la **misma fila**, adquiere `RowExclusiveLock` en la tabla (compatible para filas distintas) y `ExclusiveLock` sobre la tupla, pero al detectar un `xmax` activo queda bloqueada solicitando **`transactionid ShareLock` (`granted = False`)**. En `pg_stat_activity` se observa `state = active`, `wait_event_type = Lock`, `wait_event = transactionid`, `blocking_pids = [3616]`.
    3. Al ejecutar `ROLLBACK` en Sesión A tras `2,0 s`, el lock se libera al instante y Sesión B completa su `UPDATE` en `2,00 s` (si Sesión A hubiera hecho `COMMIT`, en `READ COMMITTED` PostgreSQL re-evalúa el `WHERE` contra la nueva tupla confirmada antes de aplicar el cambio de B).

---

### Pregunta 4: ¿Qué validez científica tienen los resultados si el 99% de los siniestros de AITARA son simulados?

- **Respuesta técnica concisa (~35–40 s):**
  - La honestidad metodológica es explícita desde el esquema: en `sig_ae4.incidentes_viales` cargamos **`1.429` incidentes (`12` reales = `0,84%` y `1.417` simulados = `99,16%`)**, protegidos por `CHECK (origen IN ('real', 'simulado'))`. Nunca se mezclan en una misma métrica: todas las consultas de autoría desglosan `real` y `simulado` por separado.
  - **Sesgo verificado del generador sintético:** Los `1.417` incidentes simulados fueron generados exclusivamente alrededor de los **7 `nodos_referencia_aitara`** (`182` a `217` eventos por nodo), lo que explica que delegaciones como **32-33** (`402` sim) y **Riberas del Paraná** (`405` sim) concentren la densidad simulada mientras 6 delegaciones periféricas registren `0`. Además, `nivel_drenaje` es un atributo experto de `src/warehouse/db.py` (no una capa hidráulica oficial) y los `12` partes reales tienen `llovia IS NULL`.
  - **Qué conclusiones SÍ tienen validez empírica directa:**
    1. Toda la **Fase II regional (`a–i`)** sobre datos oficiales IGN/BAHRA/NE 50m.
    2. Las **104 intersecciones escolares en avenidas de mano única sin semáforo** (`Autoría 1`), calculadas con infraestructura oficial real de IDE Posadas + OSM.
    3. La **brecha territorial de equipamiento real** en `Autoría 3` (ej. **Itaembé Guazú** con `663` intersecciones y `0` semáforos vs **Sede Central** con `44,31` semáforos cada `100` intersecciones).
    - Las razones lluvia/seco (`1,74×` en drenaje `BAJO`/`MEDIO` vs `1,59×` en `ALTO`) validan el pipeline analítico y quedan listas para recalcularse con evidencia causal apenas se incorporen partes reales con registro meteorológico.

---

### Pregunta 5: ¿Cómo se vinculan los incisos `a–i` con transporte e infraestructura vial, y por qué `ST_Touches` difería en 4 pares de provincias IGN?

- **Respuesta técnica concisa (~35–40 s):**
  - **Vínculo de `a–i` con transporte e infraestructura:**
    - `a–c` caracterizan la jerarquía político-territorial y la concentración demográfica (`Capital` alcanza **`407,39 hab/km²`** sobre `964,48 km²` y `392.919` hab., explicando la presión sobre la red vial urbana frente a departamentos rurales como `San Pedro` con `9,11 hab/km²`).
    - `d–f` identifican fronteras internacionales y barreras hidrográficas reales (`Río Paraná` recorre `246,439 km` por `7` departamentos misioneros, `Río Uruguay` `336,989 km` por `7` departamentos y `Río Iguazú` `132,217 km` por `2` departamentos), determinantes para puentes, cruces fronterizos y obras de drenaje.
    - `g–i` miden accesibilidad directa de las **`140` localidades de Misiones** a los corredores viales troncales (**RN 12**: `67` localidades a `4,415 km` promedio; **RN 14**: `66` localidades a `14,728 km` promedio y hasta `50,258 km` en `Alicia Baja`; **RN 101**: `7` localidades a `5,727 km` promedio) y al corredor fluvial del Paraná (`Bernardo de Irigoyen` es el extremo a `97,266 km`, con el `100%` de Misiones y `1.156` localidades argentinas dentro de `200 km`).
  - **Por qué `ST_Touches` difería en 4 pares de provincias IGN (`Entre Ríos–Corrientes`, `Buenos Aires–Entre Ríos`, `San Juan–La Rioja`, `Jujuy–Salta`):**
    - Según el estándar **DE-9IM**, `ST_Touches(A, B)` exige intersección de fronteras **con interiores estrictamente disjuntos** ($I(A) \cap I(B) = \emptyset$).
    - En la geometría oficial del WFS del IGN detectamos **4 micro-solapamientos bidimensionales** (`ST_Dimension = 2`, `ST_Overlaps = true`) de apenas **`5,29 m²`**, **`4,77 m²`**, **`0,03 m²`** y **`<0,005 m²` (`0,00 m²`)**, suficientes para que `ST_Touches` devuelva `FALSE` (dejando a `Jujuy` con `0` vecinos y a `Entre Ríos` con `1` en vez de `3`), mientras `ST_Intersects` devuelve `TRUE`. En cambio, en `paises` (`Natural Earth 50m`) los `12` países dieron `diff_micro_overlap = 0`.
  - **Respaldo sobre ingesta Shapefile (`ogr2ogr` GDAL 3.13.2), codificación DBF y `ST_MakeValid` ([`outputs/verificacion_ogr2ogr.txt`](../outputs/verificacion_ogr2ogr.txt)):**
    - Al cargar el Shapefile oficial [`ide_delegaciones_shp.zip`](../datos_externos/ide_delegaciones_shp.zip) en vivo con **`GDAL 3.13.2 "Iowa City"`** (`ogr2ogr.exe` vía `/vsizip/` y `SHAPE_ENCODING=ISO-8859-1`) hacia `staging.ide_delegaciones_ogr_demo` (`12` `MULTIPOLYGON`, `EPSG:4326`), preservamos correctamente los acentos (`Itaembé Guazú`, `Itaembé Miní Oeste`) y comprobamos `todas_validas = f` (`false`) en el dato crudo de `staging`. Por eso el flujo productivo normaliza en [`sql/01_cargar_staging_a_final.sql`](../sql/01_cargar_staging_a_final.sql) mediante `ST_MakeValid` + `ST_CollectionExtract(..., 3)` antes de poblar `sig_ae4.delegaciones` (que exige `CHECK (ST_IsValid(geom))`).

---

## Parte III — Checklist de Entregables (Moodle + Google Drive)

### 1. Entrega Grupal en Moodle (Producto Técnico PDF + Carpeta `sql/`)
- [ ] **Archivo ZIP / carpeta `sql/`** con todos los scripts reproducibles y ordenados:
  - [`sql/00_init.sql`](../sql/00_init.sql) (esquemas `staging` y `sig_ae4`, 19 tablas, constraints `CHECK`/FK, 3 funciones y triggers)
  - [`sql/01_cargar_staging_a_final.sql`](../sql/01_cargar_staging_a_final.sql) (normalización `staging -> sig_ae4`, reparación topológica `ST_MakeValid` y reproyección `4326 -> 5348`)
  - [`sql/01_validacion.sql`](../sql/01_validacion.sql) (validación geométrica, integridad referencial y sanity checks `4A–4D`)
  - [`sql/02_consultas_a_i.sql`](../sql/02_consultas_a_i.sql) (incisos `a–i` regionales sobre `geography`)
  - [`sql/03_consultas_autoria.sql`](../sql/03_consultas_autoria.sql) (Autoría 1 Incorporación, Autoría 2A/2B/2C Mantenimiento, Autoría 3 Cobertura sobre `geom_m` `5348`)
  - [`sql/04_indices_benchmark.sql`](../sql/04_indices_benchmark.sql) (`34` índices GiST estándar + funcionales `geography`, `VACUUM ANALYZE`, trampa `geom::geography`)
  - [`sql/05_edicion_transacciones.sql`](../sql/05_edicion_transacciones.sql) (ABM, auditoría, 3 rechazos `SQLSTATE 23514`/`23503`, guía de bloqueo MVCC)
- [ ] **Producto Técnico (PDF)** consolidando:
  - Contexto, fuentes oficiales/complementarias, verificación de ingesta `GDAL 3.13.2` (`ogr2ogr.exe` + `ISO-8859-1` + `ST_MakeValid`, [`outputs/verificacion_ogr2ogr.txt`](../outputs/verificacion_ogr2ogr.txt)) y aclaración `real` (`12`) vs `simulado` (`1.417`).
  - Modelo E-R espacial ([`docs/DER_sig_ae4.md`](DER_sig_ae4.md) y [`outputs/der_sig_ae4.png`](../outputs/der_sig_ae4.png)).
  - **4 figuras cartográficas renderizadas en QGIS 4.2.1** (`QgsMapRendererParallelJob`, `1800×1150 px`) listas para insertar en el informe y presentar en la defensa:
    - [`outputs/mapas_qgis/mapa_01_regional_ign.png`](../outputs/mapas_qgis/mapa_01_regional_ign.png)
    - [`outputs/mapas_qgis/mapa_02_posadas_infraestructura_y_siniestros.png`](../outputs/mapas_qgis/mapa_02_posadas_infraestructura_y_siniestros.png)
    - [`outputs/mapas_qgis/mapa_03_autoria1_escuelas_sin_semaforo.png`](../outputs/mapas_qgis/mapa_03_autoria1_escuelas_sin_semaforo.png)
    - [`outputs/mapas_qgis/mapa_04_autoria3_brecha_delegaciones.png`](../outputs/mapas_qgis/mapa_04_autoria3_brecha_delegaciones.png)
  - Resultados verificados de validación, incisos `a–i`, Autoría 1–3, Fase III, conteo nativo `21/21` en QGIS 4.2.1 ([`outputs/verificacion_qgis_4_2_1.txt`](../outputs/verificacion_qgis_4_2_1.txt)) y Benchmark GiST ([`outputs/benchmark_resultados.md`](../outputs/benchmark_resultados.md) + [`outputs/benchmark_gist_volumen.png`](../outputs/benchmark_gist_volumen.png)).
  - **RECORDATORIO CRÍTICO:** Completar e incorporar al final del PDF las **2 citas bibliográficas en formato APA 7** tomadas del material oficial de la cátedra antes de exportar y subir.

### 2. Carpeta Individual Google Drive `AE4`
- [ ] Subir el proyecto nativo **`QGIS 4.2.1 'Belém do Pará'`** sin contraseñas embebidas (`75,997` bytes, `21` capas verificadas, `0` tokens `user=`/`password=`): [`qgis/proyecto_ae4.qgz`](../qgis/proyecto_ae4.qgz) junto con [`qgis/GUIA_QGIS_FASE3.md`](../qgis/GUIA_QGIS_FASE3.md).
- [ ] Subir los **4 mapas temáticos renderizados en QGIS 4.2.1** (`outputs/mapas_qgis/`) y los **2 reportes de verificación nativa**:
  - [`outputs/mapas_qgis/mapa_01_regional_ign.png`](../outputs/mapas_qgis/mapa_01_regional_ign.png)
  - [`outputs/mapas_qgis/mapa_02_posadas_infraestructura_y_siniestros.png`](../outputs/mapas_qgis/mapa_02_posadas_infraestructura_y_siniestros.png)
  - [`outputs/mapas_qgis/mapa_03_autoria1_escuelas_sin_semaforo.png`](../outputs/mapas_qgis/mapa_03_autoria1_escuelas_sin_semaforo.png)
  - [`outputs/mapas_qgis/mapa_04_autoria3_brecha_delegaciones.png`](../outputs/mapas_qgis/mapa_04_autoria3_brecha_delegaciones.png)
  - [`outputs/verificacion_qgis_4_2_1.txt`](../outputs/verificacion_qgis_4_2_1.txt) y [`outputs/verificacion_ogr2ogr.txt`](../outputs/verificacion_ogr2ogr.txt)
- [ ] Subir las **9 capturas interactivas** verificadas en [`qgis/GUIA_QGIS_FASE3.md`](../qgis/GUIA_QGIS_FASE3.md#L263-L275):
  - `01_qgis_proyecto_crs_capas.png` (`EPSG:5348`, grupos `Posadas` y `Regional`, subgrupo `Consultas de Autoría`, simbología `real` vs `simulado`)
  - `02_qgis_sin_password_conexion.png` (`localhost:5433`, `aitara_ae4_sig`, prompt de credenciales / sin contraseña en texto plano)
  - `03_db_manager_autoria1_cruces.png` (capa de `104` cruces escolares sin semáforo en DB Manager / Navegador SQL)
  - `04_db_manager_autoria2b_lluvia.png` (Top 30 calles sensibles a lluvia + `asfalto_sobre_empedrado`)
  - `05_db_manager_autoria3_delegaciones.png` (coroplético de `12` delegaciones por `indice_brecha_prioridad`)
  - `06_abm_insert_update_delete_auditoria.png` (edición en vivo + `sig_ae4.auditoria_ediciones`)
  - `07_rechazos_integridad_qgis.png` (errores `SQLSTATE 23514` y `23503`)
  - `08_bloqueo_mvcc_psql_qgis.png` (espera `wait_event_type = Lock` en `pg_stat_activity` y desbloqueo tras `ROLLBACK`)
  - `09_der_sig_ae4.png` ([`outputs/der_sig_ae4.png`](../outputs/der_sig_ae4.png))
- [ ] Subir respaldo de salidas reproducibles y scripts (`ae4_sig/outputs/`, `ae4_sig/sql/` y `ae4_sig/scripts/`).

### 3. Texto en Línea Individual en Moodle
- [ ] **Reflexión en las 3 dimensiones:**
  - **Saber (conceptual):** comprensión de sistemas de referencia (`EPSG:4326`, proyección planar `EPSG:5348` POSGAR 2007 Faja 6, cálculo geodésico `geography`), estructura R-Tree / MBR de índices GiST, predicados topológicos DE-9IM (`ST_Touches` vs `ST_Intersects`) y aislamiento transaccional MVCC.
  - **Saber Hacer (procedimental):** ingesta espacial automatizada con `GDAL 3.13.2` (`ogr2ogr` con `SHAPE_ENCODING=ISO-8859-1` hacia `staging`) y reparación topológica (`ST_MakeValid`, `ST_CollectionExtract`), modelado relacional con triggers (`trg_01_sync_geom_m`, `trg_02_sync_incidente_nodos`, auditoría JSONB), consultas espaciales multipredicado en PostGIS + **QGIS 4.2.1** (`21` capas verificadas + `4` mapas temáticos) y medición empírica con `EXPLAIN (ANALYZE, BUFFERS)`.
  - **Saber Ser (actitudinal/ético):** rigor y transparencia estadística al separar `12` incidentes reales de `1.417` simulados (evitando falsas inferencias causales), seguridad operativa al sanear `.qgz` (`0` tokens de credenciales) y excluir `.env` en Git, y trabajo colaborativo ordenado en rama aislada.
- [ ] **Decisión técnica justificada por integrante:**
  - **Joaquín (Índices GiST y doble SRC):** decidió implementar almacenamiento canónico `EPSG:4326` + columna proyectada `geom_m` en `EPSG:5348` mantenida por trigger `trg_01_sync_geom_m`, junto con `geom::geography` e índices GiST duales (estándar + funcional `(geom::geography)`), logrando aceleraciones verificadas de `11,87×` en cruce urbano, `47,80×` en KNN y `58,88×` al evitar el `Seq Scan` por casteo a `geography`.
  - **Compañero (Modelo relacional espacial e integración en QGIS 4.2.1):** decidió estructurar el esquema normalizado `sig_ae4` de `19` tablas con restricciones `CHECK` (`ST_IsValid`, dominio de `origen`, rango `severidad`), FKs espaciales y auditoría DML en JSONB, integrado de forma nativa en **`QGIS 4.2.1 'Belém do Pará'`** (`proyecto_ae4.qgz` con `21` capas verificadas, subgrupo de Autoría preconfigurado, `4` láminas PNG vía `QgsMapRendererParallelJob` y pruebas de edición/bloqueo concurrente).
- [ ] **Citas APA 7:** verificar que las **2 citas del material oficial de la cátedra en formato APA 7** queden incluidas tanto en el informe PDF como en la fundamentación si la consigna individual las solicita.
