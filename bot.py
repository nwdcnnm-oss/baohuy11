import time
import asyncio
import requests
import getpass
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

# ================== NHẬP TOKEN KHI CHẠY ==================
print("8080338995:AAHitAzhTUUb1XL0LB44BiJmOCgulA4fx38")
BOT_TOKEN = getpass.getpass("> ")
if not BOT_TOKEN:
    raise RuntimeError("❌ Chưa nhập BOT TOKEN")

# ================== API ==================
API_URL = "https://abcdxyz310107.x10.mx/apifl.php"

# ================== ADMIN ==================
OWNER_ID = 5736655322
ADMIN_IDS = {OWNER_ID}

ADMIN_DENY_TEXT = (
    "❌ **Chỉ admin được sử dụng bot**\n"
    "📩 **Vui lòng IB admin để được cấp quyền**"
)

DELAY_SECONDS = 20
MAX_AUTO_MINUTES = 180
user_auto_task = {}

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

async def deny_if_not_admin(update: Update):
    await update.message.reply_text(ADMIN_DENY_TEXT, parse_mode="Markdown")

# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await deny_if_not_admin(update)
        return
    await update.message.reply_text(
        "🤖 **BOT ADMIN PANEL**\n\n"
        "/chay\n"
        "/buff <username>\n"
        "/auto <phút> <username>\n"
        "/stop\n"
        "/addadmin <user_id>\n"
        "/deladmin <user_id>\n"
        "/listadmin",
        parse_mode="Markdown"
    )

async def chay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await deny_if_not_admin(update)
        return
    status = "🔁 Auto đang chạy" if update.effective_user.id in user_auto_task else "🟢 Bot rảnh"
    await update.message.reply_text(f"✅ Bot đang hoạt động\n📡 {status}")

# ================== ADMIN MANAGER ==================
async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await deny_if_not_admin(update)
        return
    if not context.args:
        await update.message.reply_text("❌ /addadmin <user_id>")
        return
    try:
        new_id = int(context.args[0])
        ADMIN_IDS.add(new_id)
        await update.message.reply_text(f"✅ Đã thêm admin: `{new_id}`", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ user_id không hợp lệ")

async def deladmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await deny_if_not_admin(update)
        return
    if not context.args:
        await update.message.reply_text("❌ /deladmin <user_id>")
        return
    try:
        del_id = int(context.args[0])
        if del_id == OWNER_ID:
            await update.message.reply_text("❌ Không thể xoá owner")
            return
        ADMIN_IDS.discard(del_id)
        await update.message.reply_text(f"🗑️ Đã xoá admin: `{del_id}`", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ user_id không hợp lệ")

async def listadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await deny_if_not_admin(update)
        return
    text = "📋 **Danh sách Admin**\n" + "\n".join(f"- `{i}`" for i in ADMIN_IDS)
    await update.message.reply_text(text, parse_mode="Markdown")

# ================== BUFF ==================
async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await deny_if_not_admin(update)
        return
    if not context.args:
        await update.message.reply_text("❌ /buff <username>")
        return

    username = context.args[0]
    await update.message.reply_text(f"⏳ Đang xử lý, đợi {DELAY_SECONDS}s...")
    await asyncio.sleep(DELAY_SECONDS)

    try:
        requests.get(API_URL, params={"username": username}, timeout=15)
        await update.message.reply_text(
            "🎉 **TĂNG FOLLOW THÀNH CÔNG** 🎉\n"
            "@\n\n"
            "UID:\n"
            f"Nickname: `{username}`\n\n"
            "FOLLOW BAN ĐẦU:\n"
            "FOLLOW ĐÃ TĂNG:\n"
            "FOLLOW HIỆN TẠI:",
            parse_mode="Markdown"
        )
    except Exception:
        await update.message.reply_text("❌ Lỗi kết nối API")

# ================== AUTO ==================
async def auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await deny_if_not_admin(update)
        return

    if uid in user_auto_task:
        await update.message.reply_text("⚠️ Auto đang chạy, dùng /stop để dừng")
        return

    if len(context.args) < 2:
        await update.message.reply_text("❌ /auto <phút> <username>")
        return

    try:
        minutes = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ <phút> phải là số")
        return

    if minutes <= 0 or minutes > MAX_AUTO_MINUTES:
        await update.message.reply_text(f"❌ Thời gian: 1–{MAX_AUTO_MINUTES} phút")
        return

    username = context.args[1]
    end_time = time.time() + minutes * 60

    async def job():
        count = 0
        try:
            while time.time() < end_time:
                requests.get(API_URL, params={"username": username}, timeout=15)
                count += 1
                await asyncio.sleep(DELAY_SECONDS)
        except asyncio.CancelledError:
            await update.message.reply_text("🛑 Auto đã dừng")
        finally:
            user_auto_task.pop(uid, None)
            await update.message.reply_text(f"✅ Kết thúc auto\nTổng lượt: {count}")

    user_auto_task[uid] = asyncio.create_task(job())
    await update.message.reply_text(
        f"▶️ Bắt đầu auto `{minutes}` phút cho `{username}`",
        parse_mode="Markdown"
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await deny_if_not_admin(update)
        return
    task = user_auto_task.get(uid)
    if not task:
        await update.message.reply_text("ℹ️ Không có auto đang chạy")
        return
    task.cancel()
    await update.message.reply_text("🛑 Đã dừng auto")

# ================== MAIN ==================
def main():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chay", chay))
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("auto", auto))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("addadmin", addadmin))
    app.add_handler(CommandHandler("deladmin", deladmin))
    app.add_handler(CommandHandler("listadmin", listadmin))

    app.run_polling()

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print("♻️ Restart bot:", e)
            time.sleep(5)
