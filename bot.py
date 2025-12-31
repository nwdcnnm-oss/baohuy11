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
    # 👇 Thay Token Bot của bạn vào đây
    "BOT_TOKEN": "8080338995:AAGJcUCZvBaLSjgHJfjpiWK6a-xFBa4TCEU",
    
    # 👇 Thay ID Telegram của bạn vào đây (Dùng @userinfobot để lấy)
    "ADMINS": [5736655322],
    
    # 👇 Danh sách API Buff
    "API_URLS": [
        "https://abcdxyz310107.x10.mx/apifl.php?fl1={}",
        "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"
    ],
    
    "INTERVAL": 900, # Thời gian quét lại (900 giây = 15 phút)
    "DB_FILE": "database.json"
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# Logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Biến lưu trữ dữ liệu
AUTO_DB = {}

# ================== MODULE HỆ THỐNG ==================

def save_database():
    try:
        with open(CONFIG["DB_FILE"], 'w', encoding='utf-8') as f:
            json.dump(AUTO_DB, f, ensure_ascii=False, indent=4)
    except Exception as e: logger.error(f"Lỗi lưu file: {e}")

def load_database():
    global AUTO_DB
    if os.path.exists(CONFIG["DB_FILE"]):
        try:
            with open(CONFIG["DB_FILE"], 'r', encoding='utf-8') as f:
                data = json.load(f)
                AUTO_DB = {int(k): v for k, v in data.items()}
            print(f"✅ Đã tải {len(AUTO_DB)} tiến trình từ database.")
        except: AUTO_DB = {}

# ================== XỬ LÝ API (NHẬN DIỆN CHỜ 15P) ==================

async def fetch_stats(username):
    """Lấy dữ liệu và kiểm tra trạng thái API"""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        for url_template in CONFIG["API_URLS"]:
            try:
                url = url_template.format(username)
                async with session.get(url, headers=HEADERS, ssl=False) as res:
                    text = await res.text()
                    
                    # 1. Kiểm tra nếu API bắt chờ 15 phút
                    wait_keywords = ["15 minutes", "wait", "đợi", "chậm lại", "thử lại sau", "slow down"]
                    if any(kw in text.lower() for kw in wait_keywords):
                        return None, "WAITING"

                    # 2. Parse dữ liệu JSON
                    data = json.loads(text)
                    if isinstance(data, dict):
                        before = int(data.get('followers_before', 0))
                        plus = int(data.get('followers_increased', 0))
                        nickname = data.get('nickname', 'Unknown')
                        current = data.get('followers_now', before + plus)
                        return {
                            "before": before, 
                            "plus": plus, 
                            "nickname": nickname, 
                            "current": current
                        }, "OK"
            except: continue
    return None, "ERROR"

# ================== TIẾN TRÌNH CHẠY NGẦM (JOB) ==================

async def autobuff_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    if chat_id not in AUTO_DB:
        context.job.schedule_removal()
        return

    info = AUTO_DB[chat_id]
    username = info["username"]
    message_id = info["message_id"]
    
    data, status = await fetch_stats(username)
    time_now = datetime.now(VN_TZ).strftime("%H:%M:%S - %d/%m")

    try:
        if status == "WAITING":
            text = (
                f"<b>🚀 HỆ THỐNG AUTO BUFF</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👤 User: <code>@{escape(username)}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"⏳ <b>Trạng thái:</b> <code>Chờ API nghỉ 15p...</code>\n"
                f"🕒 Lần quét cuối: <code>{time_now}</code>\n"
                f"📢 <i>Bot sẽ tự động thử lại sau mỗi 15p.</i>"
            )
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode="HTML")
            return

        if status == "OK" and data:
            # Chỉ cập nhật tin nhắn nếu số Follow có thay đổi
            if data["plus"] != info.get("last_plus"):
                total = max(data["before"] + data["plus"], data["current"])
                msg = (
                    f"<b>🚀 THEO DÕI TIẾN ĐỘ VIP</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>User:</b> <code>@{escape(username)}</code>\n"
                    f"🏷 <b>Name:</b> {escape(data['nickname'])}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📉 <b>Gốc:</b> <code>{data['before']:,}</code>\n"
                    f"📈 <b>Tăng:</b> <code>+{data['plus']:,}</code>\n"
                    f"📊 <b>Tổng:</b> <code>{total:,}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🕒 <b>Cập nhật:</b> <code>{time_now}</code>\n"
                    f"✅ <b>Trạng thái:</b> Hoạt động ⚡️"
                )
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=msg, parse_mode="HTML")
                
                # Lưu trạng thái mới
                AUTO_DB[chat_id]["last_plus"] = data["plus"]
                save_database()
    except BadRequest as e:
        if "Message to edit not found" in str(e):
            context.job.schedule_removal()
            del AUTO_DB[chat_id]
            save_database()

# ================== CÁC LỆNH ĐIỀU KHIỂN ==================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔰 <b>HỆ THỐNG BUFF FOLLOW V5.0</b>\n\n"
        "🔸 <code>/autobuff user</code> : Bật tự động (Admin)\n"
        "🔸 <code>/stopbuff</code> : Dừng theo dõi\n"
        "🔸 <code>/buff user</code> : Kiểm tra nhanh\n"
        "🔸 <code>/checkapi user</code> : Debug dữ liệu",
        parse_mode="HTML"
    )

async def cmd_autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if user_id not in CONFIG["ADMINS"]:
        return await update.message.reply_text(f"❌ Bạn không phải Admin (ID: {user_id})")

    if not context.args:
        return await update.message.reply_text("❌ Vui lòng nhập Username. VD: <code>/autobuff nguyenvana</code>", parse_mode="HTML")

    username = context.args[0].replace("@", "")
    
    # Xóa Job cũ nếu đang chạy ở chat này
    for job in context.job_queue.get_jobs_by_name(str(chat_id)): job.schedule_removal()

    msg = await update.message.reply_text(f"⏳ Đang kết nối API cho <code>{username}</code>...", parse_mode="HTML")
    
    # Lưu vào database
    AUTO_DB[chat_id] = {"username": username, "message_id": msg.message_id, "last_plus": -1}
    save_database()

    # Kích hoạt vòng lặp 15 phút
    context.job_queue.run_repeating(autobuff_job, interval=CONFIG["INTERVAL"], first=5, chat_id=chat_id, name=str(chat_id))
    
    await msg.edit_text(f"✅ <b>Đã kích hoạt Auto!</b>\n👤 User: <code>{username}</code>\n⏱ Cập nhật: 15 phút/lần.", parse_mode="HTML")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    
    if jobs:
        for job in jobs: job.schedule_removal()
        if chat_id in AUTO_DB: del AUTO_DB[chat_id]
        save_database()
        await update.message.reply_text("🛑 Đã dừng toàn bộ tiến trình Auto.")
    else:
        await update.message.reply_text("⚠️ Không có tiến trình nào đang chạy.")

async def cmd_buff_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    username = context.args[0].replace("@", "")
    msg = await update.message.reply_text("⏳ Đang check...")
    data, status = await fetch_stats(username)
    if data:
        from datetime import datetime
        time_now = datetime.now(VN_TZ).strftime("%H:%M:%S")
        total = data["before"] + data["plus"]
        await msg.edit_text(
            f"👤 User: {username}\n📉 Gốc: {data['before']:,}\n📈 Tăng: +{data['plus']:,}\n📊 Tổng: {total:,}\n🕒 Lúc: {time_now}",
            parse_mode="HTML"
        )
    else:
        await msg.edit_text(f"❌ API báo: {status}")

# ================== KHỞI ĐỘNG (RESTART LOGIC) ==================

async def post_init(application: Application):
    """Tự động chạy lại các Job cũ sau khi bot restart"""
    load_database()
    for chat_id, info in AUTO_DB.items():
        application.job_queue.run_repeating(
            autobuff_job, 
            interval=CONFIG["INTERVAL"], 
            first=10, 
            chat_id=chat_id, 
            name=str(chat_id)
        )
    print("♻️ Hệ thống đã khôi phục các tiến trình Auto cũ.")

def main():
    if "TOKEN" in CONFIG["BOT_TOKEN"]:
        print("❌ LỖI: Chưa nhập BOT_TOKEN!")
        return

    # Khởi tạo Application
    app = ApplicationBuilder().token(CONFIG["BOT_TOKEN"]).post_init(post_init).build()

    # Đăng ký lệnh
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("autobuff", cmd_autobuff))
    app.add_handler(CommandHandler("stopbuff", cmd_stop))
    app.add_handler(CommandHandler("buff", cmd_buff_manual))

    print("🚀 Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
