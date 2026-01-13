import axios from "axios";
import config from "./config.js";

export async function notify(text) {
  if (!config.TELEGRAM_TOKEN || !config.TELEGRAM_CHAT_ID) return;
  await axios.post(
    `https://api.telegram.org/bot${config.TELEGRAM_TOKEN}/sendMessage`,
    { chat_id: config.TELEGRAM_CHAT_ID, text }
  );
}
