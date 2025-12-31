import os
import json
import logging
import asyncio
import aiohttp
import pytz
from datetime import datetime
from html import escape

# Thư viện Telegram
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Application
from telegram.error import BadRequest

# Import server ảo để treo bot
from keep_alive import keep_alive

# ========================================================
# 1. CẤU HÌNH HỆ THỐNG (CONFIG)
# ========================================================
CONFIG = {
    "BOT_TOKEN": "8080338995:AAGJcUCZvBaLSjgHJfjpiWK6a-xFBa4TCEU",
    "ADMINS": [5736655322],
    "API_URLS": [
        "https://abcdxyz310107.x10.mx/apifl.php?fl1={}",
        "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"
    ],
    "INTERVAL": 900,  # Quét mỗi 15 phút
    "DB_FILE": "buff_database.json"
}

# Thiết lập múi giờ Việt Nam
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# Biến toàn cục lưu trữ tiến trình buff
AUTO_DB = {}

# Cấu hình log để theo dõi lỗi
logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

# ========================================================
# 2. CÁC HÀM XỬ LÝ DỮ LIỆU (DATABASE & API)
# ========================================================

def load_database():
    """Tải dữ liệu từ file JSON vào bộ nhớ"""
    global AUTO_DB
    if os.path.exists(CONFIG["DB_FILE"]):
        try:
            with open(CONFIG["DB_FILE"], 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Chuyển ID chat từ chuỗi sang số nguyên
                AUTO_DB = {int(k): v for k, v in data.items()}
        except Exception as e:
            print(f"Lỗi khi tải DB: {e}")

def save_database():
    """Lưu dữ liệu hiện tại vào file JSON"""
    try:
        with open(CONFIG["DB_FILE"], 'w', encoding='utf-8') as f:
            json.dump(AUTO_DB, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Lỗi khi lưu DB: {e}")

async def call_api(session, url):
    """Gửi yêu cầu đến một API đơn lẻ"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with session.get(url, headers=headers, timeout=36, ssl=False) as response:
            if response.status == 200:
                return await response.text()
    except:
        return None

async def fetch_best_data(username):
    """Quét tất cả API và trả về kết quả tốt nhất"""
    async with aiohttp.ClientSession() as session:
        # Chuẩn bị danh sách các task gọi API
        tasks = []
        for url_template in CONFIG["API_URLS"]:
            url = url_template.format(username)
            tasks.append(call_api(session, url))
        
        # Chạy tất cả task song song
        responses = await asyncio.gather(*tasks)
        
        valid_results = []
        status_code = "OK"

        for text in responses:
            if not text: continue
            
            # Kiểm tra nếu API phản hồi lỗi delay (15p, 36p...)
            delay_keywords = ["wait", "delay", "minutes", "thử lại", "đợi"]
            if any(kw in text.lower() for kw in delay_keywords):
                status_code = "DELAY"
                continue
            
            try:
                data = json.loads(text)
                valid_results.append({
                    "before": int(data.get('followers_before', 0)),
                    "plus": int(data.get('followers_increased', 0)),
                    "nickname": data.get('nickname', 'N/A'),
                    "now": int(data.get('followers_now', 0))
                })
            except:
                continue

        if valid_results:
            # Trả về kết quả có số lượng tăng cao nhất
            best = max(valid_results, key=lambda x: x['plus'])
            return best, "OK"
        
        return None, status_code

# ========================================================
# 3. CÁC LỆNH CỦA BOT (COMMAND HANDLERS)
# ========================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /start"""
    msg = (
        "🤖 <b>HỆ THỐNG THEO DÕI BUFF FOLLOW</b>\n\n"
        "Sử dụng các lệnh sau:\n"
        "1. /buff [username] - Kiểm tra nhanh số liệu\n"
        "2. /autobuff [username] - Bật tự động nhắn tin khi tăng\n"
        "3. /stopbuff - Tắt chế độ tự động"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def buff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /buff để kiểm tra thủ công"""
    if not context.args:
        await update.message.reply_text("❌ Vui lòng nhập Username!")
        return

    username = context.args[0].replace("@", "")
    temp_msg = await update.message.reply_text("🔍 Đang truy vấn API...")

    data, status = await fetch_best_data(username)
    time_str = datetime.now(VN_TZ).strftime("%H:%M:%S")

    if data:
        total = max(data['before'] + data['plus'], data['now'])
        res_text = (
            f"<b>📊 KẾT QUẢ KIỂM TRA</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User:</b> @{escape(username)}\n"
            f"🏷 <b>Tên:</b> {escape(data['nickname'])}\n"
            f"📉 <b>Gốc:</b> {data['before']:,}\n"
            f"📈 <b>Tăng:</b> +{data['plus']:,}\n"
            f"📊 <b>Tổng:</b> {total:,}\n"
            f"🕒 <b>Lúc:</b> {time_str}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        await temp_msg.edit_text(res_text, parse_mode="HTML")
    else:
        await temp_msg.edit_text(f"⚠️ API phản hồi: {status}")

async def autobuff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /autobuff để bật tự động"""
    user_id = update.effective_user.id
    if user_id not in CONFIG["ADMINS"]:
        await update.message.reply_text("❌ Bạn không có quyền Admin!")
        return

    if not context.args:
        await update.message.reply_text("❌ Cú pháp: /autobuff [username]")
        return

    username = context.args[0].replace("@", "")
    chat_id = update.effective_chat.id

    # Hủy các tiến trình cũ tại chat này nếu có
    existing_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in existing_jobs:
        job.schedule_removal()

    # Lưu thông tin vào bộ nhớ và file
    AUTO_DB[chat_id] = {
        "username": username,
        "last_plus": -1,
        "is_waiting": False
    }
    save_database()

    # Thiết lập vòng lặp quét tự động
    context.job_queue.run_repeating(
        autobuff_task,
        interval=CONFIG["INTERVAL"],
        first=5,
        chat_id=chat_id,
        name=str(chat_id)
    )

    await update.message.reply_text(f"✅ Đã bật Auto cho @{username}\nChu kỳ: 15 phút/lần.")

async def stopbuff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /stopbuff để dừng tự động"""
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    
    if jobs:
        for job in jobs:
            job.schedule_removal()
        if chat_id in AUTO_DB:
            del AUTO_DB[chat_id]
        save_database()
        await update.message.reply_text("🛑 Đã dừng toàn bộ tiến trình Auto.")
    else:
        await update.message.reply_text("⚠️ Hiện không có tiến trình nào đang chạy.")

# ========================================================
# 4. TIẾN TRÌNH CHẠY NGẦM (JOB TASK)
# ========================================================

async def autobuff_task(context: ContextTypes.DEFAULT_TYPE):
    """Hàm này sẽ được gọi mỗi 15 phút bởi Job Queue"""
    chat_id = context.job.chat_id
    if chat_id not in AUTO_DB:
        return

    info = AUTO_DB[chat_id]
    username = info["username"]
    
    data, status = await fetch_best_data(username)
    time_now = datetime.now(VN_TZ).strftime("%H:%M:%S")

    # Xử lý khi API bắt đợi (Delay 36p hoặc 15p)
    if status == "DELAY":
        if not info.get("is_waiting"):
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⏳ <b>API Delay:</b> Hệ thống @{username} đang bắt chờ. Bot sẽ tự thử lại sau.",
                parse_mode="HTML"
            )
            AUTO_DB[chat_id]["is_waiting"] = True
        return

    # Nếu có dữ liệu và số lượng tăng lớn hơn lần trước
    if data and data["plus"] > info.get("last_plus", -1):
        total = max(data['before'] + data['plus'], data['now'])
        msg = (
            f"<b>🔔 THÔNG BÁO TỰ ĐỘNG</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User:</b> @{escape(username)}\n"
            f"📈 <b>Tăng thêm:</b> +{data['plus']:,}\n"
            f"📊 <b>Tổng:</b> {total:,}\n"
            f"🕒 <b>Lúc:</b> {time_now}\n"
            f"✅ <i>Tiếp tục theo dõi...</i>"
        )
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
        
        # Cập nhật dữ liệu mới nhất
        AUTO_DB[chat_id]["last_plus"] = data["plus"]
        AUTO_DB[chat_id]["is_waiting"] = False
        save_database()

# ========================================================
# 5. KHỞI CHẠY BOT
# ========================================================

async def on_startup(application: Application):
    """Hàm chạy khi bot vừa bật lên để khôi phục tiến trình"""
    load_database()
    for chat_id, info in AUTO_DB.items():
        application.job_queue.run_repeating(
            autobuff_task,
            interval=CONFIG["INTERVAL"],
            first=10,
            chat_id=chat_id,
            name=str(chat_id)
        )
    print(">>> Hệ thống đã khôi phục các tác vụ cũ.")

def main():
    # 1. Chạy server giữ bot sống
    keep_alive()

    # 2. Xây dựng ứng dụng Bot
    app = ApplicationBuilder().token(CONFIG["BOT_TOKEN"]).post_init(on_startup).build()

    # 3. Đăng ký các lệnh điều khiển
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("buff", buff_command))
    app.add_handler(CommandHandler("autobuff", autobuff_command))
    app.add_handler(CommandHandler("stopbuff", stopbuff_command))

    # 4. Bắt đầu nhận tin nhắn
    print(">>> Bot đã Online và sẵn sàng!")
    app.run_polling()

if __name__ == "__main__":
    main()
