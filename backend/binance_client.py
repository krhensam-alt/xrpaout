import os
import pandas as pd
import numpy as np
import datetime
from binance.client import Client
from config import config

class BinanceClient:
    def __init__(self):
        self.is_mock = config.MOCK_MODE
        self.access = config.BINANCE_ACCESS_KEY
        self.secret = config.BINANCE_SECRET_KEY
        self.symbol = "XRPUSDT"
        self.base_currency = "USDT"
        self.asset_currency = "XRP"
        
        if not self.is_mock and self.access and self.secret:
            try:
                self.client = Client(self.access, self.secret)
                # API 키 유효성 테스트 (계좌 정보 조회)
                self.client.get_account()
            except Exception as e:
                print(f"바이낸스 API 인증 실패 또는 오류, Mock 모드로 자동 전환합니다: {e}")
                self.is_mock = True
        else:
            self.is_mock = True
            
        # 가상 잔고 상태 (Mock 모드용) - 10만원 상당의 USDT/XRP
        self.mock_usdt = 75.0  # 약 10만원
        self.mock_xrp = 150.0
        self.mock_avg_buy_price = 0.5 # USDT 기준
        self.last_price = 0.5

    def get_ohlcv(self, interval="1h", count=100) -> pd.DataFrame:
        """캔들 데이터 조회 (Binance 형식: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d)"""
        # Upbit "minute60" -> Binance "1h" 매핑
        if interval == "minute60": interval = "1h"
        
        try:
            klines = self.client.get_klines(symbol=self.symbol, interval=interval, limit=count)
            df = pd.DataFrame(klines, columns=[
                'time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            df.set_index('time', inplace=True)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            self.last_price = float(df['close'].iloc[-1])
            return df[['open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            if not self.is_mock:
                print(f"바이낸스 캔들 조회 실패: {e}")
            
        # 가상 데이터 생성 (실패 시)
        now = datetime.datetime.now()
        dates = [now - datetime.timedelta(hours=i) for i in range(count - 1, -1, -1)]
        base_price = self.last_price
        closes = []
        for _ in range(count):
            change = base_price * np.random.uniform(-0.015, 0.015)
            base_price += change
            closes.append(base_price)
            
        df = pd.DataFrame({
            'open': [c * 0.999 for c in closes],
            'high': [c * 1.008 for c in closes],
            'low': [c * 0.992 for c in closes],
            'close': closes,
            'volume': np.random.uniform(100000, 5000000, size=count)
        }, index=dates)
        self.last_price = float(closes[-1])
        return df

    def get_current_price(self) -> float:
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            self.last_price = float(ticker['price'])
            return self.last_price
        except Exception:
            pass
        self.last_price += self.last_price * np.random.uniform(-0.002, 0.002)
        return self.last_price

    def get_balances(self) -> dict:
        """계좌 잔고 조회 (Binance는 USDT 기준)"""
        current_price = self.get_current_price()
        
        if not self.is_mock:
            try:
                account = self.client.get_account()
                usdt = 0.0
                xrp = 0.0
                for balance in account['balances']:
                    if balance['asset'] == 'USDT':
                        usdt = float(balance['free'])
                    elif balance['asset'] == 'XRP':
                        xrp = float(balance['free'])
                
                # 평단가 조회 (바이낸스는 별도 로직 필요, 여기선 0으로 일단 처리)
                avg_buy_price = 0.0 
                
                return {
                    "krw": usdt * 1350, # 표시용 KRW 환산 (1350원 가정)
                    "usdt": usdt,
                    "xrp": xrp,
                    "total_val": (usdt + (xrp * current_price)) * 1350,
                    "avg_buy_price": avg_buy_price,
                    "is_mock": False
                }
            except Exception as e:
                print(f"바이낸스 잔고 조회 오류: {e}")
                
        return {
            "krw": self.mock_usdt * 1350,
            "usdt": self.mock_usdt,
            "xrp": self.mock_xrp,
            "total_val": (self.mock_usdt + (self.mock_xrp * current_price)) * 1350,
            "avg_buy_price": self.mock_avg_buy_price,
            "is_mock": True
        }

    def execute_order(self, decision: str, percentage: float) -> dict:
        """주문 실행"""
        price = self.get_current_price()
        balances = self.get_balances()
        
        if decision == "BUY":
            target_usdt = balances["usdt"] * (percentage / 100.0)
            if target_usdt < 10: # 바이낸스 최소 주문 금액 약 10 USDT
                return {"success": False, "reason": "최소 매수 금액(10 USDT) 미달"}
                
            amount_to_buy = target_usdt / price
            if not self.is_mock:
                try:
                    res = self.client.order_market_buy(symbol=self.symbol, quoteOrderQty=round(target_usdt, 2))
                    return {"success": True, "result": res, "price": price, "amount": amount_to_buy, "total_krw": target_usdt * 1350}
                except Exception as e:
                    return {"success": False, "reason": str(e)}
            else:
                self.mock_usdt -= target_usdt
                self.mock_xrp += amount_to_buy
                return {"success": True, "result": "MOCK_BUY_SUCCESS", "price": price, "amount": amount_to_buy, "total_krw": target_usdt * 1350}
                
        elif decision == "SELL":
            # 매도 전 혹시 있을지 모를 예약 주문(OCO 등) 먼저 취소
            self.cancel_all_orders()
            
            target_xrp = balances["xrp"] * (percentage / 100.0)
            target_usdt = target_xrp * price
            if target_usdt < 10:
                return {"success": False, "reason": "최소 매도 금액(10 USDT 상당) 미달"}
                
            if not self.is_mock:
                try:
                    res = self.client.order_market_sell(symbol=self.symbol, quantity=round(target_xrp, 2))
                    return {"success": True, "result": res, "price": price, "amount": target_xrp, "total_krw": target_usdt * 1350}
                except Exception as e:
                    return {"success": False, "reason": str(e)}
            else:
                self.mock_xrp -= target_xrp
                self.mock_usdt += target_usdt
                return {"success": True, "result": "MOCK_SELL_SUCCESS", "price": price, "amount": target_xrp, "total_krw": target_usdt * 1350}
                
        return {"success": False, "reason": "의사결정이 HOLD이거나 유효하지 않음"}

    def cancel_all_orders(self):
        """대기 중인 모든 주문 취소 (매도 전 실행)"""
        if self.is_mock: return True
        try:
            orders = self.client.get_open_orders(symbol=self.symbol)
            for order in orders:
                self.client.cancel_order(symbol=self.symbol, orderId=order['orderId'])
            return True
        except Exception as e:
            print(f"주문 취소 실패: {e}")
            return False

    def check_safety_orders(self, amount: float, buy_price: float) -> bool:
        """거래소에 안전 OCO 주문이 정상적으로 등록되어 있는지 확인"""
        if self.is_mock: return True
        try:
            orders = self.client.get_open_orders(symbol=self.symbol)
            if not orders:
                return False
            
            tp_price = round(buy_price * 1.050, 4)
            
            # 매도 주문('SELL') 중 익절 가격과 수량이 대략 일치하는 주문이 있는지 확인
            for order in orders:
                if order['side'] == 'SELL':
                    order_price = float(order['price'])
                    order_volume = float(order['origQty'])
                    
                    # 가격 오차 1% 이내, 수량 오차 2% 이내 허용
                    if abs(order_price - tp_price) / tp_price < 0.01 and abs(order_volume - amount) / amount < 0.02:
                        return True
            return False
        except Exception as e:
            print(f"바이낸스 안전 주문 상태 조회 실패: {e}")
            return True # API 오류 시 중복 등록 방지를 위해 일단 True 반환

    def place_safety_orders(self, amount: float, buy_price: float):
        """매수 직후 익절(+2.5%) 및 손절(-3.5%) OCO 주문 예약 (서버 다운 대비)"""
        if self.is_mock: return {"success": True, "info": "MOCK_OCO_PLACED"}
        
        tp_price = round(buy_price * 1.050, 4)
        sl_price = round(buy_price * 0.965, 4)
        stop_limit_price = round(sl_price * 0.995, 4) # 손절 실행가보다 약간 낮게 설정
        
        try:
            # OCO 주문: 익절(Limit) + 손절(Stop-Loss-Limit)
            res = self.client.create_oco_order(
                symbol=self.symbol,
                side='SELL',
                quantity=round(amount, 2),
                price=str(tp_price),
                stopPrice=str(sl_price),
                stopLimitPrice=str(stop_limit_price),
                stopLimitTimeInForce='GTC'
            )
            return {"success": True, "result": res}
        except Exception as e:
            print(f"바이낸스 안전 주문(OCO) 예약 실패: {e}")
            return {"success": False, "reason": str(e)}

binance_client = BinanceClient()
