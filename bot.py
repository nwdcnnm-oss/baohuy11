import aiohttp
import asyncio
import re
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import BadRequest
# Nếu bạn chạy trên Replit/Render thì giữ dòng này, nếu chạy máy cá nhân thì xóa
try:
    from keep_alive import keep_alive
except ImportError:
    def keep_alive(): pass

# ================== CẤU HÌNH ==================
# ⚠️ CẢNH BÁO: Đừng để lộ Token công khai. Hãy dán lại token của bạn vào dưới đây.
BOT_TOKEN = "8080338995:AAGJcUCZvBaLSjgHJfjpiWK6a-xFBa4TCEU" 

ALLOWED_GROUP_ID = -1002666964512
ADMINS = [5736655322]

API_FL1 = "https://abcdxyz310107.x10.mx/apifl.php?fl1={}"
API_FL2 = "https://abcdxyz310107.x10.mx/apifl.php?fl2={}"

# Giả lập trình duyệt để tránh bị chặn IP
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

WRONG_GROUP_MSG = (
    "❌ *Xin lỗi, bot này chỉ hoạt động trong nhóm này:*\n"
    "👉 https://t.me/baohuydevs"
)

NO_ADMIN_MSG = "🔒 Lệnh này chỉ admin mới được sử dụng."
TIMEOUT = aiohttp.ClientTimeout(total=20)

# Logger để theo dõi lỗi
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# chat_id: { username, message_id }
AUTO_BUFF = {}
# =============================================


# ---------- CHECK GROUP ----------
async def check_group(update: Update):
    chat = update.effective_chat
    if not chat:
        return False
    
    # Cho phép chat riêng với Admin hoặc trong nhóm quy định
    if chat.id != ALLOWED_GROUP_ID and update.effective_user.id not in ADMINS:
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


# ---------- CALL API ----------
async def call_api(session, url):
    try:
        async with session.get(url, headers=HEADERS) as r:
            if r.status == 200:
                return (await r.text()).strip()
    except Exception as e:
        logging.error(f"Lỗi gọi API {url}: {e}")
    return ""


# ---------- PARSE DATA ----------
def parse_follow_data(text):
    if not text:
        return None

    # Regex linh hoạt hơn một chút
    nickname = re.search(r'nickname[:\s]*([^\n\r]+)', text, re.IGNORECASE)
    before = re.search(r'follow\s*(?:trước|cũ)[:\s]*(\d+)', text, re.IGNORECASE)
    plus = re.search(r'\+(\d+)', text)

    return {
        "nickname": nickname.group(1).strip() if nickname else "Đang cập nhật...",
        "before": int(before.group(1)) if before else 0,
        "plus": int(plus.group(1)) if plus else 0
    }


# ---------- FORMAT ----------
def format_success(username, nickname, before, plus):
    total = before + plus
    return (
        "✅ *BUFF THÀNH CÔNG*\n\n"
        f"👤 User: @{username}\n"
        f"🏷 Tên: {nickname}\n"
        f"📉 Ban đầu: {before}\n"
        f"📈 Đã tăng: +{plus}\n"
        f"📊 Tổng follow: {total}"
    )


# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update):
        return

    await update.message.reply_text(
        "🤖 *Bot Buff Follow*\n\n"
        "1️⃣ `/buff <username>` : Check tay\n"
        "2️⃣ `/autobuff <username>` : Tự động cập nhật (Admin)\n"
        "3️⃣ `/stopbuff` : Dừng tự động (Admin)",
        parse_mode="Markdown"
    )


# ---------- /buff ----------
async def buff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update):
        return

    if not context.args:
        await update.message.reply_text("❌ Sử dụng: `/buff <username>`", parse_mode="Markdown")
        return

    username = context.args[0].replace("@", "") # Xóa @ nếu người dùng lỡ nhập

    wait_msg = await update.message.reply_text("⏳ *Đang kết nối API...*", parse_mode="Markdown")

    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        res1, res2 = await asyncio.gather(
            call_api(session, API_FL1.format(username)),
            call_api(session, API_FL2.format(username))
        )

    d1 = parse_follow_data(res1)
    d2 = parse_follow_data(res2)

    if not d1 and not d2:
        await wait_msg.edit_text("⚠️ *Lỗi: Không lấy được dữ liệu từ API (Có thể web đang bảo trì)*", parse_mode="Markdown")
        return

    # Ưu tiên lấy data từ nguồn nào có
    data_source = d1 if d1 else d2
    nickname = data_source["nickname"]
    before = data_source["before"]
    
    # Cộng dồn số tăng từ cả 2 nguồn (nếu logic của bạn là 2 server buff khác nhau)
    plus = (d1["plus"] if d1 else 0) + (d2["plus"] if d2 else 0)

    await wait_msg.edit_text(
        format_success(username, nickname, before, plus),
        parse_mode="Markdown"
    )


# ---------- AUTOBUFF JOB ----------
async def autobuff_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    data = AUTO_BUFF.get(chat_id)
    
    if not data:
        context.job.schedule_removal() # Nếu không có dữ liệu thì hủy job luôn
        return

    username = data["username"]
    message_id = data["message_id"]

    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        res1, res2 = await asyncio.gather(
            call_api(session, API_FL1.format(username)),
            call_api(session, API_FL2.format(username))
        )

    d1 = parse_follow_data(res1)
    d2 = parse_follow_data(res2)

    if not d1 and not d2:
        return # API lỗi thì bỏ qua lần này, đợi lần sau

    data_source = d1 if d1 else d2
    nickname = data_source["nickname"]
    before = data_source["before"]
    plus = (d1["plus"] if d1 else 0) + (d2["plus"] if d2 else 0)

    new_text = format_success(username, nickname, before, plus)

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=new_text,
            parse_mode="Markdown"
        )
    except BadRequest as e:
        # Bỏ qua lỗi nếu nội dung tin nhắn giống hệt tin nhắn cũ (Message is not modified)
        if "Message is not modified" in str(e):
            pass
        else:
            logging.error(f"Lỗi edit message: {e}")
    except Exception as e:
        logging.error(f"Lỗi không xác định trong job: {e}")


# ---------- /autobuff (ADMIN) ----------
async def autobuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update):
        return

    if not is_admin(update.effective_user.id):
        await update.message.reply_text(NO_ADMIN_MSG)
        return

    if not context.args:
        await update.message.reply_text("❌ Sử dụng: `/autobuff <username>`", parse_mode="Markdown")
        return

    chat_id = update.effective_chat.id
    username = context.args[0].replace("@", "")

    if chat_id in AUTO_BUFF:
        await update.message.reply_text("⚠️ Autobuff đang chạy ở nhóm này rồi. Dùng /stopbuff trước.")
        return

    msg = await update.message.reply_text(
        f"⏳ *Đã bật Autobuff cho:* {username}\n(Cập nhật mỗi 15 phút)",
        parse_mode="Markdown"
    )

    AUTO_BUFF[chat_id] = {
        "username": username,
        "message_id": msg.message_id
    }

    context.job_queue.run_repeating(
        autobuff_job,
        interval=900, # 900 giây = 15 phút
        first=10,     # Chạy lần đầu sau 10 giây
        chat_id=chat_id,
        name=str(chat_id)
    )


# ---------- /stopbuff ----------
async def stopbuff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update):
        return

    if not is_admin(update.effective_user.id):
        await update.message.reply_text(NO_ADMIN_MSG)
        return

    chat_id = update.effective_chat.id
    
    # Xóa job theo tên (tên job = chat_id)
    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if not jobs:
        await update.message.reply_text("⚠️ Hiện không có Autobuff nào đang chạy.")
        return

    for job in jobs:
        job.schedule_removal()

    AUTO_BUFF.pop(chat_id, None)
    await update.message.reply_text("🛑 Đã dừng Autobuff thành công.")


# ---------- MAIN ----------
def main():
    keep_alive() # Chỉ hoạt động nếu có file keep_alive.py

    print("🚀 Bot đang khởi động...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buff", buff))
    app.add_handler(CommandHandler("autobuff", autobuff))
    app.add_handler(CommandHandler("stopbuff", stopbuff))

    app.run_polling()

if __name__ == "__main__":
    main()
