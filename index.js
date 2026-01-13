import config from "./config.js";
import { getPrice, placeOrder, getOpenOrders, cancelOrder } from "./bitkub.js";
import { notify } from "./telegram.js";

async function main() {
  const price = await getPrice();

  const buyPrice = price * (1 - config.BUY_DROP_PERCENT / 100);
  const sellPrice = price * (1 + config.SELL_RISE_PERCENT / 100);

  const qty = config.TRADE_THB / buyPrice;

  const openOrders = await getOpenOrders();

  // 🔴 ยกเลิกออเดอร์ค้าง
  for (const o of openOrders) {
    const ageMin = (Date.now() - o.ts) / 60000;
    if (ageMin > config.MAX_ORDER_MINUTES) {
      await cancelOrder(o.id);
      await notify(`❌ Cancel order ${o.id} (timeout ${ageMin.toFixed(1)} min)`);
    }
  }

  // 🟢 วาง grid ใหม่เมื่อไม่มีออเดอร์
  if (openOrders.length === 0) {
    await placeOrder("bid", qty, buyPrice);
    await notify(
      `🟢 BUY\nราคา ${buyPrice.toFixed(4)}\nจำนวน ${qty.toFixed(2)}`
    );

    await placeOrder("ask", qty, sellPrice);
    await notify(
      `🔵 SELL\nราคา ${sellPrice.toFixed(4)}\nจำนวน ${qty.toFixed(2)}`
    );
  }
}

main().catch(err => {
  notify("⚠️ ERROR\n" + err.message);
});
