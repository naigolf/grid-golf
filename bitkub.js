import axios from "axios";
import crypto from "crypto";

const API = "https://api.bitkub.com";
const KEY = process.env.BITKUB_API_KEY;
const SECRET = process.env.BITKUB_API_SECRET;

function sign(str) {
  return crypto.createHmac("sha256", SECRET).update(str).digest("hex");
}

export async function getPrice(symbol) {
  const res = await axios.get(`${API}/api/market/ticker`);
  return res.data[symbol].last;
}

export async function getBalance() {
  const ts = Date.now();
  const payload = `ts=${ts}`;
  const sig = sign(payload);

  const res = await axios.post(
    `${API}/api/market/bal`,
    payload + `&sig=${sig}`,
    { headers: { "X-BTK-APIKEY": KEY } }
  );
  return res.data.result;
}

export async function placeOrder(type, symbol, amount, price) {
  const ts = Date.now();
  const payload = `sym=${symbol}&amt=${amount}&rat=${price}&typ=${type}&ts=${ts}`;
  const sig = sign(payload);

  const res = await axios.post(
    `${API}/api/market/place-bid`,
    payload + `&sig=${sig}`,
    { headers: { "X-BTK-APIKEY": KEY } }
  );
  return res.data;
}


export async function getOpenOrders(symbol) {
  const ts = Date.now();
  const payload = `sym=${symbol}&ts=${ts}`;
  const sig = sign(payload);

  const res = await axios.post(
    `${API}/api/market/my-open-orders`,
    payload + `&sig=${sig}`,
    { headers: { "X-BTK-APIKEY": KEY } }
  );
  return res.data.result || [];
}

export async function cancelOrder(orderId, symbol) {
  const ts = Date.now();
  const payload = `id=${orderId}&sym=${symbol}&ts=${ts}`;
  const sig = sign(payload);

  return axios.post(
    `${API}/api/market/cancel-order`,
    payload + `&sig=${sig}`,
    { headers: { "X-BTK-APIKEY": KEY } }
  );
}

