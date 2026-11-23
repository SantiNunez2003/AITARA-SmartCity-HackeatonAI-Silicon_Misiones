"""Genera versiones universitarias limpias (sin marca AITARA) de Figura 01 (DER),
Figura 06 (Mapa Posadas en QGIS 4.2.1) y recorta el logo oficial de la UCP en
`ae4_sig/dock/figuras/`.

Se ejecuta en dos pasos o directamente:
  1) Con python estándar: recorta logo UCP y genera Figura_01_modelo_entidad_relacion.png
  2) Con python-qgis.bat: renderiza Figura_06_posadas_infraestructura_siniestros.png
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

FIG_DIR = Path(__file__).resolve().parents[1] / "dock" / "figuras"
SCRIPTS_DIR = Path(__file__).resolve().parent


def prepare_ucp_logo() -> None:
    from PIL import Image

    src = FIG_DIR / "_logo_ucp_2.png"
    dst = FIG_DIR / "logo_ucp.png"
    if not src.exists():
        raise FileNotFoundError(f"No existe {src}")

    im = Image.open(src).convert("RGBA")
    # Recortar márgenes blancos manteniendo padding discreto
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    comp = Image.alpha_composite(bg, im).convert("RGB")
    bbox = comp.point(lambda p: 255 if p < 245 else 0).getbbox()
    if bbox:
        pad = 8
        crop_box = (
            max(0, bbox[0] - pad),
            max(0, bbox[1] - pad),
            min(im.width, bbox[2] + pad),
            min(im.height, bbox[3] + pad),
        )
        im = im.crop(crop_box)
    im.save(dst, format="PNG")
    for tmp in ("_logo_ucp_1.png", "_logo_ucp_2.png"):
        p = FIG_DIR / tmp
        if p.exists():
            p.unlink()
    print(f"[OK] logo_ucp.png: {im.size[0]}x{im.size[1]} px ({dst.stat().st_size} bytes)")


def _sanitize_text(txt: str) -> str:
    replacements = [
        ("nodos_referencia_aitara", "nodos_control_vial"),
        ("IDE/OSM/AITARA", "IDE Posadas / OpenStreetMap"),
        ("ANALÍTICA AITARA, CLIMA Y AUDITORÍA", "SINIESTRALIDAD, EXPOSICIÓN CLIMÁTICA Y AUDITORÍA"),
        ("OSM vía AITARA", "OpenStreetMap"),
        ("AITARA (atributo experto)", "Clasificación experta (Posadas)"),
        ("AITARA (reales + simulados)", "Prensa local + sintéticos"),
        ("Hechos viales reales y simulados con enlace automático a intersecciones y nodos AITARA.", "Siniestros reales y sintéticos vinculados a intersecciones y nodos de control."),
        ("Nodos de corredores críticos AITARA con atributos expertos y nivel de drenaje.", "Nodos de control vial en Posadas con atributos operativos y drenaje."),
        ("Código de nodo AITARA", "Código de nodo de control"),
        ("nodos AITARA", "nodos de control"),
        ("AITARA", "estudio"),
    ]
    out = txt
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def generate_clean_der() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    sys.path.insert(0, str(SCRIPTS_DIR))
    import generar_qgis_y_der as gqd

    clean_tables = {}
    for tbl in gqd.TABLES:
        t = copy.deepcopy(tbl)
        t.name = _sanitize_text(t.name)
        t.source = _sanitize_text(t.source)
        t.summary = _sanitize_text(t.summary)
        t.notes = [_sanitize_text(n) for n in t.notes]
        for col in t.columns:
            col.name = _sanitize_text(col.name)
            col.constraints = _sanitize_text(col.constraints)
            col.description = _sanitize_text(col.description)
        clean_tables[t.name] = t

    fig, ax = plt.subplots(figsize=(24, 16.5), dpi=250)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 68)
    ax.axis("off")
    fig.patch.set_facecolor("#F8FAFC")

    banner = FancyBboxPatch(
        (1.2, 63.3), 97.6, 3.9,
        boxstyle="round,pad=0.2,rounding_size=0.6",
        facecolor="#0F172A", edgecolor="#334155", linewidth=1.5, zorder=2,
    )
    ax.add_patch(banner)
    ax.text(
        50.0, 65.85,
        "MODELO ENTIDAD-RELACIÓN ESPACIAL — ESQUEMA sig_ae4 (PostgreSQL 16 + PostGIS 3.4)",
        ha="center", va="center", fontsize=14.5, fontweight="bold", color="#FFFFFF", family="DejaVu Sans", zorder=3,
    )
    ax.text(
        50.0, 64.15,
        "19 Tablas: 6 Regionales (IGN/NE) · 11 Urbanas Posadas (IDE Posadas / OpenStreetMap) · 2 Alfanuméricas/Auditoría  |  "
        "Dual SRID: EPSG:4326 (geom) + EPSG:5348 (geom_m) + GiST (geom::geography)",
        ha="center", va="center", fontsize=9.2, color="#CBD5E1", family="DejaVu Sans", zorder=3,
    )

    zone_boxes = {
        "regional": (1.2, 7.6, 26.0, 54.6),
        "urbano": (28.2, 7.6, 37.8, 54.6),
        "analitica": (69.8, 7.6, 29.0, 54.6),
    }
    zone_titles = {
        "regional": gqd.ZONE_PALETTE["regional"]["title"],
        "urbano": "ZONA 2 — ESCALA URBANA POSADAS (IDE POSADAS + OPENSTREETMAP)",
        "analitica": "ZONA 3 — SINIESTRALIDAD, EXPOSICIÓN CLIMÁTICA Y AUDITORÍA",
    }
    for zkey, (zx, zy, zw, zh) in zone_boxes.items():
        pal = gqd.ZONE_PALETTE[zkey]
        zpatch = FancyBboxPatch(
            (zx, zy), zw, zh,
            boxstyle="round,pad=0.2,rounding_size=0.7",
            facecolor=pal["bg"], edgecolor=pal["border"], linewidth=1.8, zorder=1,
        )
        ax.add_patch(zpatch)
        ax.text(
            zx + zw / 2.0, zy + zh - 1.35,
            zone_titles[zkey],
            ha="center", va="center", fontsize=7.6, fontweight="bold", color=pal["header"], family="DejaVu Sans", zorder=2,
        )

    pal1 = gqd.ZONE_PALETTE["regional"]
    gqd._draw_entity_box(ax, clean_tables["paises"], 2.1, 49.3, 12.0, 9.5, pal1, font_size=5.8)
    gqd._draw_entity_box(ax, clean_tables["provincias"], 2.1, 35.7, 12.0, 10.6, pal1, font_size=5.8)
    gqd._draw_entity_box(ax, clean_tables["departamentos"], 2.1, 22.8, 12.0, 9.9, pal1, font_size=5.8)
    gqd._draw_entity_box(ax, clean_tables["localidades"], 2.1, 8.9, 12.0, 10.9, pal1, font_size=5.8)
    gqd._draw_entity_box(ax, clean_tables["cursos_agua"], 14.9, 41.5, 11.7, 11.2, pal1, font_size=5.8)
    gqd._draw_entity_box(ax, clean_tables["rutas"], 14.9, 25.5, 11.7, 11.2, pal1, font_size=5.8)

    note1 = FancyBboxPatch(
        (14.9, 9.2), 11.7, 12.5,
        boxstyle="round,pad=0.2,rounding_size=0.5",
        facecolor="#DBEAFE", edgecolor="#2563EB", linewidth=1.1, zorder=3,
    )
    ax.add_patch(note1)
    ax.text(
        20.75, 15.45,
        "CRITERIO MÉTRICO REGIONAL\n"
        "• Solo geom (EPSG:4326)\n"
        "• Distancias/áreas geodésicas\n"
        "  vía geom::geography (m / km²)\n"
        "• Índice funcional GiST:\n"
        "  USING GIST ((geom::geography))\n"
        "• Validación CHECK ST_IsValid\n"
        "• 04_indices_benchmark.sql",
        ha="center", va="center", fontsize=6.2, color="#1E3A8A", family="DejaVu Sans", zorder=4,
    )

    pal2 = gqd.ZONE_PALETTE["urbano"]
    col_xs = [29.0, 41.3, 53.6]
    cw = 11.4
    gqd._draw_entity_box(ax, clean_tables["delegaciones"], col_xs[0], 46.8, cw, 12.0, pal2, font_size=5.6)
    gqd._draw_entity_box(ax, clean_tables["escuelas"], col_xs[1], 45.6, cw, 13.2, pal2, font_size=5.6)
    gqd._draw_entity_box(ax, clean_tables["semaforos"], col_xs[2], 44.8, cw, 14.0, pal2, font_size=5.6)
    gqd._draw_entity_box(ax, clean_tables["paradas"], col_xs[0], 29.5, cw, 13.4, pal2, font_size=5.6)
    gqd._draw_entity_box(ax, clean_tables["avenidas_mano_unica"], col_xs[1], 30.8, cw, 12.1, pal2, font_size=5.6)
    gqd._draw_entity_box(ax, clean_tables["asfalto_sobre_empedrado"], col_xs[2], 30.8, cw, 12.1, pal2, font_size=5.6)
    gqd._draw_entity_box(ax, clean_tables["ciclovias"], col_xs[0], 13.4, cw, 12.2, pal2, font_size=5.6)
    gqd._draw_entity_box(ax, clean_tables["calles"], col_xs[1], 13.4, cw, 12.2, pal2, font_size=5.6)
    gqd._draw_entity_box(ax, clean_tables["intersecciones"], col_xs[2], 9.0, cw, 18.2, pal2, font_size=5.5)

    ax.text(
        40.85, 10.2,
        "Cruces espaciales urbanos en geom_m (EPSG:5348):\n"
        "ST_DWithin / ST_Within / <-> (KNN) sobre índices GiST geom_m",
        ha="center", va="center", fontsize=5.8, fontweight="bold", color="#065F46",
        bbox={"boxstyle": "round,pad=0.28", "facecolor": "#D1FAE5", "edgecolor": "#059669", "linewidth": 0.9},
        zorder=4,
    )

    pal3 = gqd.ZONE_PALETTE["analitica"]
    gqd._draw_entity_box(ax, clean_tables["auditoria_ediciones"], 70.6, 45.8, 12.5, 12.8, pal3, font_size=5.6)
    gqd._draw_entity_box(ax, clean_tables["exposicion_clima"], 85.9, 45.8, 12.1, 12.8, pal3, font_size=5.5)
    gqd._draw_entity_box(ax, clean_tables["incidentes_viales"], 70.6, 9.2, 12.5, 29.0, pal3, font_size=5.5)
    gqd._draw_entity_box(ax, clean_tables["nodos_control_vial"], 85.9, 13.5, 12.1, 24.7, pal3, font_size=5.5)

    gqd._draw_arrow(ax, (8.1, 49.3), (8.1, 46.3), "1:N pais_id", "#1D4ED8", label_offset=(2.6, 0.0))
    gqd._draw_arrow(ax, (8.1, 35.7), (8.1, 32.7), "1:N provincia_id", "#1D4ED8", label_offset=(3.1, 0.0))
    gqd._draw_arrow(ax, (8.1, 22.8), (8.1, 19.8), "1:N departamento_id", "#1D4ED8", label_offset=(3.4, 0.0))

    gqd._draw_arrow(ax, (70.6, 15.2), (65.0, 15.2), "", "#B45309")
    ax.text(
        67.8, 18.2, "FK\ninterseccion_id\n(<=150 m)",
        ha="center", va="center", fontsize=5.3, fontweight="bold", color="#9A3412",
        bbox={"boxstyle": "round,pad=0.2", "facecolor": "#FFFFFF", "edgecolor": "#B45309", "linewidth": 0.85}, zorder=7,
    )

    gqd._draw_arrow(ax, (83.1, 24.5), (85.9, 24.5), "", "#B45309")
    ax.text(
        84.5, 28.2, "FK\nnodo_ref\n(<=500m)",
        ha="center", va="center", fontsize=4.9, fontweight="bold", color="#9A3412",
        bbox={"boxstyle": "round,pad=0.16", "facecolor": "#FFFFFF", "edgecolor": "#B45309", "linewidth": 0.85}, zorder=7,
    )

    gqd._draw_arrow(ax, (65.0, 52.2), (70.6, 52.2), "", "#DC2626", dashed=True)
    ax.text(
        67.8, 55.2, "TRG\nauditar\nsemaforos",
        ha="center", va="center", fontsize=5.3, fontweight="bold", color="#B91C1C",
        bbox={"boxstyle": "round,pad=0.2", "facecolor": "#FEF2F2", "edgecolor": "#DC2626", "linewidth": 0.85}, zorder=7,
    )

    gqd._draw_arrow(
        ax, (76.85, 38.2), (76.85, 45.8),
        "TRG trg_auditar_incidentes (INSERT/UPDATE/DELETE)", "#DC2626", dashed=True,
    )

    legend = FancyBboxPatch(
        (1.2, 1.0), 97.6, 5.5,
        boxstyle="round,pad=0.2,rounding_size=0.5",
        facecolor="#FFFFFF", edgecolor="#64748B", linewidth=1.3, zorder=2,
    )
    ax.add_patch(legend)
    ax.text(2.4, 5.2, "LEYENDA TÉCNICA DEL MODELO (00_init.sql + 04_indices_benchmark.sql)",
            ha="left", va="center", fontsize=8.0, fontweight="bold", color="#0F172A", family="DejaVu Sans", zorder=3)

    items = [
        (2.4, 3.3, "[PK] Primary Key (INTEGER GENERATED ALWAYS AS IDENTITY)"),
        (26.5, 3.3, "[FK] Foreign Key 1:N (flecha continua azul/ámbar)"),
        (53.0, 3.3, "[UQ] Restricción UNIQUE (incluye uq_intersecciones_par)"),
        (76.5, 3.3, "[CHK] Restricción CHECK (ST_IsValid, origen, severidad 1..5, drenaje)"),
        (2.4, 1.8, "[GEN] Columna generada STORED (horas_por_nodo)"),
        (26.5, 1.8, "[4326] GEOMETRY WGS84 (intercambio, WFS, QGIS + GiST geography)"),
        (53.0, 1.8, "[5348] GEOMETRY POSGAR 2007 Faja 6 (m) vía trg_01_sync_geom_m"),
        (76.5, 1.8, "TRG (flecha discontinua roja): trg_02_sync_incidente_nodos + trg_auditar_* -> JSONB"),
    ]
    for ix, iy, itext in items:
        ax.text(ix, iy, itext, ha="left", va="center", fontsize=6.4, color="#334155", family="DejaVu Sans", zorder=3)

    out_path = FIG_DIR / "Figura_01_modelo_entidad_relacion.png"
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.2, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[OK] {out_path.name}: {out_path.stat().st_size} bytes")


def generate_clean_mapa02() -> None:
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
    from qgis.core import QgsApplication, QgsRectangle

    sys.path.insert(0, str(SCRIPTS_DIR))
    import construir_proyecto_qgis4 as cq

    creds = cq.load_env_credentials(cq.ENV_PATH)
    autoria_sql = cq.extract_autoria_queries(cq.SQL_AUTORIA_PATH)
    qgs = QgsApplication([], False)
    qgs.initQgis()
    try:
        proj, layers, _ = cq.build_project_and_layers(creds, autoria_sql)
        out_path = FIG_DIR / "Figura_06_posadas_infraestructura_siniestros.png"
        cq.render_thematic_map(
            out_path,
            title="Mapa 2 · Posadas: Infraestructura Vial, Nodos de Control y Siniestralidad",
            subtitle="Separación estricta entre siniestros reales (n=12) y eventos sintéticos (n=1.417) sobre red vial, semáforos y escuelas",
            crs_authid="EPSG:5348",
            extent=QgsRectangle(6600800.0, 6964000.0, 6612400.0, 6975400.0),
            render_layers=[
                layers["incidentes_viales"],
                layers["nodos_referencia_aitara"],
                layers["semaforos"],
                layers["escuelas"],
                layers["avenidas_mano_unica"],
                layers["asfalto_sobre_empedrado"],
                layers["ciclovias"],
                layers["calles"],
                layers["delegaciones"],
            ],
            background_hex="#f8fafc",
            legend_entries=[
                cq.LegendEntry("section", "Siniestralidad (incidentes_viales)"),
                cq.LegendEntry("marker", "Incidente real (n=12)", fill="#dc2626", stroke="#7f1d1d", shape="diamond", size_px=12),
                cq.LegendEntry("marker", "Simulado · Severidad 3", fill="#ea580c", stroke="#9a3412", shape="circle", size_px=10),
                cq.LegendEntry("marker", "Simulado · Severidad 2", fill="#f59e0b", stroke="#92400e", shape="circle", size_px=8),
                cq.LegendEntry("marker", "Simulado · Severidad 1", fill="#fbbf24", stroke="#b45309", shape="circle", size_px=6),
                cq.LegendEntry("section", "Nodos de Control Vial (Drenaje)"),
                cq.LegendEntry("marker", "Drenaje BAJO (3 nodos)", fill="#be123c", stroke="#ffffff", shape="pentagon", size_px=12),
                cq.LegendEntry("marker", "Drenaje MEDIO (2 nodos)", fill="#9333ea", stroke="#ffffff", shape="pentagon", size_px=11),
                cq.LegendEntry("marker", "Drenaje ALTO (2 nodos)", fill="#0284c7", stroke="#ffffff", shape="pentagon", size_px=11),
                cq.LegendEntry("section", "Equipamiento y Red Vial IDE / OSM"),
                cq.LegendEntry("marker", "Semáforos IDE (280)", fill="#10b981", stroke="#064e3b", shape="circle", size_px=8),
                cq.LegendEntry("marker", "Escuelas IDE (367)", fill="#2563eb", stroke="#1e3a8a", shape="square", size_px=8),
                cq.LegendEntry("line", "Avenida mano única (IDE)", fill="#f97316", line_width=3.2),
                cq.LegendEntry("line", "Asfalto sobre empedrado", fill="#0d9488", line_width=2.0),
                cq.LegendEntry("line", "Ciclovía (IDE)", fill="#16a34a", line_width=2.2, dashed=True),
                cq.LegendEntry("line", "Calles OSM (1.286)", fill="#94a3b8", line_width=1.3),
                cq.LegendEntry("fill", "Delegación municipal (12)", fill="59,130,246,45", stroke="#1e3a8a", dashed=True),
            ],
            summary_title="Síntesis Urbana (Posadas)",
            summary_lines=[
                "• Incidentes: 12 reales / 1.417 sim.",
                "• 7 nodos de control (geom_m)",
                "• 280 semáforos · 367 escuelas IDE",
                "• 8 corredores mano única · 52 ciclovías",
                "• 613 obras asfalto s/empedrado",
            ],
            footer_left="Fuente: IDE Posadas (WFS) y OpenStreetMap en PostgreSQL/PostGIS (distancias métricas en EPSG:5348).",
        )
        print(f"[OK] {out_path.name}: {out_path.stat().st_size} bytes")
    finally:
        qgs.exitQgis()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "py"
    if mode == "py":
        prepare_ucp_logo()
        generate_clean_der()
    elif mode == "qgis":
        generate_clean_mapa02()
