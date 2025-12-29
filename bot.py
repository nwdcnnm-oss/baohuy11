#!/usr/bin/env python3
import time, asyncio, aiohttp, logging
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    ContextTypes, MessageHandler, filters
)
from keep_alive import keep_alive

# ================= CONFIG =================
BOT_TOKEN = "8080338995:AAHitAzhTUUb1XL0LB44BiJmOCgulA4fx38"
ADMINS = [5736655322]
ALLOWED_GROUP_ID = -1002666964512

API_DELAY = 36
AUTO_INTERVAL = 900  # 15 phút
BUFF_COOLDOWN = 30   # /buff public

# ================= DATA =================
AUTO_JOBS = {}          # {uid: {username: job}}
AUTO_LAST = {}          # {(uid, username): last_follow}
AUTO_STATS = {}         # {(uid, username): {date, count}}
USER_COOLDOWN = {}      # {uid: last_time}
session = None

# ================= LOG =================
logging.basicConfig(level=logging.INFO)

# ================= UTILS =================
def is_admin(uid): 
    return uid in ADMINS

def allow_group(update): 
    return update.effective_chat.id == ALLOWED_GROUP_ID

# ================= SESSION =================
async def get_session():
    global session
    if not session or session.closed:
        session = aiohttp.ClientSession()
    return session

# ================= API =================
async def call_api(username):
    urls = [
        f"https://abcdxyz310107.x10.mx/apifl.php?fl1={username}",
        f"https://abcdxyz310107.x10.mx/apifl.php?fl2={username}",
    ]
    s = await get_session()
    for url in urls:
        try:
            async with s.get(url, timeout=40) as r:
                data = await r.json(content_type=None)
                if data.get("success"):
                    return data
        except:
            pass
    return {"success": False, "message": "API lỗi"}

def format_result(d):
    return (
        "✅ BUFF THÀNH CÔNG\n\n"
        f"👤 @{d.get('username')}\n"
        f"Follow trước: {d.get('followers_before')}\n"
        f"Follow tăng: +{d.get('followers_increased')}\n"
        f"Follow hiện tại: {d.get('followers_now')}"
    )

# ================= GUARD =================
async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type in ("group", "supergroup") and chat.id != ALLOWED_GROUP_ID:
        await context.bot.leave_chat(chat.id)

# ================= /buff (PUBLIC) =================
async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allow_group(update):
        return

    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❌ /buff <username>")
        return

    now = time.time()
    if now - USER_COOLDOWN.get(uid, 0) < BUFF_COOLDOWN:
        await update.message.reply_text(
            f"⏳ Chờ {BUFF_COOLDOWN}s để buff lại."
        )
        return

    USER_COOLDOWN[uid] = now
    username = context.args[0].lstrip("@")

    await update.message.reply_text(f"⏳ Đang buff @{username}...")
    await asyncio.sleep(API_DELAY)

    data = await call_api(username)
    if data.get("success"):
        await update.message.reply_text(format_result(data))
    else:
        await update.message.reply_text("❌ Buff thất bại")

# ================= AUTO CORE =================
async def auto_task(username, chat_id, context, uid):
    await asyncio.sleep(API_DELAY)
    data = await call_api(username)
    if not data.get("success"):
        return

    key = (uid, username)
    now = int(data.get("followers_now", 0))
    last = AUTO_LAST.get(key)

    if last and now <= last:
        return

    AUTO_LAST[key] = now
    today = datetime.now().strftime("%Y-%m-%d")
    AUTO_STATS.setdefault(key, {"date": today, "count": 0})
    if AUTO_STATS[key]["date"] != today:
        AUTO_STATS[key] = {"date": today, "count": 0}
    AUTO_STATS[key]["count"] += 1

    await context.bot.send_message(chat_id, format_result(data))

# ================= /autobuff (ADMIN) =================
async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allow_group(update):
        return

    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ Chỉ admin")
        return

    if not context.args:
        await update.message.reply_text("❌ /autobuff <username>")
        return

    username = context.args[0].lstrip("@")
    AUTO_JOBS.setdefault(uid, {})

    if username in AUTO_JOBS[uid]:
        await update.message.reply_text("⚠️ User đang treo")
        return

    job = context.job_queue.run_repeating(
        lambda c: asyncio.create_task(
            auto_task(username, update.effective_chat.id, c, uid)
        ),
        interval=AUTO_INTERVAL,
        first=0
    )

    AUTO_JOBS[uid][username] = job
    await update.message.reply_text(
        f"✅ Treo auto @{username}\n⏱ 900 giây"
    )

# ================= /stopbuff =================
async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allow_group(update):
        return

    uid = update.effective_user.id
    if uid not in AUTO_JOBS:
        await update.message.reply_text("⚠️ Không có auto")
        return

    if not context.args:
        await update.message.reply_text("❌ /stopbuff <username|all>")
        return

    if context.args[0] == "all":
        for job in AUTO_JOBS[uid].values():
            job.schedule_removal()
        AUTO_JOBS[uid].clear()
        await update.message.reply_text("🛑 Dừng toàn bộ auto")
        return

    username = context.args[0].lstrip("@")
    job = AUTO_JOBS[uid].pop(username, None)
    if job:
        job.schedule_removal()
        await update.message.reply_text(f"🛑 Đã dừng @{username}")
    else:
        await update.message.reply_text("⚠️ Không tìm thấy user")

# ================= /listbuff =================
async def listbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allow_group(update):
        return

    uid = update.effective_user.id
    users = AUTO_JOBS.get(uid, {})
    if not users:
        await update.message.reply_text("📭 Không có auto")
        return

    msg = "📋 AUTO ĐANG TREO:\n"
    for u in users:
        msg += f"• @{u}\n"
    await update.message.reply_text(msg)

# ================= MAIN =================
def main():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.ALL, guard), group=0)
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("stopbuff", stopbuff))
    app.add_handler(CommandHandler("listbuff", listbuff))

    logging.info("🤖 BOT CHẠY - PUBLIC BUFF + ADMIN AUTO")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()

