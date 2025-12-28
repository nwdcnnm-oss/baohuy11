import time
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from keep_alive import keep_alive

# ================= CẤU HÌNH =================
BOT_TOKEN = "8080338995:AAHitAzhTUUb1XL0LB44BiJmOCgulA4fx38"  # Thay bằng token bot của bạn
ADMINS = [5736655322]           # Thay bằng user_id admin
AUTO_JOBS = {}
USER_COOLDOWN = {}             # Lưu last_time của từng user
BUFF_INTERVAL = 900            # 15 phút = 900 giây

# ================= Keep Alive =================
keep_alive()  # Giữ bot online

# ================= Kiểm tra admin =================
def is_admin(user_id):
    return user_id in ADMINS

# ================= /start =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot Buff Telegram\n\n"
        "📌 Lệnh:\n"
        "/buff <username> – Buff 1 lần (15 phút/lần, mọi người dùng)\n"
        "/autobuff <username> <time> – Auto buff (giây) (chỉ admin)\n"
        "/stopbuff – Dừng auto buff (chỉ admin)\n"
        "/listbuff – Xem danh sách auto buff (chỉ admin)\n"
        "/adm – Thông tin admin (chỉ admin)\n"
        "/addadmin <user_id> – Thêm admin mới (chỉ admin)"
    )

# ================= /adm =================
async def adm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_admin(user_id):
        await update.message.reply_text(
            f"✅ Bạn là admin\nUser ID: {user_id}\nAdmins hiện tại: {ADMINS}"
        )
    else:
        await update.message.reply_text("❌ Bạn không có quyền dùng lệnh này.")

# ================= /addadmin =================
async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Bạn không có quyền dùng lệnh này.")
        return

    if not context.args:
        await update.message.reply_text("❌ Dùng: /addadmin <user_id>")
        return

    try:
        new_admin = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ user_id phải là số.")
        return

    if new_admin in ADMINS:
        await update.message.reply_text(f"⚠️ User {new_admin} đã là admin.")
        return

    ADMINS.append(new_admin)
    await update.message.reply_text(f"✅ Đã thêm admin mới: {new_admin}\nADMINS hiện tại: {ADMINS}")

# ================= Gọi API =================
async def call_buff_api(username: str):
    url = f"https://abcdxyz310107.x10.mx/apifl.php?username={username}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=15) as response:
                response.raise_for_status()
                data = await response.json()
                return data
        except Exception as e:
            raise RuntimeError(f"Lỗi API: {e}")

# ================= Format kết quả =================
def format_result(data: dict):
    return (
        f"✅ Tăng follow thành công\n"
        f"👤 @{data.get('username', 'Unknown')}\n"
        f"UID: {data.get('uid', 'Không có')}\n"
        f"Nickname: {data.get('nickname', 'Không có')}\n"
        f"FOLLOW BAN ĐẦU: {data.get('follow_base', '0')}\n"
        f"FOLLOW ĐÃ TĂNG: +{data.get('follow_added', '0')}\n"
        f"FOLLOW HIỆN TẠI: {data.get('follow_current', '0')}"
    )

# ================= /buff (mọi người, cooldown 15 phút) =================
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
        minutes = remain // 60
        seconds = remain % 60
        await update.message.reply_text(f"⏳ Bạn phải chờ {minutes} phút {seconds} giây mới buff lại.")
        return

    USER_COOLDOWN[user_id] = now
    await update.message.reply_text("⏳ Chờ 20 giây để buff...")
    await asyncio.sleep(20)

    try:
        data = await call_buff_api(username)
        await update.message.reply_text(format_result(data))
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

# ================= AUTO BUFF JOB (chỉ admin) =================
async def auto_buff_job(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    username = job_data["username"]
    chat_id = job_data["chat_id"]
    print(f"[AUTO BUFF] Bắt đầu buff @{username} cho chat_id {chat_id}")

    try:
        data = await call_buff_api(username)
        await context.bot.send_message(chat_id=chat_id, text=format_result(data))
    except Exception as e:
        print(f"[AUTO BUFF] Lỗi: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi auto buff: {e}")

# ================= /autobuff (chỉ admin) =================
async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Chỉ admin mới có quyền dùng lệnh này.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("❌ Dùng: /autobuff <username> <time_giây>")
        return

    chat_id = update.effective_chat.id
    username = context.args[0]

    try:
        interval = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Thời gian phải là số (giây)")
        return

    if user_id in AUTO_JOBS:
        await update.message.reply_text("⚠️ Bạn đã bật auto buff rồi. Dùng /stopbuff trước.")
        return

    job = context.job_queue.run_repeating(
        auto_buff_job,
        interval=interval,
        first=0,
        data={"username": username, "chat_id": chat_id},
        name=str(user_id)
    )

    AUTO_JOBS[user_id] = job
    await update.message.reply_text(
        f"✅ Đã bật AUTO BUFF\n👤 Username: {username}\n⏱️ Mỗi {interval} giây"
    )

# ================= /stopbuff (chỉ admin) =================
async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Chỉ admin mới có quyền dùng lệnh này.")
        return

    job = AUTO_JOBS.pop(user_id, None)
    if job:
        job.schedule_removal()
        await update.message.reply_text("🛑 Đã dừng auto buff.")
    else:
        await update.message.reply_text("⚠️ Bạn chưa bật auto buff.")

# ================= /listbuff (chỉ admin) =================
async def listbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Chỉ admin mới có quyền dùng lệnh này.")
        return

    if not AUTO_JOBS:
        await update.message.reply_text("⚠️ Hiện tại không có auto buff nào đang chạy.")
        return

    msg = "📋 Danh sách AUTO BUFF đang chạy:\n\n"
    for uid, job in AUTO_JOBS.items():
        username = job.data.get("username", "Unknown")
        interval = job.interval
        msg += f"👤 Admin User ID: {uid}\n   Username: {username}\n   Interval: {interval} giây\n\n"

    await update.message.reply_text(msg)

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buff", buff))  # mở cho mọi người
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("stopbuff", stopbuff))
    app.add_handler(CommandHandler("listbuff", listbuff))
    app.add_handler(CommandHandler("adm", adm))
    app.add_handler(CommandHandler("addadmin", addadmin))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: None))

    print("🤖 Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
