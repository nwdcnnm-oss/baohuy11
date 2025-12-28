import time
import asyncio
import aiohttp
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

# ================= CẤU HÌNH =================
BOT_TOKEN = "8080338995:AAHitAzhTUUb1XL0LB44BiJmOCgulA4fx38"  # Thay bằng token bot
ADMINS = [5736655322]  # Thay bằng Telegram user_id admin
AUTO_JOBS = {}
USER_COOLDOWN = {}
BUFF_INTERVAL = 900  # 15 phút

# ================= Logging =================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ================= Kiểm tra admin =================
def is_admin(user_id):
    return user_id in ADMINS

# ================= /start =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot Buff Telegram 24/7\n"
        "Lệnh:\n"
        "/buff <username>\n"
        "/autobuff <username> <giây>\n"
        "/autobuffme\n"
        "/stopbuff\n"
        "/listbuff\n"
        "/adm\n"
        "/addadmin <user_id>"
    )

# ================= Gọi API (session chung) =================
session = None

async def call_buff_api(username: str):
    global session
    if session is None:
        session = aiohttp.ClientSession()
    url = f"https://abcdxyz310107.x10.mx/apifl.php?username={username}"
    async with session.get(url, timeout=15) as response:
        response.raise_for_status()
        return await response.json()

# ================= Format kết quả =================
def format_result(data: dict):
    if not data.get("success"):
        return f"❌ Lỗi: {data.get('message','Không xác định')}"
    
    return (
        f"✅ {data.get('message','Thành công')}\n"
        f"👤 @{data.get('username','Unknown')}\n"
        f"Nickname: {data.get('nickname','Không có')}\n"
        f"FOLLOW BAN ĐẦU: {data.get('followers_before','0')}\n"
        f"FOLLOW ĐÃ TĂNG: +{data.get('followers_increased','0')}\n"
        f"FOLLOW HIỆN TẠI: {data.get('followers_now','0')}"
    )

# ================= /buff =================
async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❌ Dùng: /buff <username>")
        return

    username = context.args[0]
    now = time.time()
    last_time = USER_COOLDOWN.get(user_id, 0)
    if now - last_time < BUFF_INTERVAL:
        remain = int(BUFF_INTERVAL - (now - last_time))
        await update.message.reply_text(f"⏳ Chờ {remain} giây mới buff lại.")
        return

    USER_COOLDOWN[user_id] = now
    await update.message.reply_text("⏳ Chờ 20 giây để buff...")
    await asyncio.sleep(20)

    try:
        data = await call_buff_api(username)
        await update.message.reply_text(format_result(data))
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

# ================= AUTO BUFF JOB =================
async def auto_buff_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    username = job.data["username"]
    chat_id = job.data["chat_id"]
    try:
        data = await call_buff_api(username)
        await context.bot.send_message(chat_id=chat_id, text=format_result(data))
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi auto buff: {e}")

# ================= /autobuff =================
async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Chỉ admin mới dùng được lệnh này.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ Dùng: /autobuff <username> <giây>")
        return

    username = context.args[0]
    try:
        interval = int(context.args[1])
        if interval < 60:
            await update.message.reply_text("⚠️ Interval tối thiểu 60 giây.")
            return
    except ValueError:
        await update.message.reply_text("❌ Thời gian phải là số giây.")
        return

    if user_id in AUTO_JOBS:
        await update.message.reply_text("⚠️ Bạn đã bật auto buff rồi. Dùng /stopbuff trước.")
        return

    job = context.job_queue.run_repeating(
        auto_buff_job, interval=interval, first=0,
        data={"username": username, "chat_id": update.effective_chat.id},
        name=str(user_id)
    )
    AUTO_JOBS[user_id] = job
    await update.message.reply_text(f"✅ Bật auto buff @{username} mỗi {interval} giây.")

# ================= /autobuffme =================
async def autobuffme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username

    if not username:
        await update.message.reply_text("❌ Bạn chưa đặt username Telegram, không thể auto buff.")
        return

    interval = 900  # 15 phút

    if user_id in AUTO_JOBS:
        await update.message.reply_text("⚠️ Bạn đã bật auto buff rồi. Dùng /stopbuff trước.")
        return

    job = context.job_queue.run_repeating(
        auto_buff_job, interval=interval, first=0,
        data={"username": username, "chat_id": update.effective_chat.id},
        name=str(user_id)
    )
    AUTO_JOBS[user_id] = job
    await update.message.reply_text(f"✅ Bật auto buff @{username} mỗi 15 phút.")

# ================= /stopbuff =================
async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    job = AUTO_JOBS.pop(user_id, None)
    if job:
        job.schedule_removal()
        await update.message.reply_text("🛑 Dừng auto buff thành công.")
    else:
        await update.message.reply_text("⚠️ Bạn chưa bật auto buff.")

# ================= /listbuff =================
async def listbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not AUTO_JOBS:
        await update.message.reply_text("⚠️ Không có auto buff nào đang chạy.")
        return
    msg = "📋 Danh sách AUTO BUFF:\n"
    for uid, job in AUTO_JOBS.items():
        username = job.data["username"]
        interval = job.interval
        msg += f"👤 Admin {uid} - @{username} - {interval} giây\n"
    await update.message.reply_text(msg)

# ================= /adm =================
async def adm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Chỉ admin mới xem được danh sách admin.")
        return
    msg = "📋 Danh sách Admin:\n" + "\n".join([str(a) for a in ADMINS])
    await update.message.reply_text(msg)

# ================= /addadmin =================
async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Chỉ admin mới thêm admin được.")
        return
    if not context.args:
        await update.message.reply_text("❌ Dùng: /addadmin <user_id>")
        return
    try:
        new_admin = int(context.args[0])
        if new_admin in ADMINS:
            await update.message.reply_text("⚠️ Người này đã là admin.")
            return
        ADMINS.append(new_admin)
        await update.message.reply_text(f"✅ Thêm admin thành công: {new_admin}")
    except ValueError:
        await update.message.reply_text("❌ user_id không hợp lệ.")

# ================= MAIN =================
def main():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("autobuffme", autobuffme))
    app.add_handler(CommandHandler("stopbuff", stopbuff))
    app.add_handler(CommandHandler("listbuff", listbuff))
    app.add_handler(CommandHandler("adm", adm))
    app.add_handler(CommandHandler("addadmin", addadmin))

    logging.info("🤖 Bot 24/7 đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
