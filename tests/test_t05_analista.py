from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

import api
from src.contracts import AporteFactor, EvaluacionNodo, Evidencia, ParametrosEscenario, Prioridad
from src.engine.analista import AgenteAnalista, _contexto, _numeros_validos


def prioridad():
    nodo = EvaluacionNodo(nodo_id="n", nombre="Cruce A", lat=-27, lon=-55,
                          riesgo_estructural=0.3, variacion_escenario=12,
                          riesgo_final=0.87, es_critico=True, factores=[])
    return Prioridad(nodo=nodo, nivel="critico", riesgo_estructural=0.3,
                     variacion_escenario=12, riesgo_escenario=0.87,
                     aportes=[AporteFactor(nombre="clima", aporte=0.2, descripcion="lluvia")],
                     evidencia=[Evidencia(id="abc", fecha=datetime(2025, 1, 1), tipo="choque",
                                          fuente="medio", url="https://ejemplo.test/incidente", origen="real")])


def analista():
    agente = AgenteAnalista(db=object())
    p = prioridad()
    agente.risk_engine = SimpleNamespace(evaluate_all_nodes=lambda params: ([p.nodo], [p]))
    return agente


def test_respaldo_y_evidencia(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    agente = analista()
    params = ParametrosEscenario()
    contexto = _contexto(params, [prioridad()])
    for pregunta in ("¿Cuál es el riesgo?", "¿Cuántos incidentes hay?", "¿Qué ruta alternativa hay?"):
        respuesta = agente.responder_consulta_operador(pregunta, params)
        assert _numeros_validos(respuesta, contexto)
        assert "incidentes: 1" in respuesta
    assert "rutas alternativas no están" in agente.responder_consulta_operador("¿Qué ruta alternativa hay?", params)
    p = prioridad()
    p.evidencia = []
    agente.risk_engine.evaluate_all_nodes = lambda params: ([p.nodo], [p])
    assert "no tiene evidencia" in agente.responder_consulta_operador("¿Qué ocurre en Cruce A?", params)


def test_control_gemini_y_normalizacion(monkeypatch):
    agente = analista()
    monkeypatch.setenv("GEMINI_MODEL", "modelo-configurado")
    salida = SimpleNamespace(output_text="Riesgo 87 % y valor inventado 999")
    agente._get_genai_client = lambda: SimpleNamespace(interactions=SimpleNamespace(create=lambda **kwargs: salida))
    respuesta = agente.responder_consulta_operador("¿Riesgo?", ParametrosEscenario())
    assert "999" not in respuesta
    salida.output_text = "Riesgo 87 % y aporte 0,2"
    assert agente.responder_consulta_operador("¿Riesgo?", ParametrosEscenario()) == salida.output_text
    assert not _numeros_validos("Riesgo 88 %", _contexto(ParametrosEscenario(), [prioridad()]))


def test_api_sin_clave(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with TestClient(api.app) as cliente:
        monkeypatch.setattr(api, "analista", analista())
        respuesta = cliente.post("/api/ask", json={"pregunta": "¿Riesgo?"})
        assert respuesta.status_code == 200
        assert "incidentes: 1" in respuesta.json()["respuesta"]


def test_modelo_predeterminado_y_configurable(monkeypatch):
    agente = analista()
    llamadas = []
    def crear(**kwargs):
        llamadas.append(kwargs["model"])
        return SimpleNamespace(output_text="Riesgo 0.87")
    agente._get_genai_client = lambda: SimpleNamespace(interactions=SimpleNamespace(create=crear))
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    agente.responder_consulta_operador("Riesgo", ParametrosEscenario())
    monkeypatch.setenv("GEMINI_MODEL", "modelo-alternativo")
    agente.responder_consulta_operador("Riesgo", ParametrosEscenario())
    assert llamadas == ["gemini-3.5-flash-lite", "modelo-alternativo"]


def test_formato_y_control_de_redondeo(monkeypatch):
    from src.engine.analista import _respaldo
    p = prioridad()
    p.aportes[0].aporte = 0.33249999999999996
    p.nivel = "no_critico"
    contexto = _contexto(ParametrosEscenario(), [p])
    respuesta = _respaldo("Cruce A", ParametrosEscenario(), [p])
    assert "0.33" in respuesta and "no crítico" in respuesta and "actividad escolar: sí" in respuesta
    assert "True" not in respuesta and "False" not in respuesta
    assert _numeros_validos("aporte 0,33 o 33 %", contexto)
    assert not _numeros_validos("aporte 34 %", contexto)


def test_numeros_junto_a_unidades_y_marcadores_de_lista():
    contexto = "Distancia 500 m, velocidad 45 km/h, duración 30 min y valor 0.99."
    for texto in ("500m", "45km/h", "30min", "_0.99_"):
        assert _numeros_validos(texto, contexto)
        assert not _numeros_validos(texto, "Sin valores disponibles")
    assert _numeros_validos("1. Primero\n2) Segundo", "Sin valores disponibles")
    assert not _numeros_validos("99. inventado", "Sin valores disponibles")
    assert not _numeros_validos("1. Primero\n3. inventado", "Sin valores disponibles")


def test_respaldo_seleccion_y_prioridades(monkeypatch):
    import re
    agente = analista()
    prioridades = []
    for nombre in ("Avenida López", "Avenida Mitre", "Avenida Uruguay", "Avenida Corrientes"):
        p = prioridad().model_copy(deep=True)
        p.nodo.nombre = nombre
        prioridades.append(p)
    agente.risk_engine.evaluate_all_nodes = lambda params: ([p.nodo for p in prioridades], prioridades)
    monkeypatch.setattr(agente, "_get_genai_client", lambda: None)
    params = ParametrosEscenario()
    detalle = agente.responder_consulta_operador("¿Qué pasa en LOPEZ?", params)
    assert "Avenida López" in detalle and "Avenida Mitre" not in detalle
    assert "Aporte clima" in detalle and "https://ejemplo.test/incidente" in detalle
    resumen = agente.responder_consulta_operador("¿Cuáles son las prioridades?", params)
    assert all(p.nodo.nombre in resumen for p in prioridades[:3])
    assert "Avenida Corrientes" not in resumen and "Nodos evaluados: 4" in resumen
    assert "no están en el contexto" not in resumen
    assert "no están en el contexto" in agente.responder_consulta_operador("¿Rutas alternativas?", params)
    informe = agente.generar_informe_turno(params)
    assert "Avenida Corrientes" not in informe.recomendacion_estrategica
    for texto in (detalle, resumen):
        assert not re.search(r"(?<![\w/])\d+[.,]\d{3,}(?!\d)", texto)
