import { getPrice, getBalance, placeOrder } from "./bitkub.js";

const SYMBOL = "XRP_THB";
const GRID = 0.006; // 0.6%
const MIN_THB = 100;

async function run() {
  const price = await getPrice(SYMBOL);
  const bal = await getBalance();

  const thb = bal.THB?.available || 0;
  const xrp = bal.XRP?.available || 0;

  console.log("PRICE:", price, "THB:", thb, "XRP:", xrp);

  // ถ้ามี XRP → ตั้งขาย
  if (xrp * price >= MIN_THB) {
    const sellPrice = Math.floor(price * (1 + GRID) * 100) / 100;
    console.log("SELL @", sellPrice);
    await placeOrder("sell", SYMBOL, xrp, sellPrice);
    return;
  }

  // ถ้ามี THB → ตั้งซื้อ
  if (thb >= MIN_THB) {
    const buyPrice = Math.floor(price * (1 - GRID) * 100) / 100;
    const amount = Math.floor((thb / buyPrice) * 100) / 100;
    console.log("BUY @", buyPrice);
    await placeOrder("buy", SYMBOL, amount, buyPrice);
  }
}

run().catch(console.error);
