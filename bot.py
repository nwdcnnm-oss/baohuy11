import asyncio
import aiohttp
import pytz
import time
import json
import re
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from keep_alive import keep_alive

# ================= CONFIG =================
BOT_TOKEN = "8080338995:AAHI8yhEUnJGgqEIDcaJ0eIKBGtuQpzQiX8"

ALLOWED_GROUP_ID = -1002666964512
ADMINS = [5736655322]

API_FL1 = "https://abcdxyz310107.x10.mx/apifl.php?fl1={}"
API_FL2 = "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"

VIETNAM_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

API_TIMEOUT = 36
API_RETRY = 11
API_COOLDOWN = 600   # 10 phút
AUTO_BUFF_DELAY = 60
# =========================================

session_instance = None
auto_buff_running = False

api_status = {
    "API_FL1": 0,
    "API_FL2": 0
}

# ================= SESSION =================
async def get_session():
    global session_instance
    if session_instance is None or session_instance.closed:
        session_instance = aiohttp.ClientSession()
    return session_instance

# ================= UTILS =================
async def check_group(update: Update):
    if update.effective_chat.id != ALLOWED_GROUP_ID:
        await update.message.reply_text(
            "❌ Xin lỗi, bot này chỉ hoạt động trong nhóm này:\n"
            "👉 https://t.me/baohuydevs"
        )
        return False
    return True

def is_admin(uid: int):
    return uid in ADMINS

def now_vn():
    return datetime.now(VIETNAM_TZ).strftime("%H:%M:%S")

# ================= FORMAT =================
def format_result(username, name, before, added):
    total = before + added
    return (
        "📊 KẾT QUẢ KIỂM TRA\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 User: @{username}\n"
        f"🏷 Tên: {name}\n"
        f"📉 Gốc: {before}\n"
        f"📈 Tăng: +{added}\n"
        f"📊 Tổng: {total}\n"
        f"🕒 Lúc: {now_vn()}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

# ================= API CORE =================
def api_available(name: str):
    return time.time() >= api_status.get(name, 0)

async def call_api_safe(name: str, url: str):
    if not api_available(name):
        return None

    session = await get_session()

    for _ in range(API_RETRY + 1):
        try:
            async with session.get(url, timeout=API_TIMEOUT) as r:
                return await r.text()
        except:
            pass

    api_status[name] = time.time() + API_COOLDOWN
    return None

# ================= BUFF CORE =================
async def do_buff(target_id: str):
    tasks = []

    if api_available("API_FL1"):
        tasks.append(call_api_safe("API_FL1", API_FL1.format(target_id)))
    if api_available("API_FL2"):
        tasks.append(call_api_safe("API_FL2", API_FL2.format(target_id)))

    if not tasks:
        return format_result(target_id, target_id, 0, 0)

    results = await asyncio.gather(*tasks)
    raw = next((r for r in results if r), None)

    username = target_id
    name = target_id
    before = 0
    after = 0

    if raw:
        try:
            data = json.loads(raw)
            username = data.get("username", target_id)
            name = data.get("name", username)
            before = int(data.get("before", data.get("old", 0)))
            after = int(data.get("after", data.get("new", before)))
        except:
            nums = list(map(int, re.findall(r"\d+", raw)))
            if len(nums) >= 2:
                before, after = nums[0], nums[-1]
            elif len(nums) == 1:
                before = after = nums[0]

    added = max(after - before, 0)
    return format_result(username, name, before, added)

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update):
        return
    await update.message.reply_text(
        "🤖 Bot BUFF đang hoạt động\n\n"
        "📌 /buff <id>\n"
        "♻️ /autobuff\n"
        "🛑 /stopbuff"
    )

async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update):
        return
    if not context.args:
        await update.message.reply_text("❌ /buff <user_id>")
        return

    msg = await update.message.reply_text("⏳ Đang xử lý...")
    await msg.edit_text(await do_buff(context.args[0]))

async def auto_buff_loop(app):
    global auto_buff_running
    while auto_buff_running:
        try:
            text = await do_buff("auto")
            await app.bot.send_message(ALLOWED_GROUP_ID, text)
        except Exception as e:
            print("AUTO BUFF ERROR:", e)
        await asyncio.sleep(AUTO_BUFF_DELAY)

async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global auto_buff_running
    if not await check_group(update):
        return
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Chỉ ADMIN được dùng /autobuff")
        return
    if auto_buff_running:
        await update.message.reply_text("⚠️ AUTO BUFF đang chạy")
        return

    auto_buff_running = True
    context.application.create_task(auto_buff_loop(context.application))
    await update.message.reply_text("✅ Đã BẬT AUTO BUFF")

async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global auto_buff_running
    if not await check_group(update):
        return
    if not is_admin(update.effective_user.id):
        return

    auto_buff_running = False
    await update.message.reply_text("🛑 Đã TẮT AUTO BUFF")

# ================= MAIN =================
def main():
    keep_alive()  # ♻️ treo Render

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("stopbuff", stopbuff))

    print("🤖 Bot đang chạy (FULL – STABLE)...")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
