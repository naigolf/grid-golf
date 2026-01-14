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
        
        # --- ตั้งค่ากลยุทธ์ตรงนี้ ---
        self.symbol = os.environ.get('SYMBOL', 'THB_BTC')
        self.trade_amt = float(os.environ.get('TRADE_AMOUNT', '500'))
        self.rsi_buy = 30
        self.tp_percent = 1.5
        self.timeframe = '15'
        # ------------------------
        
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
        """คำนวณ RSI 14 ย้อนหลัง แบบไม่ต้องใช้ Library"""
        try:
            # แปลง Symbol ให้ชัวร์ (Candle API บางทีชอบแบบมี THB_)
            sym_clean = self.symbol.lower().replace('thb_', '').replace('_thb', '') + '_thb'
            
            # ดึงข้อมูลแท่งเทียน
            url = f"{self.base_url}/api/market/candles?sym={sym_clean}&res={self.timeframe}&lmt=20"
            response = requests.get(url)
            
            # Check HTTP Status
            if response.status_code != 200:
                print(f"❌ API Error: {response.status_code}")
                return None, None

            data = response.json()
            
            # [FIXED] ถ้าไม่มีข้อมูล ให้ return None, None (2 ค่า) แทนที่จะเป็น None ค่าเดียว
            if not data or 'c' not in data: 
                print(f"⚠️ No candle data for {sym_clean}")
                return None, None
            
            closes = [float(c) for c in data['c']] # ราคาปิด
            
            if len(closes) < 15: 
                print("⚠️ Not enough data points for RSI")
                return None, None
            
            # คำนวณ RSI
            gains = []
            losses = []
            for i in range(1, 15):
                change = closes[i] - closes[i-1]
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
            
            return rsi, closes[-1] # คืนค่า RSI และราคาปัจจุบัน
        except Exception as e:
            print(f"❌ RSI Calc Error: {e}")
            return None, None # [FIXED] Return 2 values here too

    def place_order(self, side, val, price):
        sym = self.symbol.lower().replace('thb_', '').replace('_thb', '') + '_thb'
        if sym.startswith('thb_'): sym = 'btc_thb'
        
        if side == 'buy':
            endpoint, amt = '/api/v3/market/place-bid', float(val)
        else:
            endpoint, amt = '/api/v3/market/place-ask', float(f"{val:.8f}")

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
        
        # --- LOGIC การซื้อขาย ---
        
        # 1. ถ้ายังไม่มีของ (ถือเงินสด) -> รอซื้อเมื่อ RSI ต่ำ
        if not self.state['holding']:
            if rsi <= self.rsi_buy:
                msg = f"📉 RSI ต่ำ ({rsi:.2f})! กำลังเข้าซื้อ..."
                print(msg)
                self.telegram.send_message(msg)
                
                # ซื้อที่ราคาตลาด (หรือบวกนิดหน่อยให้แมทช์เลย)
                buy_price = current_price * 1.001 
                res = self.place_order('buy', self.trade_amt, buy_price)
                
                if res and res.get('error') == 0:
                    # คำนวณจำนวนเหรียญที่ได้ (หักค่าธรรมเนียม 0.25% เผื่อไว้)
                    qty = (self.trade_amt / buy_price) * 0.9975
                    self.state = {'holding': True, 'buy_price': buy_price, 'qty': qty}
                    self.save_state()
                    self.telegram.send_message(f"✅ ซื้อสำเร็จ! @ {buy_price:,.2f} เป้าขาย: {buy_price * (1 + self.tp_percent/100):,.2f}")
            else:
                print(f"⏳ รอจังหวะ (RSI > {self.rsi_buy})")

        # 2. ถ้ามีของแล้ว -> รอขายเมื่อกำไรถึงเป้า
        else:
            buy_price = self.state.get('buy_price', 0)
            target_price = buy_price * (1 + self.tp_percent/100)
            
            # ป้องกัน buy_price เป็น 0
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
            
            # (Option) ตัดขาดทุนถ้าลงหนักเกิน 5%
            elif profit_pct < -5.0:
                 self.telegram.send_message(f"⚠️ ขาดทุนเกิน 5% คัทลอสเพื่อรักษาทุน")

if __name__ == '__main__':
    bot = BitkubRSIBot()
    bot.run()
