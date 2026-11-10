"""Tests automatizados para el Fallback Territorial y Guardrails del Agente Investigador."""

import pytest
from src.engine.investigador import AgenteInvestigador


def test_fallback_country_los_naranjos():
    inv = AgenteInvestigador()
    res = inv.resolver_georreferenciacion(
        calle_1="Av. Alicia Moreau de Justo",
        calle_2=None,
        referencia_espacial="Country Los Naranjos",
        texto_completo="Choque frontal sobre ex Ruta 213 frente al acceso a Country Los Naranjos"
    )
    assert res["estado"] == "RESUELTO_AUTOMATICO"
    assert res["tipo_ubicacion"] == "corredor_hito"
    assert abs(res["lat"] - (-27.446188)) < 0.0001
    assert abs(res["lon"] - (-55.957563)) < 0.0001
    assert res["confianza"] >= 0.90
    assert res["requiere_revision_humana"] is False


def test_fallback_autodromo_rosamonte():
    inv = AgenteInvestigador()
    res = inv.resolver_georreferenciacion(
        calle_1="Av. Fangio",
        referencia_espacial="Autódromo Rosamonte",
        texto_completo="Despiste durante el fin de semana en las inmediaciones del autódromo"
    )
    assert res["estado"] == "RESUELTO_AUTOMATICO"
    assert abs(res["lat"] - (-27.440662)) < 0.001
    assert res["confianza"] >= 0.90


def test_interseccion_tradicional_sigue_funcionando():
    inv = AgenteInvestigador()
    res = inv.resolver_georreferenciacion(
        calle_1="San Lorenzo",
        calle_2="Tucumán",
        texto_completo="Colisión en San Lorenzo y Tucumán"
    )
    assert res["estado"] == "RESUELTO_AUTOMATICO"
    assert res["tipo_ubicacion"] == "interseccion"
    assert abs(res["lat"] - (-27.372414)) < 0.001


def test_guardrail_rechaza_punto_fuera_de_corredor():
    inv = AgenteInvestigador()
    # Si la calle es Moreau de Justo pero el punto cae en el centro (-27.36), el guardrail debe detectar incoherencia
    valido = inv.validar_consistencia_corredor("Av. Alicia Moreau de Justo", lat=-27.3600, lon=-55.8900)
    assert valido is False

    # Un punto al sur sobre la traza es válido
    valido_sur = inv.validar_consistencia_corredor("Av. Alicia Moreau de Justo", lat=-27.4461, lon=-55.9575)
    assert valido_sur is True


def test_caso_ambiguo_deriva_a_revision_humana():
    inv = AgenteInvestigador()
    res = inv.resolver_georreferenciacion(
        calle_1=None,
        calle_2=None,
        texto_completo="Toque en chacra desconocida sin altura"
    )
    assert res["estado"] == "DERIVADO_A_REVISION_HUMANA"
    assert res["confianza"] <= 0.50
    assert res["requiere_revision_humana"] is True
