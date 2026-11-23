# Actividad Foro AE4 — Santiago Agustín Nuñez

- **Estudiante:** Nuñez, Santiago Agustín
- **DNI:** 44.952.958
- **Cátedra:** Sistemas de Información Geográfica (UCP — Sede Posadas)
- **Profesor:** Edgar Rolando Ibáñez
- **Alternativa implementada:** Opción A — PostgreSQL 16.4 + PostGIS 3.4.3 + QGIS 4.2.1
- **Fecha de entrega:** 23 de noviembre de 2026

---

## 1. Elección de la tecnología

En nuestro proyecto optamos por la arquitectura cliente-servidor con **PostgreSQL 16.4 + PostGIS 3.4.3** acoplada a **QGIS 4.2.1**. Su ventaja determinante frente a GeoPackage (.gpkg, basado en SQLite sobre un único archivo local) es el soporte de **concurrencia multiversión (MVCC)** con bloqueos a nivel de fila (RowExclusiveLock), la ejecución de **triggers reactivos en PL/pgSQL** y la validación declarativa estricta mediante restricciones CHECK (ST_IsValid(geom)) y claves foráneas. Como limitación, exige administrar un motor de base de datos (que resolvimos contenedorizándolo en Docker sobre el puerto 5433) y gestionar credenciales de red. Recomiendo **QGIS + GeoPackage** para relevamientos individuales, cartografía portátil de escritorio o entregas rápidas sin infraestructura de servidor; en cambio, **PostgreSQL/PostGIS** es indispensable cuando múltiples operadores editan simultáneamente, cuando se requiere auditoría transaccional (JSONB) o cuando se procesan cruces complejos y grandes volúmenes con planificación de consultas (EXPLAIN ANALYZE).

## 2. Calidad de los datos geográficos

Los errores que más comprometen un análisis espacial son las geometrías inválidas (autointersecciones), el uso de sistemas de referencia en grados (EPSG:4326) para medir distancias métricas planas y las discontinuidades topológicas en redes viales. En nuestro proyecto, al reconstruir las 1.286 calles de Posadas a partir de nodos ordenados de OpenStreetMap, detectamos que varias arterias con el mismo nombre estaban interrumpidas por plazas o tramos no conectados; al unirlas secuencialmente se generaban líneas rectas artificiales que cruzaban manzanas enteras, además de micro-segmentos degenerados de longitud cero que fallaban el control ST_IsValid. Lo resolvimos en el pipeline ETL cortando automáticamente un nuevo sub-tramo (MultiLineString) cada vez que la distancia Haversine entre vértices consecutivos superaba los 300 m y aplicando una micro-extensión de ~1 m a los segmentos puntuales, logrando 0 geometrías inválidas en las 18.442 entidades cargadas.

## 3. Consultas y análisis espaciales

Desarrollé la consulta de **Autoría 1 (incorporación de semaforización en entorno escolar)** en EPSG:5348 (*POSGAR 2007 / Argentina Faja 6*). El procedimiento identifica cuáles de las 7.898 intersecciones viales de Posadas se encuentran simultáneamente a ≤ 150 m de alguna de las 367 escuelas oficiales y a ≤ 25 m de una avenida de mano única, pero **carecen de semáforo dentro de un radio de 30 m** (NOT EXISTS con ST_DWithin), resolviendo la asignación de la escuela más próxima mediante JOIN LATERAL y el operador KNN (<->). El análisis detectó **104 intersecciones críticas** (encabezadas por *Beethoven y Av. Centenario*, *Av. Centenario y Derqui* y *Av. Lavalle y Neumann*). Si hubiéramos usado únicamente consultas alfanuméricas (WHERE calle = ...), habría sido imposible detectar escuelas ubicadas a media cuadra sobre la arteria transversal, evaluar radios de cobertura real en metros o descartar semáforos cuyos nombres de calle difieren por abreviaturas entre padrones.

## 4. Índices espaciales y rendimiento

Sin índices espaciales, el motor debe evaluar la distancia o intersección geométrica exacta vértice por vértice entre el producto cartesiano de las tablas (Seq Scan). Al implementar los 34 índices **GiST (R-Tree sobre Rectángulos Mínimos Envolventes - MBR)**, PostGIS filtra primero en milisegundos las cajas envolventes (&&) y solo ejecuta el cálculo geométrico exacto sobre las tuplas candidatas. En nuestras mediciones con EXPLAIN (ANALYZE, BUFFERS) (mediana de 5 corridas), el cruce urbano de proximidad intersecciones × calles (ST_DWithin 30 m, 18.194 pares) bajó de **4.009,17 ms a 337,74 ms (11,87× más rápido)**, y la asignación puntual incidentes × delegaciones (ST_Within) pasó de **22,92 ms a 1,78 ms (12,88×)**.

## 5. Cartografía y comunicación de resultados

Un mapa geométricamente exacto puede fracasar comunicacionalmente si satura la vista con todas las capas activas o si mezcla datos de distinta naturaleza bajo un mismo símbolo. Al diseñar la cartografía de Posadas en QGIS 4.2.1 (Figura 6 y Mapa 3), tuvimos que separar visualmente 12 siniestros reales relevados de prensa local respecto de 1.417 eventos sintéticos de demostración: representamos los reales con **rombos rojos destacados** en el nivel superior del orden de dibujo y los sintéticos con círculos graduados con transparencia, apagando por defecto el grupo regional (IGN) para despejar la lectura urbana. Asimismo, en el mapa de brecha por delegación (Mapa 4), emplear una rampa coroplética graduada sobre la tasa normalizada (semáforos cada 100 intersecciones) permitió comunicar de un vistazo el contraste entre Sede Central (44,31) y delegaciones periféricas como Itaembé Guazú e Itaembé Miní Este (0,00).

## 6. Aplicaciones reales y toma de decisiones

Si este sistema se desplegara en la Secretaría de Movilidad Urbana de la Municipalidad de Posadas, incorporaría tres funcionalidades adicionales:

- **Integración en vivo con la estación meteorológica municipal (OPAD)** y partes oficiales de siniestralidad con marca pluviométrica real para reemplazar la serie sintética.
- **Aforos vehiculares horarios y sentidos de giro** en la red de calles para modelar congestión por franja horaria.
- **Un formulario móvil conectado a PostGIS** para que los inspectores registren incidentes o fallas semafóricas en campo disparando los triggers de validación y auditoría.

Con la información ya generada, el municipio puede tomar tres decisiones inmediatas: priorizar la instalación de semáforos o reductores en los **104 cruces escolares sobre avenidas de mano única**, planificar obras de drenaje y limpieza de sumideros antes de alertas de lluvia en los **30 corredores más sensibles** (encabezados por *Av. San Martín* y *Av. Lavalle*), y reasignar presupuesto de equipamiento vial hacia las delegaciones periféricas sin cobertura semafórica.
