import os
import json
import logging
import asyncio
import aiohttp
import re
import pytz
from datetime import datetime
from html import escape
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Application
from telegram.error import BadRequest, Forbidden

# ================== CẤU HÌNH (CONFIG) ==================
CONFIG = {
    # 👇 Thay Token của bạn vào đây
    "BOT_TOKEN": "8080338995:AAGJcUCZvBaLSjgHJfjpiWK6a-xFBa4TCEU",
    
    # 👇 ID Admin (Người được dùng lệnh quản lý)
    "ADMINS": [5736655322],
    
    # 👇 Các nguồn API (Link dự phòng)
    "API_URLS": [
        "https://abcdxyz310107.x10.mx/apifl.php?fl1={}",
        "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"
    ],
    
    # Thời gian cập nhật auto (giây) - Mặc định 15 phút
    "INTERVAL": 900, 
    
    # File lưu dữ liệu
    "DB_FILE": "database.json"
}

# Cấu hình Web Request
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# Logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Biến toàn cục lưu dữ liệu Auto
AUTO_DB = {}

# ================== MODULE DATABASE (LƯU TRỮ) ==================

def load_database():
    """Đọc dữ liệu từ file JSON khi khởi động"""
    global AUTO_DB
    if os.path.exists(CONFIG["DB_FILE"]):
        try:
            with open(CONFIG["DB_FILE"], 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Chuyển key từ string về int (do JSON lưu key là string)
                AUTO_DB = {int(k): v for k, v in data.items()}
            logger.info(f"✅ Đã tải lại {len(AUTO_DB)} tác vụ Auto từ Database.")
        except Exception as e:
            logger.error(f"❌ Lỗi đọc Database: {e}")
            AUTO_DB = {}

def save_database():
    """Lưu dữ liệu hiện tại vào file JSON"""
    try:
        with open(CONFIG["DB_FILE"], 'w', encoding='utf-8') as f:
            json.dump(AUTO_DB, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"❌ Lỗi lưu Database: {e}")

# ================== MODULE API & XỬ LÝ SỐ LIỆU ==================

def clean_string(text):
    if not text: return "Unknown"
    return re.sub(r'[^\w\s\-\.]', '', str(text)).strip()

def parse_api_response(text):
    """Phân tích JSON thông minh"""
    if not text or len(text) < 5: return None
    try:
        data = json.loads(text)
        if not isinstance(data, dict): return None

        # Mapping các key có thể xuất hiện
        nick_keys = ['nickname', 'name', 'username', 'user']
        before_keys = ['followers_before', 'before', 'start', 'begin']
        plus_keys = ['followers_increased', 'plus', 'add', 'increased']
        curr_keys = ['followers_now', 'current', 'now', 'total']

        nickname = next((str(data[k]) for k in nick_keys if k in data and data[k]), "Unknown")
        before = next((int(data[k]) for k in before_keys if k in data and str(data[k]).isdigit()), 0)
        plus = next((int(data[k]) for k in plus_keys if k in data and str(data[k]).isdigit()), 0)
        current = next((int(data[k]) for k in curr_keys if k in data and str(data[k]).isdigit()), 0)

        # Logic Fix lỗi tính toán
        if plus == 0 and current > before: plus = current - before
        if current == 0: current = before + plus

        if before > 0 or plus > 0 or current > 0:
            return {
                "nickname": clean_string(nickname),
                "before": before,
                "plus": plus,
                "current": current
            }
    except:
        pass
    return None

async def fetch_stats(username):
    """Lấy dữ liệu từ API tốt nhất"""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        tasks = []
        for url in CONFIG["API_URLS"]:
            tasks.append(session.get(url.format(username), headers=HEADERS, ssl=False))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_data = []
        for res in results:
            if isinstance(res, aiohttp.ClientResponse) and res.status == 200:
                text = await res.text()
                parsed = parse_api_response(text)
                if parsed: valid_data.append(parsed)

    if not valid_data: return None
    # Lấy kết quả có số lượng tăng cao nhất (chính xác nhất)
    return max(valid_data, key=lambda x: x['plus'])

def make_message(username, data):
    """Tạo nội dung tin nhắn"""
    time_str = datetime.now(VN_TZ).strftime("%H:%M:%S - %d/%m")
    total = max(data['before'] + data['plus'], data['current'])
    
    return (
        f"<b>🚀 THEO DÕI TIẾN ĐỘ VIP</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> <code>@{escape(username)}</code>\n"
        f"🏷 <b>Name:</b> {escape(data['nickname'])}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📉 <b>Gốc:</b> <code>{data['before']:,}</code>\n"
        f"📈 <b>Tăng:</b> <code>+{data['plus']:,}</code>\n"
        f"📊 <b>Tổng:</b> <code>{total:,}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <b>Cập nhật:</b> <code>{time_str}</code>\n"
        f"✅ <b>Status:</b> Running..."
    )

# ================== BOT JOB QUEUE (AUTO) ==================

async def autobuff_task(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    
    # Kiểm tra xem user còn trong DB không (trường hợp bị xóa tay)
    if chat_id not in AUTO_DB:
        context.job.schedule_removal()
        return

    info = AUTO_DB[chat_id]
    username = info["username"]
    message_id = info["message_id"]
    last_plus = info.get("last_plus", -1)

    data = await fetch_stats(username)

    # Nếu không có dữ liệu hoặc số lượng không đổi -> Skip
    if not data or data["plus"] == last_plus:
        return

    new_msg = make_message(username, data)

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=new_msg,
            parse_mode="HTML"
        )
        # Cập nhật DB
        AUTO_DB[chat_id]["last_plus"] = data["plus"]
        save_database() # Lưu ngay lập tức
        
    except BadRequest as e:
        if "Message to edit not found" in str(e):
            # Tin nhắn bị xóa -> Hủy Auto
            context.job.schedule_removal()
            del AUTO_DB[chat_id]
            save_database()
            await context.bot.send_message(chat_id, f"⚠️ Đã dừng Auto {username} do tin nhắn gốc bị xóa.")
    except Forbidden:
        # Bot bị chặn -> Hủy Auto
        context.job.schedule_removal()
        if chat_id in AUTO_DB:
            del AUTO_DB[chat_id]
            save_database()

# ================== HANDLERS (LỆNH) ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔰 <b>BOT MANAGER PRO V2</b>\n\n"
        "🔹 <code>/buff user</code> : Check thủ công\n"
        "🔹 <code>/autobuff user</code> : Bật Auto (Admin)\n"
        "🔹 <code>/stopbuff</code> : Tắt Auto\n"
        "🔹 <code>/checkapi user</code> : Test API",
        parse_mode="HTML"
    )

async def checkapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("❌ Nhập: /checkapi user")
    username = context.args[0].replace("@", "")
    msg = await update.message.reply_text("🔍 Scanning...", parse_mode="HTML")
    
    report = ""
    async with aiohttp.ClientSession() as session:
        for i, url in enumerate(CONFIG["API_URLS"]):
            try:
                async with session.get(url.format(username), headers=HEADERS, ssl=False, timeout=10) as res:
                    txt = await res.text()
                    stt = "✅ 200" if res.status == 200 else f"❌ {res.status}"
                    preview = escape(txt[:100])
                    report += f"<b>API {i+1}:</b> {stt}\n<code>{preview}...</code>\n\n"
            except Exception as e:
                report += f"<b>API {i+1}:</b> ❌ Error: {str(e)}\n\n"
    
    await msg.edit_text(f"📡 <b>API DEBUG:</b>\n{report}", parse_mode="HTML")

async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("❌ Nhập: /buff user")
    username = context.args[0].replace("@", "")
    msg = await update.message.reply_text("⏳ Đang tải...", parse_mode="HTML")
    
    data = await fetch_stats(username)
    if data:
        await msg.edit_text(make_message(username, data), parse_mode="HTML")
    else:
        await msg.edit_text("⚠️ Không lấy được dữ liệu.", parse_mode="HTML")

async def cmd_autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if user_id not in CONFIG["ADMINS"]:
        return await update.message.reply_text("🔒 Lệnh dành cho Admin.")
    
    if not context.args:
        return await update.message.reply_text("❌ Nhập: /autobuff user")

    username = context.args[0].replace("@", "")
    
    # Xóa job cũ nếu có
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs: job.schedule_removal()

    msg = await update.message.reply_text(f"✅ <b>Kích hoạt Auto:</b> {username}\n⏱ Refresh: {CONFIG['INTERVAL']}s", parse_mode="HTML")
    
    # 1. Lưu vào RAM
    AUTO_DB[chat_id] = {
        "username": username,
        "message_id": msg.message_id,
        "last_plus": -1
    }
    
    # 2. Lưu vào File
    save_database()
    
    # 3. Chạy Job
    context.job_queue.run_repeating(
        autobuff_task, 
        interval=CONFIG['INTERVAL'], 
        first=10, 
        chat_id=chat_id, 
        name=str(chat_id)
    )

async def cmd_stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in CONFIG["ADMINS"]: return
    chat_id = update.effective_chat.id
    
    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if jobs:
        for job in jobs: job.schedule_removal()
        
        if chat_id in AUTO_DB:
            del AUTO_DB[chat_id]
            save_database()
            
        await update.message.reply_text("🛑 <b>Đã dừng Auto.</b>", parse_mode="HTML")
    else:
        await update.message.reply_text("⚠️ Không có tiến trình chạy.")

# ================== KHỞI ĐỘNG HỆ THỐNG ==================

async def post_init(application: Application):
    """Hàm chạy 1 lần khi bot khởi động để khôi phục Job"""
    load_database()
    if not AUTO_DB: return

    count = 0
    for chat_id, info in AUTO_DB.items():
        try:
            # Khôi phục job
            application.job_queue.run_repeating(
                autobuff_task,
                interval=CONFIG['INTERVAL'],
                first=10, # Chạy sau 10s khởi động
                chat_id=chat_id,
                name=str(chat_id)
            )
            count += 1
        except Exception as e:
            logger.error(f"Lỗi khôi phục Job ID {chat_id}: {e}")
            
    if count > 0:
        print(f"♻️ ĐÃ KHÔI PHỤC {count} TIẾN TRÌNH AUTO!")
        
        # Gửi thông báo cho Admin biết bot đã reset và chạy lại
        for admin_id in CONFIG["ADMINS"]:
            try:
                await application.bot.send_message(admin_id, f"♻️ Bot vừa khởi động lại. Đã khôi phục {count} tiến trình Auto.")
            except: pass

def main():
    if "TOKEN" in CONFIG["BOT_TOKEN"]:
        print("❌ VUI LÒNG NHẬP TOKEN TRONG PHẦN CONFIG!")
        return

    # Chạy Web Server ảo để giữ bot sống (nếu chạy trên Replit/Render)
    try:
        from keep_alive import keep_alive
        keep_alive()
    except ImportError:
        pass

    print("🚀 Bot đang khởi động...")
    
    # Build App với post_init
    app = ApplicationBuilder().token(CONFIG["BOT_TOKEN"]).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", cmd_autobuff))
    app.add_handler(CommandHandler("stopbuff", cmd_stopbuff))
    app.add_handler(CommandHandler("checkapi", checkapi))

    app.run_polling()

if __name__ == "__main__":
    main()
