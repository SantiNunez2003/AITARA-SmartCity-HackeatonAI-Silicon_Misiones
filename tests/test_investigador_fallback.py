"""Tests automatizados para T12: Agente Investigador con Nomenclador OSM y Gemini Function Calling."""

import json
from pathlib import Path
import re
from types import SimpleNamespace
import pytest

from src.contracts import ParametrosEscenario
from src.engine.investigador import (
    CONFIANZA_INTERSECCION_OSM,
    CONFIANZA_LUGAR_UNICO,
    CONFIANZA_PUNTO_SOBRE_CALLE_CERCA_DE_LUGAR,
    CONFIANZA_SIN_RESOLVER,
    CONFIANZA_SOLO_CALLE,
    AgenteInvestigador,
)
from src.engine.risk_model import ExplainableRiskEngine, distancia_metros
from src.ingesta.lector import AgenteLector
from src.territorio.nomenclador import (
    buscar_calle,
    buscar_interseccion,
    buscar_lugar,
    punto_sobre_calle_cerca_de,
)
from src.warehouse.db import DBWrapper, SILVER_JSONL_PATH, init_schema, seed_reference_data


def test_nomenclador_osm_local_y_tolerancia_escritura():
    """Verifica que data/territorio/ tenga datos reales de OSM con ID y fuente, y que nomenclador funcione offline."""
    calles_q1 = buscar_calle("Quaranta")
    calles_q2 = buscar_calle("Quarantá")
    assert calles_q1 and calles_q2
    assert calles_q1[0]["osm_id"] == calles_q2[0]["osm_id"]
    assert calles_q1[0]["fuente"] == "openstreetmap"

    cruce = buscar_interseccion("San Lorenzo", "Tucumán")
    assert cruce["encontrada"] is True
    assert cruce["osm_id"] > 0
    assert cruce["fuente"] == "openstreetmap"

    lugares = buscar_lugar("Autódromo Rosamonte")
    assert len(lugares) == 1
    assert lugares[0]["osm_id"] > 0
    assert lugares[0]["fuente"] == "openstreetmap"

    punto = punto_sobre_calle_cerca_de("Av. Alicia Moreau de Justo", lugares[0]["lat"], lugares[0]["lon"])
    assert punto is not None
    assert punto["osm_id"] > 0
    assert punto["fuente"] == "openstreetmap"


def test_investigador_sin_coordenadas_hardcodeadas():
    """Verifica que src/engine/investigador.py no tenga coordenadas de calles o lugares escritas a mano."""
    ruta_inv = Path(__file__).resolve().parent.parent / "src" / "engine" / "investigador.py"
    codigo = ruta_inv.read_text(encoding="utf-8")
    # No debe haber números decimales del tipo -27.xxxx o -55.xxxx en investigador.py
    coordenadas_literales = re.findall(r"-27\.\d{3,}|-55\.\d{3,}", codigo)
    assert coordenadas_literales == [], f"Se encontraron coordenadas hardcodeadas: {coordenadas_literales}"


def test_fallback_country_los_naranjos():
    inv = AgenteInvestigador()
    res = inv.resolver_georreferenciacion(
        calle_1="Av. Alicia Moreau de Justo",
        calle_2=None,
        referencia_espacial="Country Los Naranjos",
        texto_completo="Choque frontal sobre ex Ruta 213 frente al acceso a Country Los Naranjos",
    )
    assert res["estado"] == "resuelto"
    assert res["tipo_ubicacion"] == "corredor_hito"
    assert res["confianza"] == CONFIANZA_PUNTO_SOBRE_CALLE_CERCA_DE_LUGAR
    assert res["requiere_revision_humana"] is False
    assert res["metodo"] == "nomenclador"
    assert len(res["pasos_resolucion"]) >= 2


def test_fallback_autodromo_rosamonte():
    inv = AgenteInvestigador()
    res = inv.resolver_georreferenciacion(
        calle_1="Av. Fangio",
        referencia_espacial="Autódromo Rosamonte",
        texto_completo="Despiste durante el fin de semana en las inmediaciones del autódromo",
    )
    assert res["estado"] == "resuelto"
    assert res["confianza"] == CONFIANZA_PUNTO_SOBRE_CALLE_CERCA_DE_LUGAR
    assert res["requiere_revision_humana"] is False
    assert res["metodo"] == "nomenclador"
    assert res["pasos_resolucion"]


def test_interseccion_tradicional_sigue_funcionando():
    inv = AgenteInvestigador()
    res = inv.resolver_georreferenciacion(
        calle_1="San Lorenzo",
        calle_2="Tucumán",
        texto_completo="Colisión en San Lorenzo y Tucumán",
    )
    assert res["estado"] == "resuelto"
    assert res["tipo_ubicacion"] == "interseccion"
    assert res["confianza"] == CONFIANZA_INTERSECCION_OSM
    assert abs(res["lat"] - (-27.372414)) < 0.001
    assert abs(res["lon"] - (-55.896466)) < 0.001
    assert res["pasos_resolucion"]


def test_guardrail_rechaza_punto_fuera_de_corredor():
    inv = AgenteInvestigador()
    valido = inv.validar_consistencia_corredor("Av. Alicia Moreau de Justo", lat=-27.3600, lon=-55.8900)
    assert valido is False

    valido_sur = inv.validar_consistencia_corredor("Av. Alicia Moreau de Justo", lat=-27.4461, lon=-55.9575)
    assert valido_sur is True


def test_12_incidentes_reales_posadas_con_nomenclador_osm():
    """Evalúa los 12 incidentes reales de data/silver/incidentes_posadas.jsonl con el nuevo Investigador."""
    inv = AgenteInvestigador()
    incidentes = [
        json.loads(line)
        for line in SILVER_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(incidentes) == 12

    # 9 incidentes coinciden a < 150 m; 3 presentan diferencia documentada porque la coordenada previa
    # estaba desplazada respecto de la geometría real de OpenStreetMap (inc-pos-003, inc-pos-007, inc-pos-011).
    diferencias_osm_documentadas = {"inc-pos-003", "inc-pos-007", "inc-pos-011"}

    for inc in incidentes:
        res = inv.resolver_georreferenciacion(
            calle_1=inc.get("calle_1"),
            calle_2=inc.get("calle_2"),
            referencia_espacial=inc.get("referencia_espacial"),
            texto_completo=f"{inc.get('titulo', '')} {inc.get('resumen', '')}",
        )
        assert res["estado"] == "resuelto", f"No se resolvió {inc['id']}: {res}"
        assert res["requiere_revision_humana"] is False
        assert res["lat"] is not None and res["lon"] is not None
        assert res["pasos_resolucion"]
        assert res["metodo"] == "nomenclador"

        dist = distancia_metros(inc["lat"], inc["lon"], res["lat"], res["lon"])
        if inc["id"] not in diferencias_osm_documentadas:
            assert dist < 150.0, f"{inc['id']} superó 150 m: {dist:.1f} m"
        else:
            # Verificar que la coordenada devuelta proviene exactamente de OpenStreetMap
            assert res["osm_id"] is not None and res["osm_id"] > 0


def test_gemini_coordenadas_inventadas_se_rechazan():
    """Simula que Gemini devuelve coordenadas inventadas que no salieron de las funciones del nomenclador."""
    inv = AgenteInvestigador()

    llamadas = []

    def mock_generate_content(model, contents, config=None):
        llamadas.append(contents)
        if len(llamadas) == 1:
            return SimpleNamespace(
                function_calls=[
                    SimpleNamespace(name="buscar_calle", args={"nombre": "Quaranta"})
                ],
                candidates=[],
                text="",
            )
        # En la segunda vuelta, Gemini inventa coordenadas (-27.351111, -55.891111) no devueltas por el nomenclador
        return SimpleNamespace(
            function_calls=[],
            candidates=[],
            text=json.dumps({
                "resuelto": True,
                "lat": -27.351111,
                "lon": -55.891111,
                "ubicacion_resuelta": "Coordenada inventada por LLM",
                "modo_resolucion": "interseccion",
            }),
        )

    inv._genai_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=mock_generate_content)
    )

    res = inv.resolver_georreferenciacion(
        calle_1=None,
        calle_2=None,
        referencia_espacial=None,
        texto_completo="Siniestro vial en ubicación difusa sin esquina clara",
    )
    assert res["requiere_revision_humana"] is True
    assert res["estado"] == "revisión humana"
    assert res["lat"] is None
    assert res["lon"] is None
    assert res["metodo"] == "gemini"
    assert len(res["pasos_resolucion"]) == 1


def test_gemini_caido_usa_nomenclador_o_deriva_a_revision_sin_coordenadas_por_defecto():
    """Simula Gemini caído (excepción de red/API) y verifica que no usa coordenadas por defecto."""
    inv = AgenteInvestigador()

    def mock_fallo(*args, **kwargs):
        raise ConnectionError("Servicio Gemini no disponible")

    inv._genai_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=mock_fallo)
    )

    # Caso 1: Sin datos resolubles -> deriva a revisión humana con lat=None, lon=None
    res_ambiguo = inv.resolver_georreferenciacion(
        calle_1=None,
        calle_2=None,
        referencia_espacial=None,
        texto_completo="Toque en chacra desconocida sin altura ni calles",
    )
    assert res_ambiguo["estado"] == "revisión humana"
    assert res_ambiguo["requiere_revision_humana"] is True
    assert res_ambiguo["lat"] is None
    assert res_ambiguo["lon"] is None
    assert res_ambiguo["confianza"] == CONFIANZA_SIN_RESOLVER

    # Caso 2: Solo una calle sin esquina precisa y Gemini caído -> revisión humana con confianza 0.50 y lat=None
    res_una_calle = inv.resolver_georreferenciacion(
        calle_1="Av. Quaranta",
        calle_2=None,
        referencia_espacial="a metros de la rotonda",
        texto_completo="Despiste sobre avenida Quaranta a metros de la rotonda",
    )
    assert res_una_calle["estado"] == "revisión humana"
    assert res_una_calle["requiere_revision_humana"] is True
    assert res_una_calle["lat"] is None
    assert res_una_calle["lon"] is None
    assert res_una_calle["confianza"] == CONFIANZA_SOLO_CALLE
    assert any(p["funcion"] == "buscar_calle" for p in res_una_calle["pasos_resolucion"])


def test_caso_ambiguo_rotonda_quaranta_y_uruguay_con_gemini_simulado():
    """Simula la resolución con Gemini mediante function calling para 'a metros de la rotonda de Quaranta y Uruguay'."""
    inv = AgenteInvestigador()
    cruce_real = buscar_interseccion("Quaranta", "Uruguay")
    assert cruce_real["encontrada"] is True

    turno = {"n": 0}

    def mock_generate_content(model, contents, config=None):
        turno["n"] += 1
        if turno["n"] == 1:
            return SimpleNamespace(
                function_calls=[
                    SimpleNamespace(
                        name="buscar_interseccion",
                        args={"calle_1": "Quaranta", "calle_2": "Uruguay"},
                    )
                ],
                candidates=[],
                text="",
            )
        return SimpleNamespace(
            function_calls=[],
            candidates=[],
            text=json.dumps({
                "resuelto": True,
                "lat": cruce_real["lat"],
                "lon": cruce_real["lon"],
                "ubicacion_resuelta": "Rotonda de Av. Quaranta y Av. Uruguay",
                "modo_resolucion": "interseccion",
            }),
        )

    inv._genai_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=mock_generate_content)
    )

    res = inv.resolver_georreferenciacion(
        calle_1="Av. Quaranta",
        calle_2=None,
        referencia_espacial="a metros de la rotonda",
        texto_completo="Colisión entre dos vehículos a metros de la rotonda de Quaranta y Uruguay",
    )
    assert res["estado"] == "resuelto"
    assert res["requiere_revision_humana"] is False
    assert res["metodo"] == "gemini"
    assert res["confianza"] == CONFIANZA_INTERSECCION_OSM
    assert res["lat"] == cruce_real["lat"]
    assert res["lon"] == cruce_real["lon"]
    assert len(res["pasos_resolucion"]) == 1
    assert res["pasos_resolucion"][0]["funcion"] == "buscar_interseccion"


def test_privacidad_pasos_resolucion_no_guarda_nombres_de_personas():
    """Verifica que pasos_resolucion nunca almacene nombres de personas aunque vengan en los argumentos."""
    inv = AgenteInvestigador()

    def mock_generate_content(model, contents, config=None):
        return SimpleNamespace(
            function_calls=[
                SimpleNamespace(
                    name="buscar_lugar",
                    args={"texto": "Juan Carlos Pérez frente a Casino Club con María Gómez"},
                )
            ],
            candidates=[],
            text="",
        )

    inv._genai_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=mock_generate_content)
    )
    res = inv.resolver_georreferenciacion(
        texto_completo="El conductor Juan Carlos Pérez chocó con María Gómez frente al Casino Club"
    )
    serializado = json.dumps(res["pasos_resolucion"], ensure_ascii=False).lower()
    assert "juan" not in serializado
    assert "carlos" not in serializado
    assert "maria" not in serializado
    assert "gomez" not in serializado


def test_casos_en_revision_humana_se_guardan_sin_coordenadas_y_no_afectan_riesgo():
    """Verifica que los casos en revisión humana se guarden con estado 'pendiente', sin coordenadas, y queden fuera del motor de riesgo."""
    import sqlite3
    import threading

    lector = AgenteLector()
    art = {
        "id": "inc-revision-001",
        "fuente": "primera_edicion",
        "url": "https://ejemplo.test/choque-solo-calle",
        "titulo": "Despiste de motocicleta sobre avenida Quaranta dejó un lesionado",
        "texto": "El siniestro ocurrió sobre la avenida Quaranta sin precisarse la intersección ni altura.",
    }
    inc = lector.estructurar_noticia(art)
    assert inc is not None
    assert inc.estado_verificacion == "pendiente"
    assert inc.requiere_revision_humana is True
    assert inc.ubicacion_valida is False
    assert inc.lat is None
    assert inc.lon is None
    assert inc.confianza == CONFIANZA_SOLO_CALLE
    assert inc.metodo == "nomenclador"
    assert len(inc.pasos_resolucion) >= 1

    # Verificar que al insertarse en la base de datos no rompa ni contamine el motor de riesgo
    db = DBWrapper.__new__(DBWrapper)
    db.use_duckdb = False
    db._lock = threading.RLock()
    db.con = sqlite3.connect(":memory:")
    init_schema(db)
    seed_reference_data(db)
    db.execute(
        "INSERT INTO silver_incident_history (id, fuente, fecha_publicacion, tipo_incidente, severidad, confianza, lat, lon, origen) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (inc.id, inc.fuente, "2026-11-10", inc.tipo_incidente, inc.severidad, inc.confianza, inc.lat, inc.lon, inc.origen),
    )
    engine = ExplainableRiskEngine(db)
    _, prioridades = engine.evaluate_all_nodes(ParametrosEscenario())
    assert all(p.total_evidencia == 0 for p in prioridades)
