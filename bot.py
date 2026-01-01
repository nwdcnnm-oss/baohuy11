import aiohttp
import asyncio
import re
import urllib.parse
import random
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

# ================== CẤU HÌNH ==================
BOT_TOKEN = "8080338995:AAHI8yhEUnJGgqEIDcaJ0eIKBGtuQpzQiX8"
ALLOWED_GROUP_ID = -1002666964512

API_FL1 = "https://abcdxyz310107.x10.mx/apifl.php?fl1={}"
API_FL2 = "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"

WRONG_GROUP_MSG = (
    "❌ *Xin lỗi, bot này chỉ hoạt động trong nhóm riêng tư\.*"
)

# Timeout request (30s là đủ)
TIMEOUT = aiohttp.ClientTimeout(total=30)
# Header giả lập trình duyệt
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
# =============================================

def get_vietnam_time():
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    return datetime.now(tz).strftime("%H:%M:%S \- %d/%m/%Y")

# Hàm escape an toàn tuyệt đối cho MarkdownV2
def esc(text):
    return escape_markdown(str(text), version=2)

async def check_group(update: Update):
    chat = update.effective_chat
    if not chat or chat.id != ALLOWED_GROUP_ID:
        if update.message:
            await update.message.reply_text(WRONG_GROUP_MSG, parse_mode=ParseMode.MARKDOWN_V2)
        return False
    return True

async def call_api(session, url):
    try:
        async with session.get(url, headers=HEADERS) as r:
            if r.status == 200:
                return (await r.text()).strip()
    except:
        return ""
    return ""

def parse_follow_data(text):
    if not text: return None
    # Regex bắt nickname và số lượng
    nickname = re.search(r'nickname[:\s]*([^\n\r]+)', text, re.IGNORECASE)
    before = re.search(r'follow\s*trước[:\s]*(\d+)', text, re.IGNORECASE)
    plus = re.search(r'\+(\d+)', text)
    
    return {
        "nickname": nickname.group(1).strip() if nickname else "Unknown",
        "before": int(before.group(1)) if before else 0,
        "plus": int(plus.group(1)) if plus else 0
    }

async def loading_animation(message):
    """Hàm tạo hiệu ứng loading giả lập"""
    steps = [
        "⏳ *Đang kết nối đến máy chủ\.\.\.*",
        "🔄 *Đang lấy dữ liệu user\.\.\. `20%`*",
        "🔄 *Đang đồng bộ API\.\.\. `60%`*",
        "🔄 *Đang xử lý kết quả\.\.\. `90%`*"
    ]
    for step in steps:
        try:
            await message.edit_text(step, parse_mode=ParseMode.MARKDOWN_V2)
            # Delay ngẫu nhiên từ 0.5s đến 1s để tạo cảm giác thực
            await asyncio.sleep(random.uniform(0.5, 1.0))
        except:
            pass

async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update): return
    
    if not context.args:
        await update.message.reply_text("❌ Sử dụng: `/buff <username>`", parse_mode=ParseMode.MARKDOWN)
        return

    raw_username = context.args[0]
    safe_username_url = urllib.parse.quote(raw_username) # Mã hóa URL an toàn
    
    # Gửi tin nhắn chờ ban đầu
    wait_msg = await update.message.reply_text("⏳ *Khởi tạo\.\.\.*", parse_mode=ParseMode.MARKDOWN_V2)

    # Chạy song song: Vừa gọi API, vừa chạy hiệu ứng loading
    # Điều này giúp tận dụng thời gian chờ API để hiện animation
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        task_api = asyncio.gather(
            call_api(session, API_FL1.format(safe_username_url)),
            call_api(session, API_FL2.format(safe_username_url))
        )
        task_loading = loading_animation(wait_msg)

        # Chờ cả 2 hoàn thành
        (res1, res2), _ = await asyncio.gather(task_api, task_loading)

    # Xử lý dữ liệu sau khi xong
    d1 = parse_follow_data(res1)
    d2 = parse_follow_data(res2)

    if not d1 and not d2:
        await wait_msg.edit_text("⚠️ *Lỗi: Không lấy được dữ liệu từ API\!*", parse_mode=ParseMode.MARKDOWN_V2)
        return

    # Tổng hợp dữ liệu
    data = d1 if d1 else d2
    nickname = data["nickname"]
    before = data["before"]
    total_plus = (d1["plus"] if d1 else 0) + (d2["plus"] if d2 else 0)
    current = before + total_plus
    time_now = get_vietnam_time()

    # Nội dung kết quả (Dùng hàm esc() để tránh lỗi Markdown)
    msg_content = (
        f"✅ *BUFF THÀNH CÔNG*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 *User:* `@{esc(raw_username)}`\n"
        f"📛 *Name:* {esc(nickname)}\n"
        f"📊 *Ban đầu:* `{before}`\n"
        f"📈 *Đã tăng:* `+{total_plus}`\n"
        f"✨ *Hiện tại:* `{current}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕒 *Time:* {esc(time_now)}"
    )

    try:
        await wait_msg.edit_text(msg_content, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        # Fallback text thuần nếu vẫn lỗi format (trường hợp hiếm)
        print(f"Error sending MD: {e}")
        await wait_msg.edit_text(f"✅ Xong! (Lỗi hiển thị format)\nUser: {raw_username}\nTăng: {total_plus}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update): return
    await update.message.reply_text("🤖 *Sẵn sàng\!* Gõ `/buff username`", parse_mode=ParseMode.MARKDOWN_V2)

def main():
    # from keep_alive import keep_alive
    # keep_alive() 
    
    print("🤖 Bot đang chạy...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buff", buff))
    app.run_polling()

if __name__ == "__main__":
    main()
