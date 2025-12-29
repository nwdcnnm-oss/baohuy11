import aiohttp
import asyncio
import re
import logging
import json
from datetime import datetime
import pytz 
from html import escape 
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import BadRequest, Forbidden

# ================== CẤU HÌNH HỆ THỐNG ==================

# 👇 NHẬP TOKEN CỦA BẠN VÀO ĐÂY
BOT_TOKEN = "8080338995:AAGJcUCZvBaLSjgHJfjpiWK6a-xFBa4TCEU" 

# ID Admin (Người được dùng lệnh /autobuff)
ADMINS = [5736655322] 

# Danh sách API
API_ENDPOINTS = [
    "https://abcdxyz310107.x10.mx/apifl.php?fl1={}",
    "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"
]

# Cấu hình mạng
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01"
}
TIMEOUT = aiohttp.ClientTimeout(total=20) # 20s timeout
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# Logging
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

# ================== HÀM XỬ LÝ DỮ LIỆU (QUAN TRỌNG) ==================

def clean_string(text):
    """Lọc tên người dùng cho sạch đẹp"""
    if not text: return "Unknown"
    return re.sub(r'[^\w\s\-\.]', '', str(text)).strip()

def parse_data(text):
    """
    Phân tích dữ liệu JSON chính xác cho API của bạn
    Hỗ trợ các key: followers_increased, followers_before, followers_now
    """
    if not text or len(text) < 5: return None
    
    nickname = "Unknown"
    before = 0
    plus = 0
    current = 0

    try:
        # Thử đọc JSON
        data = json.loads(text)
        
        if isinstance(data, dict):
            # 1. Lấy Nickname
            for k in ['nickname', 'name', 'username', 'user']:
                if k in data and data[k]: nickname = str(data[k]); break

            # 2. Lấy Số Ban Đầu (Before)
            # API của bạn: followers_before
            for k in ['followers_before', 'before', 'start', 'trước', 'begin']:
                if k in data and str(data[k]).isdigit(): before = int(data[k]); break

            # 3. Lấy Số Đã Tăng (Plus)
            # API của bạn: followers_increased
            for k in ['followers_increased', 'plus', 'add', 'tăng', 'increased']:
                if k in data and str(data[k]).isdigit(): plus = int(data[k]); break

            # 4. Lấy Số Hiện Tại (Current) - Để dự phòng tính toán
            # API của bạn: followers_now
            for k in ['followers_now', 'followers_total', 'current', 'now']:
                if k in data and str(data[k]).isdigit(): current = int(data[k]); break

            # === LOGIC TÍNH TOÁN ===
            # Nếu API không trả về 'plus' nhưng có 'now' và 'before' -> Tự tính
            if plus == 0 and current > before:
                plus = current - before
            
            # Nếu API trả về plus > 0 nhưng không có current -> Tự tính current
            if current == 0:
                current = before + plus

            # Chỉ trả về kết quả nếu tìm thấy ít nhất 1 thông số
            if before > 0 or plus > 0 or current > 0:
                return {
                    "nickname": clean_string(nickname), 
                    "before": before, 
                    "plus": plus,
                    "current": current
                }

    except json.JSONDecodeError:
        pass # Nếu lỗi JSON thì bỏ qua
    except Exception as e:
        logger.error(f"Parse JSON Error: {e}")

    return None

async def call_api(session, url):
    """Gọi API an toàn"""
    try:
        async with session.get(url, headers=HEADERS, ssl=False) as r:
            if r.status == 200:
                return await r.text()
    except:
        pass
    return ""

async def fetch_data_merged(username):
    """Lấy dữ liệu từ nhiều nguồn và chọn kết quả tốt nhất"""
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        tasks = [call_api(session, url.format(username)) for url in API_ENDPOINTS]
        raw_results = await asyncio.gather(*tasks)

    best_data = None

    for raw in raw_results:
        parsed = parse_data(raw)
        if parsed:
            # Logic chọn: Lấy cái nào có số tăng (plus) lớn nhất
            if best_data is None or parsed['plus'] > best_data['plus']:
                best_data = parsed
            # Nếu plus bằng nhau thì lấy cái nào cập nhật số before mới nhất
            elif parsed['plus'] == best_data['plus'] and parsed['before'] > best_data['before']:
                best_data = parsed

    return best_data

def format_message(username, data):
    """Tạo tin nhắn hiển thị đẹp mắt"""
    time_now = datetime.now(VN_TZ).strftime("%H:%M:%S - %d/%m")
    
    # Tính toán lại tổng để chắc chắn
    total = data['before'] + data['plus']
    # Nếu API có trả về current riêng thì dùng current đó (chính xác hơn)
    if data.get('current', 0) > total:
        total = data['current']

    return (
        f"<b>🚀 HỆ THỐNG BUFF FOLLOW V5.0</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> <code>@{escape(username)}</code>\n"
        f"🏷 <b>Name:</b> {escape(data['nickname'])}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📉 <b>Gốc:</b> <code>{data['before']:,}</code>\n"
        f"📈 <b>Đã tăng:</b> <code>+{data['plus']:,}</code>\n"
        f"📊 <b>Tổng:</b> <code>{total:,}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <b>Cập nhật:</b> <code>{time_now}</code>\n"
        f"✅ <b>Trạng thái:</b> Đang chạy..."
    )

# ================== AUTO BUFF JOB ==================

async def autobuff_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    info = AUTO_BUFF.get(chat_id)
    
    if not info:
        context.job.schedule_removal()
        return

    username = info["username"]
    message_id = info["message_id"]
    last_plus = info.get("last_plus", -1)

    result = await fetch_data_merged(username)
    
    # Nếu không lấy được dữ liệu hoặc số lượng không đổi -> Bỏ qua
    if not result: return
    if result["plus"] == last_plus: return

    new_text = format_message(username, result)

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=new_text,
            parse_mode="HTML"
        )
        # Cập nhật trạng thái mới
        AUTO_BUFF[chat_id]["last_plus"] = result["plus"]
    
    except BadRequest as e:
        if "Message to edit not found" in str(e):
            # Tin nhắn bị xóa -> Dừng Auto
            context.job.schedule_removal()
            AUTO_BUFF.pop(chat_id, None)
            try: await context.bot.send_message(chat_id, f"⚠️ Tin nhắn theo dõi {username} đã bị xóa. Đã dừng Auto.")
            except: pass
    except Forbidden:
        # Bot bị kick -> Dừng Auto
        context.job.schedule_removal()
        AUTO_BUFF.pop(chat_id, None)

# ================== BOT COMMANDS ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔰 <b>MENU BUFF PRO V5.0</b>\n\n"
        "🔸 <code>/buff user</code> : Kiểm tra tiến độ ngay\n"
        "🔸 <code>/autobuff user</code> : Tự động cập nhật 15p/lần (Admin)\n"
        "🔸 <code>/checkapi user</code> : Xem dữ liệu thô (Debug)\n"
        "🔸 <code>/stopbuff</code> : Dừng chạy tự động",
        parse_mode="HTML"
    )

async def checkapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh Debug để xem API trả về cái gì"""
    if not context.args: return await update.message.reply_text("❌ Nhập: /checkapi username")
    
    username = context.args[0].replace("@", "")
    msg = await update.message.reply_text("🔍 Đang quét API...", parse_mode="HTML")
    
    log_text = ""
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        for i, url in enumerate(API_ENDPOINTS):
            raw = await call_api(session, url.format(username))
            status = "✅ 200 OK" if raw else "❌ Error/Empty"
            preview = (raw[:150] + "...") if len(raw) > 150 else raw
            log_text += f"<b>API {i+1}:</b> {status}\n<code>{escape(preview)}</code>\n\n"
            
    await msg.edit_text(f"📡 <b>DỮ LIỆU GỐC:</b>\n{log_text}", parse_mode="HTML")

async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("❌ Nhập: <code>/buff username</code>", parse_mode="HTML")
    
    username = context.args[0].replace("@", "")
    msg = await update.message.reply_text("⏳ <i>Đang tải dữ liệu...</i>", parse_mode="HTML")
    
    result = await fetch_data_merged(username)
    
    if not result:
        return await msg.edit_text("⚠️ <b>Không tìm thấy dữ liệu!</b>\nKiểm tra lại User hoặc API.", parse_mode="HTML")

    await msg.edit_text(format_message(username, result), parse_mode="HTML")

async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return await update.message.reply_text("🔒 Chỉ Admin mới được dùng Auto.")
        
    if not context.args:
        return await update.message.reply_text("❌ Nhập: <code>/autobuff username</code>", parse_mode="HTML")

    chat_id = update.effective_chat.id
    username = context.args[0].replace("@", "")

    # Xóa job cũ nếu có
    for job in context.job_queue.get_jobs_by_name(str(chat_id)):
        job.schedule_removal()

    msg = await update.message.reply_text(
        f"✅ <b>Đã kích hoạt Auto Buff!</b>\n👤 User: <code>{username}</code>\n⏱ Cập nhật: 15 phút/lần",
        parse_mode="HTML"
    )
    
    # Lưu info
    AUTO_BUFF[chat_id] = {"username": username, "message_id": msg.message_id, "last_plus": -1}
    
    # Set Job: 900s = 15 phút. first=10s
    context.job_queue.run_repeating(autobuff_job, interval=900, first=10, chat_id=chat_id, name=str(chat_id))

async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS: return
    
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    
    if jobs:
        for job in jobs: job.schedule_removal()
        AUTO_BUFF.pop(chat_id, None)
        await update.message.reply_text("🛑 <b>Đã dừng Auto Buff.</b>", parse_mode="HTML")
    else:
        await update.message.reply_text("⚠️ Không có tiến trình nào đang chạy.")

# ================== MAIN ==================
def main():
    if "TOKEN_CUA_BAN" in BOT_TOKEN:
        print("❌ LỖI: CHƯA NHẬP BOT TOKEN!")
        return

    keep_alive() # Chạy Web Server
    print("🚀 Bot đang chạy...")
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("stopbuff", stopbuff))
    app.add_handler(CommandHandler("checkapi", checkapi))

    app.run_polling()

if __name__ == "__main__":
    main()
