import React from 'react';
import { Activity, Wifi, WifiOff, Cpu, Database } from 'lucide-react';

export default function Header({ wsConnected, backendStatus, isMock }) {
  return (
    <header className="glass-panel" style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div className="flex-between">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ 
            background: 'linear-gradient(135deg, #00f2fe 0%, #4facfe 100%)', 
            borderRadius: '10px', 
            padding: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 15px rgba(0, 242, 254, 0.4)'
          }}>
            <Activity size={20} color="#000" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.1rem', fontWeight: 700, letterSpacing: '-0.5px' }}>XRP AI Trader</h1>
            <span style={{ fontSize: '0.65rem', color: 'hsl(var(--text-muted))', letterSpacing: '0.5px' }}>
              GEMMA QUANT ENGINE
            </span>
          </div>
        </div>

        {/* Live Indicator Badges */}
        <div style={{ display: 'flex', gap: '6px' }}>
          <span className="badge" style={{ 
            background: wsConnected ? 'hsla(150, 80%, 40%, 0.15)' : 'hsla(350, 80%, 50%, 0.15)',
            color: wsConnected ? 'hsl(150, 80%, 40%)' : 'hsl(350, 80%, 50%)',
            border: `1px solid hsla(${wsConnected ? '150, 80%, 40%' : '350, 80%, 50%'}, 0.3)`
          }}>
            {wsConnected ? <Wifi size={10} /> : <WifiOff size={10} />}
            {wsConnected ? 'LIVE' : 'WS OFF'}
          </span>
        </div>
      </div>

      {/* Secondary Subsystem Status bar */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        borderTop: '1px solid var(--border-glass)', 
        paddingTop: '6px',
        fontSize: '0.7rem',
        color: 'hsl(var(--text-subtle))'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Database size={11} color={backendStatus ? 'hsl(150, 80%, 40%)' : 'hsl(var(--text-subtle))'} />
          <span>API: {backendStatus ? 'OK' : 'ERR'}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Cpu size={11} color="hsl(200, 100%, 50%)" />
          <span>MODE: <strong style={{ color: isMock ? 'hsl(30, 100%, 60%)' : 'hsl(150, 80%, 40%)' }}>
            {isMock ? 'MOCK/SIM' : 'REAL API'}
          </strong></span>
        </div>
      </div>
    </header>
  );
}
