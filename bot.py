import aiohttp
import asyncio
import re
import urllib.parse
import random
import logging
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

# --- IMPORT KEEP ALIVE ---
from keep_alive import keep_alive

# ================== CẤU HÌNH ==================
BOT_TOKEN = "8080338995:AAHI8yhEUnJGgqEIDcaJ0eIKBGtuQpzQiX8"
ALLOWED_GROUP_ID = -1002666964512

API_CONFIG = {
    "fl1": "https://abcdxyz310107.x10.mx/apifl.php?fl1={}",
    "fl2": "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"
}

WRONG_GROUP_MSG = "❌ *Bot chỉ hoạt động trong nhóm được cấp phép\.*"
# =============================================

logging.basicConfig(level=logging.INFO)

def get_vietnam_time():
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    return datetime.now(tz).strftime("%H:%M:%S \- %d/%m/%Y")

def esc(text):
    """Hàm chống lỗi format Markdown"""
    return escape_markdown(str(text or "Unknown"), version=2)

async def check_group(update: Update):
    if not update.effective_chat or update.effective_chat.id != ALLOWED_GROUP_ID:
        if update.message:
            await update.message.reply_text(WRONG_GROUP_MSG, parse_mode=ParseMode.MARKDOWN_V2)
        return False
    return True

async def fetch_api(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return (await response.text()).strip()
    except:
        return ""
    return ""

def parse_result(text):
    if not text: return None
    nickname = re.search(r'nickname[:\s]*([^\n\r]+)', text, re.IGNORECASE)
    before = re.search(r'follow\s*trước[:\s]*(\d+)', text, re.IGNORECASE)
    plus = re.search(r'\+(\d+)', text)
    return {
        "name": nickname.group(1).strip() if nickname else "Không rõ",
        "before": int(before.group(1)) if before else 0,
        "plus": int(plus.group(1)) if plus else 0
    }

async def handle_buff(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    if not await check_group(update): return
    
    if not context.args:
        await update.message.reply_text(f"❌ Cú pháp: `/{mode} <username>`", parse_mode=ParseMode.MARKDOWN_V2)
        return

    username = context.args[0]
    safe_user = urllib.parse.quote(username)
    
    wait_msg = await update.message.reply_text(f"⏳ *Đang khởi tạo nguồn {mode.upper()}\.\.\.*", parse_mode=ParseMode.MARKDOWN_V2)

    # Animation loading
    for p in [30, 65, 90]:
        await asyncio.sleep(random.uniform(0.5, 1.0))
        await wait_msg.edit_text(f"🔄 *Nguồn {mode.upper()} đang xử lý: {p}%\.\.\.*", parse_mode=ParseMode.MARKDOWN_V2)

    raw_res = await fetch_api(API_CONFIG[mode].format(safe_user))
    data = parse_result(raw_res)

    if not data:
        await wait_msg.edit_text(f"⚠️ *Nguồn {mode.upper()} lỗi hoặc sai username\!*", parse_mode=ParseMode.MARKDOWN_V2)
        return

    res_msg = (
        f"✅ *BUFF THÀNH CÔNG \- {mode.upper()}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 *User:* `@{esc(username)}`\n"
        f"📛 *Tên:* {esc(data['name'])}\n"
        f"📊 *Trước:* `{data['before']}`\n"
        f"📈 *Tăng:* `+{data['plus']}`\n"
        f"✨ *Tổng:* `{data['before'] + data['plus']}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕒 *Lúc:* {get_vietnam_time()}"
    )
    await wait_msg.edit_text(res_msg, parse_mode=ParseMode.MARKDOWN_V2)

async def start(update, context):
    if not await check_group(update): return
    await update.message.reply_text("🤖 *Bot sẵn sàng\!*\nSử dụng `/fl1` hoặc `/fl2` kèm username\.", parse_mode=ParseMode.MARKDOWN_V2)

def main():
    # Kích hoạt server giữ bot thức
    keep_alive()
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fl1", lambda u, c: handle_buff(u, c, "fl1")))
    app.add_handler(CommandHandler("fl2", lambda u, c: handle_buff(u, c, "fl2")))
    
    print("--- BOT IS RUNNING ---")
    # drop_pending_updates giúp tránh lỗi Conflict khi khởi động lại
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
