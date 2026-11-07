# AITARA — Respuestas Consolidadas para la Guía Dinámica de Trabajo
**Hackathon Silicon Misiones 2026 — Track: Smart City (Desafío 1: Movilidad Urbana)**  
**Equipo:** AITARA (Santiago Nuñez, Joaquín Sanchez, Facundo Fraga, Ana Florencia Zayas)  
**Mentores:** Enzo Mereles (3764-730955), Ulises (3764-581417)

---

## DÍA 1 — Comprensión del Desafío y Organización del Equipo

### 1. ¿Qué desafío eligió el equipo?
Track Smart City — Desafío 1: *IA para Entender y Anticipar la Movilidad Urbana*.

### 2. ¿Qué problema principal identificamos?
Ruptura en la cadena de transformación del dato en decisión operativa: el municipio de Posadas gestiona el tránsito de manera reactiva debido a que la información territorial se releva de forma manual, fragmentada y con retraso temporal, impidiendo anticipar congestiones o incidentes viales antes de que los corredores colapsen.

### 3. ¿Quiénes son los principales usuarios o actores afectados?
- **Usuarios directos:** Operadores y planificadores del Centro de Operaciones y la Dirección de Tránsito / Movilidad Urbana de Posadas (toman la decisión de despacho y logística preventiva).
- **Ejecutores en territorio:** Inspectores de tránsito y patrullas móviles (requieren asignación previa en puntos calientes en lugar de acudir cuando el nudo ya es irreversible).
- **Beneficiarios indirectos:** Ciudadanos, conductores y usuarios del transporte público que sufren las demoras y el riesgo de siniestros.

### 4. ¿Cómo se resuelve actualmente esta problemática?
De manera artesanal, subjetiva y reactiva: conteos vehiculares manuales con planillas de papel cada 15 minutos en esquinas testigo, llamados al 911 o reclamos vecinales cuando el accidente ya ocurrió, y lectura diferida de noticias en portales o grupos de mensajería horas después del hecho.

### 5. ¿Qué información tenemos disponible?
- Pliego oficial del Desafío 1 (Silicon Misiones).
- Entrevista técnica inicial con Matías Ruiz (Director de Movilidad Urbana de Posadas).
- Geoportal abierto de IDE Posadas (capas vectoriales de semaforización, establecimientos educativos y transporte público).
- Topología de la red vial de Posadas vía OpenStreetMap (OSMnx).
- Portales públicos de noticias locales (Canal 12, El Territorio, Misiones Online).

### 6. ¿Qué información necesitamos investigar o validar?
- Estructura y motor de las bases de datos que utiliza actualmente la municipalidad para garantizar compatibilidad nativa (PostgreSQL/PostGIS u homólogos).
- Registros históricos de siniestralidad georreferenciados para calibrar las ponderaciones de riesgo.
- Nivel de acceso y frecuencia de actualización de los datos meteorológicos locales (OPAD).

### 7. Primer foco de trabajo del equipo
Mapear la problemática bajo la pirámide de transformación del dato (DIKW: Datos -> Información -> Conocimiento -> Sabiduría) y estructurar una arquitectura de integración ELT que alimente un sistema de soporte a decisiones (DSS) explicable, sin intervenir la infraestructura física de semáforos.

### 8. Principales dudas o supuestos
- **Supuesto 1:** El municipio dispone de un entorno relacional o GIS compatible con estándares OGC (`ST_*`), lo que permite que nuestra solución sea anexable sin imponer cambios en sus sistemas internos.
- **Supuesto 2:** La geocodificación y análisis de noticias locales sumado a variables exógenas (lluvias de la OPAD y horarios escolares) provee una señal temprana suficiente para anticipar incidentes con 30 a 60 minutos de ventana.
- **Duda técnica:** Cuál es el grado de centralización real de la red semafórica actual y si emite logs o únicamente opera con controladores aislados en calle.

---

## DÍA 2 — Comprensión y Validación del Problema

### 1. Problema validado
Ruptura en la cadena de transformación del dato de movilidad urbana en Posadas: la gestión opera de forma reactiva porque los datos territoriales se generan de forma manual, dispersa y diferida (planillas de 15 minutos y noticias con horas de retraso), impidiendo anticipar incidentes o desplegar operativos preventivos en corredores críticos.

### 2. Usuario o actor principal
- **¿Quién es?** Operador de Despacho y Planificación de Tránsito / Movilidad Urbana de la Municipalidad de Posadas.
- **¿Qué necesidad tiene?** Disponer de información territorial correctamente estructurada, normalizada y georreferenciada en tiempo y espacio, sumada a un Sistema de Soporte a Decisiones (DSS) explicable que le permita accionar y coordinar recursos preventivos (inspectores, conos, balizas) con 30 a 60 minutos de anticipación.
- **¿Qué dificultad experimenta actualmente?** La información y datos existentes se encuentran dispersos, manuales y desacoplados en silos (planillas de papel, capas GIS aisladas, noticias tardías), obligándolo a operar a ciegas y de manera puramente reactiva.

### 3. Evidencias o información que respaldan el problema
- Entrevista técnica directa con Matías Ruiz (Director de Movilidad Urbana de Posadas).
- Cuellos de botella recurrentes documentados en accesos escolares (ej. Av. Corrientes y Tucumán a las 07:00 AM).
- Alta siniestralidad diferida de motociclistas en avenidas periféricas (Quaranta, Alicia M. de Justo).
- Falta de cruce entre alertas meteorológicas (OPAD) y vulnerabilidad topográfica de calzadas.

### 4. Datos disponibles
- Capas GIS abiertas de IDE Posadas (semaforización, escuelas, líneas de transporte).
- Red vial topológica en OpenStreetMap (OSMnx).
- Portales locales de noticias (Canal 12, El Territorio, Misiones Online) para minado y scoring de siniestros.
- Datos climáticos de precipitación en tiempo real e históricos (OPAD / Open-Meteo).
*Nota metodológica:* Estos datos dan cobertura directa a las 4 dimensiones del modelo: IDE Posadas y OSMnx alimentan la red vial; OPAD aporta la dimensión ambiental; calendarios escolares/administrativos cubren la demanda programada; y la minería de noticias cubre el riesgo siniestral.

### 5. Datos o información que todavía necesitamos
- Estructura y esquemas relacionales exactos de las bases de datos municipales existentes para acoplarnos sin fricción (PostgreSQL/PostGIS).
- Registros históricos de despachos y partes de inspectores para calibrar las ponderaciones del motor de inferencia.

### 6. Restricciones detectadas
- **Pliego Silicon Misiones:** Cero intervención física o automática sobre controladores semafóricos; prohibido emitir peritajes o deslindar culpas legales. Exclusivamente sistema de apoyo a la toma de decisiones (DSS).
- **Operativas:** Solución de arquitectura abierta (SQL / OGC `ST_*`), anexable y no disruptiva con los sistemas preexistentes del municipio.

### 7. Alcance del proyecto (Scope del MVP)
Desarrollo de un Decision Support System (DSS) enfocado en anticipar congestión y riesgo vial en nodos críticos de Posadas mediante un motor de inferencia explicable (XAI). Para anticipar sin depender de costosos sensores de conteo continuo en calle, el sistema descompone la movilidad en 4 dimensiones integradas:
1. **Dimensión Temporal y Demanda (Event-Driven):** Sincronía de la vida urbana (horarios escolares, comercio, eventos). *Comportamiento:* Determinístico; cruza calendarios y horarios pico contra la capacidad de cada arteria.
2. **Dimensión Meteorológica de Calzada (Context-Driven):** Alteraciones por el entorno físico (lluvia, visibilidad). *Comportamiento:* Dinámico; correlaciona estaciones meteorológicas (OPAD) con topografía y cuencas de escurrimiento.
3. **Dimensión Topológica y Capacidad Vial (Network-Driven):** Vulnerabilidad física y geométrica de la red (anchos de calzada, sentidos únicos, badenes, giros a la izquierda, paradas de colectivos) que reducen la capacidad de la arteria. *Comportamiento:* Cuasi-estático; define la fricción base de cada nodo del grafo vial.
4. **Dimensión de Riesgo Siniestral (Safety-Driven):** Patrones de riesgo humano e infracciones. *Comportamiento:* Probabilístico; procesa el histórico de siniestros minado de noticias locales mediante clustering espacial.

### 8. Criterios iniciales de éxito
- Extracción y normalización estructurada y validada de siniestros a partir de fuentes dispersas.
- Capacidad de predecir incrementos de congestión con al menos 30 minutos de anticipación.
- Generación de recomendaciones operativas claras y explicables (XAI), reduciendo el tiempo de reacción municipal de horas a minutos.

---

## DÍA 3 — Ideación y Diseño de la Solución

### 1. Alternativas de solución evaluadas
- **Alternativa A: Simulación de Microtráfico Físico (tipo SUMO / Aimsun)**  
  *Pros:* Alta fidelidad visual de colas de vehículos.  
  *Contras:* Requiere matrices Origen-Destino (O-D) calibradas y sensores continuos por carril que Posadas no posee (*garbage in, garbage out*).  
  *Veredicto:* **Descartada por inviabilidad de datos de entrada.**
- **Alternativa B: Tablero Descriptivo de BI Clásico (PowerBI / Metabase)**  
  *Pros:* Rápido armado, bajo costo de cómputo.  
  *Contras:* Es 100% retroactivo. Muestra el pasado, pero no anticipa situaciones operativas para el despacho preventivo de hoy.  
  *Veredicto:* **Descartada por no resolver la problemática de anticipación.**
- **Alternativa C: Pipeline ELT + Motor de Riesgo Multivariado Explicable (AITARA - Seleccionada)**  
  *Pros:* No depende de sensores IoT costosos; integra datos existentes (IDE, noticias, clima); entrega recomendaciones accionables con 30-60 minutos de anticipación; respeta 100% las restricciones del pliego.  
  *Contras:* Requiere normalización y geocodificación de noticias locales no estructuradas.  
  *Veredicto:* **Seleccionada por balance óptimo entre viabilidad, valor predictivo y adopción municipal.**

### 2. Justificación del rol específico de la Inteligencia Artificial
La IA no se incorpora como un adorno ni como un chatbot genérico, sino en dos eslabones críticos donde el software tradicional falla:
1. **Extracción y Geocodificación de Señales Débiles (NLP con Structured Outputs):** Minado automatizado de incidentes en noticias locales (Canal 12, El Territorio, Misiones Online), extrayendo intersección, tipología de vehículo, severidad y factores temporales con validación estricta de esquema JSON.
2. **Inferencia Espaciotemporal y Explicabilidad (XAI):** Ponderación multidimensional no lineal entre variables exógenas (lluvia OPAD + horarios escolares + topología) para emitir una recomendación con justificación causal que el operador humano pueda auditar y validar.

### 3. Prototipo a desarrollar (MVP)
- **Tipo:** Aplicación web analítica e interactiva (Dashboard DSS en Streamlit + Leaflet/PyDeck).
- **Caso Piloto:** Corredor y nodo escolar de **Av. Corrientes y Tucumán (Colegio San Basilio Magno)** en horario pico de ingreso escolar (07:00 AM) bajo condiciones climáticas adversas.
- **Funcionalidades del MVP:**
  - Selector de horizonte temporal de anticipación ($T+30$ y $T+60$ minutos).
  - Semáforo de riesgo espaciotemporal por nodo.
  - Matriz de Despacho Preventivo sugerida (cantidad de inspectores, conos y puntos de desvío sugeridos).
  - Panel de justificación causal explicable (por qué se dispara la alerta).


---

## DÍA 4 — JUEVES 5
Desarrollo, validación y factibilidad

### 1. Estado actual del prototipo
Prototipo funcional operativo y ejecutable localmente (MVP interactivo en Streamlit + Python + DuckDB Spatial). Cuenta con ingesta de capas territoriales de IDE Posadas y red vial OSMnx, motor de inferencia de 4 dimensiones calibrado y visualización geoespacial interactiva de los 5 nodos críticos de Posadas.

### 2. ¿Qué funciona actualmente?
- Selector interactivo de horizonte temporal de anticipación ($T+30$ y $T+60$ minutos).
- Inyección dinámica de variables meteorológicas (simulación de tasa de precipitaciones en mm/h).
- Motor de scoring de riesgo espaciotemporal multivariado (0 a 100) con categorización visual (Bajo, Medio, Alto, Crítico).
- Generación automática de la Matriz de Despacho Preventivo (asignación sugerida de inspectores, conos y balizas).
- Panel de Explicabilidad Causal (XAI) que traduce en lenguaje natural para el operador qué factores urbanos combinados activaron la alerta.

### 3. ¿Qué falta desarrollar o ajustar?
- Conexión al feed de API meteorológica continua para automatizar el deslizador de lluvia.
- Calibración de los pesos de siniestralidad con mayor volumen de noticias históricas geocodificadas.
- Integración de exportación de órdenes de despacho a PDF/impresión para el cuerpo de inspectores de guardia.

### 4. Herramientas y tecnologías utilizadas
- **Lenguaje:** Python 3.12.
- **Almacenamiento & Analítica:** DuckDB con extensión Spatial (arquitectura ELT en memoria de alto rendimiento y costo cero en licencias).
- **Topología Territorial:** OpenStreetMap (OSMnx / NetworkX) y capas vectoriales abiertas de IDE Posadas (Shapefiles / GeoJSON).
- **Frontend Interactivo:** Streamlit con visualización cartográfica Leaflet / PyDeck.
- **Procesamiento de Señales Débiles:** Pipeline NLP con extracción estructurada de entidades (intersecciones y siniestros viales de portales locales).

### 5. Factibilidad técnica
**¿Es técnicamente posible implementar la solución? ¿Por qué?**  
Sí, 100% factible. Porque no requiere la compra ni instalación de hardware físico nuevo (cámaras o espiras en calle), utiliza estándares abiertos de datos geoespaciales (OGC `ST_*`) compatibles de forma nativa con las bases relacionales que ya opera el municipio (PostgreSQL/PostGIS), y su consumo computacional es liviano, pudiendo ejecutarse en un servidor local o en la nube municipal sin costos de licenciamiento privativo.

### 6. Factibilidad de datos
**¿Contamos con los datos necesarios?**  
[X] Parcialmente.  
*Observaciones:* Contamos con la red vial completa, la ubicación de escuelas y semáforos de IDE Posadas, los registros meteorológicos de la OPAD y las noticias locales para siniestros. Para la puesta en producción plena, se requerirá acceso a los aforos vehiculares de los controladores semafóricos y al registro municipal de partes diarios de inspectores.

### 7. Riesgos o limitaciones
- **Riesgo 1 (Sesgo de reporte en medios digitales):** No todos los siniestros menores llegan a la prensa digital. *Mitigación:* El modelo no depende exclusivamente de las noticias; la demanda escolar programada, la topología vial y el clima sostienen la predicción de forma determinística.
- **Riesgo 2 (Adopción del operador):** Resistencia al cambio del personal municipal acostumbrado a planillas de papel. *Mitigación:* Interfaz minimalista, explicabilidad causal (el sistema no es una caja negra) y respeto estricto al rol humano: el sistema sugiere, el operador decide.

### 8. Posible implementación
**¿Qué sería necesario para implementar esta propuesta en un contexto real?**  
- Acople del pipeline de ingesta a la base de datos interna de la Secretaría de Movilidad Urbana de Posadas.
- Instalación del servicio en un servidor interno municipal o instancia en nube provincial.
- Capacitación operativa de 2 horas a los operadores de despacho del Centro de Monitoreo / Tránsito.
- Protocolo de retroalimentación donde el operador valide con un clic si la recomendación preventiva fue acertada, refinando los pesos del modelo.

### 9. Impacto esperado
**¿Qué mejora podría generar la solución?**  
- Reducción drástica del tiempo de reacción ante cuellos de botella: paso de una gestión reactiva diferida (30-60 minutos después de ocurrido el colapso) a una gestión preventiva con 30 a 60 minutos de anticipación.
- Optimización en el despliegue del personal de tránsito: asignación de inspectores por criticidad real explicada en lugar de patrullaje errático.
- Reducción de siniestralidad vial secundaria por colisiones por alcance y frenadas bruscas en accesos escolares y cruces troncales.

### 10. Correcciones prioritarias antes de la entrega
- Consolidar la Ficha de Proyecto en el límite estricto de 300 palabras (redactada en 265 palabras).
- Congelar el pitch de 3 minutos cronometrados y ensayar las respuestas a preguntas complejas del jurado.
- Asegurar que la demo en Streamlit pueda ejecutarse 100% offline en la notebook durante el Demo Day ante cualquier falla de conectividad en el edificio de Silicon Misiones.

---

## DÍA 5 — VIERNES 6
Consolidación, ficha de proyecto y preparación del pitch

### 1. Nombre final del proyecto
AITARA (Sistema de Soporte a Decisiones para la Movilidad Urbana).

### 2. Problema
La gestión de tránsito en Posadas opera de forma reactiva debido a datos fragmentados, manuales y diferidos (planillas de 15 minutos y noticias tardías), lo que impide predecir cuellos de botella y desplegar operativos preventivos antes del colapso vial.

### 3. Usuario principal
Operador de Despacho y Planificación de Tránsito / Movilidad Urbana de la Municipalidad de Posadas.

### 4. Solución
Decision Support System (DSS) que integra datos territoriales abiertos (IDE Posadas), red vial (OSMnx), clima en tiempo real (OPAD) y minería de siniestros en noticias locales mediante un pipeline ELT y un motor explicable de 4 dimensiones para emitir recomendaciones de despacho preventivo.

### 5. Uso de Inteligencia Artificial
NLP con esquemas estructurados para minar incidentes viales de diarios locales y motor de inferencia espaciotemporal explicable (XAI) que justifica en lenguaje natural cada recomendación de despacho para el operador humano.

### 6. Datos utilizados o necesarios
Capas vectoriales de IDE Posadas (semáforos, escuelas), red vial de OpenStreetMap, feed meteorológico de la OPAD y archivo de noticias locales.

### 7. Funcionamiento de la solución
Ingesta continua en DuckDB Spatial -> Evaluación del grafo vial contra 4 dimensiones de riesgo (Demanda, Clima, Capacidad, Siniestralidad) -> Cálculo de criticidad por nodo -> Generación de matriz de despacho y reporte explicable en tablero interactivo para el operador.

### 8. Impacto esperado
Anticipación operativa de 30 a 60 minutos, optimización del recurso humano municipal y prevención de nudos de congestión en ingresos escolares y avenidas troncales.

### 9. Factibilidad
100% viable técnica y económicamente; software libre, estándares abiertos SQL OGC `ST_*`, compatible con PostGIS municipal y sin costo de adquisición de sensores.

### 10. Link al prototipo / demo
Prototipo local en Streamlit (ejecutable en vivo en Demo Day en `http://localhost:8501`) y repositorio con preview interactiva.

### 11. Link al repositorio, si corresponde
Repositorio Git local / GitHub de AITARA.

### 12. Link a presentación final
`docs/architecture/pitch_deck.html` (Presentación interactiva con temporizador y atajos de teclado para backups técnicos).

### 13. Integrante/s responsable/s del pitch
Santiago Agustín Nuñez (Defensa técnica y demo en vivo) y Facundo Fraga / Joaquín Sanchez (Soporte y Q&A).

### 14. Mensaje principal del pitch
*"Posadas no necesita gastar millones en sensores para anticipar sus colapsos viales: AITARA transforma los datos que la ciudad ya tiene en decisiones preventivas para sus inspectores antes de que el nudo sea irreversible."*

### 15. Correcciones finales luego del taller de pitch
Incorporar diapositivas de respaldo con atajos rápidos de teclado (`B` para backups, `5` para demo, `1` para portada) para responder preguntas de arquitectura profunda, motor matemático y TCO sin salir del tiempo límite de 3 minutos.
