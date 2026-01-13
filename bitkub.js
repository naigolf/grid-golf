import axios from "axios";
import crypto from "crypto";
import config from "./config.js";

const BASE = "https://api.bitkub.com";

function sign(payload) {
  return crypto
    .createHmac("sha256", config.BITKUB_API_SECRET)
    .update(JSON.stringify(payload))
    .digest("hex");
}

// 📈 ดึงราคาปัจจุบัน
export async function getPrice() {
  const res = await axios.get(`${BASE}/api/market/ticker`);

  if (!res.data[config.SYMBOL_TICKER]) {
    throw new Error("❌ Symbol not found in ticker");
  }

  return res.data[config.SYMBOL_TICKER].last;
}

// 🟢 วางออเดอร์
export async function placeOrder(type, amount, rate) {
  const payload = {
    sym: config.SYMBOL_TRADE,
    amt: amount,
    rat: rate,
    typ: type,
    ts: Date.now()
  };

  payload.sig = sign(payload);

  const res = await axios.post(
    `${BASE}/api/market/place-${type}`,
    payload,
    { headers: { "X-BTK-APIKEY": config.BITKUB_API_KEY } }
  );

  return res.data;
}

// 📋 ดูออเดอร์ค้าง
export async function getOpenOrders() {
  const payload = {
    sym: config.SYMBOL_TRADE,
    ts: Date.now()
  };

  payload.sig = sign(payload);

  const res = await axios.post(
    `${BASE}/api/market/my-open-orders`,
    payload,
    { headers: { "X-BTK-APIKEY": config.BITKUB_API_KEY } }
  );

  return res.data.result || [];
}

// ❌ ยกเลิกออเดอร์
export async function cancelOrder(id) {
  const payload = {
    sym: config.SYMBOL_TRADE,
    id,
    ts: Date.now()
  };

  payload.sig = sign(payload);

  await axios.post(
    `${BASE}/api/market/cancel-order`,
    payload,
    { headers: { "X-BTK-APIKEY": config.BITKUB_API_KEY } }
  );
}
