import config from "./config.js";
import { getPrice, placeOrder, getOpenOrders, cancelOrder } from "./bitkub.js";
import { notify } from "./telegram.js";

async function main() {
  const price = await getPrice();

  const buyPrice = price * (1 - config.BUY_DROP_PERCENT / 100);
  const sellPrice = price * (1 + config.SELL_RISE_PERCENT / 100);

  const qty = config.TRADE_THB / buyPrice;

  const orders = await getOpenOrders();

  // กันออเดอร์ค้าง
  for (const o of orders) {
    const ageMin = (Date.now() - o.ts) / 60000;
    if (ageMin > config.MAX_ORDER_MINUTES) {
      await cancelOrder(o.id);
      await notify(`❌ Cancel order ${o.id} (timeout ${ageMin.toFixed(1)} min)`);
    }
  }

  // วาง Grid 1 ชั้น เมื่อไม่มีออเดอร์ค้าง
  if (orders.length === 0) {
    await placeOrder("buy", qty, buyPrice);
    await notify(`🟢 BUY @ ${buyPrice.toFixed(4)} | qty ${qty.toFixed(2)}`);

    await placeOrder("sell", qty, sellPrice);
    await notify(`🔵 SELL @ ${sellPrice.toFixed(4)} | qty ${qty.toFixed(2)}`);
  }
}

main().catch(err => notify("⚠️ ERROR\n" + err.message));
