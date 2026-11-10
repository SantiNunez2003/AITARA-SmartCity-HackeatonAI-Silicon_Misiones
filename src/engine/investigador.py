"""AITARA - Agente Investigador (Joaquín Technical RFC).

Componente autónomo con herramientas territoriales que interviene para
desambiguar y georreferenciar incidentes viales:
1. Nomenclador de intersecciones de Posadas (OSM / IDE Posadas).
2. Nomenclador de hitos y puntos de interés periurbanos fuera de la cuadrícula.
3. Fallback territorial y guardrail de coherencia topológica sobre corredores.
"""

from typing import Dict, Any, Optional, Tuple
import math
import unicodedata


def _quitar_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )



class AgenteInvestigador:
    def __init__(self):
        # Nomenclador base de calles y lugares de referencia de Posadas (incluyendo hitos periurbanos)
        self.puntos_interes_posadas = {
            "rotonda uruguay": (-27.3912, -55.9084, "Rotonda Av. Uruguay y Quaranta"),
            "casino club": (-27.3915, -55.9078, "Av. Quaranta frente a Casino Club"),
            "san basilio": (-27.3638, -55.8936, "Av. Corrientes y Tucumán (Colegio San Basilio)"),
            "colegio san basilio": (-27.3638, -55.8936, "Av. Corrientes y Tucumán"),
            "colegio santa maria": (-27.3680, -55.8920, "Calle Buenos Aires y Bolívar"),
            "parque de la salud": (-27.3785, -55.8890, "Av. López Torres y Cabred (Hospital Madariaga)"),
            "hospital madariaga": (-27.3785, -55.8890, "Av. López Torres y Cabred"),
            "placita del puente": (-27.3705, -55.8840, "Acceso Sur y Av. Mitre"),
            "rotonda acceso oeste": (-27.3680, -55.9450, "Av. Ulises López y Chacabuco"),
            "transferencia quaranta": (-27.4080, -55.9180, "Av. Quaranta y Av. Santa Catalina"),
            "country los naranjos": (-27.446188, -55.957563, "Av. Alicia Moreau de Justo frente al Country Los Naranjos"),
            "los naranjos": (-27.446188, -55.957563, "Av. Alicia Moreau de Justo frente al Country Los Naranjos"),
            "autodromo rosamonte": (-27.440662, -55.926958, "Av. Fangio y Calle 190 (Autódromo Rosamonte)"),
            "autodromo": (-27.440662, -55.926958, "Av. Fangio y Calle 190 (Autódromo Rosamonte)"),
            "campus unam": (-27.424500, -55.887200, "Ruta 12 y Campus UNaM"),
            "transferencia unam": (-27.424500, -55.887200, "Estación Transferencia UNaM"),
            "parque del conocimiento": (-27.373200, -55.961000, "Av. Ulises López frente al Parque del Conocimiento"),
            "aeropuerto": (-27.385500, -55.970800, "Acceso Aeropuerto General San Martín"),
            "itaembe guazu": (-27.376500, -55.998000, "Av. Los Jilgueros y Av. Los Lirios (Itaembé Guazú)"),
            "itaembe mini": (-27.412000, -55.938000, "Av. 147 y Av. 170 (Itaembé Miní)"),
            "puente internacional": (-27.376209, -55.880326, "Cabecera Puente Internacional San Roque González de Santa Cruz"),
            "el brete": (-27.354000, -55.889000, "Av. Costanera y Av. Urquiza (Bahía El Brete)"),
            "villa cabello": (-27.371000, -55.935000, "Av. Tambor de Tacuarí y Av. Kolping (Villa Cabello)"),
        }

        # Intersecciones conocidas de la red vial Posadas
        self.intersecciones_conocidas = {
            ("san lorenzo", "tucuman"): (-27.372414, -55.896466, "Calle San Lorenzo y Tucumán (Microcentro)"),
            ("corrientes", "tucuman"): (-27.372758, -55.901911, "Av. Corrientes y Tucumán"),
            ("uruguay", "quaranta"): (-27.403800, -55.902800, "Rotonda Av. Uruguay y Quaranta (RN12)"),
            ("quaranta", "tomas guido"): (-27.401150, -55.917214, "Av. Quaranta y Av. Tomás Guido"),
            ("san martin", "santa cruz"): (-27.398994, -55.920856, "Av. San Martín y Av. Santa Cruz / Andresito"),
            ("san martin", "andresito"): (-27.397231, -55.920662, "Av. San Martín y Av. Andresito"),
            ("trincheras de san jose", "lopez torres"): (-27.378438, -55.891536, "Av. Trincheras de San José y López Torres"),
            ("cabred", "lopez torres"): (-27.385123, -55.892459, "Av. Cabred y Av. López Torres"),
            ("centenario", "lavalle"): (-27.365137, -55.904835, "Av. Centenario y Av. Lavalle"),
            ("urquiza", "san martin"): (-27.358844, -55.915393, "Av. Urquiza y Av. San Martín"),
            ("uruguay", "cabred"): (-27.384758, -55.899969, "Av. Uruguay y Av. Cabred"),
            ("mitre", "lopez torres"): (-27.375151, -55.891101, "Av. Mitre y Av. López Torres"),
            ("santa fe", "buenos aires"): (-27.364339, -55.892216, "Calle Santa Fe entre Buenos Aires y Rivadavia"),
            ("alicia moreau de justo", "quaranta"): (-27.402395, -55.921365, "Av. Alicia Moreau de Justo y Quaranta"),
        }

    def _normalizar_calle(self, calle: Optional[str]) -> str:
        if not calle:
            return ""
        c = _quitar_tildes(calle.lower().strip())
        for pref in ["avenida ", "av. ", "av ", "calle ", "ruta ", "ex ruta ", "exruta ", "rp "]:
            if c.startswith(pref):
                c = c[len(pref):].strip()
        return c

    def validar_consistencia_corredor(self, calle: str, lat: float, lon: float) -> bool:
        """Guardrail: Comprueba que las coordenadas no estén groseramente desviadas del corredor."""
        c = self._normalizar_calle(calle)
        # Corredor RP 213 / Moreau de Justo: se extiende al sur de Quaranta (-27.402 a -27.47)
        if "alicia moreau de justo" in c or "213" in c:
            if lat > -27.39: # Más al norte de Quaranta es incoherente
                return False
            if not (-55.98 <= lon <= -55.91):
                return False
        # Corredor Travesía Urbana Quaranta (eje este-oeste entre -27.39 y -27.42)
        if "quaranta" in c:
            if not (-27.42 <= lat <= -27.38):
                return False
        return True

    def resolver_georreferenciacion(
        self,
        calle_1: Optional[str] = None,
        calle_2: Optional[str] = None,
        referencia_espacial: Optional[str] = None,
        texto_completo: str = ""
    ) -> Dict[str, Any]:
        """Resuelve coordenadas con fallback jerárquico:
        1. Hitos periurbanos (country, autódromo, parques, etc.)
        2. Intersección de calles explícitas
        3. Búsqueda por texto libre en el nomenclador
        4. Guardrail de consistencia topológica
        """
        texto_busqueda = _quitar_tildes(f"{referencia_espacial or ''} {texto_completo} {calle_1 or ''} {calle_2 or ''}".lower())

        # 1. Fallback a hitos conocidos de Posadas
        for key, (lat, lon, direccion_norm) in self.puntos_interes_posadas.items():
            if key in texto_busqueda:
                valido = True
                if calle_1:
                    valido = self.validar_consistencia_corredor(calle_1, lat, lon)
                return {
                    "estado": "RESUELTO_AUTOMATICO",
                    "lat": lat,
                    "lon": lon,
                    "ubicacion_resuelta": direccion_norm,
                    "tipo_ubicacion": "corredor_hito" if calle_1 else "punto_singular",
                    "confianza": 0.95 if valido else 0.50,
                    "metodo": "Agente Investigador: Coincidencia con hito territorial de Posadas",
                    "requiere_revision_humana": not valido
                }

        # 2. Intersección conocida
        if calle_1 and calle_2:
            c1 = self._normalizar_calle(calle_1)
            c2 = self._normalizar_calle(calle_2)
            for (k1, k2), (lat, lon, direccion_norm) in self.intersecciones_conocidas.items():
                if (k1 in c1 and k2 in c2) or (k1 in c2 and k2 in c1):
                    return {
                        "estado": "RESUELTO_AUTOMATICO",
                        "lat": lat,
                        "lon": lon,
                        "ubicacion_resuelta": direccion_norm,
                        "tipo_ubicacion": "interseccion",
                        "confianza": 0.95,
                        "metodo": "Agente Investigador: Intersección vial validada",
                        "requiere_revision_humana": False
                    }

        # 3. Derivación a revisión humana si no hay certeza
        lat_def, lon_def = (-27.3670, -55.8960)
        return {
            "estado": "DERIVADO_A_REVISION_HUMANA",
            "lat": lat_def,
            "lon": lon_def,
            "ubicacion_resuelta": texto_completo or f"{calle_1 or ''} y {calle_2 or ''}".strip(),
            "tipo_ubicacion": "indeterminado",
            "confianza": 0.40,
            "metodo": "Agente Investigador: Ubicación ambigua fuera de catálogo",
            "requiere_revision_humana": True
        }

    def investigar_ubicacion(self, texto_ubicacion: str) -> Dict[str, Any]:
        """Compatibilidad con interfaz previa."""
        return self.resolver_georreferenciacion(texto_completo=texto_ubicacion)


if __name__ == "__main__":
    inv = AgenteInvestigador()
    r1 = inv.resolver_georreferenciacion(
        calle_1="Av. Alicia Moreau de Justo",
        referencia_espacial="Country Los Naranjos",
        texto_completo="Choque frente al Country Los Naranjos sobre ex Ruta 213"
    )
    print("Caso Country Los Naranjos:", r1)

