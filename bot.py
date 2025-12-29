import aiohttp
import asyncio
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

# ================== CẤU HÌNH ==================
BOT_TOKEN = "8080338995:AAHitAzhTUUb1XL0LB44BiJmOCgulA4fx38"

ALLOWED_GROUP_ID = -1002666964512
ADMINS = [5736655322]

API_FL1 = "https://abcdxyz310107.x10.mx/apifl.php?fl1={}"
API_FL2 = "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"

WRONG_GROUP_MSG = (
    "❌ *Xin lỗi, bot này chỉ hoạt động trong nhóm này:*\n"
    "👉 https://t.me/baohuydevs"
)

NO_ADMIN_MSG = "🔒 Lệnh này chỉ admin mới được sử dụng."

AUTO_BUFF_USERS = {}
TIMEOUT = aiohttp.ClientTimeout(total=15)
# =============================================


# ---------- CHECK GROUP ----------
async def check_group(update: Update):
    chat = update.effective_chat
    if not chat or chat.id != ALLOWED_GROUP_ID:
        if update.message:
            await update.message.reply_text(
                WRONG_GROUP_MSG,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        return False
    return True


# ---------- CHECK ADMIN ----------
def is_admin(user_id: int):
    return user_id in ADMINS


# ---------- CALL API (aiohttp) ----------
async def call_api(session, url):
    try:
        async with session.get(url) as r:
            if r.status == 200:
                text = await r.text()
                return text.strip()
    except:
        pass
    return ""


# ---------- PARSE FOLLOW ----------
def parse_follow_data(text):
    if not text:
        return None

    nickname = re.search(r'nickname[:\s]*([^\n\r]+)', text, re.IGNORECASE)
    before = re.search(r'follow\s*trước[:\s]*(\d+)', text, re.IGNORECASE)
    plus = re.search(r'\+(\d+)', text)

    return {
        "nickname": nickname.group(1).strip() if nickname else "Không rõ",
        "before": int(before.group(1)) if before else 0,
        "plus": int(plus.group(1)) if plus else 0
    }


# ---------- FORMAT KẾT QUẢ ----------
def format_buff_success(username, nickname, before, plus):
    after = before + plus
    return (
        "✅ *BUFF THÀNH CÔNG*\n\n"
        f"👤 @{username}\n"
        f"Nickname: {nickname}\n"
        f"Follow trước: {before}\n"
        f"Follow tăng: +{plus}\n"
        f"Follow hiện tại: {after}"
    )


# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update):
        return

    await update.message.reply_text(
        "🤖 *Bot Buff Follow*\n\n"
        "/buff <username>\n"
        "/autobuff <username> (admin)\n"
        "/stopbuff (admin)",
        parse_mode="Markdown"
    )


# ---------- /buff ----------
async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update):
        return

    if len(context.args) != 1:
        await update.message.reply_text("❌ /buff <username>")
        return

    username = context.args[0]
    await update.message.reply_text("⏳ Đang buff, vui lòng chờ...")

    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        res1, res2 = await asyncio.gather(
            call_api(session, API_FL1.format(username)),
            call_api(session, API_FL2.format(username)),
        )

    d1 = parse_follow_data(res1)
    d2 = parse_follow_data(res2)

    if not d1 and not d2:
        return

    nickname = d1["nickname"] if d1 else d2["nickname"]
    before = d1["before"] if d1 else d2["before"]
    plus = (d1["plus"] if d1 else 0) + (d2["plus"] if d2 else 0)

    await update.message.reply_text(
        format_buff_success(username, nickname, before, plus),
        parse_mode="Markdown"
    )


# ---------- AUTOBUFF JOB ----------
async def autobuff_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    username = context.job.data

    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        res1, res2 = await asyncio.gather(
            call_api(session, API_FL1.format(username)),
            call_api(session, API_FL2.format(username)),
        )

    d1 = parse_follow_data(res1)
    d2 = parse_follow_data(res2)
    if not d1 and not d2:
        return

    nickname = d1["nickname"] if d1 else d2["nickname"]
    before = d1["before"] if d1 else d2["before"]
    plus = (d1["plus"] if d1 else 0) + (d2["plus"] if d2 else 0)

    await context.bot.send_message(
        chat_id,
        format_buff_success(username, nickname, before, plus),
        parse_mode="Markdown"
    )


# ---------- /autobuff (ADMIN ONLY) ----------
async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update):
        return

    if not is_admin(update.effective_user.id):
        await update.message.reply_text(NO_ADMIN_MSG)
        return

    if len(context.args) != 1:
        await update.message.reply_text("❌ /autobuff <username>")
        return

    chat_id = update.effective_chat.id
    username = context.args[0]

    if chat_id in AUTO_BUFF_USERS:
        await update.message.reply_text("⚠️ Autobuff đang chạy")
        return

    AUTO_BUFF_USERS[chat_id] = username

    context.job_queue.run_repeating(
        autobuff_job,
        interval=900,
        first=0,
        chat_id=chat_id,
        data=username,
        name=str(chat_id)
    )

    await update.message.reply_text(
        f"✅ Autobuff đã bật\n👤 `{username}`\n⏱ 15 phút / lần",
        parse_mode="Markdown"
    )


# ---------- /stopbuff (ADMIN ONLY) ----------
async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update):
        return

    if not is_admin(update.effective_user.id):
        await update.message.reply_text(NO_ADMIN_MSG)
        return

    chat_id = update.effective_chat.id
    for job in context.job_queue.get_jobs_by_name(str(chat_id)):
        job.schedule_removal()

    AUTO_BUFF_USERS.pop(chat_id, None)
    await update.message.reply_text("🛑 Autobuff đã dừng")


# ---------- MAIN ----------
def main():
    keep_alive()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("stopbuff", stopbuff))

    print("🤖 Bot đang chạy (aiohttp)...")
    app.run_polling()


if __name__ == "__main__":
    main()
