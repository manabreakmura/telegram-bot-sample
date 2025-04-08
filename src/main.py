import logging
from datetime import datetime, timedelta
from itertools import batched

import aiosqlite
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

DATABASE_URL = config("DATABASE_URL")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

date_state, time_state, location_state = range(3)
results = {}


async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users 
            (id INTEGER PRIMARY KEY,
            telegram_id INTEGER NOT NULL UNIQUE,
            first_name TINYTEXT NOT NULL,
            username TINYTEXT NULL)
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS orders
            (id INTEGER PRIMARY KEY,
            date TINYTEXT NOT NULL,
            time TINYTEXT NOT NULL,
            location TINYTEXT NULL,
            telegram_id INTEGER NULL,
            FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE)
            """
        )

        await db.execute(
            """
            INSERT OR IGNORE INTO users (telegram_id, first_name, username) VALUES (?, ?, ?)
            """,
            (
                update.effective_user.id,
                update.effective_user.first_name,
                update.effective_user.username,
            ),
        )

        await db.commit()

    now = datetime.now()
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
    results["date"] = query.data

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
    results["time"] = query.data

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
    results["location"] = query.data
    await query.delete_message()

    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            """
            INSERT INTO orders (date, time, location, telegram_id) VALUES (?, ?, ?, ?)
            """,
            (
                results["date"],
                results["time"],
                results["location"],
                update.effective_user.id,
            ),
        )
        await db.commit()

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=", ".join([value for value in results.values()]),
    )

    return ConversationHandler.END


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="The conversation state has been reset."
    )
    return ConversationHandler.END


async def error_handler(update: Update, context: CallbackContext) -> None:
    logging.error(f'Update "{update}" caused error "{context.error}"')
    if update:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Something went wrong. We're looking into it.",
        )


async def total_command(update: Update, context: CallbackContext):
    results = []
    async with aiosqlite.connect(DATABASE_URL) as db:
        async with db.execute(
            """
            SELECT users.username, users.telegram_id, users.first_name, orders.date, COUNT (*)
            FROM users LEFT JOIN (orders) ON users.telegram_id = orders.telegram_id
            GROUP BY orders.date
            HAVING COUNT (*) >= 1
            ORDER BY orders.date DESC
            """
        ) as rows:
            async for row in rows:
                results.append(str(row))

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="\n".join(results)
    )


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
    application.add_handler(CommandHandler("total", total_command))
    application.add_error_handler(error_handler)
    application.run_polling()
