import aiohttp
import asyncio
import re
import pytz
import time
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

# ================== CẤU HÌNH ==================
BOT_TOKEN = "8080338995:8080338995:AAFXhz1kjZsZlE3KUP_FCTis6bF3j0PIAKU"
ALLOWED_GROUP_ID = -1002666964512
ADMINS = [5736655322]

API_FL1 = "https://abcdxyz310107.x10.mx/apifl.php?fl1={}"
API_FL2 = "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"

VIETNAM_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
session_instance = None

# ================== TIỆN ÍCH ==================

def get_now_vn():
    return datetime.now(VIETNAM_TZ).strftime("%H:%M:%S - %d/%m/%Y")

async def get_session():
    global session_instance
    if session_instance is None or session_instance.closed:
        session_instance = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))
    return session_instance

def is_admin(user_id: int):
    return user_id in ADMINS

# ================== XỬ LÝ API ==================

async def call_api(url):
    session = await get_session()
    try:
        async with session.get(url) as r:
            if r.status == 200:
                text = await r.text()
                return text.strip()
            return ""
    except:
        return ""

def parse_follow_data(text):
    if not text: return None
    nickname = re.search(r'nickname[:\s]*([^\n\r]+)', text, re.IGNORECASE)
    before = re.search(r'follow\s*trước[:\s]*(\d+)', text, re.IGNORECASE)
    plus = re.search(r'\+(\d+)', text)
    return {
        "nickname": nickname.group(1).strip() if nickname else "Không rõ",
        "before": int(before.group(1)) if before else 0,
        "plus": int(plus.group(1)) if plus else 0
    }

# ================== LOGIC AUTO RUN 2 API ==================

async def run_dual_api_process(username):
    """Hàm lõi để chạy song song 2 API và gộp kết quả"""
    res1, res2 = await asyncio.gather(
        call_api(API_FL1.format(username)),
        call_api(API_FL2.format(username))
    )
    
    d1, d2 = parse_follow_data(res1), parse_follow_data(res2)
    
    if not d1 and not d2:
        return None

    nickname = d1["nickname"] if d1 else d2["nickname"]
    before = d1["before"] if d1 else d2["before"]
    # Cộng dồn số follow tăng từ cả 2 API
    total_plus = (d1["plus"] if d1 else 0) + (d2["plus"] if d2 else 0)
    
    return {
        "nickname": nickname,
        "before": before,
        "plus": total_plus,
        "after": before + total_plus
    }

# ================== LỆNH BOT ==================

async def autobuff_job(context: ContextTypes.DEFAULT_TYPE):
    """Tiến trình chạy ngầm: Tự động gọi 2 API mỗi chu kỳ"""
    username = context.job.data
    data = await run_dual_api_process(username)
    
    if data:
        text = (
            "🔄 **[AUTOBUFF] HỆ THỐNG ĐÃ CHẠY**\n"
            f"👤 User: `@{username}`\n"
            f"🏷 Nickname: {data['nickname']}\n"
            f"📈 Tổng tăng (2 API): +{data['plus']}\n"
            f"📊 Hiện tại: {data['after']}\n"
            f"⏰ Lúc: `{get_now_vn()}`"
        )
        await context.bot.send_message(context.job.chat_id, text, parse_mode="Markdown")

async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 1:
        return await update.message.reply_text("⚠️ Cú pháp: `/autobuff <username>`")

    username = context.args[0]
    chat_id = update.effective_chat.id
    
    # Dừng các job cũ cho chat này
    for job in context.job_queue.get_jobs_by_name(str(chat_id)):
        job.schedule_removal()

    # Thiết lập chạy mỗi 900 giây (15 phút)
    context.job_queue.run_repeating(
        autobuff_job, 
        interval=900, 
        first=5, 
        chat_id=chat_id, 
        data=username, 
        name=str(chat_id)
    )
    
    await update.message.reply_text(
        f"🚀 **Đã kích hoạt Autobuff Dual-API**\n👤 User: `@{username}`\n⏱ Chu kỳ: 15 phút/lần\n⚙️ Trạng thái: Chạy song song 2 Server",
        parse_mode="Markdown"
    )

async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh buff thủ công cũng chạy 2 API"""
    if len(context.args) < 1: return
    username = context.args[0]
    msg = await update.message.reply_text(f"⏳ Đang buff song song 2 API cho @{username}...")
    
    data = await run_dual_api_process(username)
    if not data:
        return await msg.edit_text("❌ Lỗi: Cả 2 server API không phản hồi.")

    result_text = (
        "✅ **BUFF THÀNH CÔNG (DUAL SERVER)**\n"
        f"👤 User: `@{username}`\n"
        f"📉 Trước: {data['before']}\n"
        f"📈 Tăng tổng: +{data['plus']}\n"
        f"📊 Sau buff: {data['after']}\n"
        f"⏰ {get_now_vn()}"
    )
    await msg.edit_text(result_text, parse_mode="Markdown")

async def check_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    msg = await update.message.reply_text("🔍 Đang check 2 server...")
    
    # Check song song để lấy tốc độ
    start = time.time()
    r1, r2 = await asyncio.gather(call_api(API_FL1.format("test")), call_api(API_FL2.format("test")))
    lat = round((time.time() - start) * 1000)

    t = f"📊 **STATUS**\nS1: {'✅' if r1 else '❌'}\nS2: {'✅' if r2 else '❌'}\n⚡ Ping: {lat}ms\n🕒 {get_now_vn()}"
    await msg.edit_text(t, parse_mode="Markdown")

async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    for job in context.job_queue.get_jobs_by_name(str(update.effective_chat.id)):
        job.schedule_removal()
    await update.message.reply_text("🛑 Đã dừng Autobuff.")

async def post_init(application):
    await get_session()

def main():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("stopbuff", stopbuff))
    app.add_handler(CommandHandler("checkapi", check_api))
    print(f"🤖 Bot Dual-API đang chạy... [{get_now_vn()}]")
    app.run_polling()

if __name__ == "__main__":
    main()
