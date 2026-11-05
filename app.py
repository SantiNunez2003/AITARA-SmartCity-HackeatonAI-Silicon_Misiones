"""AITARA — Sistema de Soporte a Decisiones (DSS) para Movilidad Urbana.

Hackathon Silicon Misiones 2026 — Desafío 1: IA para Entender y Anticipar la Movilidad Urbana.
"""

import datetime
from pathlib import Path
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

from src.warehouse.db import get_db_connection, init_schema, seed_reference_data
from src.engine.risk_model import ExplainableRiskEngine

st.set_page_config(
    page_title="AITARA — DSS Movilidad Urbana Posadas",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
con = get_db_connection()
init_schema(con)
seed_reference_data(con)

# Load nodes and features
nodes_df = con.df("""
    SELECT 
        s.node_id, s.name, s.lat, s.lon, s.corridor_type, s.lanes, 
        s.has_traffic_light, s.has_bus_stop, s.is_school_zone, s.school_name,
        s.drainage_risk_level, g.historical_incident_score, g.base_capacity_veh_hour
    FROM silver_intersections s
    JOIN gold_node_risk_features g ON s.node_id = g.node_id
""")

# Sidebar Controls
st.sidebar.title("AITARA — Control Operativo")
st.sidebar.markdown("**Decision Support System (DSS)**  \nMunicipalidad de Posadas")

st.sidebar.markdown("---")
st.sidebar.subheader("Parámetros de Simulación")

# Time slider
sim_hour = st.sidebar.slider("Hora de observación actual", min_value=6, max_value=22, value=6, step=1)
sim_minute = st.sidebar.select_slider("Minuto actual", options=[0, 15, 30, 45], value=45)
sim_time = datetime.time(hour=sim_hour, minute=sim_minute)

# Horizon selector
horizon = st.sidebar.radio(
    "Horizonte de Anticipación",
    options=[30, 60],
    format_func=lambda x: f"T + {x} minutos (Despacho preventivo)",
    index=0
)

# Weather simulation
st.sidebar.subheader("Dimensión Ambiental (OPAD)")
rain_mm = st.sidebar.slider("Precipitación pluvial (mm/h)", min_value=0.0, max_value=40.0, value=12.0, step=2.0)

# Corridor filter
st.sidebar.subheader("Filtros de Red")
selected_corridor = st.sidebar.selectbox("Tipo de Corredor", ["TODOS", "ESCOLAR", "TRONCAL", "ACCESO_PERIFERICO"])

# Run Evaluation Engine
engine = ExplainableRiskEngine()
evaluations = []

for _, row in nodes_df.iterrows():
    if selected_corridor != "TODOS" and row["corridor_type"] != selected_corridor:
        continue
    ev = engine.evaluate_node(row.to_dict(), sim_time, rain_mm, horizon_minutes=horizon)
    evaluations.append(ev)

# Header
st.title("AITARA: Anticipación de Movilidad Urbana")
target_dt = datetime.datetime.combine(datetime.date.today(), sim_time) + datetime.timedelta(minutes=horizon)
st.caption(f"Monitoreo actual: **{sim_time.strftime('%H:%M')} hs** | Ventana proyectada de decisión: **{target_dt.strftime('%H:%M')} hs (T+{horizon} min)**")

# Top KPI Cards
col1, col2, col3, col4 = st.columns(4)
crit_count = sum(1 for e in evaluations if e.risk_level == "CRÍTICO")
alto_count = sum(1 for e in evaluations if e.risk_level == "ALTO")
total_inspectors = sum(e.dispatch_recommendation["inspectors_count"] for e in evaluations)
total_cones = sum(e.dispatch_recommendation["cones_count"] for e in evaluations)

col1.metric("Nodos en Riesgo Crítico", crit_count, delta="Acción inmediata" if crit_count > 0 else "Normal", delta_color="inverse")
col2.metric("Nodos en Riesgo Alto", alto_count)
col3.metric("Inspectores a Despachar", f"{total_inspectors} efectivos")
col4.metric("Balizamiento Preventivo", f"{total_cones} conos asignados")

st.markdown("---")

# Main Layout: Map & Dispatch
left_col, right_col = st.columns([1.2, 1.0])

with left_col:
    st.subheader("Mapa Espaciotemporal de Riesgo (Posadas)")
    
    # Initialize Folium Map centered in Posadas
    m = folium.Map(location=[-27.3800, -55.9100], zoom_start=13, tiles="cartodbpositron")
    
    color_map = {
        "CRÍTICO": "#D32F2F", # Red
        "ALTO": "#F57C00",    # Orange
        "MEDIO": "#FBC02D",   # Yellow
        "BAJO": "#388E3C"     # Green
    }
    
    for ev in evaluations:
        c = color_map.get(ev.risk_level, "#388E3C")
        popup_html = f"""
        <div style="font-family: Arial; width: 220px;">
            <h4 style="margin: 0; color: {c};">{ev.name}</h4>
            <p><b>Riesgo:</b> {ev.risk_level} ({int(ev.risk_score * 100)}%)</p>
            <p><b>Factor Principal:</b> {ev.dominant_factor}</p>
            <p><b>Causa:</b> {ev.explanation}</p>
            <hr style="margin: 4px 0;"/>
            <p style="font-size: 11px;"><b>Recomendación:</b> {ev.dispatch_recommendation['action']}</p>
        </div>
        """
        folium.CircleMarker(
            location=[ev.lat, ev.lon],
            radius=12 if ev.risk_level in ["CRÍTICO", "ALTO"] else 8,
            color=c,
            fill=True,
            fill_color=c,
            fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{ev.name} — {ev.risk_level}"
        ).add_to(m)
        
    st_folium(m, width="100%", height=450)

with right_col:
    st.subheader("Caso Piloto Foco: Av. Corrientes y Tucumán")
    pilot_ev = next((e for e in evaluations if e.node_id == "N1_CORRIENTES_TUCUMAN"), None)
    
    if pilot_ev:
        st.markdown(f"**Estado Proyectado:** `{pilot_ev.risk_level}` (Score: {pilot_ev.risk_score})")
        st.info(f"**Diagnóstico Explicable (XAI):** {pilot_ev.explanation}")
        
        st.markdown("#### Contribución de las 4 Dimensiones:")
        dim_data = pd.DataFrame({
            "Dimensión": [
                "1. Demanda Temporal (Escuelas)",
                "2. Meteorología (Lluvia/Calzada)",
                "3. Topología Vial (Capacidad)",
                "4. Riesgo Siniestral Histórico"
            ],
            "Nivel de Fricción": [
                pilot_ev.dim_temporal,
                pilot_ev.dim_clima,
                pilot_ev.dim_topologia,
                pilot_ev.dim_siniestral
            ]
        })
        st.bar_chart(dim_data.set_index("Dimensión"))
        
        st.success(f"**Orden Operativa Sugerida:** {pilot_ev.dispatch_recommendation['action']}")
    else:
        st.warning("Seleccione 'TODOS' o 'ESCOLAR' para visualizar el caso piloto.")

st.markdown("---")

# Bottom Table: Dispatch Matrix
st.subheader("Matriz de Despacho Preventivo para Operadores")

dispatch_rows = []
for ev in evaluations:
    dispatch_rows.append({
        "Intersección": ev.name,
        "Tipo": ev.corridor_type,
        "Riesgo": ev.risk_level,
        "Prioridad": ev.dispatch_recommendation["priority"],
        "Inspectores": ev.dispatch_recommendation["inspectors_count"],
        "Conos": ev.dispatch_recommendation["cones_count"],
        "Acción Preventiva Sugerida": ev.dispatch_recommendation["action"],
        "Desvío / Mitigación": ev.dispatch_recommendation["suggested_diversion"]
    })

dispatch_df = pd.DataFrame(dispatch_rows)
st.dataframe(dispatch_df, use_container_width=True)

st.caption("AITARA DSS — Sistema de Apoyo a Decisiones de Movilidad Urbana. Respeta las restricciones del pliego (cero intervención automática de semáforos; 100% soporte al operador humano).")
