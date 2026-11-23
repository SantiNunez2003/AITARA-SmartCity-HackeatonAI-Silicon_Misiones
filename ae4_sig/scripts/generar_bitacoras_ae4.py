"""Genera las bitácoras individuales AE4 SIG en formatos DOCX (APA 7 / UCP) y Markdown.

Salidas producidas exclusivamente dentro de `ae4_sig/dock/`:
  - `ae4_sig/dock/Bitacora_AE4_Nunez_Santiago.docx`
  - `ae4_sig/dock/Bitacora_AE4_Nunez_Santiago.md`
  - `ae4_sig/dock/Bitacora_AE4_Sanchez_Joaquin.docx`
  - `ae4_sig/dock/Bitacora_AE4_Sanchez_Joaquin.md`

Reutiliza el formateador institucional APA 7 / UCP de `generar_informe_ae4.py` y
verifica programáticamente la ausencia de términos ajenos al contexto académico
y de backticks literales en los documentos Word generados.
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
class BitacoraEntry:
    """Registro cronológico de actividad según Consignas_Bitacora_AE4.docx."""

    fecha: str
    fase: str
    actividad: str
    herramientas: str
    dificultades_soluciones: str
    evidencias: str
    decisiones_reflexion: str


@dataclass(frozen=True)
class StudentBitacoraSpec:
    """Especificación completa de la bitácora individual de un integrante."""

    slug: str
    nombre_completo: str
    nombre_portada: str
    dni: str
    rol_principal: str
    fecha_entrega: str
    resumen_rol: str
    entries: Sequence[BitacoraEntry]
    moodle_saber: str
    moodle_saber_hacer: str
    moodle_saber_ser: str
    moodle_decision_tecnica: str
    referencias: Sequence[str]


def add_bitacora_cover(rb: gia.ReportBuilder, spec: StudentBitacoraSpec) -> None:
    """Genera la portada institucional UCP de la bitácora individual."""
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
        ("Actividad de Evaluación 4 (AE4) — Bitácora Individual", True, True),
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
        ("Estudiante:", f" {spec.nombre_portada}"),
        ("DNI:", f" {spec.dni}"),
        ("Rol en el proyecto:", f" {spec.rol_principal}"),
        ("Profesor:", " Edgar Rolando Ibáñez"),
        ("Fecha de entrega:", f" {spec.fecha_entrega}"),
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

    p_year = rb.doc.add_paragraph()
    p_year.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_year.paragraph_format.first_line_indent = Cm(0)
    p_year.paragraph_format.space_before = Pt(36)
    p_year.paragraph_format.space_after = Pt(0)
    p_year.paragraph_format.line_spacing = 1.5
    r_y1 = p_year.add_run("AÑO:")
    gia.set_run_font(r_y1, size_pt=12.0, bold=True, underline=True)
    r_y2 = p_year.add_run(" 2026")
    gia.set_run_font(r_y2, size_pt=12.0)

    rb.md.extend(
        [
            "# UNIVERSIDAD DE LA CUENCA DEL PLATA",
            "**Facultad de Ingeniería, Tecnología y Arquitectura**  ",
            "**Ingeniería en Sistemas de Información**  ",
            "**Sistemas de Información Geográfica**  ",
            "**Actividad de Evaluación 4 (AE4) — Bitácora Individual**  ",
            "Sede Posadas",
            "",
            f"- **Estudiante:** {spec.nombre_portada}",
            f"- **DNI:** {spec.dni}",
            f"- **Rol en el proyecto:** {spec.rol_principal}",
            "- **Profesor:** Edgar Rolando Ibáñez",
            f"- **Fecha de entrega:** {spec.fecha_entrega}",
            "- **AÑO:** 2026",
            "",
            "---",
            "",
        ]
    )


def add_h1(rb: gia.ReportBuilder, title: str, *, page_break: bool = True) -> None:
    """Agrega Heading 1 respetando saltos de página configurables."""
    if page_break:
        rb.h1(title)
        return
    p = rb.doc.add_paragraph(style="Heading 1")
    p.paragraph_format.page_break_before = False
    p.paragraph_format.space_before = Pt(12)
    gia.add_inline_runs(p, title, base_size_pt=12.0, base_bold=True)
    rb.md.extend([f"## {title}", ""])


def build_bitacora_document(spec: StudentBitacoraSpec) -> Tuple[Path, Path]:
    """Construye y verifica el DOCX y Markdown de la bitácora individual."""
    doc = gia.configure_document()
    rb = gia.ReportBuilder(doc)
    add_bitacora_cover(rb, spec)

    add_h1(rb, "1. Contexto del proyecto y rol individual", page_break=True)
    rb.p(
        "Bitácora documental de la participación individual en el Proyecto Integrador Final "
        "de la Actividad de Evaluación 4 (AE4), desarrollado en pareja bajo la **Opción A "
        "(PostgreSQL 16.4 + PostGIS 3.4.3 integrado con QGIS 4.2.1 y GDAL 3.13.2)** sobre la "
        "problemática de movilidad urbana, infraestructura vial y siniestralidad de la ciudad de "
        "Posadas en su marco territorial regional."
    )
    rb.p(spec.resumen_rol)

    summary_rows = [
        [e.fecha, e.fase, e.actividad, e.evidencias] for e in spec.entries
    ]
    rb.table(
        1,
        f"Síntesis cronológica de aportes individuales — {spec.nombre_completo}",
        ["Fecha", "Fase", "Actividad principal", "Evidencias clave"],
        summary_rows,
        [2.3, 2.0, 6.2, 5.42],
        [
            WD_ALIGN_PARAGRAPH.CENTER,
            WD_ALIGN_PARAGRAPH.CENTER,
            WD_ALIGN_PARAGRAPH.LEFT,
            WD_ALIGN_PARAGRAPH.LEFT,
        ],
        (
            "Registro consolidado según las consignas oficiales de bitácora AE4 "
            "(Consignas_Bitacora_AE4.docx)."
        ),
        body_font_pt=8.5,
    )

    add_h1(rb, "2. Registro cronológico detallado de actividades", page_break=False)
    for idx, entry in enumerate(spec.entries, start=1):
        rb.h2(f"Registro {idx} — {entry.fecha} ({entry.fase})")
        rb.bullets(
            [
                f"**Actividad realizada:** {entry.actividad}",
                f"**Herramientas y procedimientos utilizados:** {entry.herramientas}",
                f"**Dificultades encontradas y soluciones aplicadas:** {entry.dificultades_soluciones}",
                f"**Evidencias del trabajo:** {entry.evidencias}",
                f"**Decisiones técnicas y reflexión sobre lo aprendido:** {entry.decisiones_reflexion}",
            ]
        )

    add_h1(rb, "3. Reflexión integradora y fundamentación (Moodle)", page_break=True)
    rb.p(
        "La siguiente síntesis articula las tres dimensiones de la rúbrica evaluativa y la "
        "justificación técnica de la decisión arquitectónica principal asumida durante el proyecto, "
        "para su registro en el portafolio y en el Texto en Línea de Moodle."
    )
    rb.bullets(
        [
            f"**Saber (dimensión conceptual):** {spec.moodle_saber}",
            f"**Saber Hacer (dimensión procedimental):** {spec.moodle_saber_hacer}",
            f"**Saber Ser (dimensión actitudinal y ética):** {spec.moodle_saber_ser}",
        ]
    )
    rb.h2("Decisión técnica relevante justificada")
    rb.p(spec.moodle_decision_tecnica)

    add_h1(rb, "4. Referencias", page_break=False)
    rb.references(spec.referencias)

    docx_path = gia.DOCK_DIR / f"Bitacora_AE4_{spec.slug}.docx"
    md_path = gia.DOCK_DIR / f"Bitacora_AE4_{spec.slug}.md"

    doc.save(str(docx_path))
    md_path.write_text("\n".join(rb.md), encoding="utf-8")

    verify_bitacora_outputs(docx_path, md_path)
    return docx_path, md_path


def verify_bitacora_outputs(docx_path: Path, md_path: Path) -> None:
    """Verifica existencia, ausencia de términos prohibidos y formato limpio."""
    assert docx_path.exists() and docx_path.stat().st_size > 5_000, f"DOCX inválido: {docx_path}"
    assert md_path.exists() and md_path.stat().st_size > 2_000, f"MD inválido: {md_path}"

    loaded = Document(str(docx_path))
    chunks: List[str] = [p.text for p in loaded.paragraphs]
    for t in loaded.tables:
        for row in t.rows:
            for cell in row.cells:
                chunks.append(cell.text)

    w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    xml_texts: List[str] = []
    content_fonts: set[str] = set()
    with zipfile.ZipFile(docx_path, "r") as zf:
        for name in zf.namelist():
            if name.startswith("word/") and name.endswith(".xml"):
                root = ET.fromstring(zf.read(name))
                xml_texts.extend(t for t in root.itertext() if t)
                if name == "word/document.xml" or name.startswith(("word/header", "word/footer")):
                    for rfonts in root.iter(f"{w_ns}rFonts"):
                        for val in rfonts.attrib.values():
                            content_fonts.add(val)

    assert content_fonts == {"Times New Roman"}, (
        f"FALLO TIPOGRAFÍA en {docx_path.name}: fuentes detectadas {sorted(content_fonts)}"
    )

    md_text = md_path.read_text(encoding="utf-8")
    all_docx_text = "\n".join(chunks) + "\n" + "\n".join(xml_texts)
    full_text = all_docx_text + "\n" + md_text

    assert "aitara" not in full_text.lower(), (
        f"FALLO EDITORIAL en {docx_path.name}: se detectó término prohibido."
    )
    bad_idx = all_docx_text.find("`")
    assert bad_idx == -1, (
        f"FALLO FORMATO en {docx_path.name}: backtick literal cerca de "
        f"{all_docx_text[max(0, bad_idx - 25):bad_idx + 25]!r}"
    )
    assert len(loaded.tables) == 1, f"Se esperaba 1 tabla en {docx_path.name}"


def build_specs() -> List[StudentBitacoraSpec]:
    """Define las bitácoras individuales de Santiago Nuñez y Joaquín Sánchez."""
    santiago = StudentBitacoraSpec(
        slug="Nunez_Santiago",
        nombre_completo="Santiago Agustín Nuñez",
        nombre_portada="Nuñez, Santiago Agustín",
        dni="44.952.958",
        rol_principal="Diseño DDL espacial, ETL urbano OSM/siniestralidad, Consultas de Autoría y Concurrencia MVCC",
        fecha_entrega="23 de noviembre de 2026",
        resumen_rol=(
            "Mi responsabilidad principal abarcó la arquitectura base de PostgreSQL/PostGIS, el "
            "diseño del esquema normalizado `sig_ae4` con triggers reactivos, la ingesta de la red "
            "vial urbana de OpenStreetMap y siniestralidad vial de Posadas, la formulación de las "
            "tres consultas espaciales de autoría (`03_consultas_autoria.sql`) y la verificación "
            "de transacciones ABM, rechazos de integridad y bloqueo concurrente MVCC en la Fase III."
        ),
        entries=[
            BitacoraEntry(
                fecha="19/11/2026",
                fase="Fase I",
                actividad=(
                    "Configuración de infraestructura PostgreSQL `16.4` + PostGIS `3.4.3` en "
                    "Docker (`docker-compose.yml`, puerto `5433`) y diseño DDL completo del esquema "
                    "`sig_ae4` (`sql/00_init.sql`) con `19` tablas normalizadas, restricciones y "
                    "funciones PL/pgSQL reactivas para habilitar la ingesta paralela de capas "
                    "oficiales por parte de Joaquín."
                ),
                herramientas=(
                    "Docker Compose (`postgis/postgis:16-3.4`), `psql`, PostgreSQL `16.4`, "
                    "PostGIS `3.4.3` y SQL/PL-pgSQL (`GENERATED ALWAYS AS IDENTITY`, "
                    "`FOREIGN KEY`, `CHECK (ST_IsValid(geom))`, triggers `BEFORE`/`AFTER`)."
                ),
                dificultades_soluciones=(
                    "El trigger de enlace espacial de incidentes (`trg_02_sync_incidente_nodos`) "
                    "necesitaba la columna proyectada `geom_m` en `EPSG:5348` ya calculada antes "
                    "de buscar vecinos cercanos por KNN (`<->`). Se resolvió nombrando los "
                    "triggers alfabéticamente (`trg_01_sync_geom_m` seguido de "
                    "`trg_02_sync_incidente_nodos`) para garantizar el orden determinístico de "
                    "disparo de PostgreSQL en `BEFORE INSERT OR UPDATE`."
                ),
                evidencias=(
                    "`docker-compose.yml`, `sql/00_init.sql` (`19` tablas, `3` funciones PL/pgSQL "
                    "y bitácora `JSONB` `auditoria_ediciones`)."
                ),
                decisiones_reflexion=(
                    "Definir los esquemas desacoplados `staging` y `sig_ae4` desde el primer día "
                    "permitió que Joaquín comenzara de inmediato a ingestar IGN e IDE Posadas sin "
                    "chocar con las restricciones productivas. Comprendí en la práctica cómo las "
                    "claves `IDENTITY`, `CHECK (ST_IsValid(geom))` y los triggers encadenados "
                    "blindan la edición concurrente desde QGIS."
                ),
            ),
            BitacoraEntry(
                fecha="20/11/2026",
                fase="Fase I",
                actividad=(
                    "Desarrollo y ejecución del pipeline ETL de infraestructura urbana "
                    "OpenStreetMap, nodos de control vial, siniestralidad de Posadas y exposición "
                    "climática, seguido de la auditoría integral de integridad (`sql/01_validacion.sql`) "
                    "sobre las `19` tablas unificadas (incluyendo las `13` capas oficiales cargadas "
                    "por Joaquín)."
                ),
                herramientas=(
                    "Python (`psycopg2-binary`, `shapely`, `ast`, `python-dotenv`), JSON/JSONL "
                    "de red vial urbana OSM y prensa local curada, más consultas SQL de auditoría "
                    "en `psql`."
                ),
                dificultades_soluciones=(
                    "Al reconstruir `1.286` calles desde nodos ordenados de OpenStreetMap, algunas "
                    "arterias homónimas discontinuas generaban trazos rectos artificiales cruzando "
                    "manzanas; además, micro-segmentos degenerados fallaban `ST_IsValid`. Se "
                    "implementó segmentación automática en sub-tramos cuando la distancia Haversine "
                    "entre nodos superaba `300,0 m` y una extensión mínima (`~1 m`) para segmentos "
                    "puntuales."
                ),
                evidencias=(
                    "Carga verificada de `1.286` calles, `7.898` intersecciones (`72` con "
                    "`nivel_drenaje`), `7` nodos de control, `1.429` incidentes (`12` reales + "
                    "`1.417` simulados) y `2` filas de `exposicion_clima`; salida limpia en "
                    "`outputs/validacion_resultados.txt` (`18.442` geometrías válidas, `0` "
                    "huérfanos en las `5` FKs)."
                ),
                decisiones_reflexion=(
                    "Separar explícitamente `origen IN ('real', 'simulado')` con restricción "
                    "`CHECK` impide mezclar los `12` siniestros reales relevados (ocurridos entre "
                    "enero y noviembre de 2026, sin dato de lluvia) con los `1.417` eventos "
                    "sintéticos 2023–2025. Aprendí que la calidad científica de un SIG depende "
                    "tanto de la trazabilidad de sus fuentes como de su rigor geométrico."
                ),
            ),
            BitacoraEntry(
                fecha="21/11/2026",
                fase="Fase II",
                actividad=(
                    "Formulación, programación y ejecución de las tres consultas espaciales "
                    "originales de autoría sobre Posadas (`sql/03_consultas_autoria.sql`), "
                    "cruzando las capas oficiales IDE cargadas por Joaquín (`escuelas`, `semaforos`, "
                    "`avenidas_mano_unica`, `asfalto_sobre_empedrado`, `delegaciones`) con la red "
                    "OSM e incidentes: Autoría 1, Autoría 2A/2B/2C y Autoría 3."
                ),
                herramientas=(
                    "PostgreSQL/PostGIS (`ST_DWithin`, `ST_Distance`, `ST_Within`, `ST_Area`, "
                    "`ST_Length`, operador KNN `<->` en `EPSG:5348`, `JOIN LATERAL`, `CTE` y "
                    "agregaciones condicionales `COUNT(*) FILTER`)."
                ),
                dificultades_soluciones=(
                    "Al cruzar intersecciones con múltiples escuelas dentro de `150 m`, el `JOIN` "
                    "tradicional duplicaba filas y `i.id`, impidiendo a Joaquín cargar las "
                    "consultas como capas dinámicas en QGIS DB Manager (que exige clave primaria "
                    "única). Se resolvió reemplazando por `JOIN LATERAL (... ORDER BY i.geom_m <-> "
                    "e.geom_m LIMIT 1)` para conservar exactamente una fila por esquina (`104` "
                    "intersecciones candidatas)."
                ),
                evidencias=(
                    "`sql/03_consultas_autoria.sql`, `outputs/consultas_autoria_resultados.txt`, "
                    "`outputs/mapas_qgis/mapa_03_autoria1_escuelas_sin_semaforo.png` (`104` cruces "
                    "escolares en mano única sin semáforo) y "
                    "`mapa_04_autoria3_brecha_delegaciones.png` (`12` delegaciones)."
                ),
                decisiones_reflexion=(
                    "Normalizar la siniestralidad por exposición horaria (`1.000` horas-nodo) en "
                    "Autoría 2A reveló una razón lluvia/seco simulada de `1,74×` en drenaje "
                    "`BAJO`/`MEDIO` frente a `1,59×` en `ALTO`, y en Autoría 3 expuso `0` "
                    "semáforos en Itaembé Guazú e Itaembé Miní Este frente a `44,31` cada `100` "
                    "intersecciones en Sede Central. Confirmé el valor del SQL espacial analítico "
                    "para priorizar inversión pública con evidencia."
                ),
            ),
            BitacoraEntry(
                fecha="22/11 al 23/11/2026",
                fase="Fase III",
                actividad=(
                    "Ejecución y documentación de pruebas transaccionales ABM, rechazos "
                    "controlados de integridad (`sql/05_edicion_transacciones.sql`) y ensayo "
                    "automatizado de bloqueo concurrente MVCC (`scripts/test_bloqueo_concurrente.py`) "
                    "sobre la misma instancia conectada por Joaquín desde `QGIS 4.2.1` "
                    "(`proyecto_ae4.qgz`), cerrando además la auditoría contra la consigna AE4."
                ),
                herramientas=(
                    "PostgreSQL `psql`, Python `psycopg2` multihilo (`threading`), vistas de "
                    "sistema `pg_stat_activity` y `pg_locks`, más `QGIS 4.2.1` conectado a "
                    "`localhost:5433`."
                ),
                dificultades_soluciones=(
                    "Al probar concurrencia entre dos clientes, las ediciones hechas dentro de QGIS "
                    "no bloqueaban inmediatamente a `psql` porque el cliente SIG mantiene los "
                    "cambios en un búfer local en memoria hasta pulsar *Guardar cambios de la capa*. "
                    "Para reproducir y medir de forma determinística el bloqueo, se diseñó un test "
                    "con dos sesiones concurrentes sincronizadas que inspeccionan `pg_locks` y "
                    "`pg_stat_activity`."
                ),
                evidencias=(
                    "`outputs/edicion_transacciones_resultados.txt` (alta/baja `TEST_QGIS_01`, "
                    "desplazamiento de `3.512,44 m` con reasignación automática de triggers, "
                    "`8` entradas en `auditoria_ediciones` y `3` rechazos `SQLSTATE 23514`/`23503`) "
                    "y `outputs/bloqueo_concurrente_resultados.txt` (`transactionid ShareLock` "
                    "liberado tras `2,00 s`)."
                ),
                decisiones_reflexion=(
                    "Verificar que PostgreSQL MVCC nunca bloquea lecturas contra escrituras y "
                    "resuelve conflictos de escritura a nivel de fila mediante `RowExclusiveLock` y "
                    "`transactionid ShareLock` cerró de punta a punta la comprensión de la "
                    "arquitectura cliente-servidor."
                ),
            ),
        ],
        moodle_saber=(
            "Consolidé los fundamentos de modelado relacional espacial bajo el estándar *Simple "
            "Feature Access* (Open Geospatial Consortium [OGC], 2011), diferenciando el rol de "
            "las restricciones geométricas (`ST_IsValid`), la integridad referencial en tablas "
            "espaciales, los triggers reactivos en PostgreSQL/PostGIS y el control de "
            "concurrencia multiversión (MVCC) frente a clientes SIG como QGIS."
        ),
        moodle_saber_hacer=(
            "Diseñé e implementé en PostgreSQL `16.4` / PostGIS `3.4.3` un esquema normalizado de "
            "`19` tablas (`sig_ae4`), triggers PL/pgSQL para reproyección y enlace espacial "
            "automático, pipelines ETL en Python para reconstruir y validar `18.442` geometrías, "
            "consultas espaciales complejas con `JOIN LATERAL`, `ST_DWithin` y KNN `<->`, y "
            "pruebas reales de edición ABM, rechazos de restricciones y bloqueos concurrentes."
        ),
        moodle_saber_ser=(
            "Mantuve rigor metodológico y transparencia al separar estrictamente mediante "
            "restricciones `CHECK` los `12` siniestros reales relevados de prensa local respecto de "
            "los `1.417` eventos sintéticos de demostración, evitando presentar patrones "
            "simulados como evidencia empírica y validando en vivo toda la entrega antes del "
            "cierre."
        ),
        moodle_decision_tecnica=(
            "La decisión técnica central asumida en la Fase I y verificada en la Fase III fue "
            "implementar un **modelo relacional espacial normalizado (`sig_ae4`, `19` tablas) "
            "protegido por integridad declarativa, triggers encadenados y control transaccional "
            "MVCC**. Siguiendo el estándar *Simple Feature Access* (OGC, 2011) y los principios "
            "de calidad de datos geográficos (Olaya, 2014), todas las geometrías exigen validez "
            "estricta (`NOT NULL CHECK (ST_IsValid(geom))`), claves primarias `GENERATED ALWAYS "
            "AS IDENTITY` sin colisiones entre clientes y restricciones de dominio (`origen`, "
            "`severidad 1..5`). Sobre ese esquema, los triggers `trg_01_sync_geom_m`, "
            "`trg_02_sync_incidente_nodos` y `fn_auditar_edicion()` automatizan la coherencia "
            "métrica, los vínculos espaciales (`<= 150 m` y `<= 500 m`) y la bitácora `JSONB` "
            "ante cualquier alta o desplazamiento desde QGIS (PostGIS Project Steering Committee, "
            "2024). En concurrencia, las pruebas comprobaron rechazos inmediatos (`SQLSTATE "
            "23514` y `23503`) ante datos inválidos y bloqueo de fila ordenado (`RowExclusiveLock` "
            "y `transactionid ShareLock`) bajo MVCC cuando dos sesiones editan la misma tupla "
            "(PostgreSQL Global Development Group, 2024)."
        ),
        referencias=[
            (
                "Olaya, V. (2014). *Sistemas de Información Geográfica*. Creative Commons "
                "Attribution 3.0. https://volaya.github.io/libro-sig/"
            ),
            (
                "Open Geospatial Consortium. (2011). *OpenGIS Implementation Standard for "
                "Geographic information - Simple feature access - Part 1: Common architecture "
                "(OGC 06-103r4)*. https://www.ogc.org/standards/sfa/"
            ),
            (
                "PostGIS Project Steering Committee. (2024). *PostGIS 3.4.3 manual*. "
                "https://postgis.net/documentation/"
            ),
            (
                "PostgreSQL Global Development Group. (2024). *PostgreSQL 16.4 documentation*. "
                "https://www.postgresql.org/docs/16/"
            ),
        ],
    )

    joaquin = StudentBitacoraSpec(
        slug="Sanchez_Joaquin",
        nombre_completo="Joaquín Sebastián Sánchez",
        nombre_portada="Sánchez, Joaquín Sebastián",
        dni="45.452.416",
        rol_principal="Cartografía oficial WFS/SHP, Consultas regionales (a–i), Índices GiST/Benchmark e Integración QGIS 4.2.1",
        fecha_entrega="23 de noviembre de 2026",
        resumen_rol=(
            "La responsabilidad principal que sostuve en el proyecto consistió en relevar, "
            "descargar y normalizar las fuentes geográficas oficiales nacionales y municipales "
            "(IGN, BAHRA, Natural Earth 50m, IDE Posadas e INDEC 2022) a través de un esquema "
            "`staging`, resolver las `9` consultas espaciales regionales obligatorias (`a–i`) y el "
            "diagnóstico topológico DE-9IM, diseñar y medir los `34` índices espaciales GiST "
            "hasta `1.000.000` de puntos, y construir el proyecto nativo en `QGIS 4.2.1` con sus "
            "láminas cartográficas y el informe final APA 7."
        ),
        entries=[
            BitacoraEntry(
                fecha="19/11/2026",
                fase="Fase I",
                actividad=(
                    "Descarga automatizada de fuentes OGC WFS oficiales, ingesta cruda en el "
                    "esquema `staging` definido por Santiago (`00_init.sql`), prueba de carga "
                    "Shapefile con `ogr2ogr` (`GDAL 3.13.2`) y normalización/reparación topológica "
                    "de las `13` tablas oficiales hacia `sig_ae4`."
                ),
                herramientas=(
                    "Python (`requests`, `psycopg2`), GeoServer WFS de IGN e IDE Posadas, "
                    "`GDAL 3.13.2` (`ogr2ogr.exe` vía `/vsizip/`), `SHAPE_ENCODING=ISO-8859-1` y "
                    "SQL espacial (`ST_MakeValid`, `ST_CollectionExtract`, `ST_PointOnSurface`, "
                    "`ST_Within`)."
                ),
                dificultades_soluciones=(
                    "Se identificaron tres problemas de origen: (1) la capa `ign:pais` solo "
                    "exponía Argentina, por lo que se integró Natural Earth 50m para cubrir los "
                    "`12` países sudamericanos; (2) el filtro del Río Uruguay devolvía homónimos "
                    "en Patagonia/Andes, resuelto filtrando por longitud `>= -62°`; y (3) el "
                    "Shapefile de `delegaciones` presentó acentos rotos si no se declaraba "
                    "`ISO-8859-1` y `2` autointersecciones (`todas_validas = f` en `staging`), "
                    "reparadas en `01_cargar_staging_a_final.sql` antes de agregar `331.753` "
                    "habitantes desde `459` radios censales 2022."
                ),
                evidencias=(
                    "`scripts/descargar_ign_ide.py`, `scripts/cargar_ign_ide.py`, "
                    "`scripts/cargar_ogr2ogr_referencia.ps1`, "
                    "`sql/01_cargar_staging_a_final.sql` y `outputs/verificacion_ogr2ogr.txt`."
                ),
                decisiones_reflexion=(
                    "Aislar la carga cruda en `staging` sobre la base desplegada por Santiago "
                    "permitió diagnosticar y sanear defectos reales de cartografía oficial antes "
                    "de poblar `sig_ae4` sin relajar las reglas `ST_IsValid` ni el cálculo de "
                    "`geom_m`."
                ),
            ),
            BitacoraEntry(
                fecha="20/11/2026",
                fase="Fase II",
                actividad=(
                    "Formulación y ejecución de las `9` consultas espaciales regionales "
                    "obligatorias (incisos `a` a `i`) en `sql/02_consultas_a_i.sql` y diagnóstico "
                    "topológico de fronteras provinciales del IGN, en paralelo al cierre de la "
                    "carga urbana y validación global ejecutada por Santiago."
                ),
                herramientas=(
                    "PostGIS `geography` sobre elipsoide WGS 84 (`ST_Area`, `ST_Length`, "
                    "`ST_Distance`, `ST_DWithin`), operaciones de superposición (`ST_Union`, "
                    "`ST_Intersection`, `ST_CollectionExtract`), predicados DE-9IM (`ST_Touches`, "
                    "`ST_Intersects`, `ST_Overlaps`, `ST_Dimension`) y `CROSS JOIN LATERAL` con `<->`."
                ),
                dificultades_soluciones=(
                    "En el inciso `d` (vecindad), `ST_Touches` difería respecto de `ST_Intersects` "
                    "en `4` límites interprovinciales del IGN (*Entre Ríos–Corrientes*, *Buenos "
                    "Aires–Entre Ríos*, *San Juan–La Rioja* y *Jujuy–Salta*). Al inspeccionar "
                    "`ST_Dimension(ST_Intersection(a.geom, b.geom))` se comprobaron `4` "
                    "micro-solapamientos bidimensionales de `0,00` a `5,29 m²`, los cuales violan "
                    "la condición de interiores disjuntos exigida por `ST_Touches` según DE-9IM."
                ),
                evidencias=(
                    "`sql/02_consultas_a_i.sql` y `outputs/consultas_a_i_resultados.txt` (`140` "
                    "localidades BAHRA en Misiones, `Bernardo de Irigoyen` a `97,266 km` del "
                    "Paraná, `1.156` localidades a `< 200 km` del río y accesibilidad a `RN 12`, "
                    "`RN 14` y `RN 101`)."
                ),
                decisiones_reflexion=(
                    "Elegir `geom::geography` en escala regional evitó deformaciones continentales "
                    "y de las `7` fajas POSGAR de Argentina (`EPSG:5343–5349`), mientras que el "
                    "uso de `ST_Union` sobre cursos fluviales segmentados garantizó no duplicar "
                    "longitudes al cruzar departamentos."
                ),
            ),
            BitacoraEntry(
                fecha="21/11/2026",
                fase="Fase II",
                actividad=(
                    "Diseño de `34` índices espaciales GiST (`sql/04_indices_benchmark.sql`) para "
                    "acelerar las consultas regionales y las consultas urbanas de autoría de "
                    "Santiago, junto con el benchmark reproducible (`scripts/benchmark_gist.py`) "
                    "hasta `1.000.000` de puntos."
                ),
                herramientas=(
                    "Índices PostGIS `USING GIST` (`geom`, `geom_m` y funcionales "
                    "`(geom::geography)`), `VACUUM ANALYZE`, `EXPLAIN (ANALYZE, BUFFERS)` y "
                    "Python (`psycopg2`, `matplotlib`) para análisis y curva logarítmica."
                ),
                dificultades_soluciones=(
                    "Al medir consultas regionales con `ST_DWithin(geom::geography, ...)`, el "
                    "planificador descartaba el índice GiST estándar sobre `geom` "
                    "(`gist_geometry_ops_2d`) y caía en `Seq Scan` (`240.178,937 ms`, `282.565` "
                    "buffers). Se creó el índice GiST funcional `USING GIST ((geom::geography))` "
                    "(`gist_geography_ops`), bajando a `4.078,849 ms` (`58,88×` de aceleración)."
                ),
                evidencias=(
                    "`sql/04_indices_benchmark.sql`, `scripts/benchmark_gist.py`, "
                    "`outputs/benchmark_resultados.md` (`11,87×` en cruce urbano, `47,80×` en KNN, "
                    "`17,36×–28,16×` hasta `1M` de puntos) y `outputs/benchmark_gist_volumen.png`."
                ),
                decisiones_reflexion=(
                    "Comprobar empíricamente la arquitectura R-Tree / MBR (filtro grueso `&&` + "
                    "refinamiento exacto GEOS) y la diferencia entre familias de operadores "
                    "`geometry` y `geography` demostró que indexar mal una expresión casteada es "
                    "equivalente a no tener índice en producción."
                ),
            ),
            BitacoraEntry(
                fecha="22/11 al 23/11/2026",
                fase="Fase III",
                actividad=(
                    "Construcción programática del proyecto nativo `QGIS 4.2.1` (`proyecto_ae4.qgz`) "
                    "integrando las `17` tablas PostGIS, el WMS municipal y las `3` capas SQL de "
                    "autoría formuladas por Santiago, validación cruzada `1:1` de las `21` capas, "
                    "renderizado de `4` láminas cartográficas, DER e informe final APA 7."
                ),
                herramientas=(
                    "`QGIS 4.2.1 'Belém do Pará'` (`python-qgis.bat`, `QgsProject`, "
                    "`QgsMapRendererParallelJob`), proveedor nativo `postgres`, servicio WMS de "
                    "IDE Posadas, `matplotlib` y `python-docx`."
                ),
                dificultades_soluciones=(
                    "Era crítico evitar que el archivo `.qgz` almacenara usuario o contraseña de "
                    "PostgreSQL en texto plano dentro del XML empaquetado. Se parametrizaron las "
                    "cadenas `datasource` sin secretos, delegando la autenticación a *AuthDB* o al "
                    "prompt interactivo al abrir QGIS, y se verificaron `0` tokens `user=` / "
                    "`password=` junto con coincidencia exacta de `18.588` entidades en `21/21` capas."
                ),
                evidencias=(
                    "`qgis/proyecto_ae4.qgz`, `qgis/GUIA_QGIS_FASE3.md`, "
                    "`outputs/verificacion_qgis_4_2_1.txt`, `outputs/mapas_qgis/*.png`, "
                    "`outputs/der_sig_ae4.png`, `dock/AE4_SIG_Sanchez_Nunez.docx` y `.md`."
                ),
                decisiones_reflexion=(
                    "Configurar el proyecto QGIS en `EPSG:5348` con el subgrupo de Autoría en "
                    "DB Manager y validación automatizada `1:1` permitió que Santiago verificara "
                    "de forma reproducible las ediciones ABM y la concurrencia MVCC."
                ),
            ),
        ],
        moodle_saber=(
            "Comprendí en profundidad la organización de índices espaciales GiST basados en "
            "estructuras **R-Tree** sobre Rectángulos Mínimos Envolventes (*MBR*) (Guttman, 1984) "
            "y su ejecución en dos fases (filtro grueso *lossy* mediante `&&` o `<->` seguido de "
            "refinamiento exacto en GEOS), así como la distinción topológica DE-9IM entre "
            "`ST_Touches` y `ST_Intersects` y la incompatibilidad de familias de operadores entre "
            "`geometry` y `geography` (PostGIS Project Steering Committee, 2024)."
        ),
        moodle_saber_hacer=(
            "Implementé la descarga OGC WFS e ingesta ETL con `GDAL 3.13.2` (`ogr2ogr` con "
            "`ISO-8859-1`) y saneamiento topológico (`ST_MakeValid`) desde `staging`, resolví "
            "las `9` consultas regionales (`a–i`), creé `34` índices GiST midiendo medianas con "
            "`EXPLAIN (ANALYZE, BUFFERS)` hasta `1.000.000` de puntos, e integré las `21` capas "
            "en `QGIS 4.2.1` sin credenciales embebidas, produciendo cartografía temática e "
            "informe APA 7 reproducible."
        ),
        moodle_saber_ser=(
            "Prioricé la ética técnica y la reproducibilidad: verifiqué que el proyecto `.qgz` "
            "tuviera `0` secretos embebidos y que `.env` quedara excluido del control de "
            "versiones, audité `1:1` las `18.588` entidades entre QGIS y PostGIS, y documenté de "
            "forma transparente los micro-solapamientos de origen en las fuentes oficiales."
        ),
        moodle_decision_tecnica=(
            "La decisión técnica determinante fue combinar el almacenamiento canónico en "
            "`EPSG:4326` con cálculo geodésico `geom::geography` en la escala regional (`a–i`) e "
            "implementar **índices GiST funcionales `USING GIST ((geom::geography))`** junto con "
            "los índices estándar sobre `geom` y `geom_m` (Olaya, 2014). Un índice GiST clásico "
            "sobre `geometry` indexa cajas 2D planas con la familia `gist_geometry_ops_2d` "
            "(Guttman, 1984; PostGIS Project Steering Committee, 2024); al castear "
            "`geom::geography` en consulta, PostGIS requiere `gist_geography_ops` y el "
            "planificador cae en `Seq Scan`. Nuestro benchmark demostró que agregar el índice "
            "funcional redujo la consulta `localidades × cursos_agua` (`200 km`) de "
            "`240.178,937 ms` (`282.565` buffers) a `4.078,849 ms` (`45.853` buffers), "
            "alcanzando un speedup verificado de `58,88×` y sosteniendo aceleraciones de "
            "`11,87×` a `47,80×` en el resto de cargas."
        ),
        referencias=[
            (
                "Guttman, A. (1984). R-trees: A dynamic index structure for spatial searching. "
                "*Proceedings of the 1984 ACM SIGMOD International Conference on Management of "
                "Data*, 47–57. https://doi.org/10.1145/602259.602266"
            ),
            (
                "Olaya, V. (2014). *Sistemas de Información Geográfica*. Creative Commons "
                "Attribution 3.0. https://volaya.github.io/libro-sig/"
            ),
            (
                "PostGIS Project Steering Committee. (2024). *PostGIS 3.4.3 manual*. "
                "https://postgis.net/documentation/"
            ),
            (
                "QGIS Development Team. (2026). *QGIS Geographic Information System (Version 4.2.1 "
                "'Belém do Pará')*. Open Source Geospatial Foundation. https://qgis.org/"
            ),
        ],
    )

    return [santiago, joaquin]


def main() -> None:
    gia.DOCK_DIR.mkdir(parents=True, exist_ok=True)
    for spec in build_specs():
        docx_path, md_path = build_bitacora_document(spec)
        print(f"[OK] DOCX generado: {docx_path} ({docx_path.stat().st_size:,} bytes)")
        print(f"[OK] MD generado  : {md_path} ({md_path.stat().st_size:,} bytes)")
    print("[OK] Bitácoras individuales generadas y verificadas sin términos prohibidos.")


if __name__ == "__main__":
    main()
