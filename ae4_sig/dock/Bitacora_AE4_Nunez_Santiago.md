# UNIVERSIDAD DE LA CUENCA DEL PLATA
**Facultad de Ingeniería, Tecnología y Arquitectura**  
**Ingeniería en Sistemas de Información**  
**Sistemas de Información Geográfica**  
**Actividad de Evaluación 4 (AE4) — Bitácora Individual**  
Sede Posadas

- **Estudiante:** Nuñez, Santiago Agustín
- **DNI:** 44.952.958
- **Rol en el proyecto:** Diseño DDL espacial, ETL urbano OSM/siniestralidad, Consultas de Autoría y Concurrencia MVCC
- **Profesor:** Edgar Rolando Ibáñez
- **Fecha de entrega:** 23 de noviembre de 2026
- **AÑO:** 2026

---

## 1. Contexto del proyecto y rol individual

Bitácora documental de la participación individual en el Proyecto Integrador Final de la Actividad de Evaluación 4 (AE4), desarrollado en pareja bajo la **Opción A (PostgreSQL 16.4 + PostGIS 3.4.3 integrado con QGIS 4.2.1 y GDAL 3.13.2)** sobre la problemática de movilidad urbana, infraestructura vial y siniestralidad de la ciudad de Posadas en su marco territorial regional.

Mi responsabilidad principal abarcó la arquitectura base de PostgreSQL/PostGIS, el diseño del esquema normalizado `sig_ae4` con triggers reactivos, la ingesta de la red vial urbana de OpenStreetMap y siniestralidad vial de Posadas, la formulación de las tres consultas espaciales de autoría (`03_consultas_autoria.sql`) y la verificación de transacciones ABM, rechazos de integridad y bloqueo concurrente MVCC en la Fase III.

**Tabla 1.** *Síntesis cronológica de aportes individuales — Santiago Agustín Nuñez*

| Fecha | Fase | Actividad principal | Evidencias clave |
| :---: | :---: | :--- | :--- |
| 19/11/2026 | Fase I | Configuración de infraestructura PostgreSQL `16.4` + PostGIS `3.4.3` en Docker (`docker-compose.yml`, puerto `5433`) y diseño DDL completo del esquema `sig_ae4` (`sql/00_init.sql`) con `19` tablas normalizadas, restricciones y funciones PL/pgSQL reactivas para habilitar la ingesta paralela de capas oficiales por parte de Joaquín. | `docker-compose.yml`, `sql/00_init.sql` (`19` tablas, `3` funciones PL/pgSQL y bitácora `JSONB` `auditoria_ediciones`). |
| 20/11/2026 | Fase I | Desarrollo y ejecución del pipeline ETL de infraestructura urbana OpenStreetMap, nodos de control vial, siniestralidad de Posadas y exposición climática, seguido de la auditoría integral de integridad (`sql/01_validacion.sql`) sobre las `19` tablas unificadas (incluyendo las `13` capas oficiales cargadas por Joaquín). | Carga verificada de `1.286` calles, `7.898` intersecciones (`72` con `nivel_drenaje`), `7` nodos de control, `1.429` incidentes (`12` reales + `1.417` simulados) y `2` filas de `exposicion_clima`; salida limpia en `outputs/validacion_resultados.txt` (`18.442` geometrías válidas, `0` huérfanos en las `5` FKs). |
| 21/11/2026 | Fase II | Formulación, programación y ejecución de las tres consultas espaciales originales de autoría sobre Posadas (`sql/03_consultas_autoria.sql`), cruzando las capas oficiales IDE cargadas por Joaquín (`escuelas`, `semaforos`, `avenidas_mano_unica`, `asfalto_sobre_empedrado`, `delegaciones`) con la red OSM e incidentes: Autoría 1, Autoría 2A/2B/2C y Autoría 3. | `sql/03_consultas_autoria.sql`, `outputs/consultas_autoria_resultados.txt`, `outputs/mapas_qgis/mapa_03_autoria1_escuelas_sin_semaforo.png` (`104` cruces escolares en mano única sin semáforo) y `mapa_04_autoria3_brecha_delegaciones.png` (`12` delegaciones). |
| 22/11 al 23/11/2026 | Fase III | Ejecución y documentación de pruebas transaccionales ABM, rechazos controlados de integridad (`sql/05_edicion_transacciones.sql`) y ensayo automatizado de bloqueo concurrente MVCC (`scripts/test_bloqueo_concurrente.py`) sobre la misma instancia conectada por Joaquín desde `QGIS 4.2.1` (`proyecto_ae4.qgz`), cerrando además la auditoría contra la consigna AE4. | `outputs/edicion_transacciones_resultados.txt` (alta/baja `TEST_QGIS_01`, desplazamiento de `3.512,44 m` con reasignación automática de triggers, `8` entradas en `auditoria_ediciones` y `3` rechazos `SQLSTATE 23514`/`23503`) y `outputs/bloqueo_concurrente_resultados.txt` (`transactionid ShareLock` liberado tras `2,00 s`). |

*Nota.* Registro consolidado según las consignas oficiales de bitácora AE4 (Consignas_Bitacora_AE4.docx).

## 2. Registro cronológico detallado de actividades

### Registro 1 — 19/11/2026 (Fase I)

- **Actividad realizada:** Configuración de infraestructura PostgreSQL `16.4` + PostGIS `3.4.3` en Docker (`docker-compose.yml`, puerto `5433`) y diseño DDL completo del esquema `sig_ae4` (`sql/00_init.sql`) con `19` tablas normalizadas, restricciones y funciones PL/pgSQL reactivas para habilitar la ingesta paralela de capas oficiales por parte de Joaquín.
- **Herramientas y procedimientos utilizados:** Docker Compose (`postgis/postgis:16-3.4`), `psql`, PostgreSQL `16.4`, PostGIS `3.4.3` y SQL/PL-pgSQL (`GENERATED ALWAYS AS IDENTITY`, `FOREIGN KEY`, `CHECK (ST_IsValid(geom))`, triggers `BEFORE`/`AFTER`).
- **Dificultades encontradas y soluciones aplicadas:** El trigger de enlace espacial de incidentes (`trg_02_sync_incidente_nodos`) necesitaba la columna proyectada `geom_m` en `EPSG:5348` ya calculada antes de buscar vecinos cercanos por KNN (`<->`). Se resolvió nombrando los triggers alfabéticamente (`trg_01_sync_geom_m` seguido de `trg_02_sync_incidente_nodos`) para garantizar el orden determinístico de disparo de PostgreSQL en `BEFORE INSERT OR UPDATE`.
- **Evidencias del trabajo:** `docker-compose.yml`, `sql/00_init.sql` (`19` tablas, `3` funciones PL/pgSQL y bitácora `JSONB` `auditoria_ediciones`).
- **Decisiones técnicas y reflexión sobre lo aprendido:** Definir los esquemas desacoplados `staging` y `sig_ae4` desde el primer día permitió que Joaquín comenzara de inmediato a ingestar IGN e IDE Posadas sin chocar con las restricciones productivas. Comprendí en la práctica cómo las claves `IDENTITY`, `CHECK (ST_IsValid(geom))` y los triggers encadenados blindan la edición concurrente desde QGIS.

### Registro 2 — 20/11/2026 (Fase I)

- **Actividad realizada:** Desarrollo y ejecución del pipeline ETL de infraestructura urbana OpenStreetMap, nodos de control vial, siniestralidad de Posadas y exposición climática, seguido de la auditoría integral de integridad (`sql/01_validacion.sql`) sobre las `19` tablas unificadas (incluyendo las `13` capas oficiales cargadas por Joaquín).
- **Herramientas y procedimientos utilizados:** Python (`psycopg2-binary`, `shapely`, `ast`, `python-dotenv`), JSON/JSONL de red vial urbana OSM y prensa local curada, más consultas SQL de auditoría en `psql`.
- **Dificultades encontradas y soluciones aplicadas:** Al reconstruir `1.286` calles desde nodos ordenados de OpenStreetMap, algunas arterias homónimas discontinuas generaban trazos rectos artificiales cruzando manzanas; además, micro-segmentos degenerados fallaban `ST_IsValid`. Se implementó segmentación automática en sub-tramos cuando la distancia Haversine entre nodos superaba `300,0 m` y una extensión mínima (`~1 m`) para segmentos puntuales.
- **Evidencias del trabajo:** Carga verificada de `1.286` calles, `7.898` intersecciones (`72` con `nivel_drenaje`), `7` nodos de control, `1.429` incidentes (`12` reales + `1.417` simulados) y `2` filas de `exposicion_clima`; salida limpia en `outputs/validacion_resultados.txt` (`18.442` geometrías válidas, `0` huérfanos en las `5` FKs).
- **Decisiones técnicas y reflexión sobre lo aprendido:** Separar explícitamente `origen IN ('real', 'simulado')` con restricción `CHECK` impide mezclar los `12` siniestros reales relevados (ocurridos entre enero y noviembre de 2026, sin dato de lluvia) con los `1.417` eventos sintéticos 2023–2025. Aprendí que la calidad científica de un SIG depende tanto de la trazabilidad de sus fuentes como de su rigor geométrico.

### Registro 3 — 21/11/2026 (Fase II)

- **Actividad realizada:** Formulación, programación y ejecución de las tres consultas espaciales originales de autoría sobre Posadas (`sql/03_consultas_autoria.sql`), cruzando las capas oficiales IDE cargadas por Joaquín (`escuelas`, `semaforos`, `avenidas_mano_unica`, `asfalto_sobre_empedrado`, `delegaciones`) con la red OSM e incidentes: Autoría 1, Autoría 2A/2B/2C y Autoría 3.
- **Herramientas y procedimientos utilizados:** PostgreSQL/PostGIS (`ST_DWithin`, `ST_Distance`, `ST_Within`, `ST_Area`, `ST_Length`, operador KNN `<->` en `EPSG:5348`, `JOIN LATERAL`, `CTE` y agregaciones condicionales `COUNT(*) FILTER`).
- **Dificultades encontradas y soluciones aplicadas:** Al cruzar intersecciones con múltiples escuelas dentro de `150 m`, el `JOIN` tradicional duplicaba filas y `i.id`, impidiendo a Joaquín cargar las consultas como capas dinámicas en QGIS DB Manager (que exige clave primaria única). Se resolvió reemplazando por `JOIN LATERAL (... ORDER BY i.geom_m <-> e.geom_m LIMIT 1)` para conservar exactamente una fila por esquina (`104` intersecciones candidatas).
- **Evidencias del trabajo:** `sql/03_consultas_autoria.sql`, `outputs/consultas_autoria_resultados.txt`, `outputs/mapas_qgis/mapa_03_autoria1_escuelas_sin_semaforo.png` (`104` cruces escolares en mano única sin semáforo) y `mapa_04_autoria3_brecha_delegaciones.png` (`12` delegaciones).
- **Decisiones técnicas y reflexión sobre lo aprendido:** Normalizar la siniestralidad por exposición horaria (`1.000` horas-nodo) en Autoría 2A reveló una razón lluvia/seco simulada de `1,74×` en drenaje `BAJO`/`MEDIO` frente a `1,59×` en `ALTO`, y en Autoría 3 expuso `0` semáforos en Itaembé Guazú e Itaembé Miní Este frente a `44,31` cada `100` intersecciones en Sede Central. Confirmé el valor del SQL espacial analítico para priorizar inversión pública con evidencia.

### Registro 4 — 22/11 al 23/11/2026 (Fase III)

- **Actividad realizada:** Ejecución y documentación de pruebas transaccionales ABM, rechazos controlados de integridad (`sql/05_edicion_transacciones.sql`) y ensayo automatizado de bloqueo concurrente MVCC (`scripts/test_bloqueo_concurrente.py`) sobre la misma instancia conectada por Joaquín desde `QGIS 4.2.1` (`proyecto_ae4.qgz`), cerrando además la auditoría contra la consigna AE4.
- **Herramientas y procedimientos utilizados:** PostgreSQL `psql`, Python `psycopg2` multihilo (`threading`), vistas de sistema `pg_stat_activity` y `pg_locks`, más `QGIS 4.2.1` conectado a `localhost:5433`.
- **Dificultades encontradas y soluciones aplicadas:** Al probar concurrencia entre dos clientes, las ediciones hechas dentro de QGIS no bloqueaban inmediatamente a `psql` porque el cliente SIG mantiene los cambios en un búfer local en memoria hasta pulsar *Guardar cambios de la capa*. Para reproducir y medir de forma determinística el bloqueo, se diseñó un test con dos sesiones concurrentes sincronizadas que inspeccionan `pg_locks` y `pg_stat_activity`.
- **Evidencias del trabajo:** `outputs/edicion_transacciones_resultados.txt` (alta/baja `TEST_QGIS_01`, desplazamiento de `3.512,44 m` con reasignación automática de triggers, `8` entradas en `auditoria_ediciones` y `3` rechazos `SQLSTATE 23514`/`23503`) y `outputs/bloqueo_concurrente_resultados.txt` (`transactionid ShareLock` liberado tras `2,00 s`).
- **Decisiones técnicas y reflexión sobre lo aprendido:** Verificar que PostgreSQL MVCC nunca bloquea lecturas contra escrituras y resuelve conflictos de escritura a nivel de fila mediante `RowExclusiveLock` y `transactionid ShareLock` cerró de punta a punta la comprensión de la arquitectura cliente-servidor.

## 3. Reflexión integradora y fundamentación (Moodle)

La siguiente síntesis articula las tres dimensiones de la rúbrica evaluativa y la justificación técnica de la decisión arquitectónica principal asumida durante el proyecto, para su registro en el portafolio y en el Texto en Línea de Moodle.

- **Saber (dimensión conceptual):** Consolidé los fundamentos de modelado relacional espacial bajo el estándar *Simple Feature Access* (Open Geospatial Consortium [OGC], 2011), diferenciando el rol de las restricciones geométricas (`ST_IsValid`), la integridad referencial en tablas espaciales, los triggers reactivos en PostgreSQL/PostGIS y el control de concurrencia multiversión (MVCC) frente a clientes SIG como QGIS.
- **Saber Hacer (dimensión procedimental):** Diseñé e implementé en PostgreSQL `16.4` / PostGIS `3.4.3` un esquema normalizado de `19` tablas (`sig_ae4`), triggers PL/pgSQL para reproyección y enlace espacial automático, pipelines ETL en Python para reconstruir y validar `18.442` geometrías, consultas espaciales complejas con `JOIN LATERAL`, `ST_DWithin` y KNN `<->`, y pruebas reales de edición ABM, rechazos de restricciones y bloqueos concurrentes.
- **Saber Ser (dimensión actitudinal y ética):** Mantuve rigor metodológico y transparencia al separar estrictamente mediante restricciones `CHECK` los `12` siniestros reales relevados de prensa local respecto de los `1.417` eventos sintéticos de demostración, evitando presentar patrones simulados como evidencia empírica y validando en vivo toda la entrega antes del cierre.

### Decisión técnica relevante justificada

La decisión técnica central asumida en la Fase I y verificada en la Fase III fue implementar un **modelo relacional espacial normalizado (`sig_ae4`, `19` tablas) protegido por integridad declarativa, triggers encadenados y control transaccional MVCC**. Siguiendo el estándar *Simple Feature Access* (OGC, 2011) y los principios de calidad de datos geográficos (Olaya, 2014), todas las geometrías exigen validez estricta (`NOT NULL CHECK (ST_IsValid(geom))`), claves primarias `GENERATED ALWAYS AS IDENTITY` sin colisiones entre clientes y restricciones de dominio (`origen`, `severidad 1..5`). Sobre ese esquema, los triggers `trg_01_sync_geom_m`, `trg_02_sync_incidente_nodos` y `fn_auditar_edicion()` automatizan la coherencia métrica, los vínculos espaciales (`<= 150 m` y `<= 500 m`) y la bitácora `JSONB` ante cualquier alta o desplazamiento desde QGIS (PostGIS Project Steering Committee, 2024). En concurrencia, las pruebas comprobaron rechazos inmediatos (`SQLSTATE 23514` y `23503`) ante datos inválidos y bloqueo de fila ordenado (`RowExclusiveLock` y `transactionid ShareLock`) bajo MVCC cuando dos sesiones editan la misma tupla (PostgreSQL Global Development Group, 2024).

## 4. Referencias

- Olaya, V. (2014). *Sistemas de Información Geográfica*. Creative Commons Attribution 3.0. https://volaya.github.io/libro-sig/
- Open Geospatial Consortium. (2011). *OpenGIS Implementation Standard for Geographic information - Simple feature access - Part 1: Common architecture (OGC 06-103r4)*. https://www.ogc.org/standards/sfa/
- PostGIS Project Steering Committee. (2024). *PostGIS 3.4.3 manual*. https://postgis.net/documentation/
- PostgreSQL Global Development Group. (2024). *PostgreSQL 16.4 documentation*. https://www.postgresql.org/docs/16/
