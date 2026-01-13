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

export async function getPrice() {
  const res = await axios.get(`${BASE}/api/market/ticker`);
  if (!res.data[config.SYMBOL_TICKER]) {
    throw new Error("Symbol not found in ticker");
  }
  return res.data[config.SYMBOL_TICKER].last;
}

export async function placeOrder(side, amount, rate) {
  const payload = {
    sym: config.SYMBOL_TRADE,
    amt: amount,
    rat: rate,
    typ: "limit",
    side: side, // buy | sell
    ts: Date.now()
  };

  payload.sig = sign(payload);

  const res = await axios.post(
    `${BASE}/api/v3/market/place-order`,
    payload,
    {
      headers: {
        "X-BTK-APIKEY": config.BITKUB_API_KEY
      }
    }
  );

  return res.data;
}

export async function getOpenOrders() {
  const payload = {
    sym: config.SYMBOL_TRADE,
    ts: Date.now()
  };

  payload.sig = sign(payload);

  const res = await axios.post(
    `${BASE}/api/v3/market/my-open-orders`,
    payload,
    {
      headers: {
        "X-BTK-APIKEY": config.BITKUB_API_KEY
      }
    }
  );

  return res.data.result || [];
}

export async function cancelOrder(orderId) {
  const payload = {
    sym: config.SYMBOL_TRADE,
    id: orderId,
    ts: Date.now()
  };

  payload.sig = sign(payload);

  return axios.post(
    `${BASE}/api/v3/market/cancel-order`,
    payload,
    {
      headers: {
        "X-BTK-APIKEY": config.BITKUB_API_KEY
      }
    }
  );
}
