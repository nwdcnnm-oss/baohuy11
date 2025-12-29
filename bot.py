import aiohttp
import asyncio
import re
import logging
import json
import os
from datetime import datetime
import pytz 
from html import escape 
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import BadRequest, Forbidden

# ================== CẤU HÌNH HỆ THỐNG ==================
# 👇 HÃY DÁN TOKEN CỦA BẠN VÀO DƯỚI ĐÂY 👇
BOT_TOKEN = "8080338995:AAGJcUCZvBaLSjgHJfjpiWK6a-xFBa4TCEU" 

ALLOWED_GROUP_ID = -1002666964512
ADMINS = [5736655322]

# Danh sách API dự phòng
API_ENDPOINTS = [
    "https://abcdxyz310107.x10.mx/apifl.php?fl1={}",
    "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"
]

# Header giả lập trình duyệt Chrome mới nhất
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/json,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Timeout cao (60s) để chờ server free phản hồi
TIMEOUT = aiohttp.ClientTimeout(total=60)
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# Cấu hình Log
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bộ nhớ tạm
AUTO_BUFF = {} 

# Import Keep Alive
try:
    from keep_alive import keep_alive
except ImportError:
    def keep_alive(): pass

# ================== CÁC HÀM TIỆN ÍCH ==================

async def check_perm(update: Update):
    """Kiểm tra quyền Admin hoặc nhóm được phép"""
    chat = update.effective_chat
    user = update.effective_user
    if not chat: return False
    
    if user.id in ADMINS: return True
    if chat.id == ALLOWED_GROUP_ID: return True
    
    return False

async def call_api(session, url):
    """Gọi API an toàn với cơ chế thử lại"""
    try:
        async with session.get(url, headers=HEADERS, ssl=False) as r:
            if r.status == 200:
                text = await r.text()
                return text.strip()
    except Exception as e:
        logger.error(f"API Error ({url}): {e}")
    return ""

def clean_string(text):
    """Làm sạch tên người dùng khỏi ký tự rác JSON"""
    if not text: return "Unknown"
    # Xóa các ký tự: ngoặc kép, ngoặc đơn, ngoặc nhọn, hai chấm
    cleaned = re.sub(r'["\'\{\}:]', '', text)
    return cleaned.strip().strip('.')

def parse_data(text):
    """
    Phân tích dữ liệu thông minh (Hỗ trợ JSON lẫn Text)
    """
    if not text: return None
    
    nickname = "Unknown"
    before = 0
    plus = 0

    # Ưu tiên 1: Thử đọc dạng JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            # Tìm nickname
            for k in ['nickname', 'name', 'user']:
                if k in data: nickname = str(data[k]); break
            # Tìm before
            for k in ['start', 'before', 'trước', 'old']:
                if k in data and str(data[k]).isdigit(): before = int(data[k]); break
            # Tìm plus
            for k in ['plus', 'add', 'tăng', 'new']:
                if k in data and str(data[k]).isdigit(): plus = int(data[k]); break
            
            return {"nickname": clean_string(nickname), "before": before, "plus": plus}
    except:
        pass # Nếu lỗi JSON, chuyển sang Regex

    # Ưu tiên 2: Quét Regex
    # Tìm nickname (bỏ qua các ký tự đặc biệt của JSON)
    nick_match = re.search(r'nickname\W+([^\n\r,]+)', text, re.IGNORECASE)
    if nick_match:
        nickname = clean_string(nick_match.group(1))

    # Tìm số liệu
    before_match = re.search(r'(?:trước|cũ|start|begin)[^0-9]*(\d+)', text, re.IGNORECASE)
    plus_match = re.search(r'(?:\+|plus|tăng|add)[^0-9]*(\d+)', text, re.IGNORECASE)

    if before_match: before = int(before_match.group(1))
    if plus_match: plus = int(plus_match.group(1))

    return {
        "nickname": nickname,
        "before": before,
        "plus": plus
    }

def format_message(username, nickname, before, plus):
    """Tạo nội dung tin nhắn HTML đẹp"""
    total = before + plus
    time_now = datetime.now(VN_TZ).strftime("%H:%M:%S - %d/%m")
    
    # Escape HTML để an toàn
    safe_user = escape(username)
    safe_nick = escape(nickname)

    return (
        f"<b>🚀 HỆ THỐNG BUFF FOLLOW V5.0</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> <code>@{safe_user}</code>\n"
        f"🏷 <b>Name:</b> {safe_nick}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📉 <b>Ban đầu:</b> <code>{before:,}</code>\n"
        f"📈 <b>Đã tăng:</b> <code>+{plus:,}</code>\n"
        f"📊 <b>Tổng:</b> <code>{total:,}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <b>Cập nhật:</b> <code>{time_now}</code>\n"
        f"✅ <b>Trạng thái:</b> Đang hoạt động..."
    )

# ================== XỬ LÝ LOGIC CHÍNH ==================

async def fetch_data_merged(username):
    """Lấy dữ liệu từ nhiều nguồn và gộp lại"""
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        tasks = [call_api(session, url.format(username)) for url in API_ENDPOINTS]
        results = await asyncio.gather(*tasks)

    d1 = parse_data(results[0])
    d2 = parse_data(results[1])

    if not d1 and not d2: return None

    # Logic hợp nhất: Lấy nickname đẹp nhất, lấy số liệu max
    base = d1 if (d1 and d1["nickname"] != "Unknown") else d2
    if not base and d1: base = d1
    if not base: base = {"nickname": "Unknown", "before": 0}

    # Cộng dồn số tăng từ cả 2 nguồn
    plus = (d1["plus"] if d1 else 0) + (d2["plus"] if d2 else 0)
    
    # Lấy mốc ban đầu (Before)
    before = max((d1["before"] if d1 else 0), (d2["before"] if d2 else 0))

    return {
        "nickname": base["nickname"],
        "before": before,
        "plus": plus
    }

# ================== JOB QUEUE (AUTOBUFF) ==================

async def autobuff_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    data = AUTO_BUFF.get(chat_id)
    
    if not data:
        context.job.schedule_removal()
        return

    username = data["username"]
    message_id = data["message_id"]
    last_plus = data.get("last_plus", -1)

    result = await fetch_data_merged(username)
    if not result: return 

    # Nếu số lượng không đổi -> Không làm gì (Tránh lỗi Telegram)
    if result["plus"] == last_plus:
        return

    new_text = format_message(username, result["nickname"], result["before"], result["plus"])

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=new_text,
            parse_mode="HTML"
        )
        AUTO_BUFF[chat_id]["last_plus"] = result["plus"]
    except BadRequest as e:
        # Nếu tin nhắn bị xóa, dừng auto
        if "Message to edit not found" in str(e):
            context.job.schedule_removal()
            AUTO_BUFF.pop(chat_id, None)
            try: await context.bot.send_message(chat_id, f"⚠️ Tin nhắn đã bị xóa. Auto Buff dừng lại.")
            except: pass
    except Forbidden:
        # Bot bị kick
        context.job.schedule_removal()
        AUTO_BUFF.pop(chat_id, None)

# ================== LỆNH BOT ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_perm(update): return
    await update.message.reply_text(
        "🔰 <b>MENU BUFF V5.0</b>\n"
        "1️⃣ <code>/buff user</code> : Check ngay\n"
        "2️⃣ <code>/autobuff user</code> : Treo 15p (Admin)\n"
        "3️⃣ <code>/checkapi user</code> : Kiểm tra API\n"
        "4️⃣ <code>/stopbuff</code> : Dừng treo",
        parse_mode="HTML"
    )

async def checkapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Công cụ Debug API"""
    if not await check_perm(update): return
    if not context.args:
        await update.message.reply_text("Nhập: /checkapi username")
        return
    
    username = context.args[0].replace("@", "")
    msg = await update.message.reply_text("🔍 Đang kết nối API gốc...", parse_mode="HTML")
    
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        raw_text = await call_api(session, API_ENDPOINTS[0].format(username))
    
    display_text = escape(raw_text[:2000]) if raw_text else "API trả về Rỗng/Lỗi!"
    await msg.edit_text(f"📡 <b>RAW DATA (Source 1):</b>\n<pre>{display_text}</pre>", parse_mode="HTML")

async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_perm(update): return
    if not context.args:
        await update.message.reply_text("❌ Nhập: <code>/buff username</code>", parse_mode="HTML")
        return
    
    username = context.args[0].replace("@", "")
    msg = await update.message.reply_text("⏳ <i>Đang tải dữ liệu...</i>", parse_mode="HTML")
    
    result = await fetch_data_merged(username)
    
    if not result:
        await msg.edit_text("⚠️ <b>Không lấy được dữ liệu.</b>\nHãy thử <code>/checkapi</code> để kiểm tra.", parse_mode="HTML")
        return

    text = format_message(username, result["nickname"], result["before"], result["plus"])
    await msg.edit_text(text, parse_mode="HTML")

async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_perm(update): return
    if update.effective_user.id not in ADMINS: 
        await update.message.reply_text("🔒 Lệnh dành riêng cho Admin.")
        return

    if not context.args:
        await update.message.reply_text("❌ Nhập: <code>/autobuff username</code>", parse_mode="HTML")
        return

    chat_id = update.effective_chat.id
    username = context.args[0].replace("@", "")

    # Xóa job cũ ở nhóm này
    if chat_id in AUTO_BUFF:
        for job in context.job_queue.get_jobs_by_name(str(chat_id)):
            job.schedule_removal()

    msg = await update.message.reply_text(
        f"✅ <b>Kích hoạt Auto Buff V5</b>\n👤 User: <code>{username}</code>\n⏱ Chu kỳ: 15 phút",
        parse_mode="HTML"
    )
    
    AUTO_BUFF[chat_id] = {"username": username, "message_id": msg.message_id, "last_plus": -1}
    
    # Interval 900s = 15 phút
    context.job_queue.run_repeating(autobuff_job, interval=900, first=10, chat_id=chat_id, name=str(chat_id))

async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_perm(update): return
    if update.effective_user.id not in ADMINS: return

    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    
    if not jobs:
        await update.message.reply_text("⚠️ Không có tiến trình nào đang chạy.")
        return

    for job in jobs: job.schedule_removal()
    AUTO_BUFF.pop(chat_id, None)
    await update.message.reply_text("🛑 Đã dừng Auto Buff.")

def main():
    keep_alive() # Chạy web server
    print("🚀 Bot V5.0 is Starting...")
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("stopbuff", stopbuff))
    app.add_handler(CommandHandler("checkapi", checkapi))

    app.run_polling()

if __name__ == "__main__":
    main()
