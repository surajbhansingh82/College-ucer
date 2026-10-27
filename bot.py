# ============================================================
# COLLEGE ASSISTANT BOT - bot.py
# Steps clearly labeled [STEP N] for easy debugging
# ============================================================
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)
import scraper
import os
import re

BOT_TOKEN = "8905812415:AAHZ8VnxHsXhsF-6PffGvnx3j283nRjnD20"

COLLEGE, STUDENT_ID, PASSWORD, CAPTCHA = range(4)
MAX_MSG_LEN = 4000   # Telegram safe limit (4096 se thoda kam)


# ============================================================
# [HELPER] Menu Builders
# ============================================================
def get_main_menu(chat_id):
    # ✅ FIX: dono check karo — file AND memory session
    session_exists = (
        os.path.exists(f"session_{chat_id}.json")
        or chat_id in scraper.active_sessions
    )
    keyboard = []
    if not session_exists:
        keyboard.append([InlineKeyboardButton("🔐 Login", callback_data='login')])
    else:
        keyboard.append([InlineKeyboardButton("🔍 Check Login Status", callback_data='check_status')])
        keyboard.append([InlineKeyboardButton("🚪 Logout", callback_data='logout')])
    keyboard.extend([
        [InlineKeyboardButton("📊 Attendance", callback_data='menu_attendance')],
        [InlineKeyboardButton("💰 Fees", callback_data='fetch_fees')],
        [InlineKeyboardButton("📝 Marks", callback_data='fetch_marks')],
        [InlineKeyboardButton("📚 Library", callback_data='fetch_library')]
    ])
    return InlineKeyboardMarkup(keyboard)


def get_attendance_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Day Wise", callback_data='att_day_wise')],
        [InlineKeyboardButton("📈 Summary - Till Date", callback_data='att_summary')],
        [InlineKeyboardButton("🕰️ Attendance History", callback_data='att_history')],
        [InlineKeyboardButton("🔙 Back", callback_data='back_main')]
    ])


# ✅ NEW: Cancel button for login flow
def get_cancel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel Login", callback_data='cancel_login')]
    ])


# ============================================================
# [STEP 1] /start
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[STEP 1] /start called for chat {update.effective_chat.id}")
    chat_id = update.effective_chat.id
    msg_text = "Namaste! Main aapka College Assistant Bot hoon.\n"
    session_exists = (
        os.path.exists(f"session_{chat_id}.json")
        or chat_id in scraper.active_sessions
    )
    msg_text += "✅ Aap already logged in hain!" if session_exists else "Niche menu se Login karein:"
    if update.message:
        await update.message.reply_text(msg_text, reply_markup=get_main_menu(chat_id))
    else:
        await update.callback_query.message.edit_text(msg_text, reply_markup=get_main_menu(chat_id))


# ============================================================
# [STEP 2-5] Main Menu Callback Router
# ============================================================
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data
    print(f"[STEP 2-5] menu_handler: chat={chat_id} data={data}")

    # --- [STEP 3a] Logout ---
    if data == 'logout':
        session_file = f"session_{chat_id}.json"
        if os.path.exists(session_file):
            os.remove(session_file)
        # ✅ browser cleanup
        if chat_id in scraper.active_sessions:
            await scraper.cleanup_session(chat_id)
        await query.message.edit_text("🚪 Aap successfully Logout ho gaye hain.", reply_markup=get_main_menu(chat_id))
        return

    # --- [STEP 3b] Check Status ---
    if data == 'check_status':
        await query.message.edit_text("⏳ Portal check kar rahe hain, wait karein...")
        is_valid, msg = await scraper.check_session(chat_id)
        await query.message.edit_text(msg, reply_markup=get_main_menu(chat_id))
        return

    # --- [STEP 3c] Back ---
    if data == 'back_main':
        await query.message.edit_text("Main Menu:", reply_markup=get_main_menu(chat_id))
        return

    # --- [STEP 6 ENTRY] Login ---
    if data == 'login':
        await query.edit_message_text("👉 College Code likhein (jaise UCER):", reply_markup=get_cancel_keyboard())
        return COLLEGE

    # --- [STEP 4] Attendance Sub-menu ---
    if data == 'menu_attendance':
        await query.message.edit_text("📊 Attendance dekhne ke liye option chunein:", reply_markup=get_attendance_menu())
        return

    # --- [STEP 5] Data Fetch + Error/Large Data Handling ---
    if data.startswith('att_') or data.startswith('fetch_'):
        if data.startswith('att_'):
            action = 'attendance'
            sub_action = data.replace('att_', '')
            await query.message.edit_text("⏳ Data fetch kar rahe hain...")
            res = await scraper.fetch_data(chat_id, action, sub_action)
        else:
            action = data.replace('fetch_', '')
            await query.message.edit_text(f"⏳ {action.capitalize()} fetch kar rahe hain...")
            res = await scraper.fetch_data(chat_id, action)

        # --- Error: Screenshot ---
        if isinstance(res, str) and res.startswith("ERROR_SCREENSHOT|"):
            err_msg = res.split("|", 1)[1]
            await query.message.edit_text(f"❌ System Error: {err_msg}")
            err_file = f"error_{chat_id}.png"
            if os.path.exists(err_file):
                await query.message.reply_photo(photo=open(err_file, 'rb'), caption="Yeh error ka screenshot.")
                os.remove(err_file)
            await query.message.reply_text("Aage kya?", reply_markup=get_main_menu(chat_id))

        # --- Error: Session Expired ---
        elif res == "SESSION_EXPIRED":
            await query.message.edit_text("❌ Session expire. Dobara Login karein.", reply_markup=get_main_menu(chat_id))

        # --- ✅ FIX: Bada data -> TXT file ---
        elif len(res) > MAX_MSG_LEN:
            clean = re.sub(r'<[^>]+>', '', res).replace('**', '')
            txt_path = f"data_{chat_id}_{action}.txt"
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(clean)
            await query.message.reply_document(
                document=open(txt_path, 'rb'),
                filename=f"{action}_data.txt",
                caption=f"📄 Data bada tha ({len(res)} chars). TXT file me bhej rahe hain."
            )
            os.remove(txt_path)
            await query.message.reply_text("Aage kya?", reply_markup=get_main_menu(chat_id))

        # --- Normal (small) data ---
        else:
            try:
                await query.message.reply_text(res, parse_mode='HTML')
            except Exception as e:
                # HTML parse fail ho toh plain text bhej do
                print(f"[STEP 5] HTML parse failed, sending plain: {e}")
                await query.message.reply_text(re.sub(r'<[^>]+>', '', res))
            await query.message.reply_text("Aage kya?", reply_markup=get_main_menu(chat_id))
        return


# ============================================================
# [STEP 6] LOGIN FLOW — with Cancel button at each step
# ============================================================
async def get_college(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[STEP 6a] get_college: {update.message.chat_id}")
    context.user_data['college'] = update.message.text.upper()
    await update.message.reply_text("👉 Apni Student ID likhein:", reply_markup=get_cancel_keyboard())
    return STUDENT_ID


async def get_student_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[STEP 6b] get_student_id: {update.message.chat_id}")
    context.user_data['student_id'] = update.message.text
    await update.message.reply_text("👉 Apna Password likhein:", reply_markup=get_cancel_keyboard())
    return PASSWORD


async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[STEP 6c] get_password: {update.message.chat_id}")
    context.user_data['password'] = update.message.text
    chat_id = update.message.chat_id
    college = context.user_data['college']
    await update.message.reply_text("⏳ Portal open kar rahe hain, Captcha nikal rahe hain...")
    img_path = await scraper.get_captcha_image(chat_id, college)
    if img_path and os.path.exists(img_path):
        await update.message.reply_photo(
            photo=open(img_path, 'rb'),
            caption="👉 Captcha Code dekhein:",
            reply_markup=get_cancel_keyboard()
        )
        return CAPTCHA
    else:
        await update.message.reply_text("❌ Portal open nahi ho paya. /start dabayein.")
        return ConversationHandler.END


async def get_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[STEP 6d] get_captcha: {update.message.chat_id}")
    captcha_text = update.message.text
    chat_id = update.message.chat_id
    await update.message.reply_text("⏳ Login kar rahe hain...")
    success, message = await scraper.submit_login(
        chat_id,
        context.user_data['student_id'],
        context.user_data['password'],
        captcha_text
    )
    await update.message.reply_text(message, reply_markup=get_main_menu(chat_id))
    return ConversationHandler.END


# ============================================================
# [STEP 7] LOGIN CANCEL (NEW)
# ============================================================
async def cancel_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[STEP 7] cancel_login: {update.callback_query.message.chat_id}")
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    # Agar captcha image browser open hua tha toh cleanup
    if chat_id in scraper.active_sessions and 'password' in context.user_data:
        # Login complete nahi hua tha -> browser band karo
        pass  # scraper.get_captcha_image ne session banaya ho toh
    await query.message.edit_text("❌ Login cancel kar diya gaya.", reply_markup=get_main_menu(chat_id))
    context.user_data.clear()
    return ConversationHandler.END


# ============================================================
# MAIN
# ============================================================
def main():
    print("Bot start ho raha hai...")
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_handler, pattern='^login$')],
        states={
            COLLEGE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_college)],
            STUDENT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_student_id)],
            PASSWORD:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            CAPTCHA:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_captcha)],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(cancel_login, pattern='^cancel_login$'),  # ✅ NEW
        ],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(menu_handler))

    print("Bot Telegram par ready hai!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()