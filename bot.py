import aiohttp
import asyncio
import re
from datetime import datetime
import pytz # Thư viện xử lý múi giờ
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

# ================== CẤU HÌNH ==================
BOT_TOKEN = "8080338995:AAHI8yhEUnJGgqEIDcaJ0eIKBGtuQpzQiX8"
ALLOWED_GROUP_ID = -1002666964512

API_FL1 = "https://abcdxyz310107.x10.mx/apifl.php?fl1={}"
API_FL2 = "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"

WRONG_GROUP_MSG = (
    "❌ *Xin lỗi, bot này chỉ hoạt động trong nhóm này:*\n"
    "👉 https://t.me/baohuydevs"
)

TIMEOUT = aiohttp.ClientTimeout(total=120)
# =============================================

# Hàm lấy ngày giờ Việt Nam hiện tại
def get_vietnam_time():
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    return datetime.now(tz).strftime("%H:%M:%S - %d/%m/%Y")

async def check_group(update: Update):
    chat = update.effective_chat
    if not chat or chat.id != ALLOWED_GROUP_ID:
        if update.message:
            await update.message.reply_text(WRONG_GROUP_MSG, parse_mode="Markdown", disable_web_page_preview=True)
        return False
    return True

async def call_api(session, url):
    try:
        async with session.get(url) as r:
            if r.status == 200:
                return (await r.text()).strip()
    except:
        pass
    return ""

def parse_follow_data(text):
    if not text: return None
    nickname = re.search(r'nickname[:\s]*([^\n\r]+)', text, re.IGNORECASE)
    before = re.search(r'follow\s*trước[:\s]*(\d+)', text, re.IGNORECASE)
    plus = re.search(r'\+(\d+)', text)
    return {
        "nickname": nickname.group(1).strip() if nickname else "Không rõ",
        "before": int(before.group(1)) if before else 0,
        "plus": int(plus.group(1)) if plus else 0
    }

def format_success(username, nickname, before, plus):
    time_str = get_vietnam_time()
    return (
        "✅ *BUFF THÀNH CÔNG*\n"
        "--------------------------\n"
        f"👤 *Tài khoản:* @{username}\n"
        f"📛 *Nickname:* {nickname}\n"
        f"📊 *Trước khi tăng:* {before}\n"
        f"📈 *Đã tăng thêm:* +{plus}\n"
        f"✨ *Hiện tại:* {before + plus}\n"
        "--------------------------\n"
        f"🕒 *Thời gian:* {time_str}"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update): return
    await update.message.reply_text("🤖 *Bot Buff Follow*\nSử dụng: `/buff <username>`", parse_mode="Markdown")

async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update): return
    if len(context.args) != 1:
        await update.message.reply_text("❌ `/buff <username>`")
        return

    username = context.args[0]
    wait_msg = await update.message.reply_text("⏳ *Đang xử lý dữ liệu...*", parse_mode="Markdown")

    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        res1, res2 = await asyncio.gather(
            call_api(session, API_FL1.format(username)),
            call_api(session, API_FL2.format(username))
        )

    d1, d2 = parse_follow_data(res1), parse_follow_data(res2)

    if not d1 and not d2:
        await wait_msg.edit_text("⚠️ *API không trả dữ liệu!*")
        return

    nickname = d1["nickname"] if d1 else d2["nickname"]
    before = d1["before"] if d1 else d2["before"]
    plus = (d1["plus"] if d1 else 0) + (d2["plus"] if d2 else 0)

    await wait_msg.edit_text(format_success(username, nickname, before, plus), parse_mode="Markdown")

def main():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buff", buff))
    print(f"🤖 Bot is running... Time: {get_vietnam_time()}")
    app.run_polling()

if __name__ == "__main__":
    main()
