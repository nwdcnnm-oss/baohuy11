#!/usr/bin/env python3
import asyncio
import time
import aiohttp
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from keep_alive import keep_alive

# ================== CONFIG ==================
BOT_TOKEN = "8080338995:AAHitAzhTUUb1XL0LB44BiJmOCgulA4fx38"

ALLOWED_GROUP_ID = -1002666964512   # ❗ ĐỔI ID GROUP THẬT
ADMINS = [5736655322]

API_DELAY = 5
AUTO_INTERVAL = 900      # 15 phút
BUFF_COOLDOWN = 30       # buff public

# ================== DATA ==================
AUTO_JOBS = {}           # {admin_id: {username: job}}
USER_COOLDOWN = {}       # {user_id: last_time}
session = None

# ================== LOG ==================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ================== UTILS ==================
def is_admin(uid):
    return uid in ADMINS

def in_allowed_group(update: Update):
    chat = update.effective_chat
    return chat and chat.id == ALLOWED_GROUP_ID

# ================== API ==================
async def get_session():
    global session
    if not session or session.closed:
        session = aiohttp.ClientSession()
    return session

async def call_api(username):
    urls = [
        f"https://abcdxyz310107.x10.mx/apifl.php?fl1={username}",
        f"https://abcdxyz310107.x10.mx/apifl.php?fl2={username}",
    ]
    s = await get_session()
    for url in urls:
        try:
            async with s.get(url, timeout=30) as r:
                data = await r.json(content_type=None)
                if data.get("success"):
                    return data
        except Exception as e:
            logging.warning(e)
    return {"success": False}

def format_msg(d):
    return (
        "✅ BUFF THÀNH CÔNG\n\n"
        f"👤 @{d.get('username','?')}\n"
        f"Follow tăng: +{d.get('followers_increased','0')}\n"
        f"Hiện tại: {d.get('followers_now','?')}"
    )

# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not in_allowed_group(update):
        await update.message.reply_text("❌ Bot chỉ hoạt động trong group chỉ định.")
        return

    await update.message.reply_text(
        "🤖 BOT BUFF ONLINE\n\n"
        "/ping\n"
        "/buff <username>  (mọi người)\n"
        "/autobuff <username> (admin)\n"
        "/stopbuff <username|all>"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ BOT ONLINE")

# ================== /buff PUBLIC ==================
async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not in_allowed_group(update):
        return

    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❌ /buff <username>")
        return

    now = time.time()
    if now - USER_COOLDOWN.get(uid, 0) < BUFF_COOLDOWN:
        await update.message.reply_text("⏳ Chờ 30s để buff lại.")
        return

    USER_COOLDOWN[uid] = now
    username = context.args[0].lstrip("@")

    await update.message.reply_text(f"⏳ Đang buff @{username}...")
    await asyncio.sleep(API_DELAY)

    data = await call_api(username)
    if data.get("success"):
        await update.message.reply_text(format_msg(data))
    else:
        await update.message.reply_text("❌ Buff thất bại.")

# ================== AUTO CORE ==================
async def auto_job(context, username, chat_id):
    data = await call_api(username)
    if data.get("success"):
        await context.bot.send_message(chat_id, format_msg(data))

# ================== /autobuff ADMIN ==================
async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not in_allowed_group(update):
        return

    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ Chỉ admin được dùng.")
        return

    if not context.args:
        await update.message.reply_text("❌ /autobuff <username>")
        return

    username = context.args[0].lstrip("@")
    AUTO_JOBS.setdefault(uid, {})

    if username in AUTO_JOBS[uid]:
        await update.message.reply_text("⚠️ User này đang auto.")
        return

    job = context.job_queue.run_repeating(
        lambda c: asyncio.create_task(
            auto_job(c, username, update.effective_chat.id)
        ),
        interval=AUTO_INTERVAL,
        first=0
    )

    AUTO_JOBS[uid][username] = job
    await update.message.reply_text(
        f"✅ Auto buff @{username}\n⏱ 900 giây"
    )

# ================== /stopbuff ==================
async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not in_allowed_group(update):
        return

    uid = update.effective_user.id
    if uid not in AUTO_JOBS or not AUTO_JOBS[uid]:
        await update.message.reply_text("⚠️ Không có auto nào.")
        return

    if not context.args:
        await update.message.reply_text("❌ /stopbuff <username|all>")
        return

    if context.args[0] == "all":
        for job in AUTO_JOBS[uid].values():
            job.schedule_removal()
        AUTO_JOBS[uid].clear()
        await update.message.reply_text("🛑 Đã dừng toàn bộ auto.")
        return

    username = context.args[0].lstrip("@")
    job = AUTO_JOBS[uid].pop(username, None)
    if job:
        job.schedule_removal()
        await update.message.reply_text(f"🛑 Đã dừng @{username}")
    else:
        await update.message.reply_text("⚠️ Không tìm thấy user.")

# ================== MAIN ==================
def main():
    keep_alive()  # 🔥 giữ bot sống (Render/Replit)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("stopbuff", stopbuff))

    logging.info("🤖 BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
