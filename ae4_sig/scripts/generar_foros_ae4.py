"""Genera las participaciones del Foro AE4 en DOCX (100% Times New Roman) y MD limpio.

Salidas generadas en `ae4_sig/dock/`:
  - `ae4_sig/dock/Actividad_Foro_AE4_Nunez_Santiago.docx`
  - `ae4_sig/dock/Actividad_Foro_AE4_Nunez_Santiago.md`
  - `ae4_sig/dock/Actividad_Foro_AE4_Sanchez_Joaquin.docx`
  - `ae4_sig/dock/Actividad_Foro_AE4_Sanchez_Joaquin.md`

Los archivos Markdown se producen sin backticks ni fórmulas LaTeX (`$...$`) para
habilitar una importación limpia hacia Google Docs en Times New Roman puro.
"""

from __future__ import annotations

import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple
import xml.etree.ElementTree as ET

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import generar_informe_ae4 as gia  # noqa: E402


@dataclass(frozen=True)
class ForoSpec:
    slug: str
    estudiante_portada: str
    estudiante_completo: str
    dni: str
    secciones: Sequence[Tuple[str, Sequence[str]]]


def add_foro_cover(rb: gia.ReportBuilder, spec: ForoSpec) -> None:
    assert gia.LOGO_PATH.exists(), f"Logo UCP no encontrado: {gia.LOGO_PATH}"

    p_logo = rb.doc.add_paragraph()
    p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_logo.paragraph_format.first_line_indent = Cm(0)
    p_logo.paragraph_format.space_before = Pt(0)
    p_logo.paragraph_format.space_after = Pt(18)
    p_logo.paragraph_format.line_spacing = 1.0
    p_logo.add_run().add_picture(str(gia.LOGO_PATH), width=Cm(8.5))

    header_lines = [
        ("UNIVERSIDAD DE LA CUENCA DEL PLATA", True, False),
        ("Facultad de Ingeniería, Tecnología y Arquitectura", True, False),
        ("Ingeniería en Sistemas de Información", True, False),
        ("Sistemas de Información Geográfica", True, False),
        ("Actividad de Evaluación 4 (AE4) — Foro de Debate", True, True),
    ]
    for text, bold, underline in header_lines:
        p = rb.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.5
        r = p.add_run(text)
        gia.set_run_font(r, size_pt=12.0, bold=bold, underline=underline)

    p_sede = rb.doc.add_paragraph()
    p_sede.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sede.paragraph_format.first_line_indent = Cm(0)
    p_sede.paragraph_format.space_before = Pt(4)
    p_sede.paragraph_format.space_after = Pt(0)
    p_sede.paragraph_format.line_spacing = 1.5
    r_sede = p_sede.add_run("Sede Posadas")
    gia.set_run_font(r_sede, size_pt=12.0)

    meta_items = [
        ("Estudiante:", f" {spec.estudiante_portada}"),
        ("DNI:", f" {spec.dni}"),
        ("Profesor:", " Edgar Rolando Ibáñez"),
        ("Alternativa:", " Opción A — PostgreSQL 16.4 + PostGIS 3.4.3 + QGIS 4.2.1"),
        ("Fecha de entrega:", " 23 de noviembre de 2026"),
    ]
    for idx, (lbl, val) in enumerate(meta_items):
        p = rb.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.space_before = Pt(32 if idx == 0 else 0)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.7
        r1 = p.add_run(lbl)
        gia.set_run_font(r1, size_pt=12.0, bold=True, underline=True)
        r2 = p.add_run(val)
        gia.set_run_font(r2, size_pt=12.0)

    rb.md.extend(
        [
            f"# Actividad Foro AE4 — {spec.estudiante_completo}",
            "",
            f"- **Estudiante:** {spec.estudiante_portada}",
            f"- **DNI:** {spec.dni}",
            "- **Cátedra:** Sistemas de Información Geográfica (UCP — Sede Posadas)",
            "- **Profesor:** Edgar Rolando Ibáñez",
            "- **Alternativa implementada:** Opción A — PostgreSQL 16.4 + PostGIS 3.4.3 + QGIS 4.2.1",
            "- **Fecha de entrega:** 23 de noviembre de 2026",
            "",
            "---",
            "",
        ]
    )


def build_foro_doc(spec: ForoSpec) -> Tuple[Path, Path]:
    doc = gia.configure_document()
    rb = gia.ReportBuilder(doc)
    add_foro_cover(rb, spec)

    for idx, (titulo, bloques) in enumerate(spec.secciones):
        if idx == 0:
            rb.h1(titulo)
        else:
            p = rb.doc.add_paragraph(style="Heading 1")
            p.paragraph_format.page_break_before = False
            p.paragraph_format.space_before = Pt(12)
            gia.add_inline_runs(p, titulo, base_size_pt=12.0, base_bold=True)
            rb.md.extend([f"## {titulo}", ""])

        for item in bloques:
            if isinstance(item, list):
                rb.bullets(item)
            else:
                rb.p(item)

    docx_path = gia.DOCK_DIR / f"Actividad_Foro_AE4_{spec.slug}.docx"
    md_path = gia.DOCK_DIR / f"Actividad_Foro_AE4_{spec.slug}.md"

    doc.save(str(docx_path))
    md_path.write_text("\n".join(rb.md), encoding="utf-8")
    verify_foro_outputs(docx_path, md_path)
    return docx_path, md_path


def verify_foro_outputs(docx_path: Path, md_path: Path) -> None:
    assert docx_path.exists() and docx_path.stat().st_size > 5_000
    assert md_path.exists() and md_path.stat().st_size > 2_000

    loaded = Document(str(docx_path))
    chunks: List[str] = [p.text for p in loaded.paragraphs]
    w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    xml_texts: List[str] = []
    content_fonts: set[str] = set()
    with zipfile.ZipFile(docx_path, "r") as zf:
        for name in zf.namelist():
            if name.startswith("word/") and name.endswith(".xml"):
                root = ET.fromstring(zf.read(name))
                xml_texts.extend(t for t in root.itertext() if t)
                if name == "word/document.xml" or name.startswith(("word/header", "word/footer")):
                    for rf in root.iter(f"{w_ns}rFonts"):
                        content_fonts.update(rf.attrib.values())

    md_text = md_path.read_text(encoding="utf-8")
    all_docx_text = "\n".join(chunks) + "\n" + "\n".join(xml_texts)
    full_text = all_docx_text + "\n" + md_text

    assert content_fonts == {"Times New Roman"}, f"Fuentes inesperadas: {sorted(content_fonts)}"
    assert "aitara" not in full_text.lower(), "Término prohibido detectado"
    assert "`" not in md_text and "`" not in all_docx_text, "Backtick residual detectado"
    assert "$" not in md_text and "$" not in all_docx_text, "Delimitador LaTeX $ detectado"
    assert "\ufffd" not in full_text, "Carácter de reemplazo Unicode detectado"


def build_specs() -> List[ForoSpec]:
    santiago = ForoSpec(
        slug="Nunez_Santiago",
        estudiante_portada="Nuñez, Santiago Agustín",
        estudiante_completo="Santiago Agustín Nuñez",
        dni="44.952.958",
        secciones=[
            (
                "1. Elección de la tecnología",
                [
                    "En nuestro proyecto optamos por la arquitectura cliente-servidor con "
                    "**PostgreSQL 16.4 + PostGIS 3.4.3** acoplada a **QGIS 4.2.1**. Su ventaja "
                    "determinante frente a GeoPackage (.gpkg, basado en SQLite sobre un único "
                    "archivo local) es el soporte de **concurrencia multiversión (MVCC)** con "
                    "bloqueos a nivel de fila (RowExclusiveLock), la ejecución de **triggers "
                    "reactivos en PL/pgSQL** y la validación declarativa estricta mediante "
                    "restricciones CHECK (ST_IsValid(geom)) y claves foráneas. Como limitación, "
                    "exige administrar un motor de base de datos (que resolvimos contenedorizándolo "
                    "en Docker sobre el puerto 5433) y gestionar credenciales de red. Recomiendo "
                    "**QGIS + GeoPackage** para relevamientos individuales, cartografía portátil "
                    "de escritorio o entregas rápidas sin infraestructura de servidor; en cambio, "
                    "**PostgreSQL/PostGIS** es indispensable cuando múltiples operadores editan "
                    "simultáneamente, cuando se requiere auditoría transaccional (JSONB) o cuando "
                    "se procesan cruces complejos y grandes volúmenes con planificación de "
                    "consultas (EXPLAIN ANALYZE)."
                ],
            ),
            (
                "2. Calidad de los datos geográficos",
                [
                    "Los errores que más comprometen un análisis espacial son las geometrías "
                    "inválidas (autointersecciones), el uso de sistemas de referencia en grados "
                    "(EPSG:4326) para medir distancias métricas planas y las discontinuidades "
                    "topológicas en redes viales. En nuestro proyecto, al reconstruir las 1.286 "
                    "calles de Posadas a partir de nodos ordenados de OpenStreetMap, detectamos "
                    "que varias arterias con el mismo nombre estaban interrumpidas por plazas o "
                    "tramos no conectados; al unirlas secuencialmente se generaban líneas rectas "
                    "artificiales que cruzaban manzanas enteras, además de micro-segmentos "
                    "degenerados de longitud cero que fallaban el control ST_IsValid. Lo resolvimos "
                    "en el pipeline ETL cortando automáticamente un nuevo sub-tramo "
                    "(MultiLineString) cada vez que la distancia Haversine entre vértices "
                    "consecutivos superaba los 300 m y aplicando una micro-extensión de ~1 m a los "
                    "segmentos puntuales, logrando 0 geometrías inválidas en las 18.442 entidades "
                    "cargadas."
                ],
            ),
            (
                "3. Consultas y análisis espaciales",
                [
                    "Desarrollé la consulta de **Autoría 1 (incorporación de semaforización en "
                    "entorno escolar)** en EPSG:5348 (*POSGAR 2007 / Argentina Faja 6*). El "
                    "procedimiento identifica cuáles de las 7.898 intersecciones viales de "
                    "Posadas se encuentran simultáneamente a ≤ 150 m de alguna de las 367 "
                    "escuelas oficiales y a ≤ 25 m de una avenida de mano única, pero **carecen de "
                    "semáforo dentro de un radio de 30 m** (NOT EXISTS con ST_DWithin), "
                    "resolviendo la asignación de la escuela más próxima mediante JOIN LATERAL y "
                    "el operador KNN (<->). El análisis detectó **104 intersecciones críticas** "
                    "(encabezadas por *Beethoven y Av. Centenario*, *Av. Centenario y Derqui* y "
                    "*Av. Lavalle y Neumann*). Si hubiéramos usado únicamente consultas "
                    "alfanuméricas (WHERE calle = ...), habría sido imposible detectar escuelas "
                    "ubicadas a media cuadra sobre la arteria transversal, evaluar radios de "
                    "cobertura real en metros o descartar semáforos cuyos nombres de calle "
                    "difieren por abreviaturas entre padrones."
                ],
            ),
            (
                "4. Índices espaciales y rendimiento",
                [
                    "Sin índices espaciales, el motor debe evaluar la distancia o intersección "
                    "geométrica exacta vértice por vértice entre el producto cartesiano de las "
                    "tablas (Seq Scan). Al implementar los 34 índices **GiST (R-Tree sobre "
                    "Rectángulos Mínimos Envolventes - MBR)**, PostGIS filtra primero en "
                    "milisegundos las cajas envolventes (&&) y solo ejecuta el cálculo geométrico "
                    "exacto sobre las tuplas candidatas. En nuestras mediciones con EXPLAIN "
                    "(ANALYZE, BUFFERS) (mediana de 5 corridas), el cruce urbano de proximidad "
                    "intersecciones × calles (ST_DWithin 30 m, 18.194 pares) bajó de **4.009,17 "
                    "ms a 337,74 ms (11,87× más rápido)**, y la asignación puntual incidentes × "
                    "delegaciones (ST_Within) pasó de **22,92 ms a 1,78 ms (12,88×)**."
                ],
            ),
            (
                "5. Cartografía y comunicación de resultados",
                [
                    "Un mapa geométricamente exacto puede fracasar comunicacionalmente si satura "
                    "la vista con todas las capas activas o si mezcla datos de distinta naturaleza "
                    "bajo un mismo símbolo. Al diseñar la cartografía de Posadas en QGIS 4.2.1 "
                    "(Figura 6 y Mapa 3), tuvimos que separar visualmente 12 siniestros reales "
                    "relevados de prensa local respecto de 1.417 eventos sintéticos de "
                    "demostración: representamos los reales con **rombos rojos destacados** en el "
                    "nivel superior del orden de dibujo y los sintéticos con círculos graduados "
                    "con transparencia, apagando por defecto el grupo regional (IGN) para despejar "
                    "la lectura urbana. Asimismo, en el mapa de brecha por delegación (Mapa 4), "
                    "emplear una rampa coroplética graduada sobre la tasa normalizada (semáforos "
                    "cada 100 intersecciones) permitió comunicar de un vistazo el contraste entre "
                    "Sede Central (44,31) y delegaciones periféricas como Itaembé Guazú e Itaembé "
                    "Miní Este (0,00)."
                ],
            ),
            (
                "6. Aplicaciones reales y toma de decisiones",
                [
                    "Si este sistema se desplegara en la Secretaría de Movilidad Urbana de la "
                    "Municipalidad de Posadas, incorporaría tres funcionalidades adicionales:",
                    [
                        "**Integración en vivo con la estación meteorológica municipal (OPAD)** y "
                        "partes oficiales de siniestralidad con marca pluviométrica real para "
                        "reemplazar la serie sintética.",
                        "**Aforos vehiculares horarios y sentidos de giro** en la red de calles "
                        "para modelar congestión por franja horaria.",
                        "**Un formulario móvil conectado a PostGIS** para que los inspectores "
                        "registren incidentes o fallas semafóricas en campo disparando los "
                        "triggers de validación y auditoría.",
                    ],
                    "Con la información ya generada, el municipio puede tomar tres decisiones "
                    "inmediatas: priorizar la instalación de semáforos o reductores en los **104 "
                    "cruces escolares sobre avenidas de mano única**, planificar obras de drenaje "
                    "y limpieza de sumideros antes de alertas de lluvia en los **30 corredores más "
                    "sensibles** (encabezados por *Av. San Martín* y *Av. Lavalle*), y reasignar "
                    "presupuesto de equipamiento vial hacia las delegaciones periféricas sin "
                    "cobertura semafórica.",
                ],
            ),
        ],
    )

    joaquin = ForoSpec(
        slug="Sanchez_Joaquin",
        estudiante_portada="Sánchez, Joaquín Sebastián",
        estudiante_completo="Joaquín Sebastián Sánchez",
        dni="45.452.416",
        secciones=[
            (
                "1. Elección de la tecnología",
                [
                    "Al implementar la **Opción A (PostgreSQL 16.4 + PostGIS 3.4.3 + QGIS 4.2.1)** "
                    "comprobamos que su mayor fortaleza frente a un archivo local **GeoPackage** "
                    "radica en la capacidad de desacoplar la arquitectura en esquemas (staging "
                    "para recepción cruda y sig_ae4 para producción validada), utilizar tipos "
                    "geodésicos nativos (geography sobre el elipsoide WGS 84) con **índices "
                    "funcionales GiST**, y conectar múltiples clientes (psql, scripts Python, "
                    "GDAL/ogr2ogr y QGIS) de forma segura sin almacenar credenciales en texto "
                    "plano dentro del archivo .qgz. Su principal costo es la complejidad inicial "
                    "de configuración y red frente a la inmediatez de un .gpkg. Recomendaría "
                    "**QGIS/GeoPackage** para proyectos académicos o profesionales de un solo "
                    "analista donde prime la portabilidad del archivo; y **PostgreSQL/PostGIS** "
                    "para infraestructuras de datos espaciales (IDE) institucionales donde conviven "
                    "escalas regionales y urbanas, automatización ETL y control de integridad "
                    "centralizado."
                ],
            ),
            (
                "2. Calidad de los datos geográficos",
                [
                    "Incluso las capas provenientes de organismos oficiales pueden contener "
                    "defectos topológicos o de codificación de caracteres que alteran predicados "
                    "espaciales sin arrojar errores visibles a simple vista. En nuestro proyecto "
                    "encontramos dos casos concretos al ingestar fuentes oficiales:",
                    [
                        "Al importar el Shapefile de delegaciones municipales de IDE Posadas con "
                        "ogr2ogr (GDAL 3.13.2), fue necesario declarar SHAPE_ENCODING=ISO-8859-1 y "
                        "reparar en staging **dos polígonos con autointersecciones** (ST_IsValid = "
                        "false) aplicando ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Force2D(geom)), "
                        "3)) antes de cruzarlos con los 459 radios censales del Censo 2022 "
                        "(331.753 habitantes).",
                        "En la capa provincial del IGN detectamos que ST_Touches omitía 4 "
                        "fronteras interprovinciales reales (*Entre Ríos–Corrientes*, *Buenos "
                        "Aires–Entre Ríos*, *San Juan–La Rioja* y *Jujuy–Salta*); al auditarlas "
                        "con ST_Dimension(ST_Intersection(a.geom, b.geom)) = 2 demostramos que "
                        "presentaban micro-solapamientos bidimensionales de 0,00 a 5,29 m² que "
                        "violaban la condición DE-9IM de interiores disjuntos de ST_Touches.",
                    ],
                ],
            ),
            (
                "3. Consultas y análisis espaciales",
                [
                    "Entre las consultas desarrolladas destaco dos escalas: en el ámbito regional "
                    "(inciso h), la asignación de cada una de las **140 localidades BAHRA de "
                    "Misiones** a su Ruta Nacional más cercana (RN 12, RN 14 o RN 101) calculando "
                    "la distancia geodésica exacta sobre el elipsoide (ST_Distance(geom::geography) "
                    "+ CROSS JOIN LATERAL), determinando que la RN 12 articula a 67 localidades "
                    "(4,42 km promedio) y la RN 14 a 66 (14,73 km promedio, con máximo en *Alicia "
                    "Baja* a 50,26 km); y en el ámbito urbano (**Autoría 3**), el cruce "
                    "multipredicado (ST_Within y ST_Area) que integra población censal 2022, "
                    "superficie en km², intersecciones, escuelas, paradas y semáforos dentro de "
                    "cada una de las **12 delegaciones de Posadas**. Con una consulta puramente "
                    "alfanumérica sería imposible agregar radios censales que no poseen columna de "
                    "delegación municipal, medir la densidad real por kilómetro cuadrado o "
                    "calcular la tasa de cobertura semafórica cada 100 intersecciones físicas "
                    "contenidas en el polígono."
                ],
            ),
            (
                "4. Índices espaciales y rendimiento",
                [
                    "En bases espaciales de escala regional y urbana, los índices B-tree "
                    "tradicionales no sirven para búsquedas bidimensionales porque un orden escalar "
                    "1D no preserva la vecindad espacial 2D. Al implementar 34 índices **GiST "
                    "(R-Tree)**, comprobamos tres efectos críticos en nuestro benchmark (EXPLAIN "
                    "(ANALYZE, BUFFERS)):",
                    [
                        "En la búsqueda de vecinos cercanos KNN (<->) entre 3.528 localidades y "
                        "1.333 cursos de agua, el tiempo cayó de **5.459,99 ms (1.238.382 bloques "
                        "leídos) a 114,24 ms (35.833 bloques), una mejora de 47,80×**.",
                        "Descubrimos además la trampa del casteo geom::geography: cuando una tabla "
                        "solo tiene índice GiST sobre geom (geometry), consultar "
                        "ST_DWithin(geom::geography, ...) cambia la familia de operadores y fuerza "
                        "un Seq Scan de **240.178,94 ms (~4 minutos)**; al crear el índice GiST "
                        "funcional USING GIST ((geom::geography)), el tiempo descendió a "
                        "**4.078,85 ms (58,88× de aceleración)**.",
                        "En la curva sintética de 10.000, 100.000 y 1.000.000 de puntos sobre "
                        "*Av. Quaranta*, GiST mantuvo la consulta en **65,36 ms (8.600 buffers)** "
                        "frente a **1.134,63 ms (3.008.336 buffers)** sin índice (17,36×).",
                    ],
                ],
            ),
            (
                "5. Cartografía y comunicación de resultados",
                [
                    "La precisión topológica y métrica en PostGIS es condición necesaria pero no "
                    "suficiente para que un mapa sea útil a un decisor. Al renderizar las cuatro "
                    "láminas temáticas del proyecto en **QGIS 4.2.1** (1800 × 1150 px), "
                    "comprobamos que la elección de la escala, el sistema de referencia visual "
                    "(EPSG:5348 para Posadas y EPSG:4326 para el marco regional del NEA) y la "
                    "jerarquía de etiquetas cambian por completo la legibilidad. Por ejemplo, en "
                    "el mapa regional (Figura 2), mostrar simultáneamente las 3.528 localidades "
                    "BAHRA y los 1.333 tramos hidrográficos con el mismo grosor producía un "
                    "empaste ilegible; fue necesario destacar con trazo diferenciado los tres ríos "
                    "principales (*Paraná*, *Uruguay* e *Iguazú*), jerarquizar rutas nacionales "
                    "frente a provinciales y filtrar etiquetas a capitales e hitos extremos "
                    "(*Bernardo de Irigoyen* a 97,27 km del Paraná). Del mismo modo, en los mapas "
                    "urbanos, combinar etiquetas selectivas solo sobre los nodos críticos evita "
                    "ocultar la red vial de base."
                ],
            ),
            (
                "6. Aplicaciones reales y toma de decisiones",
                [
                    "Para llevar este desarrollo a producción en un organismo provincial o "
                    "municipal (como la Dirección de Tránsito de Posadas o Vialidad Provincial), "
                    "sumaría tres mejoras:",
                    [
                        "**Publicación de las vistas analíticas de PostGIS mediante GeoServer "
                        "(servicios OGC WMS/WFS)** para que otras áreas municipales consuman en "
                        "vivo las capas de Autoría 1, 2 y 3 desde cualquier navegador o visor web.",
                        "**Ruteo topológico con pgRouting** sobre la tabla calles e intersecciones "
                        "para calcular tiempos de respuesta de ambulancias o inspectores hacia los "
                        "nodos críticos.",
                        "**Actualización incremental automatizada (cron ETL)** contra los servicios "
                        "WFS de IDE Posadas e IGN.",
                    ],
                    "A partir de la información generada, las autoridades pueden decidir con "
                    "respaldo empírico dónde instalar nuevos complejos semafóricos en barrios en "
                    "expansión como **Itaembé Guazú** (663 intersecciones, 10 escuelas y 0 "
                    "semáforos), en qué tramos combinar obras de **asfalto sobre empedrado** con "
                    "desagües pluviales (donde la sensibilidad bajo lluvia difiere entre 1,66× con "
                    "obra y 1,82× sin obra), y cómo planificar la conectividad de localidades "
                    "misioneras alejadas de los corredores troncales RN 12 y RN 14.",
                ],
            ),
        ],
    )
    return [santiago, joaquin]


def main() -> None:
    gia.DOCK_DIR.mkdir(parents=True, exist_ok=True)
    for spec in build_specs():
        docx_path, md_path = build_foro_doc(spec)
        print(f"[OK] DOCX generado: {docx_path} ({docx_path.stat().st_size:,} bytes)")
        print(f"[OK] MD generado  : {md_path} ({md_path.stat().st_size:,} bytes)")
    print("[OK] Foros AE4 generados en 100% Times New Roman y símbolos verificados.")


if __name__ == "__main__":
    main()
