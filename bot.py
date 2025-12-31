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

# Tích hợp Web Server để treo 24/7 (Cần file keep_alive.py)
try:
    from keep_alive import keep_alive
except ImportError:
    def keep_alive(): pass

# ================== CẤU HÌNH (CONFIG) ==================
CONFIG = {
    "BOT_TOKEN": "8080338995:AAGJcUCZvBaLSjgHJfjpiWK6a-xFBa4TCEU",
    "ADMINS": [5736655322],
    "API_URLS": [
        "https://abcdxyz310107.x10.mx/apifl.php?fl1={}",
        "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"
    ],
    "INTERVAL": 900, 
    "DB_FILE": "database_v5.json"
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

AUTO_DB = {}

# ================== HỆ THỐNG DATABASE ==================
def save_db():
    try:
        with open(CONFIG["DB_FILE"], 'w', encoding='utf-8') as f:
            json.dump(AUTO_DB, f, ensure_ascii=False, indent=4)
    except Exception as e: logger.error(f"Lỗi lưu DB: {e}")

def load_db():
    global AUTO_DB
    if os.path.exists(CONFIG["DB_FILE"]):
        try:
            with open(CONFIG["DB_FILE"], 'r', encoding='utf-8') as f:
                AUTO_DB = {int(k): v for k, v in json.load(f).items()}
        except: AUTO_DB = {}

# ================== XỬ LÝ API ==================
async def fetch_stats(username):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        tasks = [session.get(url.format(username), headers=HEADERS, ssl=False) for url in CONFIG["API_URLS"]]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        valid_data = []
        is_waiting = False
        for res in responses:
            if isinstance(res, aiohttp.ClientResponse) and res.status == 200:
                text = await res.text()
                if any(kw in text.lower() for kw in ["wait", "15 minutes", "đợi", "thử lại"]):
                    is_waiting = True; continue
                try:
                    d = json.loads(text)
                    valid_data.append({
                        "before": int(d.get('followers_before', 0)),
                        "plus": int(d.get('followers_increased', 0)),
                        "nickname": d.get('nickname', 'N/A'),
                        "current": int(d.get('followers_now', 0))
                    })
                except: continue
        if not valid_data: return None, ("WAITING" if is_waiting else "ERROR")
        return max(valid_data, key=lambda x: x['plus']), "OK"

# ================== LỆNH BUFF (KIỂM TRA THỦ CÔNG) ==================
async def cmd_buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("❌ Vui lòng nhập Username. VD: `/buff nguyenvana`", parse_mode="HTML")
    
    username = context.args[0].replace("@", "")
    msg_wait = await update.message.reply_text(f"🔍 Đang kiểm tra cho <code>{username}</code>...", parse_mode="HTML")
    
    data, status = await fetch_stats(username)
    time_now = datetime.now(VN_TZ).strftime("%H:%M:%S")

    if status == "OK" and data:
        total = max(data["before"] + data["plus"], data["current"])
        res_text = (
            f"<b>📊 KẾT QUẢ KIỂM TRA NHANH</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User:</b> <code>@{escape(username)}</code>\n"
            f"🏷 <b>Tên:</b> {escape(data['nickname'])}\n"
            f"📉 <b>Gốc:</b> <code>{data['before']:,}</code>\n"
            f"📈 <b>Tăng:</b> <code>+{data['plus']:,}</code>\n"
            f"📊 <b>Tổng:</b> <code>{total:,}</code>\n"
            f"🕒 <b>Lúc:</b> <code>{time_now}</code>\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        await msg_wait.edit_text(res_text, parse_mode="HTML")
    elif status == "WAITING":
        await msg_wait.edit_text("⏳ API đang bận (Chờ 15p). Thử lại sau.")
    else:
        await msg_wait.edit_text("❌ Không lấy được dữ liệu. Kiểm tra lại Username.")

# ================== LỆNH AUTOBUFF (TỰ ĐỘNG TRẢ LỜI) ==================
async def autobuff_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    if chat_id not in AUTO_DB: return
    info = AUTO_DB[chat_id]; username = info["username"]
    data, status = await fetch_stats(username)
    if status == "OK" and data:
        if data["plus"] > info.get("last_plus", -1):
            total = max(data["before"] + data["plus"], data["current"])
            time_now = datetime.now(VN_TZ).strftime("%H:%M:%S")
            msg = (
                f"<b>🔔 CẬP NHẬT AUTO: +{data['plus']:,}</b>\n"
                f"👤 User: <code>@{escape(username)}</code>\n"
                f"📊 Tổng: <code>{total:,}</code>\n"
                f"🕒 Lúc: <code>{time_now}</code>"
            )
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
            AUTO_DB[chat_id]["last_plus"] = data["plus"]; save_db()

async def cmd_autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in CONFIG["ADMINS"]: return
    if not context.args: return await update.message.reply_text("Cú pháp: `/autobuff username`")
    
    username = context.args[0].replace("@", "")
    chat_id = update.effective_chat.id
    for job in context.job_queue.get_jobs_by_name(str(chat_id)): job.schedule_removal()
    
    AUTO_DB[chat_id] = {"username": username, "last_plus": -1}; save_db()
    context.job_queue.run_repeating(autobuff_job, interval=CONFIG["INTERVAL"], first=5, chat_id=chat_id, name=str(chat_id))
    await update.message.reply_text(f"✅ Đã bật Auto cho <code>{username}</code> (15p/lần).", parse_mode="HTML")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if jobs:
        for job in jobs: job.schedule_removal()
        if chat_id in AUTO_DB: del AUTO_DB[chat_id]; save_db()
        await update.message.reply_text("🛑 Đã dừng Auto.")

# ================== KHỞI CHẠY ==================
async def post_init(application: Application):
    load_db()
    for cid, info in AUTO_DB.items():
        application.job_queue.run_repeating(autobuff_job, interval=CONFIG["INTERVAL"], first=10, chat_id=cid, name=str(cid))

def main():
    keep_alive()
    app = ApplicationBuilder().token(CONFIG["BOT_TOKEN"]).post_init(post_init).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Bot Ready!")))
    app.add_handler(CommandHandler("buff", cmd_buff))
    app.add_handler(CommandHandler("autobuff", cmd_autobuff))
    app.add_handler(CommandHandler("stopbuff", cmd_stop))
    app.run_polling()

if __name__ == "__main__":
    main()
