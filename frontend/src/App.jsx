import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import AssetOverview from './components/AssetOverview';
import AiDecisionCard from './components/AiDecisionCard';
import CustomChart from './components/CustomChart';
import TradeHistory from './components/TradeHistory';
import { Play } from 'lucide-react';

// 같은 서버에서 서빙될 때 (로컬 및 동일 포트 접속용)
const BACKEND_URL = window.location.origin;
const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;

export default function App() {
  const [wsConnected, setWsConnected] = useState(false);
  const [backendStatus, setBackendStatus] = useState(false);
  const [statusData, setStatusData] = useState(null);
  const [balances, setBalances] = useState(null);
  const [reports, setReports] = useState([]);
  const [logs, setLogs] = useState([]);
  const [chartData, setChartData] = useState([]);
  const [toast, setToast] = useState(null);
  const [triggering, setTriggering] = useState(false);

  // 토스트 메시지 헬퍼
  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  };

  // REST API 초기 데이터 로드
  const fetchInitialData = async () => {
    try {
      const [resStatus, resAsset, resReports, resLogs, resChart] = await Promise.all([
        fetch(`${BACKEND_URL}/api/status`).catch(() => null),
        fetch(`${BACKEND_URL}/api/asset`).catch(() => null),
        fetch(`${BACKEND_URL}/api/reports`).catch(() => null),
        fetch(`${BACKEND_URL}/api/logs`).catch(() => null),
        fetch(`${BACKEND_URL}/api/chart`).catch(() => null)
      ]);

      if (resStatus?.ok) {
        const d = await resStatus.json();
        setStatusData(d);
        setBackendStatus(true);
      } else {
        setBackendStatus(false);
      }

      if (resAsset?.ok) setBalances(await resAsset.json());
      if (resReports?.ok) setReports(await resReports.json());
      if (resLogs?.ok) setLogs(await resLogs.json());
      if (resChart?.ok) setChartData(await resChart.json());
    } catch (e) {
      console.error("초기 데이터 로드 에러:", e);
      setBackendStatus(false);
    }
  };

  // 웹소켓 연결 관리
  useEffect(() => {
    fetchInitialData();
    
    let ws;
    let reconnectTimer;

    const connectWs = () => {
      ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        setWsConnected(true);
        console.log("웹소켓 연결 성공");
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          const { type, data } = msg;

          if (type === 'connected') {
            if (data.balances) setBalances(data.balances);
            // 상태 업데이트 반영
          } else if (type === 'ticker') {
            if (data.balances) setBalances(data.balances);
            // 현재가 갱신 등
          } else if (type === 'balance_update') {
            setBalances(data);
          } else if (type === 'new_report') {
            setReports(prev => [data, ...prev].slice(0, 20));
            showToast(`[AI 리포트 갱신] ${data.decision} (${Math.round(data.confidence * 100)}% 확신)`);
          } else if (type === 'new_trade') {
            setLogs(prev => [data, ...prev].slice(0, 50));
            showToast(`[주문 체결 성공] ${data.decision} | 총액 ${Math.round(data.total_krw).toLocaleString()}원`);
            // 잔고도 즉시 다시 호출
            fetch(`${BACKEND_URL}/api/asset`).then(r => r.json()).then(setBalances).catch(()=>{});
          }
        } catch (err) {
          console.error("WS 메시지 파싱 오류:", err);
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        // 3초 후 재연결 시도
        reconnectTimer = setTimeout(connectWs, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connectWs();

    // 15초마다 주기적으로 백엔드 상태 및 데이터 폴링 보완 (WS 불안정 대비)
    const pollingInterval = setInterval(fetchInitialData, 15000);

    return () => {
      clearTimeout(reconnectTimer);
      clearInterval(pollingInterval);
      if (ws) ws.close();
    };
  }, []);

  // 수동 매매 사이클 즉시 기동 트리거
  const handleTriggerCycle = async () => {
    if (triggering) return;
    setTriggering(true);
    showToast("수동으로 AI 트레이딩 사이클을 요청합니다...");
    try {
      const res = await fetch(`${BACKEND_URL}/api/trigger`, { method: 'POST' });
      if (res.ok) {
        showToast("AI 트레이딩 분석 사이클이 백그라운드에서 즉시 기동되었습니다.");
        // 데이터 갱신 가속
        setTimeout(fetchInitialData, 2000);
      } else {
        showToast("서버 요청에 실패했습니다. 백엔드가 기동 중인지 확인하세요.");
      }
    } catch (e) {
      showToast("백엔드 서버에 접속할 수 없습니다.");
    } finally {
      setTriggering(false);
    }
  };

  const isMockMode = statusData?.is_mock_mode ?? true;
  const currentPrice = statusData?.current_price ?? 730;

  return (
    <div className="app-container">
      {/* Live Notification Toast */}
      {toast && (
        <div className="live-toast">
          {toast}
        </div>
      )}

      {/* 1. 상단 네비게이션바 */}
      <Header 
        wsConnected={wsConnected} 
        backendStatus={backendStatus} 
        isMock={isMockMode} 
      />

      {/* 2. 자산 요약 및 실시간 수익률 */}
      <AssetOverview 
        balances={balances} 
        currentPrice={currentPrice} 
      />

      {/* 3. 최신 AI 판단 리포트 카드 */}
      <AiDecisionCard 
        report={reports[0]} 
      />

      {/* 4. 실시간 커스텀 시세 추이 차트 */}
      <CustomChart 
        data={chartData} 
      />

      {/* 5. 매매 및 로그 타임라인 */}
      <TradeHistory 
        logs={logs} 
      />

      {/* 6. 즉시 시연을 위한 수동 사이클 구동 버튼 */}
      <div className="demo-trigger-wrapper">
        <button 
          className="glass-button trigger-btn" 
          onClick={handleTriggerCycle}
          disabled={triggering}
        >
          <Play size={16} fill="currentColor" />
          {triggering ? "AI 분석 엔진 가동 중..." : "AI 트레이딩 사이클 즉시 실행"}
        </button>
        <span style={{ fontSize: '0.6rem', color: isMockMode ? 'hsl(var(--text-subtle))' : 'hsl(var(--color-sell))', display: 'block', marginTop: '6px' }}>
          {isMockMode
            ? "* 60분마다 자동 동작하며, 이 버튼은 시뮬레이션 사이클을 즉시 1회 실행합니다."
            : "⚠️ 실전 모드: 클릭 시 실제 계좌에서 AI 판단에 따른 매매가 즉시 집행될 수 있습니다."}
        </span>
      </div>
    </div>
  );
}
