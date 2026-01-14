import os
import time
import hmac
import hashlib
import json
import requests
from datetime import datetime

class TelegramNotifier:
    def __init__(self):
        self.token = os.environ.get('TELEGRAM_TOKEN')
        self.chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        self.base_url = f'https://api.telegram.org/bot{self.token}'
    
    def send_message(self, message):
        try:
            if not self.token or not self.chat_id: return
            url = f'{self.base_url}/sendMessage'
            data = {'chat_id': self.chat_id, 'text': message, 'parse_mode': 'HTML'}
            requests.post(url, data=data, timeout=10)
        except Exception as e:
            print(f"Telegram Error: {e}")

class BitkubRSIBot:
    def __init__(self):
        self.api_key = os.environ.get('BITKUB_API_KEY')
        self.api_secret = os.environ.get('BITKUB_API_SECRET')
        self.base_url = 'https://api.bitkub.com'
        self.telegram = TelegramNotifier()
        
        # --- ตั้งค่ากลยุทธ์ ---
        self.symbol = os.environ.get('SYMBOL', 'THB_BTC')
        self.trade_amt = float(os.environ.get('TRADE_AMOUNT', '500'))
        self.rsi_buy = 30
        self.tp_percent = 1.5
        self.timeframe = '15' # 15 นาที
        # --------------------
        
        self.state = {'holding': False, 'buy_price': 0, 'qty': 0}

    def _get_server_time(self):
        try:
            return int(requests.get(f'{self.base_url}/api/v3/servertime').text)
        except:
            return int(time.time() * 1000)

    def _make_request(self, endpoint, method='GET', payload=None):
        try:
            if method == 'POST':
                ts = self._get_server_time()
                body = json.dumps(payload or {}, separators=(',', ':'))
                sig = hmac.new(self.api_secret.encode(), f"{ts}{method}{endpoint}{body}".encode(), hashlib.sha256).hexdigest()
                headers = {
                    'Accept': 'application/json', 'Content-Type': 'application/json',
                    'X-BTK-APIKEY': self.api_key, 'X-BTK-SIGN': sig, 'X-BTK-TIMESTAMP': str(ts)
                }
                return requests.post(f"{self.base_url}{endpoint}", data=body, headers=headers).json()
            else:
                return requests.get(f"{self.base_url}{endpoint}").json()
        except Exception as e:
            return {'error': str(e)}

    def get_rsi(self):
        """คำนวณ RSI จาก TradingView Endpoint ของ Bitkub"""
        try:
            # 1. เตรียม Symbol (Bitkub TradingView ใช้ BTC_THB ตัวใหญ่)
            sym = self.symbol.upper().replace('THB_', '').replace('_THB', '') + '_THB'
            if sym.startswith('THB_'): sym = 'BTC_THB'
            
            # 2. คำนวณช่วงเวลา (เอา 100 แท่งย้อนหลัง)
            now_ts = int(time.time())
            # 15 นาที * 60 วินาที * 100 แท่ง
            from_ts = now_ts - (int(self.timeframe) * 60 * 100)
            
            # 3. เรียก API /tradingview/history
            url = f"{self.base_url}/tradingview/history?symbol={sym}&resolution={self.timeframe}&from={from_ts}&to={now_ts}"
            
            response = requests.get(url, timeout=10)
            data = response.json()
            
            # ตรวจสอบข้อมูล (Format: {s: "ok", c: [close_prices], ...})
            if data.get('s') != 'ok' or not data.get('c'):
                print(f"⚠️ No chart data for {sym}: {data}")
                return None, None
            
            closes = [float(c) for c in data['c']]
            
            if len(closes) < 15:
                print("⚠️ Not enough data for RSI")
                return None, None
            
            # 4. คำนวณ RSI
            gains = []
            losses = []
            # ใช้ข้อมูล 14 แท่งล่าสุด
            recent_closes = closes[-15:] 
            
            for i in range(1, len(recent_closes)):
                change = recent_closes[i] - recent_closes[i-1]
                if change >= 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            avg_gain = sum(gains) / 14
            avg_loss = sum(losses) / 14
            
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            
            current_price = closes[-1]
            return rsi, current_price
            
        except Exception as e:
            print(f"❌ RSI Error: {e}")
            return None, None

    def place_order(self, side, val, price):
        # แปลง Symbol สำหรับ v3 API (ตัวเล็ก btc_thb)
        sym = self.symbol.lower().replace('thb_', '').replace('_thb', '') + '_thb'
        if sym.startswith('thb_'): sym = 'btc_thb'
        
        if side == 'buy':
            endpoint, amt = '/api/v3/market/place-bid', float(val)
        else:
            endpoint, amt = '/api/v3/market/place-ask', float(f"{val:.8f}") # คำนวณเหรียญมาแล้ว

        payload = {'sym': sym, 'amt': amt, 'rat': float(f"{price:.2f}"), 'typ': 'limit'}
        return self._make_request(endpoint, 'POST', payload)

    def load_state(self):
        try:
            with open('bot_state.json', 'r') as f: self.state = json.load(f)
        except: pass

    def save_state(self):
        with open('bot_state.json', 'w') as f: json.dump(self.state, f)

    def run(self):
        print("🤖 Bot Started (RSI Strategy)...")
        self.load_state()
        
        rsi, current_price = self.get_rsi()
        
        if rsi is None:
            print("❌ Failed to get RSI data. Retrying next round.")
            return
        
        print(f"📊 Market Status: RSI={rsi:.2f} | Price={current_price:,.2f}")
        
        if not self.state['holding']:
            if rsi <= self.rsi_buy:
                msg = f"📉 RSI ต่ำ ({rsi:.2f})! กำลังเข้าซื้อ..."
                print(msg)
                self.telegram.send_message(msg)
                
                # ซื้อที่ราคาตลาด (Market Price) เพื่อให้ได้ของชัวร์
                buy_price = current_price * 1.002 # เผื่อราคาขยับ 0.2%
                
                res = self.place_order('buy', self.trade_amt, buy_price)
                
                if res and res.get('error') == 0:
                    # คำนวณเหรียญที่ได้ (BTC)
                    qty = (self.trade_amt / buy_price) * 0.9975
                    self.state = {'holding': True, 'buy_price': buy_price, 'qty': qty}
                    self.save_state()
                    self.telegram.send_message(f"✅ ซื้อสำเร็จ! @ {buy_price:,.2f} THB")
            else:
                print(f"⏳ รอจังหวะ (RSI > {self.rsi_buy})")

        else:
            buy_price = self.state.get('buy_price', 0)
            target_price = buy_price * (1 + self.tp_percent/100)
            
            if buy_price == 0: profit_pct = 0
            else: profit_pct = ((current_price - buy_price) / buy_price) * 100
            
            print(f"💰 ถือของอยู่: ทุน {buy_price:,.2f} | ปัจจุบัน {current_price:,.2f} ({profit_pct:+.2f}%)")
            
            if current_price >= target_price:
                msg = f"🤑 กำไรแล้ว ({profit_pct:.2f}%)! ขายทำกำไร..."
                print(msg)
                self.telegram.send_message(msg)
                
                res = self.place_order('sell', self.state['qty'], current_price)
                
                if res and res.get('error') == 0:
                    self.state = {'holding': False, 'buy_price': 0, 'qty': 0}
                    self.save_state()
                    self.telegram.send_message(f"💵 ขายเรียบร้อย! รับกำไรเข้ากระเป๋า")
            
            elif profit_pct < -5.0:
                 self.telegram.send_message(f"⚠️ ขาดทุนเกิน 5% (เตือน)")

if __name__ == '__main__':
    bot = BitkubRSIBot()
    bot.run()
