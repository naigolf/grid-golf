import axios from "axios";

const TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const CHAT_ID = process.env.TELEGRAM_CHAT_ID;

export async function sendTelegram(msg) {
  const url = `https://api.telegram.org/bot${TOKEN}/sendMessage`;
  await axios.post(url, {
    chat_id: CHAT_ID,
    text: msg
  });
}
