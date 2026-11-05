# AITARA — Guion y Estructura de Pitch (Demo Day)
**Duración Objetivo:** 3 Minutos exactos (180 segundos)  
**Formato:** Presentación proyectada + Demostración del prototipo en vivo  
**Audiencia:** Jurado de Silicon Misiones, autoridades municipales de Posadas y mentores.

---

### Mensaje Central (Lo que el jurado debe recordar)
> *"Posadas no necesita gastar millones en sensores de tránsito para anticipar sus colapsos viales: AITARA transforma los datos que la ciudad ya tiene en decisiones preventivas para sus inspectores antes de que el nudo sea irreversible."*

---

## Estructura Slide por Slide (30 Segundos por Bloque)

### Bloque 1: El Gancho y la Realidad Operativa (0:00 - 0:30)
- **Visual en Pantalla:** Foto de un inspector de tránsito en Posadas anotando en una planilla de papel con una fila de autos atascados de fondo.
- **Qué decir (Locución):**
  > *"En Posadas, la gestión del tránsito sigue siendo reactiva. Hoy, un operador municipal se entera de un siniestro cuando el 911 suena media hora tarde, o planifica operativos con conteos manuales de 15 minutos en planillas de papel. Mientras tanto, en esquinas como Corrientes y Tucumán, el ingreso escolar colapsa la arteria y los inspectores llegan cuando el nudo ya es imposible de desatar. El problema no es que falte voluntad: es que el municipio opera a ciegas."*

---

### Bloque 2: La Falla en la Cadena del Dato (0:30 - 1:00)
- **Visual en Pantalla:** Diagrama simple mostrando 4 silos desconectados: Portales de Noticias, IDE Posadas (capas GIS), Estaciones OPAD (lluvia) y Escuelas.
- **Qué decir (Locución):**
  > *"¿Por qué pasa esto? Porque la ciudad genera datos valiosos todos los días, pero están atrapados en silos. El Geoportal de IDE Posadas tiene las escuelas y semáforos; la OPAD registra las lluvias en tiempo real; y los portales periodísticos relatan los choques a diario. Pero nadie conecta esos puntos. Existe una ruptura técnica entre el hecho que ocurre en la calle y la decisión que toma el despachador de tránsito."*

---

### Bloque 3: Presentación de AITARA (1:00 - 1:30)
- **Visual en Pantalla:** Logo de AITARA y el concepto central: **ELT + Decision Support System (DSS)**. Cita del pliego: *100% soporte al operador humano, cero intervención en semáforos*.
- **Qué decir (Locución):**
  > *"Para resolver esto creamos AITARA, un Sistema de Soporte a Decisiones para la Movilidad Urbana. AITARA no busca reemplazar al personal municipal ni tocar los controladores semafóricos. Su propósito es uno solo: darle al despachador de tránsito una ventana de 30 a 60 minutos de anticipación para enviar inspectores, balizas y ordenar desvíos antes de que el corredor colapse."*

---

### Bloque 4: La Inteligencia Artificial Real (Sin Humo) (1:30 - 2:00)
- **Visual en Pantalla:** Diagrama de las 4 Dimensiones de Inferencia (Demanda Escolar, Lluvia en Calzada, Capacidad Geométrica y Riesgo Siniestral).
- **Qué decir (Locución):**
  > *"No usamos IA como un chatbot decorativo. La usamos en dos puntos clave:  
  > Primero, Procesamiento de Lenguaje Natural para extraer y geocodificar incidentes viales de diarios locales con validación estructurada.  
  > Segundo, un Motor de Inferencia Explicable que no es una caja negra: evalúa 4 dimensiones urbanas: demanda escolar programada, meteorología de calzada, capacidad de carriles y riesgo histórico. El operador ve la alerta y entiende exactamente por qué se disparó."*

---

### Bloque 5: Demostración en Vivo del Prototipo (2:00 - 2:30)
- **Visual en Pantalla:** Cambio a la pantalla en vivo de `http://localhost:8501`. Mostrar el mapa interactivo, mover el deslizador a **06:45 AM**, lluvia **15 mm/h** y horizonte **$T+30\text{ min}$**.
- **Qué decir (Locución):**
  > *"Esto no es una maqueta: es nuestro prototipo funcional corriendo en vivo.  
  > Imaginemos una mañana de martes a las 06:45 con lluvia. El sistema proyecta el escenario a las 07:15. Inmediatamente el nodo del Colegio San Basilio Magno se enciende en alerta CRÍTICA.  
  > La IA le explica al operador: 'Confluencia de ingreso escolar masivo más calzada resbaladiza y calzada angosta'. Y en la Matriz de Despacho emite la orden concreta: 'Despachar 2 inspectores y 6 conos ahora para encauzar la dársena'."*

---

### Bloque 6: Factibilidad, Impacto y Cierre (2:30 - 3:00)
- **Visual en Pantalla:** Arquitectura liviana (DuckDB + Python), compatibilidad nativa con PostGIS municipal, y el equipo AITARA.
- **Qué decir (Locución):**
  > *"AITARA es 100% factible hoy: está construido con estándares abiertos, es compatible de forma nativa con las bases de datos de la municipalidad y no requiere comprar equipamiento privativo.  
  > Pasamos de una gestión reactiva que llega tarde, a una gestión preventiva basada en datos que cuida a los chicos en las escuelas y ahorra horas de embotellamiento a los posadeños.  
  > Muchas gracias. Quedamos a disposición del jurado."*

---

## Preguntas Probables del Jurado y Respuestas Blindadas (Q&A)

1. **¿Por qué no usar sensores en calle o visión por computadora en cámaras?**  
   - *Respuesta:* *"Equipar y mantener cientos de intersecciones con cámaras o espiras inductivas cuesta miles de dólares y meses de obra civil. AITARA resuelve el 80% del valor predictivo hoy mismo utilizando las fuentes que la ciudad ya tiene abiertas y disponibles."*

2. **¿Qué pasa si los medios locales no reportan un choque?**  
   - *Respuesta:* *"La dimensión de siniestralidad es solo una de las cuatro patas. Aunque no hubiera noticias en una semana, las dimensiones de demanda escolar programada, topología de carriles y meteorología de la OPAD siguen operando de forma determinística y continua."*

3. **¿Cómo se integra con los sistemas de la Municipalidad?**  
   - *Respuesta:* *"El Data Warehouse utiliza SQL estándar OGC (`ST_*`), por lo que se anexa directamente a un PostgreSQL/PostGIS municipal sin requerir migraciones ni alterar sus flujos actuales."*
