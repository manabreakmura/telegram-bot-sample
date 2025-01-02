import logging

from decouple import config
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(update.message.text)


if __name__ == "__main__":
    application = ApplicationBuilder().token(config("TELEGRAM_TOKEN")).build()
    application.add_handler(MessageHandler(filters.TEXT, echo))
    application.run_polling()
