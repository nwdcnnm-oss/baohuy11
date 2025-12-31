import os
import json
import logging
import asyncio
import aiohttp
import sqlite3
import pytz
from datetime import datetime
from html import escape

# Thư viện Telegram
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Application
from telegram.error import BadRequest

# Kết nối file duy trì sự sống
try:
    from keep_alive import keep_alive
except ImportError:
    def keep_alive(): pass

# ========================================================
# 1. CẤU HÌNH HỆ THỐNG (CONFIG)
# ========================================================
CONFIG = {
    "BOT_TOKEN": os.getenv('8080338995:AAFXhz1kjZsZlE3KUP_FCTis6bF3j0PIAKU'),
    "ADMINS": [5736655322],  # Thêm ID của Admin ở đây
    "API_URLS": [
        "https://abcdxyz310107.x10.mx/apifl.php?fl1={}",
        "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"
    ],
    "INTERVAL": 900,  # 15 phút quét một lần
    "DB_FILE": "full_buff_data.json"
}

VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

# Biến lưu trữ tiến trình buff
AUTO_DB = {}

# ========================================================
# 2. HÀM XỬ LÝ DỮ LIỆU & API
# ========================================================
def create_db():
    """ Tạo cơ sở dữ liệu SQLite nếu chưa tồn tại """
    conn = sqlite3.connect('buff_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_data
                      (chat_id INTEGER PRIMARY KEY, username TEXT, last_plus INTEGER)''')
    conn.commit()
    conn.close()

def save_db():
    """ Lưu trữ dữ liệu người dùng vào cơ sở dữ liệu """
    conn = sqlite3.connect('buff_data.db')
    cursor = conn.cursor()
    for chat_id, user_info in AUTO_DB.items():
        cursor.execute('''INSERT OR REPLACE INTO user_data (chat_id, username, last_plus) 
                          VALUES (?, ?, ?)''', (chat_id, user_info["username"], user_info["last_plus"]))
    conn.commit()
    conn.close()

def load_db():
    """ Nạp dữ liệu từ cơ sở dữ liệu SQLite """
    global AUTO_DB
    conn = sqlite3.connect('buff_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id, username, last_plus FROM user_data')
    rows = cursor.fetchall()
    for row in rows:
        AUTO_DB[row[0]] = {"username": row[1], "last_plus": row[2]}
    conn.close()

async def fetch_best_data(username):
    """ Quét API với cơ chế bắt lỗi chi tiết """
    async with aiohttp.ClientSession() as session:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        tasks = [session.get(url.format(username), headers=headers, timeout=36, ssl=False) for url in CONFIG["API_URLS"]]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        results = []
        is_delay = False

        for res in responses:
            if isinstance(res, Exception):
                logging.error(f"Lỗi kết nối API: {res}")
                continue
            
            try:
                text = await res.text()

                if not text or "<html" in text.lower():
                    logging.warning("API trả về HTML hoặc trang lỗi.")
                    continue

                if any(kw in text.lower() for kw in ["wait", "delay", "minutes", "đợi", "thử lại"]):
                    is_delay = True
                    continue
                
                # Phân tích JSON an toàn
                data = json.loads(text)
                
                if 'followers_before' in data:
                    results.append({
                        "before": int(data.get('followers_before', 0)),
                        "plus": int(data.get('followers_increased', 0)),
                        "nickname": data.get('nickname', 'N/A'),
                        "now": int(data.get('followers_now', 0))
                    })
            except json.JSONDecodeError:
                logging.error(f"Lỗi phân tích JSON từ API. Nội dung: {text[:50]}...")
                continue
            except Exception as e:
                logging.error(f"Lỗi không xác định: {e}")
                continue

        if results:
            # Ưu tiên kết quả có số lượng tăng cao nhất
            return max(results, key=lambda x: x['plus']), "SUCCESS"
        
        return None, "DELAY" if is_delay else "API_ERROR"

# ========================================================
# 3. TIẾN TRÌNH CHẠY NGẦM & COMMANDS (GIỮ NGUYÊN LOGIC CŨ)
# ========================================================
async def autobuff_task(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    if chat_id not in AUTO_DB: return
    
    user_info = AUTO_DB[chat_id]
    username = user_info["username"]
    
    data, status = await fetch_best_data(username)
    
    if data:
        if data["plus"] > user_info.get("last_plus", -1):
            total = max(data['before'] + data['plus'], data['now'])
            time_str = datetime.now(VN_TZ).strftime("%H:%M:%S")
            
            report = (
                f"<b>🔔 CẬP NHẬT TIẾN ĐỘ: @{escape(username)}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 <b>Tăng thêm:</b> <code>+{data['plus']:,}</code>\n"
                f"📊 <b>Tổng hiện tại:</b> <code>{total:,}</code>\n"
                f"🕒 <b>Cập nhật lúc:</b> {time_str}\n"
                f"✅ <i>Hệ thống vẫn đang tiếp tục...</i>"
            )
            try:
                await context.bot.send_message(chat_id=chat_id, text=report, parse_mode="HTML")
                AUTO_DB[chat_id]["last_plus"] = data["plus"]
                save_db()
            except Exception as e:
                logging.error(f"Không thể gửi tin nhắn cho {chat_id}: {e}")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🔍 Kiểm tra Follower", "🔄 Auto Buff"],
        ["❌ Dừng Auto Buff"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        "Chào bạn! Chọn một tùy chọn từ menu:",
        reply_markup=reply_markup
    )

async def cmd_buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("❌ Vui lòng nhập Username!")
    
    user = context.args[0].replace("@", "")
    m = await update.message.reply_text(f"🔍 Đang truy vấn dữ liệu @{user}...")
    
    data, status = await fetch_best_data(user)
    if data:
        total = max(data['before'] + data['plus'], data['now'])
        res = (
            f"<b>📊 KẾT QUẢ CHECK NHANH</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User:</b> @{escape(user)}\n"
            f"🏷 <b>Tên:</b> {escape(data['nickname'])}\n"
            f"📉 <b>Gốc:</b> {data['before']:,}\n"
            f"📈 <b>Tăng:</b> +{data['plus']:,}\n"
            f"📊 <b>Tổng:</b> {total:,}\n"
            f"🕒 <b>Lúc:</b> {datetime.now(VN_TZ).strftime('%H:%M:%S')}"
        )
        await m.edit_text(res, parse_mode="HTML")
    else:
        error_msg = "Máy chủ API đang bận" if status == "DELAY" else "Máy chủ API lỗi hoặc bảo trì"
        await m.edit_text(f"⚠️ <b>{status}</b>: {error_msg}. Thử lại sau ít phút.", parse_mode="HTML")

async def cmd_autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in CONFIG["ADMINS"]:
        return await update.message.reply_text("🚫 Bạn không có quyền sử dụng lệnh này.")
    
    if not context.args: 
        return await update.message.reply_text("❌ Cú pháp: /autobuff [user]")
    
    user = context.args[0].replace("@", "")
    chat_id = update.effective_chat.id
    
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs:
        job.schedule_removal()
    
    AUTO_DB[chat_id] = {"username": user, "last_plus": -1}
    save_db()
    
    context.job_queue.run_repeating(
        autobuff_task, 
        interval=CONFIG["INTERVAL"], 
        first=5, 
        chat_id=chat_id, 
        name=str(chat_id)
    )
    await update.message.reply_text(f"✅ <b>ĐÃ BẬT AUTO</b>\n👤 User: @{user}\n⏱ Chu kỳ: 15 phút.", parse_mode="HTML")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if jobs:
        for j in jobs: j.schedule_removal()
        if chat_id in AUTO_DB: del AUTO_DB[chat_id]
        save_db()
        await update.message.reply_text("🛑 Đã dừng toàn bộ tiến trình Auto.")
    else:
        await update.message.reply_text("ℹ️ Không có tiến trình nào đang chạy.")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "<b>🤖 BOT BUFF FOLLOW V6.0 (OPTIMIZED)</b>\n\n"
        "🔸 <code>/buff [user]</code>: Kiểm tra dữ liệu người dùng ngay lập tức\n"
        "🔸 <code>/autobuff [user]</code>: Bật chế độ tự động kiểm tra mỗi 15 phút\n"
        "🔸 <code>/stopbuff</code>: Dừng chế độ tự động\n"
        "🔸 <code>/help</code>: Hiển thị hướng dẫn sử dụng bot"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

# ========================================================
# 4. KHỞI CHẠY
# ========================================================
async def post_init(application: Application):
    create_db()
    load_db()
    for chat_id, info in AUTO_DB.items():
        application.job_queue.run_repeating(
            autobuff_task, 
            interval=CONFIG["INTERVAL"], 
            first=10, 
            chat_id=chat_id, 
            name=str(chat_id)
        )
    print("♻️ Đã khôi phục trạng thái hoạt động!")

def main():
    keep_alive()
    app = ApplicationBuilder().token(CONFIG["BOT_TOKEN"]).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("buff", cmd_buff))
    app.add_handler(CommandHandler("autobuff", cmd_autobuff))
    app.add_handler(CommandHandler("stopbuff", cmd_stop))
    app.add_handler(CommandHandler("help", cmd_help))
    
    print("🚀 Bot is Online...")
    app.run_polling()

if __name__ == "__main__":
    main()
