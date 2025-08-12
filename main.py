import asyncio
import re
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters
)
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

# Telegram API ma'lumotlari
api_id = 27937440
api_hash = '3b462ecc2a012deda887dcd0a5759cde'
bot_token = "8312382500:AAEJ3YkbtNZsoaabJ0CGyye46gHqFLNqVvY"

ASK_PHONE, ASK_CODE, ASK_PASSWORD = range(3)
user_clients = {}  # user_id => TelegramClient

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📱 Telefon raqamingizni kiriting: (masalan: +99890xxxxxxx)")
    return ASK_PHONE

async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    user_id = update.effective_user.id
    context.user_data["phone"] = phone

    if not phone.startswith("+"):
        await update.message.reply_text("❌ Raqam noto'g'ri formatda. + bilan boshlang.")
        return ASK_PHONE

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    user_clients[user_id] = client

    if not await client.is_user_authorized():
        try:
            await client.send_code_request(phone)
            await update.message.reply_text("📩 SMS orqali kelgan kodni kiriting:")
            return ASK_CODE
        except Exception as e:
            await update.message.reply_text(f"❌ Kod yuborishda xatolik: {e}")
            return ConversationHandler.END
    else:
        await update.message.reply_text("✅ Allaqachon tizimga kirgansiz.")
        asyncio.create_task(start_clicking_loop(user_id))
        return ConversationHandler.END

async def code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    user_id = update.effective_user.id
    phone = context.user_data["phone"]
    client = user_clients.get(user_id)

    try:
        await client.sign_in(phone, code)
        await update.message.reply_text("✅ Muvaffaqiyatli tizimga kirildi!")
        asyncio.create_task(start_clicking_loop(user_id))
        return ConversationHandler.END
    except SessionPasswordNeededError:
        await update.message.reply_text("🔐 Ikki bosqichli parol yoqilgan. Parolni kiriting:")
        return ASK_PASSWORD
    except Exception as e:
        await update.message.reply_text(f"❌ Kodni tekshirishda xatolik: {e}")
        return ConversationHandler.END

async def password_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    user_id = update.effective_user.id
    client = user_clients.get(user_id)

    try:
        await client.sign_in(password=password)
        await update.message.reply_text("🔓 Parol kiritildi. Endi ish boshlayapti...")
        asyncio.create_task(start_clicking_loop(user_id))
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ Parolni tekshirishda xatolik: {e}")
        return ConversationHandler.END

async def start_clicking_loop(user_id):
    client = user_clients.get(user_id)
    if not client:
        print("❌ Client topilmadi.")
        return

    try:
        await client.start()
        bot_username = "patrickstarsrobot"

        while True:
            # /start yuborish
            await client.send_message(bot_username, "/start")
            await asyncio.sleep(3)  # bot javob berishini kutish

            # So‘nggi bot xabarini olish
            messages = await client.get_messages(bot_username, limit=1)
            if not messages:
                await asyncio.sleep(5)
                continue

            msg = messages[0]
            text = msg.message or ""

            if msg.buttons:
                # CAPTCHA tekshirish: «...» ichidagi so‘zni olish
                match = re.search(r"«(.+?)»", text)
                if match:
                    target = match.group(1).strip()
                    print(f"🔍 Captcha topildi! Kerakli rasm: {target}")

                    clicked = False
                    for row in msg.buttons:
                        for button in row:
                            if target.lower() in button.text.lower():
                                await button.click()
                                print(f"✅ Captcha bosildi: {button.text}")
                                clicked = True
                                break
                        if clicked:
                            break
                else:
                    # Oddiy "Кликер" tugmasini izlash
                    for row in msg.buttons:
                        for button in row:
                            if "Кликер" in button.text:
                                await button.click()
                                print("✅ Кликер tugmasi bosildi")
                                break

            await asyncio.sleep(400)  # 6 minut kutish

    except Exception as e:
        print("❌ Ishlash vaqtida xatolik:", e)

if __name__ == '__main__':
    app = ApplicationBuilder().token(bot_token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_handler)],
            ASK_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, code_handler)],
            ASK_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password_handler)],
        },
        fallbacks=[]
    )

    app.add_handler(conv_handler)
    print("🤖 Bot ishga tushdi.")
    app.run_polling()
