# ============================================
# CUSTOM SMS BOT - COMPLETE FINAL
# Only Custom SMS API - No Bomber APIs
# ============================================

import os
import sys
import asyncio
import logging
import aiosqlite
import aiohttp
import json
import re
import hashlib
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ===================== কনফিগারেশন =====================
BOT_TOKEN = "7930474954:AAGlxVtZMuh04xYs7kU_dDIj0MJmZ8Q0eCI"
ADMIN_ID = 1967494059
ADMIN_USERNAME = "RobiEntertainment"

DB_PATH = "custom_sms_bot.db"

# গ্লোবাল ভেরিয়েবল
SETTINGS = {}
SMS_API_URL = ""
SMS_API_KEY = ""
SMS_SENDER_ID = ""
SMS_ACTIVE = True
db_conn = None
DB_LOCK = asyncio.Lock()

# ক্যাশিং
CACHE = {}
CACHE_TIMEOUT = 300

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

print("=" * 60)
print("📨 CUSTOM SMS BOT - FINAL")
print("=" * 60)
print(f"✅ Bot Token: {'✅' if BOT_TOKEN else '❌'}")
print(f"✅ Admin ID: {ADMIN_ID}")
print("=" * 60)

# ===================== ডাটাবেস =====================
async def get_db():
    global db_conn
    async with DB_LOCK:
        try:
            if db_conn is None:
                db_conn = await aiosqlite.connect(DB_PATH)
                db_conn.row_factory = aiosqlite.Row
                await db_conn.execute("PRAGMA journal_mode=WAL")
                await db_conn.execute("PRAGMA synchronous=NORMAL")
                await db_conn.execute("PRAGMA cache_size=20000")
                await db_conn.execute("PRAGMA temp_store=MEMORY")
            return db_conn
        except Exception as e:
            logger.error(f"Database error: {e}")
            db_conn = None
            raise

async def close_db():
    global db_conn
    async with DB_LOCK:
        if db_conn:
            try:
                await db_conn.close()
            except:
                pass
            db_conn = None

async def init_db():
    try:
        conn = await get_db()
        
        await conn.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 3,
            total_sms INTEGER DEFAULT 0,
            total_bulk INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0,
            premium_expiry TIMESTAMP,
            last_active TIMESTAMP,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            daily_bonus_date TIMESTAMP,
            has_joined_required INTEGER DEFAULT 0,
            referral_code TEXT UNIQUE
        )''')
        
        await conn.execute('''CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount INTEGER,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        await conn.execute('''CREATE TABLE IF NOT EXISTS redeem_codes (
            code TEXT PRIMARY KEY,
            amount INTEGER,
            usages INTEGER,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        await conn.execute('''CREATE TABLE IF NOT EXISTS redeem_history (
            user_id INTEGER,
            code TEXT,
            redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, code)
        )''')
        
        await conn.execute('''CREATE TABLE IF NOT EXISTS bot_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT
        )''')
        
        await conn.execute('''CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT,
            target_id INTEGER,
            details TEXT,
            log_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        await conn.execute('''CREATE TABLE IF NOT EXISTS sms_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            phone TEXT,
            message TEXT,
            status TEXT,
            response TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        default_settings = [
            ("daily_bonus_enabled", "true"),
            ("daily_bonus_amount", "1"),
            ("daily_bonus_cooldown", "24"),
            ("sms_cost", "1"),
            ("bulk_sms_cost", "1"),
            ("phone_prefixes", "017,018,019,016,015,013,014,010"),
            ("phone_length", "11"),
            ("max_bulk_numbers", "100"),
            ("bulk_sms_interval", "0.05"),
            ("premium_bonus", "10"),
            ("sms_api_url", "https://api.paglahost.shop/Custom_SMS/api.php"),
            ("sms_api_key", "Shuvo55356"),
            ("sms_sender_id", ""),
            ("premium_price", "100"),
            ("premium_duration", "30"),
            ("required_channel", ""),
            ("required_group", ""),
            ("required_channel_link", ""),
            ("required_group_link", ""),
            ("join_required_enabled", "false"),
            ("welcome_message", "🎉 **স্বাগতম!**\n\nআমাদের কাস্টম SMS বট ব্যবহার করুন।"),
            ("denied_message", "❌ **অ্যাক্সেস অস্বীকার!**\n\nএই বট ব্যবহার করতে আপনাকে অবশ্যই আমাদের গ্রুপ/চ্যানেলে জয়েন করতে হবে।"),
            ("support_username", ADMIN_USERNAME),
        ]
        
        for key, value in default_settings:
            await conn.execute("INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)", (key, value))

        await conn.commit()
        await load_settings()
        await load_sms_api()
        logger.info("✅ Database initialized")
        
    except Exception as e:
        logger.error(f"Database init error: {e}")
        raise

async def load_settings():
    global SETTINGS
    try:
        conn = await get_db()
        cursor = await conn.execute("SELECT setting_key, setting_value FROM bot_settings")
        rows = await cursor.fetchall()
        SETTINGS = {row[0]: row[1] for row in rows}
        logger.info(f"✅ Loaded {len(SETTINGS)} settings")
    except Exception as e:
        logger.error(f"Settings load error: {e}")
        SETTINGS = {}

def get_setting(key, default=None):
    cache_key = f"setting_{key}"
    if cache_key in CACHE:
        cached_value, timestamp = CACHE[cache_key]
        if (datetime.now() - timestamp).total_seconds() < CACHE_TIMEOUT:
            return cached_value
    value = SETTINGS.get(key, default)
    CACHE[cache_key] = (value, datetime.now())
    return value

async def update_setting(key, value):
    global SETTINGS
    try:
        conn = await get_db()
        await conn.execute(
            "INSERT OR REPLACE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)",
            (key, value)
        )
        await conn.commit()
        SETTINGS[key] = value
        CACHE[f"setting_{key}"] = (value, datetime.now())
        return True
    except Exception as e:
        logger.error(f"Update setting error: {e}")
        return False

async def load_sms_api():
    global SMS_API_URL, SMS_API_KEY, SMS_SENDER_ID
    SMS_API_URL = get_setting('sms_api_url', '')
    SMS_API_KEY = get_setting('sms_api_key', '')
    SMS_SENDER_ID = get_setting('sms_sender_id', '')

# ===================== হেল্পার =====================
async def safe_api_call(url, method='GET', data=None, params=None, timeout=15):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession() as session:
            if method.upper() == 'POST':
                headers["Content-Type"] = "application/json"
                async with session.post(url, json=data, headers=headers, timeout=timeout) as resp:
                    return True, await resp.text(), resp.status
            else:
                async with session.get(url, params=params, headers=headers, timeout=timeout) as resp:
                    return True, await resp.text(), resp.status
    except Exception as e:
        return False, str(e), 500

def validate_phone(phone):
    if not phone or not phone.isdigit():
        return False, "শুধু সংখ্যা দিন!"
    length = int(get_setting('phone_length', '11'))
    if len(phone) != length:
        return False, f"{length} ডিজিটের নম্বর দিন!"
    prefixes = get_setting('phone_prefixes', '017,018,019,016,015,013,014,010').split(',')
    if prefixes != ['*'] and phone[:3] not in prefixes:
        return False, f"ভ্যালিড প্রিফিক্স নয়! ({', '.join(prefixes)})"
    return True, "✅ ভ্যালিড"

def progress_bar(current, total, length=15):
    if total <= 0:
        return "⬜" * length + " 0%"
    current = min(current, total)
    filled = int(length * current / total)
    return '🟩' * filled + '⬜' * (length - filled) + f" {round(current/total*100, 1)}%"

def generate_referral_code(user_id):
    return hashlib.md5(str(user_id).encode()).hexdigest()[:6].upper()

def is_premium_expired(expiry_date):
    if not expiry_date:
        return True
    try:
        return datetime.now() > datetime.fromisoformat(expiry_date)
    except:
        return True

# ===================== কাস্টম SMS API =====================
async def send_sms_api(phone, message):
    """আপনার কাস্টম SMS API তে রিকোয়েস্ট পাঠায়"""
    global SMS_API_URL, SMS_API_KEY, SMS_SENDER_ID
    
    if not SMS_API_URL or not SMS_API_KEY:
        return False, "SMS API কনফিগার করা নেই!", ""
    
    try:
        # GET রিকোয়েস্ট (PaglHost স্টাইল)
        params = {
            "key": SMS_API_KEY,
            "number": phone,
            "msg": message
        }
        
        # যদি Sender ID থাকে
        if SMS_SENDER_ID:
            params["senderid"] = SMS_SENDER_ID
        
        success, text, status = await safe_api_call(SMS_API_URL, method='GET', params=params)
        
        if not success:
            return False, f"API Error: {text}", text
        
        text_lower = text.lower()
        success_keywords = ['success', 'sent', 'ok', 'true', 'done', 'submitted', 'accepted']
        
        # Response check
        if any(word in text_lower for word in success_keywords):
            return True, "সফল", text
        
        # JSON response check
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                if data.get('status') in ['success', 'ok', 'true', True]:
                    return True, "সফল", text
                if data.get('success') in [True, 'true', 1]:
                    return True, "সফল", text
        except:
            pass
        
        return False, f"API রেসপন্স: {text[:150]}", text
        
    except Exception as e:
        return False, str(e), ""

async def save_sms_history(user_id, phone, message, status, response):
    try:
        conn = await get_db()
        await conn.execute(
            "INSERT INTO sms_history (user_id, phone, message, status, response) VALUES (?, ?, ?, ?, ?)",
            (user_id, phone, message[:200], status, response[:300])
        )
        await conn.commit()
    except:
        pass

async def track_transaction(user_id, trans_type, amount, description=""):
    try:
        conn = await get_db()
        await conn.execute(
            "INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)",
            (user_id, trans_type, amount, description)
        )
        await conn.commit()
    except:
        pass

async def admin_log(admin_id, action, target_id=None, details=""):
    try:
        conn = await get_db()
        await conn.execute(
            "INSERT INTO admin_logs (admin_id, action, target_id, details) VALUES (?, ?, ?, ?)",
            (admin_id, action, target_id, details)
        )
        await conn.commit()
    except:
        pass

# ===================== অ্যাক্সেস চেক =====================
async def check_user_access(user_id):
    if user_id == ADMIN_ID:
        return True, ""
    
    if get_setting('join_required_enabled', 'false') != 'true':
        return True, ""
    
    conn = await get_db()
    cursor = await conn.execute("SELECT has_joined_required FROM users WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    
    if row and row[0] == 1:
        return True, ""
    
    channel = get_setting('required_channel', '')
    group = get_setting('required_group', '')
    
    if not channel and not group:
        return True, ""
    
    channel_link = get_setting('required_channel_link', '')
    group_link = get_setting('required_group_link', '')
    
    msg = get_setting('denied_message', '❌ **অ্যাক্সেস অস্বীকার!**')
    
    keyboard = []
    if channel_link:
        keyboard.append([InlineKeyboardButton("📢 চ্যানেল জয়েন", url=channel_link)])
    if group_link:
        keyboard.append([InlineKeyboardButton("👥 গ্রুপ জয়েন", url=group_link)])
    keyboard.append([InlineKeyboardButton("✅ চেক করুন", callback_data="check_access")])
    
    return False, (msg, InlineKeyboardMarkup(keyboard))

async def check_access_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    conn = await get_db()
    await conn.execute("UPDATE users SET has_joined_required = 1 WHERE user_id = ?", (user_id,))
    await conn.commit()
    
    await query.edit_message_text(
        "✅ **জয়েন ভেরিফাইড!**\n\nআপনি এখন বট ব্যবহার করতে পারবেন।\n/start দিন।",
        parse_mode="Markdown"
    )

# ============================================================
# 📋 কীবোর্ড
# ============================================================

def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [{"text": "📨 Send SMS", "style": "primary"}, {"text": "📤 Bulk SMS", "style": "success"}],
        [{"text": "👤 My Profile", "style": "success"}, {"text": "📊 My Stats", "style": "primary"}],
        [{"text": "🎁 Redeem Code", "style": "success"}, {"text": "📞 Support", "style": "primary"}],
        [{"text": "⭐ Daily Bonus", "style": "success"}, {"text": "🏆 Leaderboard", "style": "primary"}],
        [{"text": "👑 Premium", "style": "primary"}, {"text": "🔮 Utilities", "style": "primary"}],
    ], resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        [{"text": "👥 User Control", "style": "primary"}, {"text": "📢 Group Control", "style": "primary"}],
        [{"text": "💰 Balance Control", "style": "primary"}, {"text": "🎟️ Redeem Control", "style": "success"}],
        [{"text": "📡 SMS API Settings", "style": "primary"}, {"text": "🎁 Bonus Control", "style": "success"}],
        [{"text": "📈 Reports", "style": "primary"}, {"text": "🔧 Settings", "style": "primary"}],
        [{"text": "📣 Broadcast", "style": "success"}, {"text": "📨 Test SMS", "style": "primary"}],
        [{"text": "🔄 Restart Bot", "style": "danger"}, {"text": "🔙 Exit Admin", "style": "primary"}]
    ], resize_keyboard=True)

def get_user_control_keyboard():
    return ReplyKeyboardMarkup([
        [{"text": "🚫 Block User", "style": "danger"}, {"text": "✅ Unblock User", "style": "success"}],
        [{"text": "ℹ️ User Info", "style": "primary"}, {"text": "📋 List Users", "style": "primary"}],
        [{"text": "👑 Make Premium", "style": "success"}, {"text": "❌ Remove Premium", "style": "danger"}],
        [{"text": "🗑️ Delete User", "style": "danger"}, {"text": "🔙 Back", "style": "primary"}]
    ], resize_keyboard=True)

def get_group_control_keyboard():
    return ReplyKeyboardMarkup([
        [{"text": "📢 Set Channel", "style": "primary"}, {"text": "👥 Set Group", "style": "primary"}],
        [{"text": "🔗 Set Channel Link", "style": "primary"}, {"text": "🔗 Set Group Link", "style": "primary"}],
        [{"text": "✏️ Set Welcome", "style": "primary"}, {"text": "🚫 Set Denied", "style": "danger"}],
        [{"text": "✅ Enable Join", "style": "success"}, {"text": "❌ Disable Join", "style": "danger"}],
        [{"text": "📊 View Settings", "style": "primary"}, {"text": "🔙 Back", "style": "primary"}]
    ], resize_keyboard=True)

def get_balance_keyboard():
    return ReplyKeyboardMarkup([
        [{"text": "🟢 Add Credit", "style": "success"}, {"text": "🔴 Remove Credit", "style": "danger"}],
        [{"text": "🎁 Gift All", "style": "success"}, {"text": "🎁 Gift User", "style": "success"}],
        [{"text": "📝 Set Balance", "style": "primary"}, {"text": "🔄 Reset All", "style": "danger"}],
        [{"text": "📊 Report", "style": "primary"}, {"text": "🔙 Back", "style": "primary"}]
    ], resize_keyboard=True)

def get_redeem_keyboard():
    return ReplyKeyboardMarkup([
        [{"text": "➕ Create Code", "style": "success"}, {"text": "❌ Delete Code", "style": "danger"}],
        [{"text": "🗑️ Delete All", "style": "danger"}, {"text": "✏️ Edit Code", "style": "primary"}],
        [{"text": "📋 List Codes", "style": "primary"}, {"text": "🔙 Back", "style": "primary"}]
    ], resize_keyboard=True)

def get_sms_api_keyboard():
    return ReplyKeyboardMarkup([
        [{"text": "🔗 Set API URL", "style": "primary"}, {"text": "🔑 Set API Key", "style": "primary"}],
        [{"text": "📛 Set Sender ID", "style": "primary"}, {"text": "📋 View API Config", "style": "success"}],
        [{"text": "🧪 Test API", "style": "success"}, {"text": "🔙 Back", "style": "primary"}]
    ], resize_keyboard=True)

def get_utilities_keyboard():
    return ReplyKeyboardMarkup([
        [{"text": "🌐 IP Info", "style": "primary"}],
        [{"text": "📮 ZIP Code", "style": "primary"}],
        [{"text": "🎬 Movie", "style": "primary"}],
        [{"text": "🔙 Back", "style": "primary"}]
    ], resize_keyboard=True)

# ============================================================
# 🎯 ইউটিলিটি ফাংশন
# ============================================================

async def get_ip_info():
    try:
        success, text, _ = await safe_api_call("https://ipinfo.io/json", method='GET')
        if success:
            data = json.loads(text)
            return f"📍 **IP তথ্য**\n\n🌐 IP: `{data.get('ip', 'N/A')}`\n📍 লোকেশন: {data.get('city', 'N/A')}, {data.get('region', 'N/A')}\n🌍 দেশ: {data.get('country', 'N/A')}"
        return "❌ IP তথ্য পাওয়া যায়নি!"
    except:
        return "❌ ত্রুটি!"

async def get_zip_info(country, zip_code):
    try:
        success, text, _ = await safe_api_call(f"https://api.zippopotam.us/{country}/{zip_code}", method='GET')
        if success:
            data = json.loads(text)
            places = data.get('places', [])
            if places:
                place = places[0]
                return f"📮 **ZIP কোড**\n\n📍 লোকেশন: {place.get('place name', 'N/A')}\n🌍 রাজ্য: {place.get('state', 'N/A')}\n📮 ZIP: {data.get('post code', 'N/A')}"
        return "❌ ZIP কোড তথ্য পাওয়া যায়নি!"
    except:
        return "❌ ত্রুটি!"

async def get_movie_info(title):
    try:
        success, text, _ = await safe_api_call(f"http://www.omdbapi.com/?t={title}&apikey=9f5a7d8e", method='GET')
        if success:
            data = json.loads(text)
            if data.get('Response') == 'True':
                return f"🎬 **মুভি**\n\n📽️ টাইটেল: {data.get('Title', 'N/A')}\n📅 বছর: {data.get('Year', 'N/A')}\n⭐ রেটিং: {data.get('imdbRating', 'N/A')}/10"
        return f"❌ '{title}' মুভি পাওয়া যায়নি!"
    except:
        return "❌ ত্রুটি!"

# ============================================================
# 🚀 স্টার্ট
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    conn = await get_db()
    await conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user_id, user.username or "", user.first_name or "")
    )
    await conn.execute(
        "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
        (user_id,)
    )
    await conn.execute(
        "UPDATE users SET referral_code = ? WHERE user_id = ? AND referral_code IS NULL",
        (generate_referral_code(user_id), user_id)
    )
    await conn.commit()
    
    has_access, access_data = await check_user_access(user_id)
    
    if not has_access:
        msg, keyboard = access_data
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        return
    
    if user_id == ADMIN_ID:
        await update.message.reply_text(
            "🛡️ **অ্যাডমিন প্যানেল**\n\nস্বাগতম!",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
        return
    
    welcome_msg = get_setting('welcome_message', '🎉 **স্বাগতম!**')
    welcome_msg = welcome_msg.replace('{user}', user.first_name or '')
    
    await update.message.reply_text(
        f"{welcome_msg}\n\n📌 **একটি অপশন নির্বাচন করুন:**",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# ============================================================
# 👑 প্রিমিয়াম কেনা
# ============================================================

async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = await get_db()
    cursor = await conn.execute("SELECT is_premium, premium_expiry, balance FROM users WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    
    if not row:
        await update.message.reply_text("❌ ইউজার পাওয়া যায়নি!", reply_markup=get_main_keyboard())
        return
    
    if row[0] == 1 and not is_premium_expired(row[1]):
        await update.message.reply_text("✅ আপনি ইতিমধ্যে প্রিমিয়াম!", reply_markup=get_main_keyboard())
        return
    
    if row[0] == 1 and is_premium_expired(row[1]):
        await conn.execute("UPDATE users SET is_premium = 0, premium_expiry = NULL WHERE user_id = ?", (user_id,))
        row = (0, None, row[2])
    
    price = int(get_setting('premium_price', '100'))
    duration = int(get_setting('premium_duration', '30'))
    
    if row[2] < price:
        await update.message.reply_text(
            f"❌ পর্যাপ্ত ক্রেডিট নেই!\n\n💰 প্রয়োজন: {price}\n💰 আপনার: {row[2]}",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return
    
    expiry = (datetime.now() + timedelta(days=duration)).isoformat()
    await conn.execute(
        "UPDATE users SET is_premium = 1, premium_expiry = ?, balance = balance - ? WHERE user_id = ?",
        (expiry, price, user_id)
    )
    await conn.commit()
    await track_transaction(user_id, "spend", -price, f"Bought premium ({duration} days)")
    
    await update.message.reply_text(
        f"🎉 **প্রিমিয়াম সক্রিয়!**\n\n📅 সময়কাল: {duration} দিন",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# ============================================================
# 📝 মেইন হ্যান্ডলার
# ============================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global SMS_ACTIVE
    
    user_id = update.effective_user.id
    message = update.message.text
    state = context.user_data.get('state')
    admin_state = context.user_data.get('admin_state')
    
    # ===== ব্যাক বাটন =====
    if message == "🔙 Back":
        context.user_data.clear()
        if user_id == ADMIN_ID:
            await update.message.reply_text("🛡️ **অ্যাডমিন**", parse_mode="Markdown", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text("🏠 **মেইন**", parse_mode="Markdown", reply_markup=get_main_keyboard())
        return
    
    # ============================================================
    # 🛡️ অ্যাডমিন মেনু
    # ============================================================
    if user_id == ADMIN_ID:
        if message == "👥 User Control":
            await update.message.reply_text("👥 **ইউজার কন্ট্রোল**", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
            return
        if message == "📢 Group Control":
            await update.message.reply_text("📢 **গ্রুপ কন্ট্রোল**", parse_mode="Markdown", reply_markup=get_group_control_keyboard())
            return
        if message == "💰 Balance Control":
            await update.message.reply_text("💰 **ব্যালেন্স কন্ট্রোল**", parse_mode="Markdown", reply_markup=get_balance_keyboard())
            return
        if message == "🎟️ Redeem Control":
            await update.message.reply_text("🎟️ **রিডিম কন্ট্রোল**", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
            return
        if message == "📡 SMS API Settings":
            await update.message.reply_text(
                "📡 **SMS API সেটিংস**\n\nআপনার কাস্টম API কনফিগার করুন।",
                parse_mode="Markdown",
                reply_markup=get_sms_api_keyboard()
            )
            return
        if message == "🎁 Bonus Control":
            await update.message.reply_text(
                "🎁 **বোনাস কন্ট্রোল**\n\n"
                "`DAILY ON` - চালু\n"
                "`DAILY OFF` - বন্ধ\n"
                "`DAILY AMOUNT 10` - বোনাস পরিবর্তন\n"
                "`DAILY COOLDOWN 12` - কুলডাউন",
                parse_mode="Markdown"
            )
            context.user_data['admin_state'] = 'bonus_control'
            return
        if message == "📈 Reports":
            conn = await get_db()
            cursor = await conn.execute("SELECT COUNT(*) FROM users")
            total = await cursor.fetchone()
            cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
            active = await cursor.fetchone()
            cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
            premium = await cursor.fetchone()
            cursor = await conn.execute("SELECT COUNT(*) FROM sms_history")
            sms_count = await cursor.fetchone()
            cursor = await conn.execute("SELECT COUNT(*) FROM transactions")
            trans = await cursor.fetchone()
            await update.message.reply_text(
                f"📊 **রিপোর্ট**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"👥 মোট ইউজার: `{total[0]}`\n"
                f"✅ অ্যাক্টিভ: `{active[0]}`\n"
                f"👑 প্রিমিয়াম: `{premium[0]}`\n"
                f"📨 মোট SMS: `{sms_count[0]}`\n"
                f"📝 ট্রানজেকশন: `{trans[0]}`",
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard()
            )
            return
        if message == "🔧 Settings":
            daily_enabled = get_setting('daily_bonus_enabled', 'true')
            daily_amount = get_setting('daily_bonus_amount', '1')
            sms_cost = get_setting('sms_cost', '1')
            bulk_cost = get_setting('bulk_sms_cost', '1')
            await update.message.reply_text(
                f"🔧 **সেটিংস**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"⭐ ডেইলি বোনাস: {'✅' if daily_enabled == 'true' else '❌'}\n"
                f"💰 বোনাস: `{daily_amount}`\n"
                f"📨 SMS খরচ: `{sms_cost}`\n"
                f"📤 Bulk খরচ: `{bulk_cost}`\n\n"
                f"💡 কমান্ড: `SET sms_cost 2`",
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard()
            )
            context.user_data['admin_state'] = 'settings_edit'
            return
        if message == "📣 Broadcast":
            await update.message.reply_text("📣 **Broadcast**\n\nমেসেজ দিন:", parse_mode="Markdown")
            context.user_data['admin_state'] = 'broadcast'
            return
        if message == "📨 Test SMS":
            await update.message.reply_text("📨 **Test SMS**\n\nFormat: `NUMBER MESSAGE`", parse_mode="Markdown")
            context.user_data['admin_state'] = 'test_sms'
            return
        if message == "🔄 Restart Bot":
            await update.message.reply_text("🔄 **রিস্টার্ট হচ্ছে...**", parse_mode="Markdown")
            await asyncio.sleep(2)
            os.execv(sys.executable, [sys.executable] + sys.argv)
            return
        if message == "🔙 Exit Admin":
            await update.message.reply_text("👤 **ইউজার মোড**", parse_mode="Markdown", reply_markup=get_main_keyboard())
            return

    # ============================================================
    # 📡 SMS API সেটিংস (Admin)
    # ============================================================
    if user_id == ADMIN_ID:
        if message == "🔗 Set API URL":
            await update.message.reply_text(
                f"🔗 **Set API URL**\n\nবর্তমান: `{get_setting('sms_api_url', 'N/A')}`\n\nনতুন URL দিন:",
                parse_mode="Markdown"
            )
            context.user_data['admin_state'] = 'set_api_url'
            return
        if message == "🔑 Set API Key":
            await update.message.reply_text(
                f"🔑 **Set API Key**\n\nবর্তমান: `{get_setting('sms_api_key', 'N/A')}`\n\nনতুন Key দিন:",
                parse_mode="Markdown"
            )
            context.user_data['admin_state'] = 'set_api_key'
            return
        if message == "📛 Set Sender ID":
            await update.message.reply_text(
                f"📛 **Set Sender ID**\n\nবর্তমান: `{get_setting('sms_sender_id', '(none)')}`\n\nনতুন Sender ID দিন (খালি রাখলে বাদ যাবে):",
                parse_mode="Markdown"
            )
            context.user_data['admin_state'] = 'set_sender_id'
            return
        if message == "📋 View API Config":
            api_url = get_setting('sms_api_url', 'N/A')
            api_key = get_setting('sms_api_key', 'N/A')
            sender_id = get_setting('sms_sender_id', '(none)')
            masked_key = api_key[:4] + "***" + api_key[-4:] if len(api_key) > 8 else "***"
            await update.message.reply_text(
                f"📋 **SMS API কনফিগারেশন**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"🔗 URL: `{api_url}`\n"
                f"🔑 Key: `{masked_key}`\n"
                f"📛 Sender ID: `{sender_id}`",
                parse_mode="Markdown",
                reply_markup=get_sms_api_keyboard()
            )
            return
        if message == "🧪 Test API":
            await update.message.reply_text("🧪 **Test API**\n\nটেস্ট নম্বর দিন:", parse_mode="Markdown")
            context.user_data['admin_state'] = 'test_api_number'
            return

        if admin_state == 'set_api_url':
            await update_setting('sms_api_url', message.strip())
            await load_sms_api()
            await admin_log(user_id, "Set SMS API URL", None, f"API URL updated")
            await update.message.reply_text("✅ API URL আপডেট!", reply_markup=get_sms_api_keyboard())
            context.user_data['admin_state'] = None
            return
        
        if admin_state == 'set_api_key':
            await update_setting('sms_api_key', message.strip())
            await load_sms_api()
            await admin_log(user_id, "Set SMS API Key", None, f"API Key updated")
            await update.message.reply_text("✅ API Key আপডেট!", reply_markup=get_sms_api_keyboard())
            context.user_data['admin_state'] = None
            return
        
        if admin_state == 'set_sender_id':
            await update_setting('sms_sender_id', message.strip())
            await load_sms_api()
            await admin_log(user_id, "Set Sender ID", None, f"Sender ID updated")
            await update.message.reply_text("✅ Sender ID আপডেট!", reply_markup=get_sms_api_keyboard())
            context.user_data['admin_state'] = None
            return
        
        if admin_state == 'test_api_number':
            context.user_data['test_number'] = message.strip()
            context.user_data['admin_state'] = 'test_api_message'
            await update.message.reply_text("💬 টেস্ট মেসেজ দিন:")
            return
        
        if admin_state == 'test_api_message':
            number = context.user_data.get('test_number')
            test_msg = message.strip()
            wait_msg = await update.message.reply_text("⏳ টেস্ট পাঠানো হচ্ছে...")
            success, response, raw = await send_sms_api(number, test_msg)
            if success:
                await wait_msg.edit_text(
                    f"✅ **টেস্ট সফল!**\n\n📱 {number}\n💬 {test_msg}\n\n📨 Response: `{raw[:200]}`",
                    parse_mode="Markdown",
                    reply_markup=get_sms_api_keyboard()
                )
            else:
                await wait_msg.edit_text(
                    f"❌ **টেস্ট ব্যর্থ!**\n\n📱 {number}\n\n📨 Response: `{raw[:200]}`",
                    parse_mode="Markdown",
                    reply_markup=get_sms_api_keyboard()
                )
            context.user_data['admin_state'] = None
            return
        
        if admin_state == 'settings_edit':
            parts = message.split()
            if len(parts) == 3 and parts[0].upper() == 'SET':
                key = parts[1].lower()
                value = parts[2]
                allowed = ['sms_cost', 'bulk_sms_cost', 'max_bulk_numbers', 'bulk_sms_interval', 
                          'phone_prefixes', 'phone_length', 'premium_price', 'premium_duration',
                          'daily_bonus_amount', 'daily_bonus_cooldown']
                if key in allowed:
                    await update_setting(key, value)
                    await admin_log(user_id, "Updated Setting", None, f"{key} = {value}")
                    await update.message.reply_text(f"✅ `{key}` = `{value}` সেট!", parse_mode="Markdown", reply_markup=get_admin_keyboard())
                else:
                    await update.message.reply_text(f"❌ এই সেটিং পরিবর্তন করা যাবে না!\n\nAllowed: {', '.join(allowed)}", parse_mode="Markdown", reply_markup=get_admin_keyboard())
            else:
                await update.message.reply_text("❌ Format: `SET key value`", parse_mode="Markdown", reply_markup=get_admin_keyboard())
            context.user_data['admin_state'] = None
            return
        
        if admin_state == 'test_sms':
            parts = message.split(maxsplit=1)
            if len(parts) != 2:
                await update.message.reply_text("❌ Format: `NUMBER MESSAGE`", parse_mode="Markdown", reply_markup=get_admin_keyboard())
                return
            number, msg = parts[0].strip(), parts[1].strip()
            valid, vmsg = validate_phone(number)
            if not valid:
                await update.message.reply_text(f"❌ {vmsg}", parse_mode="Markdown", reply_markup=get_admin_keyboard())
                return
            wait = await update.message.reply_text("⏳ পাঠানো হচ্ছে...")
            success, response, raw = await send_sms_api(number, msg)
            if success:
                await wait.edit_text(f"✅ **সফল!**\n📱 `{number}`\n📨 `{raw[:200]}`", parse_mode="Markdown", reply_markup=get_admin_keyboard())
            else:
                await wait.edit_text(f"❌ **ব্যর্থ!**\n📱 `{number}`\n📨 `{raw[:200]}`", parse_mode="Markdown", reply_markup=get_admin_keyboard())
            context.user_data['admin_state'] = None
            return
    
    # ============================================================
    # 👥 ইউজার কন্ট্রোল
    # ============================================================
    if message == "🚫 Block User":
        await update.message.reply_text("🚫 **Block User**\n\nইউজার আইডি দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'block_user'
        return
    if message == "✅ Unblock User":
        await update.message.reply_text("✅ **Unblock User**\n\nইউজার আইডি দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'unblock_user'
        return
    if message == "ℹ️ User Info":
        await update.message.reply_text("ℹ️ **User Info**\n\nইউজার আইডি দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'user_info'
        return
    if message == "📋 List Users":
        conn = await get_db()
        cursor = await conn.execute("SELECT user_id, username, first_name, balance, status, is_premium FROM users ORDER BY user_id DESC LIMIT 20")
        users = await cursor.fetchall()
        if users:
            response = "📋 **ইউজার লিস্ট**\n━━━━━━━━━━━━━━━━━━━\n\n"
            for i, user in enumerate(users, 1):
                status = "🟢" if user[4] == 'active' else "🔴"
                premium = "👑" if user[5] == 1 else ""
                name = user[2] or user[1] or f"User{user[0]}"
                response += f"{i}. {status} `{user[0]}` - {name} - 💰{user[3]} {premium}\n"
            await update.message.reply_text(response, parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        else:
            await update.message.reply_text("👥 কোনো ইউজার নেই!", reply_markup=get_user_control_keyboard())
        return
    if message == "👑 Make Premium":
        await update.message.reply_text("👑 **Make Premium**\n\nইউজার আইডি দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'make_premium'
        return
    if message == "❌ Remove Premium":
        await update.message.reply_text("❌ **Remove Premium**\n\nইউজার আইডি দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'remove_premium'
        return
    if message == "🗑️ Delete User":
        await update.message.reply_text("🗑️ **Delete User**\n\nইউজার আইডি দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'delete_user'
        return
    
    if admin_state == 'block_user':
        try:
            target_id = int(message.strip())
            conn = await get_db()
            await conn.execute("UPDATE users SET status = 'banned' WHERE user_id = ?", (target_id,))
            await conn.commit()
            await admin_log(user_id, "Blocked User", target_id, f"User {target_id} blocked")
            await update.message.reply_text(f"🚫 ইউজার `{target_id}` ব্লক!", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        except:
            await update.message.reply_text("❌ ভুল আইডি!", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'unblock_user':
        try:
            target_id = int(message.strip())
            conn = await get_db()
            await conn.execute("UPDATE users SET status = 'active' WHERE user_id = ?", (target_id,))
            await conn.commit()
            await admin_log(user_id, "Unblocked User", target_id, f"User {target_id} unblocked")
            await update.message.reply_text(f"✅ ইউজার `{target_id}` আনব্লক!", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        except:
            await update.message.reply_text("❌ ভুল আইডি!", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'user_info':
        try:
            target_id = int(message.strip())
            conn = await get_db()
            cursor = await conn.execute(
                "SELECT username, first_name, balance, status, is_premium, total_sms, total_bulk, join_date FROM users WHERE user_id = ?",
                (target_id,)
            )
            row = await cursor.fetchone()
            if row:
                is_prem = row[4] == 1
                await update.message.reply_text(
                    f"ℹ️ **ইউজার তথ্য**\n━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🆔 আইডি: `{target_id}`\n"
                    f"👤 নাম: {row[1] or 'N/A'}\n"
                    f"📛 ইউজারনেম: @{row[0] or 'N/A'}\n"
                    f"💰 ব্যালেন্স: `{row[2]}`\n"
                    f"📨 এসএমএস: `{row[5]}`\n"
                    f"📤 বাল্ক: `{row[6]}`\n"
                    f"👑 প্রিমিয়াম: {'✅' if is_prem else '❌'}\n"
                    f"🚦 স্ট্যাটাস: {row[3]}\n"
                    f"📅 যোগদান: {row[7][:10] if row[7] else 'N/A'}",
                    parse_mode="Markdown",
                    reply_markup=get_user_control_keyboard()
                )
            else:
                await update.message.reply_text("❌ ইউজার পাওয়া যায়নি!", reply_markup=get_user_control_keyboard())
        except:
            await update.message.reply_text("❌ ভুল আইডি!", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'make_premium':
        try:
            target_id = int(message.strip())
            expiry = (datetime.now() + timedelta(days=30)).isoformat()
            conn = await get_db()
            await conn.execute("UPDATE users SET is_premium = 1, premium_expiry = ? WHERE user_id = ?", (expiry, target_id))
            await conn.commit()
            await admin_log(user_id, "Made Premium", target_id, f"User {target_id} made premium")
            await update.message.reply_text(f"👑 ইউজার `{target_id}` প্রিমিয়াম!", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        except:
            await update.message.reply_text("❌ ভুল আইডি!", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'remove_premium':
        try:
            target_id = int(message.strip())
            conn = await get_db()
            await conn.execute("UPDATE users SET is_premium = 0, premium_expiry = NULL WHERE user_id = ?", (target_id,))
            await conn.commit()
            await admin_log(user_id, "Removed Premium", target_id, f"Premium removed")
            await update.message.reply_text(f"❌ ইউজার `{target_id}` প্রিমিয়াম রিমুভ!", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        except:
            await update.message.reply_text("❌ ভুল আইডি!", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'delete_user':
        try:
            target_id = int(message.strip())
            conn = await get_db()
            await conn.execute("DELETE FROM users WHERE user_id = ?", (target_id,))
            await conn.commit()
            await admin_log(user_id, "Deleted User", target_id, f"User {target_id} deleted")
            await update.message.reply_text(f"🗑️ ইউজার `{target_id}` ডিলিট!", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        except:
            await update.message.reply_text("❌ ভুল আইডি!", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    # ============================================================
    # 📢 গ্রুপ কন্ট্রোল
    # ============================================================
    if message == "📢 Set Channel":
        await update.message.reply_text("📢 চ্যানেল ইউজারনেম দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'set_channel'
        return
    if message == "👥 Set Group":
        await update.message.reply_text("👥 গ্রুপ ইউজারনেম দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'set_group'
        return
    if message == "🔗 Set Channel Link":
        await update.message.reply_text("🔗 চ্যানেল লিংক দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'set_channel_link'
        return
    if message == "🔗 Set Group Link":
        await update.message.reply_text("🔗 গ্রুপ লিংক দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'set_group_link'
        return
    if message == "✏️ Set Welcome":
        await update.message.reply_text("✏️ নতুন ওয়েলকাম মেসেজ দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'set_welcome'
        return
    if message == "🚫 Set Denied":
        await update.message.reply_text("🚫 ডিনাই মেসেজ দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'set_denied'
        return
    if message == "✅ Enable Join":
        await update_setting("join_required_enabled", "true")
        await update.message.reply_text("✅ জয়েন রিকোয়ার্ড চালু!", reply_markup=get_group_control_keyboard())
        return
    if message == "❌ Disable Join":
        await update_setting("join_required_enabled", "false")
        await update.message.reply_text("❌ জয়েন রিকোয়ার্ড বন্ধ!", reply_markup=get_group_control_keyboard())
        return
    if message == "📊 View Settings":
        channel = get_setting('required_channel', 'সেট করা নেই')
        group = get_setting('required_group', 'সেট করা নেই')
        channel_link = get_setting('required_channel_link', 'সেট করা নেই')
        group_link = get_setting('required_group_link', 'সেট করা নেই')
        join_enabled = get_setting('join_required_enabled', 'false')
        await update.message.reply_text(
            f"📊 **সেটিংস**\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"📢 চ্যানেল: `{channel}`\n"
            f"👥 গ্রুপ: `{group}`\n"
            f"🔗 চ্যানেল লিংক: `{channel_link}`\n"
            f"🔗 গ্রুপ লিংক: `{group_link}`\n"
            f"✅ জয়েন রিকোয়ার্ড: {'✅ চালু' if join_enabled == 'true' else '❌ বন্ধ'}",
            parse_mode="Markdown",
            reply_markup=get_group_control_keyboard()
        )
        return
    
    if admin_state == 'set_channel':
        channel = message.strip()
        if not channel.startswith('@') and not channel.startswith('-'):
            channel = '@' + channel
        await update_setting("required_channel", channel)
        await update.message.reply_text(f"✅ চ্যানেল সেট: {channel}", reply_markup=get_group_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'set_group':
        group = message.strip()
        if not group.startswith('@') and not group.startswith('-'):
            group = '@' + group
        await update_setting("required_group", group)
        await update.message.reply_text(f"✅ গ্রুপ সেট: {group}", reply_markup=get_group_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'set_channel_link':
        await update_setting("required_channel_link", message.strip())
        await update.message.reply_text("✅ চ্যানেল লিংক সেট!", reply_markup=get_group_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'set_group_link':
        await update_setting("required_group_link", message.strip())
        await update.message.reply_text("✅ গ্রুপ লিংক সেট!", reply_markup=get_group_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'set_welcome':
        await update_setting("welcome_message", message.strip())
        await update.message.reply_text("✅ ওয়েলকাম মেসেজ সেট!", reply_markup=get_group_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'set_denied':
        await update_setting("denied_message", message.strip())
        await update.message.reply_text("✅ ডিনাই মেসেজ সেট!", reply_markup=get_group_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    # ============================================================
    # 💰 ব্যালেন্স কন্ট্রোল
    # ============================================================
    if message == "🟢 Add Credit":
        await update.message.reply_text("🟢 Format: `USER_ID AMOUNT`", parse_mode="Markdown")
        context.user_data['admin_state'] = 'add_credit'
        return
    if message == "🔴 Remove Credit":
        await update.message.reply_text("🔴 Format: `USER_ID AMOUNT`", parse_mode="Markdown")
        context.user_data['admin_state'] = 'remove_credit'
        return
    if message == "🎁 Gift All":
        await update.message.reply_text("🎁 পরিমাণ দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'gift_all'
        return
    if message == "🎁 Gift User":
        await update.message.reply_text("🎁 Format: `USER_ID AMOUNT`", parse_mode="Markdown")
        context.user_data['admin_state'] = 'gift_user'
        return
    if message == "📝 Set Balance":
        await update.message.reply_text("📝 Format: `USER_ID AMOUNT`", parse_mode="Markdown")
        context.user_data['admin_state'] = 'set_balance'
        return
    if message == "🔄 Reset All":
        await update.message.reply_text("🔄 সব ইউজারের ব্যালেন্স ০ করতে চান? (হ্যাঁ/না)", parse_mode="Markdown")
        context.user_data['admin_state'] = 'reset_all'
        return
    if message == "📊 Report":
        conn = await get_db()
        cursor = await conn.execute("SELECT SUM(balance), AVG(balance), MAX(balance), COUNT(*) FROM users")
        stats = await cursor.fetchone()
        await update.message.reply_text(
            f"📊 **ব্যালেন্স রিপোর্ট**\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 মোট ইউজার: `{stats[3]}`\n"
            f"💰 মোট ব্যালেন্স: `{stats[0] or 0}`\n"
            f"📊 গড়: `{round(stats[1] or 0, 2)}`\n"
            f"📈 সর্বোচ্চ: `{stats[2]}`",
            parse_mode="Markdown",
            reply_markup=get_balance_keyboard()
        )
        return
    
    if admin_state == 'add_credit':
        try:
            parts = message.split()
            target_id, amount = int(parts[0]), int(parts[1])
            conn = await get_db()
            await conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
            await conn.commit()
            await track_transaction(target_id, "add", amount, "Admin added")
            await update.message.reply_text(f"✅ `{target_id}` কে `{amount}` ক্রেডিট যোগ!", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        except:
            await update.message.reply_text("❌ Format: `USER_ID AMOUNT`", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'remove_credit':
        try:
            parts = message.split()
            target_id, amount = int(parts[0]), int(parts[1])
            conn = await get_db()
            await conn.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, target_id))
            await conn.commit()
            await track_transaction(target_id, "remove", -amount, "Admin removed")
            await update.message.reply_text(f"✅ `{target_id}` থেকে `{amount}` কাটা!", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        except:
            await update.message.reply_text("❌ Format: `USER_ID AMOUNT`", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'gift_all':
        try:
            amount = int(message.strip())
            conn = await get_db()
            await conn.execute("UPDATE users SET balance = balance + ?", (amount,))
            await conn.commit()
            cursor = await conn.execute("SELECT COUNT(*) FROM users")
            count = await cursor.fetchone()
            await update.message.reply_text(f"🎁 {count[0]} জনকে `{amount}` ক্রেডিট!", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        except:
            await update.message.reply_text("❌ সংখ্যা দিন!", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'gift_user':
        try:
            parts = message.split()
            target_id, amount = int(parts[0]), int(parts[1])
            conn = await get_db()
            await conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
            await conn.commit()
            await track_transaction(target_id, "gift", amount, "Admin gifted")
            await update.message.reply_text(f"🎁 `{target_id}` কে `{amount}` ক্রেডিট!", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        except:
            await update.message.reply_text("❌ Format: `USER_ID AMOUNT`", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'set_balance':
        try:
            parts = message.split()
            target_id, amount = int(parts[0]), int(parts[1])
            conn = await get_db()
            await conn.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, target_id))
            await conn.commit()
            await update.message.reply_text(f"✅ `{target_id}` ব্যালেন্স `{amount}` সেট!", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        except:
            await update.message.reply_text("❌ Format: `USER_ID AMOUNT`", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'reset_all':
        if message.lower() in ['হ্যাঁ', 'yes', 'y']:
            conn = await get_db()
            await conn.execute("UPDATE users SET balance = 0")
            await conn.commit()
            await update.message.reply_text("🔄 সব ব্যালেন্স ০!", reply_markup=get_balance_keyboard())
        else:
            await update.message.reply_text("❌ বাতিল!", reply_markup=get_balance_keyboard())
        context.user_data['admin_state'] = None
        return
    
    # ============================================================
    # 🎟️ রিডিম কন্ট্রোল
    # ============================================================
    if message == "➕ Create Code":
        await update.message.reply_text("➕ Format: `CODE AMOUNT USAGES`\nExample: `BONUS25 25 50`", parse_mode="Markdown")
        context.user_data['admin_state'] = 'create_code'
        return
    if message == "❌ Delete Code":
        await update.message.reply_text("❌ কোড দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'delete_code'
        return
    if message == "🗑️ Delete All":
        conn = await get_db()
        await conn.execute("DELETE FROM redeem_codes")
        await conn.commit()
        await update.message.reply_text("🗑️ সব কোড ডিলিট!", reply_markup=get_redeem_keyboard())
        return
    if message == "✏️ Edit Code":
        await update.message.reply_text("✏️ Format: `CODE NEW_AMOUNT NEW_USAGES`", parse_mode="Markdown")
        context.user_data['admin_state'] = 'edit_code'
        return
    if message == "📋 List Codes":
        conn = await get_db()
        cursor = await conn.execute("SELECT code, amount, usages FROM redeem_codes ORDER BY created_at DESC")
        codes = await cursor.fetchall()
        if codes:
            response = "🎟️ **সব কোড**\n━━━━━━━━━━━━━━━━━━━\n\n"
            for code in codes:
                status = "✅" if code[2] > 0 else "❌"
                response += f"{status} `{code[0]}` → 💰{code[1]} (বাকি: {code[2]})\n"
            await update.message.reply_text(response, parse_mode="Markdown", reply_markup=get_redeem_keyboard())
        else:
            await update.message.reply_text("📭 কোনো কোড নেই!", reply_markup=get_redeem_keyboard())
        return
    
    if admin_state == 'create_code':
        try:
            parts = message.split()
            code, amount, usages = parts[0].upper(), int(parts[1]), int(parts[2])
            conn = await get_db()
            await conn.execute(
                "INSERT INTO redeem_codes (code, amount, usages, created_by) VALUES (?, ?, ?, ?)",
                (code, amount, usages, user_id)
            )
            await conn.commit()
            await update.message.reply_text(f"✅ কোড `{code}` তৈরি! (💰{amount})", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
        except:
            await update.message.reply_text("❌ Format: `CODE AMOUNT USAGES`", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'delete_code':
        try:
            code = message.strip().upper()
            conn = await get_db()
            await conn.execute("DELETE FROM redeem_codes WHERE code = ?", (code,))
            await conn.commit()
            await update.message.reply_text(f"🗑️ কোড `{code}` ডিলিট!", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
        except:
            await update.message.reply_text("❌ ত্রুটি!", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'edit_code':
        try:
            parts = message.split()
            code, amount, usages = parts[0].upper(), int(parts[1]), int(parts[2])
            conn = await get_db()
            await conn.execute("UPDATE redeem_codes SET amount = ?, usages = ? WHERE code = ?", (amount, usages, code))
            await conn.commit()
            await update.message.reply_text(f"✅ কোড `{code}` আপডেট!", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
        except:
            await update.message.reply_text("❌ Format: `CODE NEW_AMOUNT NEW_USAGES`", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
        context.user_data['admin_state'] = None
        return
    
    # ============================================================
    # 🎁 বোনাস কন্ট্রোল
    # ============================================================
    if admin_state == 'bonus_control':
        parts = message.split()
        cmd = parts[0].upper() if parts else ""
        if cmd == 'DAILY' and len(parts) >= 2:
            if parts[1].upper() == 'ON':
                await update_setting("daily_bonus_enabled", "true")
                await update.message.reply_text("✅ ডেইলি বোনাস চালু!", reply_markup=get_admin_keyboard())
            elif parts[1].upper() == 'OFF':
                await update_setting("daily_bonus_enabled", "false")
                await update.message.reply_text("❌ ডেইলি বোনাস বন্ধ!", reply_markup=get_admin_keyboard())
            elif parts[1].upper() == 'AMOUNT' and len(parts) >= 3:
                await update_setting("daily_bonus_amount", parts[2])
                await update.message.reply_text(f"💰 বোনাস `{parts[2]}`!", parse_mode="Markdown", reply_markup=get_admin_keyboard())
            elif parts[1].upper() == 'COOLDOWN' and len(parts) >= 3:
                await update_setting("daily_bonus_cooldown", parts[2])
                await update.message.reply_text(f"⏰ কুলডাউন `{parts[2]}` ঘণ্টা!", parse_mode="Markdown", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text("❌ ভুল কমান্ড!", reply_markup=get_admin_keyboard())
        context.user_data['admin_state'] = None
        return
    
    # ============================================================
    # 📣 ব্রডকাস্ট
    # ============================================================
    if admin_state == 'broadcast':
        conn = await get_db()
        cursor = await conn.execute("SELECT user_id FROM users WHERE status = 'active'")
        users = await cursor.fetchall()
        success = 0
        for user in users:
            try:
                await context.bot.send_message(user[0], f"📢 **ব্রডকাস্ট**\n\n{message}", parse_mode='Markdown')
                success += 1
                await asyncio.sleep(0.02)
            except:
                pass
        await update.message.reply_text(f"✅ {success} জনে ব্রডকাস্ট!", reply_markup=get_admin_keyboard())
        context.user_data['admin_state'] = None
        return
    
    # ============================================================
    # 👤 ইউজার মেনু
    # ============================================================
    if message == "📨 Send SMS":
        await update.message.reply_text("📨 **Send SMS**\n\nফোন নম্বর দিন:", parse_mode="Markdown")
        context.user_data['state'] = 'sms_number'
        return
    
    if message == "📤 Bulk SMS":
        await update.message.reply_text("📤 **Bulk SMS**\n\nনম্বরগুলো দিন (কমা বা স্পেস দিয়ে):", parse_mode="Markdown")
        context.user_data['state'] = 'bulk_numbers'
        return
    
    if message == "👤 My Profile":
        conn = await get_db()
        cursor = await conn.execute(
            "SELECT username, first_name, balance, total_sms, total_bulk, is_premium, premium_expiry, join_date FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            is_prem = row[5] == 1 and not is_premium_expired(row[6])
            msg = f"👤 **প্রোফাইল**\n━━━━━━━━━━━━━━━━━━━\n\n"
            msg += f"👤 নাম: {row[1] or 'N/A'}\n"
            msg += f"📛 ইউজারনেম: @{row[0] or 'N/A'}\n"
            msg += f"💰 ব্যালেন্স: `{row[2]}`\n"
            msg += f"📨 এসএমএস: `{row[3]}`\n"
            msg += f"📤 বাল্ক: `{row[4]}`\n"
            msg += f"👑 প্রিমিয়াম: {'✅' if is_prem else '❌'}\n"
            msg += f"📅 যোগদান: {row[7][:10] if row[7] else 'N/A'}\n\n"
            msg += f"📌 রেফারেল: `{generate_referral_code(user_id)}`"
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())
        return
    
    if message == "📊 My Stats":
        conn = await get_db()
        cursor = await conn.execute(
            "SELECT total_sms, total_bulk, balance FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            # আজকের SMS
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM sms_history WHERE user_id = ? AND DATE(sent_at) = DATE('now')",
                (user_id,)
            )
            today = await cursor.fetchone()
            # সফল SMS
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM sms_history WHERE user_id = ? AND status = 'success'",
                (user_id,)
            )
            success = await cursor.fetchone()
            # ব্যর্থ
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM sms_history WHERE user_id = ? AND status = 'failed'",
                (user_id,)
            )
            failed = await cursor.fetchone()
            
            await update.message.reply_text(
                f"📊 **আপনার স্ট্যাটস**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 ব্যালেন্স: `{row[2]}`\n"
                f"📨 মোট SMS: `{row[0]}`\n"
                f"📤 Bulk অপারেশন: `{row[1]}`\n"
                f"📅 আজকের SMS: `{today[0]}`\n"
                f"✅ সফল: `{success[0]}`\n"
                f"❌ ব্যর্থ: `{failed[0]}`",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        return
    
    if message == "🎁 Redeem Code":
        await update.message.reply_text("🎁 **রিডিম কোড দিন:**", parse_mode="Markdown")
        context.user_data['state'] = 'redeem_code'
        return
    
    if message == "📞 Support":
        support = get_setting('support_username', ADMIN_USERNAME)
        keyboard = [
            [InlineKeyboardButton("📩 অ্যাডমিন", url=f"https://t.me/{support}")],
            [InlineKeyboardButton("📢 চ্যানেল", url="https://t.me/RobiEntertainment")]
        ]
        await update.message.reply_text(
            f"📞 **যোগাযোগ**\n\n👨‍💻 অ্যাডমিন: @{support}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    if message == "⭐ Daily Bonus":
        if get_setting('daily_bonus_enabled', 'false') != 'true':
            await update.message.reply_text("❌ ডেইলি বোনাস বন্ধ!", reply_markup=get_main_keyboard())
            return
        conn = await get_db()
        cursor = await conn.execute("SELECT daily_bonus_date, is_premium, premium_expiry FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            is_prem = row[1] == 1 and not is_premium_expired(row[2])
            bonus = int(get_setting('premium_bonus' if is_prem else 'daily_bonus_amount', '10' if is_prem else '1'))
            cooldown = int(get_setting('daily_bonus_cooldown', '24'))
            if row[0]:
                try:
                    last = datetime.fromisoformat(row[0])
                    if (datetime.now() - last).total_seconds() < (cooldown * 3600):
                        remaining = (cooldown * 3600) - (datetime.now() - last).total_seconds()
                        hours = int(remaining // 3600)
                        minutes = int((remaining % 3600) // 60)
                        await update.message.reply_text(f"⏳ {hours}ঘ {minutes}মি বাকি", reply_markup=get_main_keyboard())
                        return
                except:
                    pass
            await conn.execute(
                "UPDATE users SET balance = balance + ?, daily_bonus_date = ? WHERE user_id = ?",
                (bonus, datetime.now().isoformat(), user_id)
            )
            await conn.commit()
            await track_transaction(user_id, "bonus", bonus, "Daily bonus")
            await update.message.reply_text(f"🎉 +{bonus} ক্রেডিট!", reply_markup=get_main_keyboard())
        return
    
    if message == "🏆 Leaderboard":
        conn = await get_db()
        cursor = await conn.execute("SELECT user_id, username, first_name, balance FROM users ORDER BY balance DESC LIMIT 10")
        users = await cursor.fetchall()
        if users:
            response = "🏆 **টপ ১০**\n━━━━━━━━━━━━━━━━━━━\n\n"
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            for i, user in enumerate(users):
                name = user[2] or user[1] or f"User{user[0]}"
                response += f"{medals[i]} `{user[0]}` - {name} - 💰{user[3]}\n"
            await update.message.reply_text(response, parse_mode="Markdown", reply_markup=get_main_keyboard())
        return
    
    if message == "👑 Premium":
        conn = await get_db()
        cursor = await conn.execute("SELECT is_premium, premium_expiry, balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            is_prem = row[0] == 1 and not is_premium_expired(row[1])
            text = "👑 **প্রিমিয়াম**\n━━━━━━━━━━━━━━━━━━━\n\n"
            text += "🔹 কম SMS খরচ\n"
            text += "🔹 এক্সট্রা ডেইলি বোনাস\n"
            text += "🔹 প্রায়োরিটি সাপোর্ট\n\n"
            if is_prem:
                text += "✅ **আপনি প্রিমিয়াম!**"
            else:
                price = get_setting('premium_price', '100')
                duration = get_setting('premium_duration', '30')
                text += f"💎 {price} ক্রেডিট / {duration} দিন\n"
                text += "📌 /buy_premium"
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())
        return
    
    # ============================================================
    # 🔮 ইউটিলিটিস
    # ============================================================
    if message == "🔮 Utilities":
        await update.message.reply_text("🔮 **ইউটিলিটিস**", reply_markup=get_utilities_keyboard())
        return
    
    if message == "🌐 IP Info":
        result = await get_ip_info()
        await update.message.reply_text(result, parse_mode="Markdown", reply_markup=get_utilities_keyboard())
        return
    
    if message == "📮 ZIP Code":
        await update.message.reply_text("📮 Format: `COUNTRY ZIP`\nExample: `us 33162`", parse_mode="Markdown")
        context.user_data['state'] = 'zip_info'
        return
    
    if message == "🎬 Movie":
        await update.message.reply_text("🎬 মুভির নাম দিন:", parse_mode="Markdown")
        context.user_data['state'] = 'movie_info'
        return
    
    # ============================================================
    # 📝 স্টেট হ্যান্ডলিং
    # ============================================================
    if state == 'sms_number':
        number = message.strip()
        valid, msg = validate_phone(number)
        if not valid:
            await update.message.reply_text(f"❌ {msg}", parse_mode="Markdown")
            return
        context.user_data['sms_number'] = number
        context.user_data['state'] = 'sms_message'
        await update.message.reply_text(f"✅ `{number}`\n\n💬 মেসেজ দিন:", parse_mode="Markdown")
        return
    
    if state == 'sms_message':
        number = context.user_data.get('sms_number')
        msg = message.strip()
        if not number:
            await update.message.reply_text("❌ ত্রুটি!", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        
        cost = int(get_setting('sms_cost', '1'))
        conn = await get_db()
        cursor = await conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row or row[0] < cost:
            await update.message.reply_text(f"❌ প্রয়োজন: {cost} ক্রেডিট", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        
        wait_msg = await update.message.reply_text(f"⏳ পাঠানো হচ্ছে...", parse_mode="Markdown")
        success, response, raw = await send_sms_api(number, msg)
        
        await save_sms_history(user_id, number, msg, "success" if success else "failed", raw)
        
        if success:
            await conn.execute(
                "UPDATE users SET balance = balance - ?, total_sms = total_sms + 1 WHERE user_id = ?",
                (cost, user_id)
            )
            await conn.commit()
            await track_transaction(user_id, "spend", -cost, f"SMS to {number}")
            await wait_msg.edit_text(
                f"✅ **সফল!**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"📱 `{number}`\n"
                f"💬 {msg[:100]}\n"
                f"💰 খরচ: {cost}",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        else:
            await wait_msg.edit_text(
                f"❌ **ব্যর্থ!**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"📱 `{number}`\n"
                f"📨 Response: `{raw[:200]}`",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        context.user_data.clear()
        return
    
    if state == 'bulk_numbers':
        raw = message.strip()
        numbers = [num.strip() for num in re.split(r'[,\s\n]+', raw) if num.strip()]
        valid = []
        seen = set()
        for num in numbers:
            if num in seen:
                continue
            seen.add(num)
            v, _ = validate_phone(num)
            if v:
                valid.append(num)
        if not valid:
            await update.message.reply_text("❌ কোনো ভ্যালিড নম্বর নেই!", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        max_bulk = int(get_setting('max_bulk_numbers', '100'))
        if len(valid) > max_bulk:
            await update.message.reply_text(f"❌ সর্বোচ্চ {max_bulk}টি!", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        context.user_data['bulk_numbers'] = valid
        context.user_data['state'] = 'bulk_message'
        await update.message.reply_text(f"✅ {len(valid)} টি নম্বর\n\n💬 মেসেজ দিন:", parse_mode="Markdown")
        return
    
    if state == 'bulk_message':
        numbers = context.user_data.get('bulk_numbers', [])
        msg = message.strip()
        if not numbers:
            await update.message.reply_text("❌ ত্রুটি!", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        
        cost_per = int(get_setting('bulk_sms_cost', '1'))
        total = len(numbers)
        total_cost = total * cost_per
        
        conn = await get_db()
        cursor = await conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row or row[0] < total_cost:
            await update.message.reply_text(f"❌ প্রয়োজন: {total_cost} ক্রেডিট", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        
        status_msg = await update.message.reply_text(f"⏳ {total} টি নম্বরে পাঠানো হচ্ছে...", parse_mode="Markdown")
        success_list = []
        failed_list = []
        interval = float(get_setting('bulk_sms_interval', '0.05'))
        
        batch_size = 5
        for i in range(0, total, batch_size):
            batch = numbers[i:i+batch_size]
            tasks = [send_sms_api(num, msg) for num in batch]
            results = await asyncio.gather(*tasks)
            
            for idx, (success, response, raw) in enumerate(results):
                num = batch[idx]
                if success:
                    success_list.append(num)
                    await save_sms_history(user_id, num, msg, "success", raw)
                else:
                    failed_list.append(num)
                    await save_sms_history(user_id, num, msg, "failed", raw)
                
                await conn.execute(
                    "UPDATE users SET balance = balance - ?, total_sms = total_sms + 1 WHERE user_id = ?",
                    (cost_per, user_id)
                )
            
            await conn.commit()
            processed = min(i + batch_size, total)
            try:
                bar = progress_bar(processed, total)
                await status_msg.edit_text(f"⏳ পাঠানো...\n{bar}\n📊 {processed}/{total}", parse_mode="Markdown")
            except:
                pass
            await asyncio.sleep(interval)
        
        await conn.execute("UPDATE users SET total_bulk = total_bulk + 1 WHERE user_id = ?", (user_id,))
        await conn.commit()
        await track_transaction(user_id, "spend", -total_cost, f"Bulk SMS ({len(success_list)} success)")
        
        result = f"✅ **Bulk সম্পূর্ণ!**\n━━━━━━━━━━━━━━━━━━━\n\n"
        result += f"📤 মোট: {total}\n"
        result += f"✅ সফল: {len(success_list)}\n"
        result += f"❌ ব্যর্থ: {len(failed_list)}\n"
        result += f"💰 খরচ: {len(success_list) * cost_per}"
        if failed_list:
            result += f"\n\n❌ ব্যর্থ: {', '.join(failed_list[:5])}"
            if len(failed_list) > 5:
                result += f" এবং আরও {len(failed_list) - 5}টি"
        await status_msg.edit_text(result, parse_mode="Markdown", reply_markup=get_main_keyboard())
        context.user_data.clear()
        return
    
    if state == 'redeem_code':
        code = message.strip().upper()
        conn = await get_db()
        cursor = await conn.execute("SELECT 1 FROM redeem_history WHERE user_id = ? AND code = ?", (user_id, code))
        if await cursor.fetchone():
            await update.message.reply_text("❌ আপনি ইতিমধ্যে ব্যবহার করেছেন!", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        cursor = await conn.execute("SELECT amount, usages FROM redeem_codes WHERE code = ?", (code,))
        row = await cursor.fetchone()
        if not row or row[1] <= 0:
            await update.message.reply_text("❌ ভুল বা মেয়াদোত্তীর্ণ কোড!", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        amount = row[0]
        await conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await conn.execute("UPDATE redeem_codes SET usages = usages - 1 WHERE code = ?", (code,))
        await conn.execute("INSERT INTO redeem_history (user_id, code) VALUES (?, ?)", (user_id, code))
        await conn.commit()
        await track_transaction(user_id, "redeem", amount, f"Redeemed {code}")
        await update.message.reply_text(f"🎉 **রিডিম সফল!**\n✅ +{amount} ক্রেডিট", parse_mode="Markdown", reply_markup=get_main_keyboard())
        context.user_data.clear()
        return
    
    if state == 'zip_info':
        parts = message.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ Format: `COUNTRY ZIP`", parse_mode="Markdown")
            return
        result = await get_zip_info(parts[0], parts[1])
        await update.message.reply_text(result, parse_mode="Markdown")
        context.user_data.pop('state', None)
        return
    
    if state == 'movie_info':
        result = await get_movie_info(message)
        await update.message.reply_text(result, parse_mode="Markdown")
        context.user_data.pop('state', None)
        return
    
    # ডিফল্ট
    await update.message.reply_text("❌ **বাটন ব্যবহার করুন!**", parse_mode="Markdown")

# ============================================================
# 🚀 মেইন
# ============================================================

async def main():
    try:
        await init_db()
        
        app = Application.builder().token(BOT_TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("buy_premium", buy_premium))
        app.add_handler(CallbackQueryHandler(check_access_callback, pattern="check_access"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        print("✅ Bot is RUNNING!")
        print(f"📡 SMS API URL: {SMS_API_URL}")
        print(f"🔑 SMS API Key: {'✅' if SMS_API_KEY else '❌'}")
        print(f"📛 Sender ID: {SMS_SENDER_ID or '(none)'}")
        print(f"⚡ Custom SMS Bot Ready!")
        print("=" * 60)
        
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        await asyncio.sleep(5)
        await main()
    finally:
        await close_db()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Stopped!")
    except Exception as e:
        print(f"❌ Fatal: {e}")
        os.execv(sys.executable, [sys.executable] + sys.argv)
