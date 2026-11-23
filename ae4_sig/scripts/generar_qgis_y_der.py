"""Genera el proyecto QGIS (.qgz), el diagrama DER (.png) y el diccionario DER (.md) para AE4 SIG.

Salidas generadas dentro de ae4_sig/:
  - ae4_sig/qgis/proyecto_ae4.qgz  (ZIP válido con proyecto_ae4.qgs en EPSG:5348)
  - ae4_sig/outputs/der_sig_ae4.png (DER de alta resolución en 3 zonas con matplotlib Agg)
  - ae4_sig/docs/DER_sig_ae4.md    (Mermaid erDiagram + diccionario de datos de las 19 tablas)

Restricciones de seguridad y esquema:
  - Sin credenciales embebidas: nunca escribe user= ni password= en el XML de QGIS.
  - Coincide exactamente con el esquema `sig_ae4` definido en `ae4_sig/sql/00_init.sql`.
"""

from __future__ import annotations

import math
import uuid
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


AE4_ROOT = Path(__file__).resolve().parents[1]
QGIS_OUT_PATH = AE4_ROOT / "qgis" / "proyecto_ae4.qgz"
QGS_INTERNAL_NAME = "proyecto_ae4.qgs"
DER_PNG_PATH = AE4_ROOT / "outputs" / "der_sig_ae4.png"
DER_MD_PATH = AE4_ROOT / "docs" / "DER_sig_ae4.md"

PG_DBNAME = "aitara_ae4_sig"
PG_HOST = "localhost"
PG_PORT = "5433"
PG_SCHEMA = "sig_ae4"

WMS_DATASOURCE = (
    "contextualWMSLegend=0"
    "&crs=EPSG:4326"
    "&dpiMode=7"
    "&format=image/png"
    "&layers=geonode:DELEGACIONES_MUNICIPALES_POSADAS_20250"
    "&styles"
    "&url=https://www.ide.posadas.gob.ar/geoserver/ows"
)


# -----------------------------------------------------------------------------
# 1. Utilidades geodésicas (WGS84 -> POSGAR 2007 / Argentina Faja 6 EPSG:5348)
# -----------------------------------------------------------------------------


def wgs84_to_epsg5348(lon_deg: float, lat_deg: float) -> Tuple[float, float]:
    """Proyecta coordenadas geográficas (WGS84/GRS80) a EPSG:5348 (Transverse Mercator).

    Parámetros oficiales EPSG:5348:
      +proj=tmerc +lat_0=-90 +lon_0=-57 +k=1 +x_0=6500000 +y_0=0 +ellps=GRS80 +units=m
    """
    a = 6378137.0
    f = 1.0 / 298.257222101
    e2 = 2.0 * f - f * f
    ep2 = e2 / (1.0 - e2)
    e4 = e2 * e2
    e6 = e4 * e2

    k0 = 1.0
    lon0 = math.radians(-57.0)
    lat0 = math.radians(-90.0)
    x0 = 6500000.0
    y0 = 0.0

    def meridional_arc(phi: float) -> float:
        return a * (
            (1.0 - e2 / 4.0 - 3.0 * e4 / 64.0 - 5.0 * e6 / 256.0) * phi
            - (3.0 * e2 / 8.0 + 3.0 * e4 / 32.0 + 45.0 * e6 / 1024.0) * math.sin(2.0 * phi)
            + (15.0 * e4 / 256.0 + 45.0 * e6 / 1024.0) * math.sin(4.0 * phi)
            - (35.0 * e6 / 3072.0) * math.sin(6.0 * phi)
        )

    phi = math.radians(lat_deg)
    lam = math.radians(lon_deg)
    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)
    tan_phi = math.tan(phi)

    n_rad = a / math.sqrt(1.0 - e2 * sin_phi * sin_phi)
    t_val = tan_phi * tan_phi
    c_val = ep2 * cos_phi * cos_phi
    a_val = (lam - lon0) * cos_phi

    m_val = meridional_arc(phi)
    m0 = meridional_arc(lat0)

    easting = x0 + k0 * n_rad * (
        a_val
        + (1.0 - t_val + c_val) * (a_val**3) / 6.0
        + (5.0 - 18.0 * t_val + t_val * t_val + 72.0 * c_val - 58.0 * ep2) * (a_val**5) / 120.0
    )
    northing = y0 + k0 * (
        m_val
        - m0
        + n_rad
        * tan_phi
        * (
            (a_val**2) / 2.0
            + (5.0 - t_val + 9.0 * c_val + 4.0 * c_val * c_val) * (a_val**4) / 24.0
            + (61.0 - 58.0 * t_val + t_val * t_val + 600.0 * c_val - 330.0 * ep2)
            * (a_val**6)
            / 720.0
        )
    )
    return easting, northing


def compute_posadas_extent_5348() -> Tuple[float, float, float, float]:
    """Calcula el bounding box urbano de Posadas en EPSG:5348 a partir de WGS84."""
    # Cubre el ejido urbano de Posadas (calles, semáforos, escuelas, paradas e incidentes)
    lon_min, lat_min = -55.99, -27.46
    lon_max, lat_max = -55.86, -27.34
    corners = [
        wgs84_to_epsg5348(lon_min, lat_min),
        wgs84_to_epsg5348(lon_min, lat_max),
        wgs84_to_epsg5348(lon_max, lat_min),
        wgs84_to_epsg5348(lon_max, lat_max),
    ]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    return round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)


# -----------------------------------------------------------------------------
# 2. Definición y generación del proyecto QGIS (.qgz / .qgs)
# -----------------------------------------------------------------------------


@dataclass
class LayerSpec:
    """Especificación de capa vectorial PostGIS para QGIS 3.x."""

    table: str
    label: str
    group: str
    pg_geom_type: str  # Point | MultiLineString | MultiPolygon
    qgis_geom: str     # Point | Line | Polygon
    checked: bool
    style_kind: str    # marker | line | fill | incidentes_rules
    style_opts: Dict[str, str] = field(default_factory=dict)
    label_field: Optional[str] = None

    @property
    def layer_id(self) -> str:
        return f"sig_ae4_{self.table}"

    @property
    def datasource(self) -> str:
        return (
            f"dbname='{PG_DBNAME}' host={PG_HOST} port={PG_PORT} sslmode=disable "
            f"key='id' srid=4326 type={self.pg_geom_type} checkPrimaryKeyUnicity='1' "
            f'table="{PG_SCHEMA}"."{self.table}" (geom)'
        )


URBAN_LAYERS: List[LayerSpec] = [
    LayerSpec(
        table="incidentes_viales",
        label="incidentes_viales",
        group="Posadas (IDE + OSM + AITARA)",
        pg_geom_type="Point",
        qgis_geom="Point",
        checked=True,
        style_kind="incidentes_rules",
    ),
    LayerSpec(
        table="nodos_referencia_aitara",
        label="nodos_referencia_aitara",
        group="Posadas (IDE + OSM + AITARA)",
        pg_geom_type="Point",
        qgis_geom="Point",
        checked=True,
        style_kind="marker",
        style_opts={
            "name": "star",
            "color": "217,70,239,255",
            "outline_color": "112,26,117,255",
            "outline_width": "0.45",
            "size": "4.2",
        },
    ),
    LayerSpec(
        table="semaforos",
        label="semaforos",
        group="Posadas (IDE + OSM + AITARA)",
        pg_geom_type="Point",
        qgis_geom="Point",
        checked=True,
        style_kind="marker",
        style_opts={
            "name": "triangle",
            "color": "16,185,129,255",
            "outline_color": "6,78,59,255",
            "outline_width": "0.4",
            "size": "3.0",
        },
    ),
    LayerSpec(
        table="escuelas",
        label="escuelas",
        group="Posadas (IDE + OSM + AITARA)",
        pg_geom_type="Point",
        qgis_geom="Point",
        checked=True,
        style_kind="marker",
        style_opts={
            "name": "square",
            "color": "124,58,237,255",
            "outline_color": "76,29,149,255",
            "outline_width": "0.35",
            "size": "2.8",
        },
    ),
    LayerSpec(
        table="paradas",
        label="paradas",
        group="Posadas (IDE + OSM + AITARA)",
        pg_geom_type="Point",
        qgis_geom="Point",
        checked=True,
        style_kind="marker",
        style_opts={
            "name": "circle",
            "color": "14,165,233,220",
            "outline_color": "12,74,110,255",
            "outline_width": "0.25",
            "size": "1.9",
        },
    ),
    LayerSpec(
        table="intersecciones",
        label="intersecciones",
        group="Posadas (IDE + OSM + AITARA)",
        pg_geom_type="Point",
        qgis_geom="Point",
        checked=True,
        style_kind="marker",
        style_opts={
            "name": "circle",
            "color": "71,85,105,170",
            "outline_color": "30,41,59,200",
            "outline_width": "0.2",
            "size": "1.2",
        },
    ),
    LayerSpec(
        table="avenidas_mano_unica",
        label="avenidas_mano_unica",
        group="Posadas (IDE + OSM + AITARA)",
        pg_geom_type="MultiLineString",
        qgis_geom="Line",
        checked=True,
        style_kind="line",
        style_opts={
            "line_color": "37,99,235,235",
            "line_width": "0.85",
            "line_style": "solid",
        },
    ),
    LayerSpec(
        table="asfalto_sobre_empedrado",
        label="asfalto_sobre_empedrado",
        group="Posadas (IDE + OSM + AITARA)",
        pg_geom_type="MultiLineString",
        qgis_geom="Line",
        checked=True,
        style_kind="line",
        style_opts={
            "line_color": "180,83,9,225",
            "line_width": "0.65",
            "line_style": "solid",
        },
    ),
    LayerSpec(
        table="ciclovias",
        label="ciclovias",
        group="Posadas (IDE + OSM + AITARA)",
        pg_geom_type="MultiLineString",
        qgis_geom="Line",
        checked=True,
        style_kind="line",
        style_opts={
            "line_color": "22,163,74,230",
            "line_width": "0.6",
            "line_style": "dash",
        },
    ),
    LayerSpec(
        table="calles",
        label="calles",
        group="Posadas (IDE + OSM + AITARA)",
        pg_geom_type="MultiLineString",
        qgis_geom="Line",
        checked=True,
        style_kind="line",
        style_opts={
            "line_color": "148,163,184,185",
            "line_width": "0.35",
            "line_style": "solid",
        },
    ),
    LayerSpec(
        table="delegaciones",
        label="delegaciones",
        group="Posadas (IDE + OSM + AITARA)",
        pg_geom_type="MultiPolygon",
        qgis_geom="Polygon",
        checked=True,
        style_kind="fill",
        style_opts={
            "color": "59,130,246,45",
            "outline_color": "30,58,138,255",
            "outline_width": "0.75",
            "outline_style": "solid",
        },
        label_field="nombre",
    ),
]

REGIONAL_LAYERS: List[LayerSpec] = [
    LayerSpec(
        table="localidades",
        label="localidades",
        group="Regional (IGN)",
        pg_geom_type="Point",
        qgis_geom="Point",
        checked=False,
        style_kind="marker",
        style_opts={
            "name": "circle",
            "color": "51,65,85,220",
            "outline_color": "248,250,252,255",
            "outline_width": "0.25",
            "size": "2.0",
        },
    ),
    LayerSpec(
        table="cursos_agua",
        label="cursos_agua",
        group="Regional (IGN)",
        pg_geom_type="MultiLineString",
        qgis_geom="Line",
        checked=False,
        style_kind="line",
        style_opts={
            "line_color": "56,189,248,220",
            "line_width": "0.5",
            "line_style": "solid",
        },
    ),
    LayerSpec(
        table="rutas",
        label="rutas",
        group="Regional (IGN)",
        pg_geom_type="MultiLineString",
        qgis_geom="Line",
        checked=False,
        style_kind="line",
        style_opts={
            "line_color": "185,28,28,200",
            "line_width": "0.55",
            "line_style": "solid",
        },
    ),
    LayerSpec(
        table="departamentos",
        label="departamentos",
        group="Regional (IGN)",
        pg_geom_type="MultiPolygon",
        qgis_geom="Polygon",
        checked=False,
        style_kind="fill",
        style_opts={
            "color": "148,163,184,25",
            "outline_color": "100,116,139,220",
            "outline_width": "0.45",
            "outline_style": "dash",
        },
    ),
    LayerSpec(
        table="provincias",
        label="provincias",
        group="Regional (IGN)",
        pg_geom_type="MultiPolygon",
        qgis_geom="Polygon",
        checked=False,
        style_kind="fill",
        style_opts={
            "color": "203,213,225,20",
            "outline_color": "71,85,105,240",
            "outline_width": "0.65",
            "outline_style": "solid",
        },
    ),
    LayerSpec(
        table="paises",
        label="paises",
        group="Regional (IGN)",
        pg_geom_type="MultiPolygon",
        qgis_geom="Polygon",
        checked=False,
        style_kind="fill",
        style_opts={
            "color": "226,232,240,18",
            "outline_color": "30,41,59,255",
            "outline_width": "0.85",
            "outline_style": "solid",
        },
    ),
]


def _append_spatialrefsys_5348(parent: ET.Element) -> ET.Element:
    srs = ET.SubElement(parent, "spatialrefsys", nativeFormat="Wkt")
    wkt = (
        'PROJCRS["POSGAR 2007 / Argentina 6",'
        'BASEGEOGCRS["POSGAR 2007",'
        'DATUM["Posiciones Geodesicas Argentinas 2007",'
        'ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],'
        'PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],'
        'ID["EPSG",4694]],'
        'CONVERSION["Argentina zone 6",'
        'METHOD["Transverse Mercator",ID["EPSG",9807]],'
        'PARAMETER["Latitude of natural origin",-90,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],'
        'PARAMETER["Longitude of natural origin",-57,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],'
        'PARAMETER["Scale factor at natural origin",1,SCALEUNIT["unity",1],ID["EPSG",8805]],'
        'PARAMETER["False easting",6500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],'
        'PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],'
        'CS[Cartesian,2],'
        'AXIS["northing (X)",north,ORDER[1],LENGTHUNIT["metre",1]],'
        'AXIS["easting (Y)",east,ORDER[2],LENGTHUNIT["metre",1]],'
        'ID["EPSG",5348]]'
    )
    fields = [
        ("wkt", wkt),
        (
            "proj4",
            "+proj=tmerc +lat_0=-90 +lon_0=-57 +k=1 +x_0=6500000 +y_0=0 "
            "+ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs",
        ),
        ("srsid", "28265"),
        ("srid", "5348"),
        ("authid", "EPSG:5348"),
        ("description", "POSGAR 2007 / Argentina 6"),
        ("projectionacronym", "tmerc"),
        ("ellipsoidacronym", "EPSG:7019"),
        ("geographicflag", "false"),
    ]
    for tag, val in fields:
        el = ET.SubElement(srs, tag)
        el.text = val
    return srs


def _append_spatialrefsys_4326(parent: ET.Element) -> ET.Element:
    srs = ET.SubElement(parent, "spatialrefsys", nativeFormat="Wkt")
    wkt = (
        'GEOGCRS["WGS 84",'
        'ENSEMBLE["World Geodetic System 1984 ensemble",'
        'MEMBER["World Geodetic System 1984 (Transit)"],'
        'MEMBER["World Geodetic System 1984 (G730)"],'
        'MEMBER["World Geodetic System 1984 (G873)"],'
        'MEMBER["World Geodetic System 1984 (G1150)"],'
        'MEMBER["World Geodetic System 1984 (G1674)"],'
        'MEMBER["World Geodetic System 1984 (G1762)"],'
        'MEMBER["World Geodetic System 1984 (G2139)"],'
        'ELLIPSOID["WGS 84",6378137,298.257223563,LENGTHUNIT["metre",1]],'
        'ENSEMBLEACCURACY[2.0]],'
        'PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],'
        'CS[ellipsoidal,2],'
        'AXIS["geodetic latitude (Lat)",north,ORDER[1],ANGLEUNIT["degree",0.0174532925199433]],'
        'AXIS["geodetic longitude (Lon)",east,ORDER[2],ANGLEUNIT["degree",0.0174532925199433]],'
        'ID["EPSG",4326]]'
    )
    fields = [
        ("wkt", wkt),
        ("proj4", "+proj=longlat +datum=WGS84 +no_defs"),
        ("srsid", "3452"),
        ("srid", "4326"),
        ("authid", "EPSG:4326"),
        ("description", "WGS 84"),
        ("projectionacronym", "longlat"),
        ("ellipsoidacronym", "EPSG:7030"),
        ("geographicflag", "true"),
    ]
    for tag, val in fields:
        el = ET.SubElement(srs, tag)
        el.text = val
    return srs


def _add_option_map(parent: ET.Element, values: Dict[str, str]) -> ET.Element:
    opt_map = ET.SubElement(parent, "Option", type="Map")
    for k, v in values.items():
        ET.SubElement(opt_map, "Option", type="QString", name=k, value=v)
    return opt_map


def _build_symbol(sym_type: str, sym_name: str, layer_class: str, props: Dict[str, str]) -> ET.Element:
    sym = ET.Element(
        "symbol",
        type=sym_type,
        name=sym_name,
        alpha="1",
        clip_to_extent="1",
        force_rhr="0",
    )
    layer = ET.SubElement(
        sym,
        "layer",
        {"class": layer_class, "enabled": "1", "pass": "0", "locked": "0"},
    )
    _add_option_map(layer, props)
    return sym


def _append_renderer(maplayer: ET.Element, spec: LayerSpec) -> None:
    if spec.style_kind == "incidentes_rules":
        renderer = ET.SubElement(
            maplayer,
            "renderer-v2",
            type="RuleRenderer",
            forceraster="0",
            symbollevels="0",
            enableorderby="0",
            referencescale="-1",
        )
        rules_el = ET.SubElement(renderer, "rules", key=f"{{{uuid.uuid4()}}}")
        rules = [
            ("origen = 'real'", "Incidente real (AITARA)", "0"),
            (
                "origen = 'simulado' AND severidad >= 4",
                "Simulado AITARA — Alta (severidad 4-5)",
                "1",
            ),
            (
                "origen = 'simulado' AND severidad <= 3",
                "Simulado AITARA — Leve/Mod (severidad 1-3)",
                "2",
            ),
            ("ELSE", "Otros incidentes", "3"),
        ]
        for expr, label, sym_idx in rules:
            ET.SubElement(
                rules_el,
                "rule",
                key=f"{{{uuid.uuid4()}}}",
                filter=expr,
                label=label,
                symbol=sym_idx,
            )

        symbols_el = ET.SubElement(renderer, "symbols")
        rule_symbols = [
            {
                "name": "diamond",
                "color": "220,38,38,255",
                "outline_color": "127,29,29,255",
                "outline_style": "solid",
                "outline_width": "0.55",
                "outline_width_unit": "MM",
                "size": "4.0",
                "size_unit": "MM",
            },
            {
                "name": "circle",
                "color": "249,115,22,235",
                "outline_color": "154,52,18,255",
                "outline_style": "solid",
                "outline_width": "0.4",
                "outline_width_unit": "MM",
                "size": "2.9",
                "size_unit": "MM",
            },
            {
                "name": "circle",
                "color": "245,158,11,200",
                "outline_color": "146,64,14,255",
                "outline_style": "solid",
                "outline_width": "0.3",
                "outline_width_unit": "MM",
                "size": "2.0",
                "size_unit": "MM",
            },
            {
                "name": "circle",
                "color": "100,116,139,190",
                "outline_color": "51,65,85,255",
                "outline_style": "solid",
                "outline_width": "0.3",
                "outline_width_unit": "MM",
                "size": "2.0",
                "size_unit": "MM",
            },
        ]
        for idx, props in enumerate(rule_symbols):
            symbols_el.append(_build_symbol("marker", str(idx), "SimpleMarker", props))
        return

    renderer = ET.SubElement(
        maplayer,
        "renderer-v2",
        type="singleSymbol",
        forceraster="0",
        symbollevels="0",
        enableorderby="0",
        referencescale="-1",
    )
    symbols_el = ET.SubElement(renderer, "symbols")
    opts = dict(spec.style_opts)

    if spec.style_kind == "marker":
        props = {
            "name": opts.get("name", "circle"),
            "color": opts.get("color", "59,130,246,255"),
            "outline_color": opts.get("outline_color", "30,58,138,255"),
            "outline_style": "solid",
            "outline_width": opts.get("outline_width", "0.35"),
            "outline_width_unit": "MM",
            "size": opts.get("size", "2.5"),
            "size_unit": "MM",
        }
        symbols_el.append(_build_symbol("marker", "0", "SimpleMarker", props))
    elif spec.style_kind == "line":
        props = {
            "line_color": opts.get("line_color", "100,116,139,255"),
            "line_style": opts.get("line_style", "solid"),
            "line_width": opts.get("line_width", "0.5"),
            "line_width_unit": "MM",
            "capstyle": "round",
            "joinstyle": "round",
        }
        symbols_el.append(_build_symbol("line", "0", "SimpleLine", props))
    elif spec.style_kind == "fill":
        props = {
            "color": opts.get("color", "59,130,246,45"),
            "style": "solid",
            "outline_color": opts.get("outline_color", "30,58,138,255"),
            "outline_style": opts.get("outline_style", "solid"),
            "outline_width": opts.get("outline_width", "0.6"),
            "outline_width_unit": "MM",
        }
        symbols_el.append(_build_symbol("fill", "0", "SimpleFill", props))


def _append_simple_labeling(maplayer: ET.Element, field_name: str) -> None:
    labeling = ET.SubElement(maplayer, "labeling", type="simple")
    settings = ET.SubElement(labeling, "settings", calloutType="simple")
    text_style = ET.SubElement(
        settings,
        "text-style",
        fieldName=field_name,
        isExpression="0",
        fontFamily="Sans Serif",
        fontSize="8.5",
        fontSizeUnit="Point",
        fontWeight="600",
        textColor="30,58,138,255",
        textOpacity="1",
    )
    buf = ET.SubElement(
        text_style,
        "text-buffer",
        bufferDraw="1",
        bufferSize="1.0",
        bufferSizeUnits="MM",
        bufferColor="255,255,255,220",
    )
    _ = buf
    ET.SubElement(settings, "placement", placement="1", dist="0", priority="5")


def build_qgis_project_xml() -> str:
    """Construye el XML completo de proyecto_ae4.qgs (QGIS 3.x) sin credenciales."""
    xmin, ymin, xmax, ymax = compute_posadas_extent_5348()
    all_vector_layers = URBAN_LAYERS + REGIONAL_LAYERS
    wms_id = "ide_posadas_delegaciones_wms"

    qgis = ET.Element(
        "qgis",
        projectname="AE4 SIG — AITARA + IGN + IDE Posadas",
        version="3.34.11-Prizren",
    )

    ET.SubElement(qgis, "homePath", path="")
    title_el = ET.SubElement(qgis, "title")
    title_el.text = "AE4 SIG — AITARA + IGN + IDE Posadas"

    # CRS del proyecto: EPSG:5348 (POSGAR 2007 / Argentina 6)
    project_crs = ET.SubElement(qgis, "projectCrs")
    _append_spatialrefsys_5348(project_crs)

    # Lienzo principal en metros (EPSG:5348) centrado sobre Posadas
    canvas = ET.SubElement(qgis, "mapcanvas", name="theMapCanvas", annotationsVisible="1")
    units_el = ET.SubElement(canvas, "units")
    units_el.text = "meters"
    extent_el = ET.SubElement(canvas, "extent")
    for tag, val in [("xmin", xmin), ("ymin", ymin), ("xmax", xmax), ("ymax", ymax)]:
        el = ET.SubElement(extent_el, tag)
        el.text = f"{val:.2f}"
    rot_el = ET.SubElement(canvas, "rotation")
    rot_el.text = "0"
    dest_srs = ET.SubElement(canvas, "destinationsrs")
    _append_spatialrefsys_5348(dest_srs)
    ET.SubElement(canvas, "rendermaptile").text = "0"
    ET.SubElement(canvas, "expressionContextScope")

    # Árbol de capas con 2 grupos principales + WMS opcional apagado
    root_tree = ET.SubElement(qgis, "layer-tree-group")
    ET.SubElement(root_tree, "customproperties")

    grp_urban = ET.SubElement(
        root_tree,
        "layer-tree-group",
        name="Posadas (IDE + OSM + AITARA)",
        expanded="1",
        checked="Qt::Checked",
    )
    for spec in URBAN_LAYERS:
        ET.SubElement(
            grp_urban,
            "layer-tree-layer",
            id=spec.layer_id,
            name=spec.label,
            source=spec.datasource,
            providerKey="postgres",
            checked="Qt::Checked" if spec.checked else "Qt::Unchecked",
            expanded="1" if spec.table == "incidentes_viales" else "0",
        )

    ET.SubElement(
        grp_urban,
        "layer-tree-layer",
        id=wms_id,
        name="IDE Posadas — Delegaciones (WMS)",
        source=WMS_DATASOURCE,
        providerKey="wms",
        checked="Qt::Unchecked",
        expanded="0",
    )

    grp_regional = ET.SubElement(
        root_tree,
        "layer-tree-group",
        name="Regional (IGN)",
        expanded="0",
        checked="Qt::Unchecked",
    )
    for spec in REGIONAL_LAYERS:
        ET.SubElement(
            grp_regional,
            "layer-tree-layer",
            id=spec.layer_id,
            name=spec.label,
            source=spec.datasource,
            providerKey="postgres",
            checked="Qt::Unchecked",
            expanded="0",
        )

    ET.SubElement(root_tree, "custom-order", enabled="0")

    # Orden de dibujo (puntos arriba, líneas en medio, polígonos abajo)
    layer_order = ET.SubElement(qgis, "layerorder")
    for spec in all_vector_layers:
        ET.SubElement(layer_order, "layer", id=spec.layer_id)
    ET.SubElement(layer_order, "layer", id=wms_id)

    # Capas del proyecto (<projectlayers>)
    project_layers = ET.SubElement(qgis, "projectlayers")
    for spec in all_vector_layers:
        ml = ET.SubElement(
            project_layers,
            "maplayer",
            type="vector",
            geometry=spec.qgis_geom,
            wkbType=spec.pg_geom_type,
            autoRefreshEnabled="0",
            simplifyDrawingHints="0" if spec.qgis_geom == "Point" else "1",
            readOnly="0",
            hasScaleBasedVisibilityFlag="0",
        )
        ET.SubElement(ml, "id").text = spec.layer_id
        ET.SubElement(ml, "datasource").text = spec.datasource
        ET.SubElement(ml, "layername").text = spec.label
        srs_el = ET.SubElement(ml, "srs")
        _append_spatialrefsys_4326(srs_el)
        ET.SubElement(ml, "provider", encoding="UTF-8").text = "postgres"
        _append_renderer(ml, spec)
        if spec.label_field:
            _append_simple_labeling(ml, spec.label_field)
            ml.set("labelsEnabled", "1")
        else:
            ml.set("labelsEnabled", "0")

    # Capa WMS opcional de referencia (IDE Posadas)
    wms_ml = ET.SubElement(
        project_layers,
        "maplayer",
        type="raster",
        autoRefreshEnabled="0",
        hasScaleBasedVisibilityFlag="0",
    )
    ET.SubElement(wms_ml, "id").text = wms_id
    ET.SubElement(wms_ml, "datasource").text = WMS_DATASOURCE
    ET.SubElement(wms_ml, "layername").text = "IDE Posadas — Delegaciones (WMS)"
    wms_srs = ET.SubElement(wms_ml, "srs")
    _append_spatialrefsys_4326(wms_srs)
    ET.SubElement(wms_ml, "provider").text = "wms"
    pipe = ET.SubElement(wms_ml, "pipe")
    ET.SubElement(
        pipe,
        "rasterrenderer",
        type="singlebandcolordata",
        band="1",
        alphaBand="-1",
        opacity="0.65",
    )

    # Propiedades básicas del proyecto
    props = ET.SubElement(qgis, "properties")
    measure = ET.SubElement(props, "Measurement")
    ET.SubElement(measure, "DistanceUnits", type="QString").text = "meters"
    ET.SubElement(measure, "AreaUnits", type="QString").text = "m2"
    spatial_ref = ET.SubElement(props, "SpatialRefSys")
    ET.SubElement(spatial_ref, "ProjectionsEnabled", type="int").text = "1"

    ET.indent(qgis, space="  ")
    xml_body = ET.tostring(qgis, encoding="unicode")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>\n"
        f"{xml_body}\n"
    )


def generate_qgz_and_verify() -> Tuple[float, float, float, float]:
    """Escribe proyecto_ae4.qgz y verifica integridad ZIP, XML y ausencia de secretos."""
    xml_content = build_qgis_project_xml()
    QGIS_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(QGIS_OUT_PATH, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(QGS_INTERNAL_NAME, xml_content.encode("utf-8"))

    # Verificación obligatoria post-escritura
    with zipfile.ZipFile(QGIS_OUT_PATH, mode="r") as zf:
        names = zf.namelist()
        if QGS_INTERNAL_NAME not in names:
            raise RuntimeError(f"Falta {QGS_INTERNAL_NAME} dentro de {QGIS_OUT_PATH}")
        raw_xml = zf.read(QGS_INTERNAL_NAME).decode("utf-8")

    lowered = raw_xml.lower()
    if "password" in lowered or "user=" in lowered:
        raise RuntimeError("Se detectó credencial o palabra prohibida en el XML de QGIS")

    parsed = ET.fromstring(raw_xml)
    layers_found = parsed.findall("./projectlayers/maplayer")
    if len(layers_found) != 18:
        raise RuntimeError(f"Cantidad inesperada de capas en .qgs: {len(layers_found)} (esperado 18)")

    return compute_posadas_extent_5348()


# -----------------------------------------------------------------------------
# 3. Modelo de metadatos de las 19 tablas (coincidente con sql/00_init.sql)
# -----------------------------------------------------------------------------


@dataclass
class ColumnDef:
    name: str
    sql_type: str
    constraints: str
    description: str
    badge: str = ""  # PK, FK, UQ, CHK, GEN, GEOM4326, GEOM5348


@dataclass
class TableDef:
    name: str
    zone: str  # regional | urbano | analitica
    source: str
    summary: str
    columns: List[ColumnDef]
    notes: List[str] = field(default_factory=list)


TABLES: List[TableDef] = [
    # --- ZONA 1: ESCALA REGIONAL (6 tablas) ---
    TableDef(
        name="paises",
        zone="regional",
        source="Natural Earth 50m (complemento IGN)",
        summary="Polígonos nacionales de Sudamérica para contexto geopolítico regional.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("codigo_iso3", "VARCHAR(3)", "NOT NULL, UNIQUE", "Código ISO 3166-1 alfa-3", "UQ"),
            ColumnDef("nombre", "VARCHAR(120)", "NOT NULL", "Nombre del país"),
            ColumnDef("subregion", "VARCHAR(80)", "NULL", "Subregión geográfica"),
            ColumnDef("poblacion", "BIGINT", "CHECK (poblacion >= 0)", "Población total", "CHK"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'Natural Earth 50m (complemento IGN)'", "Fuente oficial"),
            ColumnDef("geom", "GEOMETRY(MultiPolygon, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Límite nacional WGS84", "GEOM4326"),
        ],
        notes=["Índices GiST: idx_paises_geom_gist (geom) e idx_paises_geog_gist ((geom::geography))."],
    ),
    TableDef(
        name="provincias",
        zone="regional",
        source="IGN",
        summary="Jurisdicciones provinciales argentinas vinculadas a su país.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("codigo_indec", "VARCHAR(10)", "NOT NULL, UNIQUE", "Código INDEC provincial", "UQ"),
            ColumnDef("nombre", "VARCHAR(120)", "NOT NULL", "Nombre corto"),
            ColumnDef("nombre_completo", "VARCHAR(180)", "NULL", "Denominación oficial completa"),
            ColumnDef("region", "VARCHAR(60)", "NOT NULL", "Región geográfica (ej. NEA)"),
            ColumnDef("poblacion", "BIGINT", "CHECK (poblacion >= 0)", "Población provincial", "CHK"),
            ColumnDef("pais_id", "INTEGER", "NOT NULL, FK -> paises(id)", "País contenedor", "FK"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'IGN'", "Fuente oficial"),
            ColumnDef("geom", "GEOMETRY(MultiPolygon, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Límite provincial WGS84", "GEOM4326"),
        ],
        notes=["Índices GiST: idx_provincias_geom_gist e idx_provincias_geog_gist."],
    ),
    TableDef(
        name="departamentos",
        zone="regional",
        source="IGN",
        summary="Departamentos/partidos de Argentina vinculados a su provincia.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("codigo_indec", "VARCHAR(10)", "NOT NULL, UNIQUE", "Código INDEC departamental", "UQ"),
            ColumnDef("nombre", "VARCHAR(120)", "NOT NULL", "Nombre del departamento"),
            ColumnDef("nombre_completo", "VARCHAR(180)", "NULL", "Denominación completa"),
            ColumnDef("poblacion", "BIGINT", "CHECK (poblacion >= 0)", "Población departamental", "CHK"),
            ColumnDef("provincia_id", "INTEGER", "NOT NULL, FK -> provincias(id)", "Provincia contenedora", "FK"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'IGN'", "Fuente oficial"),
            ColumnDef("geom", "GEOMETRY(MultiPolygon, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Límite departamental WGS84", "GEOM4326"),
        ],
        notes=["Índices GiST: idx_departamentos_geom_gist e idx_departamentos_geog_gist."],
    ),
    TableDef(
        name="localidades",
        zone="regional",
        source="IGN-BAHRA",
        summary="Asentamientos y localidades BAHRA con jerarquía de capitales.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("codigo_bahra", "VARCHAR(30)", "NOT NULL, UNIQUE", "Código censal BAHRA", "UQ"),
            ColumnDef("nombre", "VARCHAR(150)", "NOT NULL", "Nombre de la localidad"),
            ColumnDef("tipo_asentamiento", "VARCHAR(80)", "NULL", "Categoría BAHRA"),
            ColumnDef("es_capital_nacional", "BOOLEAN", "NOT NULL DEFAULT FALSE", "Indicador capital nacional"),
            ColumnDef("es_capital_provincial", "BOOLEAN", "NOT NULL DEFAULT FALSE", "Indicador capital provincial"),
            ColumnDef("departamento_id", "INTEGER", "NOT NULL, FK -> departamentos(id)", "Departamento contenedor", "FK"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'IGN-BAHRA'", "Fuente oficial"),
            ColumnDef("geom", "GEOMETRY(Point, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Centroide puntual WGS84", "GEOM4326"),
        ],
        notes=["Índices GiST: idx_localidades_geom_gist e idx_localidades_geog_gist ((geom::geography))."],
    ),
    TableDef(
        name="cursos_agua",
        zone="regional",
        source="IGN",
        summary="Red hidrográfica regional (ríos y arroyos).",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("id_origen", "VARCHAR(50)", "NOT NULL, UNIQUE", "Identificador IGN de origen", "UQ"),
            ColumnDef("nombre", "VARCHAR(150)", "NOT NULL", "Nombre del curso hídrico"),
            ColumnDef("nombre_corto", "VARCHAR(120)", "NULL", "Nombre abreviado"),
            ColumnDef("categoria", "VARCHAR(60)", "NULL", "Clasificación hidrográfica"),
            ColumnDef("es_principal", "BOOLEAN", "NOT NULL DEFAULT FALSE", "Marca de curso principal"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'IGN'", "Fuente oficial"),
            ColumnDef("geom", "GEOMETRY(MultiLineString, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Traza lineal WGS84", "GEOM4326"),
        ],
        notes=["Índices GiST: idx_cursos_agua_geom_gist e idx_cursos_agua_geog_gist."],
    ),
    TableDef(
        name="rutas",
        zone="regional",
        source="IGN",
        summary="Red vial troncal nacional y provincial.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("id_origen", "VARCHAR(50)", "NOT NULL, UNIQUE", "Identificador IGN de origen", "UQ"),
            ColumnDef("nombre", "VARCHAR(120)", "NOT NULL", "Designación de ruta"),
            ColumnDef("numero_ruta", "VARCHAR(30)", "NULL", "Número de ruta"),
            ColumnDef("jurisdiccion", "VARCHAR(20)", "NOT NULL, CHECK IN ('nacional','provincial')", "Jurisdicción vial", "CHK"),
            ColumnDef("superficie_calzada", "INTEGER", "NULL", "Código de tipo de calzada IGN"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'IGN'", "Fuente oficial"),
            ColumnDef("geom", "GEOMETRY(MultiLineString, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Traza vial WGS84", "GEOM4326"),
        ],
        notes=["Índices GiST: idx_rutas_geom_gist e idx_rutas_geog_gist."],
    ),
    # --- ZONA 2: ESCALA URBANA POSADAS — IDE & OSM (9 tablas) ---
    TableDef(
        name="delegaciones",
        zone="urbano",
        source="IDE Posadas",
        summary="12 delegaciones municipales de Posadas con población censal 2022.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("id_ide", "VARCHAR(40)", "UNIQUE", "ID oficial IDE Posadas", "UQ"),
            ColumnDef("nombre", "VARCHAR(120)", "NOT NULL", "Nombre de delegación"),
            ColumnDef("descripcion", "VARCHAR(180)", "NULL", "Descripción administrativa"),
            ColumnDef("poblacion_2022", "INTEGER", "CHECK (poblacion_2022 >= 0)", "Población Censo 2022", "CHK"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'IDE Posadas'", "Fuente oficial"),
            ColumnDef("geom", "GEOMETRY(MultiPolygon, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Polígono WGS84", "GEOM4326"),
            ColumnDef("geom_m", "GEOMETRY(MultiPolygon, 5348)", "NULL (sincronizado por trigger)", "Polígono métrico POSGAR 2007 Faja 6", "GEOM5348"),
        ],
        notes=["Trigger trg_01_sync_geom_m; índices GiST sobre geom y geom_m."],
    ),
    TableDef(
        name="semaforos",
        zone="urbano",
        source="IDE Posadas",
        summary="Cruces semaforizados oficiales de Posadas (auditados en ediciones).",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("id_ide", "VARCHAR(40)", "UNIQUE", "ID oficial IDE Posadas", "UQ"),
            ColumnDef("nombre", "VARCHAR(200)", "NOT NULL", "Identificación del cruce"),
            ColumnDef("calle_1", "VARCHAR(120)", "NULL", "Arteria principal"),
            ColumnDef("calle_2", "VARCHAR(120)", "NULL", "Arteria transversal"),
            ColumnDef("estado", "VARCHAR(60)", "NULL", "Estado operativo"),
            ColumnDef("centralizado", "VARCHAR(20)", "NULL", "Integración a central semafórica"),
            ColumnDef("peatonales", "VARCHAR(20)", "NULL", "Presencia de semáforos peatonales"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'IDE Posadas'", "Fuente oficial"),
            ColumnDef("geom", "GEOMETRY(Point, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Ubicación WGS84", "GEOM4326"),
            ColumnDef("geom_m", "GEOMETRY(Point, 5348)", "NULL (sincronizado por trigger)", "Ubicación métrica EPSG:5348", "GEOM5348"),
        ],
        notes=["Triggers: trg_01_sync_geom_m (BEFORE) y trg_auditar_semaforos (AFTER DML -> auditoria_ediciones)."],
    ),
    TableDef(
        name="escuelas",
        zone="urbano",
        source="IDE Posadas",
        summary="Establecimientos educativos urbanos de Posadas.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("id_ide", "VARCHAR(40)", "UNIQUE", "ID oficial IDE Posadas", "UQ"),
            ColumnDef("cueanexo", "VARCHAR(30)", "NULL", "Código CUE-Anexo"),
            ColumnDef("nombre", "VARCHAR(220)", "NOT NULL", "Nombre del establecimiento"),
            ColumnDef("sector", "VARCHAR(40)", "NULL", "Gestión estatal o privada"),
            ColumnDef("calle", "VARCHAR(150)", "NULL", "Dirección vial"),
            ColumnDef("barrio", "VARCHAR(120)", "NULL", "Barrio de pertenencia"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'IDE Posadas'", "Fuente oficial"),
            ColumnDef("geom", "GEOMETRY(Point, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Ubicación WGS84", "GEOM4326"),
            ColumnDef("geom_m", "GEOMETRY(Point, 5348)", "NULL (sincronizado por trigger)", "Ubicación métrica EPSG:5348", "GEOM5348"),
        ],
        notes=["Trigger trg_01_sync_geom_m; índices GiST sobre geom y geom_m."],
    ),
    TableDef(
        name="paradas",
        zone="urbano",
        source="IDE Posadas",
        summary="Paradas de transporte público urbano con detalle de dársena.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("id_ide", "VARCHAR(40)", "UNIQUE", "ID oficial IDE Posadas", "UQ"),
            ColumnDef("codigo", "VARCHAR(60)", "NULL", "Código operativo de parada"),
            ColumnDef("nombre", "VARCHAR(220)", "NOT NULL", "Denominación de parada"),
            ColumnDef("barrio", "VARCHAR(120)", "NULL", "Barrio"),
            ColumnDef("activo", "VARCHAR(20)", "NULL", "Estado activo"),
            ColumnDef("darsena", "VARCHAR(20)", "NULL", "Existencia de dársena"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'IDE Posadas'", "Fuente oficial"),
            ColumnDef("geom", "GEOMETRY(Point, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Ubicación WGS84", "GEOM4326"),
            ColumnDef("geom_m", "GEOMETRY(Point, 5348)", "NULL (sincronizado por trigger)", "Ubicación métrica EPSG:5348", "GEOM5348"),
        ],
        notes=["Trigger trg_01_sync_geom_m; índices GiST sobre geom y geom_m."],
    ),
    TableDef(
        name="avenidas_mano_unica",
        zone="urbano",
        source="IDE Posadas",
        summary="Avenidas con circulación de sentido único en Posadas.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("id_ide", "VARCHAR(40)", "UNIQUE", "ID oficial IDE Posadas", "UQ"),
            ColumnDef("nombre", "VARCHAR(150)", "NOT NULL", "Nombre de avenida"),
            ColumnDef("sentido", "VARCHAR(60)", "NULL", "Sentido de circulación"),
            ColumnDef("vigente", "VARCHAR(10)", "NULL", "Vigencia normativa"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'IDE Posadas'", "Fuente oficial"),
            ColumnDef("geom", "GEOMETRY(MultiLineString, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Eje lineal WGS84", "GEOM4326"),
            ColumnDef("geom_m", "GEOMETRY(MultiLineString, 5348)", "NULL (sincronizado por trigger)", "Eje métrico EPSG:5348", "GEOM5348"),
        ],
        notes=["Trigger trg_01_sync_geom_m; índices GiST sobre geom y geom_m."],
    ),
    TableDef(
        name="asfalto_sobre_empedrado",
        zone="urbano",
        source="IDE Posadas",
        summary="Obras municipales de pavimentación asfáltica sobre empedrado.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("id_ide", "VARCHAR(40)", "UNIQUE", "ID oficial IDE Posadas", "UQ"),
            ColumnDef("nombre", "VARCHAR(180)", "NOT NULL", "Tramo intervenido"),
            ColumnDef("anio", "VARCHAR(20)", "NULL", "Año de ejecución"),
            ColumnDef("tipo_obra", "VARCHAR(120)", "NULL", "Tipología de obra"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'IDE Posadas'", "Fuente oficial"),
            ColumnDef("geom", "GEOMETRY(MultiLineString, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Eje lineal WGS84", "GEOM4326"),
            ColumnDef("geom_m", "GEOMETRY(MultiLineString, 5348)", "NULL (sincronizado por trigger)", "Eje métrico EPSG:5348", "GEOM5348"),
        ],
        notes=["Trigger trg_01_sync_geom_m; índices GiST sobre geom y geom_m."],
    ),
    TableDef(
        name="ciclovias",
        zone="urbano",
        source="IDE Posadas",
        summary="Red de ciclovías y bicisendas urbanas de Posadas.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("id_ide", "VARCHAR(40)", "UNIQUE", "ID oficial IDE Posadas", "UQ"),
            ColumnDef("nombre", "VARCHAR(180)", "NOT NULL", "Nombre de ciclovía"),
            ColumnDef("tramo", "TEXT", "NULL", "Descripción de tramo"),
            ColumnDef("anio", "INTEGER", "NULL", "Año de habilitación"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'IDE Posadas'", "Fuente oficial"),
            ColumnDef("geom", "GEOMETRY(MultiLineString, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Eje lineal WGS84", "GEOM4326"),
            ColumnDef("geom_m", "GEOMETRY(MultiLineString, 5348)", "NULL (sincronizado por trigger)", "Eje métrico EPSG:5348", "GEOM5348"),
        ],
        notes=["Trigger trg_01_sync_geom_m; índices GiST sobre geom y geom_m."],
    ),
    TableDef(
        name="calles",
        zone="urbano",
        source="OSM vía AITARA",
        summary="Red vial de calles normalizadas de Posadas reconstruida desde nodos OSM.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("osm_id", "BIGINT", "NOT NULL, UNIQUE", "Identificador OpenStreetMap", "UQ"),
            ColumnDef("nombre", "VARCHAR(180)", "NOT NULL", "Nombre de la calle"),
            ColumnDef("nombre_normalizado", "VARCHAR(180)", "NOT NULL, UNIQUE", "Clave textual normalizada", "UQ"),
            ColumnDef("aliases", "TEXT[]", "NULL", "Denominaciones alternativas"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'OSM vía AITARA'", "Fuente"),
            ColumnDef("geom", "GEOMETRY(MultiLineString, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Traza multitramo WGS84", "GEOM4326"),
            ColumnDef("geom_m", "GEOMETRY(MultiLineString, 5348)", "NULL (sincronizado por trigger)", "Traza métrica EPSG:5348", "GEOM5348"),
        ],
        notes=["Trigger trg_01_sync_geom_m; índices GiST sobre geom y geom_m."],
    ),
    TableDef(
        name="intersecciones",
        zone="urbano",
        source="OSM vía AITARA",
        summary="Nodos y rotondas de cruce entre arterias normalizadas de Posadas.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("osm_id", "BIGINT", "NOT NULL", "ID de nodo OpenStreetMap"),
            ColumnDef("nombre", "VARCHAR(240)", "NOT NULL", "Nombre del cruce"),
            ColumnDef("calle_1", "VARCHAR(140)", "NOT NULL", "Primera arteria"),
            ColumnDef("calle_2", "VARCHAR(140)", "NOT NULL", "Segunda arteria"),
            ColumnDef("calle_1_norm", "VARCHAR(140)", "NOT NULL, UNIQUE(calle_1_norm, calle_2_norm)", "Arteria 1 normalizada", "UQ"),
            ColumnDef("calle_2_norm", "VARCHAR(140)", "NOT NULL, UNIQUE(calle_1_norm, calle_2_norm)", "Arteria 2 normalizada", "UQ"),
            ColumnDef("subtipo", "VARCHAR(20)", "NOT NULL, CHECK IN ('nodo','rotonda')", "Tipo topológico", "CHK"),
            ColumnDef("nivel_drenaje", "VARCHAR(10)", "CHECK IN ('ALTO','MEDIO','BAJO')", "Nivel de drenaje asignado", "CHK"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'OSM vía AITARA'", "Fuente"),
            ColumnDef("geom", "GEOMETRY(Point, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Punto de cruce WGS84", "GEOM4326"),
            ColumnDef("geom_m", "GEOMETRY(Point, 5348)", "NULL (sincronizado por trigger)", "Punto métrico EPSG:5348", "GEOM5348"),
        ],
        notes=[
            "Restricción compuesta: CONSTRAINT uq_intersecciones_par UNIQUE (calle_1_norm, calle_2_norm).",
            "Referenciada por incidentes_viales.interseccion_id (<= 150 m vía trg_02_sync_incidente_nodos).",
        ],
    ),
    # --- ZONA 3: ANALÍTICA AITARA, CLIMA Y AUDITORÍA (4 tablas) ---
    TableDef(
        name="nodos_referencia_aitara",
        zone="analitica",
        source="AITARA (atributo experto)",
        summary="Nodos de corredores críticos AITARA con atributos expertos y nivel de drenaje.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("node_id", "VARCHAR(60)", "NOT NULL, UNIQUE", "Código de nodo AITARA", "UQ"),
            ColumnDef("nombre", "VARCHAR(180)", "NOT NULL", "Nombre del nodo/corredor"),
            ColumnDef("corridor_type", "VARCHAR(60)", "NOT NULL", "Tipología de corredor"),
            ColumnDef("lanes", "INTEGER", "CHECK (lanes > 0)", "Cantidad de carriles", "CHK"),
            ColumnDef("has_traffic_light", "BOOLEAN", "NULL", "Indicador experto de semáforo"),
            ColumnDef("has_bus_stop", "BOOLEAN", "NULL", "Indicador experto de parada"),
            ColumnDef("is_school_zone", "BOOLEAN", "NULL", "Indicador de entorno escolar"),
            ColumnDef("school_name", "VARCHAR(150)", "NULL", "Escuela asociada"),
            ColumnDef("nivel_drenaje", "VARCHAR(10)", "NOT NULL, CHECK IN ('ALTO','MEDIO','BAJO')", "Capacidad experta de drenaje", "CHK"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL DEFAULT 'AITARA (atributo experto)'", "Fuente"),
            ColumnDef("geom", "GEOMETRY(Point, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Ubicación WGS84", "GEOM4326"),
            ColumnDef("geom_m", "GEOMETRY(Point, 5348)", "NULL (sincronizado por trigger)", "Ubicación métrica EPSG:5348", "GEOM5348"),
        ],
        notes=["Referenciada por incidentes_viales.nodo_referencia_id (<= 500 m vía trg_02_sync_incidente_nodos)."],
    ),
    TableDef(
        name="incidentes_viales",
        zone="analitica",
        source="AITARA (reales + simulados)",
        summary="Hechos viales reales y simulados con enlace automático a intersecciones y nodos AITARA.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("id_origen", "VARCHAR(60)", "UNIQUE", "ID externo/simulación", "UQ"),
            ColumnDef("nombre", "VARCHAR(260)", "NOT NULL", "Título descriptivo del incidente"),
            ColumnDef("origen", "VARCHAR(15)", "NOT NULL, CHECK IN ('real','simulado')", "Separación estricta de origen", "CHK"),
            ColumnDef("fuente", "VARCHAR(80)", "NOT NULL", "Fuente del registro"),
            ColumnDef("fecha_evento", "TIMESTAMP", "NOT NULL", "Fecha y hora del siniestro"),
            ColumnDef("tipo_incidente", "VARCHAR(40)", "NOT NULL", "Tipología del siniestro"),
            ColumnDef("severidad", "INTEGER", "NOT NULL, CHECK (1..5)", "Escala de gravedad 1 a 5", "CHK"),
            ColumnDef("vehiculos", "TEXT[]", "NULL", "Vehículos involucrados"),
            ColumnDef("ubicacion_texto", "TEXT", "NULL", "Texto original de ubicación"),
            ColumnDef("llovia", "BOOLEAN", "NULL", "Indicador climático (NULL en reales)"),
            ColumnDef("precipitacion_mm_h", "NUMERIC(6,2)", "CHECK (precipitacion_mm_h >= 0)", "Intensidad de lluvia (mm/h)", "CHK"),
            ColumnDef("confianza", "NUMERIC(4,3)", "CHECK (confianza BETWEEN 0 AND 1)", "Confianza de geocodificación", "CHK"),
            ColumnDef("interseccion_id", "INTEGER", "FK -> intersecciones(id)", "Intersección OSM <= 150 m", "FK"),
            ColumnDef("nodo_referencia_id", "INTEGER", "FK -> nodos_referencia_aitara(id)", "Nodo experto <= 500 m", "FK"),
            ColumnDef("geom", "GEOMETRY(Point, 4326)", "NOT NULL, CHECK (ST_IsValid(geom))", "Ubicación WGS84", "GEOM4326"),
            ColumnDef("geom_m", "GEOMETRY(Point, 5348)", "NULL (sincronizado por trigger)", "Ubicación métrica EPSG:5348", "GEOM5348"),
        ],
        notes=[
            "Triggers: trg_01_sync_geom_m -> trg_02_sync_incidente_nodos (BEFORE) y trg_auditar_incidentes (AFTER).",
        ],
    ),
    TableDef(
        name="exposicion_clima",
        zone="analitica",
        source="AITARA (simulado/exposición)",
        summary="Horas de exposición climática para normalizar tasas lluvia vs. seco.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("condicion", "VARCHAR(20)", "NOT NULL, UNIQUE, CHECK IN ('lluvia','seco')", "Condición meteorológica", "UQ"),
            ColumnDef("horas_nodo_totales", "INTEGER", "NOT NULL, CHECK (> 0)", "Horas acumuladas totales", "CHK"),
            ColumnDef("nodos_observados", "INTEGER", "NOT NULL DEFAULT 7, CHECK (> 0)", "Cantidad de nodos base", "CHK"),
            ColumnDef("horas_por_nodo", "NUMERIC(10,2)", "GENERATED ALWAYS AS (horas_nodo_totales::NUMERIC / nodos_observados) STORED", "Horas normalizadas por nodo", "GEN"),
            ColumnDef("periodo_inicio", "DATE", "NOT NULL DEFAULT '2023-01-01'", "Inicio de ventana"),
            ColumnDef("periodo_fin", "DATE", "NOT NULL DEFAULT '2025-12-31'", "Fin de ventana"),
        ],
        notes=["Tabla alfanumérica usada como denominador de tasas en 03_consultas_autoria.sql (Autoría 2A y 2C)."],
    ),
    TableDef(
        name="auditoria_ediciones",
        zone="analitica",
        source="Triggers PL/pgSQL (fn_auditar_edicion)",
        summary="Bitácora inmutable de INSERT, UPDATE y DELETE sobre semaforos e incidentes_viales.",
        columns=[
            ColumnDef("id", "INTEGER", "PK, GENERATED ALWAYS AS IDENTITY", "Identificador único", "PK"),
            ColumnDef("tabla_nombre", "VARCHAR(80)", "NOT NULL", "Tabla auditada"),
            ColumnDef("operacion", "VARCHAR(10)", "NOT NULL, CHECK IN ('INSERT','UPDATE','DELETE')", "Operación DML", "CHK"),
            ColumnDef("registro_id", "INTEGER", "NULL", "ID del registro afectado"),
            ColumnDef("usuario", "VARCHAR(80)", "NOT NULL DEFAULT current_user", "Rol PostgreSQL ejecutor"),
            ColumnDef("fecha_hora", "TIMESTAMPTZ", "NOT NULL DEFAULT now()", "Marca temporal con zona"),
            ColumnDef("detalle", "JSONB", "NULL", "Payload con nombre, geom_wkt, anterior y nuevo"),
        ],
        notes=["Poblada automáticamente por trg_auditar_semaforos y trg_auditar_incidentes."],
    ),
]


# -----------------------------------------------------------------------------
# 4. Generación del Diagrama DER (matplotlib Agg -> outputs/der_sig_ae4.png)
# -----------------------------------------------------------------------------


ZONE_PALETTE = {
    "regional": {
        "bg": "#EFF6FF",
        "border": "#1D4ED8",
        "header": "#1E3A8A",
        "card_bg": "#FFFFFF",
        "card_edge": "#3B82F6",
        "title": "ZONA 1 — ESCALA REGIONAL (IGN / BAHRA / Natural Earth 50m)\nEPSG:4326 (geom) + Índice Funcional GiST (geom::geography)",
    },
    "urbano": {
        "bg": "#ECFDF5",
        "border": "#047857",
        "header": "#065F46",
        "card_bg": "#FFFFFF",
        "card_edge": "#10B981",
        "title": "ZONA 2 — ESCALA URBANA POSADAS (IDE Posadas & OpenStreetMap)\nDual SRID: geom (EPSG:4326) + geom_m (EPSG:5348 POSGAR 2007 Faja 6) vía trg_01_sync_geom_m",
    },
    "analitica": {
        "bg": "#FFFBEB",
        "border": "#B45309",
        "header": "#92400E",
        "card_bg": "#FFFFFF",
        "card_edge": "#F59E0B",
        "title": "ZONA 3 — ANALÍTICA AITARA, CLIMA Y AUDITORÍA\nFKs espaciales automáticas (trg_02_sync_incidente_nodos) + Triggers de auditoría",
    },
}


def _short_col_label(col: ColumnDef) -> str:
    prefix_parts: List[str] = []
    if col.badge == "PK":
        prefix_parts.append("[PK]")
    elif col.badge == "FK":
        prefix_parts.append("[FK]")
    elif col.badge == "UQ":
        prefix_parts.append("[UQ]")
    elif col.badge == "CHK":
        prefix_parts.append("[CHK]")
    elif col.badge == "GEN":
        prefix_parts.append("[GEN]")
    elif col.badge == "GEOM4326":
        prefix_parts.append("[4326]")
    elif col.badge == "GEOM5348":
        prefix_parts.append("[5348]")
    prefix = " ".join(prefix_parts)
    sql_t = col.sql_type
    if sql_t.startswith("GEOMETRY(") and sql_t.endswith(")"):
        sql_t = sql_t[len("GEOMETRY(") : -1]
    short_type = (
        sql_t.replace("MultiPolygon, ", "MPoly ")
        .replace("MultiLineString, ", "MLine ")
        .replace("Point, ", "Pt ")
        .replace("VARCHAR", "VC")
        .replace("INTEGER", "INT")
        .replace("BOOLEAN", "BOOL")
        .replace("TIMESTAMPTZ", "TSTZ")
        .replace("TIMESTAMP", "TS")
        .replace("NUMERIC", "NUM")
    )
    if prefix:
        return f"{prefix} {col.name} : {short_type}"
    return f"  {col.name} : {short_type}"


def _draw_entity_box(
    ax: plt.Axes,
    table: TableDef,
    x: float,
    y: float,
    w: float,
    h: float,
    palette: Dict[str, str],
    header_h: float = 2.05,
    font_size: float = 6.2,
    tag_note: str = "",
) -> Tuple[float, float, float, float]:
    """Dibuja una tarjeta de entidad con cabecera y listado de columnas."""
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.15,rounding_size=0.45",
        linewidth=1.35,
        edgecolor=palette["card_edge"],
        facecolor=palette["card_bg"],
        zorder=3,
    )
    ax.add_patch(box)

    header = FancyBboxPatch(
        (x, y + h - header_h),
        w,
        header_h,
        boxstyle="round,pad=0.15,rounding_size=0.35",
        linewidth=0,
        facecolor=palette["header"],
        zorder=4,
    )
    ax.add_patch(header)

    title_txt = table.name if not tag_note else f"{table.name}  ({tag_note})"
    ax.text(
        x + w / 2.0,
        y + h - header_h / 2.0,
        title_txt,
        ha="center",
        va="center",
        fontsize=font_size + 1.1,
        fontweight="bold",
        color="#FFFFFF",
        family="DejaVu Sans",
        zorder=5,
    )

    body_top = y + h - header_h - 0.35
    body_bottom = y + 0.3
    n_cols = len(table.columns)
    step = (body_top - body_bottom) / max(n_cols, 1)

    for idx, col in enumerate(table.columns):
        cy = body_top - (idx + 0.45) * step
        label = _short_col_label(col)
        color = "#0F172A"
        weight = "normal"
        if col.badge == "PK":
            color = "#1E3A8A"
            weight = "bold"
        elif col.badge == "FK":
            color = "#9A3412"
            weight = "bold"
        elif col.badge in ("GEOM4326", "GEOM5348"):
            color = "#065F46"
            weight = "bold"
        elif col.badge in ("UQ", "GEN"):
            color = "#4338CA"
        ax.text(
            x + 0.35,
            cy,
            label,
            ha="left",
            va="center",
            fontsize=font_size,
            fontweight=weight,
            color=color,
            family="DejaVu Sans Mono",
            zorder=5,
        )

    return x, y, w, h


def _draw_arrow(
    ax: plt.Axes,
    start: Tuple[float, float],
    end: Tuple[float, float],
    label: str,
    color: str,
    dashed: bool = False,
    rad: float = 0.0,
    label_offset: Tuple[float, float] = (0.0, 0.0),
) -> None:
    style = "dashed" if dashed else "solid"
    arrow = FancyArrowPatch(
        start,
        end,
        connectionstyle=f"arc3,rad={rad}",
        arrowstyle="-|>,head_length=6.5,head_width=3.8",
        linewidth=1.55,
        linestyle=style,
        color=color,
        zorder=6,
    )
    ax.add_patch(arrow)
    mx = (start[0] + end[0]) / 2.0 + label_offset[0]
    my = (start[1] + end[1]) / 2.0 + label_offset[1]
    if label:
        ax.text(
            mx,
            my,
            label,
            ha="center",
            va="center",
            fontsize=6.1,
            fontweight="bold",
            color=color,
            bbox={
                "boxstyle": "round,pad=0.22",
                "facecolor": "#FFFFFF",
                "edgecolor": color,
                "linewidth": 0.85,
                "alpha": 0.95,
            },
            zorder=7,
        )


def generate_der_png() -> None:
    """Dibuja y exporta el DER completo en alta resolución (outputs/der_sig_ae4.png)."""
    table_by_name: Dict[str, TableDef] = {t.name: t for t in TABLES}

    fig, ax = plt.subplots(figsize=(24, 16.5), dpi=250)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 68)
    ax.axis("off")
    fig.patch.set_facecolor("#F8FAFC")

    # Encabezado principal
    banner = FancyBboxPatch(
        (1.2, 63.3),
        97.6,
        3.9,
        boxstyle="round,pad=0.2,rounding_size=0.6",
        facecolor="#0F172A",
        edgecolor="#334155",
        linewidth=1.5,
        zorder=2,
    )
    ax.add_patch(banner)
    ax.text(
        50.0,
        65.85,
        "MODELO ENTIDAD-RELACIÓN ESPACIAL — ESQUEMA sig_ae4 (PostgreSQL 16 + PostGIS 3.4)",
        ha="center",
        va="center",
        fontsize=14.5,
        fontweight="bold",
        color="#FFFFFF",
        family="DejaVu Sans",
        zorder=3,
    )
    ax.text(
        50.0,
        64.15,
        "19 Tablas: 6 Regionales (IGN/NE) · 11 Urbanas Posadas (IDE/OSM/AITARA) · 2 Alfanuméricas/Auditoría  |  "
        "Dual SRID: EPSG:4326 (geom) + EPSG:5348 (geom_m) + GiST (geom::geography)",
        ha="center",
        va="center",
        fontsize=9.2,
        color="#CBD5E1",
        family="DejaVu Sans",
        zorder=3,
    )

    # Contenedores de las 3 zonas
    zone_boxes = {
        "regional": (1.2, 7.6, 26.0, 54.6),
        "urbano": (28.2, 7.6, 37.8, 54.6),
        "analitica": (69.8, 7.6, 29.0, 54.6),
    }
    for zkey, (zx, zy, zw, zh) in zone_boxes.items():
        pal = ZONE_PALETTE[zkey]
        zpatch = FancyBboxPatch(
            (zx, zy),
            zw,
            zh,
            boxstyle="round,pad=0.2,rounding_size=0.7",
            facecolor=pal["bg"],
            edgecolor=pal["border"],
            linewidth=1.8,
            zorder=1,
        )
        ax.add_patch(zpatch)
        ax.text(
            zx + zw / 2.0,
            zy + zh - 1.35,
            pal["title"],
            ha="center",
            va="center",
            fontsize=7.8,
            fontweight="bold",
            color=pal["header"],
            family="DejaVu Sans",
            zorder=2,
        )

    coords: Dict[str, Tuple[float, float, float, float]] = {}

    # --- ZONA 1: REGIONAL ---
    pal1 = ZONE_PALETTE["regional"]
    coords["paises"] = _draw_entity_box(ax, table_by_name["paises"], 2.1, 49.3, 12.0, 9.5, pal1, font_size=5.8)
    coords["provincias"] = _draw_entity_box(ax, table_by_name["provincias"], 2.1, 35.7, 12.0, 10.6, pal1, font_size=5.8)
    coords["departamentos"] = _draw_entity_box(ax, table_by_name["departamentos"], 2.1, 22.8, 12.0, 9.9, pal1, font_size=5.8)
    coords["localidades"] = _draw_entity_box(ax, table_by_name["localidades"], 2.1, 8.9, 12.0, 10.9, pal1, font_size=5.8)

    coords["cursos_agua"] = _draw_entity_box(ax, table_by_name["cursos_agua"], 14.9, 41.5, 11.7, 11.2, pal1, font_size=5.8)
    coords["rutas"] = _draw_entity_box(ax, table_by_name["rutas"], 14.9, 25.5, 11.7, 11.2, pal1, font_size=5.8)

    # Nota técnica Zona 1
    note1 = FancyBboxPatch(
        (14.9, 9.2),
        11.7,
        12.5,
        boxstyle="round,pad=0.2,rounding_size=0.5",
        facecolor="#DBEAFE",
        edgecolor="#2563EB",
        linewidth=1.1,
        zorder=3,
    )
    ax.add_patch(note1)
    ax.text(
        20.75,
        15.45,
        "CRITERIO MÉTRICO REGIONAL\n"
        "• Solo geom (EPSG:4326)\n"
        "• Distancias/áreas geodésicas\n"
        "  vía geom::geography (m / km²)\n"
        "• Índice funcional GiST:\n"
        "  USING GIST ((geom::geography))\n"
        "• Validación CHECK ST_IsValid\n"
        "• 04_indices_benchmark.sql",
        ha="center",
        va="center",
        fontsize=6.2,
        color="#1E3A8A",
        family="DejaVu Sans",
        zorder=4,
    )

    # --- ZONA 2: URBANO POSADAS (3x3) ---
    pal2 = ZONE_PALETTE["urbano"]
    col_xs = [29.0, 41.3, 53.6]
    cw = 11.4

    # Fila superior (y=46.8..58.9)
    coords["delegaciones"] = _draw_entity_box(ax, table_by_name["delegaciones"], col_xs[0], 46.8, cw, 12.0, pal2, font_size=5.6)
    coords["escuelas"] = _draw_entity_box(ax, table_by_name["escuelas"], col_xs[1], 45.6, cw, 13.2, pal2, font_size=5.6)
    coords["semaforos"] = _draw_entity_box(ax, table_by_name["semaforos"], col_xs[2], 44.8, cw, 14.0, pal2, font_size=5.6)

    # Fila media (y=29.5..42.9)
    coords["paradas"] = _draw_entity_box(ax, table_by_name["paradas"], col_xs[0], 29.5, cw, 13.4, pal2, font_size=5.6)
    coords["avenidas_mano_unica"] = _draw_entity_box(ax, table_by_name["avenidas_mano_unica"], col_xs[1], 30.8, cw, 12.1, pal2, font_size=5.6)
    coords["asfalto_sobre_empedrado"] = _draw_entity_box(ax, table_by_name["asfalto_sobre_empedrado"], col_xs[2], 30.8, cw, 12.1, pal2, font_size=5.6)

    # Fila inferior (y=9.0..27.2)
    coords["ciclovias"] = _draw_entity_box(ax, table_by_name["ciclovias"], col_xs[0], 13.4, cw, 12.2, pal2, font_size=5.6)
    coords["calles"] = _draw_entity_box(ax, table_by_name["calles"], col_xs[1], 13.4, cw, 12.2, pal2, font_size=5.6)
    coords["intersecciones"] = _draw_entity_box(ax, table_by_name["intersecciones"], col_xs[2], 9.0, cw, 18.2, pal2, font_size=5.5)

    # Nota de cruces espaciales dentro de Zona 2 (bajo ciclovias + calles, sin tocar intersecciones)
    ax.text(
        40.85,
        10.2,
        "Cruces espaciales urbanos en geom_m (EPSG:5348):\n"
        "ST_DWithin / ST_Within / <-> (KNN) sobre índices GiST geom_m",
        ha="center",
        va="center",
        fontsize=5.8,
        fontweight="bold",
        color="#065F46",
        bbox={"boxstyle": "round,pad=0.28", "facecolor": "#D1FAE5", "edgecolor": "#059669", "linewidth": 0.9},
        zorder=4,
    )

    # --- ZONA 3: ANALÍTICA AITARA, CLIMA & AUDITORÍA ---
    pal3 = ZONE_PALETTE["analitica"]
    coords["auditoria_ediciones"] = _draw_entity_box(
        ax, table_by_name["auditoria_ediciones"], 70.6, 45.8, 12.5, 12.8, pal3, font_size=5.6
    )
    coords["exposicion_clima"] = _draw_entity_box(
        ax, table_by_name["exposicion_clima"], 85.9, 45.8, 12.1, 12.8, pal3, font_size=5.5
    )
    coords["incidentes_viales"] = _draw_entity_box(
        ax, table_by_name["incidentes_viales"], 70.6, 9.2, 12.5, 29.0, pal3, font_size=5.5
    )
    coords["nodos_referencia_aitara"] = _draw_entity_box(
        ax, table_by_name["nodos_referencia_aitara"], 85.9, 13.5, 12.1, 24.7, pal3, font_size=5.5
    )

    # --- FLECHAS FK (1 : N) ---
    # Regional hierarchy
    _draw_arrow(ax, (8.1, 49.3), (8.1, 46.3), "1:N pais_id", "#1D4ED8", label_offset=(2.6, 0.0))
    _draw_arrow(ax, (8.1, 35.7), (8.1, 32.7), "1:N provincia_id", "#1D4ED8", label_offset=(3.1, 0.0))
    _draw_arrow(ax, (8.1, 22.8), (8.1, 19.8), "1:N departamento_id", "#1D4ED8", label_offset=(3.4, 0.0))

    # incidentes_viales -> intersecciones (FK interseccion_id vía trg_02 <= 150 m)
    _draw_arrow(
        ax,
        (70.6, 15.2),
        (65.0, 15.2),
        "",
        "#B45309",
    )
    ax.text(
        67.8,
        18.2,
        "FK\ninterseccion_id\n(<=150 m)",
        ha="center",
        va="center",
        fontsize=5.3,
        fontweight="bold",
        color="#9A3412",
        bbox={"boxstyle": "round,pad=0.2", "facecolor": "#FFFFFF", "edgecolor": "#B45309", "linewidth": 0.85},
        zorder=7,
    )

    # incidentes_viales -> nodos_referencia_aitara (FK nodo_referencia_id vía trg_02 <= 500 m)
    _draw_arrow(
        ax,
        (83.1, 24.5),
        (85.9, 24.5),
        "",
        "#B45309",
    )
    ax.text(
        84.5,
        28.2,
        "FK\nnodo_ref\n(<=500m)",
        ha="center",
        va="center",
        fontsize=4.9,
        fontweight="bold",
        color="#9A3412",
        bbox={"boxstyle": "round,pad=0.16", "facecolor": "#FFFFFF", "edgecolor": "#B45309", "linewidth": 0.85},
        zorder=7,
    )

    # --- FLECHAS DE TRIGGERS DE AUDITORÍA (discontinuas) ---
    # semaforos -> auditoria_ediciones
    _draw_arrow(
        ax,
        (65.0, 52.2),
        (70.6, 52.2),
        "",
        "#DC2626",
        dashed=True,
    )
    ax.text(
        67.8,
        55.2,
        "TRG\nauditar\nsemaforos",
        ha="center",
        va="center",
        fontsize=5.3,
        fontweight="bold",
        color="#B91C1C",
        bbox={"boxstyle": "round,pad=0.2", "facecolor": "#FEF2F2", "edgecolor": "#DC2626", "linewidth": 0.85},
        zorder=7,
    )

    # incidentes_viales -> auditoria_ediciones
    _draw_arrow(
        ax,
        (76.85, 38.2),
        (76.85, 45.8),
        "TRG trg_auditar_incidentes (INSERT/UPDATE/DELETE)",
        "#DC2626",
        dashed=True,
        label_offset=(0.0, 0.0),
    )

    # --- LEYENDA INFERIOR ---
    legend = FancyBboxPatch(
        (1.2, 1.0),
        97.6,
        5.5,
        boxstyle="round,pad=0.2,rounding_size=0.5",
        facecolor="#FFFFFF",
        edgecolor="#64748B",
        linewidth=1.3,
        zorder=2,
    )
    ax.add_patch(legend)
    ax.text(
        2.2,
        5.35,
        "LEYENDA TÉCNICA DEL MODELO (00_init.sql + 04_indices_benchmark.sql)",
        ha="left",
        va="center",
        fontsize=8.2,
        fontweight="bold",
        color="#0F172A",
        zorder=3,
    )
    legend_items = [
        "[PK] Primary Key (INTEGER GENERATED ALWAYS AS IDENTITY)",
        "[FK] Foreign Key 1:N (flecha continua azul/ámbar)",
        "[UQ] Restricción UNIQUE (incluye uq_intersecciones_par)",
        "[CHK] Restricción CHECK (ST_IsValid, origen, severidad 1..5, drenaje)",
        "[GEN] Columna generada STORED (horas_por_nodo)",
        "[4326] GEOMETRY WGS84 (intercambio, WFS, QGIS + GiST geography)",
        "[5348] GEOMETRY POSGAR 2007 Faja 6 (m) vía trg_01_sync_geom_m",
        "TRG (flecha discontinua roja): trg_02_sync_incidente_nodos + trg_auditar_* -> JSONB",
    ]
    for i, item in enumerate(legend_items):
        col_i = i % 4
        row_i = i // 4
        lx = 2.2 + col_i * 24.2
        ly = 3.6 - row_i * 1.6
        ax.text(
            lx,
            ly,
            item,
            ha="left",
            va="center",
            fontsize=6.8,
            color="#334155",
            family="DejaVu Sans",
            zorder=3,
        )

    DER_PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(DER_PNG_PATH, dpi=250, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


# -----------------------------------------------------------------------------
# 5. Generación de documentación DER en Markdown (docs/DER_sig_ae4.md)
# -----------------------------------------------------------------------------


def _mermaid_type(sql_type: str) -> str:
    clean = (
        sql_type.replace("[]", "_array")
        .replace("(", "_")
        .replace(")", "")
        .replace(", ", "_")
        .replace(",", "_")
        .replace(" ", "_")
    )
    return clean


def _mermaid_key(badge: str) -> str:
    if badge == "PK":
        return "PK"
    if badge == "FK":
        return "FK"
    if badge == "UQ":
        return "UK"
    return ""


def generate_der_markdown() -> None:
    """Genera ae4_sig/docs/DER_sig_ae4.md con Mermaid erDiagram y diccionario completo."""
    lines: List[str] = [
        "# Modelo Entidad-Relación Espacial (`sig_ae4`)",
        "",
        "Documentación estructural de las **19 tablas** del esquema productivo `sig_ae4` "
        "(PostgreSQL 16 + PostGIS 3.4), correspondiente exactamente a [`sql/00_init.sql`](../sql/00_init.sql). "
        "Además existe el esquema auxiliar `staging` para ingesta cruda previa a la normalización.",
        "",
        "## Arquitectura de Sistemas de Referencia y Triggers",
        "",
        "- **`geom` (`EPSG:4326`, WGS 84 geográfico)**: presente en las 17 tablas espaciales para intercambio WFS/GeoJSON y visualización directa en QGIS.",
        "- **`geom_m` (`EPSG:5348`, POSGAR 2007 / Argentina Faja 6, metros)**: presente en las 11 tablas urbanas de Posadas y mantenido automáticamente `BEFORE INSERT OR UPDATE OF geom` por `trg_01_sync_geom_m` (`sig_ae4.fn_sync_geom_m()`).",
        "- **`geom::geography`**: criterio métrico geodésico utilizado en las 6 tablas regionales (`paises`, `provincias`, `departamentos`, `localidades`, `cursos_agua`, `rutas`) respaldado por índices funcionales `USING GIST ((geom::geography))` en [`sql/04_indices_benchmark.sql`](../sql/04_indices_benchmark.sql).",
        "- **Vínculo espacial automático de incidentes (`trg_02_sync_incidente_nodos`)**: al insertar o mover `incidentes_viales`, asigna la intersección OSM más cercana dentro de `150 m` (`interseccion_id`) y el nodo experto AITARA más cercano dentro de `500 m` (`nodo_referencia_id`).",
        "- **Auditoría DML (`trg_auditar_semaforos`, `trg_auditar_incidentes`)**: registra `INSERT`, `UPDATE` y `DELETE` en `sig_ae4.auditoria_ediciones` con payload JSONB (`nombre`, `geom_wkt`, `anterior`, `nuevo`).",
        "",
        "![Diagrama Entidad-Relación sig_ae4](../outputs/der_sig_ae4.png)",
        "",
        "## Diagrama Mermaid (`erDiagram`)",
        "",
        "```mermaid",
        "erDiagram",
        "    paises ||--o{ provincias : \"pais_id\"",
        "    provincias ||--o{ departamentos : \"provincia_id\"",
        "    departamentos ||--o{ localidades : \"departamento_id\"",
        "    intersecciones ||--o{ incidentes_viales : \"interseccion_id (<=150m)\"",
        "    nodos_referencia_aitara ||--o{ incidentes_viales : \"nodo_referencia_id (<=500m)\"",
        "    semaforos ||..o{ auditoria_ediciones : \"trg_auditar_semaforos\"",
        "    incidentes_viales ||..o{ auditoria_ediciones : \"trg_auditar_incidentes\"",
        "",
    ]

    for tbl in TABLES:
        lines.append(f"    {tbl.name} {{")
        for col in tbl.columns:
            mtype = _mermaid_type(col.sql_type)
            mkey = _mermaid_key(col.badge)
            comment = col.description.replace('"', "'")
            if mkey:
                lines.append(f'        {mtype} {col.name} {mkey} "{comment}"')
            else:
                lines.append(f'        {mtype} {col.name} "{comment}"')
        lines.append("    }")

    lines.extend(["```", "", "## Diccionario de Datos (19 Tablas)", ""])

    zone_headers = [
        ("regional", "1. Escala Regional — IGN / BAHRA / Natural Earth 50m (6 tablas)"),
        ("urbano", "2. Escala Urbana Posadas — IDE Posadas & OSM (9 tablas)"),
        ("analitica", "3. Analítica AITARA, Exposición Climática y Auditoría (4 tablas)"),
    ]

    for zone_key, zone_title in zone_headers:
        lines.append(f"### {zone_title}")
        lines.append("")
        for tbl in [t for t in TABLES if t.zone == zone_key]:
            lines.append(f"#### `sig_ae4.{tbl.name}`")
            lines.append("")
            lines.append(f"- **Fuente:** {tbl.source}")
            lines.append(f"- **Propósito:** {tbl.summary}")
            for n in tbl.notes:
                lines.append(f"- **Notas / Triggers / Índices:** {n}")
            lines.append("")
            lines.append("| Columna | Tipo SQL | Restricciones | Descripción |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for col in tbl.columns:
                lines.append(
                    f"| `{col.name}` | `{col.sql_type}` | {col.constraints} | {col.description} |"
                )
            lines.append("")

    DER_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    DER_MD_PATH.write_text("\n".join(lines), encoding="utf-8")


# -----------------------------------------------------------------------------
# 6. Punto de entrada
# -----------------------------------------------------------------------------


def main() -> int:
    xmin, ymin, xmax, ymax = generate_qgz_and_verify()
    generate_der_png()
    generate_der_markdown()

    print(f"[OK] QGIS .qgz generado y verificado: {QGIS_OUT_PATH}")
    print(f"     Extent EPSG:5348 -> xmin={xmin}, ymin={ymin}, xmax={xmax}, ymax={ymax}")
    print(f"[OK] DER PNG generado: {DER_PNG_PATH}")
    print(f"[OK] DER Markdown generado: {DER_MD_PATH} ({len(TABLES)} tablas documentadas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
