"""Partes sintéticos reproducibles; no representan tasas observadas."""
import json, math, random, sqlite3, threading
from datetime import datetime, timedelta
from pathlib import Path
from src.warehouse.db import DBWrapper, init_schema, seed_reference_data

SEMILLA = 7107
INICIO = datetime(2023, 1, 1)
DIAS = 1095
TASA_HORA = 0.0045
PROBABILIDAD_LLUVIA = 0.22
PRECIPITACION_LLUVIA_MM_H = 8.0
MULTIPLICADOR_LLUVIA = 1.8
MULTIPLICADOR_PICO = 1.5
MULTIPLICADOR_ESCOLAR = 1.3
MULTIPLICADOR_CARRIL = 0.12
MULTIPLICADOR_SEMAFORO = 0.9
MULTIPLICADOR_PARADA = 1.1
DESVIO_GRADOS = 0.00025
SALIDA = Path(__file__).resolve().parents[2] / "data" / "simulado" / "incidentes.jsonl"


def generar(multiplicador_lluvia=MULTIPLICADOR_LLUVIA, dias=DIAS, semilla=SEMILLA):
    db = DBWrapper.__new__(DBWrapper)
    db.use_duckdb = False
    db._lock = threading.RLock()
    db.con = sqlite3.connect(":memory:")
    init_schema(db)
    seed_reference_data(db)
    nodos = db.df("SELECT * FROM silver_intersections").to_dict("records")
    db.con.close()
    rng = random.Random(semilla)
    eventos, exposicion = [], {"lluvia": 0, "seco": 0}
    for hora in range(dias * 24):
        fecha = INICIO + timedelta(hours=hora)
        lluvia = rng.random() < PROBABILIDAD_LLUVIA
        exposicion["lluvia" if lluvia else "seco"] += len(nodos)
        pico = fecha.hour in (7, 8, 12, 13, 17, 18)
        for nodo in nodos:
            tasa = TASA_HORA
            tasa *= 1 + MULTIPLICADOR_CARRIL * nodo["lanes"]
            tasa *= MULTIPLICADOR_SEMAFORO if nodo["has_traffic_light"] else 1
            tasa *= MULTIPLICADOR_PARADA if nodo["has_bus_stop"] else 1
            tasa *= MULTIPLICADOR_PICO if pico else 1
            tasa *= MULTIPLICADOR_ESCOLAR if pico and nodo["is_school_zone"] and fecha.weekday() < 5 else 1
            tasa *= multiplicador_lluvia if lluvia else 1
            limite, producto, cantidad = math.exp(-tasa), 1.0, -1
            while producto > limite:
                producto *= rng.random()
                cantidad += 1
            for _ in range(cantidad):
                instante = fecha + timedelta(minutes=rng.randrange(60))
                eventos.append({"id": f"sim-{len(eventos)+1:06d}", "fuente": rng.choice(["parte_policial", "911"]),
                    "titulo": "Parte sintético de incidente vial", "url": None,
                    "fecha_publicacion": instante.isoformat(), "fecha_evento": instante.isoformat(),
                    "tipo_incidente": rng.choice(["choque", "vuelco", "atropello"]),
                    "severidad": rng.choices([1, 2, 3], [65, 30, 5])[0],
                    "vehiculos": rng.choice([["auto", "moto"], ["auto", "auto"], ["moto"]]),
                    "ubicacion_texto": nodo["name"], "lat": nodo["lat"] + rng.uniform(-DESVIO_GRADOS, DESVIO_GRADOS),
                    "lon": nodo["lon"] + rng.uniform(-DESVIO_GRADOS, DESVIO_GRADOS),
                    "confianza": 0.9, "resumen": "Registro generado para demostración.",
                    "llovia": lluvia, "precipitacion_mm_h": PRECIPITACION_LLUVIA_MM_H if lluvia else 0.0,
                    "origen": "simulado"})
    return eventos, exposicion


def main():
    eventos, exposicion = generar()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open("w", encoding="utf-8", newline="\n") as archivo:
        for evento in eventos:
            archivo.write(json.dumps(evento, ensure_ascii=False) + "\n")
    (SALIDA.parent / "exposicion.json").write_text(json.dumps(exposicion, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(eventos)} eventos; exposición declarada: {exposicion}")


if __name__ == "__main__":
    main()
