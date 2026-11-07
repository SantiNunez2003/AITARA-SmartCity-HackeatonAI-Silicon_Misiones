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
        assert "Incidentes de evidencia: 1" in respuesta
        assert "https://ejemplo.test/incidente" in respuesta
    assert "rutas alternativas no está" in agente.responder_consulta_operador("¿Qué ruta alternativa hay?", params)
    p = prioridad()
    p.evidencia = []
    agente.risk_engine.evaluate_all_nodes = lambda params: ([p.nodo], [p])
    assert "no tiene evidencia" in agente.responder_consulta_operador("¿Qué ocurre?", params)


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
        assert "Incidentes de evidencia: 1" in respuesta.json()["respuesta"]
