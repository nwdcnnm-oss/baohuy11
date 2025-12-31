import os
import json
import logging
import asyncio
import aiohttp
import pytz
from datetime import datetime
from html import escape

# Thư viện Telegram chính thức
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Application
from telegram.error import BadRequest

# Tích hợp công cụ duy trì server
from keep_alive import keep_alive

# ========================================================
# 1. CẤU HÌNH HỆ THỐNG
# ========================================================
CONFIG = {
    "BOT_TOKEN": "8080338995:AAGJcUCZvBaLSjgHJfjpiWK6a-xFBa4TCEU",
    "ADMINS": [5736655322],
    "API_URLS": [
        "https://abcdxyz310107.x10.mx/apifl.php?fl1={}",
        "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"
    ],
    "INTERVAL": 900,  # 15 phút quét một lần
    "DB_FILE": "buff_database.json" # File lưu trữ tiến trình
}

# Thiết lập múi giờ Việt Nam để báo cáo thời gian chính xác
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# Biến lưu trữ dữ liệu trong bộ nhớ RAM
AUTO_DB = {}

# Cấu hình Logging để Admin theo dõi lỗi qua Console
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ========================================================
# 2. HÀM QUẢN LÝ DỮ LIỆU (DATABASE)
# ========================================================

def load_data():
    """Tải dữ liệu từ file vào Bot khi khởi động"""
    global AUTO_DB
    if os.path.exists(CONFIG["DB_FILE"]):
        try:
            with open(CONFIG["DB_FILE"], 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                # Chuyển đổi Key từ chuỗi sang số nguyên (Chat ID)
                AUTO_DB = {int(k): v for k, v in raw_data.items()}
            logging.info(f"Đã khôi phục {len(AUTO_DB)} tiến trình từ Database.")
        except Exception as e:
            logging.error(f"Lỗi nạp Database: {e}")

def save_data():
    """Lưu dữ liệu từ RAM vào file để tránh mất khi reset"""
    try:
        with open(CONFIG["DB_FILE"], 'w', encoding='utf-8') as f:
            json.dump(AUTO_DB, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Lỗi lưu Database: {e}")

# ========================================================
# 3. HÀM XỬ LÝ API (THÔNG MINH)
# ========================================================

async def fetch_api_data(username):
    """
    Quét API song song. 
    Xử lý thông minh lỗi 'OK' ảo và lỗi 'Delay 36p'.
    """
    async with aiohttp.ClientSession() as session:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        tasks = []
        for url in CONFIG["API_URLS"]:
            tasks.append(session.get(url.format(username), headers=headers, timeout=25, ssl=False))
        
        # Chạy tất cả API cùng lúc để lấy kết quả nhanh nhất
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = []
        status_reason = "KHÔNG XÁC ĐỊNH"

        for res in responses:
            if isinstance(res, Exception): continue
            
            try:
                content = await res.text()
                
                # CHẶN LỖI API BÁO OK ẢO
                if content.strip().upper() == "OK":
                    status_reason = "API CHƯA TRẢ KẾT QUẢ (CHỈ BÁO OK)"
                    continue

                # NHẬN DIỆN LỖI DELAY (36P HOẶC 15P)
                delay_words = ["wait", "delay", "minutes", "đợi", "thử lại"]
                if any(word in content.lower() for word in delay_words):
                    status_reason = "API ĐANG BẬN (DELAY 15-36 PHÚT)"
                    continue

                # PHÂN TÍCH DỮ LIỆU JSON
                data = json.loads(content)
                if 'followers_before' in data and 'followers_increased' in data:
                    valid_results.append({
                        "before": int(data.get('followers_before', 0)),
                        "plus": int(data.get('followers_increased', 0)),
                        "name": data.get('nickname', 'N/A'),
                        "now": int(data.get('followers_now', 0))
                    })
                else:
                    status_reason = "CẤU TRÚC JSON SAI"
            except:
                status_reason = "LỖI PHÂN TÍCH JSON"

        if valid_results:
            # Lấy kết quả tốt nhất (có số tăng cao nhất)
            return max(valid_results, key=lambda x: x['plus']), "SUCCESS"
        
        return None, status_reason

# ========================================================
# 4. CÁC LỆNH ĐIỀU KHIỂN BOT
# ========================================================

async def cmd_buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /buff: Kiểm tra nhanh số liệu hiện tại"""
    if not context.args:
        await update.message.reply_text("⚠️ Cú pháp: <code>/buff username</code>", parse_mode="HTML")
        return

    user = context.args[0].replace("@", "")
    processing_msg = await update.message.reply_text(f"⏳ Đang kiểm tra @{user}...")

    data, status = await fetch_api_data(user)
    time_now = datetime.now(VN_TZ).strftime("%H:%M:%S")

    if data:
        total = max(data['before'] + data['plus'], data['now'])
        msg = (
            f"<b>📊 KẾT QUẢ KIỂM TRA</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User:</b> @{escape(user)}\n"
            f"🏷 <b>Tên:</b> {escape(data['name'])}\n"
            f"📉 <b>Gốc:</b> {data['before']:,}\n"
            f"📈 <b>Tăng:</b> +{data['plus']:,}\n"
            f"📊 <b>Tổng:</b> {total:,}\n"
            f"🕒 <b>Lúc:</b> {time_now}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        await processing_msg.edit_text(msg, parse_mode="HTML")
    else:
        await processing_msg.edit_text(f"❌ <b>Lỗi:</b> {status}", parse_mode="HTML")

async def autobuff_job_task(context: ContextTypes.DEFAULT_TYPE):
    """Tiến trình chạy ngầm: Tự động nhắn tin khi có follow mới"""
    chat_id = context.job.chat_id
    if chat_id not in AUTO_DB: return
    
    user_info = AUTO_DB[chat_id]
    username = user_info["username"]
    
    data, status = await fetch_api_data(username)
    
    if data:
        # CHỈ GỬI TIN NHẮN NẾU SỐ FOLLOW TĂNG THÊM SO VỚI LẦN TRƯỚC
        if data["plus"] > user_info.get("last_plus", -1):
            total = max(data['before'] + data['plus'], data['now'])
            time_now = datetime.now(VN_TZ).strftime("%H:%M:%S")
            
            report = (
                f"<b>🔔 THÔNG BÁO TỰ ĐỘNG</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>User:</b> @{escape(username)}\n"
                f"📈 <b>Tăng thêm:</b> +{data['plus']:,}\n"
                f"📊 <b>Tổng hiện tại:</b> {total:,}\n"
                f"🕒 <b>Cập nhật lúc:</b> {time_now}\n"
                f"✅ <i>Vẫn đang tiếp tục theo dõi...</i>"
            )
            await context.bot.send_message(chat_id=chat_id, text=report, parse_mode="HTML")
            
            # Cập nhật mốc tăng mới nhất vào DB
            AUTO_DB[chat_id]["last_plus"] = data["plus"]
            save_data()

async def cmd_autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /autobuff: Bật theo dõi tự động mỗi 15 phút"""
    if update.effective_user.id not in CONFIG["ADMINS"]:
        await update.message.reply_text("❌ Bạn không có quyền Admin!")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Cú pháp: <code>/autobuff username</code>", parse_mode="HTML")
        return

    user = context.args[0].replace("@", "")
    chat_id = update.effective_chat.id

    # Hủy bỏ Job cũ nếu đang chạy ở chat này
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs:
        job.schedule_removal()

    # Khởi tạo dữ liệu mới
    AUTO_DB[chat_id] = {"username": user, "last_plus": -1}
    save_data()

    # Bắt đầu vòng lặp 15 phút
    context.job_queue.run_repeating(
        autobuff_job_task, 
        interval=CONFIG["INTERVAL"], 
        first=5, 
        chat_id=chat_id, 
        name=str(chat_id)
    )

    await update.message.reply_text(
        f"✅ <b>ĐÃ BẬT AUTO BUFF</b>\n"
        f"👤 Mục tiêu: @{user}\n"
        f"⏱ Chu kỳ: 15 phút/lần.\n"
        f"💬 Bot sẽ nhắn tin mới khi phát hiện có follow tăng thêm.",
        parse_mode="HTML"
    )

async def cmd_stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /stopbuff: Dừng toàn bộ tiến trình auto"""
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    
    if jobs:
        for job in jobs: job.schedule_removal()
        if chat_id in AUTO_DB: del AUTO_DB[chat_id]
        save_data()
        await update.message.reply_text("🛑 Đã dừng và xóa dữ liệu theo dõi tự động.")
    else:
        await update.message.reply_text("⚠️ Không có tiến trình nào đang chạy.")

# ========================================================
# 5. KHỞI CHẠY (MAIN)
# ========================================================

async def post_init_setup(application: Application):
    """Hàm này tự chạy khi Bot vừa bật nguồn để khôi phục các Job cũ"""
    load_data()
    for chat_id, info in AUTO_DB.items():
        application.job_queue.run_repeating(
            autobuff_job_task, 
            interval=CONFIG["INTERVAL"], 
            first=10, 
            chat_id=chat_id, 
            name=str(chat_id)
        )
    logging.info("Hệ thống khôi phục hoàn tất.")

def main():
    # Kích hoạt Web Server duy trì sự sống
    keep_alive()

    # Xây dựng ứng dụng Bot với khả năng khôi phục (post_init)
    app = ApplicationBuilder().token(CONFIG["BOT_TOKEN"]).post_init(post_init_setup).build()

    # Đăng ký các lệnh điều hướng
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Bot Buff Follow Online!")))
    app.add_handler(CommandHandler("buff", cmd_buff))
    app.add_handler(CommandHandler("autobuff", cmd_autobuff))
    app.add_handler(CommandHandler("stopbuff", cmd_stopbuff))

    logging.info("Bot đang bắt đầu nhận lệnh...")
    app.run_polling()

if __name__ == "__main__":
    main()
