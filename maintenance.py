from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from flask import Flask
import threading
import asyncio
import os

# ----------------------------
# Config
# ----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "7809869650:AAGdsufg3O4zR58fd75LW-MBQsFYWB0byBY")

MAINTENANCE_TEXT = """━━━━━━━━━━━━━━━
📢 <b>Important Notice</b>
━━━━━━━━━━━━━━━

🚫 <b>The bot is currently under FULL maintenance.</b>  
⚠️ <i>All features are disabled — nothing will work during this period.</i>  

🎁 You will receive <b>9 days FREE subscription</b>.  
⏳ <i>The countdown will begin only from the day the bot comes back online</i>.  

🙏 Thank you for your patience and understanding.  

━━━━━━━━━━━━━━━
👨‍💻 Managed by <b>@ftmbotzx</b>  
📢 Stay connected in our channel for the next update!
"""

# ----------------------------
# Telegram Bot
# ----------------------------
async def reply_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            MAINTENANCE_TEXT,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

async def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, reply_maintenance))
    print("✅ Bot is running...")

    # Start without signal handlers
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Keep alive forever
    await asyncio.Event().wait()

def start_bot():
    asyncio.run(run_bot())

# ----------------------------
# Web Server (for Render)
# ----------------------------
server = Flask(__name__)

@server.route("/")
def home():
    return "✅ Bot is running and server is alive!"

# ----------------------------
# Main
# ----------------------------
if __name__ == "__main__":
    # Run bot in background thread
    threading.Thread(target=start_bot, daemon=True).start()

    # Run Flask on Render
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)
