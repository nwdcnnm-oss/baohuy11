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

WRONG_GROUP_MSG = "❌ *Bot chỉ hoạt động trong nhóm được cấp phép\.*"

COOLDOWN_TIME = 30
USER_COOLDOWN = {}

API_SEMAPHORE = asyncio.Semaphore(5)

FAKE_DELAY_MIN = 4   # giây
FAKE_DELAY_MAX = 6   # giây
# ============================================

logging.basicConfig(level=logging.INFO)

# ============ UTILS ============
def get_vietnam_time():
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    return datetime.now(tz).strftime("%H:%M:%S \- %d/%m/%Y")

def esc(text):
    return escape_markdown(str(text or "Unknown"), version=2)

# ============ CHECK GROUP ============
async def check_group(update: Update):
    chat = update.effective_chat
    if not chat or chat.id != ALLOWED_GROUP_ID:
        if chat and chat.type in ("group", "supergroup"):
            try:
                await chat.leave()
            except:
                pass
        if update.message:
            await update.message.reply_text(
                WRONG_GROUP_MSG,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        return False
    return True

# ============ COOLDOWN ============
def check_cooldown(user_id):
    now = datetime.now().timestamp()
    last = USER_COOLDOWN.get(user_id, 0)
    if now - last < COOLDOWN_TIME:
        return True, int(COOLDOWN_TIME - (now - last))
    USER_COOLDOWN[user_id] = now
    return False, 0

# ============ HTTP SESSION ============
session: aiohttp.ClientSession | None = None

async def fetch_api(url, timeout=10):
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0"}
        )

    async with API_SEMAPHORE:
        try:
            async with session.get(url, timeout=timeout) as resp:
                if resp.status == 200:
                    return (await resp.text()).strip()
        except:
            pass
    return ""

async def fetch_fastest_api(urls):
    tasks = [asyncio.create_task(fetch_api(u)) for u in urls]
    done, pending = await asyncio.wait(
        tasks, return_when=asyncio.FIRST_COMPLETED
    )
    for p in pending:
        p.cancel()
    for d in done:
        return d.result()
    return ""

# ============ PARSE RESULT ============
def parse_result(text: str):
    if not text:
        return {"name": "Không rõ", "before": 0, "plus": 0}

    name = re.search(r'(nickname|name|tên)[:\s]*([^\n\r]+)', text, re.I)
    before = re.search(r'(trước|before|old)[:\s]*(\d+)', text, re.I)
    plus = re.search(r'(tăng|increase|\+)\s*(\d+)', text, re.I)

    return {
        "name": name.group(2).strip() if name else "Không rõ",
        "before": int(before.group(2)) if before else 0,
        "plus": int(plus.group(2)) if plus else 0
    }

# ============ CORE ============
async def handle_buff(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    if not await check_group(update):
        return

    if not context.args:
        await update.message.reply_text(
            f"❌ Cú pháp: `/{mode} <username>`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    cd, remain = check_cooldown(update.effective_user.id)
    if cd:
        await update.message.reply_text(
            f"⏳ Vui lòng đợi `{remain}s`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    username = context.args[0]
    safe_user = urllib.parse.quote(username)

    wait_msg = await update.message.reply_text(
        "🌐 *Đang kết nối máy chủ\.\.\.*",
        parse_mode=ParseMode.MARKDOWN_V2
    )

    # ===== LOAD API NHANH =====
    urls = [u.format(safe_user) for u in API_CONFIG[mode]]
    raw = await fetch_fastest_api(urls)

    if not raw:
        await wait_msg.edit_text(
            "⚠️ *API phản hồi chậm hoặc lỗi*",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    data = parse_result(raw)  # ✅ ĐÃ LOAD XONG API

    # ===== GIẢ LẬP XỬ LÝ (TRẢ CHẬM) =====
    fake_steps = [
        "📡 Đã nhận dữ liệu từ máy chủ...",
        "📊 Đang kiểm tra dữ liệu...",
        "🔎 Đang xác minh kết quả...",
        "🧮 Đang tổng hợp báo cáo..."
    ]

    delay = random.uniform(FAKE_DELAY_MIN, FAKE_DELAY_MAX)
    step_delay = delay / len(fake_steps)

    for step in fake_steps:
        await wait_msg.edit_text(step, parse_mode=ParseMode.MARKDOWN_V2)
        await asyncio.sleep(step_delay)

    # ===== TRẢ KẾT QUẢ =====
    total = data["before"] + data["plus"]

    result = (
        f"✅ *BUFF THÀNH CÔNG \- {mode.upper()}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 *User:* `@{esc(username)}`\n"
        f"📛 *Tên:* {esc(data['name'])}\n"
        f"📊 *Trước:* `{data['before']}`\n"
        f"📈 *Tăng:* `+{data['plus']}`\n"
        f"✨ *Tổng:* `{total}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕒 *Lúc:* {get_vietnam_time()}"
    )

    await wait_msg.edit_text(result, parse_mode=ParseMode.MARKDOWN_V2)

# ============ COMMANDS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update):
        return
    await update.message.reply_text(
        "🤖 *Bot sẵn sàng*\n"
        "• `/fl1 <username>`\n"
        "• `/fl2 <username>`",
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def fl1_cmd(update, context):
    await handle_buff(update, context, "fl1")

async def fl2_cmd(update, context):
    await handle_buff(update, context, "fl2")

# ============ MAIN ============
def main():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fl1", fl1_cmd))
    app.add_handler(CommandHandler("fl2", fl2_cmd))

    print("=== BOT IS RUNNING ===")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
