import React, { useState } from 'react'

export default function AitaraAvatar({ state = 'idle', size = 54, showBadge = true }) {
  // state: 'idle' | 'thinking' | 'speaking'
  const isThinking = state === 'thinking'
  const [imgError, setImgError] = useState(false)

  return (
    <div
      style={{
        position: 'relative',
        width: size,
        height: size,
        flexShrink: 0,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}
    >
      {/* Halo animado en modo thinking o idle */}
      <div
        style={{
          position: 'absolute',
          inset: -4,
          borderRadius: '50%',
          border: isThinking ? '2.5px solid var(--accent-blue)' : '1.5px solid var(--accent-blue-border)',
          backgroundColor: isThinking ? 'var(--accent-blue-soft)' : 'transparent',
          animation: isThinking ? 'avatarGlow 1.2s infinite ease-in-out' : 'none',
          transition: 'all 0.3s ease'
        }}
      />

      {/* Imagen 3D Toy Avatar estilo Grokbot */}
      {!imgError ? (
        <img
          src="/aitara_bot_avatar.jpg"
          alt="Aitara Assistant Bot"
          onError={() => setImgError(true)}
          style={{
            width: size,
            height: size,
            borderRadius: '50%',
            objectFit: 'cover',
            border: '2px solid var(--bg-surface)',
            boxShadow: '0 2px 8px rgba(15, 23, 42, 0.15)',
            transform: isThinking ? 'scale(1.05)' : 'scale(1)',
            transition: 'transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)'
          }}
        />
      ) : (
        /* Fallback SVG vectorial si la imagen tardara en cargar */
        <svg
          viewBox="0 0 100 100"
          width={size}
          height={size}
          style={{
            filter: 'drop-shadow(0 2px 6px rgba(29, 78, 216, 0.3))'
          }}
        >
          <rect x="15" y="18" width="70" height="66" rx="26" fill="#1d4ed8" stroke="#1e3a8a" strokeWidth="2.5" />
          <ellipse cx="50" cy="25" rx="22" ry="4" fill="rgba(255, 255, 255, 0.3)" />
          <rect x="23" y="34" width="54" height="36" rx="16" fill="#0f172a" />
          <rect x="32" y="44" width="12" height="16" rx="6" fill="#38bdf8" />
          <rect x="56" y="44" width="12" height="16" rx="6" fill="#38bdf8" />
          <circle cx="35" cy="48" r="2.5" fill="#ffffff" />
          <circle cx="59" cy="48" r="2.5" fill="#ffffff" />
        </svg>
      )}

      {/* Badge de estado en la esquina inferior */}
      {showBadge && (
        <span
          style={{
            position: 'absolute',
            bottom: -2,
            right: -2,
            width: 14,
            height: 14,
            borderRadius: '50%',
            backgroundColor: isThinking ? '#be123c' : '#16a34a',
            border: '2.5px solid var(--bg-surface)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.2)'
          }}
          title={isThinking ? 'AITARA pensando...' : 'AITARA en línea'}
        />
      )}

      <style>{`
        @keyframes avatarGlow {
          0% { transform: scale(0.96); opacity: 0.6; }
          50% { transform: scale(1.08); opacity: 1; }
          100% { transform: scale(0.96); opacity: 0.6; }
        }
        @keyframes dotPulse {
          0%, 100% { opacity: 0.3; transform: scale(0.8); }
          50% { opacity: 1; transform: scale(1.2); }
        }
      `}</style>
    </div>
  )
}
