# -*- coding: utf-8 -*-
import telebot
from telebot import util
import subprocess
import os
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import json
import logging
import signal
import threading
import re
import sys
import atexit
import requests
import io
from urllib.parse import urlparse
import urllib3
import random
try:
    from flask import Flask, request
except ImportError:
    Flask = None
    request = None

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Configuration ---
TOKEN = '8811551274:AAFDEA3j3sNh87VscICRC2dcagMD5Wl385M'  # <-- Yahan apna Telegram bot token paste karo
OWNER_ID = int(os.environ.get('OWNER_ID', '8781077406'))
ADMIN_ID = int(os.environ.get('ADMIN_ID', str(OWNER_ID)))
YOUR_USERNAME = os.environ.get('OWNER_USERNAME', '@XLARYAN_0100')
if not TOKEN or TOKEN == 'PASTE_YOUR_BOT_TOKEN_HERE':
    raise RuntimeError('Bot token set karo: TOKEN = \'PASTE_YOUR_BOT_TOKEN_HERE\' ko apne token se replace karo.')

# Required subscription channels are managed from the Admin Panel.
REQUIRED_CHANNELS = []

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')

FREE_USER_LIMIT = 10
SUBSCRIBED_USER_LIMIT = 15
ADMIN_LIMIT = 999
OWNER_LIMIT = float('inf')

os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

bot = telebot.TeleBot(TOKEN)

# Telegram button styling: primary = blue.
# Requires a recent pyTelegramBotAPI version with Bot API button styles.
def primary_inline_button(text, **kwargs):
    # Use Bot API button styling when supported; otherwise fall back safely.
    try:
        return types.InlineKeyboardButton(text, style="primary", **kwargs)
    except (TypeError, AttributeError):
        return types.InlineKeyboardButton(text, **kwargs)

def primary_reply_button(text, **kwargs):
    # Reply-keyboard styles are not supported by every pyTelegramBotAPI release.
    try:
        return types.KeyboardButton(text, style="primary", **kwargs)
    except (TypeError, AttributeError):
        return types.KeyboardButton(text, **kwargs)

bot_scripts = {}
user_subscriptions = {}
user_files = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
user_custom_limits = {}
bot_locked = False
banned_users = set()

# Auto-recovery tracking
auto_recovery_last_restart = {}

# --- Persistent uptime across restarts ---
PERSISTENT_START_FILE = os.path.join(IROTECH_DIR, 'bot_start_time.txt')

def get_persistent_start_time():
    if os.path.exists(PERSISTENT_START_FILE):
        try:
            with open(PERSISTENT_START_FILE, 'r') as f:
                timestamp = f.read().strip()
                return datetime.fromisoformat(timestamp)
        except Exception as e:
            logging.error(f"Failed to read persistent start time: {e}")
    now = datetime.now()
    try:
        with open(PERSISTENT_START_FILE, 'w') as f:
            f.write(now.isoformat())
    except Exception as e:
        logging.error(f"Failed to write persistent start time: {e}")
    return now

BOT_START_TIME = get_persistent_start_time()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== SAMBANOVA AI CONFIGURATION ====================
SAMBA_API_KEY = os.environ.get('SAMBA_API_KEY', 'e4502644-72e1-41bb-96df-e13aa741a6f9')
SAMBA_URL = "https://api.sambanova.ai/v1/chat/completions"

AVAILABLE_MODELS = {
    'llama': 'Meta-Llama-3.3-70B-Instruct',
    'deepseek': 'DeepSeek-V3.1',
    'minimax': 'MiniMax-M2.7',
    'gpt-oss': 'gpt-oss-120b'
}
DEFAULT_MODEL = 'llama'
global_model = DEFAULT_MODEL
# =====================================================================

# --- Keyboard Layouts ---
COMMAND_BUTTONS_LAYOUT_USER_SPEC = [
    ["💎 𝐔𝐩𝐝𝐚𝐭𝐞𝐬 𝐂𝐡𝐚𝐧𝐧𝐞𝐥"],
    ["💠 Upload", "📂 𝐌𝐲 𝐅𝐢𝐥𝐞𝐬"],
    ["⚡ 𝐁𝐨𝐭 𝐒𝐩𝐞𝐞𝐝", "💫 𝐒𝐭𝐚𝐭𝐮𝐬"],
    ["🔄 𝐑𝐞𝐬𝐭𝐚𝐫𝐭", "🛑 𝐒𝐭𝐨𝐩"],
    ["⚙️ Recommended Install", "🤖 𝐀𝐆𝐄𝐍𝐓"],
    ["🌐 𝐆𝐈𝐓𝐇𝐔𝐁", "👑 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐎𝐰𝐧𝐞𝐫"]
]
ADMIN_COMMAND_BUTTONS_LAYOUT_USER_SPEC = [
    ["💎 𝐔𝐩𝐝𝐚𝐭𝐞𝐬 𝐂𝐡𝐚𝐧𝐧𝐞𝐥"],
    ["💠 Upload", "📂 𝐌𝐲 𝐅𝐢𝐥𝐞𝐬"],
    ["⚡ 𝐁𝐨𝐭 𝐒𝐩𝐞𝐞𝐝", "💫 𝐒𝐭𝐚𝐭𝐮𝐬"],
    ["🔄 𝐑𝐞𝐬𝐭𝐚𝐫𝐭", "🛑 𝐒𝐭𝐨𝐩"],
    ["💎 𝐒𝐮𝐛𝐬𝐜𝐫𝐢𝐩𝐭𝐢𝐨𝐧𝐬", "📣 𝐁𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭"],
    ["🔐 𝐋𝐨𝐜𝐤 𝐁𝐨𝐭", "🟢 𝐑𝐮𝐧𝐧𝐢𝐧𝐠 𝐀𝐥𝐥 𝐂𝐨𝐝𝐞"],
    ["🛠️ 𝐀𝐝𝐦𝐢𝐧 𝐏𝐚𝐧𝐞𝐥", "⚙️ Recommended Install"],
    ["🤖 𝐀𝐆𝐄𝐍𝐓", "🌐 𝐆𝐈𝐓𝐇𝐔𝐁"],
    ["📞 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐎𝐰𝐧𝐞𝐫"]
]

# --- Customizable user button labels ---
BUTTON_LABEL_DEFAULTS = {
    'updates': '💎 𝐔𝐩𝐝𝐚𝐭𝐞𝐬 𝐂𝐡𝐚𝐧𝐧𝐞𝐥',
    'upload': '💠 Upload',
    'my_files': '📂 𝐌𝐲 𝐅𝐢𝐥𝐞𝐬',
    'speed': '⚡ 𝐁𝐨𝐭 𝐒𝐩𝐞𝐞𝐝',
    'status': '💫 𝐒𝐭𝐚𝐭𝐮𝐬',
    'restart': '🔄 𝐑𝐞𝐬𝐭𝐚𝐫𝐭',
    'stop': '🛑 𝐒𝐭𝐨𝐩',
    'subscription': '💎 𝐒𝐮𝐛𝐬𝐜𝐫𝐢𝐩𝐭𝐢𝐨𝐧𝐬',
    'broadcast': '📣 𝐁𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭',
    'lock': '🔐 𝐋𝐨𝐜𝐤 𝐁𝐨𝐭',
    'run_all': '🟢 𝐑𝐮𝐧𝐧𝐢𝐧𝐠 𝐀𝐥𝐥 𝐂𝐨𝐝𝐞',
    'admin': '🛠️ 𝐀𝐝𝐦𝐢𝐧 𝐏𝐚𝐧𝐞𝐥',
    'recommended': '⚙️ Recommended Install',
    'ai': '🤖 𝐀𝐆𝐄𝐍𝐓',
    'github': '🌐 𝐆𝐈𝐓𝐇𝐔𝐁',
    'contact': '👑 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐎𝐰𝐧𝐞𝐫',
}
BUTTON_LABEL_NAMES = {
    'updates': '📢 Updates Channel', 'upload': '🌏 Upload', 'my_files': '📁 My Files',
    'speed': '⚡ Bot Speed', 'status': '🚀 Status', 'restart': '🔄 Restart',
    'stop': '🛑 Stop', 'subscription': '💎 Subscriptions', 'broadcast': '📣 Broadcast',
    'lock': '🔒 Lock Bot', 'run_all': '🟢 Run All Code', 'admin': '🛠️ Admin Panel',
    'recommended': '⚙️ Recommended Install', 'ai': '🤖 AI Assistant',
    'github': '🌐 GitHub', 'contact': '📞 Contact Owner',
}
button_labels = dict(BUTTON_LABEL_DEFAULTS)

def get_button_label(button_id):
    return button_labels.get(button_id, BUTTON_LABEL_DEFAULTS.get(button_id, button_id))

def save_button_label(button_id, label):
    label = label.strip()
    if not label:
        return False
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO button_labels (button_id, label) VALUES (?, ?)', (button_id, label))
        conn.commit()
        conn.close()
    button_labels[button_id] = label
    return True

# --- Database Setup ---
DB_LOCK = threading.Lock()

def upgrade_db():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("PRAGMA table_info(pending_uploads)")
    columns = [col[1] for col in c.fetchall()]
    if 'extra_info' not in columns:
        c.execute("ALTER TABLE pending_uploads ADD COLUMN extra_info TEXT")
        logger.info("Added extra_info column to pending_uploads")
    c.execute('''CREATE TABLE IF NOT EXISTS user_limits (
        user_id INTEGER PRIMARY KEY,
        custom_limit INTEGER
    )''')
    conn.commit()
    conn.close()

def init_db():
    logger.info(f"Initializing database at: {DATABASE_PATH}")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (user_id INTEGER PRIMARY KEY, expiry TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_files (user_id INTEGER, file_name TEXT, file_type TEXT, PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_users (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS pending_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, file_id TEXT, file_name TEXT, file_type TEXT,
            file_size INTEGER, user_name TEXT, user_username TEXT,
            timestamp TEXT, extra_info TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS verified_users (user_id INTEGER PRIMARY KEY, verified_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS banned_users (user_id INTEGER PRIMARY KEY, banned_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_limits (user_id INTEGER PRIMARY KEY, custom_limit INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS required_channels (channel TEXT PRIMARY KEY, added_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS button_labels (button_id TEXT PRIMARY KEY, label TEXT NOT NULL)''')
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
        if ADMIN_ID != OWNER_ID:
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
        conn.commit()
        conn.close()
        upgrade_db()
    except Exception as e:
        logger.error(f"Database init error: {e}")

def load_data():
    global banned_users, user_custom_limits
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id, expiry FROM subscriptions')
        for user_id, expiry in c.fetchall():
            try:
                user_subscriptions[user_id] = {'expiry': datetime.fromisoformat(expiry)}
            except ValueError:
                pass
        c.execute('SELECT user_id, file_name, file_type FROM user_files')
        for user_id, file_name, file_type in c.fetchall():
            user_files.setdefault(user_id, []).append((file_name, file_type))
        c.execute('SELECT user_id FROM active_users')
        active_users.update(row[0] for row in c.fetchall())
        c.execute('SELECT user_id FROM admins')
        admin_ids.update(row[0] for row in c.fetchall())
        c.execute('SELECT user_id FROM banned_users')
        banned_users = set(row[0] for row in c.fetchall())
        c.execute('SELECT user_id, custom_limit FROM user_limits')
        user_custom_limits = {row[0]: row[1] for row in c.fetchall()}
        c.execute('SELECT channel FROM required_channels ORDER BY added_at ASC')
        REQUIRED_CHANNELS.clear()
        REQUIRED_CHANNELS.extend(row[0] for row in c.fetchall())
        c.execute('SELECT button_id, label FROM button_labels')
        for button_id, label in c.fetchall():
            if button_id in BUTTON_LABEL_DEFAULTS and label:
                button_labels[button_id] = label
        conn.close()
    except Exception as e:
        logger.error(f"Data load error: {e}")

init_db()
load_data()

# --- stylish_text ---
def stylish_text(text: str) -> str:
    text = re.sub(r'</?code>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    mapping = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ',
        'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
        'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ',
        'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
        'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E', 'F': 'F', 'G': 'G',
        'H': 'H', 'I': 'I', 'J': 'J', 'K': 'K', 'L': 'L', 'M': 'M', 'N': 'N',
        'O': 'O', 'P': 'P', 'Q': 'Q', 'R': 'R', 'S': 'S', 'T': 'T', 'U': 'U',
        'V': 'V', 'W': 'W', 'X': 'X', 'Y': 'Y', 'Z': 'Z'
    }
    return ''.join(mapping.get(ch, ch) for ch in text)

# --- Ban / Unban ---
def ban_user(user_id):
    if user_id in admin_ids or user_id == OWNER_ID:
        return False
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO banned_users (user_id, banned_at) VALUES (?, ?)', (user_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        banned_users.add(user_id)
        return True
    except:
        return False

def unban_user(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        banned_users.discard(user_id)
        return True
    except:
        return False

def is_user_banned(user_id):
    return user_id in banned_users

# --- Custom Limit Management ---
def set_user_custom_limit(user_id, limit):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO user_limits (user_id, custom_limit) VALUES (?, ?)', (user_id, limit))
        conn.commit()
        conn.close()
        user_custom_limits[user_id] = limit

def remove_user_custom_limit(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM user_limits WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        if user_id in user_custom_limits:
            del user_custom_limits[user_id]

def get_user_file_limit(user_id):
    if user_id in user_custom_limits:
        return user_custom_limits[user_id]
    if user_id == OWNER_ID:
        return OWNER_LIMIT
    if user_id in admin_ids:
        return ADMIN_LIMIT
    if user_id in user_subscriptions and user_subscriptions[user_id]['expiry'] > datetime.now():
        return SUBSCRIBED_USER_LIMIT
    return FREE_USER_LIMIT

def get_user_file_count(user_id):
    return len(user_files.get(user_id, []))

# --- Dynamic required-channel management ---
def normalize_channel(value):
    value = value.strip()
    if not value:
        return None
    if value.startswith('https://t.me/'):
        value = '@' + value.rstrip('/').split('/')[-1]
    if value.startswith('t.me/'):
        value = '@' + value.rstrip('/').split('/')[-1]
    if value.startswith('@'):
        name = value[1:].strip()
        if re.fullmatch(r'[A-Za-z0-9_]{5,32}', name):
            return '@' + name
        return None
    if re.fullmatch(r'-100\d{5,20}', value):
        return value
    return None

def get_required_channels():
    return list(REQUIRED_CHANNELS)

def add_required_channel(channel):
    channel = normalize_channel(channel)
    if not channel:
        return False, 'Invalid channel. Use @channelusername or -100xxxxxxxxxx.'
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO required_channels (channel, added_at) VALUES (?, ?)', (channel, datetime.now().isoformat()))
        changed = c.rowcount > 0
        conn.commit()
        conn.close()
        if changed and channel not in REQUIRED_CHANNELS:
            REQUIRED_CHANNELS.append(channel)
        return changed, ('Channel added.' if changed else 'Channel already exists.')
    except Exception as e:
        logger.exception('add_required_channel failed')
        return False, f'Database error: {e}'

def remove_required_channel(channel):
    channel = normalize_channel(channel) or channel.strip()
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM required_channels WHERE channel = ?', (channel,))
        changed = c.rowcount > 0
        conn.commit()
        conn.close()
        if changed:
            try: REQUIRED_CHANNELS.remove(channel)
            except ValueError: pass
        return changed
    except Exception:
        logger.exception('remove_required_channel failed')
        return False

def create_channel_management_panel():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(primary_inline_button('➕ Add Channel', callback_data='channel_add'), primary_inline_button('➖ Remove Channel', callback_data='channel_remove'))
    markup.row(primary_inline_button('📋 List Channels', callback_data='channel_list'))
    markup.row(primary_inline_button('🔙 Back to Admin', callback_data='admin_panel'))
    return markup

def process_add_required_channel(message):
    if message.from_user.id not in admin_ids: return
    if message.text.strip().lower() == '/cancel':
        bot.reply_to(message, stylish_text('Cancelled.')); return
    channel = normalize_channel(message.text)
    if not channel:
        bot.reply_to(message, stylish_text('Invalid channel. Send @channelusername or -100xxxxxxxxxx.\n/cancel')); return
    changed, result = add_required_channel(channel)
    bot.reply_to(message, stylish_text(('✅ ' if changed else 'ℹ️ ') + result))

def process_remove_required_channel(message):
    if message.from_user.id not in admin_ids: return
    if message.text.strip().lower() == '/cancel':
        bot.reply_to(message, stylish_text('Cancelled.')); return
    channel = normalize_channel(message.text) or message.text.strip()
    if remove_required_channel(channel):
        bot.reply_to(message, stylish_text(f'✅ Removed {channel}.'))
    else:
        bot.reply_to(message, stylish_text('❌ Channel not found.'))

# --- Channel verification ---
def is_user_verified(user_id):
    if user_id in admin_ids or user_id == OWNER_ID:
        return True
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT 1 FROM verified_users WHERE user_id = ?', (user_id,))
        result = c.fetchone() is not None
        conn.close()
        return result
    except:
        return False

def set_user_verified(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO verified_users (user_id, verified_at) VALUES (?, ?)', (user_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def is_user_member_all_channels(user_id):
    if user_id in admin_ids or user_id == OWNER_ID:
        return True
    for channel in REQUIRED_CHANNELS:
        try:
            chat_member = bot.get_chat_member(channel, user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

def send_join_prompt(chat_id, user_id):
    text = (
        "🔐 Jᴏɪɴ Aʟʟ Cʜᴀɴɴᴇʟs Tᴏ Uɴʟᴏᴄᴋ Tʜᴇ Bᴏᴛ 🚀\n"
        "📢 Cᴏᴍᴘʟᴇᴛᴇ Aʟʟ Cʜᴀɴɴᴇʟ Jᴏɪɴs Tᴏ Gᴇᴛ Aᴄᴄᴇss ✅\n"
        "⚡ Aғᴛᴇʀ Jᴏɪɴɪɴɢ, Cʟɪᴄᴋ \"Vᴇʀɪғʏ\" Tᴏ Cᴏɴᴛɪɴᴜᴇ. 🔓"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch in REQUIRED_CHANNELS:
        markup.add(primary_inline_button("CLICK", url=f"https://t.me/{ch.lstrip('@')}"))
    markup.add(primary_inline_button("✅ VERIFY", callback_data=f"verify_channel_{user_id}"))
    bot.send_message(chat_id, text, parse_mode=None, reply_markup=markup, disable_web_page_preview=True)

def check_subscription_and_continue(message=None, call=None):
    user_id = (message.from_user.id if message else call.from_user.id)
    chat_id = (message.chat.id if message else call.message.chat.id)
    if is_user_banned(user_id):
        bot.send_message(chat_id, stylish_text("🚫 You are banned from using this bot."))
        return False
    if user_id in admin_ids or user_id == OWNER_ID:
        return True
    if is_user_verified(user_id):
        return True
    if is_user_member_all_channels(user_id):
        set_user_verified(user_id)
        return True
    else:
        send_join_prompt(chat_id, user_id)
        return False

@bot.callback_query_handler(func=lambda call: call.data.startswith('verify_channel_'))
def verify_channel_callback(call):
    user_id = int(call.data.split('_')[-1])
    if user_id != call.from_user.id:
        bot.answer_callback_query(call.id, stylish_text("This verification is not for you."), show_alert=True)
        return
    if is_user_verified(user_id):
        bot.answer_callback_query(call.id, stylish_text("You are already verified."), show_ale
