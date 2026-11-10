"""Tests automatizados para el pipeline de ingesta, lector y deduplicación."""

import pytest
from src.ingesta.recolector import es_noticia_vial, _id_url
from src.ingesta.lector import AgenteLector, procesar_e_ingestar_noticia
from src.warehouse.db import get_db_connection, init_schema, seed_reference_data, load_silver_incidents_from_jsonl, SILVER_JSONL_PATH


def test_prefiltro_vial_detecta_incidentes():
    assert es_noticia_vial("Grave choque entre un auto y una moto en avenida Quaranta") is True
    assert es_noticia_vial("Vuelco en la travesía urbana de Posadas dejó dos lesionados") is True
    assert es_noticia_vial("Asfalto cedió y provocó corte vial en calle Santa Fe") is True
    # Noticias políticas / deportivas sin impacto vial deben ser descartadas
    assert es_noticia_vial("Se inauguró un nuevo centro cultural en Posadas con presencia de autoridades") is False
    assert es_noticia_vial("Guaraní Antonio Franco ganó el clásico de fútbol posadeño") is False


def test_lector_extrae_sin_inventar_calle2():
    lector = AgenteLector()
    art = {
        "id": "test-inc-001",
        "fuente": "test_media",
        "url": "https://test.misiones/noticia-1",
        "titulo": "Choque frontal sobre ex Ruta 213 frente al acceso a Country Los Naranjos",
        "texto": "Un Ford Fiesta y un Renault colisionaron frente al country Los Naranjos sobre avenida Alicia Moreau de Justo."
    }
    inc = lector.estructurar_noticia(art)
    assert inc.calle_1 == "Av. Alicia Moreau de Justo"
    assert inc.calle_2 is None
    assert inc.referencia_espacial == "Country Los Naranjos"
    assert abs(inc.lat - (-27.446188)) < 0.001
    assert abs(inc.lon - (-55.957563)) < 0.001
    assert inc.confianza >= 0.90


def test_deduplicacion_y_persistencia(tmp_path):
    db = get_db_connection()
    init_schema(db)
    seed_reference_data(db)
    load_silver_incidents_from_jsonl(db)

    lector = AgenteLector()
    art_duplicado = {
        "id": "inc-pos-001",
        "fuente": "primera_edicion",
        # URL de una noticia existente en el dataset semilla
        "url": "https://www.primeraedicion.com.ar/nota/101154937/choque-camioneta-estacionada-colision-en-fila-posadas/",
        "titulo": "Chocó a una camioneta estacionada y provocó una colisión en fila",
        "texto": "Texto de prueba"
    }

    # Debe ser ignorado por deduplicación
    res = procesar_e_ingestar_noticia(art_duplicado, db, lector=lector)
    assert res is None
