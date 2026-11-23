# AE4 SIG — Integración Espacial Regional (IGN/NE) y Urbana (IDE Posadas + OSM + AITARA) en PostGIS

Implementación de una arquitectura SIG multicapa en **PostgreSQL 16.4 + PostGIS 3.4.3** sobre la rama aislada **`feat/ae4-sig-aitara-postgis`**, integrando cartografía oficial nacional/sudamericana (**IGN**, **BAHRA**, **Natural Earth 50m**) con infraestructura urbana y analítica de siniestralidad vial de Posadas (**IDE Posadas**, **OpenStreetMap** y **AITARA**).

> **Aislamiento de rama y datos:** Todo el proyecto AE4 reside exclusivamente dentro de `ae4_sig/`, sin modificar `master`, `src/` ni `data/`. Los archivos del repositorio AITARA (`data/territorio/`, `data/silver/`, `data/simulado/` y `src/warehouse/db.py`) se consumen estrictamente en modo solo lectura.

---

## 1. Arquitectura y Decisiones Técnicas Clave

- **Esquema productivo `sig_ae4` (`19` tablas)** + esquema auxiliar `staging` (`14` tablas temporales de carga GeoJSON):
  - `6` tablas regionales (`paises`, `provincias`, `departamentos`, `localidades`, `cursos_agua`, `rutas`).
  - `11` tablas urbanas de Posadas (`delegaciones`, `semaforos`, `escuelas`, `paradas`, `avenidas_mano_unica`, `asfalto_sobre_empedrado`, `ciclovias`, `calles`, `nodos_referencia_aitara`, `intersecciones`, `incidentes_viales`).
  - `2` tablas alfanuméricas y de auditoría (`exposicion_clima`, `auditoria_ediciones`).
- **Doble Sistema de Referencia Espacial (SRC):**
  - `geom` (`EPSG:4326`, WGS 84 geográfico): almacenamiento canónico para interoperabilidad WFS/GeoJSON y visualización en QGIS.
  - `geom_m` (`EPSG:5348`, *POSGAR 2007 / Argentina Faja 6*, metros): presente en las `11` tablas urbanas y sincronizado automáticamente `BEFORE INSERT OR UPDATE OF geom` por el trigger **`trg_01_sync_geom_m`** (`sig_ae4.fn_sync_geom_m()`).
  - `geom::geography`: cálculo geodésico elipsoidal en metros/km para la escala regional (`02_consultas_a_i.sql`), acelerado mediante índices GiST funcionales `USING GIST ((geom::geography))`.
- **Integridad, triggers y trazabilidad:**
  - `CHECK (ST_IsValid(geom))` en las `17` tablas espaciales, claves foráneas jerárquicas (`paises -> provincias -> departamentos -> localidades`), `CHECK (origen IN ('real', 'simulado'))` y `CHECK (severidad BETWEEN 1 AND 5)` en `incidentes_viales`.
  - Trigger **`trg_02_sync_incidente_nodos`** enlaza automáticamente cada incidente con la intersección OSM más cercana (`<= 150 m`) y el nodo experto AITARA más cercano (`<= 500 m`).
  - Triggers **`trg_auditar_semaforos`** y **`trg_auditar_incidentes`** registran todo `INSERT`/`UPDATE`/`DELETE` en `sig_ae4.auditoria_ediciones` con payload JSONB (`nombre`, `geom_wkt`, `anterior`, `nuevo`).

---

## 2. Fuentes Oficiales y de Respaldo Utilizadas

| Escala | Fuente | Archivo origen | Tabla destino (`sig_ae4`) | Registros cargados | SRID | Notas metodológicas |
| :--- | :--- | :--- | :--- | ---: | :--- | :--- |
| Regional | **Natural Earth 50m** *(complemento)* | `datos_externos/ne_paises_sudamerica.geojson` | `paises` | **12** | `4326` | Complemento para países limítrofes sudamericanos, ya que `ign:pais` del WFS del IGN solo contiene Argentina. |
| Regional | **IGN WFS** (`ign:provincia`) | `datos_externos/ign_provincias.geojson` | `provincias` | **24** | `4326` | Jurisdicciones argentinas + población Censo 2022 y región asignada en SQL. |
| Regional | **IGN WFS** (`ign:departamento`) | `datos_externos/ign_departamentos.geojson` | `departamentos` | **529** | `4326` | Departamentos/partidos/comunas + población 2022 de los `17` deptos. de Misiones. |
| Regional | **IGN-BAHRA WFS** (`ign:localidad_bahra`) | `datos_externos/ign_localidades.geojson` | `localidades` | **3,528** | `4326` | Asentamientos con marcas `es_capital_nacional` (`1`) y `es_capital_provincial` (`23`). |
| Regional | **IGN WFS** (`ign:lineas_de_aguas_continentales_perenne`) | `datos_externos/ign_cursos_agua.geojson` | `cursos_agua` | **1,333** | `4326` | Ríos Paraná, Uruguay e Iguazú completos (`es_principal = TRUE`, filtrando homónimos fuera de la Cuenca del Plata) + afluentes de Misiones. |
| Regional | **IGN WFS** (`ign:vial_nacional` + `ign:vial_provincial`) | `datos_externos/ign_vial_nacional.geojson`, `ign_vial_provincial.geojson` | `rutas` | **582** | `4326` | `286` tramos nacionales + `296` tramos provinciales (`CHECK jurisdiccion`). |
| Urbana | **IDE Posadas WFS** (`geonode:DELEGACIONES_MUNICIPALES_POSADAS_20250`) | `datos_externos/ide_delegaciones.geojson` | `delegaciones` | **12** | `4326` + `5348` | Enriquecidas con `poblacion_2022 = 331,753` hab. agregada espacialmente desde `ide_radios_censales_2022.geojson` (`459` radios). |
| Urbana | **IDE Posadas WFS** (`geonode:Intersecciones_Semaforizadas20250`) | `datos_externos/ide_semaforos.geojson` | `semaforos` | **280** | `4326` + `5348` | Cruces semaforizados oficiales (`214` dentro de los polígonos de delegaciones). |
| Urbana | **IDE Posadas WFS** (`geonode:unidades_funcionales_educativas`) | `datos_externos/ide_escuelas.geojson` | `escuelas` | **367** | `4326` + `5348` | Establecimientos educativos por sector (`Estatal` / `Privado`). |
| Urbana | **IDE Posadas WFS** (`geonode:Refugios_paradas__SIG_0`) | `datos_externos/ide_paradas.geojson` | `paradas` | **482** | `4326` + `5348` | Paradas y refugios del transporte urbano. |
| Urbana | **IDE Posadas WFS** (`geonode:manos_unicas`) | `datos_externos/ide_manos_unicas.geojson` | `avenidas_mano_unica` | **8** | `4326` + `5348` | Avenidas con circulación de sentido único. |
| Urbana | **IDE Posadas WFS** (`geonode:asfalto_sobreempedrado0`) | `datos_externos/ide_asfalto_sobre_empedrado.geojson` | `asfalto_sobre_empedrado` | **613** | `4326` + `5348` | Obras municipales de asfalto sobre empedrado. |
| Urbana | **IDE Posadas WFS** (`geonode:bicisendas_ciclovias0`) | `datos_externos/ide_ciclovias.geojson` | `ciclovias` | **52** | `4326` + `5348` | Red de ciclovías y bicisendas urbanas. |
| Urbana | **OSM vía AITARA** | `../data/territorio/calles.json` | `calles` | **1,286** | `4326` + `5348` | `MultiLineString` reconstruidos desde nodos OSM con corte por salto `> 300 m`. |
| Urbana | **OSM vía AITARA** | `../data/territorio/intersecciones.json` | `intersecciones` | **7,898** | `4326` + `5348` | Nodos/rotondas OSM con `nivel_drenaje` propagado desde nodos AITARA (`<= 150 m`). |
| Analítica | **AITARA (atributo experto)** | `../src/warehouse/db.py` (`seed_reference_data`) | `nodos_referencia_aitara` | **7** | `4326` + `5348` | `nivel_drenaje` (`ALTO`, `MEDIO`, `BAJO`) es un **atributo experto** extraído vía `ast` sin importar DuckDB. |
| Analítica | **AITARA (reales + simulados)** | `../data/silver/incidentes_posadas.jsonl`, `../data/simulado/incidentes.jsonl` | `incidentes_viales` | **1,429** | `4326` + `5348` | **12 `real`** (sin dato climático: `llovia IS NULL`) + **1,417 `simulado`** generados alrededor de los 7 nodos expertos. |
| Alfanum. | **AITARA (exposición climática)** | `../data/simulado/exposicion.json` | `exposicion_clima` | **2** | — | `lluvia`: `40,348` h-nodo (`5,764.00`/nodo); `seco`: `143,612` h-nodo (`20,516.00`/nodo), período `2023-01-01` a `2025-12-31`. |
| Auditoría | **Triggers PL/pgSQL** | `fn_auditar_edicion()` | `auditoria_ediciones` | **4 / 8*** | — | `*` `4` filas registradas al momento de `01_validacion.sql`; `8` acumuladas en `edicion_transacciones_resultados.txt` tras re-ejecutar Fase III. |

> **Nota sobre `shp2pgsql` y verificación en vivo con `GDAL 3.13.2` (`ogr2ogr.exe`):** La imagen Docker oficial `postgis/postgis:16-3.4` (`ae4_postgis`) no incluye preinstalado el binario `shp2pgsql` ni `ogr2ogr`. Por ello, la ingesta automatizada en [`scripts/cargar_ign_ide.py`](scripts/cargar_ign_ide.py) carga las capas GeoJSON hacia `staging.*` mediante `psycopg2` (`execute_values`) y ejecuta [`sql/01_cargar_staging_a_final.sql`](sql/01_cargar_staging_a_final.sql) para normalizar hacia `sig_ae4.*`. Adicionalmente, se ejecutó en vivo **`GDAL 3.13.2 "Iowa City"`** (`C:\Program Files\QGIS 4.2.1\bin\ogr2ogr.exe`) vía `/vsizip/` sobre el Shapefile oficial [`datos_externos/ide_delegaciones_shp.zip`](datos_externos/ide_delegaciones_shp.zip) con codificación declarada `SHAPE_ENCODING=ISO-8859-1`, cargando **`12` entidades `MULTIPOLYGON` (`EPSG:4326`, `exit code = 0`)** en `staging.ide_delegaciones_ogr_demo` ([`outputs/verificacion_ogr2ogr.txt`](outputs/verificacion_ogr2ogr.txt)). Esta prueba confirmó en `staging` **`todas_validas = f` (`false`)**, validando la necesidad de aplicar `ST_MakeValid` + `ST_CollectionExtract(..., 3)` en [`sql/01_cargar_staging_a_final.sql`](sql/01_cargar_staging_a_final.sql) antes de insertar en `sig_ae4.delegaciones` (protegida por `CHECK (ST_IsValid(geom))`). El script reproducible para otros Shapefiles y GeoJSON reside en [`scripts/cargar_ogr2ogr_referencia.ps1`](scripts/cargar_ogr2ogr_referencia.ps1).

---

## 3. Estructura de Archivos bajo `ae4_sig/`

```text
ae4_sig/
├── .env.example                                # Plantilla de variables de entorno (sin secretos reales)
├── .gitignore                                  # Excluye .env, datos_externos/, __pycache__/, *.pyc, *.tmp
├── README.md                                   # Esta documentación técnica
├── docker-compose.yml                          # Servicio postgis/postgis:16-3.4 (ae4_postgis, puerto 5433)
├── datos_externos/                             # Capas descargadas por descargar_ign_ide.py (no versionadas)
│   ├── *.geojson                               # 15 GeoJSON (NE 50m, IGN, IDE Posadas)
│   ├── ide_delegaciones_shp.zip                # Shapefile WFS oficial IDE Posadas
│   └── ide_delegaciones_shp/                   # Shapefile descomprimido (.shp, .dbf, .shx, .prj, .cst)
├── docs/
│   ├── DER_sig_ae4.md                          # Mermaid erDiagram + diccionario de las 19 tablas
│   └── GUION_DEFENSA_Y_ENTREGABLES.md          # Guion oral 2+3 min, coloquio y checklist Moodle/Drive
├── outputs/
│   ├── mapas_qgis/                             # 4 láminas PNG (1800x1150 px) vía QgsMapRendererParallelJob
│   │   ├── mapa_01_regional_ign.png
│   │   ├── mapa_02_posadas_infraestructura_y_siniestros.png
│   │   ├── mapa_03_autoria1_escuelas_sin_semaforo.png
│   │   └── mapa_04_autoria3_brecha_delegaciones.png
│   ├── benchmark_gist_volumen.png              # Curva de escalamiento GiST 10k / 100k / 1M puntos
│   ├── benchmark_resultados.md                 # Reporte de 5 iteraciones EXPLAIN (ANALYZE, BUFFERS)
│   ├── bloqueo_concurrente_resultados.txt      # Evidencia de bloqueo MVCC entre 2 sesiones
│   ├── consultas_a_i_resultados.txt            # Salida verificada de incisos regionales a–i
│   ├── consultas_autoria_resultados.txt        # Salida verificada de Autoría 1, 2A, 2B, 2C y 3
│   ├── der_sig_ae4.png                         # Diagrama Entidad-Relación en alta resolución (3 zonas)
│   ├── edicion_transacciones_resultados.txt    # Salida Fase III (ABM, auditoría y 3 rechazos SQLSTATE)
│   ├── validacion_resultados.txt               # Conteos, ST_IsValid, SRID, FKs y sanity checks 4A–4D
│   ├── verificacion_ogr2ogr.txt                # Evidencia en vivo GDAL 3.13.2 (ISO-8859-1 -> staging)
│   └── verificacion_qgis_4_2_1.txt             # Conteo nativo 21/21 QGIS 4.2.1 vs Postgres + 0 tokens
├── qgis/
│   ├── GUIA_QGIS_FASE3.md                      # Manual paso a paso de DB Manager, ABM, rechazos y MVCC
│   └── proyecto_ae4.qgz                        # Proyecto nativo QGIS 4.2.1 EPSG:5348 (21 capas, sin credenciales)
├── scripts/
│   ├── descargar_ign_ide.py                    # Descarga WFS IGN, IDE Posadas y Natural Earth 50m
│   ├── cargar_ign_ide.py                       # Carga GeoJSON a staging + normalización SQL a sig_ae4
│   ├── cargar_aitara.py                        # Carga calles, nodos expertos, intersecciones, incidentes y clima
│   ├── cargar_ogr2ogr_referencia.ps1           # Carga / referencia PowerShell para ogr2ogr (GDAL) y shp2pgsql
│   ├── construir_proyecto_qgis4.py             # Constructor PyQGIS 4.2.1: proyecto_ae4.qgz + 4 mapas + verificación
│   ├── benchmark_gist.py                       # Benchmark automatizado GiST + trampa geom::geography + gráfico
│   ├── generar_qgis_y_der.py                   # Generador reproducible de DER PNG, DER MD y QGZ de respaldo
│   └── test_bloqueo_concurrente.py             # Prueba automatizada de bloqueo MVCC a nivel de fila
└── sql/
    ├── 00_init.sql                             # DDL completo: 19 tablas, CHECK, FK, funciones y triggers
    ├── 01_cargar_staging_a_final.sql           # Limpieza topológica y carga staging -> sig_ae4
    ├── 01_validacion.sql                       # Auditoría integral de carga, FKs y sanity checks
    ├── 02_consultas_a_i.sql                    # Consultas regionales obligatorias (incisos a–i)
    ├── 03_consultas_autoria.sql                # Consultas espaciales de autoría (1, 2A, 2B, 2C, 3)
    ├── 04_indices_benchmark.sql                # 34 índices GiST (geom, geom_m, geom::geography) + EXPLAIN
    └── 05_edicion_transacciones.sql            # Pruebas ABM, auditoría y 3 rechazos de integridad
```

---

## 4. Guía Paso a Paso de Reproducción desde Cero

### Prerrequisitos
- **Docker Desktop** activo.
- **Python 3.11+** con `psycopg2-binary`, `python-dotenv`, `requests`, `shapely` y `matplotlib`.
- **`QGIS 4.2.1 'Belém do Pará'`** (`C:\Program Files\QGIS 4.2.1\bin\qgis-bin.exe` y `python-qgis.bat`) con **`GDAL 3.13.2 "Iowa City"`** (`ogr2ogr.exe`) *(para proyecto nativo `.qgz`, renderizado PyQGIS, carga Shapefile `ogr2ogr` y pruebas interactivas de Fase III)*.

### Paso 1 — Variables de entorno y arranque de PostGIS
Desde la raíz del repositorio:

```powershell
Copy-Item ae4_sig\.env.example ae4_sig\.env
# Editar ae4_sig\.env si se desea cambiar POSTGRES_PASSWORD (por defecto: ae4_sig_2026_local en compose)
docker compose -f ae4_sig/docker-compose.yml up -d
docker ps --filter "name=ae4_postgis"
```

### Paso 2 — Inicializar el esquema espacial (`sig_ae4` y `staging`)
`ae4_sig/docker-compose.yml` monta `./sql` en `/sql:ro` dentro del contenedor, por lo que puede ejecutarse de manera multiplataforma con `-f /sql/...`:

```powershell
docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -f /sql/00_init.sql
```

### Paso 3 — Descarga e ingesta de capas (IGN/NE/IDE Posadas + AITARA)

```powershell
# 3.1 Descargar fuentes oficiales hacia ae4_sig/datos_externos/ (si no existen ya localmente)
python ae4_sig/scripts/descargar_ign_ide.py

# 3.2 Cargar GeoJSON en staging.* y normalizar hacia sig_ae4.* (ejecuta 01_cargar_staging_a_final.sql)
python ae4_sig/scripts/cargar_ign_ide.py

# 3.3 Cargar red OSM, nodos expertos, incidentes reales/simulados y exposición climática
python ae4_sig/scripts/cargar_aitara.py
```

*(Prueba adicional verificada con **GDAL 3.13.2 `ogr2ogr.exe`**: [`scripts/cargar_ogr2ogr_referencia.ps1`](scripts/cargar_ogr2ogr_referencia.ps1) permite cargar el Shapefile `ide_delegaciones_shp.zip` vía `/vsizip/` con `SHAPE_ENCODING=ISO-8859-1` en `staging.ide_delegaciones_ogr_demo` — salida documentada en [`outputs/verificacion_ogr2ogr.txt`](outputs/verificacion_ogr2ogr.txt)).*

### Paso 4 — Validación geométrica, referencial y topológica (Fase I)

```powershell
docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -f /sql/01_validacion.sql > ae4_sig/outputs/validacion_resultados.txt
```

### Paso 5 — Consultas espaciales regionales (`a–i`) y de autoría (Fase II)

```powershell
docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -f /sql/02_consultas_a_i.sql > ae4_sig/outputs/consultas_a_i_resultados.txt
docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -f /sql/03_consultas_autoria.sql > ae4_sig/outputs/consultas_autoria_resultados.txt
```

### Paso 6 — Índices GiST y Benchmark reproducible (Fase IV)

```powershell
# Ejecuta las 5 corridas Sin GiST vs Con GiST, trampa geom::geography, curva 10k/100k/1M
# y al finalizar restaura los 34 índices GiST ejecutando sql/04_indices_benchmark.sql:
python ae4_sig/scripts/benchmark_gist.py
```

*(Si solo se desea crear los 34 índices GiST y ejecutar los `EXPLAIN (ANALYZE, BUFFERS)` puntuales sin la curva sintética hasta 1M, correr: `docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -f /sql/04_indices_benchmark.sql`.)*

### Paso 7 — Transacciones, integridad, concurrencia MVCC y QGIS 4.2.1 (Fase III)

```powershell
# 7.1 Pruebas SQL de ABM (INSERT/UPDATE/DELETE), auditoría y 3 rechazos SQLSTATE 23514 / 23503:
docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -f /sql/05_edicion_transacciones.sql > ae4_sig/outputs/edicion_transacciones_resultados.txt

# 7.2 Prueba automatizada de bloqueo MVCC entre dos sesiones concurrentes:
python ae4_sig/scripts/test_bloqueo_concurrente.py > ae4_sig/outputs/bloqueo_concurrente_resultados.txt

# 7.3 Regenerar proyecto nativo QGIS 4.2.1 (21 capas), verificar conteos 1:1 y renderizar los 4 mapas PNG:
& "C:\Program Files\QGIS 4.2.1\bin\python-qgis.bat" ae4_sig/scripts/construir_proyecto_qgis4.py

# 7.4 (Opcional) Abrir directamente el proyecto en QGIS 4.2.1 'Belém do Pará':
& "C:\Program Files\QGIS 4.2.1\bin\qgis-bin.exe" ae4_sig\qgis\proyecto_ae4.qgz

# 7.5 (Opcional) Regenerar diagramas DER (outputs/der_sig_ae4.png y docs/DER_sig_ae4.md):
python ae4_sig/scripts/generar_qgis_y_der.py
```

Para operar **`QGIS 4.2.1 'Belém do Pará'`** (`ae4_sig/qgis/proyecto_ae4.qgz`) sobre `localhost:5433`, consultar [`qgis/GUIA_QGIS_FASE3.md`](qgis/GUIA_QGIS_FASE3.md).

---

## 5. Resumen Ejecutivo de Resultados Verificados

### 5.1 Validación Integral — Fase I ([`outputs/validacion_resultados.txt`](outputs/validacion_resultados.txt))
- **19 tablas pobladas** con **0 geometrías nulas**, **0 geometrías inválidas (`ST_IsValid`)**, **0 errores de SRID** (`4326` en las 17 espaciales, `5348` en las 11 urbanas) y **0 registros huérfanos** en las 5 relaciones evaluadas.
- **Desglose de `incidentes_viales` (`1,429` totales):** `12` reales (`11` vinculados a intersección OSM = `91.7%`; `4` vinculados a nodo experto AITARA = `33.3%`) y `1,417` simulados (`100.0%` vinculados a intersección y nodo experto).
- **Sanity checks topológicos:**
  - `1` capital nacional (`Ciudad de Buenos Aires`) + `23` capitales provinciales = `24` provincias cubiertas.
  - `12` países sudamericanos con `ST_Touches = ST_Intersects` limpio (`0` micro-solapamientos en Natural Earth 50m).
  - `24` provincias argentinas IGN: Misiones limita únicamente con `Corrientes` por `ST_Touches`; se detectaron **4 pares con micro-solapamiento bidimensional** (`dim = 2`, `ST_Overlaps = t`) de `0.00` a `5.29 m²` (`Entre Ríos–Corrientes` `5.29 m²`, `Buenos Aires–Entre Ríos` `4.77 m²`, `San Juan–La Rioja` `0.03 m²`, `Jujuy–Salta` `0.00 m²`).

### 5.2 Consultas Regionales `a–i` — Fase II ([`outputs/consultas_a_i_resultados.txt`](outputs/consultas_a_i_resultados.txt))
- **a–c:** `140` localidades BAHRA en Misiones distribuidas en `17` departamentos; `Capital` concentra la mayor densidad (`407.39 hab/km²`, `392,919` hab. en `964.48 km²`), mientras `San Pedro` es el mayor en superficie (`3,818.06 km²`, `9.11 hab/km²`).
- **e–f (Hidrografía en Misiones):** `Río Uruguay` (`336.989 km` en `7` departamentos), `Río Paraná` (`246.439 km` en `7` departamentos) y `Río Iguazú` (`132.217 km` en `2` departamentos).
- **g (Alejamiento del Río Paraná):** `Bernardo de Irigoyen` (`General Manuel Belgrano`) es la localidad misionera más alejada a **`97.266 km`** (seguida por `Alicia Baja` a `94.259 km` y `El Soberbio` a `92.677 km`).
- **h (Accesibilidad a Rutas Nacionales en Misiones):** `RN 12` atiende a `67` localidades (`4.415 km` promedio, máx. `20.678 km`), `RN 14` a `66` localidades (`14.728 km` promedio, máx. `50.258 km` en `Alicia Baja`) y `RN 101` a `7` localidades (`5.727 km` promedio, máx. `15.811 km`).
- **i (`< 200 km` del Río Paraná):** `140` localidades en Misiones (`100.00%`) y **`1,156` localidades** en `9` jurisdicciones argentinas dentro del umbral de `200 km`.

### 5.3 Consultas de Autoría — Fase II ([`outputs/consultas_autoria_resultados.txt`](outputs/consultas_autoria_resultados.txt))
1. **Autoría 1 — Incorporación:** **`104` intersecciones OSM** dentro de `150 m` de escuelas IDE (`56` estatales, `48` privadas) y `25 m` de avenidas de mano única sin semáforo en `30 m`. Encabezadas por las únicas `3` con siniestro real en corredor `<= 250 m`: **Beethoven y Avenida Centenario** (`C.F.P. Nº 16`, `52.9 m`, `1` real / `214` sim en `250 m`), **Avenida Centenario y Derqui** (`E.P.E.T. Nº 01: "UNESCO"`, `136.3 m`, `1` real / `214` sim) y **Avenida Lavalle y Neumann** (`E.P.E.T. Nº 01: "UNESCO"`, `21.4 m`, `1` real / `117` sim).
2. **Autoría 2 — Mantenimiento:**
   - **2A (por `nivel_drenaje` experto):** en `simulado`, la razón de riesgo lluvia vs. seco por `1,000` h-nodo es **`1.74×`** en drenaje `BAJO` (`11.046` vs `6.337`) y `MEDIO` (`11.624` vs `6.678`), frente a **`1.59×`** en `ALTO` (`11.450` vs `7.214`); los `12` reales tienen `llovia IS NULL`.
   - **2B / 2C (`calles` × `asfalto_sobre_empedrado`):** ranking de `30` calles liderado por `Avenida San Martín` (puntaje `57.89`, `130` sim lluvia, `403` totales en `40 m`); en la red completa, `552` calles con obra (`1,019.30 km`) presentan razón simulada lluvia/seco de **`1.66×`** frente a **`1.82×`** en las `734` calles sin obra (`527.00 km`).
3. **Autoría 3 — Cobertura (`12` delegaciones):** contraste marcado entre **Sede Central** (`74` semáforos, **`44.31` cada `100` intersecciones**) y delegaciones sin semaforización oficial como **Itaembé Guazú** (`663` intersecciones, `10` escuelas, `0` semáforos) e **Itaembé Miní Este** (`462` intersecciones, `12` escuelas, `0` semáforos), mientras **32-33** (`51.82`) y **Riberas del Paraná** (`49.27`) registran los mayores valores de `indice_brecha_prioridad`.

### 5.4 Benchmark GiST & Geography — Fase IV ([`outputs/benchmark_resultados.md`](outputs/benchmark_resultados.md))

| Escenario (`5` iteraciones, mediana) | Filas | Sin GiST (ms) | Con GiST (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: |
| 1) `intersecciones × calles` (`ST_DWithin 30 m`) | 18,194 | 4,009.167 | 337.744 | **11.87×** |
| 2) `incidentes_viales × delegaciones` (`ST_Within`) | 1,201 | 22.916 | 1.779 | **12.88×** |
| 3) `localidades × cursos_agua` (KNN `<-> LATERAL`) | 3,528 | 5,459.990 | 114.235 | **47.80×** |
| Trampa `geom::geography` (`localidades × cursos_agua`, `200 km`) | 176,665 | 240,178.937 *(solo `geom`)* | 4,078.849 *(funcional `geography`)* | **58.88×** |
| Sintético `10,000` pts × `Avenida Quaranta` (`50 m`) | 57 | 17.005 | 0.660 | **25.77×** |
| Sintético `100,000` pts × `Avenida Quaranta` (`50 m`) | 538 | 169.070 | 6.003 | **28.16×** |
| Sintético `1,000,000` pts × `Avenida Quaranta` (`50 m`) | 5,188 | 1,134.634 | 65.363 | **17.36×** |

### 5.5 Transacciones, Integridad y Concurrencia — Fase III
- **ABM y Auditoría ([`outputs/edicion_transacciones_resultados.txt`](outputs/edicion_transacciones_resultados.txt)):** `INSERT` (`TEST_QGIS_01`, `SRID(geom_m) = 5348`), `UPDATE` en incidente `id=13` (`sim-000001`) con desplazamiento de `3,512.44 m` (recálculo de `interseccion_id: 409 -> 5069` y `nodo_referencia_id: 3 -> 1`, seguido de restauración limpia) y `DELETE`, todo registrado en `sig_ae4.auditoria_ediciones`.
- **Rechazos de integridad verificados:** polígono auto-intersectado *bowtie* en `delegaciones` (`SQLSTATE 23514`, `delegaciones_geom_check`), `origen = 'otro'` en `incidentes_viales` (`SQLSTATE 23514`, `incidentes_viales_origen_check`) y `departamento_id = 999999` en `localidades` (`SQLSTATE 23503`, `localidades_departamento_id_fkey`).
- **Bloqueo concurrente MVCC ([`outputs/bloqueo_concurrente_resultados.txt`](outputs/bloqueo_concurrente_resultados.txt)):** Sesión A (`pid_A=3616`) retuvo `RowExclusiveLock` + `transactionid ExclusiveLock` sobre `semaforos` `id=1`, bloqueando a Sesión B (`pid_B=3617`, `state=active`, `wait_event_type=Lock`, `wait_event=transactionid`, `ShareLock granted=False`) hasta el `ROLLBACK` tras `2.00 s`.

### 5.6 Integración Nativa QGIS 4.2.1 & GDAL 3.13.2
- **Proyecto nativo y verificación `21/21` ([`outputs/verificacion_qgis_4_2_1.txt`](outputs/verificacion_qgis_4_2_1.txt)):** [`scripts/construir_proyecto_qgis4.py`](scripts/construir_proyecto_qgis4.py) (ejecutado con PyQGIS `python-qgis.bat` de **`QGIS 4.2.1 'Belém do Pará'`**) generó [`qgis/proyecto_ae4.qgz`](qgis/proyecto_ae4.qgz) (`75,997` bytes, versión XML `4.2.1-Belém do Pará`, `EPSG:5348`, **`0` tokens de credenciales `user=`/`password=`**), validando `todas_validas_y_coincidentes=True` en sus **`21` capas**:
  - `17` tablas PostGIS (`11` urbanas en `Posadas (IDE + OSM + AITARA)` + `6` en `Regional (IGN)`), `1` capa WMS externa (`IDE Posadas — Delegaciones (WMS)`) y `3` capas SQL en el subgrupo `Consultas de Autoría (DB Manager / SQL)` (`Autoría 1` = `104`, `Autoría 2B` = `30`, `Autoría 3` = `12`).
- **4 láminas temáticas PNG (`1800×1150 px`) vía `QgsMapRendererParallelJob`:**
  - [`outputs/mapas_qgis/mapa_01_regional_ign.png`](outputs/mapas_qgis/mapa_01_regional_ign.png) (`550,321` bytes)
  - [`outputs/mapas_qgis/mapa_02_posadas_infraestructura_y_siniestros.png`](outputs/mapas_qgis/mapa_02_posadas_infraestructura_y_siniestros.png) (`1,135,961` bytes)
  - [`outputs/mapas_qgis/mapa_03_autoria1_escuelas_sin_semaforo.png`](outputs/mapas_qgis/mapa_03_autoria1_escuelas_sin_semaforo.png) (`1,102,203` bytes)
  - [`outputs/mapas_qgis/mapa_04_autoria3_brecha_delegaciones.png`](outputs/mapas_qgis/mapa_04_autoria3_brecha_delegaciones.png) (`467,483` bytes)
- **Carga en vivo con `GDAL 3.13.2 "Iowa City"` ([`outputs/verificacion_ogr2ogr.txt`](outputs/verificacion_ogr2ogr.txt)):** `ogr2ogr.exe` cargó `12` polígonos `MULTIPOLYGON` (`EPSG:4326`) desde `datos_externos/ide_delegaciones_shp.zip` (`/vsizip/`, `SHAPE_ENCODING=ISO-8859-1`) hacia `staging.ide_delegaciones_ogr_demo` (`exit code = 0`), evidenciando `todas_validas = f` (`false`) en el dato crudo de `staging` antes de la reparación topológica con `ST_MakeValid` hacia `sig_ae4.delegaciones`.
