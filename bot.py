import json, os, traceback, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from keep_alive import keep_alive

# ====== KEEP ALIVE (RENDER/REPLIT) ======
keep_alive()

# ====== CONFIG ======
TOKEN = "6367532329:AAFwf8IiA6VxhysLCr30dwvPYY7gn2XypWA"   # <-- DÁN TOKEN BOT CỦA BẠN
ADMIN_ID = 5736655322     # <-- ID TELEGRAM ADMIN
MY_QR_IMAGE = "qr_bank.jpg"

PRICE_FILE = "price.json"
USERS_FILE = "users.json"
STOCK_FILE = "stock.json"
SOLD_FILE = "sold.json"
PENDING_FILE = "pending.json"

logging.basicConfig(level=logging.INFO)

# ====== JSON UTILS ======
def load_json(file, default):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump(default, f)
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_users(): return load_json(USERS_FILE, {})
def get_stock(): return load_json(STOCK_FILE, [])
def get_sold(): return load_json(SOLD_FILE, [])
def get_pending(): return load_json(PENDING_FILE, {})
def get_price(): return load_json(PRICE_FILE, {"price": 1000}).get("price", 1000)

def is_admin(update: Update):
    return update.effective_user and update.effective_user.id == ADMIN_ID

# ====== USER ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = get_price()
    msg = (
        "🖥 HỆ THỐNG BÁN RDP\n\n"
        "🔹 /qr - Xem QR nạp tiền\n"
        "🔹 /nap <số tiền>\n"
        "🔹 /balance - Xem số dư\n"
        f"🔹 /buyrd - Mua 1 RDP (Giá {price:,}đ)\n"
        "🔹 /stockrd - Xem kho"
    )
    await update.message.reply_text(msg)

async def send_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(MY_QR_IMAGE):
        with open(MY_QR_IMAGE, "rb") as f:
            await update.message.reply_photo(
                f,
                caption="💳 Quét QR để chuyển khoản\nSau đó dùng: /nap 50000"
            )
    else:
        await update.message.reply_text("❌ Chưa có ảnh QR.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    bal = get_users().get(uid, 0)
    await update.message.reply_text(f"💰 Số dư: {bal:,}đ")

async def stockrd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📦 Kho còn: {len(get_stock())} RDP")

async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            return await update.message.reply_text("❌ Cú pháp: /nap 50000")

        raw = context.args[0].replace(".", "").replace(",", "")
        if not raw.isdigit():
            return await update.message.reply_text("❌ Số tiền không hợp lệ.")

        amount = int(raw)
        uid = str(update.effective_user.id)
        tag = update.effective_user.username or update.effective_user.first_name

        pending = get_pending()
        pending[uid] = {"amount": amount, "tag": tag}
        save_json(PENDING_FILE, pending)

        if os.path.exists(MY_QR_IMAGE):
            with open(MY_QR_IMAGE, "rb") as f:
                await update.message.reply_photo(
                    f,
                    caption=f"✅ Đã tạo lệnh nạp {amount:,}đ\n⏳ Chờ admin duyệt."
                )

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Duyệt", callback_data=f"ok|{uid}"),
            InlineKeyboardButton("❌ Từ chối", callback_data=f"no|{uid}")
        ]])

        await context.bot.send_message(
            ADMIN_ID,
            f"📥 Yêu cầu nạp mới\nUser: {tag} ({uid})\nSố tiền: {amount:,}đ",
            reply_markup=kb
        )
    except Exception:
        traceback.print_exc()
        await update.message.reply_text("⚠️ Lỗi hệ thống khi tạo lệnh nạp.")

async def buyrd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = get_users()
    stock = get_stock()
    price = get_price()

    if users.get(uid, 0) < price:
        return await update.message.reply_text("❌ Không đủ tiền.")
    if not stock:
        return await update.message.reply_text("❌ Kho đã hết.")

    acc = stock.pop(0)
    users[uid] -= price

    sold = get_sold()
    sold.append({"uid": uid, "acc": acc})

    save_json(USERS_FILE, users)
    save_json(STOCK_FILE, stock)
    save_json(SOLD_FILE, sold)

    await update.message.reply_text(
        f"✅ Mua thành công!\n\n👤 User: {acc['user']}\n🔑 Pass: {acc['pass']}"
    )

# ====== ADMIN ======
async def addacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    try:
        u, p = " ".join(context.args).split("|", 1)
        stock = get_stock()
        stock.append({"user": u.strip(), "pass": p.strip()})
        save_json(STOCK_FILE, stock)
        await update.message.reply_text(f"✅ Đã thêm tài khoản. Kho: {len(stock)}")
    except:
        await update.message.reply_text("❌ Cú pháp: /addacc user|pass")

async def setprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    try:
        new_price = int(context.args[0])
        save_json(PRICE_FILE, {"price": new_price})
        await update.message.reply_text(f"✅ Đã đổi giá: {new_price:,}đ")
    except:
        await update.message.reply_text("❌ Cú pháp: /setprice 1000")

async def setqr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    if not update.message.photo:
        return await update.message.reply_text("❌ Gửi ảnh kèm caption /setqr")
    photo = await update.message.photo[-1].get_file()
    await photo.download_to_drive(MY_QR_IMAGE)
    await update.message.reply_text("✅ Đã cập nhật ảnh QR mới!")

# ====== CALLBACK DUYỆT NẠP ======
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        return await query.answer("Không có quyền!")

    action, uid = query.data.split("|")
    pending = get_pending()

    if uid not in pending:
        return await query.edit_message_text("❌ Lệnh không còn tồn tại.")

    amount = pending[uid]["amount"]

    if action == "ok":
        users = get_users()
        users[uid] = users.get(uid, 0) + amount
        save_json(USERS_FILE, users)
        await context.bot.send_message(uid, f"✅ Nạp thành công {amount:,}đ")
        await query.edit_message_text(f"✅ Đã duyệt {amount:,}đ cho {uid}")
    else:
        await context.bot.send_message(uid, "❌ Yêu cầu nạp bị từ chối.")
        await query.edit_message_text(f"❌ Đã từ chối {uid}")

    pending.pop(uid)
    save_json(PENDING_FILE, pending)

# ====== MAIN ======
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    # User
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("qr", send_qr))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("stockrd", stockrd))
    app.add_handler(CommandHandler("nap", nap))
    app.add_handler(CommandHandler("buyrd", buyrd))

    # Admin
    app.add_handler(CommandHandler("addacc", addacc))
    app.add_handler(CommandHandler("setprice", setprice))
    app.add_handler(MessageHandler(filters.PHOTO & filters.Caption("/setqr"), setqr))

    # Callback
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("🤖 BOT ĐÃ SẴN SÀNG!")
    app.run_polling()
