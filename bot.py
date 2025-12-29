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
)
from keep_alive import keep_alive

# ================= CONFIG =================
BOT_TOKEN = "8080338995:AAHitAzhTUUb1XL0LB44BiJmOCgulA4fx38"
ADMINS = [5736655322]

API_DELAY = 36           # delay trước mỗi lần gọi API
MIN_INTERVAL = 60        # auto buff tối thiểu (giây)

# ================= GLOBAL =================
AUTO_JOBS = {}               # {uid: job}
AUTO_LAST_FOLLOWERS = {}     # {uid: followers}
AUTO_STATS = {}              # {uid: {date, count}}
USER_COOLDOWN = {}           # {uid: timestamp}

session: aiohttp.ClientSession | None = None

# ================= LOG =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ================= UTILS =================
def is_admin(uid: int) -> bool:
    return uid in ADMINS


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
async def get_session() -> aiohttp.ClientSession:
    global session
    if session is None or session.closed:
        timeout = aiohttp.ClientTimeout(total=40)
        session = aiohttp.ClientSession(timeout=timeout)
    return session


# ================= API =================
async def call_buff_api_check(username: str) -> dict:
    """
    Tự động gọi API:
    - thử fl1
    - lỗi thì fallback fl2
    """
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

            except asyncio.TimeoutError:
                continue
            except Exception:
                continue

        return {"success": False, "message": "API fl1 & fl2 đều lỗi"}

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


# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 BOT BUFF TELEGRAM 24/7\n\n"
        "/buff <username>\n"
        "/autobuffme [giây]\n"
        "/stopbuff\n"
        "/stat\n"
        "/help"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 HƯỚNG DẪN SỬ DỤNG\n\n"
        "• /buff <username>\n"
        "• /autobuffme [giây]\n"
        "• /stopbuff\n"
        "• /stat\n\n"
        "⛔ /autobuff chỉ dành cho admin\n"
        "📩 Vui lòng ib admin để được dùng"
    )


# ================= /buff =================
async def run_buff(username: str, update: Update):
    try:
        await asyncio.sleep(API_DELAY)
        data = await call_buff_api_check(username)

        if data.get("success"):
            await update.message.reply_text(format_result(data))
        else:
            await update.message.reply_text(f"❌ {data.get('message')}")

    except Exception:
        logging.exception("BUFF ERROR")
        await update.message.reply_text("❌ Lỗi hệ thống")


async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not context.args:
        await update.message.reply_text("❌ /buff <username>")
        return

    now = time.time()
    if now - USER_COOLDOWN.get(uid, 0) < 30:
        await update.message.reply_text("⏳ Vui lòng chờ 30 giây.")
        return

    USER_COOLDOWN[uid] = now
    username = context.args[0]

    await update.message.reply_text(f"⏳ Đang buff @{username}...")
    asyncio.create_task(run_buff(username, update))


# ================= AUTO BUFF CORE =================
async def run_auto_buff(username: str, chat_id: int, context, uid: int):
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
            f"🔁 Lần auto buff hôm nay: {count_today}"
        )

        await context.bot.send_message(chat_id=chat_id, text=msg)

    except Exception:
        logging.exception("AUTO BUFF ERROR")


def start_auto_job(context, username, chat_id, uid, interval):
    async def job_callback(c):
        await run_auto_buff(username, chat_id, c, uid)

    return context.job_queue.run_repeating(
        job_callback,
        interval=interval,
        first=0
    )


# ================= /autobuff (ADMIN) =================
async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not is_admin(uid):
        await update.message.reply_text("❌ Chỉ admin được dùng.")
        return

    if not context.args:
        await update.message.reply_text("❌ /autobuff <username> [giây]")
        return

    username = context.args[0]
    interval = 900

    if len(context.args) >= 2:
        try:
            interval = int(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Giây phải là số.")
            return

    if interval < MIN_INTERVAL:
        await update.message.reply_text("⚠️ Tối thiểu 60 giây.")
        return

    if uid in AUTO_JOBS:
        await update.message.reply_text("⚠️ Auto buff đang chạy.")
        return

    job = start_auto_job(
        context,
        username,
        update.effective_chat.id,
        uid,
        interval
    )

    AUTO_JOBS[uid] = job
    AUTO_LAST_FOLLOWERS[uid] = None

    await update.message.reply_text(
        f"✅ Auto buff @{username}\n⏱ {interval // 60} phút"
    )


# ================= /autobuffme =================
async def autobuffme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = update.effective_user.username

    if not username:
        await update.message.reply_text("❌ Bạn chưa có username.")
        return

    interval = 900
    if context.args:
        try:
            interval = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Giây phải là số.")
            return

    if interval < MIN_INTERVAL:
        await update.message.reply_text("⚠️ Tối thiểu 60 giây.")
        return

    if uid in AUTO_JOBS:
        await update.message.reply_text("⚠️ Auto buff đang chạy.")
        return

    job = start_auto_job(
        context,
        username,
        update.effective_chat.id,
        uid,
        interval
    )

    AUTO_JOBS[uid] = job
    AUTO_LAST_FOLLOWERS[uid] = None

    await update.message.reply_text(
        f"✅ Auto buff @{username}\n⏱ {interval // 60} phút"
    )


# ================= /stopbuff =================
async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    job = AUTO_JOBS.pop(uid, None)

    if job:
        job.schedule_removal()
        await update.message.reply_text("🛑 Đã dừng auto buff.")
    else:
        await update.message.reply_text("⚠️ Chưa bật auto buff.")


# ================= /stat =================
async def stat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    today = datetime.now().strftime("%Y-%m-%d")

    if uid not in AUTO_STATS or AUTO_STATS[uid]["date"] != today:
        await update.message.reply_text("📊 Hôm nay chưa auto buff.")
        return

    count = AUTO_STATS[uid]["count"]
    await update.message.reply_text(
        f"📊 THỐNG KÊ HÔM NAY\n\n"
        f"🔁 Số lần auto buff: {count}"
    )


# ================= MAIN =================
def main():
    keep_alive()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("autobuffme", autobuffme))
    app.add_handler(CommandHandler("stopbuff", stopbuff))
    app.add_handler(CommandHandler("stat", stat))

    logging.info("🤖 BOT ĐANG CHẠY...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
