import logging
import io
import re
import json
from datetime import datetime
from collections import defaultdict, deque
from telegram import Update, InputFile, ChatMember
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BOT_NAME = "Cyrus Security Bot"
BOT_USERNAME = "@Cyrus_Security_bot"
BOT_OWNER_ID = 7506694695

BLACKLIST_FILE = "blacklist.txt"
LOG_FILE = "logs.txt"
CONFIG_FILE = "config.json"
KNOWN_CHATS_FILE = "known_chats.json"

def load_words(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return set(w.strip().lower() for w in f if w.strip())
    except FileNotFoundError:
        return set()

def save_words(filename, words):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(words)))

def load_json(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(list(data), f, indent=2)

# Track chats for broadcasting
try:
    KNOWN_CHATS = set(load_json(KNOWN_CHATS_FILE))
except Exception:
    KNOWN_CHATS = set()

def add_known_chat(chat_id):
    if chat_id not in KNOWN_CHATS:
        KNOWN_CHATS.add(chat_id)
        save_json(KNOWN_CHATS_FILE, KNOWN_CHATS)

ABUSIVE_WORDS = load_words(BLACKLIST_FILE) or set([
    "bc", "mc", "bsdk", "madarchod", "bhenchod", "chutiya", "gandu"
])
VIOLATION_LOG = deque(maxlen=5000)
CONFIG = load_json(CONFIG_FILE)
if not CONFIG:
    CONFIG = {
        "warn_limit": 3,
        "welcome_message": f"🚩 Welcome, {{user}}! This group is protected by {BOT_NAME}. For group security and commands, DM {BOT_USERNAME}.",
    }
USER_STATS = defaultdict(int)
SPAM_TRACK = defaultdict(list)
IGNORED_USERS = set()
IGNORED_WORDS = set()

def abusive_words_text():
    return "\n".join(sorted(ABUSIVE_WORDS))

def is_admin(chat, member: ChatMember):
    return member.status in ['administrator', 'creator']

def message_contains_abuse(text):
    if not text:
        return False
    txt = text.lower().replace("*", "").replace("-", "")
    words = txt.split()
    return any(w in words or w in txt for w in ABUSIVE_WORDS) and not any(w in txt for w in IGNORED_WORDS)

def log_violation(user_id, username, reason, details=""):
    t = datetime.utcnow().isoformat()
    log_entry = f"{t}\t{user_id}\t{username}\t{reason}\t{details}"
    VIOLATION_LOG.append(log_entry)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry + "\n")

# --- Add known chats from multiple places ---
async def ensure_known_chat(update: Update):
    if hasattr(update, "effective_chat") and update.effective_chat:
        add_known_chat(update.effective_chat.id)

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_known_chat(update)
    await update.message.reply_text(
        f"👋 Hello! I am {BOT_NAME} ({BOT_USERNAME}).\n"
        "I keep this group clean & safe from spam and abuse.\n"
        "Type /help to see my commands or [DM me](http://t.me/Cyrus_Security_bot) for tips."
    )

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_known_chat(update)
    for member in update.message.new_chat_members:
        await update.message.reply_text(
            CONFIG["welcome_message"].format(user=member.mention_html()),
            parse_mode="HTML"
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_known_chat(update)
    user = update.message.from_user
    member = None
    is_admin_flag = False
    try:
        member = await context.bot.get_chat_member(update.message.chat_id, user.id)
        is_admin_flag = is_admin(update.message.chat, member)
    except Exception:
        pass
    help_text_user = (
        f"*{BOT_NAME} Help*\n"
        f"Bot username: {BOT_USERNAME}\n\n"
        "*User Commands:*\n"
        "`/help` — Show this help message\n"
        "`/checkabuse <word>` — Check if a word is blacklisted\n"
        "`/appeal` — Send appeal to the group owner\n"
        "`/report <msg-link>` — Report a message\n"
        "\n"
        f"To use {BOT_NAME} in your own group, add it from: [Cyrus Security Bot](http://t.me/Cyrus_Security_bot)"
    )
    help_text_admin = (
        "\n*Admin/Owner Commands:*\n"
        "`/addabuse <word>` — Add word to blacklist\n"
        "`/removeabuse <word>` — Remove word from blacklist\n"
        "`/listabuse` — Show blacklist\n"
        "`/ignore <user_id>` — Ignore user for checks\n"
        "`/unignore <user_id>` — Remove ignore on user\n"
        "`/ignoreword <word>` — Ignore a word from blacklist\n"
        "`/unignoreword <word>` — Remove ignore from word\n"
        "`/backup` — Owner only: Download blacklist file\n"
        "`/restore` — Owner only: Restore abusive word list (reply to file)\n"
        "`/getlog` — Owner only: Download mod log\n"
        "`/broadcast <text>` — Owner only: Broadcast a message to all known chats\n"
        "`/stats <user_id>` — Show user warning stats\n"
        "`/status` — Show bot health\n"
        "`/settings` — Show bot configuration\n"
    )
    reply = help_text_user
    if user.id == BOT_OWNER_ID or is_admin_flag:
        reply += help_text_admin
    await update.message.reply_text(reply, parse_mode="Markdown", disable_web_page_preview=True)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != BOT_OWNER_ID:
        await update.message.reply_text("Only the owner can use /broadcast.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    msg = " ".join(context.args)
    failed = []
    for chat_id in list(KNOWN_CHATS):
        try:
            await context.bot.send_message(chat_id=chat_id, text=f"📢 [Cyrus Security Bot Broadcast]\n\n{msg}")
        except Exception as e:
            failed.append(str(chat_id))
    if not failed:
        await update.message.reply_text("Broadcast sent to all known chats!")
    else:
        await update.message.reply_text(f"Broadcast sent, but failed for: {', '.join(failed)}")

# ... [The rest of your previous code for addabuse, removeabuse, listabuse, ignore, unignore, etc., cut for brevity, same as before]
# IMPORTANT: In every handler/command that accepts a message, call `await ensure_known_chat(update)` at the start.

async def add_abuse(update, context):
    await ensure_known_chat(update)
    user = update.message.from_user
    member = await context.bot.get_chat_member(update.message.chat_id, user.id)
    if not is_admin(update.message.chat, member) and user.id != BOT_OWNER_ID:
        await update.message.reply_text("Only admins or the owner can add abusive words.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /addabuse <word>")
        return
    word = context.args[0].lower().strip()
    if word in ABUSIVE_WORDS:
        await update.message.reply_text(f"'{word}' is already blacklisted.")
    else:
        ABUSIVE_WORDS.add(word)
        save_words(BLACKLIST_FILE, ABUSIVE_WORDS)
        await update.message.reply_text(f"'{word}' added to abuse blacklist.")

# ... (put other command handlers here with `await ensure_known_chat(update)` at the top, refer to your previous implementation for all features!)

# --- Monitor messages for abuse ---
async def monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_known_chat(update)
    message = update.message
    user = message.from_user
    user_id = str(user.id)
    text = message.text or ""
    chat_id = message.chat_id
    if user_id in IGNORED_USERS:
        return
    if any(w in text for w in IGNORED_WORDS):
        return
    if message_contains_abuse(text):
        await message.delete()
        USER_STATS[user_id] += 1
        log_violation(user_id, user.username, "abuse", text)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ {user.mention_html()}, your message was deleted for abusive language. Warning {USER_STATS[user_id]}/{CONFIG['warn_limit']}.",
            parse_mode="HTML"
        )
        if USER_STATS[user_id] >= CONFIG['warn_limit']:
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=user.id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"{user.mention_html()} has been banned for repeated rule violations.",
                parse_mode="HTML"
            )

# -- Auto-backup at midnight (owner gets blacklist .txt) --
async def auto_backup(context: ContextTypes.DEFAULT_TYPE):
    file_obj = io.BytesIO(abusive_words_text().encode())
    file_obj.name = "autobackup_abusive_words.txt"
    await context.bot.send_document(
        chat_id=BOT_OWNER_ID, document=InputFile(file_obj),
        caption="Daily backup by Cyrus Security Bot"
    )

# --- Main App Setup ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot_token = "8036311934:AAF3hR_uZ0aVxHmmd1XL5zMs7_1roJBswXs"
    app = ApplicationBuilder().token(bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("addabuse", add_abuse))
    # ... (other command handlers)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, monitor))
    scheduler = AsyncIOScheduler()
    scheduler.add_job(auto_backup, "cron", hour=0, minute=0, args=[app.bot])
    scheduler.start()
    app.run_polling()