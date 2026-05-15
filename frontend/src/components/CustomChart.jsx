import React, { useState } from 'react';
import { LineChart } from 'lucide-react';

export default function CustomChart({ data }) {
  const [hoverIndex, setHoverIndex] = useState(null);

  if (!data || data.length === 0) {
    return (
      <section className="glass-panel" style={{ padding: '20px 16px', textAlign: 'center', color: 'hsl(var(--text-muted))' }}>
        <p style={{ fontSize: '0.85rem' }}>차트 데이터를 불러오는 중입니다...</p>
      </section>
    );
  }

  // 가격의 최소/최대 계산
  const closes = data.map(d => d.close);
  const minClose = Math.min(...closes) * 0.998;
  const maxClose = Math.max(...closes) * 1.002;
  const range = maxClose - minClose || 1;

  // SVG 좌표 변환 (가로 400, 세로 140 기준)
  const svgWidth = 400;
  const svgHeight = 140;

  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * svgWidth;
    const y = svgHeight - ((d.close - minClose) / range) * svgHeight;
    return { x, y, ...d };
  });

  // SVG Line path 생성
  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');

  // SVG Area path (그라데이션 영역용)
  const areaPath = `${linePath} L ${svgWidth} ${svgHeight} L 0 ${svgHeight} Z`;

  const hoveredPoint = hoverIndex !== null ? points[hoverIndex] : points[points.length - 1];

  return (
    <section className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div className="flex-between">
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <LineChart size={16} color="hsl(200, 100%, 50%)" />
          <h2 style={{ fontSize: '0.95rem', fontWeight: 700 }}>XRP/KRW 실시간 추이</h2>
        </div>
        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'hsl(200, 100%, 80%)' }}>
          {hoveredPoint ? `${hoveredPoint.close.toLocaleString()} KRW` : ''}
        </span>
      </div>

      {/* SVG Rendering Container */}
      <div style={{ position: 'relative', width: '100%', height: '140px', background: 'hsla(0,0%,0%,0.2)', borderRadius: 'var(--radius-sm)' }}>
        <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} style={{ width: '100%', height: '100%', overflow: 'visible' }}>
          <defs>
            <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(200, 100%, 50%)" stopOpacity="0.4" />
              <stop offset="100%" stopColor="hsl(200, 100%, 50%)" stopOpacity="0.0" />
            </linearGradient>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Area Fill */}
          <path d={areaPath} fill="url(#chartGradient)" />

          {/* Sparkline */}
          <path d={linePath} fill="none" stroke="hsl(200, 100%, 50%)" strokeWidth="2.5" filter="url(#glow)" />

          {/* Interactive touch points */}
          {points.map((p, i) => (
            <circle
              key={i}
              cx={p.x}
              cy={p.y}
              r={hoverIndex === i ? 5 : 2}
              fill={hoverIndex === i ? '#fff' : 'hsl(200, 100%, 50%)'}
              style={{ cursor: 'pointer', transition: 'all 0.2s' }}
              onMouseEnter={() => setHoverIndex(i)}
              onMouseLeave={() => setHoverIndex(null)}
            />
          ))}

          {/* Hover indicator guideline */}
          {hoverIndex !== null && points[hoverIndex] && (
            <line
              x1={points[hoverIndex].x}
              y1="0"
              x2={points[hoverIndex].x}
              y2={svgHeight}
              stroke="hsla(210, 100%, 95%, 0.3)"
              strokeDasharray="3 3"
            />
          )}
        </svg>

        {/* Selected info float overlay */}
        {hoveredPoint && (
          <div style={{ 
            position: 'absolute', 
            bottom: '4px', 
            left: '8px', 
            fontSize: '0.6rem', 
            color: 'hsl(var(--text-subtle))',
            pointerEvents: 'none'
          }}>
            시간: {hoveredPoint.time} | 시가: {hoveredPoint.open} | 고가: {hoveredPoint.high}
          </div>
        )}
      </div>

      <div className="flex-between" style={{ fontSize: '0.65rem', color: 'hsl(var(--text-subtle))', padding: '0 4px' }}>
        <span>{points[0]?.time}</span>
        <span>최근 30개봉 (10m)</span>
        <span>{points[points.length - 1]?.time}</span>
      </div>
    </section>
  );
}
