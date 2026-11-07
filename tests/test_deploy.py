from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

import api
from api import app


def test_api_con_lifespan():
    with TestClient(app) as client:
        assert client.get("/api/status").status_code == 200
        incidents = client.get("/api/incidents")
        assert incidents.status_code == 200
        assert isinstance(incidents.json(), list)
        assert client.get("/api/ruta-inexistente").status_code == 404


ESCENARIO = {
    "franja_horaria": "07:00",
    "precipitacion_mm_h": 15,
    "dotacion_patrullas": 4,
}


def test_pedidos_simultaneos():
    def pedir(indice):
        ruta = indice % 4
        if ruta == 0:
            respuesta = client.get("/api/status")
        elif ruta == 1:
            respuesta = client.get("/api/incidents")
        elif ruta == 2:
            respuesta = client.get("/api/strategic")
        else:
            respuesta = client.post("/api/evaluate", json=ESCENARIO)
        assert respuesta.status_code == 200
        datos = respuesta.json()
        if ruta == 0:
            assert datos["total_incidentes"] > 0
        elif ruta == 1:
            assert datos
        elif ruta == 2:
            assert datos["ranking_infraestructura"]
        else:
            assert datos["nodos"]

    with TestClient(app) as client:
        with ThreadPoolExecutor(max_workers=16) as executor:
            list(executor.map(pedir, range(200)))


def test_evaluate_con_informe_fallido(monkeypatch):
    def fallar(*args, **kwargs):
        raise RuntimeError("Informe no disponible")

    with TestClient(app) as client:
        monkeypatch.setattr(api.analista, "generar_informe_turno", fallar)
        respuesta = client.post("/api/evaluate", json=ESCENARIO)
        assert respuesta.status_code == 200
        resumen = respuesta.json()["resumen_turno"]
        assert resumen["alerta_meteorologica"] == "No disponible"
        assert "Condición normal" not in respuesta.text
