import aiohttp
import asyncio
import re
import pytz
import time
import os
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, JobQueue
from keep_alive import keep_alive

# ================== CẤU HÌNH ==================
# Token đã được làm sạch để tránh lỗi InvalidToken
BOT_TOKEN = "8080338995:AAHI8yhEUnJGgqEIDcaJ0eIKBGtuQpzQiX8"

ALLOWED_GROUP_ID = -1002666964512
ADMINS = [5736655322]

# Cấu hình API
API_FL1 = "https://abcdxyz310107.x10.mx/apifl.php?fl1={}"
API_FL2 = "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"

# Cấu hình múi giờ Việt Nam
VIETNAM_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# Biến toàn cục để quản lý session
session_instance = None

# ================== TIỆN ÍCH ==================

def get_now_vn():
    """Lấy thời gian hiện tại định dạng Việt Nam"""
    return datetime.now(VIETNAM_TZ).strftime("%H:%M:%S - %d/%m/%Y")

async def get_session():
    """Khởi tạo hoặc trả về session hiện có để tối ưu hiệu suất"""
    global session_instance
    if session_instance is None or session_instance.closed:
        timeout = aiohttp.ClientTimeout(total=30)
        session_instance = aiohttp.ClientSession(timeout=timeout)
    return session_instance

def is_admin(user_id: int):
    """Kiểm tra quyền Admin"""
    return user_id in ADMINS

# ================== XỬ LÝ DỮ LIỆU API ==================

async def call_api(url):
    """Gọi API và trả về văn bản phản hồi"""
    session = await get_session()
    try:
        async with session.get(url) as r:
            if r.status == 200:
                text = await r.text()
                return text.strip()
            return ""
    except Exception as e:
        print(f"Lỗi kết nối API: {e}")
        return ""

def parse_follow_data(text):
    """Trích xuất thông tin từ phản hồi của API bằng Regex"""
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
    """Chạy song song 2 API và gộp kết quả trả về"""
    # Gửi yêu cầu đồng thời đến cả 2 server
    res1, res2 = await asyncio.gather(
        call_api(API_FL1.format(username)),
        call_api(API_FL2.format(username))
    )
    
    d1 = parse_follow_data(res1)
    d2 = parse_follow_data(res2)

    if not d1 and not d2: return None

    # Lấy thông tin cơ bản (ưu tiên d1, nếu không có lấy d2)
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

# ================== CÁC LỆNH CỦA BOT ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh chào mừng"""
    await update.message.reply_text(
        "🤖 **Bot Dual-API Buff Follow**\n\n"
        "Các lệnh khả dụng:\n"
        "🔹 `/buff <username>` - Chạy buff ngay lập tức\n"
        "🔸 `/checkapi` - Kiểm tra trạng thái server (Admin)\n"
        "🔹 `/autobuff <username>` - Tự động buff mỗi 15p (Admin)\n"
        "🔸 `/stopbuff` - Dừng tự động buff (Admin)",
        parse_mode="Markdown"
    )

async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh buff thủ công"""
    if update.effective_chat.id != ALLOWED_GROUP_ID:
        return 

    if len(context.args) < 1:
        await update.message.reply_text("⚠️ Vui lòng nhập username. HD: `/buff baohuydev`", parse_mode="Markdown")
        return

    username = context.args[0]
    msg = await update.message.reply_text(f"⏳ Đang xử lý @{username} trên cả 2 server...")

    data = await run_dual_api_logic(username)
    
    if not data:
        await msg.edit_text("❌ Lỗi: Server không phản hồi hoặc username sai.")
        return

    result_text = (
        "✅ **KẾT QUẢ BUFF SONG SONG**\n\n"
        f"👤 Tài khoản: `@{username}`\n"
        f"🏷 Nickname: {data['nickname']}\n"
        f"📉 Follow trước: {data['before']}\n"
        f"📈 Tổng tăng: +{data['plus']}\n"
        f"📊 Hiện tại: {data['after']}\n"
        f"⏰ Lúc: `{get_now_vn()}`"
    )
    await msg.edit_text(result_text, parse_mode="Markdown")

async def autobuff_job(context: ContextTypes.DEFAULT_TYPE):
    """Tiến trình chạy ngầm mỗi 15 phút"""
    username = context.job.data
    data = await run_dual_api_logic(username)
    
    if data:
        text = (
            "🔄 **[AUTO] CẬP NHẬT TRẠNG THÁI**\n"
            f"👤 User: `@{username}`\n"
            f"📈 Vừa tăng thêm: +{data['plus']}\n"
            f"📊 Tổng hiện tại: {data['after']}\n"
            f"⏰ `{get_now_vn()}`"
        )
        await context.bot.send_message(context.job.chat_id, text, parse_mode="Markdown")

async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bật chế độ tự động cho Admin"""
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 1: return

    username = context.args[0]
    chat_id = update.effective_chat.id
    
    # Xóa các lịch trình cũ nếu có
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs: job.schedule_removal()

    # Thiết lập chu kỳ 15 phút (900 giây)
    context.job_queue.run_repeating(
        autobuff_job, interval=900, first=10, 
        chat_id=chat_id, data=username, name=str(chat_id)
    )
    
    await update.message.reply_text(
        f"🚀 **Đã bật Autobuff Dual-API**\n👤 User: `@{username}`\n⏱ Tần suất: 15 phút/lần",
        parse_mode="Markdown"
    )

async def checkapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kiểm tra xem link API còn sống không"""
    if not is_admin(update.effective_user.id): return
    
    status_msg = await update.message.reply_text("🔍 Đang ping server...")
    start_time = time.time()
    
    # Check đồng thời 2 server
    r1, r2 = await asyncio.gather(call_api(API_FL1.format("test")), call_api(API_FL2.format("test")))
    latency = round((time.time() - start_time) * 1000)

    res = (
        "📊 **TRẠNG THÁI HỆ THỐNG**\n\n"
        f"Server 1: {'✅ ONLINE' if r1 else '❌ OFFLINE'}\n"
        f"Server 2: {'✅ ONLINE' if r2 else '❌ OFFLINE'}\n"
        f"⚡ Độ trễ: {latency}ms\n"
        f"🕒 Giờ VN: `{get_now_vn()}`"
    )
    await status_msg.edit_text(res, parse_mode="Markdown")

async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dừng tất cả autobuff trong chat hiện tại"""
    if not is_admin(update.effective_user.id): return
    jobs = context.job_queue.get_jobs_by_name(str(update.effective_chat.id))
    if not jobs:
        return await update.message.reply_text("Không có tiến trình nào đang chạy.")
    for job in jobs: job.schedule_removal()
    await update.message.reply_text("🛑 Đã dừng mọi tiến trình Autobuff.")

# ================== KHỞI CHẠY ==================

async def post_init(application):
    """Mở kết nối session ngay khi bot khởi động"""
    await get_session()

def main():
    # Giữ bot luôn chạy (cho Replit)
    keep_alive() 
    
    # Khởi tạo Application
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Thêm các Handler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("stopbuff", stopbuff))
    app.add_handler(CommandHandler("checkapi", checkapi))
    
    print(f"🤖 Bot Dual-API đang hoạt động... [{get_now_vn()}]")
    app.run_polling()

if __name__ == "__main__":
    main()
