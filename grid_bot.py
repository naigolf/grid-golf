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
            url = f'{self.base_url}/sendMessage'
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data)
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
        
        # Grid Trading Parameters - อ่านจาก environment variables
        self.symbol = os.environ.get('SYMBOL', 'THB_BTC')
        self.budget = float(os.environ.get('BUDGET', '1000'))
        self.grid_levels = int(os.environ.get('GRID_LEVELS', '5'))
        self.price_range = float(os.environ.get('PRICE_RANGE', '0.02'))
        self.min_order_size = float(os.environ.get('MIN_ORDER_SIZE', '10'))
        
        self.orders = []
        
    def get_server_time(self):
        """ดึง server time จาก Bitkub (milliseconds)"""
        try:
            response = requests.get(f'{self.base_url}/api/v3/servertime', timeout=10)
            return int(response.text)
        except:
            # ถ้าเรียก API ไม่ได้ ใช้เวลาปัจจุบัน
            return int(time.time() * 1000)
    
    def _get_signature(self, method, path, body=''):
        """สร้าง signature สำหรับ Bitkub API v3"""
        timestamp = self.get_server_time()
        
        # Format: timestamp + method + path + body
        payload = f"{timestamp}{method}{path}{body}"
        
        # สร้าง signature
        signature = hmac.new(
            self.api_secret.encode(),
            msg=payload.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return timestamp, signature
    
    def _make_request(self, endpoint, method='GET', payload=None):
        """ส่ง request ไปยัง Bitkub API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == 'POST':
                # สร้าง body JSON
                body = json.dumps(payload or {}, separators=(',', ':'))
                
                # สร้าง signature
                timestamp, signature = self._get_signature(method, endpoint, body)
                
                headers = {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'X-BTK-APIKEY': self.api_key,
                    'X-BTK-SIGN': signature,
                    'X-BTK-TIMESTAMP': str(timestamp)
                }
                
                print(f"Request URL: {url}")
                print(f"Timestamp: {timestamp}")
                print(f"Method: {method}")
                print(f"Path: {endpoint}")
                print(f"Body: {body}")
                print(f"Signature: {signature}")
                
                response = requests.post(url, data=body, headers=headers, timeout=30)
                print(f"Response Status: {response.status_code}")
                print(f"Response Body: {response.text}")
                return response.json()
            else:
                # GET request
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
        except requests.exceptions.Timeout:
            print(f"❌ Request timeout: {url}")
            return {'error': 'timeout'}
        except Exception as e:
            print(f"❌ Request error: {str(e)}")
            return {'error': str(e)}
    
    def get_ticker(self):
        """ดึงราคาปัจจุบัน"""
        try:
            response = self._make_request('/api/market/ticker')
            print(f"Ticker API Response: {json.dumps(response, indent=2)}")
            
            if self.symbol in response:
                return float(response[self.symbol]['last'])
            else:
                error_msg = f"❌ Symbol {self.symbol} not found in ticker response"
                print(error_msg)
                self.telegram.send_message(error_msg)
        except Exception as e:
            error_msg = f"❌ Ticker API Error: {str(e)}"
            print(error_msg)
            self.telegram.send_message(error_msg)
        return None
    
    def get_balance(self):
        """ตรวจสอบยอดเงิน"""
        response = self._make_request('/api/v3/market/balances', 'POST', {})
        
        # Debug: แสดง response เต็ม
        print(f"Balance API Response: {json.dumps(response, indent=2)}")
        
        if response.get('error') == 0:
            result = response.get('result', {})
            thb_balance = float(result.get('THB', {}).get('available', 0))
            crypto_symbol = self.symbol.split('_')[1]
            crypto_balance = float(result.get(crypto_symbol, {}).get('available', 0))
            return thb_balance, crypto_balance
        else:
            error_code = response.get('error')
            error_msg = f"❌ API Error Code: {error_code}\nResponse: {json.dumps(response, indent=2)}"
            print(error_msg)
            self.telegram.send_message(f"<b>API Error</b>\n<pre>{error_msg}</pre>")
        return 0, 0
    
    def place_order(self, side, amount_thb, price):
        """วางคำสั่งซื้อ/ขาย
        
        Args:
            side: 'buy' or 'sell'
            amount_thb: จำนวนเงิน THB ที่ต้องการใช้
            price: ราคาที่ต้องการซื้อ/ขาย (THB)
        """
        # คำนวณจำนวนเหรียญจาก THB
        amount_crypto = amount_thb / price
        
        # ปัดให้เหมาะสมกับ BTC (8 ทศนิยม)
        amount_crypto = round(amount_crypto, 8)
        
        payload = {
            'sym': self.symbol,
            'amt': amount_crypto,  # จำนวนเหรียญ (BTC)
            'rat': price,          # ราคาต่อหน่วย (THB)
            'typ': 'limit',
            'side': side
        }
        
        response = self._make_request('/api/v3/market/place-bid', 'POST', payload)
        
        if response.get('error') == 0:
            msg = f"✅ {side.upper()} {amount_crypto:.8f} {self.symbol.split('_')[1]} @ {price:,.2f} THB (≈{amount_thb:.2f} THB)"
            print(msg)
            self.telegram.send_message(f"<b>Order Placed</b>\n{msg}")
            return response.get('result')
        else:
            error_code = response.get('error')
            error_msg = f"❌ Order failed (Error {error_code}): {amount_crypto:.8f} {self.symbol.split('_')[1]} @ {price:,.2f} THB"
            print(error_msg)
            self.telegram.send_message(f"<b>⚠️ Order Failed</b>\n{error_msg}")
            return None
    
    def calculate_grid_levels(self, current_price):
        """คำนวณราคาของแต่ละ grid level"""
        upper_price = current_price * (1 + self.price_range)
        lower_price = current_price * (1 - self.price_range)
        
        price_step = (upper_price - lower_price) / (self.grid_levels - 1)
        
        grid_prices = []
        for i in range(self.grid_levels):
            price = lower_price + (i * price_step)
            grid_prices.append(round(price, 2))
        
        return grid_prices
    
    def setup_grid(self):
        """ตั้งค่า Grid Trading"""
        setup_msg = f"""
🤖 <b>Bitkub Grid Trading Bot Started</b>

📊 <b>Configuration:</b>
• Symbol: {self.symbol}
• Budget: {self.budget:,.2f} THB
• Grid Levels: {self.grid_levels}
• Price Range: ±{self.price_range*100}%
"""
        print(setup_msg)
        self.telegram.send_message(setup_msg)
        
        # ตรวจสอบยอดเงิน
        thb_balance, crypto_balance = self.get_balance()
        balance_msg = f"💵 <b>Balance:</b>\n• THB: {thb_balance:,.2f}\n• {self.symbol.split('_')[1]}: {crypto_balance:.8f}"
        print(balance_msg)
        self.telegram.send_message(balance_msg)
        
        if thb_balance < self.budget:
            error_msg = f"⚠️ <b>Insufficient Balance!</b>\nNeed: {self.budget:,.2f} THB\nAvailable: {thb_balance:,.2f} THB"
            print(error_msg)
            self.telegram.send_message(error_msg)
            return
        
        # ดึงราคาปัจจุบัน
        current_price = self.get_ticker()
        if not current_price:
            error_msg = "❌ Failed to get current price"
            print(error_msg)
            self.telegram.send_message(error_msg)
            return
        
        price_msg = f"💱 <b>Current Price:</b> {current_price:,.2f} THB"
        print(price_msg)
        
        # คำนวณ grid levels
        grid_prices = self.calculate_grid_levels(current_price)
        grid_msg = f"📊 <b>Grid Prices:</b>\n{', '.join([f'{p:,.2f}' for p in grid_prices])}"
        print(grid_msg)
        
        # คำนวณจำนวนเงินต่อออเดอร์
        order_amount = self.budget / (self.grid_levels - 1)
        
        if order_amount < self.min_order_size:
            error_msg = f"⚠️ Order size too small!\nMinimum: {self.min_order_size} THB\nCalculated: {order_amount:.2f} THB"
            print(error_msg)
            self.telegram.send_message(error_msg)
            return
        
        # วางคำสั่งซื้อที่ราคาต่ำกว่าราคาปัจจุบัน
        buy_orders = []
        print("\n🛒 Placing BUY orders...")
        for price in grid_prices:
            if price < current_price:
                result = self.place_order('buy', order_amount, price)
                if result:
                    buy_orders.append(price)
                    self.orders.append({
                        'side': 'buy',
                        'price': price,
                        'amount': order_amount,
                        'order_id': result.get('id'),
                        'timestamp': datetime.now().isoformat()
                    })
                time.sleep(0.5)
        
        summary_msg = f"""
✅ <b>Grid Setup Complete!</b>

📝 <b>Summary:</b>
• Total Orders: {len(buy_orders)}
• Buy Orders: {len(buy_orders)}
• Amount per Order: {order_amount:.2f} THB
• Total Invested: {len(buy_orders) * order_amount:.2f} THB

📊 <b>Buy Levels:</b>
{chr(10).join([f'• {p:,.2f} THB' for p in buy_orders])}
"""
        print(summary_msg)
        self.telegram.send_message(summary_msg)
        
        # บันทึกสถานะ
        self.save_state()
    
    def check_and_rebalance(self):
        """ตรวจสอบและปรับ grid ใหม่"""
        check_msg = "🔄 <b>Checking Grid Status...</b>"
        print(check_msg)
        
        current_price = self.get_ticker()
        if not current_price:
            return
        
        # ดึงคำสั่งที่กำลังทำงาน
        response = self._make_request('/api/v3/market/my-open-orders', 'POST', {})
        
        if response.get('error') == 0:
            open_orders = response.get('result', [])
            
            # กรองเฉพาะ symbol ที่เรากำลังเทรด
            my_orders = [o for o in open_orders if o.get('sym') == self.symbol]
            
            status_msg = f"""
📊 <b>Grid Status Update</b>

💱 Current Price: {current_price:,.2f} THB
📝 Open Orders: {len(my_orders)}
"""
            
            # แสดงรายละเอียดคำสั่งที่เปิดอยู่
            if my_orders:
                status_msg += "\n<b>Active Orders:</b>\n"
                for order in my_orders[:5]:  # แสดงแค่ 5 คำสั่งแรก
                    side = order.get('side', 'unknown')
                    rate = float(order.get('rate', 0))
                    amount = float(order.get('amount', 0))
                    status_msg += f"• {side.upper()}: {amount:.2f} THB @ {rate:,.2f}\n"
                
                if len(my_orders) > 5:
                    status_msg += f"...and {len(my_orders) - 5} more orders\n"
            
            print(status_msg)
            self.telegram.send_message(status_msg)
            
            # ตรวจสอบคำสั่งที่เสร็จสมบูรณ์
            self.check_filled_orders()
    
    def check_filled_orders(self):
        """ตรวจสอบคำสั่งที่ถูก fill และวางคำสั่งขายใหม่"""
        # ดึงประวัติการเทรด
        response = self._make_request('/api/v3/market/my-order-history', 'POST', {
            'sym': self.symbol,
            'lmt': 20
        })
        
        if response.get('error') == 0:
            history = response.get('result', [])
            
            # หาคำสั่งซื้อที่เพิ่ง fill ในรอบล่าสุด
            recent_fills = []
            for order in history:
                if order.get('side') == 'buy':
                    # ตรวจสอบว่า fill หรือยัง
                    filled = float(order.get('filled', 0))
                    amount = float(order.get('amount', 0))
                    if filled > 0 and filled == amount:
                        recent_fills.append(order)
            
            if recent_fills:
                fill_msg = f"✅ <b>Orders Filled!</b>\n\n{len(recent_fills)} buy order(s) completed"
                print(fill_msg)
                self.telegram.send_message(fill_msg)
    
    def save_state(self):
        """บันทึกสถานะ bot"""
        state = {
            'timestamp': datetime.now().isoformat(),
            'orders': self.orders,
            'symbol': self.symbol,
            'budget': self.budget,
            'grid_levels': self.grid_levels,
            'price_range': self.price_range
        }
        
        with open('bot_state.json', 'w') as f:
            json.dump(state, f, indent=2)
        
        print("💾 State saved")
    
    def load_state(self):
        """โหลดสถานะ bot"""
        try:
            with open('bot_state.json', 'r') as f:
                state = json.load(f)
                self.orders = state.get('orders', [])
                print("📂 State loaded")
                return True
        except FileNotFoundError:
            print("📂 No previous state found")
            return False

def main():
    bot = BitkubGridBot()
    
    start_msg = f"""
🚀 <b>Bot Starting...</b>

⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    bot.telegram.send_message(start_msg)
    
    # โหลดสถานะเดิม (ถ้ามี)
    has_state = bot.load_state()
    
    # ตั้งค่า grid ครั้งแรก
    if not has_state or len(bot.orders) == 0:
        bot.setup_grid()
    else:
        # ตรวจสอบและปรับ grid
        bot.check_and_rebalance()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        error_msg = f"❌ <b>Bot Error!</b>\n\n{str(e)}"
        print(error_msg)
        notifier = TelegramNotifier()
        notifier.send_message(error_msg)
