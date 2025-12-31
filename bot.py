import aiohttp
import asyncio
import re
import pytz
import time
import os
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

# ================== CẤU HÌNH ==================
# Token đã được làm sạch để tránh lỗi lặp ID
BOT_TOKEN = "8080338995:AAHI8yhEUnJGgqEIDcaJ0eIKBGtuQpzQiX8"

ALLOWED_GROUP_ID = -1002666964512
ADMINS = [5736655322]

# API Endpoint
API_FL1 = "https://abcdxyz310107.x10.mx/apifl.php?fl1={}"
API_FL2 = "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"

# Cấu hình múi giờ và Session
VIETNAM_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
session_instance = None

# ================== CƠ CHẾ KẾT NỐI TỐI ƯU ==================

def get_now_vn():
    """Lấy thời gian hiện tại định dạng Việt Nam"""
    return datetime.now(VIETNAM_TZ).strftime("%H:%M:%S - %d/%m/%Y")

async def get_session():
    """Dùng chung session và tăng Timeout lên 60s để chống delay server"""
    global session_instance
    if session_instance is None or session_instance.closed:
        # Tăng timeout tổng lên 60s, connect timeout 15s
        timeout = aiohttp.ClientTimeout(total=60, connect=15)
        session_instance = aiohttp.ClientSession(timeout=timeout)
    return session_instance

async def call_api_safe(url):
    """Gọi API an toàn: Tự động bỏ qua nếu server lỗi hoặc lag"""
    session = await get_session()
    try:
        async with session.get(url) as r:
            if r.status == 200:
                text = await r.text()
                # Kiểm tra nội dung có chứa từ khóa hợp lệ không
                if text and "nickname" in text.lower():
                    return text.strip()
    except Exception as e:
        print(f"⚠️ Cảnh báo: Server phản hồi chậm hoặc lỗi kết nối: {url[:30]}...")
    return None

def parse_data(text):
    """Trích xuất dữ liệu từ văn bản API"""
    if not text: return None
    try:
        nickname = re.search(r'nickname[:\s]*([^\n\r]+)', text, re.IGNORECASE)
        before = re.search(r'follow\s*trước[:\s]*(\d+)', text, re.IGNORECASE)
        plus = re.search(r'\+(\d+)', text)
        
        return {
            "nickname": nickname.group(1).strip() if nickname else "N/A",
            "before": int(before.group(1)) if before else 0,
            "plus": int(plus.group(1)) if plus else 0
        }
    except:
        return None

# ================== LOGIC XỬ LÝ SONG SONG (DUAL-API) ==================

async def process_dual_api(username):
    """Chạy đồng thời 2 server để bù trừ lỗi cho nhau"""
    # Gửi yêu cầu đi cùng lúc (Concurrency)
    results = await asyncio.gather(
        call_api_safe(API_FL1.format(username)),
        call_api_safe(API_FL2.format(username))
    )
    
    d1 = parse_data(results[0])
    d2 = parse_data(results[1])

    if not d1 and not d2:
        return None # Cả 2 server đều không phản hồi

    # Lấy thông tin hiển thị từ server nào sống
    base_info = d1 if d1 else d2
    # Cộng dồn số lượng follow tăng từ cả 2 nguồn
    plus_total = (d1["plus"] if d1 else 0) + (d2["plus"] if d2 else 0)
    
    status_str = f"S1: {'✅' if d1 else '❌'} | S2: {'✅' if d2 else '❌'}"
    
    return {
        "nickname": base_info["nickname"],
        "before": base_info["before"],
        "plus": plus_total,
        "after": base_info["before"] + plus_total,
        "status": status_str
    }

# ================== CÁC LỆNH ĐIỀU KHIỂN ==================

async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /buff cho người dùng"""
    if update.effective_chat.id != ALLOWED_GROUP_ID: return
    if not context.args:
        return await update.message.reply_text("⚠️ Cú pháp: `/buff <username>`")

    username = context.args[0]
    sent_msg = await update.message.reply_text(f"⏳ Đang xử lý song song @{username}...\n(Hệ thống chờ phản hồi tối đa 60s)")

    data = await process_dual_api(username)
    
    if not data:
        return await sent_msg.edit_text("❌ **Lỗi Server:** Cả 2 API đều không phản hồi. Username sai hoặc server đang bảo trì.")

    res_msg = (
        "✅ **BUFF HOÀN TẤT (DUAL-API)**\n\n"
        f"👤 User: `@{username}`\n"
        f"🏷 Nick: {data['nickname']}\n"
        f"📉 Trước: {data['before']}\n"
        f"📈 Tăng tổng: +{data['plus']}\n"
        f"📊 Hiện tại: {data['after']}\n"
        f"⚙️ Trạng thái: {data['status']}\n"
        f"⏰ `{get_now_vn()}`"
    )
    await sent_msg.edit_text(res_msg, parse_mode="Markdown")

async def autobuff_job(context: ContextTypes.DEFAULT_TYPE):
    """Tiến trình chạy ngầm mỗi 15 phút"""
    username = context.job.data
    data = await process_dual_api(username)
    if data:
        report = (f"🔄 **[AUTO] CẬP NHẬT**\n"
                  f"👤 `@{username}`: +{data['plus']} follow\n"
                  f"📊 Tổng: {data['after']}\n"
                  f"⏰ `{get_now_vn()}`")
        await context.bot.send_message(context.job.chat_id, report, parse_mode="Markdown")

async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bật Autobuff (Admin)"""
    if not update.effective_user.id in ADMINS: return
    if not context.args: return
    
    username = context.args[0]
    chat_id = update.effective_chat.id
    
    # Dọn dẹp job cũ
    for j in context.job_queue.get_jobs_by_name(str(chat_id)): j.schedule_removal()
    
    # Chạy lặp lại 15p
    context.job_queue.run_repeating(autobuff_job, interval=900, first=5, chat_id=chat_id, data=username, name=str(chat_id))
    await update.message.reply_text(f"🚀 Đã kích hoạt Autobuff cho `@{username}`\n⏱ Tần suất: 15 phút/lần.")

async def checkapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kiểm tra tình trạng sống chết của API (Admin)"""
    if not update.effective_user.id in ADMINS: return
    m = await update.message.reply_text("🔍 Đang ping server...")
    start = time.time()
    r1, r2 = await asyncio.gather(call_api_safe(API_FL1.format("test")), call_api_safe(API_FL2.format("test")))
    lat = round((time.time() - start) * 1000)
    
    status = (f"📊 **HỆ THỐNG API**\n"
              f"S1: {'✅ ONLINE' if r1 else '❌ ERROR'}\n"
              f"S2: {'✅ ONLINE' if r2 else '❌ ERROR'}\n"
              f"⚡ Delay: {lat}ms\n"
              f"🕒 `{get_now_vn()}`")
    await m.edit_text(status, parse_mode="Markdown")

async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dừng Autobuff (Admin)"""
    if not update.effective_user.id in ADMINS: return
    for j in context.job_queue.get_jobs_by_name(str(update.effective_chat.id)): j.schedule_removal()
    await update.message.reply_text("🛑 Đã dừng tiến trình Autobuff.")

# ================== KHỞI CHẠY ==================

async def post_init(application):
    await get_session()

def main():
    keep_alive() # Hàm giữ bot sống trên host
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("stopbuff", stopbuff))
    app.add_handler(CommandHandler("checkapi", checkapi))
    
    print(f"🤖 Bot Online - Dual API Mode Active [{get_now_vn()}]")
    app.run_polling()

if __name__ == "__main__":
    main()
