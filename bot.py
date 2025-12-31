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

# Kết nối file duy trì sự sống
try:
    from keep_alive import keep_alive
except ImportError:
    def keep_alive(): pass

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
    "INTERVAL": 900,  # 15 phút quét một lần
    "DB_FILE": "full_buff_data.json"
}

VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Biến lưu trữ tiến trình buff
AUTO_DB = {}

# ========================================================
# 2. HÀM XỬ LÝ DỮ LIỆU & API
# ========================================================

def save_db():
    """Lưu dữ liệu vào file để không mất khi Bot reset"""
    try:
        with open(CONFIG["DB_FILE"], 'w', encoding='utf-8') as f:
            json.dump(AUTO_DB, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Lỗi lưu file DB: {e}")

def load_db():
    """Tải dữ liệu từ file khi Bot khởi động"""
    global AUTO_DB
    if os.path.exists(CONFIG["DB_FILE"]):
        try:
            with open(CONFIG["DB_FILE"], 'r', encoding='utf-8') as f:
                data = json.load(f)
                AUTO_DB = {int(k): v for k, v in data.items()}
        except Exception as e:
            logging.error(f"Lỗi nạp file DB: {e}")

async def fetch_best_data(username):
    """Quét API, xử lý lỗi Delay 36p và phản hồi rác"""
    async with aiohttp.ClientSession() as session:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        tasks = [session.get(url.format(username), headers=headers, timeout=30, ssl=False) for url in CONFIG["API_URLS"]]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        results = []
        is_delay = False

        for res in responses:
            if isinstance(res, Exception): continue
            try:
                text = await res.text()
                # Phát hiện API bắt chờ (Delay)
                if any(kw in text.lower() for kw in ["wait", "delay", "minutes", "đợi", "thử lại"]):
                    is_delay = True
                    continue
                
                # Ép kiểu JSON và kiểm tra dữ liệu
                data = json.loads(text)
                if 'followers_before' in data:
                    results.append({
                        "before": int(data.get('followers_before', 0)),
                        "plus": int(data.get('followers_increased', 0)),
                        "nickname": data.get('nickname', 'N/A'),
                        "now": int(data.get('followers_now', 0))
                    })
            except: continue

        if results:
            return max(results, key=lambda x: x['plus']), "SUCCESS"
        return None, "DELAY" if is_delay else "API_ERROR"

# ========================================================
# 3. TIẾN TRÌNH CHẠY NGẦM (JOB QUEUE)
# ========================================================

async def autobuff_task(context: ContextTypes.DEFAULT_TYPE):
    """Nhiệm vụ quét định kỳ: Chỉ nhắn tin khi có follow tăng"""
    chat_id = context.job.chat_id
    if chat_id not in AUTO_DB: return
    
    user_info = AUTO_DB[chat_id]
    username = user_info["username"]
    
    data, status = await fetch_best_data(username)
    
    if data:
        # Kiểm tra nếu số follow tăng mới thực sự lớn hơn mốc đã lưu
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
            await context.bot.send_message(chat_id=chat_id, text=report, parse_mode="HTML")
            
            # Cập nhật mốc mới nhất
            AUTO_DB[chat_id]["last_plus"] = data["plus"]
            save_db()

# ========================================================
# 4. LỆNH ĐIỀU KHIỂN (COMMANDS)
# ========================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>🤖 BOT BUFF FOLLOW V6.0 (RENDER FIX)</b>\n\n"
        "🔸 <code>/buff [user]</code> : Kiểm tra nhanh\n"
        "🔸 <code>/autobuff [user]</code> : Chạy tự động 15p\n"
        "🔸 <code>/stopbuff</code> : Dừng tiến trình",
        parse_mode="HTML"
    )

async def cmd_buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("❌ Nhập Username!")
    
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
        await m.edit_text(f"⚠️ API Phản hồi: <b>{status}</b> (Thử lại sau)", parse_mode="HTML")

async def cmd_autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in CONFIG["ADMINS"]: return
    if not context.args: return await update.message.reply_text("❌ Cú pháp: /autobuff [user]")
    
    user = context.args[0].replace("@", "")
    chat_id = update.effective_chat.id
    
    # Dọn dẹp tiến trình cũ
    for j in context.job_queue.get_jobs_by_name(str(chat_id)): j.schedule_removal()
    
    AUTO_DB[chat_id] = {"username": user, "last_plus": -1}
    save_db()
    
    context.job_queue.run_repeating(autobuff_task, interval=CONFIG["INTERVAL"], first=5, chat_id=chat_id, name=str(chat_id))
    await update.message.reply_text(f"✅ <b>ĐÃ BẬT AUTO</b>\n👤 User: @{user}\n⏱ Chu kỳ: 15 phút.", parse_mode="HTML")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if jobs:
        for j in jobs: j.schedule_removal()
        if chat_id in AUTO_DB: del AUTO_DB[chat_id]
        save_db()
        await update.message.reply_text("🛑 Đã dừng toàn bộ tiến trình Auto.")

# ========================================================
# 5. KHỞI CHẠY (POST-INIT)
# ========================================================

async def post_init(application: Application):
    """Khôi phục lại toàn bộ Job khi Bot bật lên"""
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
    keep_alive() # Chạy server web duy trì sống
    
    app = ApplicationBuilder().token(CONFIG["BOT_TOKEN"]).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("buff", cmd_buff))
    app.add_handler(CommandHandler("autobuff", cmd_autobuff))
    app.add_handler(CommandHandler("stopbuff", cmd_stop))
    
    print("🚀 Bot is Online...")
    app.run_polling()

if __name__ == "__main__":
    main()
