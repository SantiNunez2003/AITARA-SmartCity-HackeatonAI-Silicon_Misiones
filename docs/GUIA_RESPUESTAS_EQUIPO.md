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
