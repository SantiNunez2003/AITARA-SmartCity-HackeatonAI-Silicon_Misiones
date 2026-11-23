"""Descarga capas oficiales desde IGN WFS, IDE Posadas WFS y Natural Earth 50m.

Guarda los archivos crudos en `ae4_sig/datos_externos/` (no versionado).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List
import requests

OUT_DIR = Path(__file__).resolve().parents[1] / "datos_externos"
IGN_WFS = "https://wms.ign.gob.ar/geoserver/ows"
IDE_WFS = "https://www.ide.posadas.gob.ar/geoserver/ows"
NE_COUNTRIES_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_50m_admin_0_countries.geojson"
)

SOVEREIGN_SOUTH_AMERICA = {
    "Argentina",
    "Bolivia",
    "Brazil",
    "Chile",
    "Colombia",
    "Ecuador",
    "Guyana",
    "Paraguay",
    "Peru",
    "Suriname",
    "Uruguay",
    "Venezuela",
}


def get_with_retries(url: str, params: Dict[str, Any] | None = None, timeout: int = 45) -> requests.Response:
    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            last_err = exc
            print(f"  [reintento {attempt}/3] {url}: {exc}")
            time.sleep(2 * attempt)
    raise RuntimeError(f"Error descargando {url}: {last_err}")


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def download_wfs_geojson(
    base_url: str,
    type_name: str,
    out_file: Path,
    cql_filter: str | None = None,
    bbox: str | None = None,
    srs_name: str = "EPSG:4326",
    max_features: int | None = None,
) -> int:
    params: Dict[str, Any] = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": type_name,
        "outputFormat": "application/json",
        "srsName": srs_name,
    }
    if cql_filter:
        params["CQL_FILTER"] = cql_filter
    if bbox:
        params["bbox"] = bbox
    if max_features:
        params["maxFeatures"] = max_features

    resp = get_with_retries(base_url, params=params, timeout=60)
    data = resp.json()
    feats = data.get("features", [])
    total = data.get("totalFeatures") or len(feats)
    save_json(out_file, data)
    print(f"[OK] {out_file.name}: {len(feats)} features (total WFS={total})")
    return len(feats)


def download_natural_earth_south_america() -> int:
    resp = get_with_retries(NE_COUNTRIES_URL, timeout=60)
    raw = resp.json()
    filtered: List[Dict[str, Any]] = []
    for feat in raw.get("features", []):
        props = feat.get("properties", {})
        admin = props.get("ADMIN") or props.get("NAME")
        if props.get("CONTINENT") == "South America" and admin in SOVEREIGN_SOUTH_AMERICA:
            filtered.append(feat)

    out_data = {
        "type": "FeatureCollection",
        "name": "ne_50m_south_america_sovereign",
        "features": filtered,
    }
    out_file = OUT_DIR / "ne_paises_sudamerica.geojson"
    save_json(out_file, out_data)
    print(f"[OK] {out_file.name}: {len(filtered)} paises soberanos de Sudamerica")
    return len(filtered)


def download_ign_cursos_agua() -> int:
    # 1) Tramos completos de los 3 rios principales solicitados (e, f, g, i)
    p1 = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": "ign:lineas_de_aguas_continentales_perenne",
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "CQL_FILTER": "fna IN ('Río Paraná','Río Uruguay','Río Iguazú')",
    }
    r1 = get_with_retries(IGN_WFS, params=p1, timeout=60).json()

    # 2) Cursos nombrados dentro de Misiones + borde inmediato (afluentes)
    p2 = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": "ign:lineas_de_aguas_continentales_perenne",
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "CQL_FILTER": "BBOX(geom,-56.2,-28.2,-53.5,-25.4,'EPSG:4326') AND fna IS NOT NULL",
        "maxFeatures": 2000,
    }
    r2 = get_with_retries(IGN_WFS, params=p2, timeout=60).json()

    by_gid: Dict[Any, Dict[str, Any]] = {}
    for feat in r1.get("features", []):
        props = feat.get("properties", {})
        # Descartar homonimos del Rio Uruguay fuera de la Cuenca del Plata (ej. Patagonia/Andes)
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or []
        lons = [pt[0] for line in coords for pt in line] if geom.get("type") == "MultiLineString" else []
        if lons and max(lons) < -62.0:
            continue
        props["_es_principal"] = True
        by_gid[props.get("gid") or feat.get("id")] = feat

    for feat in r2.get("features", []):
        props = feat.get("properties", {})
        key = props.get("gid") or feat.get("id")
        if key not in by_gid:
            props["_es_principal"] = False
            by_gid[key] = feat

    out_data = {
        "type": "FeatureCollection",
        "name": "ign_cursos_agua",
        "features": list(by_gid.values()),
    }
    out_file = OUT_DIR / "ign_cursos_agua.geojson"
    save_json(out_file, out_data)
    print(f"[OK] {out_file.name}: {len(by_gid)} tramos hidrograficos (principales + Misiones)")
    return len(by_gid)


def download_ide_delegaciones_shapefile() -> None:
    params = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": "geonode:DELEGACIONES_MUNICIPALES_POSADAS_20250",
        "outputFormat": "shape-zip",
        "srsName": "EPSG:4326",
    }
    resp = get_with_retries(IDE_WFS, params=params, timeout=45)
    out_zip = OUT_DIR / "ide_delegaciones_shp.zip"
    out_zip.write_bytes(resp.content)
    print(f"[OK] {out_zip.name}: {len(resp.content)} bytes (para demo shp2pgsql)")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Descargando fuentes oficiales en {OUT_DIR} ...")

    download_natural_earth_south_america()

    # Capas IGN (escala regional)
    download_wfs_geojson(IGN_WFS, "ign:provincia", OUT_DIR / "ign_provincias.geojson")
    download_wfs_geojson(IGN_WFS, "ign:departamento", OUT_DIR / "ign_departamentos.geojson")
    download_wfs_geojson(IGN_WFS, "ign:localidad_bahra", OUT_DIR / "ign_localidades.geojson", max_features=5000)
    download_ign_cursos_agua()
    download_wfs_geojson(
        IGN_WFS,
        "ign:vial_nacional",
        OUT_DIR / "ign_vial_nacional.geojson",
        bbox="-60.0,-31.0,-53.5,-25.0,EPSG:4326",
    )
    download_wfs_geojson(
        IGN_WFS,
        "ign:vial_provincial",
        OUT_DIR / "ign_vial_provincial.geojson",
        bbox="-56.5,-28.5,-53.5,-25.4,EPSG:4326",
    )

    # Capas IDE Posadas (escala urbana)
    ide_layers = [
        ("geonode:DELEGACIONES_MUNICIPALES_POSADAS_20250", "ide_delegaciones.geojson"),
        ("geonode:Intersecciones_Semaforizadas20250", "ide_semaforos.geojson"),
        ("geonode:unidades_funcionales_educativas", "ide_escuelas.geojson"),
        ("geonode:Refugios_paradas__SIG_0", "ide_paradas.geojson"),
        ("geonode:manos_unicas", "ide_manos_unicas.geojson"),
        ("geonode:asfalto_sobreempedrado0", "ide_asfalto_sobre_empedrado.geojson"),
        ("geonode:bicisendas_ciclovias0", "ide_ciclovias.geojson"),
        ("geonode:radios_censales_2022_poblacion_hogares_vivien", "ide_radios_censales_2022.geojson"),
    ]
    for layer, fname in ide_layers:
        download_wfs_geojson(IDE_WFS, layer, OUT_DIR / fname)

    download_ide_delegaciones_shapefile()
    print("Descarga completa.")


if __name__ == "__main__":
    main()
