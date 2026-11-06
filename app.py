"""AITARA — Sistema de Soporte a Decisiones (DSS) para Movilidad Urbana.

Hackathon Silicon Misiones 2026 — Track Smart City (Desafío 1).
Arquitectura Oficial: Propuesta Técnica Joaquín + Modo Claro Institucional + Inspector de Evidencia Lector.
"""

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

from src.contracts import ParametrosEscenario
from src.warehouse.db import (
    get_db_connection,
    init_schema,
    seed_reference_data,
    load_silver_incidents_from_jsonl,
    get_pipeline_status,
    get_all_incidents
)
from src.engine.risk_model import ExplainableRiskEngine
from src.engine.analista import AgenteAnalista

# 1. Configuración de página institucional limpia
st.set_page_config(
    page_title="AITARA — Movilidad Urbana Posadas",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. CSS de Contraste Garantizado (Paleta Estricta de 3 Colores en Modo Claro independientemente del navegador)
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Forzar lienzo claro institucional (#f8fafc) y texto pizarra (#0f172a) */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #f8fafc !important;
        color: #0f172a !important;
        font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif;
    }

    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 1.5rem !important;
        max-width: 97% !important;
    }

    /* Etiquetas de controles y textos nativos de Streamlit siempre legibles */
    label, .stMarkdown, p, h1, h2, h3, h4, span, [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
        color: #0f172a !important;
    }

    /* Tabs limpias con acento Azul Cobalto (#1d4ed8) */
    button[data-baseweb="tab"] {
        background-color: transparent !important;
        color: #475569 !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #1d4ed8 !important;
        border-bottom: 2px solid #1d4ed8 !important;
    }

    /* Inputs, Selectboxes y TextAreas en blanco puro con borde sutil */
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    textarea {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px !important;
    }

    /* Tarjetas del sistema de diseño de 3 colores */
    .aitara-section-label {
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #475569 !important;
        margin-bottom: 6px;
    }
    .aitara-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 14px;
        margin-bottom: 10px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }
    .aitara-card-alert {
        background-color: #fff1f2;
        border: 1px solid #fecdd3;
        border-left: 4px solid #be123c;
        border-radius: 8px;
        padding: 12px 14px;
        margin-bottom: 10px;
    }
    .aitara-card-news {
        background-color: #ffffff;
        border: 1px solid #bfdbfe;
        border-left: 4px solid #1d4ed8;
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 12px;
        box-shadow: 0 2px 6px rgba(29, 78, 216, 0.07);
    }
    .aitara-badge-red {
        background-color: #be123c;
        color: #ffffff !important;
        font-size: 10px;
        font-weight: 700;
        padding: 2px 7px;
        border-radius: 4px;
        text-transform: uppercase;
    }
    .aitara-badge-blue {
        background-color: #1d4ed8;
        color: #ffffff !important;
        font-size: 10px;
        font-weight: 700;
        padding: 2px 7px;
        border-radius: 4px;
        text-transform: uppercase;
    }
    .aitara-pill {
        display: inline-block;
        background-color: #f1f5f9;
        border: 1px solid #cbd5e1;
        color: #0f172a !important;
        font-size: 11px;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 4px;
        margin-right: 5px;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

# 3. Inicialización de Almacén DuckDB y Dataset Curado (Cacheado por sesión/proceso)
@st.cache_resource
def init_aitara_warehouse():
    conn = get_db_connection()
    init_schema(conn)
    seed_reference_data(conn)
    load_silver_incidents_from_jsonl(conn)
    return conn

db = init_aitara_warehouse()
init_schema(db)
seed_reference_data(db)
load_silver_incidents_from_jsonl(db)

pipeline_status = get_pipeline_status(db)
risk_engine = ExplainableRiskEngine(db)
analista = AgenteAnalista(db)
df_inc = get_all_incidents(db)
if "fecha_evento" not in df_inc.columns:
    df_inc["fecha_evento"] = df_inc["fecha_publicacion"]

# 4. Header Institucional con Monitor de Pipeline
col_h1, col_h2 = st.columns([1.5, 1.0])

with col_h1:
    st.markdown("""
    <div style="display: flex; align-items: baseline; gap: 12px;">
        <span style="font-size: 24px; font-weight: 800; color: #0f172a; letter-spacing: -0.02em;">AITARA</span>
        <span style="font-size: 12px; font-weight: 700; color: #1d4ed8; text-transform: uppercase; letter-spacing: 0.04em;">
            Copiloto Táctico de Movilidad Urbana
        </span>
        <span style="font-size: 12px; color: #475569;">· Municipalidad de Posadas</span>
    </div>
    """, unsafe_allow_html=True)

with col_h2:
    st.markdown(f"""
    <div style="text-align: right; font-size: 12px; color: #334155; padding-top: 6px;">
        <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: #1d4ed8; margin-right: 6px;"></span>
        <strong>Almacén:</strong> {pipeline_status['engine']} ·
        <strong>Lote Lector:</strong> {pipeline_status['total_incidentes']} noticias curadas ·
        <strong>Modo:</strong> Resiliente Local
    </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='margin: 8px 0 14px 0; border: none; border-top: 1px solid #cbd5e1;'/>", unsafe_allow_html=True)

# 5. Pestañas de Navegación (Táctica vs Estratégica vs Arquitectura de Datos)
tab_tactico, tab_estrategico, tab_pipeline = st.tabs([
    "1. Despacho Táctico y Gestión Diaria (Qué, Cómo, Cuándo)",
    "2. Tablero de Mejora Continua y Planificación (Cómo Mejorar)",
    "3. Trazabilidad del Pipeline y Base de Noticias (Agente Lector)"
])

with tab_tactico:
    # Definimos primero las columnas visuales (63% Mapa Izquierda | 37% Barra de Decisiones Derecha)
    col_mapa, col_panel = st.columns([1.55, 0.95], gap="medium")

    # Leemos estado de escenario desde session_state para evaluar antes de dibujar el mapa
    franja_actual = st.session_state.get("sel_franja", "07:00")
    lluvia_actual = st.session_state.get("sel_lluvia", 15.0)
    dotacion_actual = st.session_state.get("sel_dotacion", 4)
    estilo_mapa = st.session_state.get("sel_estilo_mapa", "Calles Limpias (Modo Claro)")

    params_escenario = ParametrosEscenario(
        franja_horaria=franja_actual,
        precipitacion_mm_h=float(lluvia_actual),
        dotacion_patrullas=int(dotacion_actual)
    )

    evaluaciones, ordenes = risk_engine.evaluate_all_nodes(params_escenario)
    top_critico = evaluaciones[0] if evaluaciones else None

    # --- COLUMNA IZQUIERDA: MAPA MINIMALISTA DE CALLES Y GEOMETRÍA ORTOGONAL ---
    with col_mapa:
        c_m1, c_m2 = st.columns([1.8, 1.0])
        with c_m1:
            st.markdown("""
            <div class="aitara-section-label" style="padding-top: 6px;">
                Red Vial de Posadas · Nodos Críticos e Incidentes Georreferenciados (Hacé clic en cualquier punto)
            </div>
            """, unsafe_allow_html=True)
        with c_m2:
            st.selectbox(
                "Capa base del mapa",
                ["Calles Limpias (Modo Claro)", "Calles Alto Contraste (Modo Oscuro)"],
                key="sel_estilo_mapa",
                label_visibility="collapsed"
            )

        # Selección de mapa limpio con filtro CSS desaturado sobre OpenStreetMap (100% libre de API Key)
        m = folium.Map(
            location=[-27.3820, -55.9080],
            zoom_start=13,
            tiles="OpenStreetMap",
            control_scale=True
        )
        if "Oscuro" in st.session_state.get("sel_estilo_mapa", ""):
            m.get_root().header.add_child(folium.Element(
                "<style>.leaflet-tile-pane { filter: invert(100%) hue-rotate(180deg) brightness(95%) contrast(90%) grayscale(40%); }</style>"
            ))
        else:
            m.get_root().header.add_child(folium.Element(
                "<style>.leaflet-tile-pane { filter: grayscale(85%) contrast(104%) brightness(103%); }</style>"
            ))

        # 1. Trazo Ortogonal Real del Desvío por Calle San Lorenzo (Siguiendo la cuadrícula exacta de Posadas)
        # Av. Corrientes y Catamarca -> 5 cuadras al Este por Catamarca -> giro al Sur por Calle San Lorenzo -> hasta Av. Mitre
        desvio_ortogonal_coords = [
            [-27.371812, -55.901793],  # Inicio: Av. Corrientes y Calle Catamarca (1 cuadra antes del bloqueo en Tucumán)
            [-27.370525, -55.896203],  # Esquina: Calle Catamarca y Calle San Lorenzo
            [-27.372414, -55.896466],  # Paso: Calle San Lorenzo y Calle Tucumán
            [-27.374256, -55.896695],  # Fin desvío: Calle San Lorenzo y Av. Mitre
        ]
        folium.PolyLine(
            desvio_ortogonal_coords,
            color="#1d4ed8",
            weight=4,
            dash_array="8, 6",
            opacity=0.95,
            tooltip="Corredor de absorción sugerido: Giro en Catamarca -> Calle San Lorenzo hasta Av. Mitre"
        ).add_to(m)

        # 2. Capa de Incidentes Reales Extraídos por el Agente Lector (Círculos interactivos clicables)
        for _, inc in df_inc.iterrows():
            es_grave = int(inc["severidad"]) >= 2
            inc_color = "#be123c" if es_grave else "#1d4ed8"
            folium.CircleMarker(
                location=[float(inc["lat"]), float(inc["lon"])],
                radius=6,
                color="#ffffff",
                weight=1.5,
                fill=True,
                fill_color=inc_color,
                fill_opacity=0.85,
                tooltip=f"[Noticia {inc['id']}] {inc['titulo']} — Clic para inspeccionar en panel derecho"
            ).add_to(m)

        # 3. Capa de Nodos Estratégicos Monitoreados (Halos exteriores de criticidad)
        for ev in evaluaciones:
            c = "#be123c" if ev.es_critico else "#1d4ed8"
            folium.CircleMarker(
                location=[ev.lat, ev.lon],
                radius=13 if ev.es_critico else 9,
                color=c,
                weight=2.5,
                fill=True,
                fill_color=c,
                fill_opacity=0.28 if ev.es_critico else 0.18,
                tooltip=f"[Nodo {ev.nombre}] Riesgo: {int(ev.riesgo_final * 100)}% (+{ev.variacion_escenario}%) — Clic para ver evidencia"
            ).add_to(m)

        # Renderizar mapa y capturar evento de clic
        map_event = st_folium(
            m,
            width="100%",
            height=610,
            returned_objects=["last_object_clicked", "last_clicked"]
        )

        # Leyenda limpia debajo del mapa
        st.markdown("""
        <div style="display: flex; gap: 20px; font-size: 11px; color: #334155; padding: 6px 10px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px;">
            <span><strong style="color: #be123c;">● Nodo / Siniestro Crítico</strong> (Riesgo ≥ 65% o Heridos)</span>
            <span><strong style="color: #1d4ed8;">● Nodo / Incidente Controlado</strong> (Preventivo)</span>
            <span><strong style="color: #1d4ed8;">- - - Trazo Ortogonal</strong> (Desvío Catamarca → Calle San Lorenzo → Mitre)</span>
        </div>
        """, unsafe_allow_html=True)

    # Resolver qué incidente fue seleccionado al hacer clic en el mapa (por proximidad de coordenadas)
    incidente_seleccionado = None
    click_coords = None
    if map_event:
        click_coords = map_event.get("last_object_clicked") or map_event.get("last_clicked")

    if click_coords and "lat" in click_coords and "lng" in click_coords:
        c_lat, c_lon = float(click_coords["lat"]), float(click_coords["lng"])
        mejor_dist = 999.0
        mejor_row = None
        for _, row in df_inc.iterrows():
            d = ((float(row["lat"]) - c_lat) ** 2 + (float(row["lon"]) - c_lon) ** 2) ** 0.5
            if d < mejor_dist:
                mejor_dist = d
                mejor_row = row
        # Si el clic estuvo cerca de algún punto (umbral ~1.2 km en grados), seleccionarlo
        if mejor_row is not None and mejor_dist <= 0.015:
            incidente_seleccionado = mejor_row

    # Si aún no hizo clic en el mapa, mostrar por defecto el incidente asociado al nodo más crítico (inc-pos-001)
    if incidente_seleccionado is None and not df_inc.empty:
        incidente_seleccionado = df_inc.iloc[0]
        fue_clic_directo = False
    else:
        fue_clic_directo = True

    # --- COLUMNA DERECHA: BARRA DE DECISIONES E INSPECTOR DE NOTICIAS ---
    with col_panel:
        # BLOQUE A: INSPECTOR DE EVIDENCIA DEL AGENTE LECTOR (Renderizado al tocar un punto)
        estado_inspector = "SELECCIONADO EN MAPA" if fue_clic_directo else "NODO DOMINANTE ACTIVO"
        sev_num = int(incidente_seleccionado["severidad"])
        sev_map = {0: "0 - Sin daños (Demora)", 1: "1 - Daños materiales / Anegamiento", 2: "2 - Heridos hospitalizados", 3: "3 - Crítico / Fatal"}
        sev_label = sev_map.get(sev_num, f"Nivel {sev_num}")
        badge_cls = "aitara-badge-red" if sev_num >= 2 else "aitara-badge-blue"
        fecha_ev = str(incidente_seleccionado.get("fecha_evento") or incidente_seleccionado["fecha_publicacion"]).replace("T", " ")

        st.markdown(f"""
        <div class="aitara-section-label">
            1. Evidencia Extraída por Agente Lector ({estado_inspector})
        </div>
        <div class="aitara-card-news">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 10px; font-weight: 700; color: #1d4ed8; text-transform: uppercase;">
                    Fuente: {str(incidente_seleccionado['fuente']).replace('_', ' ').upper()} · ID: {incidente_seleccionado['id']}
                </span>
                <span class="{badge_cls}">{incidente_seleccionado['tipo_incidente']}</span>
            </div>
            <div style="font-size: 13px; font-weight: 700; color: #0f172a; line-height: 1.35; margin-bottom: 6px;">
                {incidente_seleccionado['titulo']}
            </div>
            <div style="font-size: 11.5px; color: #334155; line-height: 1.4; margin-bottom: 8px;">
                {incidente_seleccionado['resumen']}
            </div>
            <div style="font-size: 11px; color: #0f172a; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px; margin-bottom: 6px;">
                <div><strong>Ubicación detectada:</strong> {incidente_seleccionado['ubicacion_texto']} ({incidente_seleccionado['calle_1']} y {incidente_seleccionado['calle_2']})</div>
                <div><strong>Coordenadas:</strong> {float(incidente_seleccionado['lat']):.5f}, {float(incidente_seleccionado['lon']):.5f} · <strong>Horario:</strong> {fecha_ev} hs</div>
                <div><strong>URL original:</strong> <a href="{incidente_seleccionado['url']}" target="_blank" style="color: #1d4ed8; text-decoration: underline;">{incidente_seleccionado['url']}</a></div>
            </div>
            <div>
                <span class="aitara-pill">Severidad: {sev_label}</span>
                <span class="aitara-pill">Vehículos: {incidente_seleccionado['vehiculos'] or 'No aplica'}</span>
                <span class="aitara-pill">Confianza Lector: {int(float(incidente_seleccionado['confianza']) * 100)}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # BLOQUE B: PARÁMETROS DEL ESCENARIO OPERATIVO
        st.markdown('<div class="aitara-section-label">2. Simulación de Escenario y Dotación de Guardia</div>', unsafe_allow_html=True)
        c_p1, c_p2, c_p3 = st.columns([1.1, 1.1, 1.0])
        with c_p1:
            st.selectbox(
                "Franja horaria",
                ["07:00", "12:00", "18:00"],
                index=0,
                key="sel_franja",
                format_func=lambda x: f"{x} hs (Pico)"
            )
        with c_p2:
            st.selectbox(
                "Lluvia (OPAD)",
                [0.0, 15.0, 40.0],
                index=1,
                key="sel_lluvia",
                format_func=lambda x: f"{x} mm/h" if x > 0 else "0 mm/h (Seco)"
            )
        with c_p3:
            st.selectbox(
                "Móviles activos",
                [1, 2, 4, 6],
                index=2,
                key="sel_dotacion",
                format_func=lambda x: f"{x} patrullas"
            )

        # BLOQUE C: DIAGNÓSTICO DE CRITICIDAD DOMINANTE (XAI)
        st.markdown('<div class="aitara-section-label" style="margin-top: 6px;">3. Diagnóstico de Criticidad Dominante (XAI)</div>', unsafe_allow_html=True)
        if top_critico:
            st.markdown(f"""
            <div class="aitara-card-alert">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <strong style="color: #0f172a; font-size: 13px;">{top_critico.nombre}</strong>
                    <span class="aitara-badge-red">Riesgo: {int(top_critico.riesgo_final * 100)}% (+{top_critico.variacion_escenario}%)</span>
                </div>
                <div style="font-size: 11.5px; color: #334155; line-height: 1.4;">
                    <strong>Causa explicable:</strong> {', '.join(top_critico.factores)}.
                </div>
            </div>
            """, unsafe_allow_html=True)

        # BLOQUE D: ÓRDENES DE DESPACHO TÁCTICO ASIGNADAS
        st.markdown('<div class="aitara-section-label">4. Órdenes de Despacho Táctico (Triaje según Dotación)</div>', unsafe_allow_html=True)
        for o in ordenes[:int(dotacion_actual)]:
            st.markdown(f"""
            <div class="aitara-card" style="padding: 9px 12px; margin-bottom: 6px;">
                <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 2px;">
                    <strong style="color: #1d4ed8;">{o.movil_id} · {o.nodo_objetivo}</strong>
                    <span style="color: #475569; font-weight: 600;">{o.hora_presentacion} hs</span>
                </div>
                <div style="font-size: 11px; color: #334155; line-height: 1.35;">
                    {o.instruccion_tactica}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # BLOQUE E: CONSULTA AL AGENTE ANALISTA (Conectado en vivo a DuckDB)
        st.markdown('<div class="aitara-section-label" style="margin-top: 8px;">5. Consulta al Agente Analista (Motor SQL DuckDB)</div>', unsafe_allow_html=True)
        q_user = st.text_input(
            "Preguntale al Analista sobre siniestros por hora, lluvias o desvíos:",
            placeholder="Ej: ¿Cuántos choques puede haber entre las 17 y 18 hs?",
            label_visibility="collapsed"
        )
        if q_user:
            resp_analista = analista.responder_consulta_operador(q_user, params_escenario)
            st.markdown(f"""
            <div class="aitara-card" style="border-left: 4px solid #0f172a; background-color: #f8fafc; font-size: 11.5px; color: #0f172a; line-height: 1.45;">
                <strong>Analista AITARA:</strong> {resp_analista}
            </div>
            """, unsafe_allow_html=True)


with tab_estrategico:
    st.markdown("""
    <div style="padding: 6px 0 12px 0;">
        <h3 style="margin: 0; font-size: 17px; font-weight: 800; color: #0f172a;">
            Respaldo para Decisiones de Infraestructura Vial (Responde al "¿Cómo Mejorar?")
        </h3>
        <p style="font-size: 12.5px; color: #475569; margin-top: 4px;">
            Análisis retrospectivo sobre la memoria de siniestros de Posadas para priorización de obras civiles, dársenas escolares y drenaje pluvial.
        </p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="aitara-card">
            <div class="aitara-section-label">Incidentes Estructurados (Silver)</div>
            <div style="font-size: 26px; font-weight: 800; color: #1d4ed8;">{pipeline_status['total_incidentes']} hechos</div>
            <div style="font-size: 11px; color: #475569;">Extraídos de Primera Edición, El Territorio y Misiones Online</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="aitara-card">
            <div class="aitara-section-label">Nodos con Deuda de Infraestructura</div>
            <div style="font-size: 26px; font-weight: 800; color: #be123c;">3 intersecciones</div>
            <div style="font-size: 11px; color: #475569;">Prioridad de intervención alta (Obras Públicas)</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class="aitara-card">
            <div class="aitara-section-label">Fricción Evitada en Transporte</div>
            <div style="font-size: 26px; font-weight: 800; color: #0f172a;">32 min promedio</div>
            <div style="font-size: 11px; color: #475569;">Mediante encauzamiento preventivo 15 min antes del pico</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="aitara-section-label" style="margin-top: 12px;">Matriz de Vulnerabilidad Estructural y Recomendación de Obra Pública</div>', unsafe_allow_html=True)
    ranking_data = [
        {
            "Intersección": "Av. San Martín y Av. Comandante Andresito",
            "Coordenadas OSM": "-27.39723, -55.92066",
            "Causa Raíz Detectada": "Cota topográfica baja y saturación de sumideros pluviales (>12 mm/h)",
            "Evidencia Histórica": "18 anegamientos anuales (inc-pos-004)",
            "Intervención Estructural Sugerida": "Ampliación de boca de tormenta y badén de derivación"
        },
        {
            "Intersección": "Rotonda Av. Uruguay y Av. Quaranta (RN12)",
            "Coordenadas OSM": "-27.40380, -55.90280",
            "Causa Raíz Detectada": "Pérdida de adherencia de motovehículos al ingresar al anillo giratorio",
            "Evidencia Histórica": "34 siniestros viales con motos (inc-pos-002)",
            "Intervención Estructural Sugerida": "Fresado de microtextura rugosa y reductores ópticos en colectora"
        },
        {
            "Intersección": "Av. Corrientes y Calle Tucumán (San Basilio)",
            "Coordenadas OSM": "-27.37276, -55.90191",
            "Causa Raíz Detectada": "Doble fila de ascenso/descenso escolar y estrangulamiento a 1 carril",
            "Evidencia Histórica": "Colisiones por alcance en ingreso escolar (inc-pos-001)",
            "Intervención Estructural Sugerida": "Dársena física exclusiva de detención rápida (Kiss & Ride 3 min)"
        }
    ]
    st.dataframe(pd.DataFrame(ranking_data), use_container_width=True, hide_index=True)


with tab_pipeline:
    st.markdown("""
    <div style="padding: 6px 0 12px 0;">
        <h3 style="margin: 0; font-size: 17px; font-weight: 800; color: #0f172a;">
            Arquitectura Medallion y Flujo de Carga de Puntos (Bronze → Silver → Gold)
        </h3>
        <p style="font-size: 12.5px; color: #475569; margin-top: 4px;">
            Trazabilidad completa de cómo se extraen las noticias locales, cómo se georreferencian en Posadas y cómo alimentan el mapa táctico.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="aitara-card">
        <div class="aitara-section-label">Flujo End-to-End de Carga de Datos</div>
        <div style="font-size: 12px; color: #334155; line-height: 1.6;">
            <strong>Paso 1 — Ingesta Multimodo (Capa Bronze - <code>sources/news.py</code>):</strong> El colector recorre <em>Primera Edición</em>, <em>El Territorio</em> y <em>Misiones Online</em> vía API REST de WordPress, RSS y HTML, filtrando artículos con vocabulario vial (choque, despiste, semáforo, anegamiento).<br/>
            <strong>Paso 2 — Extracción Semántica (Agente Lector - <code>classifier.py</code>):</strong> Cada crónica periodística se transforma en un registro JSON validado por el contrato Pydantic (<code>IncidenteVialExtraido</code>), extrayendo <code>tipo_incidente</code>, <code>severidad (0-3)</code>, <code>vehiculos</code>, <code>calle_1</code>, <code>calle_2</code> y <code>resumen</code>.<br/>
            <strong>Paso 3 — Geocodificación Ortogonal sobre Posadas (<code>data/silver/incidentes_posadas.jsonl</code>):</strong> El cruce de <code>calle_1</code> y <code>calle_2</code> se resuelve contra la geometría real de OpenStreetMap / IDE Posadas, asignando latitud y longitud exactas sobre la intersección.<br/>
            <strong>Paso 4 — Almacén Analítico DuckDB (<code>src/warehouse/db.py</code>):</strong> Al iniciar la aplicación, <code>load_silver_incidents_from_jsonl()</code> inyecta el lote curado en la tabla columnar <code>silver_incident_history</code> y cruza con los 7 nodos críticos de <code>silver_intersections</code>.<br/>
            <strong>Paso 5 — Renderizado e Interacción en Mapa (<code>app.py</code>):</strong> Folium dibuja cada fila de DuckDB en el mapa; al hacer clic en cualquier marcador, <code>st_folium</code> captura las coordenadas clicadas y renderiza instantáneamente la tarjeta de la noticia en el panel derecho.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="aitara-section-label">Explorador Directo de la Tabla <code>silver_incident_history</code> (DuckDB)</div>', unsafe_allow_html=True)
    st.dataframe(
        df_inc[["id", "fuente", "fecha_evento", "tipo_incidente", "severidad", "vehiculos", "calle_1", "calle_2", "lat", "lon", "confianza", "titulo", "url"]],
        use_container_width=True,
        hide_index=True
    )

st.markdown("""
<div style="margin-top: 18px; padding-top: 10px; border-top: 1px solid #cbd5e1; font-size: 11px; color: #475569; display: flex; justify-content: space-between;">
    <span><strong>AITARA v2.0</strong> — Sistema de Soporte a Decisiones (DSS) para Movilidad Urbana · Hackathon Silicon Misiones 2026</span>
    <span>Cumplimiento estricto del Pliego: Sin intervención física sobre semáforos ni peritaje legal; 100% asistencia al operador humano.</span>
</div>
""", unsafe_allow_html=True)
