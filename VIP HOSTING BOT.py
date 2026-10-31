import telebot
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
import threading
import re
import sys
import uuid
import atexit
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Flask Keep Alive ---
from flask import Flask

app = Flask('')

# Flask-এর নিজস্ব লগ বন্ধ রাখা
logging.getLogger('werkzeug').setLevel(logging.ERROR)

@app.route('/')
@app.route('/health')
def home():
    return "I'm Marco File Host - Running 24/7!", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def universal_keep_alive_pinger():
    """যেকোনো ক্লাউডে (Render, Koyeb, Railway, VPS) স্লিপ প্রতিরোধক অটো-পিঙ্গার"""
    time.sleep(25)
    while True:
        url = (
            os.environ.get("APP_URL") or 
            os.environ.get("RENDER_EXTERNAL_URL") or 
            os.environ.get("KOYEB_APP_URL") or 
            os.environ.get("RAILWAY_STATIC_URL")
        )
        if url:
            if not url.startswith("http"):
                url = f"https://{url}"
            try:
                FAST_SESSION.get(f"{url.rstrip('/')}/health", timeout=12)
            except Exception:
                pass
        time.sleep(180)  # প্রতি ৩ মিনিট পর পর পিং পাঠাবে

def keep_alive():
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    p = threading.Thread(target=universal_keep_alive_pinger, daemon=True)
    p.start()
    print("Universal Flask Keep-Alive & Self-Pinger started.")

# --- Configuration ---
TOKEN = '8935662121:AAGLFSxvDX63B8W6rt5vO5CLvWP_YCxCXiM'
OWNER_ID = 7490648792
ADMIN_ID = 8119339502
YOUR_USERNAME = '@Mahim_Vai_69'
UPDATE_CHANNEL = '@Mahim_Official_Channel_69'
UPDATE_CHANNEL_CHAT = '@Mahim_Like_Official'

DATA_STORAGE_DIR = os.environ.get("DATA_DIR", os.path.abspath(os.path.dirname(__file__)))
BASE_DIR = DATA_STORAGE_DIR
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')
RESTART_FLAG_FILE = os.path.join(IROTECH_DIR, 'restart_flag.json')

FREE_USER_LIMIT = 3
SUBSCRIBED_USER_LIMIT = 15
ADMIN_LIMIT = 99999
OWNER_LIMIT = float('inf')

os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

# 🚀 হাই-স্পিড মাল্টিথ্রেডিং (৩০ থ্রেড) যাতে কোনো মেসেজ আটকে না থাকে
bot = telebot.TeleBot(TOKEN, parse_mode=None, threaded=True, num_threads=30)

# 🚀 আল্ট্রা-ফাস্ট কানেকশন পুলিং (টেলিগ্রামের সাথে কানেকশন ওপেন রেখে ইনস্ট্যান্ট রেসপন্স দেয়)
FAST_SESSION = requests.Session()
adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=Retry(total=2, backoff_factor=0.1))
FAST_SESSION.mount('https://', adapter)

# --- Data ---
bot_scripts = {}
user_subscriptions = {}
user_files = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
bot_locked = False
pending_approvals = {}
users_meta = {}
channel_membership_cache = {}  # { (chat_id, uid): (is_member, expire_timestamp) }

# --- Logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Premium Emojis ---
PEM = {
    "ok": '<tg-emoji emoji-id="6111726981760423576">✅</tg-emoji>',
    "no": '<tg-emoji emoji-id="6311965254817423602">❌</tg-emoji>',
    "warn": '<tg-emoji emoji-id="6314510813214284503">⚠️</tg-emoji>',
    "admin": '<tg-emoji emoji-id="5353032893096567467">📊</tg-emoji>',
    "user": '<tg-emoji emoji-id="5352861489541714456">👤</tg-emoji>',
    "money": '<tg-emoji emoji-id="6111799373434197692">💸</tg-emoji>',
    "msg": '<tg-emoji emoji-id="5337302974806922068">💬</tg-emoji>',
    "rocket": '<tg-emoji emoji-id="5352597830089347330">🚀</tg-emoji>',
    "pin": '<tg-emoji emoji-id="6111410240807245099">📌</tg-emoji>',
    "hi": '<tg-emoji emoji-id="5353027129250453493">👋</tg-emoji>',
    "add": '<tg-emoji emoji-id="6188038822509418008">➕</tg-emoji>',
    "rem": '<tg-emoji emoji-id="6188343249791358585">➖</tg-emoji>',
    "view": '<tg-emoji emoji-id="6188447235244562676">👀</tg-emoji>',
    "wait": '<tg-emoji emoji-id="6233136657722251031">⏳</tg-emoji>',
    "bell": '<tg-emoji emoji-id="6260082445018731350">🔔</tg-emoji>',
    "crown": '<tg-emoji emoji-id="6183661284467152997">👑</tg-emoji>',
    "gear": '<tg-emoji emoji-id="6260111633616475361">⚙️</tg-emoji>',
    "check": '<tg-emoji emoji-id="6188038822509418008">✅</tg-emoji>',
    "file": '<tg-emoji emoji-id="5352721946054268944">📁</tg-emoji>',
    "key": '<tg-emoji emoji-id="6233302765582424442">🔑</tg-emoji>',
    "join": '<tg-emoji emoji-id="5352597830089347330">➡️</tg-emoji>',
    "trash": '<tg-emoji emoji-id="6311965254817423602">🗑️</tg-emoji>'
}

MAIN_MENU_BUTTONS = [
    "📢 Updates Channel", "📤 Upload File", "📂 Check Files",
    "⚡ Bot Speed", "📞 Contact Owner", "📊 Statistics",
    "💳 Subscriptions", "📢 Broadcast", "🔒 Lock Bot",
    "🟢 Running All Code", "👑 Admin Panel", "🟢 Run All",
    "➕ ADD CHANNEL", "➖ REMOVE CHANNEL", "✅ Joined - Check", "🔙 Back",
    "👥 User Bots & Files", "🗑️ Clear All Data"
]

def raw_send(chat_id, text, reply_keyboard=None, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    if reply_keyboard:
        payload["reply_markup"] = {
            "keyboard": reply_keyboard,
            "resize_keyboard": True
        }
    try:
        r = FAST_SESSION.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json=payload, timeout=8)
        return r.json()
    except Exception as e:
        logger.error(f"raw_send err: {e}")
        return {}

def rbtn(text, emoji_id=None, style=None):
    b = {"text": text}
    if emoji_id: b["icon_custom_emoji_id"] = emoji_id
    if style: b["style"] = style
    return b

def get_main_kb(user_id):
    if user_id in admin_ids:
        return [
            [rbtn("📢 Updates Channel", "5352597830089347330", "primary")],
            [rbtn("📤 Upload File", "5352721946054268944", "primary"),
             rbtn("📂 Check Files", "6188447235244562676", "primary")],
            [rbtn("⚡ Bot Speed", "6186175669991379791", "primary"),
             rbtn("📊 Statistics", "5353032893096567467", "success")],
            [rbtn("💳 Subscriptions", "6111799373434197692", "primary"),
             rbtn("📢 Broadcast", "5337302974806922068", "success")],
            [rbtn("🔒 Lock Bot", "6311965254817423602", "danger"),
             rbtn("🟢 Running All Code", "5352597830089347330", "success")],
            [rbtn("👑 Admin Panel", "6183661284467152997", "primary"),
             rbtn("📞 Contact Owner", "5337302974806922068", "primary")],
            [rbtn("👥 User Bots & Files", "5352861489541714456", "primary")]
        ]
    else:
        return [
            [rbtn("📢 Updates Channel", "5352597830089347330", "primary")],
            [rbtn("📤 Upload File", "5352721946054268944", "primary"),
             rbtn("📂 Check Files", "6188447235244562676", "primary")],
            [rbtn("⚡ Bot Speed", "6186175669991379791", "primary"),
             rbtn("📊 Statistics", "5353032893096567467", "success")],
            [rbtn("📞 Contact Owner", "5337302974806922068", "primary")]
        ]

def get_admin_panel_kb():
    return [
        [rbtn("👥 User Bots & Files", "5352861489541714456", "primary")],
        [rbtn("➕ ADD CHANNEL", "6188038822509418008", "success"), rbtn("➖ REMOVE CHANNEL", "6188343249791358585", "danger")],
        [rbtn("🗑️ Clear All Data", "6311965254817423602", "danger")],
        [rbtn("🔙 Back", "6109360506319935223", "primary")]
    ]

# --- Database & Storage (Speed Optimized SQLite) ---
DB_LOCK = threading.Lock()

def get_db():
    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-64000;")
    return conn

def init_db():
    try:
        with DB_LOCK:
            conn = get_db()
            c = conn.cursor()
            c.execute('CREATE TABLE IF NOT EXISTS subscriptions (user_id INTEGER PRIMARY KEY, expiry TEXT)')
            c.execute('''CREATE TABLE IF NOT EXISTS user_files (
                            user_id INTEGER, 
                            file_name TEXT, 
                            file_type TEXT, 
                            file_content BLOB,
                            is_running INTEGER DEFAULT 0,
                            is_zip INTEGER DEFAULT 0,
                            PRIMARY KEY (user_id, file_name))''')
            c.execute('CREATE TABLE IF NOT EXISTS active_users (user_id INTEGER PRIMARY KEY)')
            c.execute('CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)')
            c.execute('CREATE TABLE IF NOT EXISTS force_channels (chat_id TEXT PRIMARY KEY, title TEXT, invite_link TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS users_meta (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT)')
            
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
            c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (OWNER_ID,))
            if ADMIN_ID != OWNER_ID:
                c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
                c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (ADMIN_ID,))
            conn.commit()
            conn.close()
            logger.info("DB Initialized.")
    except Exception as e:
        logger.error(f"DB err: {e}")

def restore_files_and_auto_run():
    """রিস্টার্টের পর ডাটাবেস থেকে সব কোড ফাইল রিস্টোর এবং পূর্বের রানিং কোড অটো চালু করে"""
    try:
        with DB_LOCK:
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT user_id, file_name, file_type, file_content, is_running, is_zip FROM user_files')
            rows = c.fetchall()
            conn.close()

        to_restart = []
        for uid, fn, ft, content, is_run, is_zip in rows:
            folder = get_user_folder(uid)
            fp = os.path.join(folder, fn)
            if content and not os.path.exists(fp):
                if is_zip:
                    tdir = tempfile.mkdtemp(prefix=f"restore_{uid}_")
                    zp = os.path.join(tdir, "temp.zip")
                    with open(zp, 'wb') as f: f.write(content)
                    with zipfile.ZipFile(zp, 'r') as z: z.extractall(folder)
                    shutil.rmtree(tdir, ignore_errors=True)
                else:
                    with open(fp, 'wb') as f: f.write(content)
            user_files.setdefault(uid, []).append((fn, ft))
            if is_run == 1:
                to_restart.append((fp, uid, folder, fn, ft))

        logger.info("Files checked & restored from database.")
        
        if to_restart:
            def auto_runner():
                time.sleep(2)
                for fp, uid, folder, fn, ft in to_restart:
                    if os.path.exists(fp) and not is_bot_running(uid, fn):
                        try:
                            if ft == 'py':
                                threading.Thread(target=run_script, args=(fp, uid, folder, fn, None), daemon=True).start()
                            elif ft == 'js':
                                threading.Thread(target=run_js_script, args=(fp, uid, folder, fn, None), daemon=True).start()
                            time.sleep(1.0)
                        except Exception as ex:
                            logger.error(f"Auto-resume error for {fn}: {ex}")
            threading.Thread(target=auto_runner, daemon=True).start()
    except Exception as e:
        logger.error(f"Restore files err: {e}")

def load_data():
    try:
        with DB_LOCK:
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT user_id, expiry FROM subscriptions')
            for u, e in c.fetchall():
                try: user_subscriptions[u] = {'expiry': datetime.fromisoformat(e)}
                except: pass
            c.execute('SELECT user_id FROM active_users')
            active_users.update(x for (x,) in c.fetchall())
            c.execute('SELECT user_id FROM admins')
            admin_ids.update(x for (x,) in c.fetchall())
            c.execute('SELECT user_id, username, first_name FROM users_meta')
            for uid, un, fn in c.fetchall():
                users_meta[uid] = {'username': un, 'first_name': fn}
            conn.close()

        active_users.add(OWNER_ID)
        active_users.add(ADMIN_ID)
        restore_files_and_auto_run()
        logger.info(f"Loaded: {len(active_users)} active users")
    except Exception as e:
        logger.error(f"Load err: {e}")

init_db()
load_data()

# 🚀 নন-ব্লকিং ইউজার মেটাডাটা ও অ্যাক্টিভিটি ক্যাশ (বাটন ক্লিকে কোনো ডিস্ক লক বা ল্যাগ হবে না)
def register_user_activity(uid, username=None, first_name=None):
    if uid not in active_users:
        active_users.add(uid)
        def _bg_add():
            with DB_LOCK:
                try:
                    conn = get_db()
                    conn.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (uid,))
                    conn.commit()
                    conn.close()
                except Exception as e: logger.error(f"register_user_activity err: {e}")
        threading.Thread(target=_bg_add, daemon=True).start()
        
    cur = users_meta.get(uid)
    if not cur or cur.get('username') != username or cur.get('first_name') != first_name:
        users_meta[uid] = {'username': username, 'first_name': first_name}
        def _bg_meta():
            with DB_LOCK:
                try:
                    conn = get_db()
                    c = conn.cursor()
                    c.execute('INSERT OR REPLACE INTO users_meta (user_id, username, first_name) VALUES (?, ?, ?)',
                              (uid, username or '', first_name or ''))
                    conn.commit()
                    conn.close()
                except Exception as e: logger.error(f"save_user_meta err: {e}")
        threading.Thread(target=_bg_meta, daemon=True).start()

def save_user_meta(uid, username, first_name):
    users_meta[uid] = {'username': username, 'first_name': first_name}
    def _bg():
        with DB_LOCK:
            try:
                conn = get_db()
                c = conn.cursor()
                c.execute('INSERT OR REPLACE INTO users_meta (user_id, username, first_name) VALUES (?, ?, ?)',
                          (uid, username or '', first_name or ''))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"save_user_meta err: {e}")
    threading.Thread(target=_bg, daemon=True).start()

def get_user_display_name(uid):
    meta = users_meta.get(uid)
    if meta and meta.get('username'):
        return f"@{meta['username']}"
    return f"User_{uid}"

def get_user_folder(uid):
    f = os.path.join(UPLOAD_BOTS_DIR, str(uid))
    os.makedirs(f, exist_ok=True)
    return f

# --- নতুন ফাংশন: অটো-এপ্রুভাল চেকার (Owner, Admin এবং Subscribed Users) ---
def is_auto_approve_user(uid):
    if uid == OWNER_ID or uid in admin_ids:
        return True
    if uid in user_subscriptions and user_subscriptions[uid].get('expiry', datetime.min) > datetime.now():
        return True
    return False

def get_user_file_limit(uid):
    if uid == OWNER_ID: return OWNER_LIMIT
    if uid in admin_ids: return ADMIN_LIMIT
    if uid in user_subscriptions and user_subscriptions[uid]['expiry'] > datetime.now():
        return SUBSCRIBED_USER_LIMIT
    return FREE_USER_LIMIT

def get_user_file_count(uid):
    return len(user_files.get(uid, []))

def update_file_running_state(uid, fn, is_running):
    def _bg():
        with DB_LOCK:
            try:
                conn = get_db()
                conn.execute('UPDATE user_files SET is_running = ? WHERE user_id = ? AND file_name = ?',
                             (1 if is_running else 0, uid, fn))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"update_file_running_state err: {e}")
    threading.Thread(target=_bg, daemon=True).start()

def is_bot_running(owner, fn):
    key = f"{owner}_{fn}"
    info = bot_scripts.get(key)
    if info and info.get('process'):
        try:
            p = psutil.Process(info['process'].pid)
            r = p.is_running() and p.status() != psutil.STATUS_ZOMBIE
            if not r:
                cleanup_process_record(owner, fn, key, info)
            return r
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            cleanup_process_record(owner, fn, key, info)
            return False
        except: return False
    return False

def cleanup_process_record(owner, fn, key, info):
    if 'log_file' in info and hasattr(info['log_file'], 'close') and not info['log_file'].closed:
        try: info['log_file'].close()
        except: pass
    bot_scripts.pop(key, None)
    update_file_running_state(owner, fn, False)

def kill_process_tree(info):
    try:
        if 'log_file' in info and hasattr(info['log_file'], 'close') and not info['log_file'].closed:
            try: info['log_file'].close()
            except: pass
        p = info.get('process')
        if p and hasattr(p, 'pid'):
            pid = p.pid
            if pid:
                try:
                    parent = psutil.Process(pid)
                    children = parent.children(recursive=True)
                    for ch in children:
                        try: ch.terminate()
                        except:
                            try: ch.kill()
                            except: pass
                    gone, alive = psutil.wait_procs(children, timeout=1)
                    for x in alive:
                        try: x.kill()
                        except: pass
                    try:
                        parent.terminate()
                        try: parent.wait(timeout=1)
                        except psutil.TimeoutExpired: parent.kill()
                    except psutil.NoSuchProcess: pass
                    except:
                        try: parent.kill()
                        except: pass
                except psutil.NoSuchProcess: pass
    except Exception as e:
        logger.error(f"kill err: {e}")

# --- Safe Log Collector ---
def pipe_stream_safe(process, lf, log_path):
    max_bytes = 2 * 1024 * 1024  # 2MB Limit
    try:
        for line in iter(process.stdout.readline, ''):
            if not line: break
            lf.write(line)
            lf.flush()
            if os.path.exists(log_path) and os.path.getsize(log_path) > max_bytes:
                lf.close()
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                with open(log_path, 'w', encoding='utf-8', errors='ignore') as f:
                    f.writelines(lines[-500:])  # শেষের ৫০০ লাইন রাখবে
                lf = open(log_path, 'a', encoding='utf-8', errors='ignore')
    except Exception:
        pass
    finally:
        try: lf.close()
        except: pass

# --- Auto Install ---
TELEGRAM_MODULES = {
    'telebot': 'pyTelegramBotAPI', 'telegram': 'python-telegram-bot',
    'aiogram': 'aiogram', 'pyrogram': 'pyrogram', 'telethon': 'telethon',
    'requests': 'requests', 'bs4': 'beautifulsoup4', 'pillow': 'Pillow',
    'cv2': 'opencv-python-headless', 'yaml': 'PyYAML', 'dotenv': 'python-dotenv',
    'pandas': 'pandas', 'numpy': 'numpy', 'flask': 'Flask',
    'psutil': 'psutil', 'uuid': None, 'asyncio': None, 'json': None,
    'datetime': None, 'os': None, 'sys': None, 're': None, 'time': None,
    'math': None, 'random': None, 'logging': None, 'threading': None,
    'subprocess': None, 'zipfile': None, 'tempfile': None, 'shutil': None,
    'sqlite3': None, 'atexit': None
}

def attempt_install_pip(mod, msg):
    pkg = TELEGRAM_MODULES.get(mod.lower(), mod)
    if pkg is None: return False
    try:
        if msg: bot.reply_to(msg, f"🐍 Installing `{pkg}`...", parse_mode='Markdown')
        r = subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', pkg],
                           capture_output=True, text=True, check=False,
                           encoding='utf-8', errors='ignore', timeout=120)
        if r.returncode == 0:
            if msg: bot.reply_to(msg, f"{PEM['ok']} Installed `{pkg}`.", parse_mode='HTML')
            return True
        else:
            err = f"{PEM['no']} Failed.\n<pre>{r.stderr or r.stdout}</pre>"
            if len(err) > 4000: err = err[:4000] + "\n..."
            if msg: bot.reply_to(msg, err, parse_mode='HTML')
            return False
    except Exception as e:
        if msg: bot.reply_to(msg, f"{PEM['no']} Error: {e}", parse_mode='HTML')
        return False

def attempt_install_npm(mod, folder, msg):
    try:
        if msg: bot.reply_to(msg, f"🟠 Installing npm `{mod}`...")
        r = subprocess.run(['npm', 'install', '--no-audit', '--no-fund', mod], capture_output=True, text=True,
                           check=False, cwd=folder, encoding='utf-8', errors='ignore', timeout=120)
        if r.returncode == 0:
            if msg: bot.reply_to(msg, f"{PEM['ok']} npm `{mod}` installed.", parse_mode='HTML')
            return True
        else:
            err = f"{PEM['no']} npm failed.\n<pre>{r.stderr or r.stdout}</pre>"
            if len(err) > 4000: err = err[:4000] + "\n..."
            if msg: bot.reply_to(msg, err, parse_mode='HTML')
            return False
    except FileNotFoundError:
        if msg: bot.reply_to(msg, f"{PEM['no']} 'npm' not found.", parse_mode='HTML')
        return False
    except Exception as e:
        if msg: bot.reply_to(msg, f"{PEM['no']} Error: {e}", parse_mode='HTML')
        return False

# --- Run Scripts ---
def run_script(path, owner, folder, fn, msg_obj=None, attempt=1):
    max_attempts = 2
    if attempt > max_attempts:
        if msg_obj: bot.reply_to(msg_obj, f"{PEM['no']} Failed after {max_attempts} attempts.", parse_mode='HTML')
        return
    key = f"{owner}_{fn}"
    try:
        if not os.path.exists(path):
            if msg_obj: bot.reply_to(msg_obj, f"{PEM['no']} Script not found.", parse_mode='HTML')
            if owner in user_files:
                user_files[owner] = [f for f in user_files.get(owner, []) if f[0] != fn]
            remove_user_file_db(owner, fn)
            return
        if attempt == 1:
            cp = None
            try:
                cp = subprocess.Popen([sys.executable, path], cwd=folder,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, encoding='utf-8', errors='ignore')
                out, err = cp.communicate(timeout=4)
                rc = cp.returncode
                if rc != 0 and err:
                    m = re.search(r"ModuleNotFoundError: No module named '(.+?)'", err)
                    if m:
                        mod = m.group(1).strip().strip("'\"")
                        if attempt_install_pip(mod, msg_obj):
                            if msg_obj: bot.reply_to(msg_obj, f"{PEM['wait']} Retrying...", parse_mode='HTML')
                            time.sleep(1.5)
                            threading.Thread(target=run_script, args=(path, owner, folder, fn, msg_obj, attempt+1), daemon=True).start()
                            return
                        return
                    else:
                        if msg_obj: bot.reply_to(msg_obj, f"{PEM['no']} Error:\n<pre>{err[:500]}</pre>", parse_mode='HTML')
                        return
            except subprocess.TimeoutExpired:
                if cp and cp.poll() is None: cp.kill(); cp.communicate()
            except FileNotFoundError:
                if msg_obj: bot.reply_to(msg_obj, f"{PEM['no']} Python not found.", parse_mode='HTML')
                return
            except Exception as e:
                if msg_obj: bot.reply_to(msg_obj, f"{PEM['no']} Error: {e}", parse_mode='HTML')
                return
            finally:
                if cp and cp.poll() is None: cp.kill(); cp.communicate()
        
        log_path = os.path.join(folder, f"{os.path.splitext(fn)[0]}.log")
        lf = open(log_path, 'w', encoding='utf-8', errors='ignore')
        
        si = None; cf = 0
        if os.name == 'nt':
            si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE

        pr = subprocess.Popen([sys.executable, path], cwd=folder,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                              startupinfo=si, creationflags=cf,
                              encoding='utf-8', errors='ignore', text=True, bufsize=1)
        
        threading.Thread(target=pipe_stream_safe, args=(pr, lf, log_path), daemon=True).start()

        bot_scripts[key] = {
            'process': pr, 'log_file': lf, 'file_name': fn,
            'chat_id': getattr(msg_obj, 'chat', type('', (), {'id': owner})).id if msg_obj else owner,
            'script_owner_id': owner,
            'start_time': datetime.now(), 'user_folder': folder,
            'type': 'py', 'script_key': key
        }
        update_file_running_state(owner, fn, True)
        if msg_obj: bot.reply_to(msg_obj, f"{PEM['ok']} Python script '{fn}' started! (PID: {pr.pid})", parse_mode='HTML')
    except Exception as e:
        if msg_obj: bot.reply_to(msg_obj, f"{PEM['no']} Error: {e}", parse_mode='HTML')
        if key in bot_scripts:
            kill_process_tree(bot_scripts[key]); del bot_scripts[key]
        update_file_running_state(owner, fn, False)

def run_js_script(path, owner, folder, fn, msg_obj=None, attempt=1):
    max_attempts = 2
    if attempt > max_attempts:
        if msg_obj: bot.reply_to(msg_obj, f"{PEM['no']} Failed after {max_attempts} attempts.", parse_mode='HTML')
        return
    key = f"{owner}_{fn}"
    try:
        if not os.path.exists(path):
            if msg_obj: bot.reply_to(msg_obj, f"{PEM['no']} Script not found.", parse_mode='HTML')
            if owner in user_files:
                user_files[owner] = [f for f in user_files.get(owner, []) if f[0] != fn]
            remove_user_file_db(owner, fn)
            return
        if attempt == 1:
            cp = None
            try:
                cp = subprocess.Popen(['node', path], cwd=folder,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, encoding='utf-8', errors='ignore')
                out, err = cp.communicate(timeout=4)
                rc = cp.returncode
                if rc != 0 and err:
                    m = re.search(r"Cannot find module '(.+?)'", err)
                    if m:
                        mod = m.group(1).strip().strip("'\"")
                        if not mod.startswith('.') and not mod.startswith('/'):
                            if attempt_install_npm(mod, folder, msg_obj):
                                if msg_obj: bot.reply_to(msg_obj, f"{PEM['wait']} Retrying...", parse_mode='HTML')
                                time.sleep(1.5)
                                threading.Thread(target=run_js_script, args=(path, owner, folder, fn, msg_obj, attempt+1), daemon=True).start()
                                return
                            return
                    if msg_obj: bot.reply_to(msg_obj, f"{PEM['no']} Error:\n<pre>{err[:500]}</pre>", parse_mode='HTML')
                    return
            except subprocess.TimeoutExpired:
                if cp and cp.poll() is None: cp.kill(); cp.communicate()
            except FileNotFoundError:
                if msg_obj: bot.reply_to(msg_obj, f"{PEM['no']} 'node' not found.", parse_mode='HTML')
                return
            except Exception as e:
                if msg_obj: bot.reply_to(msg_obj, f"{PEM['no']} Error: {e}", parse_mode='HTML')
                return
            finally:
                if cp and cp.poll() is None: cp.kill(); cp.communicate()
        
        log_path = os.path.join(folder, f"{os.path.splitext(fn)[0]}.log")
        lf = open(log_path, 'w', encoding='utf-8', errors='ignore')
        
        si = None; cf = 0
        if os.name == 'nt':
            si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE

        pr = subprocess.Popen(['node', path], cwd=folder,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                              startupinfo=si, creationflags=cf,
                              encoding='utf-8', errors='ignore', text=True, bufsize=1)
        
        threading.Thread(target=pipe_stream_safe, args=(pr, lf, log_path), daemon=True).start()

        bot_scripts[key] = {
            'process': pr, 'log_file': lf, 'file_name': fn,
            'chat_id': getattr(msg_obj, 'chat', type('', (), {'id': owner})).id if msg_obj else owner,
            'script_owner_id': owner,
            'start_time': datetime.now(), 'user_folder': folder,
            'type': 'js', 'script_key': key
        }
        update_file_running_state(owner, fn, True)
        if msg_obj: bot.reply_to(msg_obj, f"{PEM['ok']} JS script '{fn}' started! (PID: {pr.pid})", parse_mode='HTML')
    except Exception as e:
        if msg_obj: bot.reply_to(msg_obj, f"{PEM['no']} Error: {e}", parse_mode='HTML')
        if key in bot_scripts:
            kill_process_tree(bot_scripts[key]); del bot_scripts[key]
        update_file_running_state(owner, fn, False)

def save_user_file(uid, fn, ft='py', file_content=None, is_zip=False):
    with DB_LOCK:
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('''INSERT OR REPLACE INTO user_files 
                         (user_id, file_name, file_type, file_content, is_running, is_zip) 
                         VALUES (?, ?, ?, ?, ?, ?)''', 
                         (uid, fn, ft, file_content, 0, 1 if is_zip else 0))
            conn.commit()
            conn.close()
            if uid not in user_files: user_files[uid] = []
            user_files[uid] = [(n, t) for n, t in user_files[uid] if n != fn]
            user_files[uid].append((fn, ft))
        except Exception as e: logger.error(f"save_user_file: {e}")

def remove_user_file_db(uid, fn):
    with DB_LOCK:
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (uid, fn))
            conn.commit()
            conn.close()
            if uid in user_files:
                user_files[uid] = [f for f in user_files[uid] if f[0] != fn]
                if not user_files[uid]: del user_files[uid]
        except Exception as e: logger.error(f"remove_user_file: {e}")

def save_subscription(uid, exp):
    with DB_LOCK:
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO subscriptions (user_id, expiry) VALUES (?, ?)', (uid, exp.isoformat()))
            conn.commit()
            conn.close()
            user_subscriptions[uid] = {'expiry': exp}
        except Exception as e: logger.error(f"save_sub: {e}")

def remove_subscription_db(uid):
    with DB_LOCK:
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('DELETE FROM subscriptions WHERE user_id = ?', (uid,))
            conn.commit()
            conn.close()
            user_subscriptions.pop(uid, None)
        except Exception as e: logger.error(f"remove_sub: {e}")

def add_admin_db(uid):
    with DB_LOCK:
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (uid,))
            conn.commit()
            conn.close()
            admin_ids.add(uid)
        except Exception as e: logger.error(f"add_admin: {e}")

def remove_admin_db(uid):
    if uid == OWNER_ID: return False
    with DB_LOCK:
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('DELETE FROM admins WHERE user_id = ?', (uid,))
            conn.commit()
            removed = c.rowcount > 0
            conn.close()
            if removed: admin_ids.discard(uid)
            return removed
        except Exception as e: logger.error(f"remove_admin: {e}"); return False

# --- Force Join Channels (স্মার্ট ক্যাশসহ) ---
def get_force_channels():
    with DB_LOCK:
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT chat_id, title, invite_link FROM force_channels ORDER BY title')
            res = c.fetchall()
            conn.close()
            return res
        except: return []

def add_force_channel_db(chat_id, title, invite_link):
    with DB_LOCK:
        try:
            conn = get_db()
            conn.execute('INSERT OR REPLACE INTO force_channels (chat_id, title, invite_link) VALUES (?, ?, ?)',
                         (str(chat_id), title, invite_link))
            conn.commit()
            conn.close()
        except Exception: pass

def remove_force_channel_db(chat_id):
    with DB_LOCK:
        try:
            conn = get_db()
            cur = conn.execute('DELETE FROM force_channels WHERE chat_id = ?', (str(chat_id),))
            conn.commit()
            res = cur.rowcount > 0
            conn.close()
            return res
        except Exception: return False

def user_joined_required_channels(uid):
    if uid in admin_ids: return True
    now = time.time()
    for chat_id, _, _ in get_force_channels():
        cached = channel_membership_cache.get((chat_id, uid))
        if cached and cached[1] > now:
            if not cached[0]: return False
            continue
        try:
            member = bot.get_chat_member(chat_id, uid)
            is_mem = member.status in ('member', 'administrator', 'creator')
            channel_membership_cache[(chat_id, uid)] = (is_mem, now + 60)
            if not is_mem: return False
        except Exception:
            return False
    return True

def send_force_join_prompt(chat_id, uid):
    channels = get_force_channels()
    if not channels: return False
    kb = []
    for _, title, link in channels:
        kb.append([rbtn(f"📢 Join {title}", "5352597830089347330", "primary")])
    kb.append([rbtn("✅ Joined - Check", "6111726981760423576", "success")])
    links = "\n".join(f"• <a href=\"{link}\">{title}</a>" for _, title, link in channels)
    raw_send(chat_id, f"{PEM['warn']} <b>Bot use করতে আগে নিচের channel/group-এ join করুন:</b>\n\n{links}\n\nJoin করার পর <b>✅ Joined - Check</b> চাপুন।", reply_keyboard=kb)
    return True

def process_add_channel(m):
    uid = m.from_user.id
    if uid not in admin_ids: return
    if m.text and (m.text.lower() == '/cancel' or m.text in MAIN_MENU_BUTTONS):
        raw_send(m.chat.id, "Cancelled.", reply_keyboard=get_main_kb(uid)); return
    value = (m.text or '').strip()
    try:
        if value.startswith('https://t.me/'):
            username = '@' + value.rstrip('/').split('/')[-1]
        elif value.startswith('@'):
            username = value
        else:
            username = value
        chat = bot.get_chat(username)
        chat_id = str(chat.id)
        title = getattr(chat, 'title', None) or getattr(chat, 'username', None) or chat_id
        link = getattr(chat, 'invite_link', None)
        if not link:
            un = getattr(chat, 'username', None)
            if un: link = f"https://t.me/{un}"
            else:
                try: link = bot.export_chat_invite_link(chat.id)
                except: link = None
        if not link:
            raw_send(m.chat.id, f"{PEM['no']} Invite link পাওয়া যায়নি। Bot-কে admin করে আবার try করুন.", reply_keyboard=get_main_kb(uid)); return
        me = bot.get_me()
        bot.get_chat_member(chat.id, me.id)
        add_force_channel_db(chat_id, title, link)
        raw_send(m.chat.id, f"{PEM['ok']} Added: <b>{title}</b>\n<code>{chat_id}</code>", reply_keyboard=get_admin_panel_kb())
    except Exception as e:
        raw_send(m.chat.id, f"{PEM['no']} Channel add failed:\n<code>{str(e)[:400]}</code>", reply_keyboard=get_admin_panel_kb())

def host_request_text(status, aid, ap):
    username = ap.get("username")
    uname = f"@{username}" if username else "N/A"
    created = datetime.fromtimestamp(ap.get("timestamp", time.time())).strftime("%Y-%m-%d %H:%M:%S")
    filename = ap.get("file_name", "Unknown")
    user_id = ap.get("user_id", "N/A")
    if status == "pending":
        heading = "⚡ NEW BOT HOSTING REQUEST"
        status_line = "STATUS: PENDING 🎯"
    elif status == "approved":
        heading = "🎉 NEW BOT SUCCESSFULLY HOSTED ✅"
        status_line = "STATUS: SUCCESSFUL ✅"
    else:
        heading = "🚫 NEW BOT REQUEST CANCELED ❌"
        status_line = "STATUS: CANCELED ❌"
    return (
        f"{heading}\n\n"
        f"🤖 FILE INFORMATION\n\n"
        f"NAME: {filename}\n"
        f"ORDER ID: {aid}\n"
        f"TIME: {created}\n\n"
        f"👤 CLIENT INFO\n\n"
        f"Username: {uname}\n"
        f"ID: {user_id}\n\n"
        f"{status_line}\n\n"
        f"BOT = @asfreehosting_bot"
    )

def publish_pending_host_request(aid, ap):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ APPROVE", callback_data=f"hostapprove:{aid}"),
        types.InlineKeyboardButton("❌ CANCEL", callback_data=f"hostcancel:{aid}")
    )
    try:
        sent = bot.send_message(
            UPDATE_CHANNEL_CHAT, host_request_text("pending", aid, ap),
            reply_markup=markup, disable_web_page_preview=True
        )
        ap["channel_chat_id"] = sent.chat.id
        ap["channel_message_id"] = sent.message_id
    except Exception as e:
        logger.error(f"pending update-channel notice failed: {e}")

def publish_auto_approved_notice(aid, ap):
    try:
        bot.send_message(
            UPDATE_CHANNEL_CHAT, host_request_text("approved", aid, ap),
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"auto approve update-channel notice failed: {e}")

def update_host_request_post(aid, ap, status):
    chat_id = ap.get("channel_chat_id", UPDATE_CHANNEL_CHAT)
    message_id = ap.get("channel_message_id")
    if not message_id: return
    try:
        bot.edit_message_text(
            host_request_text(status, aid, ap), chat_id, message_id,
            reply_markup=None, disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"update channel status edit failed: {e}")

def notify_admin_new_file(aid, uid, uname, fname, fn, ft, is_zip=False):
    txt = (
        f"{PEM['bell']} <b>New File Upload — Approval Needed!</b>\n\n"
        f"{PEM['user']} Name: <b>{fname}</b>\n"
        f"{PEM['user']} Username: @{uname or 'N/A'}\n"
        f"{PEM['user']} User ID: <code>{uid}</code>\n\n"
        f"{PEM['file']} File: <code>{fn}</code>\n"
        f"{PEM['gear']} Type: <b>{ft.upper()}</b>"
        + (f"\n📦 (ZIP Archive)" if is_zip else "") +
        f"\n\n{PEM['pin']} Approval ID: <code>{aid}</code>\n\n"
        f"👉 নিচের বাটনে ক্লিক করুন অথবা লিখে পাঠান:\n"
        f"<code>approve {aid}</code> বা <code>reject {aid}</code>"
    )
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ APPROVE", callback_data=f"hostapprove:{aid}"),
        types.InlineKeyboardButton("❌ REJECT", callback_data=f"hostcancel:{aid}")
    )
    for admin in set([int(ADMIN_ID)] + list(admin_ids)):
        try:
            bot.send_message(admin, txt, reply_markup=markup, parse_mode='HTML')
        except Exception as e:
            logger.error(f"notify admin {admin}: {e}")

def notify_user_approved(uid, fn, ft):
    try:
        txt = (f"{PEM['ok']} <b>File Approved & Started!</b>\n\n"
               f"{PEM['file']} File: <code>{fn}</code>\n"
               f"{PEM['gear']} Type: {ft.upper()}\n\n"
               f"{PEM['rocket']} Your file is now running 24/7!")
        raw_send(uid, txt, reply_keyboard=get_main_kb(uid))
    except Exception as e: logger.error(f"notify_user_approved: {e}")

def notify_user_rejected(uid, fn, reason=""):
    try:
        txt = (f"{PEM['no']} <b>File Rejected!</b>\n\n"
               f"{PEM['file']} File: <code>{fn}</code>\n\n")
        if reason: txt += f"{PEM['msg']} Reason: {reason}\n\n"
        txt += f"{PEM['wait']} Contact support if needed."
        raw_send(uid, txt, reply_keyboard=get_main_kb(uid))
    except Exception as e: logger.error(f"notify_user_rejected: {e}")

# --- File Handling (Auto Approval Logic Included) ---
def handle_zip(content, zname, message):
    uid = message.from_user.id
    register_user_activity(uid, message.from_user.username, message.from_user.first_name)
    folder = get_user_folder(uid)
    tdir = None
    try:
        tdir = tempfile.mkdtemp(prefix=f"u_{uid}_zip_")
        zp = os.path.join(tdir, zname)
        with open(zp, 'wb') as f: f.write(content)
        with zipfile.ZipFile(zp, 'r') as z:
            for m in z.infolist():
                mp = os.path.abspath(os.path.join(tdir, m.filename))
                if not mp.startswith(os.path.abspath(tdir)):
                    raise zipfile.BadZipFile(f"Unsafe: {m.filename}")
            z.extractall(tdir)
        items = os.listdir(tdir)
        py_f = [f for f in items if f.endswith('.py')]
        js_f = [f for f in items if f.endswith('.js')]
        req = 'requirements.txt' if 'requirements.txt' in items else None
        pkg = 'package.json' if 'package.json' in items else None
        if req:
            rp = os.path.join(tdir, req)
            bot.reply_to(message, f"{PEM['wait']} Installing Python deps...", parse_mode='HTML')
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', '-r', rp],
                               capture_output=True, text=True, check=True,
                               encoding='utf-8', errors='ignore', timeout=120)
                bot.reply_to(message, f"{PEM['ok']} Python deps installed.", parse_mode='HTML')
            except subprocess.CalledProcessError as e:
                err = f"{PEM['no']} Failed.\n<pre>{e.stderr or e.stdout}</pre>"
                if len(err) > 4000: err = err[:4000] + "\n..."
                bot.reply_to(message, err, parse_mode='HTML'); return
        if pkg:
            bot.reply_to(message, f"{PEM['wait']} Installing Node deps...", parse_mode='HTML')
            try:
                subprocess.run(['npm', 'install', '--no-audit', '--no-fund'], capture_output=True, text=True,
                               check=True, cwd=tdir, encoding='utf-8', errors='ignore', timeout=120)
                bot.reply_to(message, f"{PEM['ok']} Node deps installed.", parse_mode='HTML')
            except FileNotFoundError:
                bot.reply_to(message, f"{PEM['no']} 'npm' not found.", parse_mode='HTML'); return
            except subprocess.CalledProcessError as e:
                err = f"{PEM['no']} Failed.\n<pre>{e.stderr or e.stdout}</pre>"
                if len(err) > 4000: err = err[:4000] + "\n..."
                bot.reply_to(message, err, parse_mode='HTML'); return
        main_s = None; ft = None
        for p in ['main.py', 'bot.py', 'app.py']:
            if p in py_f: main_s = p; ft = 'py'; break
        if not main_s:
            for p in ['index.js', 'main.js', 'bot.js', 'app.js']:
                if p in js_f: main_s = p; ft = 'js'; break
        if not main_s:
            if py_f: main_s = py_f[0]; ft = 'py'
            elif js_f: main_s = js_f[0]; ft = 'js'
        if not main_s:
            bot.reply_to(message, f"{PEM['no']} No .py or .js found!", parse_mode='HTML'); return
        for name in os.listdir(tdir):
            src = os.path.join(tdir, name)
            dst = os.path.join(folder, name)
            if os.path.isdir(dst): shutil.rmtree(dst, ignore_errors=True)
            elif os.path.exists(dst): os.remove(dst)
            shutil.move(src, dst)
            
        save_user_file(uid, main_s, ft, file_content=content, is_zip=True)
        aid = str(uuid.uuid4())[:8].upper()

        # ⚡ অটো-এপ্রুভাল চেকিং (Owner, Admin এবং Subscribed Users)
        if is_auto_approve_user(uid):
            ap = {
                'user_id': uid, 'file_name': main_s, 'file_type': ft,
                'file_path': os.path.join(folder, main_s),
                'user_folder': folder, 'is_zip': True, 'main_script': main_s,
                'timestamp': time.time(), 'username': message.from_user.username
            }
            publish_auto_approved_notice(aid, ap)
            fp = os.path.join(folder, main_s)
            if ft == 'py':
                threading.Thread(target=run_script, args=(fp, uid, folder, main_s, message), daemon=True).start()
            elif ft == 'js':
                threading.Thread(target=run_js_script, args=(fp, uid, folder, main_s, message), daemon=True).start()
            notify_user_approved(uid, main_s, ft)
        else:
            pending_approvals[aid] = {
                'user_id': uid, 'file_name': main_s, 'file_type': ft,
                'file_path': os.path.join(folder, main_s),
                'user_folder': folder, 'message_info': message,
                'is_zip': True, 'main_script': main_s, 'timestamp': time.time(),
                'username': message.from_user.username
            }
            publish_pending_host_request(aid, pending_approvals[aid])
            txt = (f"{PEM['ok']} <b>Files extracted & deps installed!</b>\n\n"
                   f"{PEM['wait']} Waiting for <b>Admin Approval</b>.\n"
                   f"{PEM['pin']} Approval ID: <code>{aid}</code>\n\n"
                   f"You will be notified once approved.")
            raw_send(uid, txt, reply_keyboard=get_main_kb(uid))
            notify_admin_new_file(aid, uid, message.from_user.username,
                                  message.from_user.first_name, main_s, ft, is_zip=True)
    except zipfile.BadZipFile as e:
        bot.reply_to(message, f"{PEM['no']} Invalid ZIP: {e}", parse_mode='HTML')
    except Exception as e:
        logger.error(f"zip err: {e}", exc_info=True)
        bot.reply_to(message, f"{PEM['no']} Error: {e}", parse_mode='HTML')
    finally:
        if tdir and os.path.exists(tdir):
            try: shutil.rmtree(tdir)
            except: pass

def handle_js(path, uid, folder, fn, message):
    try:
        register_user_activity(uid, message.from_user.username, message.from_user.first_name)
        with open(path, 'rb') as f: content = f.read()
        save_user_file(uid, fn, 'js', file_content=content, is_zip=False)
        aid = str(uuid.uuid4())[:8].upper()

        if is_auto_approve_user(uid):
            ap = {
                'user_id': uid, 'file_name': fn, 'file_type': 'js',
                'file_path': path, 'user_folder': folder, 'is_zip': False,
                'main_script': fn, 'timestamp': time.time(),
                'username': message.from_user.username
            }
            publish_auto_approved_notice(aid, ap)
            threading.Thread(target=run_js_script, args=(path, uid, folder, fn, message), daemon=True).start()
            notify_user_approved(uid, fn, 'js')
        else:
            pending_approvals[aid] = {
                'user_id': uid, 'file_name': fn, 'file_type': 'js',
                'file_path': path, 'user_folder': folder,
                'message_info': message, 'is_zip': False,
                'main_script': fn, 'timestamp': time.time(),
                'username': message.from_user.username
            }
            publish_pending_host_request(aid, pending_approvals[aid])
            txt = (f"{PEM['ok']} <b>JS file received!</b>\n\n"
                   f"{PEM['wait']} Waiting for <b>Admin Approval</b>.\n"
                   f"{PEM['pin']} Approval ID: <code>{aid}</code>")
            raw_send(uid, txt, reply_keyboard=get_main_kb(uid))
            notify_admin_new_file(aid, uid, message.from_user.username,
                                  message.from_user.first_name, fn, 'js', is_zip=False)
    except Exception as e:
        logger.error(f"js err: {e}", exc_info=True)
        bot.reply_to(message, f"{PEM['no']} Error: {e}", parse_mode='HTML')

def handle_py(path, uid, folder, fn, message):
    try:
        register_user_activity(uid, message.from_user.username, message.from_user.first_name)
        with open(path, 'rb') as f: content = f.read()
        save_user_file(uid, fn, 'py', file_content=content, is_zip=False)
        aid = str(uuid.uuid4())[:8].upper()

        if is_auto_approve_user(uid):
            ap = {
                'user_id': uid, 'file_name': fn, 'file_type': 'py',
                'file_path': path, 'user_folder': folder, 'is_zip': False,
                'main_script': fn, 'timestamp': time.time(),
                'username': message.from_user.username
            }
            publish_auto_approved_notice(aid, ap)
            threading.Thread(target=run_script, args=(path, uid, folder, fn, message), daemon=True).start()
            notify_user_approved(uid, fn, 'py')
        else:
            pending_approvals[aid] = {
                'user_id': uid, 'file_name': fn, 'file_type': 'py',
                'file_path': path, 'user_folder': folder,
                'message_info': message, 'is_zip': False,
                'main_script': fn, 'timestamp': time.time(),
                'username': message.from_user.username
            }
            publish_pending_host_request(aid, pending_approvals[aid])
            txt = (f"{PEM['ok']} <b>Python file received!</b>\n\n"
                   f"{PEM['wait']} Waiting for <b>Admin Approval</b>.\n"
                   f"{PEM['pin']} Approval ID: <code>{aid}</code>")
            raw_send(uid, txt, reply_keyboard=get_main_kb(uid))
            notify_admin_new_file(aid, uid, message.from_user.username,
                                  message.from_user.first_name, fn, 'py', is_zip=False)
    except Exception as e:
        logger.error(f"py err: {e}", exc_info=True)
        bot.reply_to(message, f"{PEM['no']} Error: {e}", parse_mode='HTML')

# --- Welcome ---
def send_welcome(chat_id, user_id, first_name, username):
    global bot_locked
    register_user_activity(user_id, username, first_name)
    if bot_locked and user_id not in admin_ids:
        raw_send(chat_id, f"{PEM['warn']} Bot locked by admin.", reply_keyboard=get_main_kb(user_id))
        return
    if user_id not in admin_ids and not user_joined_required_channels(user_id):
        send_force_join_prompt(chat_id, user_id)
        return
    
    limit = get_user_file_limit(user_id)
    curr = get_user_file_count(user_id)
    lim_str = str(limit) if limit != float('inf') else "Unlimited"
    exp_info = ""
    is_premium = False
    if user_id == OWNER_ID: 
        st = f"{PEM['crown']} Owner"
        is_premium = True
    elif user_id in admin_ids: 
        st = f"{PEM['admin']} Admin"
        is_premium = True
    elif user_id in user_subscriptions:
        e = user_subscriptions[user_id].get('expiry')
        if e and e > datetime.now():
            st = f"{PEM['check']} Premium"; dl = (e - datetime.now()).days
            exp_info = f"\n{PEM['wait']} Expires in {dl} days"
            is_premium = True
        else: 
            st = f"{PEM['user']} Free (Expired)"
            remove_subscription_db(user_id)
    else: 
        st = f"{PEM['user']} Free User"
    
    appr_note = "⚡ <b>Instant Launch Active!</b> (No Approval Needed)" if is_premium else "⚠️ Free users' files need <b>Admin Approval</b>."

    txt = (f"{PEM['hi']} <b>Welcome, {first_name}!</b>\n\n"
           f"{PEM['user']} ID: <code>{user_id}</code>\n"
           f"✳️ Username: @{username or 'Not set'}\n"
           f"🔰 Status: {st}{exp_info}\n"
           f"{PEM['file']} Files: {curr} / {lim_str}\n\n"
           f"{PEM['gear']} Host & run Python (`.py`) or JS (`.js`) scripts.\n"
           f"{PEM['pin']} {appr_note}\n\n"
           f"{PEM['rocket']} Use buttons below.")
    raw_send(chat_id, txt, reply_keyboard=get_main_kb(user_id))

# --- Commands ---
@bot.message_handler(commands=['start', 'help'])
def cmd_start(m):
    try: bot.clear_step_handler_by_chat_id(m.chat.id)
    except: pass
    send_welcome(m.chat.id, m.from_user.id, m.from_user.first_name, m.from_user.username)

@bot.message_handler(commands=['admin'])
def cmd_admin(m):
    try: bot.clear_step_handler_by_chat_id(m.chat.id)
    except: pass
    register_user_activity(m.from_user.id, m.from_user.username, m.from_user.first_name)
    if m.from_user.id in admin_ids:
        raw_send(m.chat.id, f"{PEM['admin']} <b>Admin Panel</b>\n{PEM['pin']} Use buttons below.",
                 reply_keyboard=get_admin_panel_kb())
    else:
        bot.reply_to(m, f"{PEM['no']} Not admin.", parse_mode='HTML')

# --- Decision Handler ---
def decide_host_request(aid, action, actor_id, reply_message=None):
    if actor_id not in admin_ids:
        if reply_message:
            bot.reply_to(reply_message, f"{PEM['no']} Admin only.", parse_mode='HTML')
        return False
    ap = pending_approvals.get(aid)
    if not ap:
        if reply_message:
            bot.reply_to(reply_message, f"{PEM['no']} Request not found or already handled.", parse_mode='HTML')
        return False

    file_uid = ap['user_id']
    fn = ap['file_name']
    ft = ap['file_type']
    fp = ap['file_path']
    folder = ap['user_folder']
    om = ap.get('message_info')

    pending_approvals.pop(aid, None)
    if action == "approve":
        try:
            target = om if om else reply_message
            if ft == 'py':
                threading.Thread(target=run_script, args=(fp, file_uid, folder, fn, target), daemon=True).start()
            elif ft == 'js':
                threading.Thread(target=run_js_script, args=(fp, file_uid, folder, fn, target), daemon=True).start()
            notify_user_approved(file_uid, fn, ft)
            update_host_request_post(aid, ap, "approved")
            if reply_message:
                bot.reply_to(reply_message,
                    f"{PEM['ok']} <b>Approved & Started!</b>\n\n"
                    f"{PEM['user']} User: <code>{file_uid}</code>\n"
                    f"{PEM['file']} File: <code>{fn}</code>",
                    parse_mode='HTML')
            return True
        except Exception as e:
            logger.error(f"approve err: {e}", exc_info=True)
            if reply_message:
                bot.reply_to(reply_message, f"{PEM['no']} Error: {e}", parse_mode='HTML')
            return False

    try:
        if os.path.exists(fp):
            os.remove(fp)
        remove_user_file_db(file_uid, fn)
    except Exception as e:
        logger.error(f"reject del: {e}")
    notify_user_rejected(file_uid, fn, reason="Admin canceled the hosting request.")
    update_host_request_post(aid, ap, "canceled")
    if reply_message:
        bot.reply_to(reply_message,
            f"{PEM['no']} <b>Canceled & Deleted!</b>\n\n"
            f"{PEM['user']} User: <code>{file_uid}</code>\n"
            f"{PEM['file']} File: <code>{fn}</code>",
            parse_mode='HTML')
    return True

@bot.message_handler(func=lambda m: m.text and (m.text.lower().startswith("approve ") or m.text.lower().startswith("reject ")))
def handle_approval_text(m):
    register_user_activity(m.from_user.id, m.from_user.username, m.from_user.first_name)
    uid = m.from_user.id
    if uid not in admin_ids:
        bot.reply_to(m, f"{PEM['no']} Admin only.", parse_mode='HTML')
        return
    parts = m.text.strip().split()
    if len(parts) != 2:
        bot.reply_to(m, f"{PEM['warn']} Use: <code>approve ABCD1234</code> or <code>reject ABCD1234</code>", parse_mode='HTML')
        return
    action = "approve" if parts[0].lower() == "approve" else "cancel"
    decide_host_request(parts[1].upper(), action, uid, m)

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith(("hostapprove:", "hostcancel:")))
def handle_host_request_callback(call):
    uid = call.from_user.id
    if uid not in admin_ids:
        bot.answer_callback_query(call.id, "Only admins can do this.", show_alert=True)
        return
    prefix, aid = call.data.split(":", 1)
    action = "approve" if prefix == "hostapprove" else "cancel"
    ok = decide_host_request(aid.upper(), action, uid)
    try:
        new_text = "✅ Approved by admin" if action == "approve" else "❌ Rejected by admin"
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.send_message(call.message.chat.id, f"{call.message.text}\n\n<b>Status:</b> {new_text}", parse_mode='HTML')
    except Exception:
        pass
    try:
        bot.answer_callback_query(call.id, "Done!" if ok else "Already processed.")
    except Exception:
        pass

# --- Clear All Data Callback Handler (Double Confirmation) ---
@bot.callback_query_handler(func=lambda call: call.data in ["req_clear_all", "confirm_clear_all_final", "cancel_clear_all"])
def handle_clear_all_flow(call):
    uid = call.from_user.id
    if uid not in admin_ids:
        bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
        return

    if call.data == "cancel_clear_all":
        try:
            bot.edit_message_text("❌ অপারেশন বাতিল করা হয়েছে। কোনো ডাটা ডিলিট হয়নি।", 
                                  call.message.chat.id, call.message.message_id)
        except: pass
        return

    if call.data == "req_clear_all":
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("💥 হ্যাঁ, স্থায়ীভাবে সব মুছে ফেলুন", callback_data="confirm_clear_all_final"),
            types.InlineKeyboardButton("❌ বাতিল", callback_data="cancel_clear_all")
        )
        try:
            bot.edit_message_text(
                f"{PEM['warn']} <b>চূড়ান্ত সতর্কতা (Final Confirmation)!</b>\n\n"
                f"আপনি কি শতভাগ নিশ্চিত? এটি কার্যকর হলে:\n"
                f"• সমস্ত ইউজারের ফাইল ও প্রসেস বন্ধ হবে।\n"
                f"• ডাটাবেসের সমস্ত রেকর্ড ও কোড স্থায়ীভাবে মুছে যাবে।\n"
                f"• বট সম্পূর্ণ ফ্রেশভাবে রিস্টার্ট নেবে।",
                call.message.chat.id, call.message.message_id,
                reply_markup=markup, parse_mode='HTML'
            )
        except: pass
        return

    if call.data == "confirm_clear_all_final":
        bot.answer_callback_query(call.id, "ক্লিয়ার করা হচ্ছে...")
        try:
            bot.edit_message_text(
                f"{PEM['wait']} <b>সকল প্রসেস বন্ধ করে সমস্ত ডাটা মুছে ফেলা হচ্ছে... বট রিস্টার্ট নিচ্ছে!</b>\n\n"
                f"বট পুনরায় অনলাইনে এসে আপনাকে সফল হওয়ার মেসেজ পাঠিয়ে দেবে। অনুগ্রহ করে ৫-১০ সেকেন্ড অপেক্ষা করুন।", 
                call.message.chat.id, call.message.message_id, parse_mode='HTML'
            )
        except: pass

        def perform_wipe():
            logger.warning("Executing Full System Wipe...")
            try:
                with open(RESTART_FLAG_FILE, 'w') as f:
                    json.dump({"chat_id": call.message.chat.id, "action": "wipe_success"}, f)
            except Exception as e:
                logger.error(f"Flag save error: {e}")

            for k in list(bot_scripts.keys()):
                kill_process_tree(bot_scripts[k])
            bot_scripts.clear()

            try:
                if os.path.exists(UPLOAD_BOTS_DIR):
                    shutil.rmtree(UPLOAD_BOTS_DIR)
                os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
            except Exception as e:
                logger.error(f"Upload wipe error: {e}")

            with DB_LOCK:
                try:
                    conn = get_db()
                    c = conn.cursor()
                    c.execute('DELETE FROM user_files')
                    c.execute('DELETE FROM subscriptions')
                    c.execute('DELETE FROM active_users')
                    c.execute('DELETE FROM force_channels')
                    c.execute('DELETE FROM users_meta')
                    c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
                    c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (OWNER_ID,))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    logger.error(f"DB wipe error: {e}")

            user_files.clear()
            user_subscriptions.clear()
            active_users.clear()
            active_users.add(OWNER_ID)
            pending_approvals.clear()
            users_meta.clear()

            time.sleep(1)
            python = sys.executable
            os.execl(python, python, *sys.argv)

        threading.Thread(target=perform_wipe, daemon=True).start()

# --- Callback Query Handler for Downloading User Files ---
@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("dluser:"))
def handle_download_user_files(call):
    admin_uid = call.from_user.id
    if admin_uid not in admin_ids:
        bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
        return

    target_uid = int(call.data.split(":", 1)[1])
    folder = get_user_folder(target_uid)
    files = user_files.get(target_uid, [])

    if not files or not os.path.exists(folder):
        bot.answer_callback_query(call.id, "কোনো ফাইল পাওয়া যায়নি!", show_alert=True)
        return

    bot.answer_callback_query(call.id, "ফাইল পাঠানো হচ্ছে...")
    uname = get_user_display_name(target_uid)

    sent_any = False
    for fn, ft in files:
        fp = os.path.join(folder, fn)
        if os.path.exists(fp):
            r = is_bot_running(target_uid, fn)
            status_txt = "🟢 Running" if r else "🔴 Stopped"
            cap = f"👤 User: {uname} (<code>{target_uid}</code>)\n📁 File: <code>{fn}</code>\n🚦 Status: {status_txt}"
            try:
                with open(fp, 'rb') as f_obj:
                    bot.send_document(call.message.chat.id, f_obj, caption=cap, parse_mode='HTML')
                sent_any = True
                time.sleep(0.3)
            except Exception as e:
                logger.error(f"Error sending file {fn} to admin: {e}")

    if not sent_any:
        bot.send_message(call.message.chat.id, f"{PEM['no']} ইউজারের কোনো সোর্স ফাইল ডিরেক্টরিতে পাওয়া যায়নি।", parse_mode='HTML')

# --- Button Text Handler ---
@bot.message_handler(func=lambda m: m.text in MAIN_MENU_BUTTONS)
def handle_btn(m):
    global bot_locked
    try: bot.clear_step_handler_by_chat_id(m.chat.id)
    except: pass

    t = m.text; uid = m.from_user.id
    register_user_activity(uid, m.from_user.username, m.from_user.first_name)

    if t == "✅ Joined - Check":
        channel_membership_cache.clear()
        if user_joined_required_channels(uid):
            send_welcome(m.chat.id, uid, m.from_user.first_name, m.from_user.username)
        else:
            send_force_join_prompt(m.chat.id, uid)
        return
    if uid not in admin_ids and not user_joined_required_channels(uid):
        send_force_join_prompt(m.chat.id, uid)
        return

    if t == "📢 Updates Channel":
        raw_send(m.chat.id, f"{PEM['msg']} <b>Updates Channel:</b>\n{UPDATE_CHANNEL}",
                 reply_keyboard=get_main_kb(uid))
    elif t == "📤 Upload File":
        limit = get_user_file_limit(uid); curr = get_user_file_count(uid)
        if curr >= limit:
            lim_str = str(limit) if limit != float('inf') else "Unlimited"
            raw_send(m.chat.id, f"{PEM['warn']} Limit reached ({curr}/{lim_str}).", reply_keyboard=get_main_kb(uid)); return
        
        info_txt = "⚡ <b>Instant Launch:</b> You have direct hosting access without approval!" if is_auto_approve_user(uid) else f"{PEM['warn']} <i>Free user files require Admin Approval.</i>"
        raw_send(m.chat.id,
                 f"{PEM['file']} Send your <code>.py</code>, <code>.js</code> or <code>.zip</code> file.\n{info_txt}",
                 reply_keyboard=get_main_kb(uid))
    elif t == "📂 Check Files":
        files = user_files.get(uid, [])
        if not files:
            raw_send(m.chat.id, f"{PEM['file']} No files.", reply_keyboard=get_main_kb(uid)); return
        msg = f"{PEM['file']} <b>Your files:</b>\n\n"
        kb = []
        for fn, ft in sorted(files):
            r = is_bot_running(uid, fn)
            icon = "🟢" if r else "🔴"
            msg += f"{icon} <code>{fn}</code> ({ft})\n"
            kb.append([rbtn(f"{'Stop' if r else 'Start'} {fn}", "6111726981760423576" if not r else "6311965254817423602",
                           "danger" if r else "success"),
                       rbtn(f"Logs {fn}", "6188447235244562676", "primary"),
                       rbtn(f"Delete {fn}", "6188343249791358585", "danger")])
        kb.append([rbtn("🔙 Back", "6109360506319935223", "primary")])
        raw_send(m.chat.id, msg, reply_keyboard=kb)
    elif t == "⚡ Bot Speed":
        t0 = time.time()
        res = raw_send(m.chat.id, f"{PEM['wait']} Testing...")
        diff = round((time.time() - t0) * 1000, 2)
        st = f"{PEM['check']} Unlocked" if not bot_locked else f"{PEM['warn']} Locked"
        if uid == OWNER_ID: lvl = f"{PEM['crown']} Owner"
        elif uid in admin_ids: lvl = f"{PEM['admin']} Admin"
        elif uid in user_subscriptions and user_subscriptions[uid].get('expiry', datetime.min) > datetime.now(): lvl = f"{PEM['check']} Premium"
        else: lvl = f"{PEM['user']} Free"
        if res and res.get("result"):
            try:
                bot.edit_message_text(f"{PEM['rocket']} Speed: <b>{diff} ms</b> ⚡ (Ultra-Fast)\n🚦 {st}\n👤 {lvl}",
                                      m.chat.id, res["result"]["message_id"], parse_mode='HTML')
            except: pass
    elif t == "📞 Contact Owner":
        raw_send(m.chat.id, f"{PEM['msg']} <b>Contact Owner:</b>\nhttps://t.me/{YOUR_USERNAME.replace('@', '')}",
                 reply_keyboard=get_main_kb(uid))
    elif t == "📊 Statistics":
        total_users = max(len(active_users), 1)
        total_files = sum(len(f) for f in user_files.values())
        running = sum(1 for k, v in bot_scripts.items() if is_bot_running(int(k.split('_')[0]), v['file_name']))
        mine = sum(1 for fn, _ in user_files.get(uid, []) if is_bot_running(uid, fn))
        msg = (f"{PEM['admin']} <b>Statistics:</b>\n\n"
               f"{PEM['user']} Users: {total_users}\n"
               f"{PEM['file']} Files: {total_files}\n"
               f"🟢 Running: {running}\n"
               f"{PEM['wait']} Pending: {len(pending_approvals)}\n")
        if uid in admin_ids:
            msg += f"🔒 Bot: {'Locked' if bot_locked else 'Unlocked'}\n🤖 Your Bots: {mine}"
        else:
            msg += f"🤖 Your Bots: {mine}"
        raw_send(m.chat.id, msg, reply_keyboard=get_main_kb(uid))
    elif t == "💳 Subscriptions":
        if uid not in admin_ids: raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid)); return
        raw_send(m.chat.id,
                 f"{PEM['money']} <b>Subscription Management</b>\n\n"
                 f"Send: <code>addsub ID DAYS</code>\n"
                 f"Send: <code>removesub ID</code>\n"
                 f"Send: <code>checksub ID</code>",
                 reply_keyboard=get_main_kb(uid))
    elif t == "📢 Broadcast":
        if uid not in admin_ids: raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid)); return
        msg = bot.reply_to(m, f"{PEM['msg']} Send broadcast message.\n/cancel to abort.", parse_mode='HTML')
        bot.register_next_step_handler(msg, process_broadcast)
    elif t == "🔒 Lock Bot":
        if uid not in admin_ids: raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid)); return
        bot_locked = not bot_locked
        raw_send(m.chat.id, f"{'🔒 Bot locked.' if bot_locked else '🔓 Bot unlocked.'}", reply_keyboard=get_main_kb(uid))
    elif t in ["🟢 Running All Code", "🟢 Run All"]:
        if uid not in admin_ids: raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid)); return
        run_all_scripts(m)
    elif t == "👑 Admin Panel":
        if uid not in admin_ids: raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid)); return
        raw_send(m.chat.id,
                 f"{PEM['crown']} <b>Admin Panel</b>\n\n"
                 f"Send: <code>addadmin ID</code>\n"
                 f"Send: <code>removeadmin ID</code>\n"
                 f"Send: <code>listadmins</code>",
                 reply_keyboard=get_admin_panel_kb())
    elif t == "➕ ADD CHANNEL":
        if uid not in admin_ids: return
        msg = bot.reply_to(m, f"{PEM['pin']} Channel/group @username বা public t.me link পাঠান।\n/cancel to abort.", parse_mode='HTML')
        bot.register_next_step_handler(msg, process_add_channel)
    elif t == "➖ REMOVE CHANNEL":
        if uid not in admin_ids: return
        channels = get_force_channels()
        if not channels:
            raw_send(m.chat.id, f"{PEM['warn']} No channels added.", reply_keyboard=get_admin_panel_kb()); return
        kb = [[rbtn(f"❌ Remove {title}", "6188343249791358585", "danger")] for _, title, _ in channels]
        kb.append([rbtn("🔙 Back", "6109360506319935223", "primary")])
        raw_send(m.chat.id, f"{PEM['rem']} <b>Select channel to remove:</b>", reply_keyboard=kb)
    elif t == "🔙 Back":
        raw_send(m.chat.id, f"{PEM['pin']} Main menu.", reply_keyboard=get_main_kb(uid))
    elif t == "👥 User Bots & Files":
        if uid not in admin_ids:
            raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid))
            return
        users_with_files = [u for u, files in user_files.items() if len(files) > 0]
        if not users_with_files:
            raw_send(m.chat.id, f"{PEM['warn']} বটের মধ্যে কোনো ইউজারের ফাইল নেই।", reply_keyboard=get_main_kb(uid))
            return

        msg_text = f"{PEM['admin']} <b>হোস্ট করা ইউজারদের ফাইল ও বট তালিকা:</b>\n\n"
        markup = types.InlineKeyboardMarkup()

        for idx, u in enumerate(users_with_files, 1):
            uname = get_user_display_name(u)
            total = len(user_files[u])
            running = sum(1 for fn, _ in user_files[u] if is_bot_running(u, fn))
            msg_text += (
                f"<b>{idx}. ইউজারনেম:</b> {uname}\n"
                f"🆔 <b>User ID:</b> <code>{u}</code>\n"
                f"📁 <b>আপলোড করা ফাইল:</b> {total} টি\n"
                f"🟢 <b>রানিং ফাইল:</b> {running} টি\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
            )
            markup.add(types.InlineKeyboardButton(f"📥 Get Files: {uname}", callback_data=f"dluser:{u}"))

        bot.send_message(m.chat.id, msg_text, reply_markup=markup, parse_mode='HTML')
    elif t == "🗑️ Clear All Data":
        if uid not in admin_ids:
            raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid))
            return
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("⚠️ হ্যাঁ, মুছে ফেলতে এগিয়ে যান", callback_data="req_clear_all"),
            types.InlineKeyboardButton("❌ বাতিল", callback_data="cancel_clear_all")
        )
        bot.send_message(
            m.chat.id,
            f"{PEM['warn']} <b>সতর্কতা: অল ডাটা ক্লিয়ারিং!</b>\n\n"
            f"আপনি কি সমস্ত ফাইল, হোস্টিং হিস্টোরি ও ডাটাবেস সম্পূর্ণভাবে মুছে ফেলতে চান?",
            reply_markup=markup, parse_mode='HTML'
        )

# --- Remove Force Channel Buttons ---
@bot.message_handler(func=lambda m: m.text and m.text.startswith("❌ Remove "))
def handle_remove_force_channel(m):
    uid = m.from_user.id
    if uid not in admin_ids: return
    title = m.text[len("❌ Remove "):].strip()
    found = next((x for x in get_force_channels() if x[1] == title), None)
    if not found:
        raw_send(m.chat.id, f"{PEM['no']} Channel not found.", reply_keyboard=get_admin_panel_kb()); return
    remove_force_channel_db(found[0])
    raw_send(m.chat.id, f"{PEM['ok']} Removed: <b>{title}</b>", reply_keyboard=get_admin_panel_kb())

# --- File Control via Text Commands ---
@bot.message_handler(func=lambda m: m.text and (
    m.text.startswith("Start ") or m.text.startswith("Stop ") or
    m.text.startswith("Delete ") or m.text.startswith("Logs ")
))
def handle_file_cmd(m):
    global bot_locked
    uid = m.from_user.id
    register_user_activity(uid, m.from_user.username, m.from_user.first_name)
    if uid not in admin_ids and not user_joined_required_channels(uid):
        send_force_join_prompt(m.chat.id, uid); return
    parts = m.text.split(maxsplit=1)
    if len(parts) != 2: return
    action = parts[0].lower()
    fn = parts[1].strip()

    owner = None
    for o, files in user_files.items():
        if any(f[0] == fn for f in files):
            owner = o
            break
    if owner is None:
        raw_send(m.chat.id, f"{PEM['no']} File not found.", reply_keyboard=get_main_kb(uid)); return
    if not (uid == owner or uid in admin_ids):
        raw_send(m.chat.id, f"{PEM['no']} Not yours.", reply_keyboard=get_main_kb(uid)); return

    folder = get_user_folder(owner); fp = os.path.join(folder, fn)
    ft = next((f[1] for f in user_files.get(owner, []) if f[0] == fn), 'py')
    key = f"{owner}_{fn}"

    if action == "start":
        if is_bot_running(owner, fn):
            raw_send(m.chat.id, f"{PEM['warn']} Already running.", reply_keyboard=get_main_kb(uid)); return
        if not os.path.exists(fp):
            raw_send(m.chat.id, f"{PEM['no']} Missing file.", reply_keyboard=get_main_kb(uid))
            remove_user_file_db(owner, fn); return
        if ft == 'py':
            threading.Thread(target=run_script, args=(fp, owner, folder, fn, m), daemon=True).start()
        elif ft == 'js':
            threading.Thread(target=run_js_script, args=(fp, owner, folder, fn, m), daemon=True).start()
    elif action == "stop":
        if not is_bot_running(owner, fn):
            raw_send(m.chat.id, f"{PEM['warn']} Already stopped.", reply_keyboard=get_main_kb(uid)); return
        pi = bot_scripts.get(key)
        if pi: kill_process_tree(pi)
        bot_scripts.pop(key, None)
        update_file_running_state(owner, fn, False)
        raw_send(m.chat.id, f"{PEM['ok']} Stopped {fn}.", reply_keyboard=get_main_kb(uid))
    elif action == "delete":
        if is_bot_running(owner, fn):
            pi = bot_scripts.get(key)
            if pi: kill_process_tree(pi)
            bot_scripts.pop(key, None)
        update_file_running_state(owner, fn, False)
        if os.path.exists(fp): os.remove(fp)
        lp = os.path.join(folder, f"{os.path.splitext(fn)[0]}.log")
        if os.path.exists(lp): os.remove(lp)
        remove_user_file_db(owner, fn)
        raw_send(m.chat.id, f"{PEM['ok']} Deleted {fn}.", reply_keyboard=get_main_kb(uid))
    elif action == "logs":
        lp = os.path.join(folder, f"{os.path.splitext(fn)[0]}.log")
        if not os.path.exists(lp):
            raw_send(m.chat.id, f"{PEM['no']} No logs.", reply_keyboard=get_main_kb(uid)); return
        try:
            content = ""; fs = os.path.getsize(lp)
            max_kb = 60; max_msg = 3500
            if fs == 0: content = "(Empty)"
            elif fs > max_kb * 1024:
                with open(lp, 'rb') as f:
                    f.seek(-max_kb * 1024, os.SEEK_END)
                    content = f.read().decode('utf-8', errors='ignore')
                content = f"(Last {max_kb} KB)\n...\n" + content
            else:
                with open(lp, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
            if len(content) > max_msg:
                content = content[-max_msg:]
                nl = content.find('\n')
                if nl != -1: content = "...\n" + content[nl+1:]
            if not content.strip(): content = "(No content)"
            raw_send(m.chat.id, f"{PEM['file']} Logs for <b>{fn}</b>:\n<pre>{content}</pre>",
                     reply_keyboard=get_main_kb(uid))
        except Exception as e:
            raw_send(m.chat.id, f"{PEM['no']} Error: {e}", reply_keyboard=get_main_kb(uid))

# --- Text commands for admin panel ---
@bot.message_handler(func=lambda m: m.text and (
    m.text.startswith("addadmin ") or m.text.startswith("removeadmin ") or
    m.text.lower() == "listadmins" or
    m.text.startswith("addsub ") or m.text.startswith("removesub ") or
    m.text.startswith("checksub ")
))
def handle_admin_cmd(m):
    uid = m.from_user.id
    register_user_activity(uid, m.from_user.username, m.from_user.first_name)
    if uid not in admin_ids:
        raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid)); return
    txt = m.text.strip()
    low = txt.lower()

    if low == "listadmins":
        lst = "\n".join(f"- <code>{a}</code> {'(Owner)' if a == OWNER_ID else ''}" for a in sorted(admin_ids))
        if not lst: lst = "(None)"
        raw_send(m.chat.id, f"{PEM['crown']} <b>Admins:</b>\n\n{lst}", reply_keyboard=get_main_kb(uid))
        return

    if low.startswith("addadmin "):
        if uid != OWNER_ID:
            raw_send(m.chat.id, f"{PEM['no']} Owner only.", reply_keyboard=get_main_kb(uid)); return
        try:
            nid = int(txt.split()[1])
            if nid == OWNER_ID or nid in admin_ids:
                raw_send(m.chat.id, f"{PEM['warn']} Already admin.", reply_keyboard=get_main_kb(uid)); return
            add_admin_db(nid)
            raw_send(m.chat.id, f"{PEM['ok']} Added admin <code>{nid}</code>.", reply_keyboard=get_main_kb(uid))
            try: bot.send_message(nid, f"{PEM['crown']} You are now Admin!", parse_mode='HTML')
            except: pass
        except:
            raw_send(m.chat.id, f"{PEM['no']} Usage: addadmin ID", reply_keyboard=get_main_kb(uid))
        return

    if low.startswith("removeadmin "):
        if uid != OWNER_ID:
            raw_send(m.chat.id, f"{PEM['no']} Owner only.", reply_keyboard=get_main_kb(uid)); return
        try:
            rid = int(txt.split()[1])
            if remove_admin_db(rid):
                raw_send(m.chat.id, f"{PEM['ok']} Removed admin <code>{rid}</code>.", reply_keyboard=get_main_kb(uid))
            else:
                raw_send(m.chat.id, f"{PEM['warn']} Not admin.", reply_keyboard=get_main_kb(uid))
        except:
            raw_send(m.chat.id, f"{PEM['no']} Usage: removeadmin ID", reply_keyboard=get_main_kb(uid))
        return

    if low.startswith("addsub "):
        try:
            parts = txt.split()
            sid = int(parts[1]); days = int(parts[2])
            if sid <= 0 or days <= 0: raise ValueError()
            ce = user_subscriptions.get(sid, {}).get('expiry')
            start = datetime.now()
            if ce and ce > start: start = ce
            ne = start + timedelta(days=days)
            save_subscription(sid, ne)
            raw_send(m.chat.id, f"{PEM['ok']} Sub added. Expiry: {ne:%Y-%m-%d}", reply_keyboard=get_main_kb(uid))
            try: bot.send_message(sid, f"{PEM['pin']} Premium Active! Expires: {ne:%Y-%m-%d}.\nYou now have <b>Direct Auto-Hosting</b> access without Admin Approval!", parse_mode='HTML')
            except: pass
        except:
            raw_send(m.chat.id, f"{PEM['no']} Usage: addsub ID DAYS", reply_keyboard=get_main_kb(uid))
        return

    if low.startswith("removesub "):
        try:
            sid = int(txt.split()[1])
            remove_subscription_db(sid)
            raw_send(m.chat.id, f"{PEM['ok']} Sub removed.", reply_keyboard=get_main_kb(uid))
            try: bot.send_message(sid, f"{PEM['no']} Subscription removed.", parse_mode='HTML')
            except: pass
        except:
            raw_send(m.chat.id, f"{PEM['no']} Usage: removesub ID", reply_keyboard=get_main_kb(uid))
        return

    if low.startswith("checksub "):
        try:
            sid = int(txt.split()[1])
            if sid in user_subscriptions:
                e = user_subscriptions[sid].get('expiry')
                if e:
                    if e > datetime.now():
                        dl = (e - datetime.now()).days
                        raw_send(m.chat.id, f"{PEM['ok']} <code>{sid}</code> active. Expires: {e:%Y-%m-%d} ({dl} days)", reply_keyboard=get_main_kb(uid))
                    else:
                        raw_send(m.chat.id, f"{PEM['warn']} <code>{sid}</code> expired.", reply_keyboard=get_main_kb(uid))
                        remove_subscription_db(sid)
                else:
                    raw_send(m.chat.id, f"{PEM['warn']} Expiry missing.", reply_keyboard=get_main_kb(uid))
            else:
                raw_send(m.chat.id, f"{PEM['user']} No sub.", reply_keyboard=get_main_kb(uid))
        except:
            raw_send(m.chat.id, f"{PEM['no']} Usage: checksub ID", reply_keyboard=get_main_kb(uid))
        return

# --- Document Handler ---
@bot.message_handler(content_types=['document'])
def handle_doc(m):
    try: bot.clear_step_handler_by_chat_id(m.chat.id)
    except: pass
    uid = m.from_user.id
    doc = m.document
    register_user_activity(uid, m.from_user.username, m.from_user.first_name)
    if uid not in admin_ids and not user_joined_required_channels(uid):
        send_force_join_prompt(m.chat.id, uid); return
    if bot_locked and uid not in admin_ids:
        raw_send(m.chat.id, f"{PEM['warn']} Bot locked.", reply_keyboard=get_main_kb(uid)); return
    limit = get_user_file_limit(uid); curr = get_user_file_count(uid)
    if curr >= limit:
        lim_str = str(limit) if limit != float('inf') else "Unlimited"
        raw_send(m.chat.id, f"{PEM['warn']} Limit reached ({curr}/{lim_str}).", reply_keyboard=get_main_kb(uid)); return
    fn = doc.file_name
    if not fn: raw_send(m.chat.id, f"{PEM['no']} No file name.", reply_keyboard=get_main_kb(uid)); return
    ext = os.path.splitext(fn)[1].lower()
    if ext not in ['.py', '.js', '.zip']:
        raw_send(m.chat.id, f"{PEM['no']} Only .py, .js, .zip allowed.", reply_keyboard=get_main_kb(uid)); return
    if doc.file_size > 25 * 1024 * 1024:
        raw_send(m.chat.id, f"{PEM['no']} Max file size 25MB.", reply_keyboard=get_main_kb(uid)); return
    try:
        fi = bot.get_file(doc.file_id)
        content = FAST_SESSION.get(f"https://api.telegram.org/file/bot{TOKEN}/{fi.file_path}", timeout=30).content
        folder = get_user_folder(uid)
        if ext == '.zip':
            handle_zip(content, fn, m)
        else:
            fp = os.path.join(folder, fn)
            with open(fp, 'wb') as f: f.write(content)
            if ext == '.js': handle_js(fp, uid, folder, fn, m)
            elif ext == '.py': handle_py(fp, uid, folder, fn, m)
    except telebot.apihelper.ApiTelegramException as e:
        if "file is too big" in str(e).lower():
            raw_send(m.chat.id, f"{PEM['no']} File too large.", reply_keyboard=get_main_kb(uid))
        else:
            raw_send(m.chat.id, f"{PEM['no']} TG Error: {e}", reply_keyboard=get_main_kb(uid))
    except Exception as e:
        logger.error(f"doc err: {e}", exc_info=True)
        raw_send(m.chat.id, f"{PEM['no']} Error: {e}", reply_keyboard=get_main_kb(uid))

# --- Broadcast ---
def process_broadcast(m):
    uid = m.from_user.id
    if uid not in admin_ids: return
    if m.text in MAIN_MENU_BUTTONS or (m.text and m.text.lower() == '/cancel'):
        raw_send(m.chat.id, "❌ Broadcast cancelled.", reply_keyboard=get_main_kb(uid))
        if m.text in MAIN_MENU_BUTTONS:
            handle_btn(m)
        return
    content = m.text
    if not content and not (m.photo or m.video or m.document or m.sticker):
        raw_send(m.chat.id, f"{PEM['no']} Empty.", reply_keyboard=get_main_kb(uid)); return
    raw_send(m.chat.id, f"{PEM['wait']} Broadcasting to {len(active_users)} users...", reply_keyboard=get_main_kb(uid))
    threading.Thread(target=do_broadcast, args=(content, m.chat.id), daemon=True).start()

def do_broadcast(text, chat_id):
    sent = 0; failed = 0; blocked = 0
    users = list(active_users); total = len(users)
    for i, u in enumerate(users):
        try:
            bot.send_message(u, f"{PEM['bell']} {text}", parse_mode='HTML')
            sent += 1
        except telebot.apihelper.ApiTelegramException as e:
            ed = str(e).lower()
            if any(s in ed for s in ["blocked", "deactivated", "chat not found", "kicked", "restricted"]):
                blocked += 1
            else: failed += 1
        except: failed += 1
        if (i + 1) % 25 == 0: time.sleep(1.2)
        elif i % 5 == 0: time.sleep(0.1)
    raw_send(chat_id, f"{PEM['ok']} <b>Broadcast Complete!</b>\n\n✅ Sent: {sent}\n❌ Failed: {failed}\n🚫 Blocked: {blocked}\n👥 Total: {total}")

# --- Run All Scripts ---
def run_all_scripts(m):
    uid = m.from_user.id; chat_id = m.chat.id
    if uid not in admin_ids: return
    raw_send(chat_id, f"{PEM['wait']} Starting all scripts...", reply_keyboard=get_main_kb(uid))
    threading.Thread(target=run_all_scripts_bg, args=(chat_id,), daemon=True).start()

def run_all_scripts_bg(chat_id):
    started = 0; users_count = 0; skipped = 0
    snapshot = dict(user_files)
    for tuid, files in snapshot.items():
        if not files: continue
        users_count += 1
        uf = get_user_folder(tuid)
        for fn, ft in files:
            if not is_bot_running(tuid, fn):
                fp = os.path.join(uf, fn)
                if os.path.exists(fp):
                    try:
                        if ft == 'py':
                            threading.Thread(target=run_script, args=(fp, tuid, uf, fn, None), daemon=True).start()
                            started += 1
                        elif ft == 'js':
                            threading.Thread(target=run_js_script, args=(fp, tuid, uf, fn, None), daemon=True).start()
                            started += 1
                        time.sleep(0.8)
                    except: skipped += 1
                else: skipped += 1
    msg = f"{PEM['ok']} Started: {started}\n👥 Users: {users_count}\n"
    if skipped: msg += f"{PEM['warn']} Skipped: {skipped}\n"
    raw_send(chat_id, msg)

# --- Check Post-Restart Notification ---
def check_post_restart():
    if os.path.exists(RESTART_FLAG_FILE):
        try:
            with open(RESTART_FLAG_FILE, 'r') as f:
                data = json.load(f)
            os.remove(RESTART_FLAG_FILE)
            cid = data.get("chat_id")
            if cid:
                time.sleep(1.5)
                raw_send(
                    cid,
                    f"{PEM['ok']} <b>All Data Cleared & Bot Restarted Successfully!</b>\n\n"
                    f"🎉 সম্পূর্ণ ডাটাবেস ও সকল হোস্টেড ফাইল সফলভাবে মুছে ফেলা হয়েছে এবং বট সম্পূর্ণ ফ্রেশভাবে পুনরায় চালু হয়েছে।",
                    reply_keyboard=get_main_kb(cid)
                )
        except Exception as e:
            logger.error(f"check_post_restart error: {e}")

# --- Cleanup ---
def cleanup():
    logger.warning("Shutting down...")
    for k in list(bot_scripts.keys()):
        if k in bot_scripts: kill_process_tree(bot_scripts[k])
atexit.register(cleanup)

# --- Main Polling ---
if __name__ == '__main__':
    logger.info("=" * 40 + f"\n🤖 Bot Starting...\n🔑 Owner: {OWNER_ID}\n🛡️ Admins: {admin_ids}\n" + "=" * 40)
    keep_alive()
    check_post_restart()
    logger.info("🚀 Polling started with 30 worker threads...")
    
    while True:
        try:
            bot.infinity_polling(
                timeout=25,
                long_polling_timeout=15,
                skip_pending=True,
                logger_level=logging.WARNING
            )
        except requests.exceptions.ReadTimeout:
            time.sleep(1)
        except requests.exceptions.ConnectionError:
            time.sleep(3)
        except Exception as e:
            logger.error(f"💥 Polling error: {e}")
            time.sleep(3)