export default {
  // ✅ Bitkub format (สำคัญ)
  SYMBOL_TICKER: "THB_DOGE", // สำหรับดึงราคา
  SYMBOL_TRADE: "DOGE_THB", // สำหรับส่งคำสั่งซื้อขาย

  // 💰 เงินต่อไม้
  TRADE_THB: 200,

  // 📊 Grid %
  BUY_DROP_PERCENT: 1.0,
  SELL_RISE_PERCENT: 1.2,

  // ⏱️ ยกเลิกออเดอร์ที่ค้างเกิน (นาที)
  MAX_ORDER_MINUTES: 30,

  // 🔐 Secrets
  BITKUB_API_KEY: process.env.BITKUB_API_KEY,
  BITKUB_API_SECRET: process.env.BITKUB_API_SECRET,

  TELEGRAM_TOKEN: process.env.TELEGRAM_TOKEN,
  TELEGRAM_CHAT_ID: process.env.TELEGRAM_CHAT_ID
};
