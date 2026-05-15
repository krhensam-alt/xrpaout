import React from 'react';
import { Brain, Sparkles, Percent, Gauge } from 'lucide-react';

export default function AiDecisionCard({ report }) {
  if (!report) {
    return (
      <section className="glass-panel" style={{ padding: '20px 16px', textAlign: 'center', color: 'hsl(var(--text-muted))' }}>
        <Brain className="animate-pulse" size={32} style={{ margin: '0 auto 10px', opacity: 0.5 }} />
        <p style={{ fontSize: '0.85rem' }}>AI 리포트를 불러오는 중이거나 아직 분석 데이터가 없습니다.</p>
      </section>
    );
  }

  const { decision, confidence, percentage, reason, indicators, timestamp } = report;
  
  // 뱃지 클래스 매핑
  const badgeClass = decision === 'BUY' ? 'badge-buy' : decision === 'SELL' ? 'badge-sell' : 'badge-hold';
  
  // 지표 파싱 (DB에서 온 문자열일 수 있음)
  let parsedIndicators = indicators;
  if (typeof indicators === 'string') {
    try { parsedIndicators = JSON.parse(indicators); } catch(e) { parsedIndicators = {}; }
  }

  const rsi = parsedIndicators?.rsi_14;
  const macdHist = parsedIndicators?.macd?.histogram;

  return (
    <section className="glass-panel" style={{ padding: '20px 16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div className="flex-between">
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Brain size={16} color="hsl(260, 100%, 75%)" />
          <h2 style={{ fontSize: '0.95rem', fontWeight: 700 }}>AI 퀀트 브레인 분석</h2>
        </div>
        <span style={{ fontSize: '0.65rem', color: 'hsl(var(--text-subtle))' }}>
          {timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''}
        </span>
      </div>

      {/* Decision Showcase Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr 1fr', gap: '12px', alignItems: 'center', background: 'hsla(222, 50%, 5%, 0.4)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
        <div>
          <span style={{ fontSize: '0.65rem', color: 'hsl(var(--text-subtle))', display: 'block', marginBottom: '4px' }}>최종 포지션</span>
          <span className={`badge ${badgeClass}`} style={{ fontSize: '1rem', padding: '6px 14px' }}>
            {decision}
          </span>
        </div>

        <div style={{ textAlign: 'center', borderLeft: '1px solid var(--border-glass)', borderRight: '1px solid var(--border-glass)' }}>
          <span style={{ fontSize: '0.65rem', color: 'hsl(var(--text-subtle))', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '2px', marginBottom: '2px' }}>
            <Gauge size={10} /> 확신도
          </span>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: confidence > 0.75 ? 'hsl(150, 80%, 40%)' : 'hsl(var(--text-main))' }}>
            {Math.round((confidence || 0) * 100)}%
          </div>
        </div>

        <div style={{ textAlign: 'center' }}>
          <span style={{ fontSize: '0.65rem', color: 'hsl(var(--text-subtle))', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '2px', marginBottom: '2px' }}>
            <Percent size={10} /> 가동 비중
          </span>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: percentage > 0 ? 'hsl(200, 100%, 60%)' : 'hsl(var(--text-muted))' }}>
            {percentage}%
          </div>
        </div>
      </div>

      {/* Rationale Logic Block */}
      <div>
        <span style={{ fontSize: '0.65rem', color: 'hsl(var(--text-muted))', display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '6px' }}>
          <Sparkles size={11} color="hsl(60, 100%, 60%)" /> AI 분석 사유 및 전략 판단 근거
        </span>
        <p style={{ 
          fontSize: '0.85rem', 
          lineHeight: 1.5, 
          color: 'hsl(var(--text-main))', 
          background: 'hsla(0,0%,0%,0.25)', 
          padding: '12px', 
          borderRadius: 'var(--radius-sm)',
          borderLeft: `3px solid ${decision === 'BUY' ? 'hsl(150, 80%, 40%)' : decision === 'SELL' ? 'hsl(350, 80%, 60%)' : 'hsl(200, 95%, 55%)'}`
        }}>
          {reason || '사유가 제공되지 않았습니다.'}
        </p>
      </div>

      {/* Rationale Subtext summary of Indicators */}
      {(rsi !== undefined || macdHist !== undefined) && (
        <div className="flex-between" style={{ fontSize: '0.65rem', color: 'hsl(var(--text-subtle))', borderTop: '1px dashed var(--border-glass)', paddingTop: '8px' }}>
          <span>참조 지표 팩터:</span>
          <div style={{ display: 'flex', gap: '10px' }}>
            {rsi !== undefined && <span>RSI: <strong style={{ color: rsi < 30 ? 'hsl(150, 80%, 40%)' : rsi > 70 ? 'hsl(350, 80%, 60%)' : 'inherit' }}>{rsi.toFixed(1)}</strong></span>}
            {macdHist !== undefined && <span>MACD Hist: <strong style={{ color: macdHist > 0 ? 'hsl(150, 80%, 40%)' : 'hsl(350, 80%, 60%)' }}>{macdHist.toFixed(2)}</strong></span>}
          </div>
        </div>
      )}
    </section>
  );
}
