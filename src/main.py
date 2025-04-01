import logging
from datetime import datetime, timedelta
from itertools import batched

from decouple import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

date_state, time_state, location_state = range(3)
answers = {}


async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    now = datetime.now().date()
    buttons = []
    for x in range(8):
        date = (now + timedelta(days=x)).strftime("%d %B %Y")
        buttons.append(InlineKeyboardButton(date, callback_data=date))

    keyboard = list(batched(buttons, n=2))
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Choose a date:",
        reply_markup=reply_markup,
    )

    return date_state


async def date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    answers["date"] = query.data

    keyboard = [
        [
            InlineKeyboardButton("09:00", callback_data="09:00"),
            InlineKeyboardButton("12:00", callback_data="12:00"),
        ],
        [
            InlineKeyboardButton("15:00", callback_data="15:00"),
            InlineKeyboardButton("18:00", callback_data="18:00"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Choose time:", reply_markup=reply_markup)

    return time_state


async def time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    answers["time"] = query.data

    keyboard = [
        [
            InlineKeyboardButton("Location 1", callback_data="Location 1"),
            InlineKeyboardButton("Location 2", callback_data="Location 2"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Choose location:", reply_markup=reply_markup)

    return location_state


async def location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    answers["location"] = query.data
    await query.edit_message_text(
        text=f"{answers['date']}\n{answers['time']}\n{answers['location']}"
    )
    return ConversationHandler.END


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="The conversation state has been reset."
    )
    return ConversationHandler.END


async def error_handler(update: Update, context: CallbackContext):
    logging.error(f'Update "{update}" caused error "{context.error}"')
    error_message = "Something went wrong. We're looking into it."
    await context.bot.send_message(chat_id=update.effective_chat.id, text=error_message)


if __name__ == "__main__":
    application = Application.builder().token(config("TELEGRAM_TOKEN")).build()
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_callback)],
        states={
            date_state: [CallbackQueryHandler(date_callback)],
            time_state: [CallbackQueryHandler(time_callback)],
            location_state: [CallbackQueryHandler(location_callback)],
        },
        fallbacks=[CommandHandler("cancel", cancel_callback)],
        allow_reentry=True,
    )
    application.add_handler(conversation_handler)
    application.add_error_handler(error_handler)
    application.run_polling()
