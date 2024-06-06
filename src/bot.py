import os
import re
import logging
from datetime import datetime
from decimal import Decimal

from beancount.loader import load_file
from beancount.core import data

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, CallbackContext, ContextTypes, ExtBot, MessageHandler, filters

from dotenv import load_dotenv

load_dotenv()
BEANCOUNT_ROOT = os.getenv("BEANCOUNT_ROOT")
BEANCOUNT_OUTPUT = os.getenv("BEANCOUNT_OUTPUT")
BOT = os.getenv("BOT")
CURRENCY = os.getenv("CURRENCY")
CHAT_ID = os.getenv("CHAT_ID")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class AccountsData:
    """Custom class for chat_data. Here we store data per message."""

    def __init__(self) -> None:
        entries, _, options = load_file(BEANCOUNT_ROOT)
        self.accounts = set()

        for entry in entries:
            if isinstance(entry, data.Open):
                self.accounts.add(entry.account)
            if isinstance(entry, data.Close):
                self.accounts.remove(entry.account)
        logger.info('Finished initiating accounts set.')


class CustomContext(CallbackContext[ExtBot, dict, dict, AccountsData]):
    """Custom class for context."""
    """Building beancount account set."""

    def __init__(self, application: Application, chat_id: int = None, user_id: int = None):
        super().__init__(application=application, chat_id=chat_id, user_id=user_id)
        self._message_id: Optional[int] = None


# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")


def get_leg_num(data):
    n = 0
    pattern = re.compile(r"\.|cny|usd|sgd|hkd|tl|rub", re.IGNORECASE)
    while 2*n+1 < len(data) -1 and pattern.sub('',data[2*n+1]).isdigit():
        n = n + 1
    return n


def get_account(base, accounts):
    pattern = re.compile('^.*' + re.sub(':', '.*:.*', base) + '.*', re.IGNORECASE)
    r = list(filter(pattern.match, accounts))
    n = len(r)
    if n == 0:
        return 'TODO', 1
    elif n == 1:
        return r[0], 0
    else:
        return r[0], 1


def parse_amount_currency(string):
    match = re.match(r'^([\d\.]+)([A-Za-z]*)$', string)
    if match:
        amount = match.group(1)
        currency = match.group(2) if match.group(2) else CURRENCY
        return amount, currency.upper()
    else:
        print('Invalid amount format')


def parse_message(msg):
    data = msg.split()
    leg_num = get_leg_num(data)
    legs = []
    sum_amounts = 0.0
    currency = CURRENCY
    for i in range(0, leg_num + 1, 2):
        account = data[i]
        amount, currency = parse_amount_currency(data[i+1])
        sum_amounts = sum_amounts + float(amount)
        leg = (account, -float(amount), currency)
        legs.append(leg)
    leg_to = (data[2 * leg_num], sum_amounts, currency)
    legs.append(leg_to)
    note_ = data[2 * leg_num + 1:]
    payee = ''.join(n for n in note_ if "@" in n)
    tags = ' '.join(n for n in note_ if "#" in n)

    prefixes = ('@', '#')
    note_ = [x for x in note_ if not x.startswith(prefixes)]
    note = ' '.join(note_)
    return legs, payee.lstrip("@"), note, tags


async def bean(update: Update, context: CustomContext) -> None:
    chat_id = update.message.chat.id
    if (chat_id != int(CHAT_ID)):
        await update.message.reply_text('You are not the owner of this bot.')
    else:
        message = update.message.text
        accounts = context.bot_data.accounts
        try:
            legs, payee, note, tags = parse_message(message)
        except Exception as e:
            print(str(e))
            response = 'error, {}'.format(str(e))
            
        flags = 0
        transactions = ''
        for leg in legs:
            _account, _amount, currency = leg
            amount = Decimal(float(_amount)).quantize(Decimal('0.00'))
            account, flag = get_account(_account, accounts)
            flags = flags + flag
            transactions = transactions + '\n  ' + account + ' ' + str(amount) + ' ' + currency

        flag_mark = '!' if flags > 0 else '*'
        date = datetime.now().strftime("%Y-%m-%d")

        transactions = f"""
{date} {flag_mark} "{payee}" "{note}"{tags}{transactions}
"""
        
        with open(BEANCOUNT_OUTPUT, 'a+') as f:
            f.write(transactions)
        print(transactions)
        response = transactions
        await update.message.reply_text(response)


def main() -> None:
    context_types = ContextTypes(context=CustomContext, bot_data=AccountsData)

    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT).context_types(context_types).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callback = bean))

    # Run the bot until the user presses Ctrl-C
    logger.info('Starting bot.')
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
