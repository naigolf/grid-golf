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
        """ส่งข้อความผ่าน Telegram"""
        try:
            if not self.token or not self.chat_id:
                print("Telegram token or chat_id not set.")
                return None
                
            url = f'{self.base_url}/sendMessage'
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=10)
            return response.json()
        except Exception as e:
            print(f"Failed to send Telegram message: {e}")
            return None

class BitkubGridBot:
    def __init__(self):
        self.api_key = os.environ.get('BITKUB_API_KEY')
        self.api_secret = os.environ.get('BITKUB_API_SECRET')
        self.base_url = 'https://api.bitkub.com'
        
        # Telegram Notifier
        self.telegram = TelegramNotifier()
        
        # Grid Trading Parameters
        self.symbol = os.environ.get('SYMBOL', 'THB_BTC')
        self.budget = float(os.environ.get('BUDGET', '1000'))
        self.grid_levels = int(os.environ.get('GRID_LEVELS', '5'))
        self.price_range = float(os.environ.get('PRICE_RANGE', '0.02'))
        self.min_order_size = float(os.environ.get('MIN_ORDER_SIZE', '10'))
        
        self.orders = []
        
    def get_server_time(self):
        """ดึง server time จาก Bitkub"""
        try:
            response = requests.get(f'{self.base_url}/api/v3/servertime', timeout=10)
            return int(response.text)
        except:
            return int(time.time() * 1000)
    
    def _get_signature(self, method, path, body=''):
        timestamp = self.get_server_time()
        payload = f"{timestamp}{method}{path}{body}"
        signature = hmac.new(
            self.api_secret.encode(),
            msg=payload.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        return timestamp, signature
    
    def _make_request(self, endpoint, method='GET', payload=None):
        url = f"{self.base_url}{endpoint}"
        try:
            if method == 'POST':
                body = json.dumps(payload or {}, separators=(',', ':'))
                timestamp, signature = self._get_signature(method, endpoint, body)
                
                headers = {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'X-BTK-APIKEY': self.api_key,
                    'X-BTK-SIGN': signature,
                    'X-BTK-TIMESTAMP': str(timestamp)
                }
                
                print(f"Request: {method} {endpoint}")
                # print(f"Body: {body}") # Uncomment for debug
                
                response = requests.post(url, data=body, headers=headers, timeout=30)
                
                # Handle non-JSON response
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {'error': 999, 'result': response.text}
            else:
                # GET Logic (Not heavily used in this bot)
                query_string = ''
                if payload:
                    query_string = '?' + '&'.join([f"{k}={v}" for k, v in payload.items()])
                timestamp, signature = self._get_signature(method, endpoint, query_string)
                headers = {
                    'Accept': 'application/json',
                    'X-BTK-APIKEY': self.api_key,
                    'X-BTK-SIGN': signature,
                    'X-BTK-TIMESTAMP': str(timestamp)
                }
                full_url = f"{url}{query_string}"
                response = requests.get(full_url, headers=headers, timeout=30)
                return response.json()
                
        except Exception as e:
            print(f"❌ Request error: {str(e)}")
            return {'error': str(e)}
    
    def get_ticker(self):
        try:
            response = requests.get(f'{self.base_url}/api/market/ticker')
            data = response.json()
            if self.symbol in data:
                return float(data[self.symbol]['last'])
        except Exception as e:
            print(f"Ticker Error: {e}")
        return None

    def get_balance(self):
        response = self._make_request('/api/v3/market/balances', 'POST', {})
        if response.get('error') == 0:
            result = response.get('result', {})
            thb = float(result.get('THB', {}).get('available', 0))
            crypto = float(result.get(self.symbol.split('_')[1], {}).get('available', 0))
            return thb, crypto
        return 0, 0

    def place_order(self, side, amount_thb, price):
        """วางคำสั่งซื้อ/ขาย (แก้ไขเรื่องทศนิยม)"""
        
        # 1. จัดการเรื่องราคา (Price) ให้เป็นทศนิยม 2 ตำแหน่งเสมอ
        price = float(f"{price:.2f}")

        # 2. คำนวณ Amount และเลือก Endpoint
        if side.lower() == 'buy':
            # ขาซื้อ: ใช้ Endpoint place-bid
            endpoint = '/api/v3/market/place-bid'
            
            # จำนวนเงิน (THB) ต้องเป็นทศนิยม 2 ตำแหน่ง
            amt = float(f"{amount_thb:.2f}")
            
            if amt < self.min_order_size:
                print(f"⚠️ Skip: Order size {amt} THB < Minimum {self.min_order_size}")
                return None
        else:
            # ขาขาย: ใช้ Endpoint place-ask
            endpoint = '/api/v3/market/place-ask'
            
            # จำนวนเหรียญ (Crypto) คำนวณจาก THB / Price
            # ต้องเป็นทศนิยม 8 ตำแหน่ง (สำหรับ BTC)
            crypto_amt = amount_thb / price
            amt = float(f"{crypto_amt:.8f}")
            
        payload = {
            'sym': self.symbol,
            'amt': amt,
            'rat': price,
            'typ': 'limit'
            # side ไม่ต้องใส่ใน body สำหรับ v3
        }
        
        # Debug: แสดงค่าที่ส่งไปจริงๆ
        print(f"🚀 Placing {side.upper()}: amt={amt}, price={price}")
        # print(f"DEBUG Payload: {json.dumps(payload)}") 
        
        response = self._make_request(endpoint, 'POST', payload)
        
        if response.get('error') == 0:
            msg = f"✅ {side.upper()} Success: {amt} @ {price:,.2f}"
            print(msg)
            self.telegram.send_message(msg)
            return response.get('result')
        else:
            err_code = response.get('error')
            # Error 11 = Amount too low / Invalid Amount
            # Error 18 = Insufficient balance
            msg = f"❌ Order Failed (Err {err_code}): {side.upper()} {amt} @ {price}"
            print(msg)
            print(f"Full Response: {response}")
            self.telegram.send_message(msg)
            return None

    def calculate_grid_levels(self, current_price):
        upper_price = current_price * (1 + self.price_range)
        lower_price = current_price * (1 - self.price_range)
        price_step = (upper_price - lower_price) / (self.grid_levels - 1)
        
        grid_prices = []
        for i in range(self.grid_levels):
            price = lower_price + (i * price_step)
            # ปัดเศษราคาตามความเหมาะสม (เช่น BTC ราคาหลักล้าน อาจไม่ต้องละเอียดมาก แต่ API รับทศนิยมได้)
            grid_prices.append(round(price, 2))
        return grid_prices

    def setup_grid(self):
        current_price = self.get_ticker()
        if not current_price:
            self.telegram.send_message("❌ Cannot fetch price. Aborting.")
            return

        thb_balance, _ = self.get_balance()
        print(f"Balance: {thb_balance:.2f} THB")
        
        if thb_balance < self.min_order_size:
            self.telegram.send_message("❌ Insufficient THB balance to start grid.")
            return

        # คำนวณราคา Grid
        grid_prices = self.calculate_grid_levels(current_price)
        
        # คำนวณ Budget ต่อไม้
        order_amount_thb = self.budget / self.grid_levels
        
        msg = f"🤖 Starting Grid\nPrice: {current_price:,.2f}\nOrders: {self.grid_levels}\nPer Order: {order_amount_thb:,.2f} THB"
        self.telegram.send_message(msg)

        # วาง Order ซื้อ (Buy Limit) ที่ราคาต่ำกว่าปัจจุบัน
        for price in grid_prices:
            if price < current_price:
                # ตรวจสอบ Budget ว่าพอมั้ย
                if thb_balance >= order_amount_thb:
                    res = self.place_order('buy', order_amount_thb, price)
                    if res:
                        self.orders.append({
                            'id': res.get('id'),
                            'side': 'buy',
                            'price': price,
                            'amount_thb': order_amount_thb,
                            'timestamp': datetime.now().isoformat()
                        })
                        thb_balance -= order_amount_thb # ตัดยอดคงเหลือใน memory
                        time.sleep(1) # Delay เพื่อป้องกัน Rate limit
        
        self.save_state()

    def check_and_rebalance(self):
        print("🔄 Checking Status...")
        # 1. เช็ค Open Orders
        response = self._make_request('/api/v3/market/my-open-orders', 'POST', {'sym': self.symbol})
        open_orders = []
        if response.get('error') == 0:
            open_orders = response.get('result', [])
        
        open_order_ids = [str(o['id']) for o in open_orders]
        
        # 2. เปรียบเทียบกับ Orders ที่เราบันทึกไว้
        # ถ้า Order ไม่อยู่ใน Open Orders แสดงว่ามัน Filled (สำเร็จ) หรือ Cancelled
        completed_orders = []
        active_orders = []
        
        for saved_order in self.orders:
            if str(saved_order['id']) not in open_order_ids:
                completed_orders.append(saved_order)
            else:
                active_orders.append(saved_order)
        
        self.orders = active_orders # อัปเดตรายการที่ยังค้างอยู่
        
        # 3. Logic Grid Trading: ถ้า Buy Filled -> ตั้ง Sell ที่ราคาสูงขึ้น 1 step
        # (นี่คือ Logic ง่ายๆ สำหรับ Grid)
        for order in completed_orders:
            if order['side'] == 'buy':
                # Order ซื้อสำเร็จ -> ต้องตั้งขาย (Take Profit)
                print(f"✅ Buy Order {order['id']} Filled! Placing Sell order.")
                self.telegram.send_message(f"✅ Buy Filled @ {order['price']:,.2f}. Placing Sell.")
                
                # คำนวณราคาขาย (เช่น บวกกำไรไป 1 grid step หรือ % คงที่)
                # ในที่นี้สมมติ +1.5%
                sell_price = order['price'] * 1.015 
                
                # ตั้งขาย
                res = self.place_order('sell', order['amount_thb'], sell_price)
                if res:
                    self.orders.append({
                        'id': res.get('id'),
                        'side': 'sell',
                        'price': sell_price,
                        'amount_thb': order['amount_thb'], # เก็บค่าอ้างอิงไว้
                        'timestamp': datetime.now().isoformat()
                    })
            
            elif order['side'] == 'sell':
                # Order ขายสำเร็จ -> รับกำไรแล้ว -> ตั้งซื้อกลับที่เดิม (Re-buy)
                print(f"💰 Sell Order {order['id']} Filled! Re-placing Buy order.")
                self.telegram.send_message(f"💰 Sell Filled @ {order['price']:,.2f}. Grid Profit! Re-buying lower.")
                
                buy_price = order['price'] / 1.015
                res = self.place_order('buy', order['amount_thb'], buy_price)
                if res:
                    self.orders.append({
                        'id': res.get('id'),
                        'side': 'buy',
                        'price': buy_price,
                        'amount_thb': order['amount_thb'],
                        'timestamp': datetime.now().isoformat()
                    })

        self.save_state()

    def save_state(self):
        state = {
            'orders': self.orders,
            'last_update': datetime.now().isoformat()
        }
        with open('bot_state.json', 'w') as f:
            json.dump(state, f, indent=2)

    def load_state(self):
        try:
            with open('bot_state.json', 'r') as f:
                state = json.load(f)
                self.orders = state.get('orders', [])
                print(f"📂 Loaded {len(self.orders)} tracked orders.")
                return True
        except:
            return False

def main():
    bot = BitkubGridBot()
    
    # โหลด state
    bot.load_state()
    
    # ถ้าไม่มี Order ค้างอยู่เลย ให้เริ่ม Setup ใหม่
    if not bot.orders:
        bot.setup_grid()
    else:
        bot.check_and_rebalance()

if __name__ == '__main__':
    main()
