"""Deduplicación del mismo hecho reportado por medios distintos."""

import json
from datetime import datetime
from itertools import combinations

from src.contracts import IncidenteSilver
from src.ingesta.deduplicador import buscar_duplicado, es_mismo_hecho, parsear_fecha
from src.ingesta.lector import procesar_noticia
from src.ingesta.recolector import _fecha_publicacion_html
from src.warehouse.db import SILVER_JSONL_PATH, get_db_connection, init_schema, seed_reference_data

EXISTENTE = {
    "id": "inc-pos-003", "fuente": "primera_edicion", "titulo": "Choque sobre avenida Quaranta",
    "url": "https://primeraedicion.example/quaranta", "fecha_publicacion": "2026-11-06T08:21:08",
    "fecha_evento": "2026-11-06T00:30:00", "tipo_incidente": "choque", "severidad": 2,
    "vehiculos": ["auto", "moto"], "calle_1": "Av. Quaranta", "calle_2": "Av. Tomás Guido",
    "ubicacion_texto": "Av. Quaranta y Tomás Guido", "lat": -27.401150, "lon": -55.917214,
    "confianza": 0.99, "estado_verificacion": "curado", "resumen": "Choque.", "origen": "real",
}


class LectorFijo:
    """Devuelve siempre el incidente indicado, sin llamar a Gemini."""

    def __init__(self, **campos):
        self.campos = campos

    def estructurar_noticia(self, articulo):
        base = {**EXISTENTE, "id": articulo["id"], "fuente": articulo["fuente"], "url": articulo["url"],
                "titulo": articulo["titulo"], "fecha_evento": None,
                "fecha_publicacion": parsear_fecha(articulo["fecha_publicacion"])}
        return IncidenteSilver(**{**base, **self.campos})


def _articulo(fuente, url, fecha):
    return {"id": f"inc-web-{fuente}", "fuente": fuente, "url": url, "titulo": f"Nota de {fuente}",
            "texto": "", "fecha_publicacion": fecha}


def _db():
    db = get_db_connection()
    init_schema(db)
    seed_reference_data(db)
    return db


def _ruta_con_existente(tmp_path):
    ruta = tmp_path / "incidentes.jsonl"
    ruta.write_text(json.dumps(EXISTENTE, ensure_ascii=False) + "\n", encoding="utf-8")
    return ruta


def test_mismo_hecho_de_otro_medio_se_agrega_como_fuente(tmp_path):
    ruta = _ruta_con_existente(tmp_path)
    articulo = _articulo("misiones_online", "https://misionesonline.example/quaranta", "Fri, 06 Nov 2026 12:00:00 +0000")
    # 40 m del existente y con otro nombre de siniestro.
    lector = LectorFijo(lat=-27.40110, lon=-55.91760, tipo_incidente="atropello")

    estado, incidente = procesar_noticia(articulo, _db(), lector=lector, ruta=ruta)

    assert estado == "duplicado_medio"
    assert incidente["id"] == "inc-pos-003"
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 1
    assert json.loads(lineas[0])["fuentes_relacionadas"] == [
        {"fuente": "misiones_online", "url": articulo["url"], "titulo": "Nota de misiones_online"}]

    # La misma nota no se vuelve a procesar.
    estado, _ = procesar_noticia(articulo, _db(), lector=lector, ruta=ruta)
    assert estado == "duplicado_url"


def test_mismo_dia_en_otro_lugar_es_otro_hecho(tmp_path):
    ruta = _ruta_con_existente(tmp_path)
    articulo = _articulo("canal_12", "https://canal12.example/mitre", "2026-11-06T10:00:00")
    lector = LectorFijo(lat=-27.375151, lon=-55.891101, calle_1="Av. Mitre")

    estado, _ = procesar_noticia(articulo, _db(), lector=lector, ruta=ruta)

    assert estado == "nuevo"
    assert len(ruta.read_text(encoding="utf-8").splitlines()) == 2


def test_mismo_lugar_dias_despues_es_otro_hecho():
    nuevo = {**EXISTENTE, "id": "otro", "fecha_evento": None, "fecha_publicacion": "2026-11-11T09:00:00"}
    assert not es_mismo_hecho(nuevo, EXISTENTE)


def test_tipos_distintos_no_se_fusionan():
    nuevo = {**EXISTENTE, "id": "otro", "tipo_incidente": "anegamiento"}
    assert not es_mismo_hecho(nuevo, EXISTENTE)


def test_ubicaciones_indeterminadas_exigen_la_misma_calle():
    a = {**EXISTENTE, "tipo_ubicacion": "indeterminado", "lat": -27.367, "lon": -55.896, "calle_1": "Av. Lavalle"}
    b = {**a, "id": "otro", "calle_1": "Av. Mitre"}
    c = {**a, "id": "otro2", "calle_1": "avenida lavalle"}
    assert not es_mismo_hecho(b, a)
    assert es_mismo_hecho(c, a)


def test_simulados_no_absorben_noticias_reales():
    assert buscar_duplicado(EXISTENTE, [{**EXISTENTE, "id": "sim-1", "origen": "simulado"}]) is None


def test_incidentes_reales_guardados_no_son_duplicados_entre_si():
    reales = [json.loads(l) for l in SILVER_JSONL_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    pares = [(a["id"], b["id"]) for a, b in combinations(reales, 2) if es_mismo_hecho(a, b)]
    assert pares == []


def test_parsear_fecha_normaliza_a_hora_de_posadas():
    assert parsear_fecha("Fri, 06 Nov 2026 12:00:00 +0000") == datetime(2026, 11, 6, 9, 0)
    assert parsear_fecha("2026-11-06T12:00:00Z") == datetime(2026, 11, 6, 9, 0)
    assert parsear_fecha("2026-11-06T08:21:08") == datetime(2026, 11, 6, 8, 21, 8)
    assert parsear_fecha("no es una fecha") is None


def test_fecha_de_publicacion_desde_metaetiquetas():
    html = '<head><meta property="article:published_time" content="2026-11-06T08:21:08-03:00" /></head>'
    assert _fecha_publicacion_html(html) == "2026-11-06T08:21:08-03:00"
    assert _fecha_publicacion_html("<head></head>") is None
