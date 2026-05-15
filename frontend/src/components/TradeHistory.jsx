import React from 'react';
import { History, ArrowUpRight, ArrowDownRight, CircleDot } from 'lucide-react';

export default function TradeHistory({ logs }) {
  return (
    <section className="glass-panel" style={{ padding: '20px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div className="flex-between">
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <History size={16} color="hsl(var(--text-muted))" />
          <h2 style={{ fontSize: '0.95rem', fontWeight: 700 }}>실시간 매매 체결 히스토리</h2>
        </div>
        <span style={{ fontSize: '0.65rem', color: 'hsl(var(--text-subtle))' }}>
          최근 {logs?.length || 0}건
        </span>
      </div>

      {(!logs || logs.length === 0) ? (
        <div style={{ padding: '20px', textAlign: 'center', color: 'hsl(var(--text-subtle))', fontSize: '0.8rem' }}>
          기록된 매매/로그 내역이 없습니다.
        </div>
      ) : (
        <div style={{ 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '10px', 
          maxHeight: '220px', 
          overflowY: 'auto',
          paddingRight: '4px'
        }}>
          {logs.map((log, index) => {
            const isBuy = log.decision === 'BUY';
            const isSell = log.decision === 'SELL';
            
            // 아이콘 및 뱃지 색상 선택
            const Icon = isBuy ? ArrowUpRight : isSell ? ArrowDownRight : CircleDot;
            const badgeClass = isBuy ? 'badge-buy' : isSell ? 'badge-sell' : 'badge-hold';

            // 시간 포맷
            const timeStr = log.timestamp 
              ? new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              : '';

            return (
              <div 
                key={log.id || index} 
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'space-between',
                  background: 'hsla(0,0%,0%,0.15)',
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-sm)',
                  borderLeft: `2px solid ${isBuy ? 'hsl(150,80%,40%)' : isSell ? 'hsl(350,80%,60%)' : 'hsl(var(--text-subtle))'}`,
                  fontSize: '0.8rem',
                  transition: 'background 0.2s'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ 
                    padding: '4px', 
                    borderRadius: 'var(--radius-full)', 
                    background: isBuy ? 'hsla(150,80%,40%,0.1)' : isSell ? 'hsla(350,80%,60%,0.1)' : 'hsla(0,0%,100%,0.05)',
                    color: isBuy ? 'hsl(150,80%,40%)' : isSell ? 'hsl(350,80%,60%)' : 'hsl(var(--text-muted))'
                  }}>
                    <Icon size={12} />
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span className={`badge ${badgeClass}`} style={{ fontSize: '0.6rem', padding: '2px 6px' }}>
                        {log.decision}
                      </span>
                      <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                        {log.price?.toLocaleString()} <small style={{ fontSize: '0.6rem', color: 'hsl(var(--text-subtle))' }}>KRW</small>
                      </span>
                    </div>
                    {log.reason && (
                      <div style={{ fontSize: '0.7rem', color: 'hsl(var(--text-muted))', marginTop: '2px', maxWidth: '200px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {log.reason}
                      </div>
                    )}
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontWeight: 600, color: 'hsl(var(--text-main))' }}>
                    {log.amount > 0 ? `${log.amount.toFixed(2)} XRP` : '-'}
                  </div>
                  <div style={{ fontSize: '0.65rem', color: 'hsl(var(--text-subtle))' }}>
                    {timeStr}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
