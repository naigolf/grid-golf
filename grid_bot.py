def place_order(self, side, amount_thb, price):
        """วางคำสั่งซื้อ/ขาย (แก้ไข Symbol และ Amount Logic)"""
        
        # 1. แปลง Symbol ให้เป็น format ที่ API v3 ชอบ (เช่น btc_thb)
        # ปกติ Bitkub ใช้ THB_BTC แต่ v3 place-bid ชอบ btc_thb
        trade_sym = self.symbol.lower().replace('thb_', '').replace('_thb', '') + '_thb'
        if trade_sym.startswith('thb_'): # กันเหนียวกรณี symbol เดิมแปลกๆ
            trade_sym = 'btc_thb'
            
        # 2. คำนวณ Amount (amt) เป็น "จำนวนเหรียญ" (Crypto Quantity) เสมอ
        # สำหรับ Limit Order: amt คือจำนวนเหรียญที่จะ ซื้อ หรือ ขาย
        crypto_amt = amount_thb / price
        
        # จัดการทศนิยม (BTC ใช้ 8 ตำแหน่ง)
        amt_str = f"{crypto_amt:.8f}"
        
        # 3. จัดการ Price
        price_str = f"{price:.2f}"

        # เลือก Endpoint
        if side.lower() == 'buy':
            endpoint = '/api/v3/market/place-bid'
        else:
            endpoint = '/api/v3/market/place-ask'

        # สร้าง Payload
        # หมายเหตุ: ส่งเป็น String หรือ Float ก็ได้ แต่ Python dict จะจัดการ type ให้
        # เราแปลงกลับเป็น float เพื่อตัด trailing zero อัตโนมัติในขั้นตอน json.dumps ของ requests
        payload = {
            'sym': trade_sym, 
            'amt': float(amt_str), # ส่งเป็นจำนวนเหรียญ (BTC)
            'rat': float(price_str),
            'typ': 'limit'
        }
        
        print(f"🚀 Placing {side.upper()} ({trade_sym}): amt={payload['amt']} BTC, price={payload['rat']} THB")
        
        response = self._make_request(endpoint, 'POST', payload)
        
        if response.get('error') == 0:
            msg = f"✅ {side.upper()} Success: {payload['amt']:.8f} BTC @ {payload['rat']:,.2f}"
            print(msg)
            self.telegram.send_message(msg)
            return response.get('result')
        else:
            err_code = response.get('error')
            # Err 11 = Invalid Symbol (มักเกิดถ้าใช้ THB_BTC)
            # Err 15 = Amount too low (ถ้าคำนวณเหรียญผิด)
            # Err 18 = Insufficient balance
            msg = f"❌ Order Failed (Err {err_code}): {side.upper()} {payload['amt']} @ {payload['rat']}"
            print(msg)
            print(f"Full Response: {response}")
            self.telegram.send_message(msg)
            return None
