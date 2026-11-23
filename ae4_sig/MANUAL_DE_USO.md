# Manual de Uso — Proyecto AE4 SIG (PostgreSQL/PostGIS + QGIS 4.2.1)

Guía operativa paso a paso para poner en marcha, consultar, visualizar, editar en vivo y regenerar todos los entregables del proyecto **AE4 — Sistemas de Información Geográfica** contenido íntegramente en `ae4_sig/`.

## Índice rápido

1. [Requisitos previos](#1-requisitos-previos)
2. [Estructura rápida de carpetas (`ae4_sig/`)](#2-estructura-rápida-de-carpetas-ae4_sig)
3. [Puesta en marcha desde cero (5 pasos)](#3-puesta-en-marcha-desde-cero-5-pasos)
4. [Ejecución de consultas, benchmark y pruebas](#4-ejecución-de-consultas-benchmark-y-pruebas)
5. [Uso en QGIS Desktop 4.2.1 (`proyecto_ae4.qgz`)](#5-uso-en-qgis-desktop-421-proyecto_ae4qgz)
6. [Regeneración y edición del informe APA 7 (`dock/`)](#6-regeneración-y-edición-del-informe-apa-7-dock)
7. [Apagado, reinicio y limpieza del entorno Docker](#7-apagado-reinicio-y-limpieza-del-entorno-docker)
8. [Solución de problemas frecuentes](#8-solución-de-problemas-frecuentes)

---

## 1. Requisitos previos

| Componente | Versión / herramienta esperada | Uso principal |
| :--- | :--- | :--- |
| **Docker Desktop** | Motor Docker + `docker compose` activos | Contenedor `ae4_postgis` (`postgis/postgis:16-3.4`) en `localhost:5433`. |
| **Python** | `3.11+` | Scripts ETL, benchmark GiST, pruebas MVCC y generación de informe. |
| **Paquetes Python base** | `psycopg2-binary`, `python-dotenv`, `requests`, `shapely`, `matplotlib` | Descarga WFS, carga en PostGIS, cálculo de geometrías y gráficos. |
| **Paquetes Python para informe** | `python-docx`, `Pillow` *(opcionales `pywin32`, `PyMuPDF`)* | Regeneración de `.docx`/`.md` y actualización automática del índice vía Word. |
| **QGIS Desktop + GDAL** | `QGIS 4.2.1 'Belém do Pará'` (`qgis-bin.exe`, `python-qgis.bat`, `ogr2ogr.exe` GDAL `3.13.2`) | Visualización, edición en vivo sobre PostGIS, render PyQGIS y prueba Shapefile `/vsizip/`. |
| **Microsoft Word** *(opcional)* | Office / Word de escritorio | Actualizar campos del `Índice general` al abrir o exportar el `.docx`. |

> **Nota sobre puertos y credenciales:** El contenedor expone PostgreSQL en el puerto **`5433`** (mapeado al `5432` interno) para no chocar con instalaciones locales de PostgreSQL. La plantilla de entorno está en [`.env.example`](.env.example). Si en tu archivo `.env` dejás `cambia_esta_password_local` o la cambiás, recordá usar exactamente esa contraseña al conectar desde QGIS o `psql`.

---

## 2. Estructura rápida de carpetas (`ae4_sig/`)

| Ruta | Contenido y función |
| :--- | :--- |
| [`docker-compose.yml`](docker-compose.yml) | Define el servicio `ae4_postgis` (`PostgreSQL 16.4 + PostGIS 3.4.3`), puerto `5433` y volumen persistente `ae4_postgis_data`. |
| [`.env.example`](.env.example) | Plantilla de variables (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`, `POSTGRES_HOST`). |
| [`sql/`](sql) | Scripts SQL ordenados (`00_init.sql` a `05_edicion_transacciones.sql`) montados como `/sql:ro` dentro del contenedor. |
| [`scripts/`](scripts) | Scripts Python y PowerShell de descarga WFS, carga ETL, `ogr2ogr`, benchmark GiST, MVCC, PyQGIS e informe APA 7. |
| [`qgis/`](qgis) | Proyecto nativo [`proyecto_ae4.qgz`](qgis/proyecto_ae4.qgz) (`21` capas, `EPSG:5348`, sin credenciales embebidas) y [`GUIA_QGIS_FASE3.md`](qgis/GUIA_QGIS_FASE3.md). |
| [`dock/`](dock) | Informe final APA 7 ([`AE4_SIG_Sanchez_Nunez.docx`](dock/AE4_SIG_Sanchez_Nunez.docx) y [`.md`](dock/AE4_SIG_Sanchez_Nunez.md)) y [`figuras/`](dock/figuras) (`logo_ucp.png` + `Figura_01` a `Figura_06`). |
| [`outputs/`](outputs) | Evidencias reproducibles en texto/Markdown, diagrama DER (`der_sig_ae4.png`), gráfico GiST y [`mapas_qgis/`](outputs/mapas_qgis). |
| [`docs/`](docs) | Documentación de respaldo: [`DER_sig_ae4.md`](docs/DER_sig_ae4.md) y [`GUION_DEFENSA_Y_ENTREGABLES.md`](docs/GUION_DEFENSA_Y_ENTREGABLES.md). |
| `datos_externos/` | Carpeta local para capas descargadas (GeoJSON y Shapefile ZIP). **Ignorada por Git**; se crea al correr `descargar_ign_ide.py`. |

---

## 3. Puesta en marcha desde cero (5 pasos)

Ejecutá todos los comandos en **PowerShell** desde la **raíz del repositorio** (carpeta padre de `ae4_sig/`):

### Paso 1 — Configurar `.env` y levantar PostgreSQL/PostGIS

```powershell
Copy-Item ae4_sig\.env.example ae4_sig\.env
# Opcional: editá ae4_sig\.env para definir tu propia POSTGRES_PASSWORD antes del primer arranque
docker compose -f ae4_sig/docker-compose.yml up -d
docker ps --filter "name=ae4_postgis"
```

Esperá hasta ver el estado **`(healthy)`** en `ae4_postgis`.

### Paso 2 — Crear esquemas, tablas, restricciones y triggers (`00_init.sql`)

```powershell
docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -f /sql/00_init.sql
```

Esto crea los esquemas `staging` y `sig_ae4` (`19` tablas productivas), las restricciones `ST_IsValid(geom)`, claves foráneas y las funciones PL/pgSQL (`trg_01_sync_geom_m`, `trg_02_sync_incidente_nodos`, `fn_auditar_edicion`).

### Paso 3 — Descargar fuentes oficiales e ingestar los datos

```powershell
# 3.1 Descarga GeoJSON y Shapefile desde IGN WFS, IDE Posadas WFS y Natural Earth 50m
python ae4_sig/scripts/descargar_ign_ide.py

# 3.2 Carga GeoJSON en staging.* y normaliza/repara geometrías hacia sig_ae4.*
python ae4_sig/scripts/cargar_ign_ide.py

# 3.3 Carga red vial OSM, nodos de control vial, incidentes y exposición climática
python ae4_sig/scripts/cargar_aitara.py
```

*(Opcional — prueba Shapefile con `ogr2ogr.exe` de GDAL 3.13.2 y codificación `ISO-8859-1` vía `/vsizip/`: ejecutar [`scripts/cargar_ogr2ogr_referencia.ps1`](scripts/cargar_ogr2ogr_referencia.ps1).)*

### Paso 4 — Validar geometrías, SRID, FKs y coherencia topológica

```powershell
docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -f /sql/01_validacion.sql
```

Resultado esperado: `19` tablas pobladas, **`18.442` geometrías válidas** (`6.008` regionales + `12.434` urbanas), `0` geometrías nulas o inválidas, `0` errores de SRID (`4326`/`5348`) y `0` registros huérfanos. *(Para sobrescribir el archivo de evidencia, redirigí con `> ae4_sig/outputs/validacion_resultados.txt`.)*

### Paso 5 — Crear los 34 índices espaciales GiST

```powershell
docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -f /sql/04_indices_benchmark.sql
```

Este paso crea los `34` índices GiST (`geom`, `geom_m` y funcionales `(geom::geography)`) necesarios para que las consultas regionales, de autoría y QGIS operen a máxima velocidad.

---

## 4. Ejecución de consultas, benchmark y pruebas

Con la base ya inicializada podés correr las consultas analíticas, el benchmark o las pruebas de integridad desde PowerShell:

```powershell
# Consultas regionales obligatorias (incisos a–i)
docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -f /sql/02_consultas_a_i.sql > ae4_sig/outputs/consultas_a_i_resultados.txt

# Consultas urbanas de autoría (1, 2A, 2B, 2C y 3)
docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -f /sql/03_consultas_autoria.sql > ae4_sig/outputs/consultas_autoria_resultados.txt

# Benchmark completo GiST (5 corridas EXPLAIN ANALYZE + curva 10k / 100k / 1M; al finalizar restaura los 34 índices)
python ae4_sig/scripts/benchmark_gist.py

# Pruebas transaccionales ABM, auditoría JSONB y 3 rechazos SQLSTATE (23514 / 23503)
docker exec -i ae4_postgis psql -U ae4_user -d aitara_ae4_sig -f /sql/05_edicion_transacciones.sql > ae4_sig/outputs/edicion_transacciones_resultados.txt

# Prueba automatizada de bloqueo concurrente MVCC entre dos sesiones PostgreSQL
python ae4_sig/scripts/test_bloqueo_concurrente.py > ae4_sig/outputs/bloqueo_concurrente_resultados.txt
```

Para abrir una **sesión interactiva `psql`** dentro del contenedor:

```powershell
docker exec -it ae4_postgis psql -U ae4_user -d aitara_ae4_sig
```

*(Comandos útiles dentro de `psql`: `\dt sig_ae4.*` lista las `19` tablas; `\di sig_ae4.*` lista los índices; `\q` sale de `psql`.)*

---

## 5. Uso en QGIS Desktop 4.2.1 (`proyecto_ae4.qgz`)

El archivo [`ae4_sig/qgis/proyecto_ae4.qgz`](qgis/proyecto_ae4.qgz) ya incluye las **`21` capas configuradas** (`17` tablas PostGIS, `3` capas SQL dinámicas de autoría y `1` capa WMS externa de IDE Posadas) en **`EPSG:5348`**. Por seguridad, **no contiene usuario ni contraseña guardados**.

### 5.1 Parámetros de conexión PostgreSQL en QGIS

Si configurás la conexión por primera vez desde **Navegador → PostgreSQL → Nueva conexión...**:

| Campo | Valor exacto |
| :--- | :--- |
| **Nombre** | `AE4_SIG_Posadas` *(o el nombre de tu preferencia)* |
| **Anfitrión (`Host`)** | `localhost` |
| **Puerto (`Port`)** | `5433` |
| **Base de datos (`Database`)** | `aitara_ae4_sig` |
| **Modo SSL (`SSL mode`)** | `disable` |
| **Autenticación** | Recomendado: pestaña **Configuraciones (`+`)** con AuthDB cifrado (`ae4_user` + tu `POSTGRES_PASSWORD`). Alternativa: ingresar usuario y clave solo al abrir sin tildar *Guardar*. |
| **Opciones útiles** | Tildar **`Listar también las tablas sin geometría`** (para inspeccionar `exposicion_clima` y `auditoria_ediciones`). |

### 5.2 Abrir y operar el proyecto

```powershell
& "C:\Program Files\QGIS 4.2.1\bin\qgis-bin.exe" ae4_sig\qgis\proyecto_ae4.qgz
```

1. Al abrirlo, QGIS pedirá usuario (`ae4_user`) y contraseña (`POSTGRES_PASSWORD` de `ae4_sig/.env`).
2. En el panel **Capas** verás dos grupos principales:
   - **`Posadas (IDE + OSM + AITARA)`** *(activo por defecto)*: incluye el subgrupo **`Consultas de Autoría (DB Manager / SQL)`** (`Autoría 1`, `Autoría 2B`, `Autoría 3`), las `11` capas urbanas de `sig_ae4` y la capa WMS externa de delegaciones.
   - **`Regional (IGN)`** *(apagado por defecto para navegar ágilmente sobre Posadas)*: contiene las `6` capas regionales (`paises`, `provincias`, `departamentos`, `localidades`, `cursos_agua`, `rutas`).
3. **Para editar datos en vivo (ABM):** seleccioná una capa editable (por ejemplo `semaforos`), activá **Conmutar edición** (lápiz), agregá o mové un punto, completá atributos y pulsá **Guardar cambios de la capa**. Al instante podés verificar desde `psql` que `geom_m` (`EPSG:5348`) se recalculó solo y quedó asentado en `sig_ae4.auditoria_ediciones`.
4. **Si querés regenerar desde cero el `.qgz` y los 4 mapas PNG (`1800 × 1150 px`):**

```powershell
& "C:\Program Files\QGIS 4.2.1\bin\python-qgis.bat" ae4_sig/scripts/construir_proyecto_qgis4.py
```

Para la guía detallada paso a paso de DB Manager, captura de pantallas de defensa y demostración de bloqueos MVCC desde la interfaz gráfica, consultá [`ae4_sig/qgis/GUIA_QGIS_FASE3.md`](qgis/GUIA_QGIS_FASE3.md).

---

## 6. Regeneración y edición del informe APA 7 (`dock/`)

Los entregables finales del informe se encuentran en [`ae4_sig/dock/`](dock):
- [`ae4_sig/dock/AE4_SIG_Sanchez_Nunez.docx`](dock/AE4_SIG_Sanchez_Nunez.docx)
- [`ae4_sig/dock/AE4_SIG_Sanchez_Nunez.md`](dock/AE4_SIG_Sanchez_Nunez.md)
- [`ae4_sig/dock/figuras/`](dock/figuras) (`logo_ucp.png` y `Figura_01` a `Figura_06`)

### Cómo regenerar si modificás texto o figuras

1. Si actualizaste datos en PostGIS y querés re-renderizar la `Figura 6` limpia con `QGIS 4.2.1`:
   ```powershell
   & "C:\Program Files\QGIS 4.2.1\bin\python-qgis.bat" ae4_sig/scripts/preparar_figuras_informe.py qgis
   ```
   *(Las figuras `Figura_01` a `Figura_05` y `logo_ucp.png` ya se encuentran listas en `ae4_sig/dock/figuras/`.)*
2. Para regenerar el `.docx` y el `.md` desde [`scripts/generar_informe_ae4.py`](scripts/generar_informe_ae4.py):
   ```powershell
   python ae4_sig/scripts/generar_informe_ae4.py
   ```
3. Si abrís `AE4_SIG_Sanchez_Nunez.docx` en Microsoft Word tras regenerarlo desde Python, aceptá la actualización de campos automática al abrir (o hacé clic derecho sobre el **`Índice general` → Actualizar campos → Actualizar toda la tabla**) para refrescar la numeración de páginas.

> **Pendientes manuales antes de entregar:** completá en la carátula el **`[Completar DNI]`** de Santiago Agustín Núñez y en la sección **7. Portafolio digital** el **`[Insertar enlace de carpeta AE4 en Google Drive]`**.

---

## 7. Apagado, reinicio y limpieza del entorno Docker

| Acción | Comando en PowerShell | Efecto sobre los datos |
| :--- | :--- | :--- |
| **Pausar el motor** *(uso diario)* | `docker compose -f ae4_sig/docker-compose.yml stop` | Detiene el contenedor **conservando** base, tablas e índices. |
| **Volver a encender** | `docker compose -f ae4_sig/docker-compose.yml start` | Reanuda `ae4_postgis` en segundos sin recargar nada. |
| **Bajar contenedor sin borrar datos** | `docker compose -f ae4_sig/docker-compose.yml down` | Elimina el contenedor pero **mantiene** el volumen `ae4_postgis_data`. |
| **Reinicio limpio total** *(¡cuidado!)* | `docker compose -f ae4_sig/docker-compose.yml down -v` | **Borra toda la base de datos** (`ae4_postgis_data`). Requiere repetir la Sección 3 desde el Paso 1. |

---

## 8. Solución de problemas frecuentes

| Síntoma | Causa probable | Solución |
| :--- | :--- | :--- |
| `connection refused` al conectar a `localhost:5433` | Docker Desktop cerrado o contenedor detenido. | Iniciá Docker Desktop y ejecutá `docker compose -f ae4_sig/docker-compose.yml up -d`. |
| QGIS pide usuario/clave cada vez que abrís `.qgz` | Comportamiento intencional: el proyecto no guarda secretos en texto plano. | Ingresá `ae4_user` y tu `POSTGRES_PASSWORD`, o guardalos cifrados en **AuthDB** de QGIS. |
| `password authentication failed` | La contraseña de `.env` difiere de la creada originalmente en el volumen Docker. | Verificá `ae4_sig/.env`; si ya existía el volumen con otra clave, recrealo con `down -v` o actualizá la clave vía `ALTER USER`. |
| Error `SQLSTATE 23514` o `23503` al guardar en QGIS | Restricción de integridad (`ST_IsValid`, dominio `CHECK` o `FOREIGN KEY`). | Corregí la geometría auto-intersectada o el valor del atributo antes de confirmar la edición. |
| Acentos/eñes rotos al importar Shapefiles con `ogr2ogr` | Falta declarar codificación Latin-1 del archivo `.dbf`. | Configurá `SHAPE_ENCODING=ISO-8859-1` como muestra [`scripts/cargar_ogr2ogr_referencia.ps1`](scripts/cargar_ogr2ogr_referencia.ps1). |
| Consultas con `geom::geography` muy lentas (`Seq Scan`) | Falta el índice GiST funcional específico para geografía. | Ejecutá `/sql/04_indices_benchmark.sql` para restaurar los índices `USING GIST ((geom::geography))`. |
