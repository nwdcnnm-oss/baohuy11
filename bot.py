import json, os, traceback, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from keep_alive import keep_alive

# Chạy server giữ bot hoạt động (Replit/VPS)
keep_alive()

# ====== CONFIG ======
TOKEN = "6367532329:AAFwf8IiA6VxhysLCr30dwvPYY7gn2XypWA" # <--- THAY TOKEN MỚI TẠI ĐÂY
ADMIN_ID = 5736655322
MY_QR_IMAGE = "qr_bank.jpg" 

PRICE_FILE = "price.json"
USERS_FILE = "users.json"
STOCK_FILE = "stock.json"
SOLD_FILE = "sold.json"
PENDING_FILE = "pending.json"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ====== DỮ LIỆU ======
def load_json(file, default):
    if not os.path.exists(file):
        with open(file, "w") as f: json.dump(default, f)
    try:
        with open(file, "r") as f: return json.load(f)
    except: return default

def save_json(file, data):
    with open(file, "w") as f: json.dump(data, f, indent=2)

def get_users(): return load_json(USERS_FILE, {})
def get_stock(): return load_json(STOCK_FILE, [])
def get_sold(): return load_json(SOLD_FILE, [])
def get_pending(): return load_json(PENDING_FILE, {})
def get_price(): return load_json(PRICE_FILE, {"price": 20000}).get("price", 20000)

def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID

# ====== LỆNH NGƯỜI DÙNG ======

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = get_price()
    msg = (
        "🖥 **HỆ THỐNG BÁN RDP TỰ ĐỘNG**\n\n"
        "🔹 `/qr` - Xem mã QR nạp tiền\n"
        "🔹 `/nap <số tiền>` - Gửi yêu cầu nạp tiền\n"
        "🔹 `/balance` - Kiểm tra số dư\n"
        f"🔹 `/buyrd` - Mua 1 RDP (Giá: **{price:,}đ**)\n"
        "🔹 `/stockrd` - Xem số lượng kho"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def send_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gửi ảnh QR nạp tiền cho khách"""
    if os.path.exists(MY_QR_IMAGE):
        with open(MY_QR_IMAGE, 'rb') as photo:
            await update.message.reply_photo(
                photo=photo,
                caption="💳 **MÃ QR NẠP TIỀN**\n\nQuét mã trên để chuyển khoản. Sau khi chuyển, hãy dùng lệnh `/nap <số tiền>` để báo hệ thống.",
                parse_mode="Markdown"
            )
    else:
        await update.message.reply_text("❌ Hệ thống chưa cập nhật ảnh QR.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    bal = get_users().get(uid, 0)
    await update.message.reply_text(f"💰 Số dư: **{bal:,}đ**", parse_mode="Markdown")

async def stockrd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = len(get_stock())
    await update.message.reply_text(f"📦 Kho còn: **{count}** RDP")

async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            return await update.message.reply_text("❌ Cú pháp: `/nap <số tiền>`\nVí dụ: `/nap 50000`", parse_mode="Markdown")

        raw = context.args[0].replace(".", "").replace(",", "")
        if not raw.isdigit():
            return await update.message.reply_text("❌ Số tiền không hợp lệ.")

        amount = int(raw)
        uid = str(update.effective_user.id)
        user_tag = update.effective_user.username or update.effective_user.first_name

        pending = get_pending()
        pending[uid] = {"amount": amount, "tag": user_tag}
        save_json(PENDING_FILE, pending)

        # Gửi QR xác nhận cho khách
        if os.path.exists(MY_QR_IMAGE):
            with open(MY_QR_IMAGE, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo,
                    caption=f"✅ **ĐÃ TẠO LỆNH NẠP**\n💰 Số tiền: **{amount:,}đ**\n⏳ Vui lòng chờ Admin duyệt bill.",
                    parse_mode="Markdown"
                )

        # Báo Admin
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Duyệt", callback_data=f"ok|{uid}"),
            InlineKeyboardButton("❌ Từ chối", callback_data=f"no|{uid}")
        ]])
        await context.bot.send_message(
            ADMIN_ID,
            f"📥 **YÊU CẦU NẠP MỚI**\nUser: {user_tag} (`{uid}`)\nSố tiền: {amount:,}đ",
            reply_markup=kb,
            parse_mode="Markdown"
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
        return await update.message.reply_text(f"❌ Không đủ tiền (Giá: {price:,}đ)")
    if not stock:
        return await update.message.reply_text("❌ Kho hàng đã hết.")

    acc = stock.pop(0)
    users[uid] -= price
    
    sold = load_json(SOLD_FILE, [])
    sold.append({"uid": uid, "acc": acc})

    save_json(USERS_FILE, users)
    save_json(STOCK_FILE, stock)
    save_json(SOLD_FILE, sold)

    await update.message.reply_text(
        f"✅ **MUA THÀNH CÔNG**\n\n👤 User: `{acc['user']}`\n🔑 Pass: `{acc['pass']}`",
        parse_mode="Markdown"
    )

# ====== LỆNH ADMIN ======

async def addacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    try:
        u, p = " ".join(context.args).split("|")
        stock = get_stock()
        stock.append({"user": u.strip(), "pass": p.strip()})
        save_json(STOCK_FILE, stock)
        await update.message.reply_text(f"✅ Đã thêm. Kho: {len(stock)}")
    except: await update.message.reply_text("❌ Cú pháp: `/addacc user|pass`")

async def setprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    try:
        new_price = int(context.args[0])
        save_json(PRICE_FILE, {"price": new_price})
        await update.message.reply_text(f"✅ Đã đổi giá: **{new_price:,}đ**", parse_mode="Markdown")
    except: await update.message.reply_text("❌ Cú pháp: `/setprice 30000`")

async def update_qr_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin gửi ảnh kèm caption /setqr để đổi mã QR"""
    if not is_admin(update)): return
    photo_file = await update.message.photo[-1].get_file()
    await photo_file.download_to_drive(MY_QR_IMAGE)
    await update.message.reply_text("✅ Đã cập nhật ảnh QR mới thành công!")

# ====== CALLBACK DUYỆT NẠP ======

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update): return
    
    action, uid = query.data.split("|")
    pending = get_pending()
    
    if uid not in pending:
        return await query.edit_message_text("❌ Yêu cầu này không còn tồn tại.")

    amount = pending[uid]["amount"]
    if action == "ok":
        users = get_users()
        users[uid] = users.get(uid, 0) + amount
        save_json(USERS_FILE, users)
        try:
            await context.bot.send_message(uid, f"✅ **NẠP THÀNH CÔNG**\nSố dư đã được cộng **{amount:,}đ**.", parse_mode="Markdown")
        except: pass
        await query.edit_message_text(f"✅ Đã duyệt {amount:,}đ cho {uid}")
    else:
        try:
            await context.bot.send_message(uid, "❌ Yêu cầu nạp của bạn bị từ chối.")
        except: pass
        await query.edit_message_text(f"❌ Đã từ chối {uid}")

    pending.pop(uid)
    save_json(PENDING_FILE, pending)

# ====== MAIN ======

if __name__ == '__main__':
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
    app.add_handler(MessageHandler(filters.PHOTO & filters.Caption(["/setqr"]), update_qr_handler))

    # Callback
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("🤖 BOT ĐÃ SẴN SÀNG!")
    app.run_polling()
