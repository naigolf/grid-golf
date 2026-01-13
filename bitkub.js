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
  return res.data[config.SYMBOL].last;
}

export async function placeOrder(type, amount, rate) {
  const payload = {
    sym: config.SYMBOL,
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

export async function getOpenOrders() {
  const payload = { sym: config.SYMBOL, ts: Date.now() };
  payload.sig = sign(payload);

  const res = await axios.post(
    `${BASE}/api/market/my-open-orders`,
    payload,
    { headers: { "X-BTK-APIKEY": config.BITKUB_API_KEY } }
  );

  return res.data.result || [];
}

export async function cancelOrder(id) {
  const payload = { sym: config.SYMBOL, id, ts: Date.now() };
  payload.sig = sign(payload);

  return axios.post(
    `${BASE}/api/market/cancel-order`,
    payload,
    { headers: { "X-BTK-APIKEY": config.BITKUB_API_KEY } }
  );
}
