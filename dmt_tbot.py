#!/usr/bin/env python

import logging
from telegram import ForceReply, Update, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackContext, CallbackQueryHandler, CommandHandler, ContextTypes, JobQueue, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import oracledb
from peewee import *
import datetime

# =================================================================================================
sqlite_users = None

db_sqlite = SqliteDatabase('people.db')
class BaseModel(Model):
    class Meta:
        database = db_sqlite

class User(BaseModel):
    ora_login = CharField()
    tg_user_id = CharField()
    tg_chat_id = CharField()
    enabled = BooleanField(default=True)

    enable_all_messages = BooleanField(default=True)
    enable_important_msg = BooleanField(default=True)
    enable_resolution = BooleanField(default=True)
    enable_fax_msg = BooleanField(default=True)

# class ShowedMessage(BaseModel):
#     user = ForeignKeyField(User, backref='showed_messages')
#     message_id = CharField()
#     date = DateTimeField(default=datetime.datetime.now)

def init_internal_db():
    db_sqlite.connect()
    db_sqlite.create_tables([User])
    global sqlite_users
    sqlite_users = User.select()

# =================================================================================================


# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# =================================================================================================
# Global variables
# =================================================================================================
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
#application = None  # Telegram bot application
connection = None   # Oracle database connection
# =================================================================================================


# =================================================================================================
# Oracle database functions
# =================================================================================================
oracle_users = list()
# Connect to oracle database
def connect_to_oracle():
    #oracledb.init_oracle_client(lib_dir=r"C:\oracle\ora11-x64-instant")
    oracledb.init_oracle_client(lib_dir=r"C:\2_WORK\DMT_DATA\oracle\ora11-x64-instant")
    global connection
    connection = oracledb.connect(user="",password="", host="192.168.10.15", port=1521, sid="DMT", disable_oob=True, protocol="TCP")
    logger.info("Connected to Oracle database.")

    cursor = connection.cursor()
    cursor.execute("select login, name from acad.users")
    for row in cursor:
        oracle_users.append((row[0].lower(), row[1]))

def select_alerts(login):
    cursor = connection.cursor()
    query = f"""select a.from_user, a.text, a.urgency, c.name from acad.alerts a
            left join acad.alerts_log b on a.id=b.alert_id
            left join acad.users c on a.from_user=c.login
            where usr='{login.upper()}' and b.insert_date >=
            to_timestamp('{(datetime.datetime.now() - datetime.timedelta(seconds=30)).strftime('%Y-%m-%d %H:%M:%S')}',
            'YYYY-MM-DD""HH24:MI:SS')"""
    cursor.execute(query)
    ret_letters = []
    for row in cursor:
        ret_letters.append(row)

    return ret_letters
# =================================================================================================
# MENU
# =================================================================================================
CHECK_CHAR = ['❌', '✅']

def get_main_menu(cur_tg_user_id):

    user = get_cur_user(cur_tg_user_id)
    if user is None:
        return InlineKeyboardMarkup()

    keyboard = [
        [InlineKeyboardButton("Все оповещения" + CHECK_CHAR[user.enabled], callback_data="1")],
        [
            InlineKeyboardButton("Обычные" + CHECK_CHAR[user.enable_all_messages], callback_data="2"),
            InlineKeyboardButton("Важные" + CHECK_CHAR[user.enable_important_msg], callback_data="3"),
        ],
        [
            InlineKeyboardButton("Резолюции" + CHECK_CHAR[user.enable_resolution], callback_data="4"),
            InlineKeyboardButton("Факсограммы" + CHECK_CHAR[user.enable_fax_msg], callback_data="5"),

        ],
        [InlineKeyboardButton("Выход", callback_data="6")],
    ]
    return InlineKeyboardMarkup(keyboard)

# =================================================================================================

def get_cur_user(cur_tg_user_id):
    try:
        select_result = User.get(User.tg_user_id == cur_tg_user_id)
    except User.DoesNotExist:
        return None

    return select_result

# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user_id = update.effective_user.id

    await update.message.reply_text("Меню:", reply_markup=get_main_menu(user_id))

async def button(update: Update, context: CallbackContext) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()
    user = get_cur_user(query.from_user.id)
    if query.data == "1":
        user.enabled = not user.enabled
    if query.data == "2":
        user.enable_all_messages = not user.enable_all_messages
    elif query.data == "3":
        user.enable_important_msg = not user.enable_important_msg
    elif query.data == "4":
        user.enable_resolution = not user.enable_resolution
    elif query.data == "5":
        user.enable_fax_msg = not user.enable_fax_msg
    elif query.data == "6":
        await query.delete_message()
    user.save()

    await query.edit_message_text(text= "Меню:", reply_markup=get_main_menu(query.from_user.id))

    #await query.edit_message_text(text=f"Selected option: {query.data}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    # print all the commands and what they do
    await update.message.reply_text("Use /start to test this bot.\nUse /add_user to add yourself to the access list.\nUse /help to see this message again.")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    # await update.message.reply_text(update.message.text)
    help_command(update, context)

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add user to the access list."""
    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id

    login_to_check = context.args[0].lower() if len(context.args) > 0 else None
    if (login_to_check is not None and login_to_check in [user[0] for user in oracle_users]
    and User.select().where(User.ora_login == login_to_check).count() == 0):
        User.create(ora_login=login_to_check, tg_user_id=user_id, tg_chat_id=chat_id).save()
        logger.info(f"User {user_id}|{user.full_name} (login:{login_to_check}) added to the access list.")
        await update.message.reply_html(rf"{user.mention_html()} (login:{login_to_check})  added to the access list.")

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

async def callback_halfminute(context: ContextTypes.DEFAULT_TYPE):
    registred_users = User.select()
    for user in registred_users:
        if not user.enabled:
            continue
        alerts = select_alerts(user.ora_login)
        for alert in alerts:
            urgency = alert[2]
            alert_text = alert[1].read()
            alert_sender = alert[3]

            if not user.enabled:
                continue

            if urgency == 1 and not user.enable_all_messages:
                continue
            if urgency == 2 and not user.enable_important_msg:
                continue

            message_text = "*Cообщение.* Отправитель: " + alert_sender + "\n" + "```\n" + alert_text + "\n```";
            await context.bot.send_message(chat_id=user.tg_chat_id, text=message_text, parse_mode="Markdown")

    logger.info(f"30 secund handler")

def main() -> None:
    """Start the bot."""

    # Connect to Oracle database
    connect_to_oracle()

    # Initialize internal database
    init_internal_db()

    # Create the Application and pass it your bot's token.
    application = Application.builder().token("6730616457:AAHafn9KGvsg41L94wiUVDXUQgdQCbHgp24").build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add_user", add_user))
    #application.add_handler(CommandHandler("get_message", get_message))


    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # add half minute job
    if application.job_queue is None:
        application.job_queue = JobQueue()
    job_queue = application.job_queue
    job_minute = job_queue.run_repeating(callback_halfminute, interval=30, first=10)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


    # application.bot.sendMessage)


if __name__ == "__main__":
    main()