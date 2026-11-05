import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

doc = docx.Document()

# Page setup
for section in doc.sections:
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

# Style setup
normal_style = doc.styles['Normal']
normal_style.font.name = 'Montserrat'
normal_style.font.size = Pt(11)
normal_style.font.color.rgb = RGBColor(33, 33, 33)

def add_title(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(15)
    run.font.color.rgb = RGBColor(24, 76, 120)

def add_h1(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(24, 76, 120)

def add_p(text, bold_prefix=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.bold = True
    p.add_run(text)

add_title('HACKATHON IA EN ACCIÓN — SILICON MISIONES 2026\nFICHA DE PROYECTO')

add_h1('1. IDENTIFICACIÓN DEL PROYECTO')
add_p('AITARA (Sistema de Soporte a Decisiones para la Movilidad Urbana Preventiva)', 'Nombre del proyecto: ')
add_p('Smart City', 'Track / Temática: ')
add_p('Desafío 1 — IA para Entender y Anticipar la Movilidad Urbana', 'Desafío Oficial: ')

# Team Table
table = doc.add_table(rows=1, cols=3)
table.alignment = WD_TABLE_ALIGNMENT.CENTER
table.autofit = False

hdr_cells = table.rows[0].cells
hdr_cells[0].text = 'Nombre y apellido'
hdr_cells[1].text = 'Rol / función'
hdr_cells[2].text = 'Formación / experiencia'
for cell in hdr_cells:
    for p in cell.paragraphs:
        for r in p.runs:
            r.bold = True
            r.font.size = Pt(10)

members = [
    ('Santiago Agustín Nuñez', 'Lead Architect & ML Engineer', 'Arquitectura de software, pipelines de datos y sistemas distribuidos.'),
    ('Joaquin Sanchez', 'Backend & Data Engineer', 'Desarrollo de APIs, bases de datos geoespaciales e ingesta de datos.'),
    ('Facundo Fraga', 'Data Analyst & GIS Specialist', 'Análisis espacial, procesamiento de capas IDE y modelado territorial.'),
    ('Ana Florencia Zayas', 'Product Owner & Referente', 'Gestión de proyectos, validación de usuario y comunicación institucional.')
]

for m in members:
    row_cells = table.add_row().cells
    row_cells[0].text = m[0]
    row_cells[1].text = m[1]
    row_cells[2].text = m[2]
    for cell in row_cells:
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.size = Pt(10)

add_p('Zayas Ana Florencia | Mail: zayasflorenciaana@gmail.com | Tel: +54 9 3764 662524', 'Responsable y contacto: ')

add_h1('2. RESUMEN DEL PROYECTO (Máximo 300 palabras)')
add_p('La gestión de la movilidad urbana en Posadas opera de forma reactiva debido a datos dispersos, relevamientos manuales en planillas de 15 minutos y lectura diferida de incidentes en noticias. Esta fragmentación impide a las autoridades anticipar anomalías y desplegar operativos preventivos antes de que los corredores colapsen.\n\nAITARA es un Sistema de Soporte a la Toma de Decisiones (Decision Support System - DSS) diseñado específicamente para los operadores de despacho y planificación de la Dirección de Tránsito y Movilidad Urbana de la Municipalidad de Posadas. Su propósito es emitir recomendaciones operativas con 30 a 60 minutos de anticipación para coordinar inspectores, balizas y desvíos preventivos.\n\nLa Inteligencia Artificial interviene de forma dual y explicable: primero, mediante procesamiento de lenguaje natural (NLP) con esquemas estructurados para minar y geocodificar incidentes viales reportados en portales periodísticos locales; segundo, a través de un motor de inferencia espaciotemporal (XAI) que cruza cuatro dimensiones complementarias (demanda escolar y comercial programada, meteorología en calzada de la OPAD, capacidad topográfica de la arteria y riesgo siniestral histórico).\n\nAITARA opera bajo una arquitectura ELT abierta, almacenando eventos crudos en un Data Lake y estructurándolos en un Data Warehouse local compatible con PostGIS, garantizando una integración no disruptiva con la infraestructura municipal preexistente. Cumple estrictamente las restricciones del pliego oficial: no interviene controladores físicos ni secuencias semafóricas, y no realiza peritajes legales. El impacto directo radica en reducir el tiempo de respuesta municipal de horas a minutos, mitigando siniestros en nodos escolares críticos y garantizando fluidez sustentable para la ciudadanía.')

add_h1('3. PROBLEMÁTICA Y USUARIOS')
add_p('Ruptura en la cadena de transformación del dato en decisión operativa en el municipio de Posadas. La ciudad genera y registra hechos en el territorio, pero carece de un pipeline técnico unificado que transforme datos crónicos y dispersos en conocimiento accionable. Actualmente, las decisiones de tránsito se toman de forma subjetiva o de manera reactiva: los inspectores acuden a un nudo vial cuando el embotellamiento ya se extendió cientos de metros o cuando el 911 reporta un siniestro que ocurrió media hora antes.\n\nLas consecuencias directas son: colapso recurrente en horarios pico en nodos con establecimientos educativos (ej. Av. Corrientes y Tucumán con el Colegio San Basilio Magno), alta siniestralidad diferida de usuarios vulnerables (motociclistas y peatones) en avenidas de acceso rápido (Av. Quaranta, Alicia M. de Justo), e ineficiencia en la asignación del capital humano municipal (inspectores mal distribuidos en horarios de baja fricción mientras los puntos calientes quedan desatendidos).', 'Problemática: ')
add_p('Operador de Despacho y Planificación Operativa de la Dirección de Tránsito / Centro de Monitoreo (usuario principal), cuerpo de inspectores y móviles de calle (ejecutores), y conductores, usuarios del transporte público y comunidades escolares (beneficiarios finales).', 'Usuarios y actores involucrados: ')

add_h1('4. SOLUCIÓN PROPUESTA')
add_p('Plataforma analítica y operativa de soporte a decisiones compuesta por un pipeline ELT que centraliza datos en Data Lake (Bronze) y Data Warehouse (Silver/Gold en DuckDB Spatial), un motor de inferencia explicable (XAI) que evalúa el riesgo espaciotemporal sin requerir sensores continuos por carril, y una consola web interactiva en Streamlit con mapa de calor de nodos de Posadas y Matriz de Despacho Preventivo.', 'Producto / Servicio: ')
add_p('A diferencia de simuladores físicos microscópicos (SUMO/Aimsun), AITARA no exige matrices Origen-Destino ni sensores IoT por carril. Frente a tableros descriptivos (PowerBI), no muestra el pasado sino que proyecta riesgo a 30-60 minutos. Frente a cajas negras de Machine Learning, es 100% explicable para el operador.', 'Diferencial: ')
add_p('Ingesta y geocodificación de fuentes abiertas (IDE Posadas, OSMnx, noticias, OPAD), base DuckDB/SQLite, motor de cálculo para 5 nodos críticos con foco en Av. Corrientes y Tucumán, y Matriz de Despacho con cálculo automático de inspectores, conos y desvíos.', 'MVP: ')

add_h1('5. INTELIGENCIA ARTIFICIAL')
add_p('1) NLP con Structured Outputs para extracción y geocodificación automática de siniestros desde noticias de medios locales posadeños (Canal 12, El Territorio, Misiones Online). 2) Inferencia espaciotemporal no lineal basada en 4 dimensiones de movilidad (demanda escolar programada, meteorología OPAD, capacidad física vial y riesgo histórico). La IA es central en la extracción y síntesis de inteligencia territorial previa a la decisión humana.', 'Rol y Enfoque de IA: ')

add_h1('6. DATOS Y FUNCIONAMIENTO')
add_p('Capas vectoriales de IDE Posadas (semáforos, escuelas, colectivos), topología OSMnx, feeds climáticos de la OPAD y crónicas periodísticas públicas. Sin datos personales sensibles ni patentes. Flujo: Entrada de datos multicanal -> Data Lake Bronze -> Data Warehouse Silver (normalización) -> Gold (features) -> Inferencia XAI -> Consola DSS -> Despacho Preventivo.', 'Datos y Flujo: ')

add_h1('7. MERCADO, COMPETENCIA Y MODELO DE NEGOCIO')
add_p('GovTech y Smart Cities para municipios intermedios que no disponen de presupuestos millonarios en IoT. Despliegue SaaS o instalación On-Premise en servidores municipales sin costos de licenciamiento privativo (Open Source stack).', 'Mercado y Modelo: ')

add_h1('8. FACTIBILIDAD E IMPLEMENTACIÓN')
add_p('Python 3.12, DuckDB Spatial / SQLite, Streamlit y Folium. Corre en servidores convencionales con 4GB de RAM sin GPU dedicada. Fase 1 completada en el Hackathon; Fase 2 (30 días) para enlace a bases de datos de Posadas; Fase 3 (60 días) para pilotaje en calle.', 'Tecnología y Plazos: ')

add_h1('9. IMPACTO Y ESCALABILIDAD')
add_p('Reducción sustancial del riesgo de atropellos y colisiones en escuelas, descongestión preventiva de arterias troncales y menor emisión de CO2 por detenciones innecesarias. Arquitectura 100% escalable a municipios como Oberá, Eldorado o Puerto Rico.', 'Impacto y Escalabilidad: ')

add_h1('10. SÍNTESIS FINAL')
add_p('Problema: Gestión de tránsito reactiva por datos desconectados. Solución: AITARA DSS preventivo. IA: NLP de noticias e inferencia explicable 4D. Próximo paso: Pilotaje en corredor San Basilio Magno.', 'Síntesis: ')

out_path = r'C:\Users\santi\OneDrive\Desktop\Proyectos\AITARA-Hackathon-Silicon-Misiones-2026\docs\Organizacion\FICHA DE PROYECTO - AITARA - COMPLETADA.docx'
doc.save(out_path)
print('Document successfully generated at:', out_path)
