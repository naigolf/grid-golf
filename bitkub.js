import crypto from "crypto";
import axios from "axios";
import config from "./config.js";

const BASE = "https://api.bitkub.com";

function sign(payload) {
  return crypto
    .createHmac("sha256", config.BITKUB_API_SECRET)
    .update(JSON.stringify(payload))
    .digest("hex");
}

// ----- PRICE (GET) -----
export async function getPrice() {
  const res = await axios.get(`${BASE}/api/market/ticker`);
  const t = res.data[config.SYMBOL_TICKER];
  if (!t) throw new Error("Ticker symbol not found");
  return Number(t.last);
}

// ----- PLACE ORDER (POST) -----
export async function placeOrder(side, amount, rate) {
  const payload = {
    sym: config.SYMBOL_TRADE,
    amt: Number(amount),
    rat: Number(rate),
    typ: "limit",
    side: side, // "buy" | "sell"
    ts: Date.now()
  };
  payload.sig = sign(payload);

  const res = await axios.post(
    `${BASE}/api/v3/market/place-order`,
    payload,
    {
      headers: {
        "X-BTK-APIKEY": config.BITKUB_API_KEY,
        "Content-Type": "application/json"
      }
    }
  );
  return res.data;
}

// ----- OPEN ORDERS -----
export async function getOpenOrders() {
  const payload = { sym: config.SYMBOL_TRADE, ts: Date.now() };
  payload.sig = sign(payload);

  const res = await axios.post(
    `${BASE}/api/v3/market/my-open-orders`,
    payload,
    {
      headers: {
        "X-BTK-APIKEY": config.BITKUB_API_KEY,
        "Content-Type": "application/json"
      }
    }
  );
  return res.data.result || [];
}

// ----- CANCEL -----
export async function cancelOrder(orderId) {
  const payload = { sym: config.SYMBOL_TRADE, id: orderId, ts: Date.now() };
  payload.sig = sign(payload);

  return axios.post(
    `${BASE}/api/v3/market/cancel-order`,
    payload,
    {
      headers: {
        "X-BTK-APIKEY": config.BITKUB_API_KEY,
        "Content-Type": "application/json"
      }
    }
  );
}
