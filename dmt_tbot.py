
#!/usr/bin/env python
# pylint: disable=unused-argument
# This program is dedicated to the public domain under the CC0 license.

"""
Simple Bot to reply to Telegram messages.

First, a few handler functions are defined. Then, those functions are passed to
the Application and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Basic Echobot example, repeats messages.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import oracledb

PYO_DEBUG_PACKETS=1

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

access_list = list() # list of user_id's who can access the bot
connection = None   # Oracle database connection

# Connect to oracle database
def connect_to_oracle():
    oracledb.init_oracle_client(lib_dir=r"C:\2_WORK\DMT_DATA\oracle\ora11-x64-instant")
    global connection
    connection = oracledb.connect(user="acad",password="a1", host="192.168.10.15", port=1521, sid="DMT", disable_oob=True, protocol="TCP")
    logger.info("Connected to Oracle database.")

    # cursor = connection.cursor()
    # cursor.execute("select login from acad.users")
    # for row in cursor:
    #     print(row)



# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user.id
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    # print all the commands and what they do
    await update.message.reply_text("Use /start to test this bot.\nUse /add_user to add yourself to the access list.\nUse /help to see this message again.")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    await update.message.reply_text(update.message.text)

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add user to the access list."""
    user = update.effective_user
    user_id = user.id
    access_list.append(user_id)
    logger.info(f"User {user_id}|{user.full_name} added to the access list.")
    await update.message.reply_html(rf"{user.mention_html()} added to the access list.")

async def get_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get the message."""
    message_id = context.args[0];
    cursor = connection.cursor()
    cursor.execute(f"select text from acad.alerts where id={message_id}")
    result_text = ""
    for row in cursor:
        result_text += row[0].read()
    if update.message is not None:
        await update.message.reply_text(result_text)


def main() -> None:
    """Start the bot."""

    # Connect to Oracle database
    connect_to_oracle()

    # Create the Application and pass it your bot's token.
    application = Application.builder().token("6730616457:AAHafn9KGvsg41L94wiUVDXUQgdQCbHgp24").build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add_user", add_user))
    application.add_handler(CommandHandler("get_message", get_message))

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()