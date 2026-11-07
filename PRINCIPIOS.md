# Principios del proyecto AITARA

Este archivo es la fuente única de reglas del proyecto. Lo leen Claude Code (orquestador y críticos) y Codex (implementador). Si una instrucción de otro archivo contradice a este, manda este.

## Qué es AITARA

Sistema de soporte a decisiones (DSS) para la movilidad urbana de Posadas. Integra fuentes dispersas en una memoria única de la ciudad y la analiza sobre dos ejes:

- **Seguridad vial:** dónde y cuándo aumenta el riesgo de siniestros.
- **Fluidez:** dónde se forma congestión y cuándo es anómala.

El sistema **recomienda y explica; la decisión es siempre humana**. No controla semáforos, no interviene infraestructura, no asigna responsabilidades en siniestros ni realiza peritajes.

La ficha de proyecto entregada al hackathon es el contrato con el jurado. El código tiene que hacer lo que la ficha dice, ni más ni menos.

## Regla 1: cada número tiene origen

Todo valor que aparece en pantalla, en un informe o en una respuesta del Analista sale de una de estas dos fuentes:

1. Un dato de la base (real o simulado, identificado como tal).
2. Un cálculo del motor analítico sobre esos datos.

Prohibido:

- Cifras escritas a mano en el código o en plantillas ("34 siniestros anuales", "78 % motos", "87 % de criticidad").
- Afirmaciones causales sin fuente ("cota topográfica baja", "satura sumideros") si no hay un dato que las respalde.
- Textos de recomendación fijos por intersección (un `if nodo_id == ...` con instrucciones escritas).

## Regla 2: prioridad con justificación, no despacho

El sistema entrega **prioridades**: qué nodo o corredor, con qué nivel, por qué (aporte de cada factor) y con qué evidencia (incidentes que lo respaldan, con su enlace).

Prohibido:

- Órdenes de despacho, "móviles asignados", "acción para móviles".
- Cantidades de recursos (inspectores, conos, balizas, patrullas).
- Tono imperativo u "autoritativo" hacia el operador.

Las cantidades y la asignación las decide el área municipal.

## Regla 3: datos reales, simulados y a gestionar

Cada registro lleva un campo de origen:

| Origen | Ejemplos |
|---|---|
| `real` | Red vial (OpenStreetMap), capas de IDE Posadas, clima, noticias locales |
| `simulado` | Partes policiales y del 911, aforos, reclamos, feed con formato Waze, agenda de eventos y cortes |
| `a_gestionar` | Fuentes que todavía no existen en el sistema |

Los datos simulados:

- Se generan con el generador sintético, con reglas declaradas y respetando la geografía real de Posadas.
- Se muestran en la interfaz con una marca visible de **SIMULADO**.
- Sirven para demostrar el sistema y validar el método, no para afirmar resultados sobre la ciudad.

## Regla 4: la IA tiene lugares fijos

| Componente | Naturaleza | Regla |
|---|---|---|
| Lector | LLM con salida estructurada, paso fijo | Esquema validado, evidencia textual por campo, sin datos personales, `null` si no está en el texto |
| Modelos analíticos | Estadística, deterministas | Mismos datos, mismo resultado. Descomponen cada resultado en el aporte de cada factor |
| Investigador | Agente con herramientas | Resuelve ubicaciones dudosas o deriva a revisión humana |
| Analista | Agente de solo lectura | Redacta a partir de resultados ya calculados. No calcula ni inventa |

El Analista siempre tiene respaldo sin conexión: una **plantilla que usa los mismos datos calculados**, nunca respuestas armadas por palabra clave.

## Regla 5: la demo no puede fallar

- Existe un **modo demo** que funciona sin internet y sin clave de Gemini, usando resultados guardados del Lector y el respaldo del Analista.
- Ninguna clave va al repositorio. Las claves van en `.env`, que no se versiona. `.env.example` documenta las variables.

## Documentos de referencia

Leelos en este orden cuando necesites contexto. Si alguno contradice este archivo, manda este.

| Documento | Qué aporta | Vigente |
|---|---|---|
| `docs/PROPUESTA_TECNICA.md` | Definiciones, arquitectura, componentes de IA, estrategia de datos, escenarios, avisos y métricas | Sí |
| `docs/FICHA_DE_PROYECTO.pdf` | Lo que se le prometió al jurado | Sí |
| `docs/TRANSCRIPCION_AUDIO_RUIZ.md` | Entrevista con la Dirección de Movilidad Urbana: necesidades reales del usuario | Sí |
| `docs/CHALLENGE.md` | Pliego del desafío y sus restricciones | Sí |
| `docs/archivo/` | Versiones anteriores de la propuesta (despacho táctico, anticipación a 30–60 minutos) | **No.** Solo como historial |

## Estructura de módulos

| Módulo | Responsabilidad |
|---|---|
| `src/ingesta/` | Recolector de noticias y generador sintético |
| `src/lector/` | Extracción con LLM y caché de resultados |
| `src/engine/investigador.py` | Resolución de ubicaciones dudosas |
| `src/warehouse/` | Base de datos; puntajes por nodo calculados desde los incidentes |
| `src/engine/risk_model.py` | Riesgo estructural, variación por escenario y aporte por factor |
| `src/engine/analista.py` | Redacción de informes, respuestas y avisos |
| `src/contracts.py` | Contratos de datos (Pydantic) compartidos por todos los módulos |
| `api.py` | API FastAPI; también sirve el frontend compilado |
| `frontend/` | Interfaz React + Vite + Leaflet |

## Vocabulario

| Usar | No usar |
|---|---|
| Prioridad, zona crítica, nivel de riesgo | Orden de despacho, móvil, patrulla asignada |
| Escenario, variación por escenario | Predicción a T+30, anticipación garantizada |
| Riesgo estructural | Score calibrado (si no se calibró con datos) |
| Aviso | Alerta táctica, instrucción |
