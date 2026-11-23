# Actividad Foro AE4 — Joaquín Sebastián Sánchez

- **Estudiante:** Sánchez, Joaquín Sebastián
- **DNI:** 45.452.416
- **Cátedra:** Sistemas de Información Geográfica (UCP — Sede Posadas)
- **Profesor:** Edgar Rolando Ibáñez
- **Alternativa implementada:** Opción A — PostgreSQL 16.4 + PostGIS 3.4.3 + QGIS 4.2.1
- **Fecha de entrega:** 23 de noviembre de 2026

---

## 1. Elección de la tecnología

Al implementar la **Opción A (PostgreSQL 16.4 + PostGIS 3.4.3 + QGIS 4.2.1)** comprobamos que su mayor fortaleza frente a un archivo local **GeoPackage** radica en la capacidad de desacoplar la arquitectura en esquemas (staging para recepción cruda y sig_ae4 para producción validada), utilizar tipos geodésicos nativos (geography sobre el elipsoide WGS 84) con **índices funcionales GiST**, y conectar múltiples clientes (psql, scripts Python, GDAL/ogr2ogr y QGIS) de forma segura sin almacenar credenciales en texto plano dentro del archivo .qgz. Su principal costo es la complejidad inicial de configuración y red frente a la inmediatez de un .gpkg. Recomendaría **QGIS/GeoPackage** para proyectos académicos o profesionales de un solo analista donde prime la portabilidad del archivo; y **PostgreSQL/PostGIS** para infraestructuras de datos espaciales (IDE) institucionales donde conviven escalas regionales y urbanas, automatización ETL y control de integridad centralizado.

## 2. Calidad de los datos geográficos

Incluso las capas provenientes de organismos oficiales pueden contener defectos topológicos o de codificación de caracteres que alteran predicados espaciales sin arrojar errores visibles a simple vista. En nuestro proyecto encontramos dos casos concretos al ingestar fuentes oficiales:

- Al importar el Shapefile de delegaciones municipales de IDE Posadas con ogr2ogr (GDAL 3.13.2), fue necesario declarar SHAPE_ENCODING=ISO-8859-1 y reparar en staging **dos polígonos con autointersecciones** (ST_IsValid = false) aplicando ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Force2D(geom)), 3)) antes de cruzarlos con los 459 radios censales del Censo 2022 (331.753 habitantes).
- En la capa provincial del IGN detectamos que ST_Touches omitía 4 fronteras interprovinciales reales (*Entre Ríos–Corrientes*, *Buenos Aires–Entre Ríos*, *San Juan–La Rioja* y *Jujuy–Salta*); al auditarlas con ST_Dimension(ST_Intersection(a.geom, b.geom)) = 2 demostramos que presentaban micro-solapamientos bidimensionales de 0,00 a 5,29 m² que violaban la condición DE-9IM de interiores disjuntos de ST_Touches.

## 3. Consultas y análisis espaciales

Entre las consultas desarrolladas destaco dos escalas: en el ámbito regional (inciso h), la asignación de cada una de las **140 localidades BAHRA de Misiones** a su Ruta Nacional más cercana (RN 12, RN 14 o RN 101) calculando la distancia geodésica exacta sobre el elipsoide (ST_Distance(geom::geography) + CROSS JOIN LATERAL), determinando que la RN 12 articula a 67 localidades (4,42 km promedio) y la RN 14 a 66 (14,73 km promedio, con máximo en *Alicia Baja* a 50,26 km); y en el ámbito urbano (**Autoría 3**), el cruce multipredicado (ST_Within y ST_Area) que integra población censal 2022, superficie en km², intersecciones, escuelas, paradas y semáforos dentro de cada una de las **12 delegaciones de Posadas**. Con una consulta puramente alfanumérica sería imposible agregar radios censales que no poseen columna de delegación municipal, medir la densidad real por kilómetro cuadrado o calcular la tasa de cobertura semafórica cada 100 intersecciones físicas contenidas en el polígono.

## 4. Índices espaciales y rendimiento

En bases espaciales de escala regional y urbana, los índices B-tree tradicionales no sirven para búsquedas bidimensionales porque un orden escalar 1D no preserva la vecindad espacial 2D. Al implementar 34 índices **GiST (R-Tree)**, comprobamos tres efectos críticos en nuestro benchmark (EXPLAIN (ANALYZE, BUFFERS)):

- En la búsqueda de vecinos cercanos KNN (<->) entre 3.528 localidades y 1.333 cursos de agua, el tiempo cayó de **5.459,99 ms (1.238.382 bloques leídos) a 114,24 ms (35.833 bloques), una mejora de 47,80×**.
- Descubrimos además la trampa del casteo geom::geography: cuando una tabla solo tiene índice GiST sobre geom (geometry), consultar ST_DWithin(geom::geography, ...) cambia la familia de operadores y fuerza un Seq Scan de **240.178,94 ms (~4 minutos)**; al crear el índice GiST funcional USING GIST ((geom::geography)), el tiempo descendió a **4.078,85 ms (58,88× de aceleración)**.
- En la curva sintética de 10.000, 100.000 y 1.000.000 de puntos sobre *Av. Quaranta*, GiST mantuvo la consulta en **65,36 ms (8.600 buffers)** frente a **1.134,63 ms (3.008.336 buffers)** sin índice (17,36×).

## 5. Cartografía y comunicación de resultados

La precisión topológica y métrica en PostGIS es condición necesaria pero no suficiente para que un mapa sea útil a un decisor. Al renderizar las cuatro láminas temáticas del proyecto en **QGIS 4.2.1** (1800 × 1150 px), comprobamos que la elección de la escala, el sistema de referencia visual (EPSG:5348 para Posadas y EPSG:4326 para el marco regional del NEA) y la jerarquía de etiquetas cambian por completo la legibilidad. Por ejemplo, en el mapa regional (Figura 2), mostrar simultáneamente las 3.528 localidades BAHRA y los 1.333 tramos hidrográficos con el mismo grosor producía un empaste ilegible; fue necesario destacar con trazo diferenciado los tres ríos principales (*Paraná*, *Uruguay* e *Iguazú*), jerarquizar rutas nacionales frente a provinciales y filtrar etiquetas a capitales e hitos extremos (*Bernardo de Irigoyen* a 97,27 km del Paraná). Del mismo modo, en los mapas urbanos, combinar etiquetas selectivas solo sobre los nodos críticos evita ocultar la red vial de base.

## 6. Aplicaciones reales y toma de decisiones

Para llevar este desarrollo a producción en un organismo provincial o municipal (como la Dirección de Tránsito de Posadas o Vialidad Provincial), sumaría tres mejoras:

- **Publicación de las vistas analíticas de PostGIS mediante GeoServer (servicios OGC WMS/WFS)** para que otras áreas municipales consuman en vivo las capas de Autoría 1, 2 y 3 desde cualquier navegador o visor web.
- **Ruteo topológico con pgRouting** sobre la tabla calles e intersecciones para calcular tiempos de respuesta de ambulancias o inspectores hacia los nodos críticos.
- **Actualización incremental automatizada (cron ETL)** contra los servicios WFS de IDE Posadas e IGN.

A partir de la información generada, las autoridades pueden decidir con respaldo empírico dónde instalar nuevos complejos semafóricos en barrios en expansión como **Itaembé Guazú** (663 intersecciones, 10 escuelas y 0 semáforos), en qué tramos combinar obras de **asfalto sobre empedrado** con desagües pluviales (donde la sensibilidad bajo lluvia difiere entre 1,66× con obra y 1,82× sin obra), y cómo planificar la conectividad de localidades misioneras alejadas de los corredores troncales RN 12 y RN 14.
