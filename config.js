export default {
  SYMBOL_TICKER: "THB_DOGE",   // สำหรับ ticker
  SYMBOL_TRADE: "DOGE_THB",   // สำหรับส่งคำสั่งเทรด (ยังใช้แบบเดิม)

  TRADE_THB: 200,

  BUY_DROP_PERCENT: 1.0,
  SELL_RISE_PERCENT: 1.2,

  MAX_ORDER_MINUTES: 30,

  BITKUB_API_KEY: process.env.BITKUB_API_KEY,
  BITKUB_API_SECRET: process.env.BITKUB_API_SECRET,

  TELEGRAM_TOKEN: process.env.TELEGRAM_TOKEN,
  TELEGRAM_CHAT_ID: process.env.TELEGRAM_CHAT_ID
};
