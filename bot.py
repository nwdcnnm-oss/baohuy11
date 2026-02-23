import logging
import os
from keep_alive import keep_alive

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ===== CONFIG =====
TOKEN = os.environ.get("6367532329:AAFEx-uO_wFBDwytzxH26FFkRurjLf69YHk")
ADMIN_ID = 5736655322  # đổi thành ID của bạn
PRICE = 1000
QR_IMAGE = "https://sf-static.upanhlaylink.com/img/image_202602230bdbd1a9f78746c2495358efcf16d07a.jpg"

STOCK_FILE = "stock.txt"
SOLD_FILE = "sold.txt"
BALANCE_FILE = "balance.txt"

PENDING_NAP = {}

logging.basicConfig(level=logging.INFO)

# ===== ADMIN CHECK =====
def is_admin_private(update: Update):
    return (
        update.effective_user.id == ADMIN_ID
        and update.effective_chat.type == "private"
    )

# ===== FILE =====
def load_balance():
    data = {}
    if os.path.exists(BALANCE_FILE):
        with open(BALANCE_FILE, "r") as f:
            for line in f:
                if "|" in line:
                    user, money = line.strip().split("|")
                    data[int(user)] = int(money)
    return data

def save_balance(data):
    with open(BALANCE_FILE, "w") as f:
        for user, money in data.items():
            f.write(f"{user}|{money}\n")

def get_stock():
    if not os.path.exists(STOCK_FILE):
        return []
    with open(STOCK_FILE, "r") as f:
        return [x.strip() for x in f if x.strip()]

def save_stock(data):
    with open(STOCK_FILE, "w") as f:
        for acc in data:
            f.write(acc + "\n")

def add_sold(acc):
    with open(SOLD_FILE, "a") as f:
        f.write(acc + "\n")

# ===== COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 BOT BÁN RDP AUTO\n\n"
        "/balance - Xem số dư\n"
        "/nap <số tiền> - Nạp tiền\n"
        "/buyrd - Mua 1 RDP\n"
        "/stockrd - Xem kho\n"
    )

    if is_admin_private(update):
        text += "\n👑 /addacc user|pass - Thêm RDP"

    await update.message.reply_text(text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_balance()
    money = data.get(update.effective_user.id, 0)
    await update.message.reply_text(f"Số dư: {money:,} VND")

async def stockrd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stock = get_stock()
    await update.message.reply_text(f"Còn {len(stock)} RDP")

async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Dùng: /nap 50000")
        return

    try:
        amount = int(context.args[0])
    except:
        await update.message.reply_text("Số tiền không hợp lệ.")
        return

    user_id = update.effective_user.id
    PENDING_NAP[user_id] = amount

    caption = (
        f"NẠP {amount:,} VND\n"
        f"Nội dung CK: {user_id}\n"
        "Chờ admin duyệt."
    )

    await update.message.reply_photo(photo=QR_IMAGE, caption=caption)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Duyệt", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("Từ chối", callback_data=f"reject_{user_id}")
        ]
    ])

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"User {user_id} nạp {amount:,} VND",
        reply_markup=keyboard
    )

async def buyrd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    balances = load_balance()
    user_id = update.effective_user.id

    if balances.get(user_id, 0) < PRICE:
        await update.message.reply_text("Không đủ số dư.")
        return

    stock = get_stock()
    if not stock:
        await update.message.reply_text("Hết RDP.")
        return

    acc = stock.pop(0)
    save_stock(stock)
    add_sold(acc)

    balances[user_id] -= PRICE
    save_balance(balances)

    await update.message.reply_text(f"Mua thành công:\n{acc}")

async def addacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_private(update):
        await update.message.reply_text("Chỉ admin private dùng lệnh này.")
        return

    if not context.args:
        await update.message.reply_text("Dùng: /addacc user|pass")
        return

    acc = context.args[0]

    with open(STOCK_FILE, "a") as f:
        f.write(acc + "\n")

    await update.message.reply_text("Đã thêm vào kho.")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin_private(update):
        return

    action, user_id = query.data.split("_")
    user_id = int(user_id)

    if user_id not in PENDING_NAP:
        await query.edit_message_text("Yêu cầu không tồn tại.")
        return

    amount = PENDING_NAP[user_id]
    balances = load_balance()

    if action == "approve":
        balances[user_id] = balances.get(user_id, 0) + amount
        save_balance(balances)

        await context.bot.send_message(
            chat_id=user_id,
            text=f"Nạp thành công {amount:,} VND"
        )
        await query.edit_message_text("Đã duyệt.")
    else:
        await context.bot.send_message(
            chat_id=user_id,
            text="Yêu cầu bị từ chối."
        )
        await query.edit_message_text("Đã từ chối.")

    del PENDING_NAP[user_id]

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("stockrd", stockrd))
    app.add_handler(CommandHandler("nap", nap))
    app.add_handler(CommandHandler("buyrd", buyrd))
    app.add_handler(CommandHandler("addacc", addacc))
    app.add_handler(CallbackQueryHandler(handle_buttons))

    print("Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
