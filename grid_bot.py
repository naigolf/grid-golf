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

class BitkubStatelessBot:
    def __init__(self):
        self.api_key = os.environ.get('BITKUB_API_KEY')
        self.api_secret = os.environ.get('BITKUB_API_SECRET')
        self.base_url = 'https://api.bitkub.com'
        self.telegram = TelegramNotifier()
        
        # --- ตั้งค่ากลยุทธ์ ---
        self.symbol = os.environ.get('SYMBOL', 'THB_BTC')
        self.trade_amt = float(os.environ.get('TRADE_AMOUNT', '330'))
        self.rsi_buy = 35     # ซื้อถ้าร่วงแรง (RSI ต่ำกว่านี้)
        self.tp_percent = 1.2 # ขายถ้ากำไรถึงเป้านี้ (%)
        self.timeframe = '15'
        # --------------------

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

    def get_wallet(self):
        """เช็คยอดเงินคงเหลือจริง"""
        try:
            res = self._make_request('/api/v3/market/balances', 'POST', {})
            if res.get('error') != 0: return 0, 0
            
            result = res['result']
            thb = float(result.get('THB', {}).get('available', 0))
            
            # หา Symbol ของเหรียญ (ตัด THB ออก)
            coin_sym = self.symbol.replace('THB_', '').replace('_THB', '').upper()
            btc = float(result.get(coin_sym, {}).get('available', 0))
            
            return thb, btc
        except:
            return 0, 0

    def get_last_buy_price(self):
        """ค้นหาประวัติการซื้อล่าสุด เพื่อหาทุน"""
        try:
            sym = self.symbol.lower().replace('thb_', '').replace('_thb', '') + '_thb'
            if sym.startswith('thb_'): sym = 'btc_thb'
            
            payload = {'sym': sym, 'lmt': 10} # ดูย้อนหลัง 10 รายการ
            res = self._make_request('/api/v3/market/my-order-history', 'POST', payload)
            
            if res.get('error') == 0:
                orders = res['result']
                for order in orders:
                    # หาออเดอร์ "Buy" ที่สำเร็จ (Filled) ล่าสุด
                    if order.get('side') == 'buy':
                        return float(order.get('rate', 0))
            return 0
        except:
            return 0

    def get_rsi(self):
        """ดึง RSI จาก TradingView API"""
        try:
            sym = self.symbol.upper().replace('THB_', '').replace('_THB', '') + '_THB'
            if sym.startswith('THB_'): sym = 'BTC_THB'
            
            now_ts = int(time.time())
            from_ts = now_ts - (int(self.timeframe) * 60 * 100)
            
            url = f"{self.base_url}/tradingview/history?symbol={sym}&resolution={self.timeframe}&from={from_ts}&to={now_ts}"
            data = requests.get(url, timeout=10).json()
            
            if data.get('s') != 'ok' or not data.get('c'): return None, None
            
            closes = [float(c) for c in data['c']]
            if len(closes) < 15: return None, None
            
            # RSI Calculation
            recent_closes = closes[-15:]
            gains, losses = [], []
            for i in range(1, len(recent_closes)):
                change = recent_closes[i] - recent_closes[i-1]
                if change >= 0: gains.append(change); losses.append(0)
                else: gains.append(0); losses.append(abs(change))
            
            avg_gain = sum(gains) / 14
            avg_loss = sum(losses) / 14
            
            if avg_loss == 0: rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            
            return rsi, closes[-1]
        except:
            return None, None

    def place_order(self, side, val, price):
        sym = self.symbol.lower().replace('thb_', '').replace('_thb', '') + '_thb'
        if sym.startswith('thb_'): sym = 'btc_thb'
        
        if side == 'buy':
            endpoint, amt = '/api/v3/market/place-bid', float(val)
        else:
            endpoint, amt = '/api/v3/market/place-ask', float(f"{val:.8f}")

        payload = {'sym': sym, 'amt': amt, 'rat': float(f"{price:.2f}"), 'typ': 'limit'}
        return self._make_request(endpoint, 'POST', payload)

    def run(self):
        print("🤖 Bot Checking (Stateless Mode)...")
        
        # 1. เช็คข้อมูลตลาด
        rsi, current_price = self.get_rsi()
        if rsi is None:
            print("❌ Error fetching chart.")
            return

        # 2. เช็คกระเป๋าตังค์จริง
        thb_balance, btc_balance = self.get_wallet()
        print(f"💰 Wallet: {thb_balance:,.2f} THB | {btc_balance:.8f} BTC")
        print(f"📊 Market: RSI={rsi:.2f} | Price={current_price:,.2f}")

        # ตรวจสอบว่า "มีของ" หรือไม่ (ถ้ามี BTC มากกว่าเศษสตางค์ ประมาณ 150 บาท)
        has_position = btc_balance > 0.00005 
        
        # --- LOGIC การตัดสินใจ ---
        
        if has_position:
            # === โหมดเตรียมขาย ===
            last_buy_price = self.get_last_buy_price()
            if last_buy_price == 0:
                print("⚠️ มีเหรียญแต่หาประวัติซื้อไม่เจอ ข้ามการขายอัตโนมัติ")
                return

            target_price = last_buy_price * (1 + self.tp_percent/100)
            profit_pct = ((current_price - last_buy_price) / last_buy_price) * 100
            
            print(f"💎 ถือของอยู่ (ทุน {last_buy_price:,.2f}) กำไร: {profit_pct:+.2f}%")
            print(f"🎯 เป้าขาย: {target_price:,.2f}")
            
            if current_price >= target_price:
                # แจ้งเตือนการขาย แบบละเอียด
                msg = (
                    f"🔴 <b>SELLING NOW!</b>\n\n"
                    f"💵 <b>Price:</b> {current_price:,.2f} THB\n"
                    f"📦 <b>Cost:</b> {last_buy_price:,.2f} THB\n"
                    f"📈 <b>Profit:</b> {profit_pct:+.2f}%"
                )
                print(msg)
                self.telegram.send_message(msg)
                
                # ขายหมดพอร์ต
                self.place_order('sell', btc_balance, current_price)
            else:
                print("⏳ ยังไม่ถึงเป้า ถือต่อ...")
                
        else:
            # === โหมดเตรียมซื้อ ===
            if thb_balance < self.trade_amt:
                print("⚠️ เงินบาทไม่พอซื้อ")
                return

            if rsi <= self.rsi_buy:
                # คำนวณเป้าขายล่วงหน้าเพื่อแจ้งเตือน
                buy_price = current_price * 1.002
                future_sell_price = buy_price * (1 + self.tp_percent/100)
                
                # แจ้งเตือนการซื้อ แบบละเอียด
                msg = (
                    f"🟢 <b>BUYING NOW!</b>\n\n"
                    f"📉 <b>RSI:</b> {rsi:.2f}\n"
                    f"💵 <b>Price:</b> {buy_price:,.2f} THB\n"
                    f"🎯 <b>Target:</b> +{self.tp_percent}%\n"
                    f"🔮 <b>Sell at:</b> {future_sell_price:,.2f} THB"
                )
                print(msg)
                self.telegram.send_message(msg)
                
                # เคาะขวา ซื้อเลย
                self.place_order('buy', self.trade_amt, buy_price)
            else:
                print(f"👀 เฝ้ารอ (RSI {rsi:.2f} > {self.rsi_buy})")

if __name__ == '__main__':
    bot = BitkubStatelessBot()
    bot.run()
                
