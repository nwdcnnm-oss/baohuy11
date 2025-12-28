import time
import asyncio
import aiohttp
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from keep_alive import keep_alive

# ================= CONFIG =================
BOT_TOKEN = "8080338995:AAHitAzhTUUb1XL0LB44BiJmOCgulA4fx38"   # ❗ THAY TOKEN MỚI
ADMINS = [5736655322]

API_DELAY = 36
API_TIMEOUT = 45
MIN_INTERVAL = 60

AUTO_JOBS = {}
USER_COOLDOWN = {}
USER_LAST_FOLLOWERS = {}

# ================= LOG =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)

# ================= ADMIN =================
def is_admin(uid: int) -> bool:
    return uid in ADMINS

# ================= /start =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 BOT BUFF TELEGRAM 24/7\n\n"
        "/buff <username>\n"
        "/autobuff <username> [giây] (admin)\n"
        "/autobuffme <giây>\n"
        "/stopbuff\n"
        "/listbuff\n"
        "/adm\n"
        "/addadmin <user_id>"
    )

# ================= AIOHTTP =================
session = None

async def get_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()
    return session

async def call_buff_api(username: str) -> dict:
    url = f"https://abcdxyz310107.x10.mx/apifl.php?username={username}"
    try:
        sess = await get_session()
        async with sess.get(url, timeout=API_TIMEOUT) as r:
            r.raise_for_status()
            data = await r.json()
            if data.get("success"):
                return data
            return {"success": False, "message": "API trả dữ liệu lỗi"}
    except Exception as e:
        log.error(f"API ERROR: {e}")
        return {"success": False, "message": str(e)}

# ================= FORMAT =================
def format_result(d: dict) -> str:
    return (
        f"✅ Auto buff thành công cho @{d.get('username','?')}\n\n"
        f"Nickname: {d.get('nickname','.')}\n"
        f"Follow trước: {d.get('followers_before','0')}\n"
        f"Follow tăng: +{d.get('followers_increased','0')}\n"
        f"Follow hiện tại: {d.get('followers_now','0')}"
    )

# ================= /buff =================
async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not context.args:
        await update.message.reply_text("❌ /buff <username>")
        return

    now = time.time()
    if now - USER_COOLDOWN.get(uid, 0) < 30:
        await update.message.reply_text("⏳ Chờ 30s rồi buff tiếp.")
        return

    USER_COOLDOWN[uid] = now
    username = context.args[0]

    await update.message.reply_text("⏳ Đang buff, vui lòng chờ...")
    await asyncio.sleep(API_DELAY)

    data = await call_buff_api(username)
    if not data.get("success"):
        await update.message.reply_text(f"❌ Lỗi: {data.get('message')}")
        return

    USER_LAST_FOLLOWERS[uid] = int(data["followers_now"])
    await update.message.reply_text(format_result(data))

# ================= AUTO BUFF CORE =================
async def run_auto_buff(username: str, chat_id: int, context, uid: int):
    await asyncio.sleep(API_DELAY)
    data = await call_buff_api(username)

    if not data.get("success"):
        await context.bot.send_message(chat_id, f"❌ Auto buff lỗi: {data.get('message')}")
        return

    now_follow = int(data["followers_now"])
    last = USER_LAST_FOLLOWERS.get(uid, 0)

    if now_follow != last:
        USER_LAST_FOLLOWERS[uid] = now_follow
        await context.bot.send_message(chat_id, format_result(data))

# ================= JOB =================
async def auto_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await run_auto_buff(
        username=job.data["username"],
        chat_id=job.data["chat_id"],
        context=context,
        uid=int(job.name)
    )

# ================= /autobuff =================
async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ Chỉ admin.")
        return

    if not context.args:
        await update.message.reply_text("❌ /autobuff <username> [giây]")
        return

    username = context.args[0]
    interval = int(context.args[1]) if len(context.args) > 1 else 900

    if interval < MIN_INTERVAL:
        await update.message.reply_text("⚠️ Interval ≥ 60s")
        return

    if uid in AUTO_JOBS:
        await update.message.reply_text("⚠️ Đã bật auto buff.")
        return

    job = context.job_queue.run_repeating(
        auto_job,
        interval=interval,
        first=0,
        name=str(uid),
        data={
            "username": username,
            "chat_id": update.effective_chat.id
        }
    )

    AUTO_JOBS[uid] = job
    USER_LAST_FOLLOWERS[uid] = 0

    await update.message.reply_text(
        f"✅ Auto buff @{username}\n⏱ Mỗi {interval} giây"
    )

# ================= /autobuffme =================
async def autobuffme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = update.effective_user.username

    if not username:
        await update.message.reply_text("❌ Bạn chưa có username.")
        return

    if not context.args:
        await update.message.reply_text("❌ /autobuffme <giây>")
        return

    interval = int(context.args[0])
    if interval < MIN_INTERVAL:
        await update.message.reply_text("⚠️ Interval ≥ 60s")
        return

    if uid in AUTO_JOBS:
        await update.message.reply_text("⚠️ Đã bật auto buff.")
        return

    job = context.job_queue.run_repeating(
        auto_job,
        interval=interval,
        first=0,
        name=str(uid),
        data={
            "username": username,
            "chat_id": update.effective_chat.id
        }
    )

    AUTO_JOBS[uid] = job
    USER_LAST_FOLLOWERS[uid] = 0

    await update.message.reply_text(f"✅ Auto buff @{username} mỗi {interval}s")

# ================= /stopbuff =================
async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    job = AUTO_JOBS.pop(uid, None)
    if job:
        job.schedule_removal()
        await update.message.reply_text("🛑 Đã dừng auto buff.")
    else:
        await update.message.reply_text("⚠️ Chưa bật auto buff.")

# ================= /listbuff =================
async def listbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not AUTO_JOBS:
        await update.message.reply_text("⚠️ Không có auto buff.")
        return

    msg = "📋 AUTO BUFF:\n"
    for uid, job in AUTO_JOBS.items():
        interval = int(job.trigger.interval.total_seconds())
        msg += f"👤 {uid} | @{job.data['username']} | {interval}s\n"

    await update.message.reply_text(msg)

# ================= ADMIN =================
async def adm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("📋 Admin:\n" + "\n".join(map(str, ADMINS)))

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        uid = int(context.args[0])
        if uid not in ADMINS:
            ADMINS.append(uid)
            await update.message.reply_text(f"✅ Đã thêm admin {uid}")
    except:
        await update.message.reply_text("❌ user_id không hợp lệ")

# ================= SHUTDOWN =================
async def shutdown(app):
    global session
    if session:
        await session.close()

# ================= MAIN =================
def main():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("autobuffme", autobuffme))
    app.add_handler(CommandHandler("stopbuff", stopbuff))
    app.add_handler(CommandHandler("listbuff", listbuff))
    app.add_handler(CommandHandler("adm", adm))
    app.add_handler(CommandHandler("addadmin", addadmin))

    app.post_shutdown = shutdown
    log.info("🤖 Bot đang chạy 24/7...")
    app.run_polling()

if __name__ == "__main__":
    main()
