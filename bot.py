import aiohttp
import asyncio
import re
import logging
import os
from datetime import datetime
import pytz # Thư viện xử lý múi giờ
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import BadRequest, Forbidden

# ================== CẤU HÌNH HỆ THỐNG ==================
# 👇 DÁN TOKEN CỦA BẠN VÀO ĐÂY 👇
BOT_TOKEN = "8080338995:AAGJcUCZvBaLSjgHJfjpiWK6a-xFBa4TCEU" 

ALLOWED_GROUP_ID = -1002666964512
ADMINS = [5736655322]

# API (Sử dụng host free nên cần timeout cao)
API_ENDPOINTS = [
    "https://abcdxyz310107.x10.mx/apifl.php?fl1={}",
    "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

TIMEOUT = aiohttp.ClientTimeout(total=60) # 60 giây chờ
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh') # Múi giờ VN

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

AUTO_BUFF = {} 

try:
    from keep_alive import keep_alive
except ImportError:
    def keep_alive(): pass

# ================== CÁC HÀM HỖ TRỢ ==================

async def check_perm(update: Update):
    """Kiểm tra quyền truy cập"""
    chat = update.effective_chat
    user = update.effective_user
    if not chat: return False
    
    # Admin được dùng mọi nơi, User thường chỉ trong nhóm
    if user.id in ADMINS or chat.id == ALLOWED_GROUP_ID:
        return True
    return False

async def call_api(session, url):
    """Gọi API an toàn"""
    try:
        async with session.get(url, headers=HEADERS, ssl=False) as r:
            if r.status == 200:
                return (await r.text()).strip()
    except Exception:
        pass
    return ""

def parse_data(text):
    """Phân tích dữ liệu trả về"""
    if not text: return None
    nickname = re.search(r'nickname[:\s]*([^\n\r<]+)', text, re.IGNORECASE)
    before = re.search(r'(?:trước|cũ|start)[:\s]*(\d+)', text, re.IGNORECASE)
    plus = re.search(r'\+(\d+)', text)
    
    return {
        "nickname": nickname.group(1).strip() if nickname else "Unknown",
        "before": int(before.group(1)) if before else 0,
        "plus": int(plus.group(1)) if plus else 0
    }

def get_time_str():
    """Lấy giờ Việt Nam hiện tại"""
    return datetime.now(VN_TZ).strftime("%H:%M:%S - %d/%m")

def format_message_40(username, nickname, before, plus):
    """Giao diện tin nhắn 4.0 Đẹp"""
    total = before + plus
    time_now = get_time_str()
    
    # Thanh trạng thái giả lập
    return (
        "🚀 *HỆ THỐNG BUFF FOLLOW V4.0*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 *User:* `@{username}`\n"
        f"🏷 *Name:* {nickname}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📉 *Ban đầu:* `{before:,}`\n"
        f"📈 *Đã tăng:* `+{plus:,}`\n"
        f"📊 *Tổng:* `{total:,}`\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🕒 *Cập nhật:* `{time_now}`\n"
        "✅ *Trạng thái:* Đang hoạt động..."
    )

# ================== XỬ LÝ DỮ LIỆU ==================

async def fetch_data(username):
    """Hàm lấy dữ liệu từ cả 2 nguồn"""
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        tasks = [call_api(session, url.format(username)) for url in API_ENDPOINTS]
        results = await asyncio.gather(*tasks)
    
    d1 = parse_data(results[0])
    d2 = parse_data(results[1])
    
    if not d1 and not d2: return None
    
    # Logic gộp dữ liệu
    base = d1 if d1 else d2
    total_plus = (d1["plus"] if d1 else 0) + (d2["plus"] if d2 else 0)
    
    return {
        "nickname": base["nickname"],
        "before": base["before"],
        "plus": total_plus
    }

# ================== AUTO BUFF JOB (15 PHÚT) ==================

async def autobuff_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    data = AUTO_BUFF.get(chat_id)
    
    if not data:
        context.job.schedule_removal()
        return

    username = data["username"]
    message_id = data["message_id"]
    last_plus = data.get("last_plus", -1) # Dùng số lượng tăng để so sánh thay vì text

    result = await fetch_data(username)
    
    if not result:
        return # API lỗi thì bỏ qua

    # Tạo nội dung tin nhắn mới
    new_text = format_message_40(username, result["nickname"], result["before"], result["plus"])

    # SO SÁNH: Nếu số lượng tăng không đổi so với lần trước -> KHÔNG SỬA MESSAGE
    # Giúp tránh lỗi "Message not modified" và đỡ spam log
    if result["plus"] == last_plus:
        return

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=new_text,
            parse_mode="Markdown"
        )
        # Cập nhật trạng thái mới vào bộ nhớ
        AUTO_BUFF[chat_id]["last_plus"] = result["plus"]
        
    except BadRequest as e:
        if "Message to edit not found" in str(e):
            context.job.schedule_removal()
            AUTO_BUFF.pop(chat_id, None)
            await context.bot.send_message(chat_id, f"⚠️ Tin nhắn gốc của {username} đã bị xóa. Auto dừng lại.")
    except Forbidden:
        context.job.schedule_removal()
        AUTO_BUFF.pop(chat_id, None)
    except Exception as e:
        logger.error(f"Job Error: {e}")

# ================== COMMANDS ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_perm(update): return
    await update.message.reply_text(
        "🔰 *MENU BOT BUFF 4.0*\n\n"
        "1️⃣ `/buff <user>` : Xem ngay lập tức\n"
        "2️⃣ `/autobuff <user>` : Treo 15 phút/lần (Admin)\n"
        "3️⃣ `/stopbuff` : Dừng treo (Admin)",
        parse_mode="Markdown"
    )

async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_perm(update): return
    if not context.args:
        await update.message.reply_text("❌ Nhập: `/buff username`", parse_mode="Markdown")
        return
    
    username = context.args[0].replace("@", "")
    msg = await update.message.reply_text("⏳ *Đang tải dữ liệu...*", parse_mode="Markdown")
    
    result = await fetch_data(username)
    
    if not result:
        await msg.edit_text("⚠️ *Lỗi kết nối API hoặc User không tồn tại.*", parse_mode="Markdown")
        return

    text = format_message_40(username, result["nickname"], result["before"], result["plus"])
    await msg.edit_text(text, parse_mode="Markdown")

async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_perm(update): return
    
    # Chỉ Admin mới được treo để tránh spam server
    if update.effective_user.id not in ADMINS: 
        await update.message.reply_text("🔒 Lệnh này chỉ dành cho Admin.")
        return

    if not context.args:
        await update.message.reply_text("❌ Nhập: `/autobuff username`", parse_mode="Markdown")
        return

    chat_id = update.effective_chat.id
    username = context.args[0].replace("@", "")

    # Xóa job cũ nếu đang chạy ở nhóm này
    if chat_id in AUTO_BUFF:
        for job in context.job_queue.get_jobs_by_name(str(chat_id)):
            job.schedule_removal()

    msg = await update.message.reply_text(
        f"✅ *Đã kích hoạt Auto Buff 4.0*\n"
        f"👤 User: `{username}`\n"
        f"⏱ Chu kỳ: 15 phút/lần",
        parse_mode="Markdown"
    )
    
    # Khởi tạo bộ nhớ
    AUTO_BUFF[chat_id] = {
        "username": username,
        "message_id": msg.message_id,
        "last_plus": -1
    }
    
    # Set interval = 900 giây (15 phút)
    context.job_queue.run_repeating(
        autobuff_job,
        interval=900, 
        first=10, 
        chat_id=chat_id, 
        name=str(chat_id)
    )

async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_perm(update): return
    if update.effective_user.id not in ADMINS: return

    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    
    if not jobs:
        await update.message.reply_text("⚠️ Hiện không có tiến trình nào chạy.")
        return

    for job in jobs: job.schedule_removal()
    AUTO_BUFF.pop(chat_id, None)
    await update.message.reply_text("🛑 Đã dừng Auto Buff thành công.")

# ================== MAIN ==================
def main():
    keep_alive() # Web server cho Render
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("stopbuff", stopbuff))
    
    print("🚀 Bot Buff 4.0 đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
```
