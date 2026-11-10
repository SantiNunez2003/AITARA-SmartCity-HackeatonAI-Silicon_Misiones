"""Script para comprobar la conexión con la API de Gemini usando google-genai."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def probar_conexion_gemini() -> int:
    raiz = Path(__file__).resolve().parent.parent
    load_dotenv(raiz / ".env")

    clave = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    modelo = os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite"

    if not clave:
        print("ERROR: No se encontró GEMINI_API_KEY ni GOOGLE_API_KEY en el entorno o .env.")
        return 1

    print(f"Probando conexión con Gemini (modelo={modelo})...")
    try:
        from google import genai

        client = genai.Client(api_key=clave)
        respuesta = client.models.generate_content(
            model=modelo,
            contents="Respondé únicamente con la palabra: CONECTADO",
        )
        texto = (respuesta.text or "").strip()
        print(f"Respuesta recibida de {modelo}: {texto}")
        return 0
    except Exception as exc:
        print(f"Error al invocar Gemini ({modelo}): {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(probar_conexion_gemini())
