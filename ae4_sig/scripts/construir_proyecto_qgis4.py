"""Construye el proyecto nativo QGIS 4.2.1 ('Belém do Pará') y renderiza 4 mapas temáticos.

Salidas generadas dentro de `ae4_sig/`:
  - `ae4_sig/qgis/proyecto_ae4.qgz`            (proyecto nativo QGIS 4.2.1 sin credenciales)
  - `ae4_sig/outputs/verificacion_qgis_4_2_1.txt` (comparación QGIS featureCount vs PostgreSQL)
  - `ae4_sig/outputs/mapas_qgis/mapa_01_regional_ign.png`
  - `ae4_sig/outputs/mapas_qgis/mapa_02_posadas_infraestructura_y_siniestros.png`
  - `ae4_sig/outputs/mapas_qgis/mapa_03_autoria1_escuelas_sin_semaforo.png`
  - `ae4_sig/outputs/mapas_qgis/mapa_04_autoria3_brecha_delegaciones.png`

Ejecución recomendada (PyQGIS 4.2.1 / PyQt6):
  & "C:\\Program Files\\QGIS 4.2.1\\bin\\python-qgis.bat" ae4_sig/scripts/construir_proyecto_qgis4.py
"""

from __future__ import annotations

import math
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# Headless safety: configurar offscreen y fuente TrueType antes de importar PyQt6 / PyQGIS
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.path.isdir(r"C:\Windows\Fonts"):
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import psycopg2  # noqa: E402
from qgis.PyQt.QtCore import QPointF, QRectF, QSize, Qt  # noqa: E402
from qgis.PyQt.QtGui import (  # noqa: E402
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPainter,
    QPen,
    QPolygonF,
)
from qgis.core import (  # noqa: E402
    Qgis,
    QgsApplication,
    QgsClassificationCustom,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDataSourceUri,
    QgsFillSymbol,
    QgsGraduatedSymbolRenderer,
    QgsLayerTreeGroup,
    QgsLineSymbol,
    QgsMapLayer,
    QgsMapRendererParallelJob,
    QgsMapSettings,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsReferencedRectangle,
    QgsRendererRange,
    QgsRuleBasedLabeling,
    QgsRuleBasedRenderer,
    QgsSingleSymbolRenderer,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
)


AE4_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = AE4_ROOT / ".env"
SQL_AUTORIA_PATH = AE4_ROOT / "sql" / "03_consultas_autoria.sql"
QGZ_PATH = AE4_ROOT / "qgis" / "proyecto_ae4.qgz"
VERIF_TXT_PATH = AE4_ROOT / "outputs" / "verificacion_qgis_4_2_1.txt"
MAPAS_DIR = AE4_ROOT / "outputs" / "mapas_qgis"

PROJECT_TITLE = "AE4 SIG — AITARA + IGN + IDE Posadas (QGIS 4.2.1)"
WMS_DATASOURCE = (
    "contextualWMSLegend=0"
    "&crs=EPSG:4326"
    "&dpiMode=7"
    "&format=image/png"
    "&layers=geonode:DELEGACIONES_MUNICIPALES_POSADAS_20250"
    "&styles"
    "&url=https://www.ide.posadas.gob.ar/geoserver/ows"
)

IMG_WIDTH = 1800
IMG_HEIGHT = 1150
MAP_RECT = QRectF(24, 102, 1360, 998)
SIDEBAR_RECT = QRectF(1402, 102, 374, 998)


# -----------------------------------------------------------------------------
# 1. Lectura de .env en memoria y extracción de consultas SQL de Autoría
# -----------------------------------------------------------------------------


def load_env_credentials(env_path: Path) -> Dict[str, str]:
    """Lee variables POSTGRES_* desde ae4_sig/.env estrictamente en memoria."""
    if not env_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo .env en {env_path}")

    creds: Dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        creds[key.strip()] = val.strip().strip('"').strip("'")

    required = ["POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]
    missing = [k for k in required if not creds.get(k)]
    if missing:
        raise KeyError(f"Faltan claves requeridas en {env_path}: {', '.join(missing)}")
    return creds


def extract_autoria_queries(sql_path: Path) -> Dict[str, str]:
    """Extrae exactamente las consultas SQL de Autoría 1, 2B y 3 desde 03_consultas_autoria.sql."""
    text = sql_path.read_text(encoding="utf-8")

    # Dividir por bloques iniciados en el encabezado "-- AUTORÍA ..."
    sections = re.split(r"(?=^-- AUTORÍA\s+[123]\b)", text, flags=re.MULTILINE)
    queries: Dict[str, str] = {}

    for sec in sections:
        header = sec.splitlines()[0] if sec.splitlines() else ""
        sql_lines = [ln for ln in sec.splitlines() if not ln.lstrip().startswith("--")]
        stmt = "\n".join(sql_lines).strip().rstrip(";").strip()
        if not stmt:
            continue

        if "AUTORÍA 1" in header:
            queries["autoria_1"] = stmt
        elif "Parte 2B" in header:
            queries["autoria_2b"] = stmt
        elif "AUTORÍA 3" in header:
            queries["autoria_3"] = stmt

    expected = {"autoria_1", "autoria_2b", "autoria_3"}
    if set(queries.keys()) != expected:
        raise RuntimeError(
            f"No se pudieron extraer todas las consultas de Autoría ({expected}); "
            f"encontradas: {set(queries.keys())}"
        )
    return queries


# -----------------------------------------------------------------------------
# 2. Helper PostGIS / QgsDataSourceUri
# -----------------------------------------------------------------------------


def _normalize_subquery(raw_subquery: str) -> str:
    """Normaliza una subconsulta SQL para el proveedor postgres de QGIS 4.2.1.

    El proveedor `postgres` de QGIS envuelve internamente `(SELECT ...)` con su
    propio alias (`AS "subQuery_0"`). Si se incluye un alias externo `AS q` o `;`
    final, el parser de QGIS marca la capa como inválida.
    """
    q = raw_subquery.strip().rstrip(";").strip()
    q = re.sub(r"\)\s+AS\s+[A-Za-z_][A-Za-z0-9_]*\s*$", ")", q, flags=re.IGNORECASE)
    if not (q.startswith("(") and q.endswith(")")):
        q = f"({q})"
    return q


def build_pg_layer_factory(
    creds: Dict[str, str],
) -> Callable[[str, str, str, str, str, Optional[Qgis.WkbType], str], QgsVectorLayer]:
    """Crea la función `make_pg_layer` vinculada a las credenciales en memoria."""

    def make_pg_layer(
        schema: str,
        table_or_subquery: str,
        geom_col: str,
        key_col: str,
        name: str,
        wkb_type: Optional[Qgis.WkbType] = None,
        srid: str = "4326",
    ) -> QgsVectorLayer:
        uri = QgsDataSourceUri()
        uri.setConnection(
            creds["POSTGRES_HOST"],
            creds["POSTGRES_PORT"],
            creds["POSTGRES_DB"],
            creds["POSTGRES_USER"],
            creds["POSTGRES_PASSWORD"],
        )
        source_target = _normalize_subquery(table_or_subquery) if schema == "" else table_or_subquery
        uri.setDataSource(schema, source_target, geom_col, "", key_col)
        if srid:
            uri.setSrid(str(srid))
        if wkb_type is not None:
            uri.setWkbType(wkb_type)

        layer = QgsVectorLayer(uri.uri(False), name, "postgres")
        assert layer.isValid(), (
            f"La capa PostGIS '{name}' es inválida: "
            f"{layer.dataProvider().error().message()}"
        )
        return layer

    return make_pg_layer


# -----------------------------------------------------------------------------
# 3. Simbología y etiquetado (PyQt6 / QGIS 4.2.1)
# -----------------------------------------------------------------------------


def _make_text_format(
    size_pt: float = 8.5,
    color: str = "#0f172a",
    weight: QFont.Weight = QFont.Weight.DemiBold,
    italic: bool = False,
    buffer_size_mm: float = 1.1,
    buffer_color: str = "#ffffff",
) -> QgsTextFormat:
    fmt = QgsTextFormat()
    font = QFont("Segoe UI")
    font.setPointSizeF(size_pt)
    font.setWeight(weight)
    font.setItalic(italic)
    fmt.setFont(font)
    fmt.setSize(size_pt)
    fmt.setColor(QColor(color))

    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSize(buffer_size_mm)
    buf.setColor(QColor(buffer_color))
    fmt.setBuffer(buf)
    return fmt


def apply_simple_labels(
    layer: QgsVectorLayer,
    field_or_expr: str,
    *,
    is_expression: bool = False,
    placement: QgsPalLayerSettings.Placement = QgsPalLayerSettings.Placement.OverPoint,
    dist_mm: float = 0.0,
    size_pt: float = 8.5,
    color: str = "#0f172a",
    weight: QFont.Weight = QFont.Weight.DemiBold,
    buffer_size_mm: float = 1.1,
    priority: int = 5,
) -> None:
    pal = QgsPalLayerSettings()
    pal.fieldName = field_or_expr
    pal.isExpression = is_expression
    pal.placement = placement
    pal.dist = dist_mm
    pal.priority = priority
    pal.setFormat(_make_text_format(size_pt=size_pt, color=color, weight=weight, buffer_size_mm=buffer_size_mm))
    layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    layer.setLabelsEnabled(True)


def apply_rule_labels(
    layer: QgsVectorLayer,
    rules_spec: Sequence[Tuple[str, str, str, bool, QgsPalLayerSettings.Placement, float, float, str, QFont.Weight, bool]],
    *,
    priority: int = 7,
    allow_overlap_if_required: bool = False,
) -> None:
    """Configura etiquetado por reglas (QgsRuleBasedLabeling)."""
    root = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())
    for label, expr, field_expr, is_expr, placement, dist_mm, size_pt, color, weight, italic in rules_spec:
        pal = QgsPalLayerSettings()
        pal.fieldName = field_expr
        pal.isExpression = is_expr
        pal.placement = placement
        pal.dist = dist_mm
        pal.priority = priority
        if allow_overlap_if_required:
            ps = pal.placementSettings()
            ps.setAllowDegradedPlacement(True)
            ps.setOverlapHandling(Qgis.LabelOverlapHandling.AllowOverlapIfRequired)
        pal.setFormat(
            _make_text_format(
                size_pt=size_pt,
                color=color,
                weight=weight,
                italic=italic,
                buffer_size_mm=1.2,
            )
        )
        root.appendChild(QgsRuleBasedLabeling.Rule(pal, 0, 0, expr, label))

    layer.setLabeling(QgsRuleBasedLabeling(root))
    layer.setLabelsEnabled(True)


def _rule_renderer(items: Sequence[Tuple[str, str, object]]) -> QgsRuleBasedRenderer:
    """Construye un QgsRuleBasedRenderer con regla raíz vacía para evitar doble dibujo."""
    root = QgsRuleBasedRenderer.Rule(None)
    for filter_expr, label, symbol in items:
        rule = QgsRuleBasedRenderer.Rule(symbol)
        if filter_expr != "ELSE":
            rule.setFilterExpression(filter_expr)
        else:
            rule.setIsElse(True)
        rule.setLabel(label)
        root.appendChild(rule)
    return QgsRuleBasedRenderer(root)


def style_layers(layers: Dict[str, QgsMapLayer]) -> None:
    """Aplica renderizadores y etiquetas temáticas a todas las capas del proyecto."""
    # --- Autoría 1 ---
    l_a1: QgsVectorLayer = layers["autoria_1"]  # type: ignore[assignment]
    l_a1.setRenderer(
        _rule_renderer(
            [
                (
                    "siniestros_corredor_250m_real > 0",
                    "Crítico: siniestro real en corredor <=250 m",
                    QgsMarkerSymbol.createSimple(
                        {
                            "name": "star",
                            "color": "220,38,38,255",
                            "outline_color": "127,29,29,255",
                            "outline_width": "0.45",
                            "size": "5.0",
                        }
                    ),
                ),
                (
                    "siniestros_corredor_250m_real = 0 AND siniestros_corredor_250m_simulado > 0",
                    "Alto: siniestro simulado en corredor <=250 m",
                    QgsMarkerSymbol.createSimple(
                        {
                            "name": "star",
                            "color": "234,88,12,255",
                            "outline_color": "124,45,18,255",
                            "outline_width": "0.4",
                            "size": "4.2",
                        }
                    ),
                ),
                (
                    "ELSE",
                    "Cruce escolar sin semáforo en av. mano única",
                    QgsMarkerSymbol.createSimple(
                        {
                            "name": "circle",
                            "color": "250,204,21,245",
                            "outline_color": "161,98,7,255",
                            "outline_width": "0.4",
                            "size": "2.4",
                        }
                    ),
                ),
            ]
        )
    )
    apply_rule_labels(
        l_a1,
        [
            (
                "Cruces con siniestros",
                "siniestros_corredor_250m_real > 0 OR siniestros_corredor_250m_simulado > 0",
                "replace(nombre, 'Avenida ', 'Av. ') || ' (' || siniestros_corredor_250m_real || 'R / ' || siniestros_corredor_250m_simulado || 'S)'",
                True,
                QgsPalLayerSettings.Placement.OrderedPositionsAroundPoint,
                2.2,
                7.2,
                "#7f1d1d",
                QFont.Weight.Bold,
                False,
            )
        ],
        priority=10,
        allow_overlap_if_required=True,
    )

    # --- Autoría 2B ---
    l_a2b: QgsVectorLayer = layers["autoria_2b"]  # type: ignore[assignment]
    l_a2b.setRenderer(
        _rule_renderer(
            [
                (
                    "tiene_asfalto_sobre_empedrado = true",
                    "Crítico con asfalto sobre empedrado (IDE)",
                    QgsLineSymbol.createSimple(
                        {
                            "color": "147,51,234,240",
                            "width": "1.25",
                            "line_style": "solid",
                            "capstyle": "round",
                            "joinstyle": "round",
                        }
                    ),
                ),
                (
                    "tiene_asfalto_sobre_empedrado = false",
                    "Crítico sin obra asfalto s/empedrado",
                    QgsLineSymbol.createSimple(
                        {
                            "color": "190,18,60,240",
                            "width": "1.25",
                            "line_style": "dash",
                            "capstyle": "round",
                            "joinstyle": "round",
                        }
                    ),
                ),
            ]
        )
    )

    # --- Autoría 3 (graduado manual sobre semaforos_cada_100_intersecciones) ---
    l_a3: QgsVectorLayer = layers["autoria_3"]  # type: ignore[assignment]
    ranges_spec = [
        (0.00, 0.50, "0.00 – 0.50 sem/100int (Déficit crítico)", "185,28,28,185", "127,29,29,255"),
        (0.50, 1.50, "0.50 – 1.50 sem/100int (Déficit alto)", "234,88,12,175", "154,52,18,255"),
        (1.50, 3.00, "1.50 – 3.00 sem/100int (Cobertura baja)", "245,158,11,165", "146,64,14,255"),
        (3.00, 5.00, "3.00 – 5.00 sem/100int (Cobertura media)", "59,130,246,155", "30,64,175,255"),
        (5.00, 50.00, "> 5.00 sem/100int (Concentración central)", "15,118,110,165", "17,94,89,255"),
    ]
    grad_ranges = []
    for lo, hi, lbl, fill_rgba, out_rgba in ranges_spec:
        sym = QgsFillSymbol.createSimple(
            {
                "color": fill_rgba,
                "outline_color": out_rgba,
                "outline_width": "0.65",
                "outline_style": "solid",
            }
        )
        grad_ranges.append(QgsRendererRange(lo, hi, sym, lbl))
    grad_renderer = QgsGraduatedSymbolRenderer("semaforos_cada_100_intersecciones", grad_ranges)
    grad_renderer.setClassificationMethod(QgsClassificationCustom())
    l_a3.setRenderer(grad_renderer)
    apply_simple_labels(
        l_a3,
        "nombre || '\\n' || format_number(semaforos_cada_100_intersecciones, 2) || ' sem/100int · ' || siniestros_real || ' real'",
        is_expression=True,
        placement=QgsPalLayerSettings.Placement.Horizontal,
        size_pt=8.0,
        color="#0f172a",
        weight=QFont.Weight.Bold,
        buffer_size_mm=1.3,
    )

    # --- incidentes_viales ---
    l_inc: QgsVectorLayer = layers["incidentes_viales"]  # type: ignore[assignment]
    l_inc.setRenderer(
        _rule_renderer(
            [
                (
                    "origen = 'real'",
                    "Real relevado (diamond 3.8 mm)",
                    QgsMarkerSymbol.createSimple(
                        {
                            "name": "diamond",
                            "color": "220,38,38,255",
                            "outline_color": "127,29,29,255",
                            "outline_width": "0.5",
                            "size": "3.8",
                        }
                    ),
                ),
                (
                    "origen = 'simulado' AND severidad = 3",
                    "Simulado AITARA · Severidad 3",
                    QgsMarkerSymbol.createSimple(
                        {
                            "name": "circle",
                            "color": "234,88,12,240",
                            "outline_color": "154,52,18,255",
                            "outline_width": "0.35",
                            "size": "2.8",
                        }
                    ),
                ),
                (
                    "origen = 'simulado' AND severidad = 2",
                    "Simulado AITARA · Severidad 2",
                    QgsMarkerSymbol.createSimple(
                        {
                            "name": "circle",
                            "color": "245,158,11,220",
                            "outline_color": "146,64,14,255",
                            "outline_width": "0.3",
                            "size": "2.1",
                        }
                    ),
                ),
                (
                    "origen = 'simulado' AND severidad = 1",
                    "Simulado AITARA · Severidad 1",
                    QgsMarkerSymbol.createSimple(
                        {
                            "name": "circle",
                            "color": "251,191,36,185",
                            "outline_color": "180,83,9,220",
                            "outline_width": "0.2",
                            "size": "1.5",
                        }
                    ),
                ),
            ]
        )
    )

    # --- nodos_referencia_aitara ---
    l_nodos: QgsVectorLayer = layers["nodos_referencia_aitara"]  # type: ignore[assignment]
    l_nodos.setRenderer(
        _rule_renderer(
            [
                (
                    "nivel_drenaje = 'BAJO'",
                    "Drenaje BAJO (crítico)",
                    QgsMarkerSymbol.createSimple(
                        {
                            "name": "pentagon",
                            "color": "190,18,60,255",
                            "outline_color": "255,255,255,255",
                            "outline_width": "0.55",
                            "size": "4.2",
                        }
                    ),
                ),
                (
                    "nivel_drenaje = 'MEDIO'",
                    "Drenaje MEDIO",
                    QgsMarkerSymbol.createSimple(
                        {
                            "name": "pentagon",
                            "color": "147,51,234,255",
                            "outline_color": "255,255,255,255",
                            "outline_width": "0.55",
                            "size": "4.0",
                        }
                    ),
                ),
                (
                    "nivel_drenaje = 'ALTO'",
                    "Drenaje ALTO",
                    QgsMarkerSymbol.createSimple(
                        {
                            "name": "pentagon",
                            "color": "2,132,199,255",
                            "outline_color": "255,255,255,255",
                            "outline_width": "0.55",
                            "size": "4.0",
                        }
                    ),
                ),
            ]
        )
    )
    apply_simple_labels(
        l_nodos,
        "replace(nombre, ' y ', '\\ny ') || '\\n[' || nivel_drenaje || ']'",
        is_expression=True,
        placement=QgsPalLayerSettings.Placement.OrderedPositionsAroundPoint,
        dist_mm=2.4,
        size_pt=7.8,
        color="#4c0519",
        weight=QFont.Weight.Bold,
        buffer_size_mm=1.2,
        priority=9,
    )

    # --- Capas urbanas simples ---
    layers["semaforos"].setRenderer(  # type: ignore[union-attr]
        QgsSingleSymbolRenderer(
            QgsMarkerSymbol.createSimple(
                {
                    "name": "circle",
                    "color": "16,185,129,245",
                    "outline_color": "6,78,59,255",
                    "outline_width": "0.35",
                    "size": "2.0",
                }
            )
        )
    )
    layers["escuelas"].setRenderer(  # type: ignore[union-attr]
        QgsSingleSymbolRenderer(
            QgsMarkerSymbol.createSimple(
                {
                    "name": "square",
                    "color": "37,99,235,245",
                    "outline_color": "30,58,138,255",
                    "outline_width": "0.35",
                    "size": "2.2",
                }
            )
        )
    )
    layers["paradas"].setRenderer(  # type: ignore[union-attr]
        QgsSingleSymbolRenderer(
            QgsMarkerSymbol.createSimple(
                {
                    "name": "triangle",
                    "color": "147,51,234,225",
                    "outline_color": "88,28,135,255",
                    "outline_width": "0.3",
                    "size": "1.7",
                }
            )
        )
    )
    layers["intersecciones"].setRenderer(  # type: ignore[union-attr]
        QgsSingleSymbolRenderer(
            QgsMarkerSymbol.createSimple(
                {
                    "name": "circle",
                    "color": "100,116,139,170",
                    "outline_color": "71,85,105,200",
                    "outline_width": "0.15",
                    "size": "1.0",
                }
            )
        )
    )
    layers["avenidas_mano_unica"].setRenderer(  # type: ignore[union-attr]
        QgsSingleSymbolRenderer(
            QgsLineSymbol.createSimple(
                {
                    "color": "249,115,22,245",
                    "width": "0.9",
                    "line_style": "solid",
                    "capstyle": "round",
                    "joinstyle": "round",
                }
            )
        )
    )
    layers["asfalto_sobre_empedrado"].setRenderer(  # type: ignore[union-attr]
        QgsSingleSymbolRenderer(
            QgsLineSymbol.createSimple(
                {
                    "color": "13,148,136,230",
                    "width": "0.55",
                    "line_style": "solid",
                    "capstyle": "round",
                    "joinstyle": "round",
                }
            )
        )
    )
    layers["ciclovias"].setRenderer(  # type: ignore[union-attr]
        QgsSingleSymbolRenderer(
            QgsLineSymbol.createSimple(
                {
                    "color": "22,163,74,235",
                    "width": "0.65",
                    "line_style": "dash",
                    "capstyle": "round",
                    "joinstyle": "round",
                }
            )
        )
    )
    layers["calles"].setRenderer(  # type: ignore[union-attr]
        QgsSingleSymbolRenderer(
            QgsLineSymbol.createSimple(
                {
                    "color": "148,163,184,185",
                    "width": "0.3",
                    "line_style": "solid",
                    "capstyle": "round",
                    "joinstyle": "round",
                }
            )
        )
    )

    l_del: QgsVectorLayer = layers["delegaciones"]  # type: ignore[assignment]
    l_del.setRenderer(
        QgsSingleSymbolRenderer(
            QgsFillSymbol.createSimple(
                {
                    "color": "59,130,246,35",
                    "outline_color": "30,58,138,235",
                    "outline_width": "0.7",
                    "outline_style": "dash",
                }
            )
        )
    )
    apply_simple_labels(
        l_del,
        "nombre",
        is_expression=False,
        placement=QgsPalLayerSettings.Placement.Horizontal,
        size_pt=8.5,
        color="#1e3a8a",
        weight=QFont.Weight.DemiBold,
        buffer_size_mm=1.1,
        priority=3,
    )

    # --- Capas Regionales (IGN) ---
    l_loc: QgsVectorLayer = layers["localidades"]  # type: ignore[assignment]
    l_loc.setRenderer(
        _rule_renderer(
            [
                (
                    "es_capital_nacional = true",
                    "Capital Nacional",
                    QgsMarkerSymbol.createSimple(
                        {
                            "name": "star",
                            "color": "220,38,38,255",
                            "outline_color": "127,29,29,255",
                            "outline_width": "0.45",
                            "size": "4.8",
                        }
                    ),
                ),
                (
                    "es_capital_provincial = true",
                    "Capital Provincial",
                    QgsMarkerSymbol.createSimple(
                        {
                            "name": "star",
                            "color": "225,29,72,255",
                            "outline_color": "136,19,55,255",
                            "outline_width": "0.4",
                            "size": "3.8",
                        }
                    ),
                ),
                (
                    "ELSE",
                    "Localidad IGN-BAHRA",
                    QgsMarkerSymbol.createSimple(
                        {
                            "name": "circle",
                            "color": "100,116,139,115",
                            "outline_color": "71,85,105,130",
                            "outline_width": "0.0",
                            "size": "0.9",
                        }
                    ),
                ),
            ]
        )
    )
    apply_rule_labels(
        l_loc,
        [
            (
                "Capitales",
                "es_capital_nacional OR es_capital_provincial",
                "nombre",
                False,
                QgsPalLayerSettings.Placement.OrderedPositionsAroundPoint,
                1.8,
                9.0,
                "#0f172a",
                QFont.Weight.Bold,
                False,
            )
        ],
    )

    layers["rutas"].setRenderer(  # type: ignore[union-attr]
        _rule_renderer(
            [
                (
                    "jurisdiccion = 'nacional'",
                    "Ruta Nacional",
                    QgsLineSymbol.createSimple(
                        {
                            "color": "220,38,38,235",
                            "width": "0.7",
                            "line_style": "solid",
                            "capstyle": "round",
                            "joinstyle": "round",
                        }
                    ),
                ),
                (
                    "jurisdiccion = 'provincial'",
                    "Ruta Provincial",
                    QgsLineSymbol.createSimple(
                        {
                            "color": "217,119,6,210",
                            "width": "0.4",
                            "line_style": "solid",
                            "capstyle": "round",
                            "joinstyle": "round",
                        }
                    ),
                ),
            ]
        )
    )

    l_agua: QgsVectorLayer = layers["cursos_agua"]  # type: ignore[assignment]
    l_agua.setRenderer(
        _rule_renderer(
            [
                (
                    "es_principal = true",
                    "Curso principal (Paraná / Uruguay / Iguazú)",
                    QgsLineSymbol.createSimple(
                        {
                            "color": "29,78,216,240",
                            "width": "1.0",
                            "line_style": "solid",
                            "capstyle": "round",
                            "joinstyle": "round",
                        }
                    ),
                ),
                (
                    "es_principal = false",
                    "Afluente / arroyo",
                    QgsLineSymbol.createSimple(
                        {
                            "color": "96,165,250,200",
                            "width": "0.35",
                            "line_style": "solid",
                            "capstyle": "round",
                            "joinstyle": "round",
                        }
                    ),
                ),
            ]
        )
    )
    apply_rule_labels(
        l_agua,
        [
            (
                "Ríos principales",
                "es_principal = true",
                "nombre",
                False,
                QgsPalLayerSettings.Placement.Curved,
                1.0,
                8.5,
                "#1e40af",
                QFont.Weight.DemiBold,
                True,
            )
        ],
    )

    layers["departamentos"].setRenderer(  # type: ignore[union-attr]
        QgsSingleSymbolRenderer(
            QgsFillSymbol.createSimple(
                {
                    "color": "255,255,255,0",
                    "outline_color": "148,163,184,180",
                    "outline_width": "0.3",
                    "outline_style": "dash",
                }
            )
        )
    )

    l_prov: QgsVectorLayer = layers["provincias"]  # type: ignore[assignment]
    l_prov.setRenderer(
        _rule_renderer(
            [
                (
                    "nombre = 'Misiones'",
                    "Provincia de Misiones (área de estudio)",
                    QgsFillSymbol.createSimple(
                        {
                            "color": "254,243,199,185",
                            "outline_color": "180,83,9,240",
                            "outline_width": "0.85",
                            "outline_style": "solid",
                        }
                    ),
                ),
                (
                    "ELSE",
                    "Otras provincias argentinas",
                    QgsFillSymbol.createSimple(
                        {
                            "color": "248,250,252,195",
                            "outline_color": "71,85,105,220",
                            "outline_width": "0.55",
                            "outline_style": "solid",
                        }
                    ),
                ),
            ]
        )
    )
    apply_rule_labels(
        l_prov,
        [
            (
                "Provincias NEA",
                "nombre IN ('Misiones', 'Corrientes', 'Entre Ríos', 'Chaco', 'Formosa', 'Santa Fe')",
                "upper(nombre)",
                True,
                QgsPalLayerSettings.Placement.Horizontal,
                0.0,
                8.0,
                "#475569",
                QFont.Weight.DemiBold,
                False,
            )
        ],
    )

    l_pais: QgsVectorLayer = layers["paises"]  # type: ignore[assignment]
    l_pais.setRenderer(
        QgsSingleSymbolRenderer(
            QgsFillSymbol.createSimple(
                {
                    "color": "229,224,213,180",
                    "outline_color": "51,65,85,255",
                    "outline_width": "0.85",
                    "outline_style": "solid",
                }
            )
        )
    )
    apply_rule_labels(
        l_pais,
        [
            (
                "Países limítrofes",
                "codigo_iso3 <> 'ARG'",
                "upper(nombre)",
                True,
                QgsPalLayerSettings.Placement.Horizontal,
                0.0,
                9.5,
                "#334155",
                QFont.Weight.Bold,
                False,
            )
        ],
    )


# -----------------------------------------------------------------------------
# 4. Construcción de proyecto, árbol de capas y verificación PostgreSQL
# -----------------------------------------------------------------------------


@dataclass
class LayerMeta:
    key: str
    display_name: str
    kind: str  # "table" | "subquery" | "wms"
    pg_target: str
    checked: bool


def build_project_and_layers(
    creds: Dict[str, str],
    autoria_sql: Dict[str, str],
) -> Tuple[QgsProject, Dict[str, QgsMapLayer], List[LayerMeta]]:
    """Configura QgsProject.instance(), carga todas las capas y arma los grupos."""
    proj = QgsProject.instance()
    proj.clear()
    proj.setTitle(PROJECT_TITLE)
    crs_5348 = QgsCoordinateReferenceSystem("EPSG:5348")
    proj.setCrs(crs_5348)
    proj.viewSettings().setDefaultViewExtent(
        QgsReferencedRectangle(QgsRectangle(6600800.0, 6964000.0, 6612400.0, 6975400.0), crs_5348)
    )

    make_pg_layer = build_pg_layer_factory(creds)

    # Definición ordenada de capas
    autoria_specs = [
        ("autoria_1", "Autoría 1 — Escuelas sin semáforo", autoria_sql["autoria_1"], Qgis.WkbType.Point, True),
        ("autoria_2b", "Autoría 2B — Tramos críticos por lluvia", autoria_sql["autoria_2b"], Qgis.WkbType.MultiLineString, False),
        ("autoria_3", "Autoría 3 — Brecha por delegación", autoria_sql["autoria_3"], Qgis.WkbType.MultiPolygon, False),
    ]
    urban_specs = [
        ("incidentes_viales", "incidentes_viales", Qgis.WkbType.Point, True),
        ("nodos_referencia_aitara", "nodos_referencia_aitara", Qgis.WkbType.Point, True),
        ("semaforos", "semaforos", Qgis.WkbType.Point, True),
        ("escuelas", "escuelas", Qgis.WkbType.Point, True),
        ("paradas", "paradas", Qgis.WkbType.Point, False),
        ("intersecciones", "intersecciones", Qgis.WkbType.Point, False),
        ("avenidas_mano_unica", "avenidas_mano_unica", Qgis.WkbType.MultiLineString, True),
        ("asfalto_sobre_empedrado", "asfalto_sobre_empedrado", Qgis.WkbType.MultiLineString, False),
        ("ciclovias", "ciclovias", Qgis.WkbType.MultiLineString, False),
        ("calles", "calles", Qgis.WkbType.MultiLineString, True),
        ("delegaciones", "delegaciones", Qgis.WkbType.MultiPolygon, True),
    ]
    regional_specs = [
        ("localidades", "localidades", Qgis.WkbType.Point, False),
        ("rutas", "rutas", Qgis.WkbType.MultiLineString, False),
        ("cursos_agua", "cursos_agua", Qgis.WkbType.MultiLineString, False),
        ("departamentos", "departamentos", Qgis.WkbType.MultiPolygon, False),
        ("provincias", "provincias", Qgis.WkbType.MultiPolygon, False),
        ("paises", "paises", Qgis.WkbType.MultiPolygon, False),
    ]

    layers: Dict[str, QgsMapLayer] = {}
    metas: List[LayerMeta] = []

    root = proj.layerTreeRoot()
    grp_posadas: QgsLayerTreeGroup = root.addGroup("Posadas (IDE + OSM + AITARA)")
    grp_posadas.setItemVisibilityChecked(True)
    grp_posadas.setExpanded(True)

    grp_autoria: QgsLayerTreeGroup = grp_posadas.addGroup("Consultas de Autoría (DB Manager / SQL)")
    grp_autoria.setItemVisibilityChecked(True)
    grp_autoria.setExpanded(True)

    for key, display_name, sql_text, wkb_t, checked in autoria_specs:
        lyr = make_pg_layer("", sql_text, "geom", "id", display_name, wkb_t, "4326")
        proj.addMapLayer(lyr, False)
        node = grp_autoria.addLayer(lyr)
        node.setItemVisibilityChecked(checked)
        layers[key] = lyr
        metas.append(LayerMeta(key=key, display_name=display_name, kind="subquery", pg_target=sql_text, checked=checked))

    for tbl, display_name, wkb_t, checked in urban_specs:
        lyr = make_pg_layer("sig_ae4", tbl, "geom", "id", display_name, wkb_t, "4326")
        proj.addMapLayer(lyr, False)
        node = grp_posadas.addLayer(lyr)
        node.setItemVisibilityChecked(checked)
        layers[tbl] = lyr
        metas.append(LayerMeta(key=tbl, display_name=display_name, kind="table", pg_target=f"sig_ae4.{tbl}", checked=checked))

    wms_name = "IDE Posadas — Delegaciones (WMS)"
    wms_layer = QgsRasterLayer(WMS_DATASOURCE, wms_name, "wms")
    assert wms_layer.isValid(), f"La capa WMS '{wms_name}' es inválida: {wms_layer.error().message()}"
    wms_layer.setOpacity(0.65)
    proj.addMapLayer(wms_layer, False)
    wms_node = grp_posadas.addLayer(wms_layer)
    wms_node.setItemVisibilityChecked(False)
    layers["wms_delegaciones"] = wms_layer
    metas.append(LayerMeta(key="wms_delegaciones", display_name=wms_name, kind="wms", pg_target=WMS_DATASOURCE, checked=False))

    grp_regional: QgsLayerTreeGroup = root.addGroup("Regional (IGN)")
    grp_regional.setItemVisibilityChecked(False)
    grp_regional.setExpanded(False)

    for tbl, display_name, wkb_t, checked in regional_specs:
        lyr = make_pg_layer("sig_ae4", tbl, "geom", "id", display_name, wkb_t, "4326")
        proj.addMapLayer(lyr, False)
        node = grp_regional.addLayer(lyr)
        node.setItemVisibilityChecked(checked)
        layers[tbl] = lyr
        metas.append(LayerMeta(key=tbl, display_name=display_name, kind="table", pg_target=f"sig_ae4.{tbl}", checked=checked))

    style_layers(layers)
    return proj, layers, metas


def verify_counts_against_postgres(
    creds: Dict[str, str],
    layers: Dict[str, QgsMapLayer],
    metas: Sequence[LayerMeta],
) -> Tuple[List[Dict[str, object]], bool]:
    """Compara featureCount() de QGIS 4.2.1 contra PostgreSQL para todas las capas."""
    conn = psycopg2.connect(
        host=creds["POSTGRES_HOST"],
        port=int(creds["POSTGRES_PORT"]),
        dbname=creds["POSTGRES_DB"],
        user=creds["POSTGRES_USER"],
        password=creds["POSTGRES_PASSWORD"],
    )
    rows: List[Dict[str, object]] = []
    all_ok = True
    try:
        with conn.cursor() as cur:
            for meta in metas:
                lyr = layers[meta.key]
                is_valid = bool(lyr.isValid())
                if meta.kind == "wms":
                    match = is_valid
                    if not match:
                        all_ok = False
                    rows.append(
                        {
                            "layer": meta.display_name,
                            "kind": "WMS",
                            "valid": is_valid,
                            "qgis_count": "N/A",
                            "postgres_count": "N/A",
                            "match": match,
                        }
                    )
                    continue

                vlyr: QgsVectorLayer = lyr  # type: ignore[assignment]
                qgis_count = int(vlyr.featureCount())
                if meta.kind == "table":
                    cur.execute(f"SELECT COUNT(*) FROM {meta.pg_target};")
                else:
                    cur.execute(f"SELECT COUNT(*) FROM ({meta.pg_target}) AS q;")
                pg_count = int(cur.fetchone()[0])
                match = is_valid and (qgis_count == pg_count)
                if not match:
                    all_ok = False
                rows.append(
                    {
                        "layer": meta.display_name,
                        "kind": "SQL" if meta.kind == "subquery" else "PostGIS",
                        "valid": is_valid,
                        "qgis_count": qgis_count,
                        "postgres_count": pg_count,
                        "match": match,
                    }
                )
    finally:
        conn.close()
    return rows, all_ok


# -----------------------------------------------------------------------------
# 5. Renderizado de mapas temáticos (QgsMapRendererParallelJob + QPainter)
# -----------------------------------------------------------------------------


@dataclass
class LegendEntry:
    kind: str  # "marker" | "line" | "fill" | "section"
    label: str
    fill: str = "#64748b"
    stroke: str = "#0f172a"
    shape: str = "circle"  # circle | diamond | square | triangle | star | pentagon
    size_px: float = 10.0
    line_width: float = 2.5
    dashed: bool = False


def _draw_star(painter: QPainter, cx: float, cy: float, r_outer: float) -> None:
    r_inner = r_outer * 0.44
    pts: List[QPointF] = []
    for idx in range(10):
        angle = math.radians(-90 + idx * 36)
        r = r_outer if idx % 2 == 0 else r_inner
        pts.append(QPointF(cx + r * math.cos(angle), cy + r * math.sin(angle)))
    painter.drawPolygon(QPolygonF(pts))


def _draw_pentagon(painter: QPainter, cx: float, cy: float, r: float) -> None:
    pts = [
        QPointF(cx + r * math.cos(math.radians(-90 + i * 72)), cy + r * math.sin(math.radians(-90 + i * 72)))
        for i in range(5)
    ]
    painter.drawPolygon(QPolygonF(pts))


def _parse_qcolor(spec: str) -> QColor:
    """Convierte '#RRGGBB' o 'r,g,b[,a]' a QColor sin ambigüedad #AARRGGBB."""
    s = spec.strip()
    if "," in s:
        parts = [int(p.strip()) for p in s.split(",")]
        return QColor(*parts)
    return QColor(s)


def _draw_legend_symbol(painter: QPainter, entry: LegendEntry, x: float, cy: float) -> None:
    painter.save()
    if entry.kind == "marker":
        painter.setBrush(_parse_qcolor(entry.fill))
        painter.setPen(QPen(_parse_qcolor(entry.stroke), 1.4))
        r = entry.size_px / 2.0
        if entry.shape == "circle":
            painter.drawEllipse(QPointF(x + 12, cy), r, r)
        elif entry.shape == "square":
            painter.drawRect(QRectF(x + 12 - r, cy - r, 2 * r, 2 * r))
        elif entry.shape == "diamond":
            poly = QPolygonF(
                [QPointF(x + 12, cy - r - 1), QPointF(x + 12 + r + 1, cy), QPointF(x + 12, cy + r + 1), QPointF(x + 12 - r - 1, cy)]
            )
            painter.drawPolygon(poly)
        elif entry.shape == "triangle":
            poly = QPolygonF(
                [QPointF(x + 12, cy - r - 1), QPointF(x + 12 + r + 1, cy + r), QPointF(x + 12 - r - 1, cy + r)]
            )
            painter.drawPolygon(poly)
        elif entry.shape == "star":
            _draw_star(painter, x + 12, cy, r + 1.5)
        elif entry.shape == "pentagon":
            _draw_pentagon(painter, x + 12, cy, r + 1.0)
    elif entry.kind == "line":
        pen = QPen(_parse_qcolor(entry.fill), entry.line_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        if entry.dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(x + 2, cy), QPointF(x + 23, cy))
    elif entry.kind == "fill":
        painter.setBrush(_parse_qcolor(entry.fill))
        pen = QPen(_parse_qcolor(entry.stroke), 1.6)
        if entry.dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRect(QRectF(x + 2, cy - 6, 20, 12))
    painter.restore()


def _make_font(
    size_pt: float,
    weight: QFont.Weight = QFont.Weight.Normal,
    italic: bool = False,
) -> QFont:
    font = QFont("Segoe UI")
    font.setPointSizeF(size_pt)
    font.setWeight(weight)
    font.setItalic(italic)
    return font


def _draw_north_arrow(painter: QPainter, cx: float, cy: float) -> None:
    painter.save()
    painter.setBrush(QColor("#ffffff"))
    painter.setPen(QPen(QColor("#cbd5e1"), 1.2))
    painter.drawEllipse(QPointF(cx, cy), 22, 22)

    left_wing = QPolygonF([QPointF(cx, cy - 15), QPointF(cx - 7, cy + 8), QPointF(cx, cy + 3)])
    right_wing = QPolygonF([QPointF(cx, cy - 15), QPointF(cx + 7, cy + 8), QPointF(cx, cy + 3)])
    painter.setPen(QPen(QColor("#0f172a"), 1.0))
    painter.setBrush(QColor("#0f172a"))
    painter.drawPolygon(left_wing)
    painter.setBrush(QColor("#f8fafc"))
    painter.drawPolygon(right_wing)

    painter.setFont(_make_font(8.0, QFont.Weight.Bold))
    painter.setPen(QColor("#0f172a"))
    painter.drawText(QRectF(cx - 12, cy + 7, 24, 14), Qt.AlignmentFlag.AlignCenter, "N")
    painter.restore()


def _pick_scale_bar(visible_extent: QgsRectangle, map_width_px: float, crs_authid: str) -> Tuple[float, str]:
    """Calcula la longitud en px y etiqueta exacta de una barra de escala legible."""
    if crs_authid == "EPSG:4326":
        lat_mid = (visible_extent.yMinimum() + visible_extent.yMaximum()) / 2.0
        meters_per_deg = 111320.0 * math.cos(math.radians(lat_mid))
        total_meters = visible_extent.width() * meters_per_deg
        candidates_m = [50000, 100000, 150000, 200000, 250000, 300000]
    else:
        total_meters = visible_extent.width()
        candidates_m = [500, 1000, 1500, 2000, 3000, 4000, 5000]

    px_per_meter = map_width_px / total_meters
    chosen_m = candidates_m[0]
    for cand in candidates_m:
        px = cand * px_per_meter
        if 120 <= px <= 230:
            chosen_m = cand
            break
        if px < 250:
            chosen_m = cand

    bar_px = chosen_m * px_per_meter
    label = f"{int(chosen_m / 1000)} km" if chosen_m >= 1000 else f"{int(chosen_m)} m"
    if crs_authid == "EPSG:4326":
        label = f"{label} (lat. media)"
    return bar_px, label


def _draw_scale_bar(
    painter: QPainter,
    x: float,
    y: float,
    bar_px: float,
    label_end: str,
) -> None:
    painter.save()
    font = _make_font(8.0, QFont.Weight.DemiBold)
    lbl_w = QFontMetricsF(font).horizontalAdvance(label_end)
    box_w = max(bar_px + 34, bar_px - 10 + lbl_w + 26)
    painter.setBrush(QColor(255, 255, 255, 236))
    painter.setPen(QPen(QColor("#cbd5e1"), 1.1))
    painter.drawRoundedRect(QRectF(x - 10, y - 20, box_w, 40), 5, 5)

    seg = bar_px / 4.0
    for idx in range(4):
        painter.setBrush(QColor("#0f172a") if idx % 2 == 0 else QColor("#ffffff"))
        painter.setPen(QPen(QColor("#0f172a"), 1.0))
        painter.drawRect(QRectF(x + idx * seg, y, seg, 7))

    painter.setFont(font)
    painter.setPen(QColor("#0f172a"))
    painter.drawText(QRectF(x - 4, y - 16, 24, 14), Qt.AlignmentFlag.AlignLeft, "0")
    painter.drawText(QRectF(x + bar_px - 14, y - 16, lbl_w + 24, 14), Qt.AlignmentFlag.AlignLeft, label_end)
    painter.restore()


def render_thematic_map(
    out_path: Path,
    *,
    title: str,
    subtitle: str,
    crs_authid: str,
    extent: QgsRectangle,
    render_layers: Sequence[QgsMapLayer],
    background_hex: str,
    legend_entries: Sequence[LegendEntry],
    summary_title: str,
    summary_lines: Sequence[str],
    footer_left: str,
) -> None:
    """Renderiza una imagen PNG de 1800x1150 px usando QgsMapRendererParallelJob y QPainter."""
    map_w = int(MAP_RECT.width())
    map_h = int(MAP_RECT.height())

    settings = QgsMapSettings()
    settings.setDestinationCrs(QgsCoordinateReferenceSystem(crs_authid))
    settings.setOutputSize(QSize(map_w, map_h))
    settings.setOutputDpi(110)
    settings.setBackgroundColor(QColor(background_hex))
    settings.setLayers(list(render_layers))
    settings.setExtent(extent)

    job = QgsMapRendererParallelJob(settings)
    job.start()
    job.waitForFinished()
    map_img = job.renderedImage()
    if map_img.isNull():
        raise RuntimeError(f"QgsMapRendererParallelJob devolvió imagen nula para {out_path.name}")

    canvas = QImage(IMG_WIDTH, IMG_HEIGHT, QImage.Format.Format_ARGB32_Premultiplied)
    canvas.fill(QColor("#ffffff"))

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    # --- Encabezado ---
    painter.setPen(QColor("#1d4ed8"))
    painter.setFont(_make_font(9.0, QFont.Weight.Bold))
    painter.drawText(
        QRectF(24, 14, 900, 20),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        "AE4 SIG · QGIS 4.2.1 'Belém do Pará'",
    )

    painter.setPen(QColor("#0f172a"))
    painter.setFont(_make_font(17.0, QFont.Weight.Bold))
    painter.drawText(QRectF(24, 34, 1340, 32), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

    painter.setPen(QColor("#475569"))
    painter.setFont(_make_font(9.0, QFont.Weight.Normal))
    painter.drawText(QRectF(24, 67, 1360, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, subtitle)

    # Etiqueta CRS derecha superior
    pill_rect = QRectF(1402, 24, 374, 52)
    painter.setBrush(QColor("#eff6ff"))
    painter.setPen(QPen(QColor("#bfdbfe"), 1.2))
    painter.drawRoundedRect(pill_rect, 6, 6)
    painter.setPen(QColor("#1e3a8a"))
    painter.setFont(_make_font(9.0, QFont.Weight.Bold))
    crs_desc = "EPSG:5348 · POSGAR 2007 / Argentina 6 (m)" if crs_authid == "EPSG:5348" else "EPSG:4326 · WGS84 Geográfico (°)"
    painter.drawText(QRectF(1414, 30, 350, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"SRC: {crs_desc}")
    vis_ext = settings.visibleExtent()
    painter.setPen(QColor("#334155"))
    painter.setFont(_make_font(8.0, QFont.Weight.Normal))
    ext_txt = (
        f"Ext: [{vis_ext.xMinimum():.2f}, {vis_ext.yMinimum():.2f}] – [{vis_ext.xMaximum():.2f}, {vis_ext.yMaximum():.2f}]"
        if crs_authid == "EPSG:4326"
        else f"Ext (m): [{vis_ext.xMinimum():,.0f}, {vis_ext.yMinimum():,.0f}] – [{vis_ext.xMaximum():,.0f}, {vis_ext.yMaximum():,.0f}]"
    )
    painter.drawText(QRectF(1414, 51, 350, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, ext_txt)

    painter.setPen(QPen(QColor("#e2e8f0"), 1.5))
    painter.drawLine(QPointF(24, 92), QPointF(1776, 92))

    # --- Lienzo del mapa ---
    painter.drawImage(MAP_RECT.topLeft(), map_img)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor("#64748b"), 1.6))
    painter.drawRect(MAP_RECT)

    # Rosa de los vientos y barra de escala sobre el borde inferior/superior del mapa
    _draw_north_arrow(painter, MAP_RECT.right() - 38, MAP_RECT.top() + 38)
    bar_px, bar_label = _pick_scale_bar(vis_ext, map_w, crs_authid)
    _draw_scale_bar(painter, MAP_RECT.left() + 24, MAP_RECT.bottom() - 34, bar_px, bar_label)

    # --- Panel lateral de leyenda y síntesis ---
    painter.setBrush(QColor("#f8fafc"))
    painter.setPen(QPen(QColor("#cbd5e1"), 1.3))
    painter.drawRoundedRect(SIDEBAR_RECT, 8, 8)

    sx = SIDEBAR_RECT.left() + 18
    sy = SIDEBAR_RECT.top() + 18
    sw = SIDEBAR_RECT.width() - 36

    painter.setPen(QColor("#0f172a"))
    painter.setFont(_make_font(11.0, QFont.Weight.Bold))
    painter.drawText(QRectF(sx, sy, sw, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "LEYENDA CARTOGRÁFICA")
    sy += 28
    painter.setPen(QPen(QColor("#cbd5e1"), 1.0))
    painter.drawLine(QPointF(sx, sy), QPointF(sx + sw, sy))
    sy += 12

    for entry in legend_entries:
        if entry.kind == "section":
            sy += 4
            painter.setPen(QColor("#1e3a8a"))
            painter.setFont(_make_font(8.5, QFont.Weight.Bold))
            painter.drawText(QRectF(sx, sy, sw, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, entry.label)
            sy += 22
        else:
            _draw_legend_symbol(painter, entry, sx, sy + 11)
            painter.setPen(QColor("#1e293b"))
            painter.setFont(_make_font(8.5, QFont.Weight.Normal))
            painter.drawText(QRectF(sx + 32, sy, sw - 32, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, entry.label)
            sy += 24

    # Bloque inferior de hallazgos / métricas verificadas
    summary_h = 34 + len(summary_lines) * 22 + 16
    box_top = max(sy + 14, SIDEBAR_RECT.bottom() - summary_h - 16)
    summary_rect = QRectF(sx, box_top, sw, SIDEBAR_RECT.bottom() - box_top - 16)
    painter.setBrush(QColor("#ffffff"))
    painter.setPen(QPen(QColor("#cbd5e1"), 1.1))
    painter.drawRoundedRect(summary_rect, 6, 6)

    painter.setPen(QColor("#0f172a"))
    painter.setFont(_make_font(9.5, QFont.Weight.Bold))
    painter.drawText(
        QRectF(sx + 12, box_top + 10, sw - 24, 20),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        summary_title,
    )
    ly = box_top + 36
    painter.setPen(QColor("#334155"))
    painter.setFont(_make_font(8.3, QFont.Weight.Normal))
    for line in summary_lines:
        painter.drawText(
            QRectF(sx + 12, ly, sw - 24, 21),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            line,
        )
        ly += 21

    # --- Pie de página ---
    painter.setPen(QColor("#64748b"))
    painter.setFont(_make_font(8.5, QFont.Weight.Normal))
    painter.drawText(QRectF(24, 1110, 1250, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, footer_left)
    painter.drawText(
        QRectF(1280, 1110, 496, 24),
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        "Proyecto: ae4_sig/qgis/proyecto_ae4.qgz · PyQGIS 4.2.1",
    )

    painter.end()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not canvas.save(str(out_path), "PNG"):
        raise RuntimeError(f"No se pudo guardar la imagen PNG: {out_path}")


def render_all_maps(
    layers: Dict[str, QgsMapLayer],
    creds: Dict[str, str],
) -> List[Path]:
    """Genera los 4 mapas temáticos PNG en ae4_sig/outputs/mapas_qgis/."""
    MAPAS_DIR.mkdir(parents=True, exist_ok=True)

    # Consultar métricas exactas en vivo para paneles laterales
    conn = psycopg2.connect(
        host=creds["POSTGRES_HOST"],
        port=int(creds["POSTGRES_PORT"]),
        dbname=creds["POSTGRES_DB"],
        user=creds["POSTGRES_USER"],
        password=creds["POSTGRES_PASSWORD"],
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FILTER (WHERE origen='real'), COUNT(*) FILTER (WHERE origen='simulado') FROM sig_ae4.incidentes_viales;")
            n_real, n_sim = cur.fetchone()
            cur.execute("SELECT COUNT(*) FROM sig_ae4.semaforos;")
            n_sem = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sig_ae4.escuelas;")
            n_esc = cur.fetchone()[0]
    finally:
        conn.close()

    # Mapa 1: Regional IGN (EPSG:4326)
    p1 = MAPAS_DIR / "mapa_01_regional_ign.png"
    render_thematic_map(
        p1,
        title="Mapa 1 · Contexto Regional NEA, Hidrografía y Red Vial (IGN + Natural Earth)",
        subtitle="Misiones, Corrientes, Entre Ríos, países limítrofes, cursos de agua principales, rutas nacionales/provinciales y capitales",
        crs_authid="EPSG:4326",
        extent=QgsRectangle(-61.7, -32.7, -52.2, -24.0),
        render_layers=[
            layers["localidades"],
            layers["rutas"],
            layers["cursos_agua"],
            layers["departamentos"],
            layers["provincias"],
            layers["paises"],
        ],
        background_hex="#dbeafe",
        legend_entries=[
            LegendEntry("section", "Límites y Divisiones"),
            LegendEntry("fill", "Provincia de Misiones (estudio)", fill="#fef3c7", stroke="#b45309"),
            LegendEntry("fill", "Provincias argentinas", fill="#f8fafc", stroke="#475569"),
            LegendEntry("fill", "Países limítrofes", fill="#e5e0d5", stroke="#334155"),
            LegendEntry("fill", "Departamentos (IGN)", fill="#ffffff00", stroke="#94a3b8", dashed=True),
            LegendEntry("section", "Hidrografía y Red Vial"),
            LegendEntry("line", "Río principal (Paraná/Uruguay/Iguazú)", fill="#1d4ed8", line_width=3.2),
            LegendEntry("line", "Afluente / arroyo", fill="#60a5fa", line_width=1.4),
            LegendEntry("line", "Ruta Nacional (RN12, RN14, etc.)", fill="#dc2626", line_width=2.6),
            LegendEntry("line", "Ruta Provincial", fill="#d97706", line_width=1.6),
            LegendEntry("section", "Localidades (IGN-BAHRA)"),
            LegendEntry("marker", "Capital Provincial", fill="#e11d48", stroke="#881337", shape="star", size_px=12),
            LegendEntry("marker", "Localidad / paraje", fill="#64748b", stroke="#475569", shape="circle", size_px=6),
        ],
        summary_title="Cobertura Regional (sig_ae4)",
        summary_lines=[
            "• 12 países (ARG, PRY, BRA, URY, ...)",
            "• 24 provincias · 529 departamentos",
            "• 1.333 cursos de agua (41 principales)",
            "• 582 tramos viales (286 RN · 296 RP)",
            "• 3.528 localidades BAHRA (Posadas cap.)",
        ],
        footer_left="Fuente: IGN Argentina (WFS capas base + BAHRA) y Natural Earth 50m en PostgreSQL/PostGIS.",
    )

    # Mapa 2: Posadas Infraestructura y Siniestros (EPSG:5348)
    p2 = MAPAS_DIR / "mapa_02_posadas_infraestructura_y_siniestros.png"
    render_thematic_map(
        p2,
        title="Mapa 2 · Posadas: Infraestructura Vial, Nodos AITARA y Siniestralidad",
        subtitle="Separación estricta entre siniestros reales (n=12) y simulados AITARA (n=1.417) sobre red vial, semáforos y escuelas",
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
            LegendEntry("section", "Siniestralidad (incidentes_viales)"),
            LegendEntry("marker", f"Incidente real (n={n_real})", fill="#dc2626", stroke="#7f1d1d", shape="diamond", size_px=12),
            LegendEntry("marker", "Simulado AITARA · Sev. 3", fill="#ea580c", stroke="#9a3412", shape="circle", size_px=10),
            LegendEntry("marker", "Simulado AITARA · Sev. 2", fill="#f59e0b", stroke="#92400e", shape="circle", size_px=8),
            LegendEntry("marker", "Simulado AITARA · Sev. 1", fill="#fbbf24", stroke="#b45309", shape="circle", size_px=6),
            LegendEntry("section", "Nodos Expertos AITARA (Drenaje)"),
            LegendEntry("marker", "Drenaje BAJO (3 nodos)", fill="#be123c", stroke="#ffffff", shape="pentagon", size_px=12),
            LegendEntry("marker", "Drenaje MEDIO (2 nodos)", fill="#9333ea", stroke="#ffffff", shape="pentagon", size_px=11),
            LegendEntry("marker", "Drenaje ALTO (2 nodos)", fill="#0284c7", stroke="#ffffff", shape="pentagon", size_px=11),
            LegendEntry("section", "Equipamiento y Red Vial IDE / OSM"),
            LegendEntry("marker", f"Semáforos IDE ({n_sem})", fill="#10b981", stroke="#064e3b", shape="circle", size_px=8),
            LegendEntry("marker", f"Escuelas IDE ({n_esc})", fill="#2563eb", stroke="#1e3a8a", shape="square", size_px=8),
            LegendEntry("line", "Avenida mano única (IDE)", fill="#f97316", line_width=3.2),
            LegendEntry("line", "Asfalto sobre empedrado", fill="#0d9488", line_width=2.0),
            LegendEntry("line", "Ciclovía (IDE)", fill="#16a34a", line_width=2.2, dashed=True),
            LegendEntry("line", "Calles OSM (1.286)", fill="#94a3b8", line_width=1.3),
            LegendEntry("fill", "Delegación municipal (12)", fill="59,130,246,45", stroke="#1e3a8a", dashed=True),
        ],
        summary_title="Síntesis Urbana (Posadas)",
        summary_lines=[
            f"• Incidentes: {n_real} reales / {n_sim:,} sim.",
            "• 7 nodos expertos AITARA (geom_m)",
            f"• {n_sem} semáforos · {n_esc} escuelas IDE",
            "• 8 corredores mano única · 52 ciclovías",
            "• 613 obras asfalto s/empedrado",
        ],
        footer_left="Fuente: IDE Posadas (WFS) + OSM/AITARA en PostgreSQL/PostGIS (distancias métricas en EPSG:5348).",
    )

    # Mapa 3: Autoría 1 — Escuelas sin semáforo sobre av. mano única (EPSG:5348)
    p3 = MAPAS_DIR / "mapa_03_autoria1_escuelas_sin_semaforo.png"
    render_thematic_map(
        p3,
        title="Mapa 3 · Autoría 1: Intersecciones Escolares Sin Semáforo en Av. Mano Única",
        subtitle="Cruces OSM <=150 m de escuela IDE y <=25 m de avenida de mano única sin semáforo IDE <=30 m (n=104 candidatas)",
        crs_authid="EPSG:5348",
        extent=QgsRectangle(6602900.0, 6968300.0, 6610200.0, 6974500.0),
        render_layers=[
            layers["autoria_1"],
            layers["escuelas"],
            layers["semaforos"],
            layers["avenidas_mano_unica"],
            layers["calles"],
            layers["delegaciones"],
        ],
        background_hex="#f8fafc",
        legend_entries=[
            LegendEntry("section", "Autoría 1 · Cruces Candidatos (104)"),
            LegendEntry("marker", "Crítico: con siniestro real <=250 m (3)", fill="#dc2626", stroke="#7f1d1d", shape="star", size_px=13),
            LegendEntry("marker", "Alto: siniestro simulado <=250 m (1)", fill="#ea580c", stroke="#7c2d12", shape="star", size_px=11),
            LegendEntry("marker", "Resto candidatas sin semáforo (100)", fill="#facc15", stroke="#a16207", shape="circle", size_px=9),
            LegendEntry("section", "Capas de Criterio Espacial"),
            LegendEntry("marker", "Escuelas IDE (radio <=150 m)", fill="#2563eb", stroke="#1e3a8a", shape="square", size_px=9),
            LegendEntry("marker", "Semáforos IDE (exclusión <=30 m)", fill="#10b981", stroke="#064e3b", shape="circle", size_px=8),
            LegendEntry("line", "Avenidas mano única (<=25 m)", fill="#f97316", line_width=3.5),
            LegendEntry("line", "Red vial OSM (calles)", fill="#94a3b8", line_width=1.2),
            LegendEntry("fill", "Límite delegaciones", fill="59,130,246,35", stroke="#1e3a8a", dashed=True),
        ],
        summary_title="Priorización Escolar (Autoría 1)",
        summary_lines=[
            "• Total candidatas detectadas: 104",
            "• 3 cruces con 1 siniestro real <=250 m:",
            "  1) Beethoven y Av. Centenario",
            "  2) Av. Centenario y Derqui",
            "  3) Av. Lavalle y Neumann",
            "• 1 cruce con 9 sim. <=250 m (Tacuarí)",
        ],
        footer_left="Consulta SQL: ae4_sig/sql/03_consultas_autoria.sql (Autoría 1 sobre geom_m EPSG:5348).",
    )

    # Mapa 4: Autoría 3 — Brecha de infraestructura vial por delegación (EPSG:5348)
    p4 = MAPAS_DIR / "mapa_04_autoria3_brecha_delegaciones.png"
    l_del: QgsVectorLayer = layers["delegaciones"]  # type: ignore[assignment]
    l_inc: QgsVectorLayer = layers["incidentes_viales"]  # type: ignore[assignment]
    tr_4326_to_5348 = QgsCoordinateTransform(
        QgsCoordinateReferenceSystem("EPSG:4326"),
        QgsCoordinateReferenceSystem("EPSG:5348"),
        QgsProject.instance(),
    )
    del_ext = tr_4326_to_5348.transformBoundingBox(l_del.extent())
    del_ext.scale(1.04)

    # Filtrar incidentes_viales a origen='real' exclusivamente durante este render
    l_inc.setSubsetString("origen = 'real'")
    try:
        render_thematic_map(
            p4,
            title="Mapa 4 · Autoría 3: Brecha de Semáforos y Siniestralidad por Delegación",
            subtitle="Coropleta graduada por semáforos cada 100 intersecciones OSM, semáforos IDE (280) e incidentes reales (12)",
            crs_authid="EPSG:5348",
            extent=del_ext,
            render_layers=[
                l_inc,
                layers["semaforos"],
                layers["calles"],
                layers["autoria_3"],
            ],
            background_hex="#f8fafc",
            legend_entries=[
                LegendEntry("section", "Semáforos / 100 Intersecciones"),
                LegendEntry("fill", "0.00 – 0.50 (Déficit crítico: 3 del.)", fill="185,28,28,185", stroke="#7f1d1d"),
                LegendEntry("fill", "0.50 – 1.50 (Déficit alto: 2 del.)", fill="234,88,12,175", stroke="#9a3412"),
                LegendEntry("fill", "1.50 – 3.00 (Cobertura baja: 3 del.)", fill="245,158,11,165", stroke="#92400e"),
                LegendEntry("fill", "3.00 – 5.00 (Cobertura media: 3 del.)", fill="59,130,246,155", stroke="#1e40af"),
                LegendEntry("fill", "> 5.00 (Sede Central: 44.31 sem/100)", fill="15,118,110,165", stroke="#115e59"),
                LegendEntry("section", "Infraestructura y Siniestros Reales"),
                LegendEntry("marker", "Incidente vial real (n=12)", fill="#dc2626", stroke="#7f1d1d", shape="diamond", size_px=12),
                LegendEntry("marker", "Semáforos IDE (n=280)", fill="#10b981", stroke="#064e3b", shape="circle", size_px=8),
                LegendEntry("line", "Red vial OSM (referencia)", fill="#94a3b8", line_width=1.0),
            ],
            summary_title="Brecha Territorial (12 Deleg.)",
            summary_lines=[
                "• Sede Central: 44.31 sem/100 int (74)",
                "• Itaembé Guazú y Miní Este: 0.00 sem",
                "• Mayor brecha: 32-33 (idx 51.82)",
                "  y Riberas del Paraná (idx 49.27)",
                "• Villa Urquiza: 4 reales (4.76 sem/100)",
            ],
            footer_left="Consulta SQL: ae4_sig/sql/03_consultas_autoria.sql (Autoría 3 · ST_Area y ST_Within en EPSG:5348).",
        )
    finally:
        l_inc.setSubsetString("")

    return [p1, p2, p3, p4]


# -----------------------------------------------------------------------------
# 6. Guardado seguro de proyecto_ae4.qgz y reporte de verificación
# -----------------------------------------------------------------------------


def strip_credentials_from_qgz(
    qgz_path: Path,
    pg_user: str,
    pg_password: str,
) -> Dict[str, object]:
    """Elimina user= y password= del XML .qgs dentro del .qgz y verifica integridad."""
    with zipfile.ZipFile(qgz_path, "r") as zin:
        entries = {name: zin.read(name) for name in zin.namelist()}

    qgs_names = [n for n in entries if n.endswith(".qgs")]
    if len(qgs_names) != 1:
        raise RuntimeError(f"Se esperaba 1 archivo .qgs en {qgz_path}, encontrados: {qgs_names}")
    qgs_name = qgs_names[0]

    raw_xml = entries[qgs_name].decode("utf-8")

    # Eliminar user='...' y password='...' de <datasource> y atributos source="..."
    cred_pattern = re.compile(
        r"\s*(?:user|password)=(?:'[^']*'|\"[^\"]*\"|&apos;[^&]*&apos;|&#39;[^&]*&#39;)"
    )
    clean_xml = cred_pattern.sub("", raw_xml)
    # Limpiar posibles espacios dobles generados al remover credenciales
    clean_xml = re.sub(r"port=(\d+)\s{2,}", r"port=\1 ", clean_xml)

    # Validar XML y versión QGIS 4.2.1
    root = ET.fromstring(clean_xml)
    qgis_version = root.attrib.get("version", "")
    if not qgis_version.startswith("4.2.1"):
        raise RuntimeError(f"Versión inesperada en <qgis version='...'>: '{qgis_version}'")

    forbidden_tokens = ["password=", "user=", pg_password, pg_user]
    found_forbidden = [tok for tok in forbidden_tokens if tok in clean_xml]
    if found_forbidden:
        raise RuntimeError(f"Persisten tokens sensibles en el XML del .qgz: {found_forbidden}")

    entries[qgs_name] = clean_xml.encode("utf-8")
    with zipfile.ZipFile(qgz_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for name, data in entries.items():
            zout.writestr(name, data)

    # Verificación final de lectura ZIP + XML
    with zipfile.ZipFile(qgz_path, "r") as zchk:
        bad = zchk.testzip()
        if bad is not None:
            raise RuntimeError(f"Archivo corrupto en ZIP {qgz_path}: {bad}")
        final_xml = zchk.read(qgs_name).decode("utf-8")
        ET.fromstring(final_xml)

    return {
        "qgz_size_bytes": qgz_path.stat().st_size,
        "qgs_entry": qgs_name,
        "qgis_version": qgis_version,
        "zip_entries": list(entries.keys()),
        "forbidden_matches": 0,
    }


def write_verification_report(
    out_path: Path,
    rows: Sequence[Dict[str, object]],
    all_ok: bool,
    qgz_info: Dict[str, object],
    map_paths: Sequence[Path],
) -> None:
    """Escribe ae4_sig/outputs/verificacion_qgis_4_2_1.txt con el detalle completo."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "=" * 92,
        "AE4 SIG — REPORTE DE VERIFICACIÓN NATIVA QGIS 4.2.1 ('Belém do Pará') vs PostgreSQL/PostGIS",
        "=" * 92,
        f"Título del proyecto : {PROJECT_TITLE}",
        "SRC del proyecto    : EPSG:5348 (POSGAR 2007 / Argentina 6)",
        f"Versión XML QGIS    : {qgz_info['qgis_version']}",
        f"Archivo generado    : {QGZ_PATH.relative_to(AE4_ROOT)} ({qgz_info['qgz_size_bytes']} bytes)",
        f"Entradas ZIP        : {', '.join(qgz_info['zip_entries'])}",
        f"Tokens credenciales : {qgz_info['forbidden_matches']} (sin user= ni password=)",
        "",
        f"{'Capa':<44} {'Tipo':<8} {'Valid':<6} {'QGIS':>8} {'Postgres':>10} {'Match':<6}",
        "-" * 92,
    ]
    for r in rows:
        lines.append(
            f"{str(r['layer']):<44} {str(r['kind']):<8} {str(r['valid']):<6} "
            f"{str(r['qgis_count']):>8} {str(r['postgres_count']):>10} {str(r['match']):<6}"
        )
    lines.extend(
        [
            "-" * 92,
            f"Resumen global      : total_capas={len(rows)} | todas_validas_y_coincidentes={all_ok}",
            "",
            "Mapas temáticos PNG renderizados vía QgsMapRendererParallelJob (1800x1150 px):",
        ]
    )
    for mp in map_paths:
        lines.append(f"  - {mp.relative_to(AE4_ROOT)} ({mp.stat().st_size} bytes)")
    lines.append("=" * 92)

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# -----------------------------------------------------------------------------
# 7. Orquestación principal
# -----------------------------------------------------------------------------


def main() -> int:
    app = QgsApplication([], False)
    app.initQgis()
    try:
        print(f"Iniciando PyQGIS {Qgis.version()} en modo headless ({os.environ.get('QT_QPA_PLATFORM')})...")
        creds = load_env_credentials(ENV_PATH)
        autoria_sql = extract_autoria_queries(SQL_AUTORIA_PATH)

        proj, layers, metas = build_project_and_layers(creds, autoria_sql)
        rows, all_ok = verify_counts_against_postgres(creds, layers, metas)
        if not all_ok:
            raise RuntimeError("Se detectó discrepancia o capa inválida en la verificación QGIS vs PostgreSQL.")

        map_paths = render_all_maps(layers, creds)

        QGZ_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not proj.write(str(QGZ_PATH)):
            raise RuntimeError(f"QgsProject.write() falló al guardar {QGZ_PATH}")

        qgz_info = strip_credentials_from_qgz(
            QGZ_PATH,
            pg_user=creds["POSTGRES_USER"],
            pg_password=creds["POSTGRES_PASSWORD"],
        )
        write_verification_report(VERIF_TXT_PATH, rows, all_ok, qgz_info, map_paths)

        print(VERIF_TXT_PATH.read_text(encoding="utf-8"))
        return 0
    finally:
        # Limpiar referencias del proyecto antes de finalizar QgsApplication
        QgsProject.instance().clear()
        app.exitQgis()


if __name__ == "__main__":
    raise SystemExit(main())
