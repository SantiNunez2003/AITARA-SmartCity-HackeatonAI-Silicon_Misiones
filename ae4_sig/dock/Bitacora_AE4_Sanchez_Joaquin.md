# UNIVERSIDAD DE LA CUENCA DEL PLATA
**Facultad de Ingeniería, Tecnología y Arquitectura**  
**Ingeniería en Sistemas de Información**  
**Sistemas de Información Geográfica**  
**Actividad de Evaluación 4 (AE4) — Bitácora Individual**  
Sede Posadas

- **Estudiante:** Sánchez, Joaquín Sebastián
- **DNI:** 45.452.416
- **Rol en el proyecto:** Cartografía oficial WFS/SHP, Consultas regionales (a–i), Índices GiST/Benchmark e Integración QGIS 4.2.1
- **Profesor:** Edgar Rolando Ibáñez
- **Fecha de entrega:** 23 de noviembre de 2026
- **AÑO:** 2026

---

## 1. Contexto del proyecto y rol individual

Bitácora documental de la participación individual en el Proyecto Integrador Final de la Actividad de Evaluación 4 (AE4), desarrollado en pareja bajo la **Opción A (PostgreSQL 16.4 + PostGIS 3.4.3 integrado con QGIS 4.2.1 y GDAL 3.13.2)** sobre la problemática de movilidad urbana, infraestructura vial y siniestralidad de la ciudad de Posadas en su marco territorial regional.

La responsabilidad principal que sostuve en el proyecto consistió en relevar, descargar y normalizar las fuentes geográficas oficiales nacionales y municipales (IGN, BAHRA, Natural Earth 50m, IDE Posadas e INDEC 2022) a través de un esquema `staging`, resolver las `9` consultas espaciales regionales obligatorias (`a–i`) y el diagnóstico topológico DE-9IM, diseñar y medir los `34` índices espaciales GiST hasta `1.000.000` de puntos, y construir el proyecto nativo en `QGIS 4.2.1` con sus láminas cartográficas y el informe final APA 7.

**Tabla 1.** *Síntesis cronológica de aportes individuales — Joaquín Sebastián Sánchez*

| Fecha | Fase | Actividad principal | Evidencias clave |
| :---: | :---: | :--- | :--- |
| 19/11/2026 | Fase I | Descarga automatizada de fuentes OGC WFS oficiales, ingesta cruda en el esquema `staging` definido por Santiago (`00_init.sql`), prueba de carga Shapefile con `ogr2ogr` (`GDAL 3.13.2`) y normalización/reparación topológica de las `13` tablas oficiales hacia `sig_ae4`. | `scripts/descargar_ign_ide.py`, `scripts/cargar_ign_ide.py`, `scripts/cargar_ogr2ogr_referencia.ps1`, `sql/01_cargar_staging_a_final.sql` y `outputs/verificacion_ogr2ogr.txt`. |
| 20/11/2026 | Fase II | Formulación y ejecución de las `9` consultas espaciales regionales obligatorias (incisos `a` a `i`) en `sql/02_consultas_a_i.sql` y diagnóstico topológico de fronteras provinciales del IGN, en paralelo al cierre de la carga urbana y validación global ejecutada por Santiago. | `sql/02_consultas_a_i.sql` y `outputs/consultas_a_i_resultados.txt` (`140` localidades BAHRA en Misiones, `Bernardo de Irigoyen` a `97,266 km` del Paraná, `1.156` localidades a `< 200 km` del río y accesibilidad a `RN 12`, `RN 14` y `RN 101`). |
| 21/11/2026 | Fase II | Diseño de `34` índices espaciales GiST (`sql/04_indices_benchmark.sql`) para acelerar las consultas regionales y las consultas urbanas de autoría de Santiago, junto con el benchmark reproducible (`scripts/benchmark_gist.py`) hasta `1.000.000` de puntos. | `sql/04_indices_benchmark.sql`, `scripts/benchmark_gist.py`, `outputs/benchmark_resultados.md` (`11,87×` en cruce urbano, `47,80×` en KNN, `17,36×–28,16×` hasta `1M` de puntos) y `outputs/benchmark_gist_volumen.png`. |
| 22/11 al 23/11/2026 | Fase III | Construcción programática del proyecto nativo `QGIS 4.2.1` (`proyecto_ae4.qgz`) integrando las `17` tablas PostGIS, el WMS municipal y las `3` capas SQL de autoría formuladas por Santiago, validación cruzada `1:1` de las `21` capas, renderizado de `4` láminas cartográficas, DER e informe final APA 7. | `qgis/proyecto_ae4.qgz`, `qgis/GUIA_QGIS_FASE3.md`, `outputs/verificacion_qgis_4_2_1.txt`, `outputs/mapas_qgis/*.png`, `outputs/der_sig_ae4.png`, `dock/AE4_SIG_Sanchez_Nunez.docx` y `.md`. |

*Nota.* Registro consolidado según las consignas oficiales de bitácora AE4 (Consignas_Bitacora_AE4.docx).

## 2. Registro cronológico detallado de actividades

### Registro 1 — 19/11/2026 (Fase I)

- **Actividad realizada:** Descarga automatizada de fuentes OGC WFS oficiales, ingesta cruda en el esquema `staging` definido por Santiago (`00_init.sql`), prueba de carga Shapefile con `ogr2ogr` (`GDAL 3.13.2`) y normalización/reparación topológica de las `13` tablas oficiales hacia `sig_ae4`.
- **Herramientas y procedimientos utilizados:** Python (`requests`, `psycopg2`), GeoServer WFS de IGN e IDE Posadas, `GDAL 3.13.2` (`ogr2ogr.exe` vía `/vsizip/`), `SHAPE_ENCODING=ISO-8859-1` y SQL espacial (`ST_MakeValid`, `ST_CollectionExtract`, `ST_PointOnSurface`, `ST_Within`).
- **Dificultades encontradas y soluciones aplicadas:** Se identificaron tres problemas de origen: (1) la capa `ign:pais` solo exponía Argentina, por lo que se integró Natural Earth 50m para cubrir los `12` países sudamericanos; (2) el filtro del Río Uruguay devolvía homónimos en Patagonia/Andes, resuelto filtrando por longitud `>= -62°`; y (3) el Shapefile de `delegaciones` presentó acentos rotos si no se declaraba `ISO-8859-1` y `2` autointersecciones (`todas_validas = f` en `staging`), reparadas en `01_cargar_staging_a_final.sql` antes de agregar `331.753` habitantes desde `459` radios censales 2022.
- **Evidencias del trabajo:** `scripts/descargar_ign_ide.py`, `scripts/cargar_ign_ide.py`, `scripts/cargar_ogr2ogr_referencia.ps1`, `sql/01_cargar_staging_a_final.sql` y `outputs/verificacion_ogr2ogr.txt`.
- **Decisiones técnicas y reflexión sobre lo aprendido:** Aislar la carga cruda en `staging` sobre la base desplegada por Santiago permitió diagnosticar y sanear defectos reales de cartografía oficial antes de poblar `sig_ae4` sin relajar las reglas `ST_IsValid` ni el cálculo de `geom_m`.

### Registro 2 — 20/11/2026 (Fase II)

- **Actividad realizada:** Formulación y ejecución de las `9` consultas espaciales regionales obligatorias (incisos `a` a `i`) en `sql/02_consultas_a_i.sql` y diagnóstico topológico de fronteras provinciales del IGN, en paralelo al cierre de la carga urbana y validación global ejecutada por Santiago.
- **Herramientas y procedimientos utilizados:** PostGIS `geography` sobre elipsoide WGS 84 (`ST_Area`, `ST_Length`, `ST_Distance`, `ST_DWithin`), operaciones de superposición (`ST_Union`, `ST_Intersection`, `ST_CollectionExtract`), predicados DE-9IM (`ST_Touches`, `ST_Intersects`, `ST_Overlaps`, `ST_Dimension`) y `CROSS JOIN LATERAL` con `<->`.
- **Dificultades encontradas y soluciones aplicadas:** En el inciso `d` (vecindad), `ST_Touches` difería respecto de `ST_Intersects` en `4` límites interprovinciales del IGN (*Entre Ríos–Corrientes*, *Buenos Aires–Entre Ríos*, *San Juan–La Rioja* y *Jujuy–Salta*). Al inspeccionar `ST_Dimension(ST_Intersection(a.geom, b.geom))` se comprobaron `4` micro-solapamientos bidimensionales de `0,00` a `5,29 m²`, los cuales violan la condición de interiores disjuntos exigida por `ST_Touches` según DE-9IM.
- **Evidencias del trabajo:** `sql/02_consultas_a_i.sql` y `outputs/consultas_a_i_resultados.txt` (`140` localidades BAHRA en Misiones, `Bernardo de Irigoyen` a `97,266 km` del Paraná, `1.156` localidades a `< 200 km` del río y accesibilidad a `RN 12`, `RN 14` y `RN 101`).
- **Decisiones técnicas y reflexión sobre lo aprendido:** Elegir `geom::geography` en escala regional evitó deformaciones continentales y de las `7` fajas POSGAR de Argentina (`EPSG:5343–5349`), mientras que el uso de `ST_Union` sobre cursos fluviales segmentados garantizó no duplicar longitudes al cruzar departamentos.

### Registro 3 — 21/11/2026 (Fase II)

- **Actividad realizada:** Diseño de `34` índices espaciales GiST (`sql/04_indices_benchmark.sql`) para acelerar las consultas regionales y las consultas urbanas de autoría de Santiago, junto con el benchmark reproducible (`scripts/benchmark_gist.py`) hasta `1.000.000` de puntos.
- **Herramientas y procedimientos utilizados:** Índices PostGIS `USING GIST` (`geom`, `geom_m` y funcionales `(geom::geography)`), `VACUUM ANALYZE`, `EXPLAIN (ANALYZE, BUFFERS)` y Python (`psycopg2`, `matplotlib`) para análisis y curva logarítmica.
- **Dificultades encontradas y soluciones aplicadas:** Al medir consultas regionales con `ST_DWithin(geom::geography, ...)`, el planificador descartaba el índice GiST estándar sobre `geom` (`gist_geometry_ops_2d`) y caía en `Seq Scan` (`240.178,937 ms`, `282.565` buffers). Se creó el índice GiST funcional `USING GIST ((geom::geography))` (`gist_geography_ops`), bajando a `4.078,849 ms` (`58,88×` de aceleración).
- **Evidencias del trabajo:** `sql/04_indices_benchmark.sql`, `scripts/benchmark_gist.py`, `outputs/benchmark_resultados.md` (`11,87×` en cruce urbano, `47,80×` en KNN, `17,36×–28,16×` hasta `1M` de puntos) y `outputs/benchmark_gist_volumen.png`.
- **Decisiones técnicas y reflexión sobre lo aprendido:** Comprobar empíricamente la arquitectura R-Tree / MBR (filtro grueso `&&` + refinamiento exacto GEOS) y la diferencia entre familias de operadores `geometry` y `geography` demostró que indexar mal una expresión casteada es equivalente a no tener índice en producción.

### Registro 4 — 22/11 al 23/11/2026 (Fase III)

- **Actividad realizada:** Construcción programática del proyecto nativo `QGIS 4.2.1` (`proyecto_ae4.qgz`) integrando las `17` tablas PostGIS, el WMS municipal y las `3` capas SQL de autoría formuladas por Santiago, validación cruzada `1:1` de las `21` capas, renderizado de `4` láminas cartográficas, DER e informe final APA 7.
- **Herramientas y procedimientos utilizados:** `QGIS 4.2.1 'Belém do Pará'` (`python-qgis.bat`, `QgsProject`, `QgsMapRendererParallelJob`), proveedor nativo `postgres`, servicio WMS de IDE Posadas, `matplotlib` y `python-docx`.
- **Dificultades encontradas y soluciones aplicadas:** Era crítico evitar que el archivo `.qgz` almacenara usuario o contraseña de PostgreSQL en texto plano dentro del XML empaquetado. Se parametrizaron las cadenas `datasource` sin secretos, delegando la autenticación a *AuthDB* o al prompt interactivo al abrir QGIS, y se verificaron `0` tokens `user=` / `password=` junto con coincidencia exacta de `18.588` entidades en `21/21` capas.
- **Evidencias del trabajo:** `qgis/proyecto_ae4.qgz`, `qgis/GUIA_QGIS_FASE3.md`, `outputs/verificacion_qgis_4_2_1.txt`, `outputs/mapas_qgis/*.png`, `outputs/der_sig_ae4.png`, `dock/AE4_SIG_Sanchez_Nunez.docx` y `.md`.
- **Decisiones técnicas y reflexión sobre lo aprendido:** Configurar el proyecto QGIS en `EPSG:5348` con el subgrupo de Autoría en DB Manager y validación automatizada `1:1` permitió que Santiago verificara de forma reproducible las ediciones ABM y la concurrencia MVCC.

## 3. Reflexión integradora y fundamentación (Moodle)

La siguiente síntesis articula las tres dimensiones de la rúbrica evaluativa y la justificación técnica de la decisión arquitectónica principal asumida durante el proyecto, para su registro en el portafolio y en el Texto en Línea de Moodle.

- **Saber (dimensión conceptual):** Comprendí en profundidad la organización de índices espaciales GiST basados en estructuras **R-Tree** sobre Rectángulos Mínimos Envolventes (*MBR*) (Guttman, 1984) y su ejecución en dos fases (filtro grueso *lossy* mediante `&&` o `<->` seguido de refinamiento exacto en GEOS), así como la distinción topológica DE-9IM entre `ST_Touches` y `ST_Intersects` y la incompatibilidad de familias de operadores entre `geometry` y `geography` (PostGIS Project Steering Committee, 2024).
- **Saber Hacer (dimensión procedimental):** Implementé la descarga OGC WFS e ingesta ETL con `GDAL 3.13.2` (`ogr2ogr` con `ISO-8859-1`) y saneamiento topológico (`ST_MakeValid`) desde `staging`, resolví las `9` consultas regionales (`a–i`), creé `34` índices GiST midiendo medianas con `EXPLAIN (ANALYZE, BUFFERS)` hasta `1.000.000` de puntos, e integré las `21` capas en `QGIS 4.2.1` sin credenciales embebidas, produciendo cartografía temática e informe APA 7 reproducible.
- **Saber Ser (dimensión actitudinal y ética):** Prioricé la ética técnica y la reproducibilidad: verifiqué que el proyecto `.qgz` tuviera `0` secretos embebidos y que `.env` quedara excluido del control de versiones, audité `1:1` las `18.588` entidades entre QGIS y PostGIS, y documenté de forma transparente los micro-solapamientos de origen en las fuentes oficiales.

### Decisión técnica relevante justificada

La decisión técnica determinante fue combinar el almacenamiento canónico en `EPSG:4326` con cálculo geodésico `geom::geography` en la escala regional (`a–i`) e implementar **índices GiST funcionales `USING GIST ((geom::geography))`** junto con los índices estándar sobre `geom` y `geom_m` (Olaya, 2014). Un índice GiST clásico sobre `geometry` indexa cajas 2D planas con la familia `gist_geometry_ops_2d` (Guttman, 1984; PostGIS Project Steering Committee, 2024); al castear `geom::geography` en consulta, PostGIS requiere `gist_geography_ops` y el planificador cae en `Seq Scan`. Nuestro benchmark demostró que agregar el índice funcional redujo la consulta `localidades × cursos_agua` (`200 km`) de `240.178,937 ms` (`282.565` buffers) a `4.078,849 ms` (`45.853` buffers), alcanzando un speedup verificado de `58,88×` y sosteniendo aceleraciones de `11,87×` a `47,80×` en el resto de cargas.

## 4. Referencias

- Guttman, A. (1984). R-trees: A dynamic index structure for spatial searching. *Proceedings of the 1984 ACM SIGMOD International Conference on Management of Data*, 47–57. https://doi.org/10.1145/602259.602266
- Olaya, V. (2014). *Sistemas de Información Geográfica*. Creative Commons Attribution 3.0. https://volaya.github.io/libro-sig/
- PostGIS Project Steering Committee. (2024). *PostGIS 3.4.3 manual*. https://postgis.net/documentation/
- QGIS Development Team. (2026). *QGIS Geographic Information System (Version 4.2.1 'Belém do Pará')*. Open Source Geospatial Foundation. https://qgis.org/
