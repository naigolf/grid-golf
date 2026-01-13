import config from "./config.js";
import { getPrice, placeOrder, getOpenOrders, cancelOrder } from "./bitkub.js";
import { notify } from "./telegram.js";

async function main() {
  const price = await getPrice();

  const buyPrice = price * (1 - config.BUY_DROP_PERCENT / 100);
  const sellPrice = price * (1 + config.SELL_RISE_PERCENT / 100);

  const qty = config.TRADE_THB / buyPrice;

  const orders = await getOpenOrders();

  // 🔴 กันออเดอร์ค้าง
  for (const o of orders) {
    const age = (Date.now() - o.ts) / 60000;
    if (age > config.MAX_ORDER_MINUTES) {
      await cancelOrder(o.id);
      await notify(`❌ Cancel order ${o.id} (timeout)`);
    }
  }

  if (orders.length === 0) {
    const buy = await placeOrder("bid", qty, buyPrice);
    await notify(
      `🟢 BUY\nราคา: ${buyPrice.toFixed(4)}\nจำนวน: ${qty.toFixed(2)}`
    );

    const sell = await placeOrder("ask", qty, sellPrice);
    await notify(
      `🔵 SELL\nราคา: ${sellPrice.toFixed(4)}\nจำนวน: ${qty.toFixed(2)}`
    );
  }
}

main().catch(err => notify("⚠️ ERROR\n" + err.message));
