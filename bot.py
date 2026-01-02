import aiohttp
import asyncio
import re
import urllib.parse
import logging
import random
from datetime import datetime
import pytz

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from keep_alive import keep_alive

# ================== CONFIG ==================
BOT_TOKEN = "8080338995:AAH7CTj8JlYfY6PEkSwLSzn832FaxfdSaP0"
ALLOWED_GROUP_ID = -1002666964512

API_CONFIG = {
    "fl1": ["https://abcdxyz310107.x10.mx/apifl.php?fl1={}"],
    "fl2": ["https://abcdxyz310107.x10.mx/apifl.php?fl2={}"]
}

TX_API_URL = "https://suntxlive.onrender.com/api/sun/txlive"

WRONG_GROUP_MSG = "❌ *Bot chỉ hoạt động trong nhóm được cấp phép\.*"

API_SEMAPHORE = asyncio.Semaphore(5)
FAKE_DELAY_MIN = 4
FAKE_DELAY_MAX = 6
# ===========================================

logging.basicConfig(level=logging.INFO)

# ============ UTILS ============
def get_vietnam_time():
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    return datetime.now(tz).strftime("%H:%M:%S \- %d/%m/%Y")

def esc(text):
    return escape_markdown(str(text or "Unknown"), version=2)

def mention_user(user):
    name = escape_markdown(user.first_name or "User", version=2)
    return f"[{name}](tg://user?id={user.id})"

# ============ CHECK GROUP ============
async def check_group(update: Update):
    chat = update.effective_chat
    if not chat or chat.id != ALLOWED_GROUP_ID:
        if update.message:
            await update.message.reply_text(
                WRONG_GROUP_MSG,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        return False
    return True

# ============ HTTP SESSION ============
session: aiohttp.ClientSession | None = None

async def fetch_api(url, timeout=12):
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0"}
        )

    async with API_SEMAPHORE:
        try:
            async with session.get(url, timeout=timeout) as resp:
                if resp.status == 200:
                    text = (await resp.text()).strip()
                    return text if text else ""
        except Exception as e:
            logging.error(f"API error: {e}")
    return ""

async def fetch_fastest_api(urls, timeout=15):
    tasks = [asyncio.create_task(fetch_api(u)) for u in urls]
    try:
        while tasks:
            done, pending = await asyncio.wait(
                tasks,
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                try:
                    res = task.result()
                    if res:
                        for p in pending:
                            p.cancel()
                        return res
                except:
                    pass
            tasks = list(pending)
    finally:
        for t in tasks:
            t.cancel()
    return ""

# ============ PARSE BUFF ============
def parse_result(text):
    name = re.search(r'(nickname|name|tên)[:\s]*([^\n\r]+)', text, re.I)
    before = re.search(r'(trước|before)[:\s]*(\d+)', text, re.I)
    plus = re.search(r'(\+|\btăng\b)[:\s]*(\d+)', text, re.I)

    return {
        "name": name.group(2).strip() if name else "Không rõ",
        "before": int(before.group(2)) if before else 0,
        "plus": int(plus.group(2)) if plus else 0
    }

# ============ BUFF CORE ============
async def handle_buff(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    if not await check_group(update):
        return

    if not context.args:
        await update.message.reply_text(
            f"❌ Cú pháp: `/{mode} <username>`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    username = context.args[0]
    safe_user = urllib.parse.quote(username)
    caller = mention_user(update.effective_user)

    wait_msg = await update.message.reply_text(
        "⏳ *Đang tải dữ liệu từ API\.\.\.*",
        parse_mode=ParseMode.MARKDOWN_V2
    )

    urls = [u.format(safe_user) for u in API_CONFIG[mode]]
    raw = await fetch_fastest_api(urls)

    if not raw:
        await wait_msg.edit_text(
            "⚠️ *API không trả dữ liệu*",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    data = parse_result(raw)

    for txt in ["📡 Đã nhận dữ liệu...", "🔎 Đang xử lý...", "📊 Tổng hợp kết quả..."]:
        await wait_msg.edit_text(txt, parse_mode=ParseMode.MARKDOWN_V2)
        await asyncio.sleep(random.uniform(1.0, 1.5))

    total = data["before"] + data["plus"]

    result = (
        f"✅ *BUFF THÀNH CÔNG \- {mode.upper()}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🙋 *Người dùng:* {caller}\n"
        f"👤 *User buff:* `@{esc(username)}`\n"
        f"📛 *Tên:* {esc(data['name'])}\n"
        f"📊 *Trước:* `{data['before']}`\n"
        f"📈 *Tăng:* `+{data['plus']}`\n"
        f"✨ *Tổng:* `{total}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕒 *Lúc:* {get_vietnam_time()}"
    )

    await wait_msg.edit_text(result, parse_mode=ParseMode.MARKDOWN_V2)

# ============ TÀI XỈU ============
async def fetch_tx_live():
    try:
        async with aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0"}
        ) as session:
            async with session.get(TX_API_URL, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logging.error(f"TX API error: {e}")
    return None

async def taixiu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update):
        return

    caller = mention_user(update.effective_user)

    msg = await update.message.reply_text(
        "🎲 *Đang load TÀI XỈU SUN LIVE\.\.\.*",
        parse_mode=ParseMode.MARKDOWN_V2
    )

    await asyncio.sleep(1.5)
    await msg.edit_text("📡 Kết nối máy chủ SUN LIVE...", parse_mode=ParseMode.MARKDOWN_V2)

    data = await fetch_tx_live()
    if not data:
        await msg.edit_text(
            "⚠️ *Không lấy được dữ liệu TÀI XỈU*",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    phien = data.get("phien", "???")
    ketqua = data.get("ketqua", "???")
    tong = data.get("tong", "???")
    xucxac = data.get("xucxac", [])

    xx = " - ".join(map(str, xucxac)) if isinstance(xucxac, list) else "?"

    result = (
        "🎲 *TÀI XỈU SUN LIVE*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🙋 *Người xem:* {caller}\n"
        f"🆔 *Phiên:* `{phien}`\n"
        f"🎯 *Kết quả:* *{ketqua}*\n"
        f"🎲 *Xúc xắc:* `{xx}`\n"
        f"➕ *Tổng:* `{tong}`\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🕒 *Lúc:* {get_vietnam_time()}"
    )

    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN_V2)

# ============ START ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update):
        return
    await update.message.reply_text(
        "🤖 *Bot sẵn sàng*\n"
        "• `/fl1 <username>`\n"
        "• `/fl2 <username>`\n"
        "• `/tx` hoặc `/taixiu`",
        parse_mode=ParseMode.MARKDOWN_V2
    )

# ============ MAIN ============
def main():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fl1", lambda u, c: handle_buff(u, c, "fl1")))
    app.add_handler(CommandHandler("fl2", lambda u, c: handle_buff(u, c, "fl2")))
    app.add_handler(CommandHandler("tx", taixiu_cmd))
    app.add_handler(CommandHandler("taixiu", taixiu_cmd))

    print("=== BOT IS RUNNING ===")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
