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
BOT_TOKEN = "8080338995:AAHI8yhEUnJGgqEIDcaJ0eIKBGtuQpzQiX8"
ALLOWED_GROUP_ID = -1002666964512
ADMINS = [5736655322]

API_FL1 = "https://abcdxyz310107.x10.mx/apifl.php?fl1={}"
API_FL2 = "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"

VIETNAM_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
session_instance = None

# ================== TIỆN ÍCH ==================

def get_now_vn():
    """Lấy thời gian thực tại Việt Nam"""
    return datetime.now(VIETNAM_TZ).strftime("%H:%M:%S - %d/%m/%Y")

async def get_session():
    """Dùng chung session để tăng tốc độ gọi API"""
    global session_instance
    if session_instance is None or session_instance.closed:
        timeout = aiohttp.ClientTimeout(total=25)
        session_instance = aiohttp.ClientSession(timeout=timeout)
    return session_instance

def is_admin(user_id: int):
    return user_id in ADMINS

# ================== XỬ LÝ DỮ LIỆU ==================

async def call_api(url):
    session = await get_session()
    try:
        async with session.get(url) as r:
            if r.status == 200:
                text = await r.text()
                return text.strip()
            return ""
    except Exception:
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

async def run_dual_api_logic(username):
    """Chạy song song 2 API và gộp kết quả"""
    res1, res2 = await asyncio.gather(
        call_api(API_FL1.format(username)),
        call_api(API_FL2.format(username))
    )
    
    d1 = parse_follow_data(res1)
    d2 = parse_follow_data(res2)
    
    if not d1 and not d2: return None

    # Ưu tiên lấy thông tin từ API có phản hồi
    nickname = d1["nickname"] if d1 else d2["nickname"]
    before = d1["before"] if d1 else d2["before"]
    total_plus = (d1["plus"] if d1 else 0) + (d2["plus"] if d2 else 0)
    
    return {
        "nickname": nickname,
        "before": before,
        "plus": total_plus,
        "after": before + total_plus
    }

# ================== CÁC LỆNH CHÍNH ==================

async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_GROUP_ID:
        return # Chỉ chạy trong nhóm quy định
    
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ Cú pháp: `/buff <username>`", parse_mode="Markdown")
        return

    username = context.args[0]
    sent_msg = await update.message.reply_text(f"⏳ Đang buff song song 2 API cho `@{username}`...")

    data = await run_dual_api_logic(username)
    if not data:
        return await sent_msg.edit_text("❌ Lỗi: Cả 2 Server API không phản hồi hoặc sai Username.")

    result = (
        "✅ **BUFF THÀNH CÔNG (DUAL SERVER)**\n\n"
        f"👤 User: `@{username}`\n"
        f"🏷 Nickname: {data['nickname']}\n"
        f"📉 Follow trước: {data['before']}\n"
        f"📈 Tổng tăng: +{data['plus']}\n"
        f"📊 Hiện tại: {data['after']}\n"
        f"⏰ `{get_now_vn()}`"
    )
    await sent_msg.edit_text(result, parse_mode="Markdown")

async def autobuff_job(context: ContextTypes.DEFAULT_TYPE):
    """Chạy ngầm mỗi 15 phút"""
    username = context.job.data
    data = await run_dual_api_logic(username)
    
    if data:
        text = (
            "🔄 **[AUTO] CẬP NHẬT TRẠNG THÁI**\n"
            f"👤 User: `@{username}` | Nickname: {data['nickname']}\n"
            f"📈 Vừa tăng: +{data['plus']} follow\n"
            f"📊 Tổng hiện tại: {data['after']}\n"
            f"⏰ Lúc: `{get_now_vn()}`"
        )
        await context.bot.send_message(context.job.chat_id, text, parse_mode="Markdown")

async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 1: return

    username = context.args[0]
    chat_id = update.effective_chat.id
    
    # Xóa các lịch trình cũ nếu đang chạy
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs: job.schedule_removal()

    # Chạy lặp lại mỗi 900 giây (15 phút)
    context.job_queue.run_repeating(
        autobuff_job, interval=900, first=5, 
        chat_id=chat_id, data=username, name=str(chat_id)
    )
    
    await update.message.reply_text(f"🚀 Đã kích hoạt **Autobuff Dual-API** cho `@{username}`\n⏱ Tần suất: 15 phút/lần.", parse_mode="Markdown")

async def checkapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    
    msg = await update.message.reply_text("🔍 Đang kiểm tra kết nối server...")
    start = time.time()
    
    # Kiểm tra đồng thời cả 2 link
    r1, r2 = await asyncio.gather(call_api(API_FL1.format("test")), call_api(API_FL2.format("test")))
    latency = round((time.time() - start) * 1000)

    res_text = (
        "📊 **TÌNH TRẠNG HỆ THỐNG**\n\n"
        f"🔹 Server 1: {'✅ Live' if r1 else '❌ Die'}\n"
        f"🔹 Server 2: {'✅ Live' if r2 else '❌ Die'}\n"
        f"⚡ Độ trễ: {latency}ms\n"
        f"🕒 Giờ VN: `{get_now_vn()}`"
    )
    await msg.edit_text(res_text, parse_mode="Markdown")

async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    jobs = context.job_queue.get_jobs_by_name(str(update.effective_chat.id))
    for job in jobs: job.schedule_removal()
    await update.message.reply_text("🛑 Đã dừng mọi tiến trình Autobuff.")

# ================== KHỞI ĐỘNG ==================

async def post_init(application):
    await get_session() # Mở sẵn session khi bot lên nguồn

def main():
    keep_alive() # Giữ bot sống trên các host như Replit
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("stopbuff", stopbuff))
    app.add_handler(CommandHandler("checkapi", checkapi))
    
    print(f"🤖 Bot đã sẵn sàng! Token hợp lệ. [{get_now_vn()}]")
    app.run_polling()

if __name__ == "__main__":
    main()
