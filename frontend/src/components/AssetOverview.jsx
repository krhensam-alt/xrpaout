import React from 'react';
import { Wallet, TrendingUp, TrendingDown, Coins } from 'lucide-react';

export default function AssetOverview({ balances, currentPrice }) {
  const krw = balances?.krw ?? 0;
  const xrp = balances?.xrp ?? 0;
  const totalVal = balances?.total_val ?? (krw + xrp * (currentPrice || 730));
  
  // 기준 원금 10만원 대비 실시간 수익률 계산
  const basePrincipal = 100000;
  const profitLoss = totalVal - basePrincipal;
  const roiPercentage = ((profitLoss) / basePrincipal) * 100;
  const isPositive = roiPercentage >= 0;

  // 자산 비중 바 계산 (XRP 비중)
  const xrpRatio = totalVal > 0 ? ((xrp * (currentPrice || 730)) / totalVal) * 100 : 0;

  return (
    <section className="glass-panel" style={{ padding: '20px 16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div className="flex-between" style={{ alignItems: 'flex-start' }}>
        <div>
          <span style={{ fontSize: '0.75rem', color: 'hsl(var(--text-muted))', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Wallet size={12} /> 총 보유 자산 (KRW 환산)
          </span>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, letterSpacing: '-0.5px', marginTop: '2px', textShadow: '0 0 20px hsla(210, 100%, 80%, 0.2)' }}>
            {Math.floor(totalVal).toLocaleString()} <span style={{ fontSize: '1rem', fontWeight: 400, color: 'hsl(var(--text-muted))' }}>KRW</span>
          </div>
        </div>

        {/* Real-time ROI pill */}
        <div style={{ 
          background: isPositive ? 'hsla(150, 80%, 40%, 0.15)' : 'hsla(350, 80%, 50%, 0.15)',
          padding: '6px 12px',
          borderRadius: 'var(--radius-full)',
          border: `1px solid hsla(${isPositive ? '150, 80%, 40%' : '350, 80%, 50%'}, 0.3)`,
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          color: isPositive ? 'hsl(150, 80%, 40%)' : 'hsl(350, 80%, 50%)',
          fontWeight: 700,
          fontSize: '0.85rem'
        }}>
          {isPositive ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
          <span>{roiPercentage > 0 ? '+' : ''}{roiPercentage.toFixed(2)}%</span>
        </div>
      </div>

      {/* Held Asset Specifics */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', background: 'hsla(0,0%,0%,0.2)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
        <div>
          <span style={{ fontSize: '0.65rem', color: 'hsl(var(--text-subtle))', display: 'block', marginBottom: '2px' }}>보유 현금</span>
          <div style={{ fontSize: '0.95rem', fontWeight: 600 }}>
            {Math.floor(krw).toLocaleString()} <span style={{ fontSize: '0.7rem', color: 'hsl(var(--text-muted))' }}>KRW</span>
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.65rem', color: 'hsl(var(--text-subtle))', display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '2px' }}>
            <Coins size={10} color="hsl(200, 100%, 50%)" /> 리플 수량
          </span>
          <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'hsl(200, 100%, 85%)' }}>
            {xrp.toFixed(4)} <span style={{ fontSize: '0.7rem', color: 'hsl(var(--text-muted))' }}>XRP</span>
          </div>
        </div>
      </div>

      {/* Custom visual ratio slider/bar */}
      <div>
        <div className="flex-between" style={{ fontSize: '0.65rem', color: 'hsl(var(--text-muted))', marginBottom: '4px' }}>
          <span>XRP 비중 ({xrpRatio.toFixed(1)}%)</span>
          <span>KRW 비중 ({(100 - xrpRatio).toFixed(1)}%)</span>
        </div>
        <div style={{ width: '100%', height: '6px', background: 'hsla(222, 30%, 20%, 0.8)', borderRadius: 'var(--radius-full)', overflow: 'hidden', display: 'flex' }}>
          <div style={{ 
            width: `${xrpRatio}%`, 
            background: 'linear-gradient(90deg, hsl(200, 100%, 40%), hsl(200, 100%, 60%))',
            transition: 'width 0.5s ease-out',
            boxShadow: '0 0 10px hsl(200, 100%, 50%)'
          }} />
        </div>
      </div>
    </section>
  );
}
