#!/usr/bin/env python3
import time
import asyncio
import aiohttp
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from keep_alive import keep_alive

# ================= CONFIG =================
BOT_TOKEN = "8080338995:AAHitAzhTUUb1XL0LB44BiJmOCgulA4fx38"
ADMINS = [5736655322]

ALLOWED_GROUP_ID = -1002666964512  # 🔒 NHÓM DUY NHẤT
API_DELAY = 36
AUTO_INTERVAL = 900  # 15 phút

# ================= GLOBAL =================
AUTO_JOBS = {}
AUTO_LAST_FOLLOWERS = {}
AUTO_STATS = {}
USER_COOLDOWN = {}
session = None

# ================= LOG =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ================= UTILS =================
def is_admin(uid: int) -> bool:
    return uid in ADMINS


def allow_group_only(update: Update) -> bool:
    chat = update.effective_chat
    return chat and chat.id == ALLOWED_GROUP_ID


def increase_auto_count(uid: int) -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    if uid not in AUTO_STATS:
        AUTO_STATS[uid] = {"date": today, "count": 0}
    if AUTO_STATS[uid]["date"] != today:
        AUTO_STATS[uid]["date"] = today
        AUTO_STATS[uid]["count"] = 0
    AUTO_STATS[uid]["count"] += 1
    return AUTO_STATS[uid]["count"]


# ================= SESSION =================
async def get_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=40)
        )
    return session


# ================= API =================
async def call_buff_api_check(username: str) -> dict:
    urls = [
        f"https://abcdxyz310107.x10.mx/apifl.php?fl1={username}",
        f"https://abcdxyz310107.x10.mx/apifl.php?fl2={username}",
    ]
    try:
        s = await get_session()
        for url in urls:
            try:
                async with s.get(url) as res:
                    if res.status != 200:
                        continue
                    data = await res.json(content_type=None)
                    if data.get("success"):
                        return data
            except Exception:
                continue
        return {"success": False, "message": "API lỗi"}
    except Exception:
        logging.exception("API ERROR")
        return {"success": False, "message": "Lỗi hệ thống"}


def format_result(data: dict) -> str:
    return (
        "✅ BUFF THÀNH CÔNG\n\n"
        f"👤 @{data.get('username','?')}\n"
        f"Nickname: {data.get('nickname','.')}\n"
        f"Follow trước: {data.get('followers_before')}\n"
        f"Follow tăng: +{data.get('followers_increased')}\n"
        f"Follow hiện tại: {data.get('followers_now')}"
    )


# ================= AUTO LEAVE GROUP =================
async def guard_and_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat:
        return

    # Nếu là group/supergroup và KHÔNG phải nhóm cho phép → leave ngay
    if chat.type in ("group", "supergroup") and chat.id != ALLOWED_GROUP_ID:
        try:
            await context.bot.leave_chat(chat.id)
            logging.info(f"🚪 Left unauthorized group: {chat.id}")
        except Exception:
            pass


# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allow_group_only(update):
        return
    await update.message.reply_text(
        "🤖 BOT BUFF TELEGRAM 24/7\n\n"
        "/buff <username>\n"
        "/autobuff <username>\n"
        "/stopbuff\n"
        "/stat"
    )


# ================= /buff =================
async def run_buff(username, update):
    await asyncio.sleep(API_DELAY)
    data = await call_buff_api_check(username)
    if data.get("success"):
        await update.message.reply_text(format_result(data))
    else:
        await update.message.reply_text(f"❌ {data.get('message')}")


async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allow_group_only(update):
        return

    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❌ /buff <username>")
        return

    now = time.time()
    if now - USER_COOLDOWN.get(uid, 0) < 30:
        await update.message.reply_text("⏳ Chờ 30s.")
        return

    USER_COOLDOWN[uid] = now
    username = context.args[0]
    await update.message.reply_text(f"⏳ Đang buff @{username}...")
    asyncio.create_task(run_buff(username, update))


# ================= AUTO CORE =================
async def run_auto_buff(username, chat_id, context, uid):
    try:
        await asyncio.sleep(API_DELAY)
        data = await call_buff_api_check(username)
        if not data.get("success"):
            return

        followers_now = int(data.get("followers_now", 0))
        last = AUTO_LAST_FOLLOWERS.get(uid)
        if last is not None and followers_now <= last:
            return

        AUTO_LAST_FOLLOWERS[uid] = followers_now
        count_today = increase_auto_count(uid)

        msg = (
            "🤖 AUTO BUFF\n\n"
            f"👤 @{username}\n"
            f"Follow trước: {data.get('followers_before')}\n"
            f"Follow tăng: +{data.get('followers_increased')}\n"
            f"Follow hiện tại: {followers_now}\n\n"
            f"🔁 Lần auto hôm nay: {count_today}"
        )
        await context.bot.send_message(chat_id=chat_id, text=msg)
    except Exception:
        logging.exception("AUTO ERROR")


def start_auto_job(context, username, chat_id, uid):
    async def job_callback(c):
        await run_auto_buff(username, chat_id, c, uid)

    return context.job_queue.run_repeating(
        job_callback,
        interval=AUTO_INTERVAL,
        first=0
    )


# ================= /autobuff =================
async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allow_group_only(update):
        return

    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ Chỉ admin được dùng.")
        return

    if not context.args:
        await update.message.reply_text("❌ /autobuff <username>")
        return

    if uid in AUTO_JOBS:
        await update.message.reply_text("⚠️ Auto buff đang chạy.")
        return

    username = context.args[0]
    job = start_auto_job(
        context,
        username,
        update.effective_chat.id,
        uid
    )

    AUTO_JOBS[uid] = job
    AUTO_LAST_FOLLOWERS[uid] = None

    await update.message.reply_text(
        f"✅ Auto buff @{username}\n"
        f"⏱ Chu kỳ: 900 giây (15 phút)\n"
        f"♾️ Trạng thái: TREO VĨNH VIỄN"
    )


# ================= /stopbuff =================
async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allow_group_only(update):
        return

    uid = update.effective_user.id
    job = AUTO_JOBS.pop(uid, None)
    if job:
        job.schedule_removal()
        await update.message.reply_text("🛑 Đã dừng auto buff.")
    else:
        await update.message.reply_text("⚠️ Chưa bật auto buff.")


# ================= /stat =================
async def stat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allow_group_only(update):
        return

    uid = update.effective_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    if uid not in AUTO_STATS or AUTO_STATS[uid]["date"] != today:
        await update.message.reply_text("📊 Hôm nay chưa auto.")
        return
    await update.message.reply_text(
        f"📊 HÔM NAY AUTO: {AUTO_STATS[uid]['count']} lần"
    )


# ================= MAIN =================
def main():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 🔒 GUARD: tự động rời nhóm khác
    app.add_handler(MessageHandler(filters.ALL, guard_and_leave), group=0)

    # Commands (chỉ chạy trong nhóm cho phép)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("stopbuff", stopbuff))
    app.add_handler(CommandHandler("stat", stat))

    logging.info("🤖 BOT ĐANG CHẠY (GROUP-LOCKED)...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()

