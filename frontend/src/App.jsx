import React, { useState, useEffect, useRef } from 'react'
import L from 'leaflet'
import AitaraAvatar from './components/AitaraAvatar'
import {
  Navigation,
  ExternalLink,
  Clock,
  CloudRain,
  Users,
  Send,
  Layers,
  Sun,
  Moon,
  MapPin,
  Copy,
  Check,
  FileText,
  AlertTriangle,
  Folder,
  FolderOpen,
  Search,
  LayoutGrid,
  List,
  Newspaper,
  SlidersHorizontal,
  CheckCircle2,
  ArrowRight,
  Radio,
  Car,
  ShieldCheck,
  Activity,
  ChevronDown,
  ChevronUp
} from 'lucide-react'

const SEVERITY_LABELS = {
  0: 'Sin daños',
  1: 'Daños materiales',
  2: 'Personas lesionadas',
  3: 'Fatal'
}

const SOURCE_LABELS = {
  primera_edicion: 'Primera Edición',
  misiones_online: 'Misiones Online',
  canal_12: 'Canal 12 Misiones',
  el_territorio: 'El Territorio'
}

function MarcaSimulado({ origen }) {
  return origen === 'simulado' ? <span style={{ background: '#92400e', color: '#fff', fontSize: '10px', fontWeight: 800, padding: '2px 5px', borderRadius: '4px', marginLeft: '5px' }}>SIMULADO</span> : null
}

function formatUbicacionVial(item, delimiter = ' × ') {
  if (!item) return 'Sin ubicación'
  if (item.calle_1 && item.calle_2) {
    const c1 = item.calle_1.replace('Av. ', '').replace('Calle ', '').trim()
    const c2 = item.calle_2.replace('Av. ', '').replace('Calle ', '').trim()
    return `${c1}${delimiter}${c2}`
  }
  if (item.referencia_espacial) {
    if (item.calle_1) {
      return `${item.calle_1.replace('Av. ', '').replace('Calle ', '')} (${item.referencia_espacial})`
    }
    return item.referencia_espacial
  }
  if (item.calle_1) {
    return item.calle_1.replace('Av. ', '').replace('Calle ', '')
  }
  if (item.ubicacion_texto && item.ubicacion_texto.length <= 60) {
    return item.ubicacion_texto
  }
  return 'Ubicación urbana'
}

export default function App() {
  const [theme, setTheme] = useState('light')
  const [activeTab, setActiveTab] = useState('tactico') // 'tactico' | 'estrategico' | 'repositorio'

  // Parámetros del Escenario Operativo (ahora en el HUD superior derecho del mapa)
  const [franja, setFranja] = useState('07:00')
  const [lluvia, setLluvia] = useState(15.0)

  // Modo de operación: false = Monitoreo de Noticias, true = Análisis de prioridades
  const [corridorMode, setCorridorMode] = useState(false)

  // Estados de Revelación Progresiva (Dropdowns y Acordeones Colapsables)
  const [isScenarioOpen, setIsScenarioOpen] = useState(false)
  const [showNewsInspector, setShowNewsInspector] = useState(true)
  const [showPriorities, setShowPriorities] = useState(true)
  const [showCriticalDetail, setShowCriticalDetail] = useState(false)

  // Capas visibles del mapa (por defecto en modo noticias: solo noticias visibles)
  const [showNodes, setShowNodes] = useState(false)
  const [showIncidents, setShowIncidents] = useState(true)

  // Funciones de conmutación de modos
  const activateCorridorAnalysis = () => {
    setCorridorMode(true)
    setShowNodes(true)
    setShowIncidents(false)
    setShowPriorities(true)
  }

  const activateNewsMonitoring = () => {
    setCorridorMode(false)
    setShowNodes(false)
    setShowIncidents(true)
    setShowNewsInspector(true)
  }

  // Datos del servidor
  const [status, setStatus] = useState(null)
  const [incidents, setIncidents] = useState([])
  const [evalData, setEvalData] = useState(null)
  const [strategic, setStrategic] = useState(null)

  // Selección activa en el mapa
  const [selectedIncident, setSelectedIncident] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)

  // Consulta al Asistente
  const [question, setQuestion] = useState('')
  const [lastAskedQuestion, setLastAskedQuestion] = useState('')
  const [analystReply, setAnalystReply] = useState(null)
  const [asking, setAsking] = useState(false)
  const [copied, setCopied] = useState(false)

  // Estado del Gestor Documental (Estilo Drive en Pestaña 3)
  const [selectedFolder, setSelectedFolder] = useState('all')
  const [driveViewMode, setDriveViewMode] = useState('grid') // 'grid' | 'list'
  const [searchQuery, setSearchQuery] = useState('')
  const [driveSelectedDoc, setDriveSelectedDoc] = useState(null)

  // Ingesta de Noticias bajo demanda y escaneo
  const [ingestUrl, setIngestUrl] = useState('')
  const [ingestLoading, setIngestLoading] = useState(false)
  const [ingestMessage, setIngestMessage] = useState(null)

  // Referencias de Leaflet
  const mapContainerRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const layersGroupRef = useRef(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  useEffect(() => {
    Promise.all([
      fetch('/api/status').then(r => r.ok ? r.json() : null).catch(() => null),
      fetch('/api/incidents').then(r => r.ok ? r.json() : []).catch(() => []),
      fetch('/api/strategic').then(r => r.ok ? r.json() : null).catch(() => null)
    ])
      .then(([st, inc, strat]) => {
        if (st) setStatus(st)
        if (inc && Array.isArray(inc) && inc.length > 0) {
          setIncidents(inc)
          setSelectedIncident(inc[0])
          setDriveSelectedDoc(inc[0])
        }
        if (strat && (strat.kpis?.length || strat.ranking_infraestructura?.length)) setStrategic(strat)
      })
      .catch(err => console.error('Error cargando datos iniciales:', err))
  }, [])

  useEffect(() => {
    fetch('/api/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        franja_horaria: franja,
        precipitacion_mm_h: Number(lluvia),
        actividad_escolar: true
      })
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) setEvalData(null)
        if (data) {
          setEvalData(data)
          if (data.nodos && data.nodos.length > 0 && !selectedNode) {
            setSelectedNode(data.nodos[0])
          }
        }
      })
      .catch(err => { setEvalData(null); console.error('Error evaluando escenario:', err) })
  }, [franja, lluvia])

  // Inicializar Mapa Leaflet una sola vez al montar
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return

    const map = L.map(mapContainerRef.current, {
      center: [-27.3815, -55.9065],
      zoom: 13,
      zoomControl: false
    })

    L.control.zoom({ position: 'bottomleft' }).addTo(map)
    L.control.scale({ imperial: false, position: 'bottomleft' }).addTo(map)

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap · Red Vial Posadas'
    }).addTo(map)

    layersGroupRef.current = L.layerGroup().addTo(map)
    mapInstanceRef.current = map
  }, [])

  // Al cambiar a la pestaña de mapa, recalcular geometría de Leaflet de inmediato
  useEffect(() => {
    if (activeTab === 'tactico' && mapInstanceRef.current) {
      setTimeout(() => {
        mapInstanceRef.current?.invalidateSize()
      }, 50)
    }
  }, [activeTab])

  // Actualizar capas sobre el mapa sin recargar
  useEffect(() => {
    const map = mapInstanceRef.current
    const group = layersGroupRef.current
    if (!map || !group) return

    group.clearLayers()

    // 2. Zonas de Monitoreo Preventivo (Halos y Etiquetas de Puntos Críticos)
    if (showNodes && evalData?.nodos) {
      evalData.nodos.forEach(nodo => {
        const isCrit = nodo.es_critico
        const color = isCrit ? '#be123c' : '#1d4ed8'

        const halo = L.circleMarker([nodo.lat, nodo.lon], {
          radius: isCrit ? 18 : 13,
          color: color,
          weight: 2,
          fillColor: color,
          fillOpacity: isCrit ? 0.22 : 0.14
        })

        const signVar = `${nodo.variacion_escenario >= 0 ? '+' : ''}${Number(nodo.variacion_escenario).toFixed(1).replace('.', ',')} %`
        halo.bindTooltip(
          `<div><strong>${nodo.nombre}</strong><br/>` +
          `Riesgo del escenario: <b>${nodo.riesgo_final}</b> <span style="font-size:9.5px; opacity:0.8;">(clima/franja)</span><br/>` +
          `Riesgo estructural: <b>${nodo.riesgo_estructural}</b> <span style="font-size:9.5px; opacity:0.8;">(base histórica)</span><br/>` +
          `Variación por estrés: <b>${signVar}</b></div>`,
          { direction: 'top' }
        )

        halo.on('click', () => {
          setSelectedNode(nodo)
          if (incidents.length > 0) {
            let closest = incidents[0]
            let bestDist = 999
            incidents.forEach(inc => {
              const d = Math.hypot(inc.lat - nodo.lat, inc.lon - nodo.lon)
              if (d < bestDist) {
                bestDist = d
                closest = inc
              }
            })
            if (bestDist < 0.018) {
              setSelectedIncident(closest)
            }
          }
        })

        halo.addTo(group)

        // Etiqueta permanente para puntos críticos identificados
        if (isCrit) {
          const shortName = nodo.nombre.replace('Av. ', '').replace('Calle ', '')
          const tag = L.tooltip({
            permanent: true,
            direction: 'right',
            offset: [16, -2],
            className: 'leaflet-tag-critical'
          })
            .setLatLng([nodo.lat, nodo.lon])
            .setContent(
              `<div style="display:flex; align-items:center; gap:5px;">
                <span style="background-color:#be123c; color:#fff; font-size:9px; font-weight:800; padding:1px 5px; border-radius:3px;">CRÍTICO</span>
                <strong style="font-size:11px; color:var(--text-primary);">${shortName}</strong>
                <span style="font-size:10px; font-weight:700; color:#be123c;">${Math.round(nodo.riesgo_final * 100)}%</span>
              </div>`
            )
          tag.addTo(group)
        }
      })
    }

    // 3. Sucesos Viales Reales (Marcadores de Noticias)
    if (showIncidents && incidents.length > 0) {
      incidents.forEach(inc => {
        const isHighSev = Number(inc.severidad) >= 2
        const isSelected = selectedIncident && selectedIncident.id === inc.id
        const fillColor = isHighSev ? '#be123c' : '#1d4ed8'

        const marker = L.circleMarker([inc.lat, inc.lon], {
          radius: isSelected ? 9.5 : 6.5,
          color: isSelected ? '#0f172a' : '#ffffff',
          weight: isSelected ? 3 : 2,
          fillColor: fillColor,
          fillOpacity: 0.95
        })

        const medioNombre = SOURCE_LABELS[inc.fuente] || inc.fuente
        marker.bindTooltip(
          `<div><strong>[${medioNombre}]</strong> ${inc.titulo}<br/>${inc.origen === 'simulado' ? '<strong style="background:#92400e;color:white">SIMULADO</strong>' : ''}</div>`,
          { direction: 'top' }
        )

        marker.on('click', () => {
          setSelectedIncident(inc)
          setShowNewsInspector(true)
          map.flyTo([inc.lat, inc.lon], Math.max(map.getZoom(), 14), { duration: 0.5 })
        })

        marker.addTo(group)
      })
    }
  }, [evalData, incidents, showNodes, showIncidents, selectedIncident])

  const handleAskAnalyst = async e => {
    e.preventDefault()
    const q = question.trim()
    if (!q) return
    setLastAskedQuestion(q)
    setQuestion('')
    setAsking(true)
    try {
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pregunta: q,
          franja_horaria: franja,
          precipitacion_mm_h: Number(lluvia)
        })
      })
      if (!res.ok) throw new Error('Consulta no disponible')
      const data = await res.json()
      setAnalystReply(data?.respuesta || 'Sin respuesta disponible.')
    } catch (err) {
      setAnalystReply('Sin respuesta disponible.')
      console.error(err)
    } finally {
      setAsking(false)
    }
  }

  const handleCopyPriorities = () => {
    const prioridades = evalData?.prioridades || []
    if (!prioridades.length) return
    navigator.clipboard.writeText(prioridades.map(p => `${p.nodo.nombre} · ${p.nivel} · ${p.riesgo_escenario}`).join('\n'))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleScanMedia = async () => {
    setIngestLoading(true)
    setIngestMessage(null)
    try {
      const res = await fetch('/api/ingest/scan?limite=8', { method: 'POST' })
      const data = await res.json()
      setIngestMessage({
        type: 'success',
        text: `Escaneo completado: ${data.nuevos_ingestados} incidentes viales nuevos (de ${data.articulos_analizados} notas analizadas). Total en sistema: ${data.total_actual}.`
      })
      const [incRes, stRes] = await Promise.all([
        fetch('/api/incidents'),
        fetch('/api/status')
      ])
      if (incRes.ok) setIncidents(await incRes.json())
      if (stRes.ok) setStatus(await stRes.json())
    } catch (err) {
      setIngestMessage({ type: 'error', text: 'Error al escanear portales de noticias.' })
    } finally {
      setIngestLoading(false)
    }
  }

  const handleIngestUrl = async (e) => {
    e.preventDefault()
    if (!ingestUrl.trim()) return
    setIngestLoading(true)
    setIngestMessage(null)
    try {
      const res = await fetch('/api/ingest/url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: ingestUrl.trim() })
      })
      const data = await res.json()
      if (data.status === 'ok') {
        setIngestMessage({ type: 'success', text: `${data.mensaje} [${data.incidente?.titulo || ''}]` })
        setIngestUrl('')
        const [incRes, stRes] = await Promise.all([
          fetch('/api/incidents'),
          fetch('/api/status')
        ])
        if (incRes.ok) setIncidents(await incRes.json())
        if (stRes.ok) setStatus(await stRes.json())
      } else {
        setIngestMessage({ type: 'info', text: data.mensaje })
      }
    } catch (err) {
      setIngestMessage({ type: 'error', text: 'Error al procesar la URL.' })
    } finally {
      setIngestLoading(false)
    }
  }

  const topCritico = evalData?.nodos?.find(nodo => nodo.es_critico) || null

  const sourceFolders = [
    { id: 'all', name: 'Todas las fuentes', count: incidents.length },
    ...Array.from(new Set(incidents.map(inc => inc.fuente).filter(Boolean))).map(id => ({ id, name: SOURCE_LABELS[id] || id, count: incidents.filter(inc => inc.fuente === id).length }))
  ]

  // Filtrado de documentos para la vista estilo Drive
  const filteredDriveDocs = incidents.filter(inc => {
    const matchFolder = selectedFolder === 'all' || inc.fuente === selectedFolder
    const q = searchQuery.toLowerCase().trim()
    const matchSearch =
      !q ||
      (inc.titulo || '').toLowerCase().includes(q) ||
      (inc.ubicacion_texto || '').toLowerCase().includes(q) ||
      (inc.calle_1 || '').toLowerCase().includes(q) ||
      (inc.calle_2 || '').toLowerCase().includes(q) ||
      String(inc.vehiculos || '').toLowerCase().includes(q)
    return matchFolder && matchSearch
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw' }}>
      {/* BARRA SUPERIOR INSTITUCIONAL (CERO JERGA TÉCNICA) */}
      <header
        style={{
          height: '56px',
          backgroundColor: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 20px',
          zIndex: 1000,
          flexShrink: 0
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
            <span style={{ fontSize: '20px', fontWeight: 800, letterSpacing: '-0.03em', color: 'var(--text-primary)' }}>
              AITARA
            </span>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                color: 'var(--accent-blue)',
                backgroundColor: 'var(--accent-blue-soft)',
                padding: '3px 8px',
                borderRadius: '4px',
                border: '1px solid var(--accent-blue-border)'
              }}
            >
              Movilidad Urbana
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>· Posadas</span>
          </div>

          {/* Pestañas de Navegación Limpias */}
          <nav style={{ display: 'flex', gap: '6px' }}>
            {[
              { id: 'tactico', label: 'Mapa de prioridades' },
              { id: 'estrategico', label: 'Análisis estratégico' },
              { id: 'repositorio', label: 'Centro de Información y Fuentes' }
            ].map(tab => {
              const active = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    padding: '7px 14px',
                    fontSize: '12px',
                    fontWeight: active ? 700 : 500,
                    color: active ? '#ffffff' : 'var(--text-secondary)',
                    backgroundColor: active ? 'var(--accent-blue)' : 'transparent',
                    border: active ? '1px solid var(--accent-blue)' : '1px solid transparent',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                >
                  {tab.label}
                </button>
              )
            })}
          </nav>
        </div>

        {/* Estado de Monitoreo y Selector Claro/Oscuro */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '11.5px',
              color: 'var(--text-secondary)',
              backgroundColor: 'var(--bg-subtle)',
              padding: '5px 11px',
              borderRadius: '6px',
              border: '1px solid var(--border-color)'
            }}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#16a34a',
                display: 'inline-block'
              }}
            />
            <span>Incidentes registrados</span>
            <span style={{ color: 'var(--text-muted)' }}>·</span>
            <strong>{status?.incidentes_por_origen?.real ?? 0} reales · {status?.incidentes_por_origen?.simulado ?? 0} SIMULADOS</strong>
          </div>

          <button
            onClick={() => setTheme(t => (t === 'light' ? 'dark' : 'light'))}
            title="Alternar Modo Claro / Modo Oscuro"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 11px',
              fontSize: '12px',
              fontWeight: 600,
              color: 'var(--text-primary)',
              backgroundColor: 'var(--bg-subtle)',
              border: '1px solid var(--border-strong)',
              borderRadius: '6px',
              cursor: 'pointer'
            }}
          >
            {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
            <span>{theme === 'light' ? 'Modo Oscuro' : 'Modo Claro'}</span>
          </button>
        </div>
      </header>

      {/* =====================================================================
          PESTAÑA 1: MAPA DE PRIORIDADES
         ===================================================================== */}
      <div
        style={{
          display: activeTab === 'tactico' ? 'flex' : 'none',
          flex: 1,
          height: 'calc(100vh - 56px)',
          maxHeight: 'calc(100vh - 56px)',
          minHeight: 0,
          overflow: 'hidden',
          position: 'relative'
        }}
      >
          {/* CUADRANTE DEL MAPA (IZQUIERDA) */}
          <div
            className={theme === 'light' ? 'map-tiles-light' : 'map-tiles-dark'}
            style={{ flex: 1, position: 'relative', height: '100%' }}
          >
            <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />

            {/* HUD FLOTANTE SUPERIOR IZQUIERDO: CAPAS CARTOGRÁFICAS Y ACCESO RÁPIDO */}
            <div
              style={{
                position: 'absolute',
                top: '14px',
                left: '14px',
                zIndex: 800,
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                maxWidth: '350px'
              }}
            >
              <div
                style={{
                  backgroundColor: 'var(--bg-glass)',
                  backdropFilter: 'blur(10px)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  padding: '10px 12px',
                  boxShadow: 'var(--shadow-md)'
                }}
              >
                <div
                  style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    color: 'var(--text-muted)',
                    marginBottom: '6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <Layers size={12} /> Capas Cartográficas Activas (Posadas)
                </div>
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11.5px', cursor: 'pointer', fontWeight: 500 }}>
                    <input type="checkbox" checked={showNodes} onChange={e => setShowNodes(e.target.checked)} />
                    <span>Corredores Críticos</span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11.5px', cursor: 'pointer', fontWeight: 500 }}>
                    <input type="checkbox" checked={showIncidents} onChange={e => setShowIncidents(e.target.checked)} />
                    <span>Noticias Georreferenciadas</span>
                  </label>
                </div>
              </div>

              {/* Acceso directo a esquinas con noticias */}
              <div
                style={{
                  backgroundColor: 'var(--bg-glass)',
                  backdropFilter: 'blur(10px)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  padding: '8px 10px',
                  boxShadow: 'var(--shadow-sm)'
                }}
              >
                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '5px' }}>
                  Foco Rápido en Sucesos Recientes:
                </div>
                <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                  {incidents.slice(0, 6).map(inc => {
                    const isSel = selectedIncident?.id === inc.id
                    return (
                      <button
                        key={inc.id}
                        onClick={() => {
                          setSelectedIncident(inc)
                          if (mapInstanceRef.current) {
                            mapInstanceRef.current.flyTo([inc.lat, inc.lon], 15, { duration: 0.6 })
                          }
                        }}
                        style={{
                          fontSize: '10.5px',
                          fontWeight: 600,
                          padding: '3px 8px',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          backgroundColor: isSel ? 'var(--accent-blue)' : 'var(--bg-subtle)',
                          color: isSel ? '#ffffff' : 'var(--text-secondary)',
                          border: '1px solid var(--border-strong)'
                        }}
                      >
                        {(() => {
                          const raw = formatUbicacionVial(inc, ' × ')
                          const label = raw.length > 22 ? `${raw.slice(0, 22)}…` : raw
                          return (
                            <>
                              {label}
                              <MarcaSimulado origen={inc.origen} />
                            </>
                          )
                        })()}
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>

            {/* CONTROLES SUPERIORES DERECHOS DEL MAPA (CONMUTACIÓN DE MODO) */}
            <div
              style={{
                position: 'absolute',
                top: '14px',
                right: '14px',
                zIndex: 800
              }}
            >
              {!corridorMode ? (
                /* BOTÓN PRINCIPAL PARA EJECUTAR ANÁLISIS DE CORREDORES */
                <button
                  onClick={activateCorridorAnalysis}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    backgroundColor: '#1d4ed8',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '20px',
                    padding: '8px 18px',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    boxShadow: '0 4px 14px rgba(29, 78, 216, 0.45)',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <Activity size={14} />
                  <span>Realizar Análisis de Corredores</span>
                  <ArrowRight size={13} />
                </button>
              ) : (
                /* MODO CORREDORES ACTIVO: BOTÓN DE RETORNO AL MONITOREO DE NOTICIAS */
                <button
                  onClick={activateNewsMonitoring}
                  title="Ocultar corredores y volver a los puntos de noticias"
                  style={{
                    backgroundColor: 'var(--bg-glass)',
                    backdropFilter: 'blur(10px)',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '20px',
                    padding: '7px 14px',
                    fontSize: '11.5px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    boxShadow: 'var(--shadow-sm)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <Newspaper size={13} color="var(--accent-blue)" />
                  <span>Volver a Noticias de Prensa</span>
                </button>
              )}
            </div>

            {/* Leyenda Inferior Derecha dentro del Mapa (Contextual según Modo) */}
            <div
              style={{
                position: 'absolute',
                bottom: '16px',
                right: '14px',
                zIndex: 800,
                backgroundColor: 'var(--bg-glass)',
                backdropFilter: 'blur(8px)',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                padding: '8px 12px',
                boxShadow: 'var(--shadow-md)',
                display: 'flex',
                gap: '14px',
                fontSize: '11px',
                color: 'var(--text-secondary)'
              }}
            >
              {corridorMode ? (
                <>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#be123c', display: 'inline-block' }} />
                    <strong>Nodo crítico</strong>
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#1d4ed8', display: 'inline-block' }} />
                    <strong>Monitoreo Preventivo</strong>
                  </span>
                </>
              ) : (
                <>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#be123c', display: 'inline-block' }} />
                    <strong>Siniestro Grave en Prensa</strong>
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#1d4ed8', display: 'inline-block' }} />
                    <strong>Incidente / Calzada Reducida</strong>
                  </span>
                </>
              )}
            </div>
          </div>

          {/* PANEL DERECHO DE DECISIONES E INSPECTOR DE NOTICIAS (495px) */}
          <aside
            style={{
              width: '495px',
              height: '100%',
              maxHeight: '100%',
              backgroundColor: 'var(--bg-surface)',
              borderLeft: '1px solid var(--border-color)',
              overflowY: 'auto',
              overflowX: 'hidden',
              padding: '16px 18px 60px 18px',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
              flexShrink: 0,
              zIndex: 900
            }}
          >
            {/* 1. ASISTENTE DE CONSULTAS Y RECOMENDACIONES CON IA (EN LA PARTE SUPERIOR) */}
            <div
              style={{
                backgroundColor: 'var(--bg-canvas)',
                border: '1px solid var(--border-strong)',
                borderRadius: '10px',
                padding: '14px 16px',
                boxShadow: 'var(--shadow-sm)',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px'
              }}
            >
              {/* Cabecera con Avatar estilo Grokbot y Estado en Línea */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <AitaraAvatar state={asking ? 'thinking' : 'idle'} size={46} />
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary)' }}>
                        Asistente AITARA
                      </span>
                      <span
                        style={{
                          fontSize: '9.5px',
                          fontWeight: 700,
                          textTransform: 'uppercase',
                          letterSpacing: '0.04em',
                          color: '#16a34a',
                          backgroundColor: 'rgba(22, 163, 74, 0.12)',
                          padding: '2px 7px',
                          borderRadius: '4px',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px'
                        }}
                      >
                        <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#16a34a' }} />
                        Analista
                      </span>
                    </div>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      Información vial y soporte de decisiones
                    </span>
                  </div>
                </div>
              </div>

              {/* Botones de Consulta Rápida (Sugerencias 1-Click) */}
              <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                {[
                  '¿Cuáles son las prioridades del escenario?',
                  '¿Qué factores explican el riesgo?'
                ].map((sug, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setQuestion(sug)
                    }}
                    style={{
                      fontSize: '10px',
                      fontWeight: 600,
                      color: 'var(--accent-blue)',
                      backgroundColor: 'var(--accent-blue-soft)',
                      border: '1px solid var(--accent-blue-border)',
                      borderRadius: '5px',
                      padding: '3px 8px',
                      cursor: 'pointer',
                      textAlign: 'left'
                    }}
                  >
                    {sug}
                  </button>
                ))}
              </div>

              {/* Formulario de Consulta */}
              <form onSubmit={handleAskAnalyst} style={{ display: 'flex', gap: '6px' }}>
                <input
                  type="text"
                  value={question}
                  onChange={e => setQuestion(e.target.value)}
                  placeholder="Consulta al Analista"
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    fontSize: '12px',
                    borderRadius: '6px',
                    border: '1px solid var(--border-strong)',
                    backgroundColor: 'var(--bg-surface)',
                    color: 'var(--text-primary)',
                    outline: 'none'
                  }}
                />
                <button
                  type="submit"
                  disabled={asking || !question.trim()}
                  style={{
                    padding: '8px 14px',
                    backgroundColor: asking ? 'var(--text-muted)' : 'var(--accent-blue)',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '6px',
                    fontWeight: 600,
                    fontSize: '12px',
                    cursor: asking ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    transition: 'background-color 0.15s ease'
                  }}
                >
                  <span>Consultar</span>
                  <Send size={12} />
                </button>
              </form>

              {/* Estado Animado de Pensamiento / Loading */}
              {asking && (
                <div
                  style={{
                    backgroundColor: 'var(--accent-blue-soft)',
                    border: '1px solid var(--accent-blue-border)',
                    borderRadius: '8px',
                    padding: '10px 14px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px'
                  }}
                >
                  <div style={{ display: 'flex', gap: '4px' }}>
                    <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: 'var(--accent-blue)', animation: 'dotPulse 1.2s infinite ease-in-out', animationDelay: '0s' }} />
                    <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: 'var(--accent-blue)', animation: 'dotPulse 1.2s infinite ease-in-out', animationDelay: '0.2s' }} />
                    <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: 'var(--accent-blue)', animation: 'dotPulse 1.2s infinite ease-in-out', animationDelay: '0.4s' }} />
                  </div>
                  <span style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--accent-blue)' }}>
                    AITARA analizando la red vial de Posadas y modelos de tránsito...
                  </span>
                </div>
              )}

              {/* Respuesta del Analista */}
              {analystReply && !asking && (
                <div
                  style={{
                    backgroundColor: 'var(--accent-blue-soft)',
                    border: '1px solid var(--accent-blue-border)',
                    borderRadius: '8px',
                    padding: '12px 14px',
                    fontSize: '12px',
                    color: 'var(--text-primary)',
                    lineHeight: 1.5
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginBottom: '8px', borderBottom: '1px solid var(--accent-blue-border)', paddingBottom: '6px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--accent-blue)' }}>
                        Resumen del Analista
                      </span>
                      <button
                        type="button"
                        onClick={() => setAnalystReply(null)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: '11px', padding: '0 4px' }}
                        title="Cerrar respuesta"
                      >
                        ✕
                      </button>
                    </div>
                    {lastAskedQuestion && (
                      <span style={{ fontSize: '11.5px', color: 'var(--text-secondary)', fontStyle: 'italic', fontWeight: 500 }}>
                        “{lastAskedQuestion}”
                      </span>
                    )}
                  </div>
                  <div
                    style={{
                      maxHeight: '170px',
                      overflowY: 'auto',
                      overflowX: 'hidden',
                      paddingRight: '6px',
                      whiteSpace: 'pre-line',
                      lineHeight: '1.6'
                    }}
                    dangerouslySetInnerHTML={{
                      __html: analystReply
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;')
                        .replace(/"/g, '&quot;')
                        .replace(/'/g, '&#39;')
                        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                        .replace(/^### (.*$)/gim, '<h4 style="margin:8px 0 4px; color:var(--text-primary);">$1</h4>')
                        .replace(/^## (.*$)/gim, '<h3 style="margin:10px 0 4px; color:var(--text-primary);">$1</h3>')
                    }}
                  />
                </div>
              )}
            </div>

            {/* =======================================================
                CONTENIDO DEL PANEL DERECHO SEGÚN EL MODO ACTIVO
               ======================================================= */}

            {!corridorMode ? (
              /* =====================================================
                 MODO 1: MONITOREO DE NOTICIAS DE PRENSA (DEFAULT)
                 - Muestra el llamador para Análisis de Corredores
                 - Muestra el Inspector de Noticias
                 - Variables disponibles en el análisis
                 ===================================================== */
              <>
                {/* Banner de Acción: Realizar Análisis de Corredores */}
                <div
                  style={{
                    backgroundColor: 'var(--accent-blue-soft)',
                    border: '1px solid var(--accent-blue-border)',
                    borderRadius: '10px',
                    padding: '14px 16px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Activity size={16} color="var(--accent-blue)" />
                    <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                      Análisis de prioridades
                    </strong>
                  </div>
                  <p style={{ fontSize: '11.5px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    El monitoreo reúne incidentes disponibles. El análisis permite consultar prioridades para el escenario seleccionado.
                  </p>
                  <button
                    onClick={activateCorridorAnalysis}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                      backgroundColor: 'var(--accent-blue)',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '6px',
                      padding: '9px 14px',
                      fontWeight: 700,
                      fontSize: '12px',
                      cursor: 'pointer',
                      marginTop: '2px',
                      boxShadow: '0 2px 6px rgba(29, 78, 216, 0.25)'
                    }}
                  >
                    <SlidersHorizontal size={13} />
                    <span>Realizar Análisis de Corredores</span>
                    <ArrowRight size={13} />
                  </button>
                </div>

                {/* Inspector de Noticias Periodísticas (Desplegado en Modo Prensa) */}
                <div
                  style={{
                    backgroundColor: 'var(--bg-canvas)',
                    border: '1px solid var(--border-strong)',
                    borderRadius: '10px',
                    overflow: 'hidden',
                    boxShadow: 'var(--shadow-sm)'
                  }}
                >
                  <button
                    onClick={() => setShowNewsInspector(open => !open)}
                    style={{
                      width: '100%',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '10px 14px',
                      backgroundColor: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      color: 'var(--text-primary)'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Newspaper size={14} color="var(--accent-blue)" />
                      <span style={{ fontSize: '11.5px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        Inspector de Prensa y Sucesos Viales
                      </span>
                      <span
                        style={{
                          fontSize: '10px',
                          backgroundColor: 'var(--bg-subtle)',
                          padding: '2px 7px',
                          borderRadius: '4px',
                          color: 'var(--text-muted)',
                          fontWeight: 600
                        }}
                      >
                        {selectedIncident ? 'Seleccionado' : `${incidents.length} disponibles`}
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '11px' }}>
                      <span>{showNewsInspector ? 'Ocultar' : 'Ver detalle'}</span>
                      {showNewsInspector ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                    </div>
                  </button>

                  {showNewsInspector && (
                    <div style={{ borderTop: '1px solid var(--border-color)', padding: '12px 14px' }}>
                      {selectedIncident ? (
                        <div>
                          {/* Cabecera Editorial del Medio */}
                          <div
                            style={{
                              backgroundColor: Number(selectedIncident.severidad) >= 2 ? 'var(--alert-crimson-soft)' : 'var(--accent-blue-soft)',
                              borderBottom: '1px solid var(--border-color)',
                              borderRadius: '6px 6px 0 0',
                              padding: '9px 12px',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center'
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span
                                style={{
                                  backgroundColor: Number(selectedIncident.severidad) >= 2 ? 'var(--alert-crimson)' : 'var(--accent-blue)',
                                  color: '#ffffff',
                                  fontSize: '10px',
                                  fontWeight: 800,
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  textTransform: 'uppercase',
                                  letterSpacing: '0.04em'
                                }}
                              >
                                {SOURCE_LABELS[selectedIncident.fuente] || selectedIncident.fuente}<MarcaSimulado origen={selectedIncident.origen} />
                              </span>
                              <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 600 }}>
                                {selectedIncident.fecha_evento ? `${selectedIncident.fecha_evento.replace('T', ' ').slice(0, 16)} hs` : 'Reciente'}
                              </span>
                            </div>

                            <span
                              style={{
                                fontSize: '10.5px',
                                fontWeight: 700,
                                color: Number(selectedIncident.severidad) >= 2 ? 'var(--alert-crimson)' : 'var(--accent-blue)',
                                textTransform: 'uppercase'
                              }}
                            >
                              {selectedIncident.tipo_incidente?.replace('_', ' ')}
                            </span>
                          </div>

                          {/* Cuerpo del Recorte Periodístico */}
                          <div style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderTop: 'none', borderRadius: '0 0 6px 6px', padding: '12px 14px' }}>
                            <h3
                              style={{
                                fontSize: '13.5px',
                                fontWeight: 800,
                                color: 'var(--text-primary)',
                                lineHeight: 1.35,
                                marginBottom: '6px'
                              }}
                            >
                              “{selectedIncident.titulo}”
                            </h3>

                            <p
                              style={{
                                fontSize: '11.5px',
                                color: 'var(--text-secondary)',
                                lineHeight: 1.45,
                                marginBottom: '10px',
                                paddingLeft: '10px',
                                borderLeft: '2px solid var(--border-strong)'
                              }}
                            >
                              {selectedIncident.resumen}
                            </p>

                            {/* Ficha de Variables Extraídas Automáticamente */}
                            <div
                              style={{
                                backgroundColor: 'var(--bg-canvas)',
                                border: '1px solid var(--border-color)',
                                borderRadius: '6px',
                                padding: '8px 10px',
                                marginBottom: '10px'
                              }}
                            >
                              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '8px', fontSize: '11px' }}>
                                <div>
                                  <span style={{ fontSize: '9.5px', color: 'var(--text-muted)', display: 'block' }}>Lugar del Hecho</span>
                                  <strong style={{ color: 'var(--text-primary)' }}>
                                    {selectedIncident.ubicacion_texto && selectedIncident.ubicacion_texto.length <= 80
                                      ? selectedIncident.ubicacion_texto
                                      : formatUbicacionVial(selectedIncident, ' y ')}
                                  </strong>
                                </div>
                                <div>
                                  <span style={{ fontSize: '9.5px', color: 'var(--text-muted)', display: 'block' }}>Calles Identificadas</span>
                                  <strong style={{ color: 'var(--text-primary)' }}>
                                    {formatUbicacionVial(selectedIncident, ' y ')}
                                  </strong>
                                </div>
                                <div>
                                  <span style={{ fontSize: '9.5px', color: 'var(--text-muted)', display: 'block' }}>Gravedad Estimada</span>
                                  <span
                                    style={{
                                      fontWeight: 700,
                                      color: Number(selectedIncident.severidad) >= 2 ? 'var(--alert-crimson)' : 'var(--accent-blue)'
                                    }}
                                  >
                                    {SEVERITY_LABELS[selectedIncident.severidad] || selectedIncident.severidad}
                                  </span>
                                </div>
                                <div>
                                  <span style={{ fontSize: '9.5px', color: 'var(--text-muted)', display: 'block' }}>Vehículos Involucrados</span>
                                  <strong style={{ color: 'var(--text-primary)', textTransform: 'capitalize' }}>
                                    {selectedIncident.vehiculos || 'Sin datos'}
                                  </strong>
                                </div>
                              </div>
                            </div>

                            {/* Pie con Coordenadas y Botón al Diario Original */}
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span className="mono" style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                                GPS: {Number(selectedIncident.lat).toFixed(4)}, {Number(selectedIncident.lon).toFixed(4)}
                              </span>

                              <a
                                href={selectedIncident.url}
                                target="_blank"
                                rel="noreferrer"
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '5px',
                                  padding: '5px 10px',
                                  borderRadius: '5px',
                                  backgroundColor: 'var(--accent-blue)',
                                  color: '#ffffff',
                                  fontSize: '11px',
                                  fontWeight: 600,
                                  textDecoration: 'none'
                                }}
                              >
                                <span>Leer nota completa</span>
                                <ExternalLink size={11} />
                              </a>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div style={{ textAlign: 'center', padding: '16px 12px', color: 'var(--text-muted)', fontSize: '11.5px', lineHeight: 1.5 }}>
                          {incidents.length ? 'Hay incidentes disponibles en el mapa.' : 'Sin incidentes disponibles.'}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </>
            ) : (
              /* =====================================================
                 MODO 2: ANÁLISIS DE PRIORIDADES
                 - Puntos de noticias desaparecen del mapa
                 - Aparece el ajuste de variables
                 - Aparecen las prioridades y su evidencia
                 ===================================================== */
              <>
                {/* Barra de Modo Activo y Retorno */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    backgroundColor: 'var(--accent-blue-soft)',
                    border: '1px solid var(--accent-blue-border)',
                    borderRadius: '8px',
                    padding: '8px 12px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', fontWeight: 700, color: 'var(--accent-blue)' }}>
                    <Activity size={14} />
                    <span>Análisis de Corredores Activo</span>
                  </div>
                  <button
                    onClick={activateNewsMonitoring}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                      backgroundColor: 'var(--bg-surface)',
                      border: '1px solid var(--border-strong)',
                      borderRadius: '5px',
                      padding: '4px 9px',
                      fontSize: '11px',
                      fontWeight: 600,
                      color: 'var(--text-secondary)',
                      cursor: 'pointer'
                    }}
                  >
                    <Newspaper size={12} color="var(--accent-blue)" />
                    <span>Ver Noticias</span>
                  </button>
                </div>

                {/* AJUSTE DE VARIABLES DEL ESCENARIO OPERATIVO (FRANJA Y LLUVIA) */}
                <div
                  style={{
                    backgroundColor: 'var(--bg-canvas)',
                    border: '1px solid var(--border-strong)',
                    borderRadius: '10px',
                    padding: '12px 14px',
                    boxShadow: 'var(--shadow-sm)'
                  }}
                >
                  <div
                    style={{
                      fontSize: '10.5px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      color: 'var(--accent-blue)',
                      marginBottom: '8px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}
                  >
                    <SlidersHorizontal size={13} /> Ajuste de Variables del Escenario
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
                    <div>
                      <label style={{ fontSize: '9.5px', fontWeight: 700, color: 'var(--text-muted)', display: 'block', marginBottom: '3px' }}>
                        FRANJA HORARIA
                      </label>
                      <select
                        value={franja}
                        onChange={e => setFranja(e.target.value)}
                        style={{
                          width: '100%',
                          padding: '5px 6px',
                          fontSize: '11.5px',
                          fontWeight: 600,
                          borderRadius: '5px',
                          border: '1px solid var(--border-strong)',
                          backgroundColor: 'var(--bg-surface)',
                          color: 'var(--text-primary)',
                          cursor: 'pointer'
                        }}
                      >
                        <option value="07:00">07:00 hs</option>
                        <option value="12:00">12:00 hs</option>
                        <option value="18:00">18:00 hs</option>
                      </select>
                    </div>

                    <div>
                      <label style={{ fontSize: '9.5px', fontWeight: 700, color: 'var(--text-muted)', display: 'block', marginBottom: '3px' }}>
                        PRECIPITACIÓN (mm/h)
                      </label>
                      <select
                        value={lluvia}
                        onChange={e => setLluvia(Number(e.target.value))}
                        style={{
                          width: '100%',
                          padding: '5px 6px',
                          fontSize: '11.5px',
                          fontWeight: 600,
                          borderRadius: '5px',
                          border: '1px solid var(--border-strong)',
                          backgroundColor: 'var(--bg-surface)',
                          color: 'var(--text-primary)',
                          cursor: 'pointer'
                        }}
                      >
                        <option value={0}>0 mm (Seco)</option>
                        <option value={15}>15 mm/h (Lluvia)</option>
                        <option value={40}>40 mm/h (Temporal)</option>
                      </select>
                    </div>

                  </div>
                </div>

                {/* PUNTO CRÍTICO DE ATENCIÓN PRIORITARIA */}
                {topCritico && (
                  <div
                    style={{
                      backgroundColor: 'var(--alert-crimson-soft)',
                      border: '1px solid var(--alert-crimson-border)',
                      borderLeft: '4px solid var(--alert-crimson)',
                      borderRadius: '8px',
                      padding: '9px 12px'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                        <AlertTriangle size={13} color="var(--alert-crimson)" />
                        <span style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: 'var(--alert-crimson)', letterSpacing: '0.04em' }}>
                          Punto Crítico ({franja} hs):
                        </span>
                        <strong style={{ fontSize: '12px', color: 'var(--text-primary)' }}>{topCritico.nombre}</strong>
                        <span
                          style={{
                            backgroundColor: 'var(--alert-crimson)',
                            color: '#ffffff',
                            fontSize: '10px',
                            fontWeight: 700,
                            padding: '1px 6px',
                            borderRadius: '3px'
                          }}
                        >
                          {Math.round(topCritico.riesgo_final * 100)}%
                        </span>
                      </div>
                      <button
                        onClick={() => setShowCriticalDetail(open => !open)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--alert-crimson)',
                          fontSize: '10.5px',
                          fontWeight: 700,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '3px'
                        }}
                      >
                        <span>{showCriticalDetail ? 'Ocultar' : 'Factores'}</span>
                        {showCriticalDetail ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                      </button>
                    </div>
                    {showCriticalDetail && (
                      <p style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: '6px', paddingTop: '6px', borderTop: '1px solid var(--alert-crimson-border)' }}>
                        <strong>Factores de riesgo:</strong> {topCritico.factores.join(' · ')}.
                      </p>
                    )}
                  </div>
                )}

                {/* Prioridades y trazabilidad del escenario */}
                <div style={{ backgroundColor: 'var(--bg-canvas)', border: '1px solid var(--border-strong)', borderRadius: '10px', overflow: 'hidden', boxShadow: 'var(--shadow-sm)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px' }}>
                    <button onClick={() => setShowPriorities(open => !open)} style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-primary)' }}>
                      <ShieldCheck size={14} color="#16a34a" /> <strong>Prioridades</strong>
                      {showPriorities ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                    </button>
                    <button onClick={handleCopyPriorities} style={{ color: 'var(--accent-blue)', cursor: 'pointer' }}>
                      {copied ? <Check size={12} /> : <Copy size={12} />} {copied ? 'Copiado' : 'Copiar'}
                    </button>
                  </div>
                  {showPriorities && (
                    <div
                      style={{
                        borderTop: '1px solid var(--border-color)',
                        padding: '10px 12px',
                        paddingRight: '8px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '8px',
                        maxHeight: '440px',
                        overflowY: 'auto',
                        overflowX: 'hidden'
                      }}
                    >
                      <div style={{ fontSize: '10.5px', color: 'var(--text-secondary)', padding: '6px 9px', backgroundColor: 'var(--bg-surface)', borderRadius: '6px', border: '1px solid var(--border-color)', lineHeight: 1.35 }}>
                        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>Guía de métricas:</span>{' '}
                        <strong>Riesgo estructural</strong> es la base histórica del punto según incidentes. <strong>Riesgo del escenario</strong> proyecta el impacto dinámico al sumar lluvia y hora pico.
                      </div>
                      {!evalData?.prioridades?.length && <p>Sin prioridades disponibles para este escenario.</p>}
                      {(evalData?.prioridades || []).map(prioridad => (
                        <div key={prioridad.nodo.nodo_id} style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '10px 12px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                            <strong style={{ fontSize: '12px', color: 'var(--text-primary)' }}>{prioridad.nodo.nombre}</strong>
                            <span
                              style={{
                                fontSize: '9.5px',
                                fontWeight: 700,
                                textTransform: 'uppercase',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                backgroundColor: prioridad.nivel === 'critico' ? 'var(--alert-crimson-soft)' : 'var(--accent-blue-soft)',
                                color: prioridad.nivel === 'critico' ? 'var(--alert-crimson)' : 'var(--accent-blue)',
                                border: `1px solid ${prioridad.nivel === 'critico' ? 'var(--alert-crimson-border)' : 'var(--accent-blue-border)'}`
                              }}
                            >
                              {prioridad.nivel === 'critico' ? 'Crítico' : 'No crítico'}
                            </span>
                          </div>

                          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '3px', fontSize: '11px', backgroundColor: 'var(--bg-canvas)', padding: '6px 8px', borderRadius: '5px', border: '1px solid var(--border-color)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span><strong>Riesgo del escenario:</strong> <span style={{ color: prioridad.nivel === 'critico' ? 'var(--alert-crimson)' : 'var(--accent-blue)', fontWeight: 700 }}>{prioridad.riesgo_escenario}</span></span>
                              <span style={{ fontSize: '9.5px', color: 'var(--text-muted)' }}>(con clima y franja)</span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span><strong>Riesgo estructural:</strong> <span style={{ fontWeight: 600 }}>{prioridad.riesgo_estructural}</span></span>
                              <span style={{ fontSize: '9.5px', color: 'var(--text-muted)' }}>(línea base histórica)</span>
                            </div>
                            <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', paddingTop: '2px', borderTop: '1px dashed var(--border-color)' }}>
                              Variación por estrés: <strong style={{ color: prioridad.variacion_escenario >= 0 ? 'var(--alert-crimson)' : 'var(--accent-blue)' }}>{prioridad.variacion_escenario >= 0 ? '+' : ''}{Number(prioridad.variacion_escenario).toFixed(1).replace('.', ',')} %</strong>
                            </div>
                          </div>
                          <div style={{ marginTop: '6px', fontWeight: 700 }}>Aportes por factor</div>
                          {(prioridad.aportes || []).map(aporte => (
                            <div key={aporte.nombre} style={{ marginTop: '5px', fontSize: '11px' }}>
                              <div>{aporte.nombre}: {Number(aporte.aporte).toFixed(2)} · {aporte.descripcion}</div>
                              <div style={{ height: '6px', backgroundColor: 'var(--bg-subtle)', borderRadius: '4px' }}>
                                <div style={{ height: '100%', width: `${Math.max(0, Math.min(100, aporte.aporte * 100))}%`, backgroundColor: 'var(--accent-blue)', borderRadius: '4px' }} />
                              </div>
                            </div>
                          ))}
                          <div style={{ marginTop: '8px', fontWeight: 700 }}>Evidencia</div>
                          <div>Mostrando {prioridad.evidencia?.length || 0} de {prioridad.total_evidencia} · {prioridad.evidencia_real} reales · {prioridad.evidencia_simulada} SIMULADOS</div>
                          {prioridad.evidencia_simulada > 0 && prioridad.evidencia_real === 0 && <div>Evidencia solo SIMULADA</div>}
                          {!prioridad.evidencia?.length && <div>Sin incidentes de evidencia registrados</div>}
                          {(prioridad.evidencia || []).map(ev => (
                            <div key={ev.id} style={{ fontSize: '11px', marginTop: '4px' }}>
                              {ev.url ? <a href={ev.url} target="_blank" rel="noreferrer">{ev.fuente} · {ev.tipo}</a> : <span>{ev.fuente} · {ev.tipo} (sin enlace)</span>}
                              {' · '}{ev.fecha}<MarcaSimulado origen={ev.origen} />
                            </div>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Inspector de Noticias Colapsado (Opcional en Modo Corredores) */}
                <div
                  style={{
                    backgroundColor: 'var(--bg-canvas)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    overflow: 'hidden'
                  }}
                >
                  <button
                    onClick={() => setShowNewsInspector(open => !open)}
                    style={{
                      width: '100%',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '8px 12px',
                      backgroundColor: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      color: 'var(--text-secondary)',
                      fontSize: '11px'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Newspaper size={13} color="var(--text-muted)" />
                      <span>Ver Recortes de Prensa Históricos ({incidents.length})</span>
                    </div>
                    {showNewsInspector ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  </button>

                  {showNewsInspector && selectedIncident && (
                    <div style={{ borderTop: '1px solid var(--border-color)', padding: '10px 12px', fontSize: '11.5px' }}>
                      <strong style={{ color: 'var(--text-primary)' }}>“{selectedIncident.titulo}”</strong><MarcaSimulado origen={selectedIncident.origen} />
                      <p style={{ color: 'var(--text-secondary)', margin: '4px 0' }}>{selectedIncident.resumen}</p>
                      <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{selectedIncident.ubicacion_texto}</span>
                    </div>
                  )}
                </div>
              </>
            )}
          </aside>
        </div>

      {/* =====================================================================
          PESTAÑA 2: PLANIFICACIÓN DE OBRAS VIALES (SIN ETIQUETAS TÉCNICAS)
         ===================================================================== */}
      <div style={{ display: activeTab === 'estrategico' ? 'block' : 'none', flex: 1, overflowY: 'auto', padding: '28px 36px', maxWidth: '1280px', margin: '0 auto', width: '100%' }}>
        {strategic ? (
          <>
            <div style={{ marginBottom: '20px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text-primary)' }}>
                Análisis estratégico de prioridades
              </h2>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                Escenario de referencia: {strategic.escenario_referencia ? `día ${strategic.escenario_referencia.dia_semana}, ${strategic.escenario_referencia.franja_horaria}, ${strategic.escenario_referencia.precipitacion_mm_h} mm/h, actividad escolar ${strategic.escenario_referencia.actividad_escolar ? 'sí' : 'no'}` : 'no disponible'}.
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
              {(strategic.kpis || []).map((k, idx) => (
                <div
                  key={idx}
                  style={{
                    backgroundColor: 'var(--bg-surface)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '10px',
                    padding: '18px 20px',
                    boxShadow: 'var(--shadow-sm)'
                  }}
                >
                  <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '6px' }}>
                    {k.label}
                  </div>
                  <div
                    style={{
                      fontSize: '28px',
                      fontWeight: 800,
                      color: k.tone === 'red' ? 'var(--alert-crimson)' : k.tone === 'blue' ? 'var(--accent-blue)' : 'var(--text-primary)',
                      marginBottom: '4px'
                    }}
                  >
                    {k.label === 'Incidentes registrados' ? `${k.reales} reales · ${k.simulados} SIMULADOS` : k.value}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{k.sub}</div>
                </div>
              ))}
            </div>

            <div
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                overflow: 'hidden',
                boxShadow: 'var(--shadow-sm)'
              }}
            >
              <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border-color)', fontWeight: 700, fontSize: '13.5px' }}>
                Ranking de prioridades
              </div>
              <p style={{ padding: '0 18px', color: 'var(--text-secondary)' }}>El ranking se calcula principalmente con datos SIMULADOS y demuestra el método; no afirma resultados sobre la ciudad.</p>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12.5px', textAlign: 'left' }}>
                <thead>
                  <tr style={{ backgroundColor: 'var(--bg-subtle)', color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase' }}>
                    <th style={{ padding: '12px 16px' }}>Intersección / Corredor</th>
                    <th style={{ padding: '12px 16px' }}>Ubicación Geográfica</th>
                    <th style={{ padding: '12px 16px' }}>Nivel</th>
                    <th style={{ padding: '12px 16px' }}>Riesgo estructural</th>
                    <th style={{ padding: '12px 16px' }}>Factor de mayor aporte / Evidencia</th>
                  </tr>
                </thead>
                <tbody>
                  {(strategic.ranking_infraestructura || []).map(row => (
                    <tr key={row.nodo_id} style={{ borderTop: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '14px 16px', fontWeight: 700, color: 'var(--text-primary)' }}>{row.interseccion}</td>
                      <td className="mono" style={{ padding: '14px 16px', color: 'var(--text-muted)', fontSize: '11.5px' }}>
                        {row.coordenadas?.map(c => Number(c).toFixed(5)).join(', ')}
                      </td>
                      <td style={{ padding: '14px 16px', color: 'var(--text-secondary)' }}>{row.nivel === 'critico' ? 'Crítico' : 'No crítico'}</td>
                      <td style={{ padding: '14px 16px', color: 'var(--alert-crimson)', fontWeight: 600 }}>{row.riesgo_estructural}</td>
                      <td style={{ padding: '14px 16px', color: 'var(--accent-blue)', fontWeight: 600 }}>{row.factor_mayor_aporte ? `${row.factor_mayor_aporte.nombre}: ${Number(row.factor_mayor_aporte.aporte).toFixed(2)}` : 'Sin factor disponible'} · {row.evidencia_real} reales · {row.evidencia_simulada} SIMULADO</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : <p>Sin datos estratégicos disponibles.</p>}
      </div>

      {/* =====================================================================
          PESTAÑA 3: CENTRO DE INFORMACIÓN Y FUENTES (DIAGRAMA + GESTOR ESTILO DRIVE)
         ===================================================================== */}
      <div style={{ display: activeTab === 'repositorio' ? 'flex' : 'none', flex: 1, flexDirection: 'column', overflow: 'hidden', padding: '18px 24px', gap: '16px' }}>
          {/* BLOQUE SUPERIOR: DIAGRAMA DE FLUJO VISUAL EN VIVO (RELEVAMIENTO Y EXPANSIÓN DE FUENTES) */}
          <div
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              borderRadius: '10px',
              padding: '14px 18px',
              boxShadow: 'var(--shadow-sm)',
              flexShrink: 0
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Activity size={16} color="var(--accent-blue)" />
                <span style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary)' }}>
                  Circuito de información vial
                </span>
              </div>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: '#16a34a',
                  backgroundColor: 'rgba(22, 163, 74, 0.1)',
                  padding: '3px 10px',
                  borderRadius: '999px'
                }}
              >
                Fuentes y procesamiento
              </span>
            </div>

            {/* 4 Etapas del Diagrama de Flujo */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr auto 1fr auto 1fr', alignItems: 'center', gap: '10px' }}>
              {/* Etapa 1 */}
              <div
                style={{
                  backgroundColor: 'var(--bg-canvas)',
                  border: '1px solid var(--border-strong)',
                  borderRadius: '8px',
                  padding: '10px 12px'
                }}
              >
                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--accent-blue)', textTransform: 'uppercase', marginBottom: '3px' }}>
                  1. Fuentes Conectadas y Futuras
                </div>
                <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '2px' }}>
                  Fuentes de incidentes
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  {sourceFolders.slice(1).map(folder => folder.name).join(' · ') || 'Sin fuentes disponibles'}
                </div>
              </div>

              <ArrowRight size={18} color="var(--accent-blue)" />

              {/* Etapa 2 */}
              <div
                style={{
                  backgroundColor: 'var(--bg-canvas)',
                  border: '1px solid var(--border-strong)',
                  borderRadius: '8px',
                  padding: '10px 12px'
                }}
              >
                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--accent-blue)', textTransform: 'uppercase', marginBottom: '3px' }}>
                  2. Lectura y Filtrado Inteligente
                </div>
                <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '2px' }}>
                  Detección de Sucesos Viales
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  Identifica choques, cortes de calzada, semáforos fuera de servicio, horarios y vehículos involucrados
                </div>
              </div>

              <ArrowRight size={18} color="var(--accent-blue)" />

              {/* Etapa 3 */}
              <div
                style={{
                  backgroundColor: 'var(--bg-canvas)',
                  border: '1px solid var(--border-strong)',
                  borderRadius: '8px',
                  padding: '10px 12px'
                }}
              >
                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--accent-blue)', textTransform: 'uppercase', marginBottom: '3px' }}>
                  3. Ubicación en Cuadrícula Vial
                </div>
                <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '2px' }}>
                  Georreferenciación en Posadas
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  Ubicación de los incidentes registrados
                </div>
              </div>

              <ArrowRight size={18} color="var(--accent-blue)" />

              {/* Etapa 4 */}
              <div
                style={{
                  backgroundColor: 'var(--bg-canvas)',
                  border: '1px solid var(--accent-blue-border)',
                  borderLeft: '3px solid var(--accent-blue)',
                  borderRadius: '8px',
                  padding: '10px 12px'
                }}
              >
                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--accent-blue)', textTransform: 'uppercase', marginBottom: '3px' }}>
                  4. Análisis de prioridades
                </div>
                <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '2px' }}>
                  Análisis y planificación
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  Presenta prioridades y su evidencia
                </div>
              </div>
            </div>
          </div>

          {/* PANEL DE CONTROL DE INGESTA ACTIVA (DEMO DAY & MONITORING) */}
          <div
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              borderRadius: '10px',
              padding: '14px 18px',
              boxShadow: 'var(--shadow-sm)',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
              flexShrink: 0
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <span style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: 'var(--accent-blue)', letterSpacing: '0.05em' }}>
                  Ingesta de Noticias Viales bajo Demanda
                </span>
                <p style={{ margin: '2px 0 0 0', fontSize: '11.5px', color: 'var(--text-secondary)' }}>
                  Escaneo automatizado de portales locales de Posadas e ingesta directa por URL con georreferenciación de hitos y deduplicación.
                </p>
              </div>

              <button
                onClick={handleScanMedia}
                disabled={ingestLoading}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  backgroundColor: 'var(--accent-blue)',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '7px 14px',
                  fontSize: '11.5px',
                  fontWeight: 700,
                  cursor: ingestLoading ? 'not-allowed' : 'pointer',
                  opacity: ingestLoading ? 0.7 : 1,
                  boxShadow: 'var(--shadow-sm)'
                }}
              >
                <Activity size={13} />
                <span>{ingestLoading ? 'Escaneando medios...' : 'Escanear Medios Locales Ahora'}</span>
              </button>
            </div>

            {/* Formulario de Ingesta por URL */}
            <form onSubmit={handleIngestUrl} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <input
                type="url"
                value={ingestUrl}
                onChange={e => setIngestUrl(e.target.value)}
                placeholder="Pegar URL de noticia vial (ej. https://misionesonline.net/... o https://www.primeraedicion.com.ar/...)"
                disabled={ingestLoading}
                style={{
                  flex: 1,
                  padding: '7px 10px',
                  fontSize: '12px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-strong)',
                  backgroundColor: 'var(--bg-canvas)',
                  color: 'var(--text-primary)'
                }}
              />
              <button
                type="submit"
                disabled={ingestLoading || !ingestUrl.trim()}
                style={{
                  backgroundColor: 'var(--bg-canvas)',
                  border: '1px solid var(--border-strong)',
                  color: 'var(--text-primary)',
                  borderRadius: '6px',
                  padding: '7px 14px',
                  fontSize: '11.5px',
                  fontWeight: 700,
                  cursor: (ingestLoading || !ingestUrl.trim()) ? 'not-allowed' : 'pointer',
                  opacity: (ingestLoading || !ingestUrl.trim()) ? 0.5 : 1
                }}
              >
                Ingestar por URL
              </button>
            </form>

            {/* Mensaje de Resultado de Ingesta */}
            {ingestMessage && (
              <div
                style={{
                  fontSize: '11.5px',
                  fontWeight: 600,
                  padding: '6px 12px',
                  borderRadius: '6px',
                  backgroundColor: ingestMessage.type === 'error' ? 'rgba(239, 68, 68, 0.1)' : ingestMessage.type === 'info' ? 'rgba(234, 179, 8, 0.1)' : 'rgba(34, 197, 94, 0.1)',
                  color: ingestMessage.type === 'error' ? '#ef4444' : ingestMessage.type === 'info' ? '#ca8a04' : '#16a34a',
                  border: `1px solid ${ingestMessage.type === 'error' ? 'rgba(239, 68, 68, 0.2)' : ingestMessage.type === 'info' ? 'rgba(234, 179, 8, 0.2)' : 'rgba(34, 197, 94, 0.2)'}`
                }}
              >
                {ingestMessage.text}
              </div>
            )}
          </div>

          {/* BLOQUE INFERIOR: EXPLORADOR DE INFORMACIÓN ESTILO GOOGLE DRIVE (3 PANELES) */}
          <div
            style={{
              flex: 1,
              display: 'flex',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              borderRadius: '10px',
              overflow: 'hidden',
              boxShadow: 'var(--shadow-sm)'
            }}
          >
            {/* COLUMNA 1: ÁRBOL DE CARPETAS Y FUENTES CONECTADAS */}
            <div
              style={{
                width: '265px',
                borderRight: '1px solid var(--border-color)',
                backgroundColor: 'var(--bg-canvas)',
                padding: '14px 12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
                overflowY: 'auto',
                flexShrink: 0
              }}
            >
              <div
                style={{
                  fontSize: '10.5px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  color: 'var(--text-muted)',
                  padding: '0 8px 6px 8px'
                }}
              >
                Unidades de Información y Fuentes
              </div>

              {sourceFolders.map(folder => {
                const isSelected = selectedFolder === folder.id
                const isSelectable = true
                return (
                  <div
                    key={folder.id}
                    onClick={() => isSelectable && setSelectedFolder(folder.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 10px',
                      borderRadius: '6px',
                      cursor: isSelectable ? 'pointer' : 'default',
                      backgroundColor: isSelected ? 'var(--accent-blue-soft)' : 'transparent',
                      border: isSelected ? '1px solid var(--accent-blue-border)' : '1px solid transparent',
                      opacity: isSelectable ? 1 : 0.85
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {isSelected ? (
                        <FolderOpen size={16} color="var(--accent-blue)" />
                      ) : (
                        <Folder size={16} color={isSelectable ? 'var(--accent-blue)' : 'var(--text-muted)'} />
                      )}
                      <div>
                        <div style={{ fontSize: '12px', fontWeight: isSelected ? 700 : 600, color: 'var(--text-primary)' }}>
                          {folder.name}
                        </div>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{folder.id === 'all' ? 'Incidentes' : 'Fuente'}</div>
                      </div>
                    </div>

                    <span
                      style={{
                        fontSize: '10px',
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: '4px',
                        backgroundColor: 'var(--bg-subtle)',
                        color: 'var(--text-secondary)'
                      }}
                    >
                      {folder.count}
                    </span>
                  </div>
                )
              })}
            </div>

            {/* COLUMNA 2: GRILLA / LISTA DE REGISTROS PROCESADOS (ESTILO DRIVE) */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              {/* Barra de herramientas del gestor documental */}
              <div
                style={{
                  padding: '10px 16px',
                  borderBottom: '1px solid var(--border-color)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '12px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, maxWidth: '420px' }}>
                  <Search size={15} color="var(--text-muted)" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    placeholder="Buscar por avenida, calle, vehículo o suceso..."
                    style={{
                      width: '100%',
                      padding: '6px 10px',
                      fontSize: '12px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-strong)',
                      backgroundColor: 'var(--bg-canvas)',
                      color: 'var(--text-primary)'
                    }}
                  />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                    Mostrando <strong>{filteredDriveDocs.length}</strong> fichas estructuradas
                  </span>

                  <div
                    style={{
                      display: 'flex',
                      border: '1px solid var(--border-strong)',
                      borderRadius: '6px',
                      overflow: 'hidden'
                    }}
                  >
                    <button
                      onClick={() => setDriveViewMode('grid')}
                      style={{
                        padding: '5px 8px',
                        backgroundColor: driveViewMode === 'grid' ? 'var(--accent-blue)' : 'var(--bg-surface)',
                        color: driveViewMode === 'grid' ? '#ffffff' : 'var(--text-secondary)',
                        border: 'none',
                        cursor: 'pointer'
                      }}
                      title="Vista de tarjetas"
                    >
                      <LayoutGrid size={14} />
                    </button>
                    <button
                      onClick={() => setDriveViewMode('list')}
                      style={{
                        padding: '5px 8px',
                        backgroundColor: driveViewMode === 'list' ? 'var(--accent-blue)' : 'var(--bg-surface)',
                        color: driveViewMode === 'list' ? '#ffffff' : 'var(--text-secondary)',
                        border: 'none',
                        cursor: 'pointer'
                      }}
                      title="Vista de lista"
                    >
                      <List size={14} />
                    </button>
                  </div>
                </div>
              </div>

              {/* Contenido del Gestor (Tarjetas o Lista) */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '14px 16px' }}>
                {!filteredDriveDocs.length && <p>Sin incidentes disponibles.</p>}
                {driveViewMode === 'grid' ? (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(245px, 1fr))', gap: '12px' }}>
                    {filteredDriveDocs.map(doc => {
                      const isSel = driveSelectedDoc?.id === doc.id
                      const isGrave = Number(doc.severidad) >= 2
                      return (
                        <div
                          key={doc.id}
                          onClick={() => setDriveSelectedDoc(doc)}
                          style={{
                            backgroundColor: isSel ? 'var(--accent-blue-soft)' : 'var(--bg-canvas)',
                            border: isSel ? '1.5px solid var(--accent-blue)' : '1px solid var(--border-color)',
                            borderRadius: '8px',
                            padding: '12px',
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                            display: 'flex',
                            flexDirection: 'column',
                            justifyContent: 'space-between',
                            gap: '8px'
                          }}
                        >
                          <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                <span
                                  style={{
                                    fontSize: '9.5px',
                                    fontWeight: 800,
                                    textTransform: 'uppercase',
                                    color: 'var(--accent-blue)'
                                  }}
                                >
                                  {SOURCE_LABELS[doc.fuente] || doc.fuente}<MarcaSimulado origen={doc.origen} />
                                </span>
                                {doc.id?.startsWith('inc-web-') && (
                                  <span style={{ background: '#059669', color: '#fff', fontSize: '8.5px', fontWeight: 800, padding: '1px 5px', borderRadius: '4px' }}>
                                    WEB VIVO
                                  </span>
                                )}
                              </div>
                              <span
                                style={{
                                  fontSize: '9.5px',
                                  fontWeight: 700,
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  backgroundColor: isGrave ? 'var(--alert-crimson)' : 'var(--accent-blue)',
                                  color: '#ffffff',
                                  textTransform: 'uppercase'
                                }}
                              >
                                {doc.tipo_incidente.replace('_', ' ')}
                              </span>
                            </div>

                            <div
                              style={{
                                fontSize: '12.5px',
                                fontWeight: 700,
                                color: 'var(--text-primary)',
                                lineHeight: 1.35,
                                marginBottom: '8px'
                              }}
                            >
                              {doc.titulo}
                            </div>

                            {/* Metadatos Temporales: Fecha de Incidente vs Extracción */}
                            <div
                              style={{
                                display: 'grid',
                                gridTemplateColumns: '1fr 1fr',
                                gap: '6px',
                                backgroundColor: 'var(--bg-subtle)',
                                padding: '6px 8px',
                                borderRadius: '4px',
                                fontSize: '10px',
                                marginBottom: '8px'
                              }}
                            >
                              <div>
                                <span style={{ fontSize: '8.5px', color: 'var(--text-muted)', display: 'block', textTransform: 'uppercase', fontWeight: 700 }}>
                                  Fecha Incidente
                                </span>
                                <strong style={{ color: 'var(--text-primary)', fontSize: '10.5px' }}>
                                  {(doc.fecha_evento || '').replace('T', ' ').slice(0, 16)} hs
                                </strong>
                              </div>
                              <div>
                                <span style={{ fontSize: '8.5px', color: 'var(--text-muted)', display: 'block', textTransform: 'uppercase', fontWeight: 700 }}>
                                  Fecha Ingesta
                                </span>
                                <strong style={{ color: 'var(--text-secondary)', fontSize: '10.5px' }}>
                                  {(doc.fecha_publicacion || '').replace('T', ' ').slice(0, 16)} hs
                                </strong>
                              </div>
                            </div>
                          </div>

                          <div
                            style={{
                              borderTop: '1px solid var(--border-color)',
                              paddingTop: '6px',
                              fontSize: '11px',
                              color: 'var(--text-secondary)',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center'
                            }}
                          >
                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '175px', fontWeight: 600 }}>
                              {formatUbicacionVial(doc, ' × ')}
                            </span>
                            <span
                              style={{
                                fontSize: '9.5px',
                                fontWeight: 700,
                                padding: '1px 6px',
                                borderRadius: '4px',
                                backgroundColor: doc.tipo_ubicacion === 'indeterminado' ? '#fef3c7' : '#ecfdf5',
                                color: doc.tipo_ubicacion === 'indeterminado' ? '#b45309' : '#047857'
                              }}
                            >
                              {doc.tipo_ubicacion === 'indeterminado' ? 'Georref. Dudosa' : `Georref: ${Math.round((doc.confianza || 0.9) * 100)}%`}
                            </span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                    <thead>
                      <tr style={{ backgroundColor: 'var(--bg-subtle)', color: 'var(--text-muted)', fontSize: '10.5px', textTransform: 'uppercase' }}>
                        <th style={{ padding: '9px 12px' }}>Medio / Fuente</th>
                        <th style={{ padding: '9px 12px' }}>Suceso Relevado</th>
                        <th style={{ padding: '9px 12px' }}>Ubicación Georreferenciada</th>
                        <th style={{ padding: '9px 12px' }}>Fecha Siniestro</th>
                        <th style={{ padding: '9px 12px' }}>Fecha Ingesta</th>
                        <th style={{ padding: '9px 12px' }}>Georref. / Confianza</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredDriveDocs.map(doc => {
                        const isSel = driveSelectedDoc?.id === doc.id
                        return (
                          <tr
                            key={doc.id}
                            onClick={() => setDriveSelectedDoc(doc)}
                            style={{
                              borderTop: '1px solid var(--border-color)',
                              backgroundColor: isSel ? 'var(--accent-blue-soft)' : 'transparent',
                              cursor: 'pointer'
                            }}
                          >
                            <td style={{ padding: '10px 12px', fontWeight: 700, color: 'var(--accent-blue)' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                {SOURCE_LABELS[doc.fuente] || doc.fuente}
                                <MarcaSimulado origen={doc.origen} />
                                {doc.id?.startsWith('inc-web-') && (
                                  <span style={{ background: '#059669', color: '#fff', fontSize: '8px', fontWeight: 800, padding: '1px 4px', borderRadius: '3px' }}>
                                    WEB
                                  </span>
                                )}
                              </div>
                            </td>
                            <td style={{ padding: '10px 12px', fontWeight: 600, color: 'var(--text-primary)' }}>{doc.titulo}</td>
                            <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>
                              {formatUbicacionVial(doc, ' y ')}
                            </td>
                            <td className="mono" style={{ padding: '10px 12px', fontSize: '11px' }}>
                              {(doc.fecha_evento || '').replace('T', ' ').slice(0, 16)} hs
                            </td>
                            <td className="mono" style={{ padding: '10px 12px', fontSize: '11px', color: 'var(--text-muted)' }}>
                              {(doc.fecha_publicacion || '').replace('T', ' ').slice(0, 16)} hs
                            </td>
                            <td style={{ padding: '10px 12px', color: doc.confianza >= 0.8 ? '#16a34a' : '#d97706', fontWeight: 700, fontSize: '10.5px' }}>
                              {doc.tipo_ubicacion === 'indeterminado' ? 'Dudoso (40%)' : `OK (${Math.round((doc.confianza || 0.9) * 100)}%)`}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* COLUMNA 3: PANEL DE DETALLE DEL ARCHIVO SELECCIONADO (ESTILO PREVIEW DE DRIVE) */}
            {driveSelectedDoc && (
              <div
                style={{
                  width: '340px',
                  borderLeft: '1px solid var(--border-color)',
                  backgroundColor: 'var(--bg-canvas)',
                  padding: '16px',
                  overflowY: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  flexShrink: 0
                }}
              >
                <div style={{ fontSize: '10.5px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                  Ficha de Información Estructurada
                </div>

                <div
                  style={{
                    backgroundColor: 'var(--bg-surface)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    padding: '12px'
                  }}
                >
                  <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-blue)', marginBottom: '4px' }}>
                    {SOURCE_LABELS[driveSelectedDoc.fuente] || driveSelectedDoc.fuente}<MarcaSimulado origen={driveSelectedDoc.origen} />
                  </div>
                  <div style={{ fontSize: '13.5px', fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1.35, marginBottom: '8px' }}>
                    {driveSelectedDoc.titulo}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>{driveSelectedDoc.resumen}</div>
                </div>

                <div
                  style={{
                    backgroundColor: 'var(--bg-surface)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    padding: '12px',
                    fontSize: '11.5px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px'
                  }}
                >
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                    <div>
                      <span style={{ color: 'var(--text-muted)', fontSize: '10px', display: 'block' }}>FECHA DEL HECHO</span>
                      <strong style={{ color: 'var(--text-primary)' }}>
                        {(driveSelectedDoc.fecha_evento || '').replace('T', ' ').slice(0, 16)} hs
                      </strong>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-muted)', fontSize: '10px', display: 'block' }}>FECHA DE INGESTA</span>
                      <strong style={{ color: 'var(--text-secondary)' }}>
                        {(driveSelectedDoc.fecha_publicacion || '').replace('T', ' ').slice(0, 16)} hs
                      </strong>
                    </div>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)', fontSize: '10px', display: 'block' }}>INTERSECCIÓN / HITO GEORREFERENCIADO</span>
                    <strong>
                      {driveSelectedDoc.ubicacion_texto && driveSelectedDoc.ubicacion_texto.length <= 80
                        ? driveSelectedDoc.ubicacion_texto
                        : formatUbicacionVial(driveSelectedDoc, ' y ')}
                    </strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)', fontSize: '10px', display: 'block' }}>ARTERIAS AFECTADAS</span>
                    <strong>
                      {formatUbicacionVial(driveSelectedDoc, ' y ')}
                    </strong>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                    <div>
                      <span style={{ color: 'var(--text-muted)', fontSize: '10px', display: 'block' }}>GRAVEDAD</span>
                      <strong>{SEVERITY_LABELS[driveSelectedDoc.severidad]}</strong>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-muted)', fontSize: '10px', display: 'block' }}>CALIDAD GEORREF.</span>
                      <strong style={{ color: driveSelectedDoc.confianza >= 0.8 ? '#16a34a' : '#d97706' }}>
                        {driveSelectedDoc.tipo_ubicacion === 'indeterminado' ? 'Dudosa (40%)' : `${Math.round((driveSelectedDoc.confianza || 0.9) * 100)}% (${driveSelectedDoc.tipo_ubicacion})`}
                      </strong>
                    </div>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)', fontSize: '10px', display: 'block' }}>VEHÍCULOS IDENTIFICADOS</span>
                    <strong style={{ textTransform: 'capitalize' }}>{driveSelectedDoc.vehiculos || 'Sin datos'}</strong>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: 'auto' }}>
                  <button
                    onClick={() => {
                      setSelectedIncident(driveSelectedDoc)
                      setActiveTab('tactico')
                    }}
                    style={{
                      width: '100%',
                      padding: '9px 12px',
                      backgroundColor: 'var(--accent-blue)',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '6px',
                      fontSize: '12px',
                      fontWeight: 700,
                      cursor: 'pointer'
                    }}
                  >
                    Ver este punto en el Mapa Operativo
                  </button>

                  <a
                    href={driveSelectedDoc.url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      backgroundColor: 'var(--bg-surface)',
                      color: 'var(--accent-blue)',
                      border: '1px solid var(--accent-blue-border)',
                      borderRadius: '6px',
                      fontSize: '12px',
                      fontWeight: 600,
                      textDecoration: 'none',
                      textAlign: 'center',
                      display: 'inline-flex',
                      justifyContent: 'center',
                      alignItems: 'center',
                      gap: '6px'
                    }}
                  >
                    <span>Abrir publicación original</span>
                    <ExternalLink size={12} />
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
  )
}
