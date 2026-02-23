from keep_alive import keep_alive
keep_alive()

import json, os, traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# ====== CONFIG ======
TOKEN = "6367532329:AAFwf8IiA6VxhysLCr30dwvPYY7gn2XypWA"
ADMIN_ID = 5736655322
PRICE_FILE = "price.json"
MY_QR_IMAGE = "https://sf-static.upanhlaylink.com/img/image_202602230bdbd1a9f78746c2495358efcf16d07a.jpg"
# ====================

USERS_FILE = "users.json"
STOCK_FILE = "stock.json"
SOLD_FILE = "sold.json"
PENDING_FILE = "pending.json"

def load_json(file, default):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump(default, f)
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

def get_users(): return load_json(USERS_FILE, {})
def get_stock(): return load_json(STOCK_FILE, [])
def get_sold(): return load_json(SOLD_FILE, [])
def get_pending(): return load_json(PENDING_FILE, {})

def get_price():
    if not os.path.exists(PRICE_FILE):
        save_json(PRICE_FILE, {"price": 20000})
    return load_json(PRICE_FILE, {"price": 20000})["price"]

def set_price(new_price):
    save_json(PRICE_FILE, {"price": new_price})

def require_admin_private(update: Update):
    return update.effective_user.id == ADMIN_ID and update.message.chat.type == "private"

# ===== USER =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = get_price()
    await update.message.reply_text(
        "🖥 BOT BÁN RDP AUTO\n"
        "/balance - xem số dư\n"
        "/nap <số tiền> - nạp QR\n"
        f"/buyrd - mua 1 RDP (Giá: {price:,}đ)\n"
        "/stockrd - xem kho"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    bal = get_users().get(uid, 0)
    await update.message.reply_text(f"💰 Số dư: {bal:,}đ")

async def stockrd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📦 Kho còn: {len(get_stock())} RDP")

async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            return await update.message.reply_text("❌ Cú pháp: /nap <số tiền>")

        raw = context.args[0].replace(".", "").replace(",", "")
        amount = int(raw)
        if amount <= 0:
            return await update.message.reply_text("❌ Số tiền không hợp lệ")

        uid = str(update.effective_user.id)

        pending = get_pending()
        pending[uid] = {"user_id": uid, "amount": amount}
        save_json(PENDING_FILE, pending)

        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=MY_QR_IMAGE,
            caption=(
                f"💳 NẠP TIỀN BẰNG QR\n\n"
                f"💰 Số tiền: {amount:,}đ\n"
                f"👉 Quét QR để chuyển khoản\n"
                f"⏳ Chờ admin duyệt"
            )
        )

        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Duyệt", callback_data=f"approve|{uid}"),
                InlineKeyboardButton("❌ Từ chối", callback_data=f"reject|{uid}")
            ]
        ])

        await context.bot.send_message(
            ADMIN_ID,
            f"📥 YÊU CẦU NẠP QR\nUser: {uid}\nSố tiền: {amount:,}đ",
            reply_markup=kb
        )
    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text("❌ Bot đang lỗi /nap, báo admin kiểm tra log.")

async def buyrd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = get_users()
    stock = get_stock()
    sold = get_sold()
    price = get_price()

    if users.get(uid, 0) < price:
        return await update.message.reply_text(f"❌ Không đủ tiền (Giá: {price:,}đ)")
    if not stock:
        return await update.message.reply_text("❌ Hết RDP")

    acc = stock.pop(0)
    users[uid] -= price
    sold.append(acc)

    save_json(USERS_FILE, users)
    save_json(STOCK_FILE, stock)
    save_json(SOLD_FILE, sold)

    await update.message.reply_text(
        f"✅ Mua thành công\nUser: {acc['user']}\nPass: {acc['pass']}"
    )

# ===== ADMIN =====

async def addacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_admin_private(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")
    if "|" not in " ".join(context.args):
        return await update.message.reply_text("❌ /addacc user|pass")

    u, p = " ".join(context.args).split("|", 1)
    stock = get_stock()
    stock.append({"user": u, "pass": p})
    save_json(STOCK_FILE, stock)
    await update.message.reply_text("✅ Đã thêm acc")

async def checkacccuaban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_admin_private(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")
    await update.message.reply_text(f"📦 Kho: {len(get_stock())}")

async def checkaccban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_admin_private(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")
    await update.message.reply_text(f"📤 Đã bán: {len(get_sold())}")

async def sendstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_admin_private(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")
    s = get_stock()
    txt = "\n".join([f"{i+1}. {x['user']}|{x['pass']}" for i, x in enumerate(s)])
    await update.message.reply_text(txt or "Kho trống")

async def sendsold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_admin_private(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")
    s = get_sold()
    txt = "\n".join([f"{i+1}. {x['user']}|{x['pass']}" for i, x in enumerate(s)])
    await update.message.reply_text(txt or "Chưa bán")

async def setprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_admin_private(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")
    try:
        new_price = int(context.args[0])
        set_price(new_price)
        await update.message.reply_text(f"✅ Đã đổi giá: {new_price:,}đ")
    except:
        await update.message.reply_text("❌ /setprice 30000")

# ===== CALLBACK =====

async def handle_approve_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if update.effective_user.id != ADMIN_ID:
        return await q.edit_message_text("🔐 Lệnh này chỉ admin dùng trong private chat")

    action, uid = q.data.split("|")
    pending = get_pending()
    if uid not in pending:
        return await q.edit_message_text("❌ Yêu cầu không tồn tại")

    amount = pending[uid]["amount"]
    users = get_users()

    if action == "approve":
        users[uid] = users.get(uid, 0) + amount
        save_json(USERS_FILE, users)
        await context.bot.send_message(uid, f"✅ Nạp thành công {amount:,}đ")
        await q.edit_message_text("✅ Đã duyệt")
    else:
        await context.bot.send_message(uid, "❌ Yêu cầu nạp bị từ chối")
        await q.edit_message_text("❌ Đã từ chối")

    pending.pop(uid)
    save_json(PENDING_FILE, pending)

# ===== MAIN =====

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("balance", balance))
app.add_handler(CommandHandler("nap", nap))
app.add_handler(CommandHandler("buyrd", buyrd))
app.add_handler(CommandHandler("stockrd", stockrd))

app.add_handler(CommandHandler("addacc", addacc))
app.add_handler(CommandHandler("checkacccuaban", checkacccuaban))
app.add_handler(CommandHandler("checkaccban", checkaccban))
app.add_handler(CommandHandler("sendstock", sendstock))
app.add_handler(CommandHandler("sendsold", sendsold))
app.add_handler(CommandHandler("setprice", setprice))

app.add_handler(CallbackQueryHandler(handle_approve_reject))

print("🤖 BOT đang chạy...")
app.run_polling()
