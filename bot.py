from keep_alive import keep_alive
keep_alive()

import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler
)

# ====== CONFIG ======
TOKEN = "6367532329:AAFwf8IiA6VxhysLCr30dwvPYY7gn2XypWA"
ADMIN_ID = 5736655322       # Telegram ID admin
PRICE_RDP = 1000         # Giá 1 RDP

# QR ảnh riêng của bạn (user quét là chuyển)
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

def require_admin_private(update: Update):
    return update.effective_user.id == ADMIN_ID and update.message.chat.type == "private"

# ====== USER COMMANDS ======

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🖥 BOT BÁN RDP AUTO\n"
        "/balance - xem số dư\n"
        "/nap <số tiền> - nạp bằng QR\n"
        "/buyrd - mua 1 RDP\n"
        "/stockrd - xem kho RDP"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = get_users()
    bal = users.get(uid, 0)
    await update.message.reply_text(f"💰 Số dư của bạn: {bal:,}đ")

async def stockrd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stock = get_stock()
    await update.message.reply_text(f"📦 Kho còn: {len(stock)} RDP")

async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("❌ Cú pháp: /nap 50000")

    try:
        amount = int(context.args[0])
        if amount <= 0:
            raise Exception()
    except:
        return await update.message.reply_text("❌ Số tiền không hợp lệ")

    uid = str(update.effective_user.id)

    pending = get_pending()
    pending[uid] = {"user_id": uid, "amount": amount}
    save_json(PENDING_FILE, pending)

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=MY_QR_IMAGE,
        caption=(
            f"💳 *NẠP TIỀN BẰNG QR*\n\n"
            f"💰 Số tiền: {amount:,}đ\n\n"
            f"👉 Quét QR ở trên bằng app ngân hàng để chuyển khoản.\n"
            f"Quét xong là chờ admin duyệt."
        ),
        parse_mode="Markdown"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Duyệt", callback_data=f"approve|{uid}"),
            InlineKeyboardButton("❌ Từ chối", callback_data=f"reject|{uid}")
        ]
    ])

    await context.bot.send_message(
        ADMIN_ID,
        f"📥 YÊU CẦU NẠP (QR RIÊNG)\n\nUser: {uid}\nSố tiền: {amount:,}đ",
        reply_markup=keyboard
    )

async def buyrd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = get_users()
    stock = get_stock()
    sold = get_sold()

    if users.get(uid, 0) < PRICE_RDP:
        return await update.message.reply_text("❌ Số dư không đủ")

    if not stock:
        return await update.message.reply_text("❌ Hết RDP trong kho")

    acc = stock.pop(0)
    users[uid] -= PRICE_RDP
    sold.append(acc)

    save_json(USERS_FILE, users)
    save_json(STOCK_FILE, stock)
    save_json(SOLD_FILE, sold)

    await update.message.reply_text(
        "✅ Mua RDP thành công!\n"
        f"👤 User: {acc['user']}\n"
        f"🔑 Pass: {acc['pass']}"
    )

# ====== ADMIN COMMANDS (PRIVATE ONLY) ======

async def addacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_admin_private(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")

    data = " ".join(context.args)
    if "|" not in data:
        return await update.message.reply_text("❌ /addacc user|pass")

    user, pwd = data.split("|", 1)
    stock = get_stock()
    stock.append({"user": user, "pass": pwd})
    save_json(STOCK_FILE, stock)
    await update.message.reply_text("✅ Đã thêm acc RDP")

async def checkacccuaban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_admin_private(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")

    stock = get_stock()
    await update.message.reply_text(f"📦 Kho hiện tại: {len(stock)} acc")

async def checkaccban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_admin_private(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")

    sold = get_sold()
    await update.message.reply_text(f"📤 Đã bán: {len(sold)} acc")

async def sendstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_admin_private(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")

    stock = get_stock()
    text = "\n".join([f"{i+1}. {x['user']}|{x['pass']}" for i, x in enumerate(stock)])
    await update.message.reply_text(text or "Kho trống")

async def sendsold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not require_admin_private(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")

    sold = get_sold()
    text = "\n".join([f"{i+1}. {x['user']}|{x['pass']}" for i, x in enumerate(sold)])
    await update.message.reply_text(text or "Chưa bán acc nào")

# ====== APPROVE / REJECT BUTTON ======

async def handle_approve_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        return await query.edit_message_text("🔐 Lệnh này chỉ admin dùng trong private chat")

    action, uid = query.data.split("|", 1)
    pending = get_pending()

    if uid not in pending:
        return await query.edit_message_text("❌ Yêu cầu đã xử lý hoặc không tồn tại.")

    amount = pending[uid]["amount"]
    users = get_users()

    if action == "approve":
        users[uid] = users.get(uid, 0) + amount
        save_json(USERS_FILE, users)
        await context.bot.send_message(uid, f"✅ Nạp thành công {amount:,}đ!")
        await query.edit_message_text(f"✅ Đã duyệt nạp {amount:,}đ cho user {uid}")
    else:
        await context.bot.send_message(uid, "❌ Yêu cầu nạp của bạn bị từ chối.")
        await query.edit_message_text(f"❌ Đã từ chối yêu cầu của user {uid}")

    pending.pop(uid)
    save_json(PENDING_FILE, pending)

# ====== MAIN ======

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

app.add_handler(CallbackQueryHandler(handle_approve_reject))

print("🤖 BOT RDP AUTO đang chạy...")
app.run_polling()
