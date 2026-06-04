
import asyncio
import logging
import random
import re
import math
import string
import decimal
from datetime import datetime, timedelta
import sqlite3
from collections import deque
import time
import uuid
import html
from typing import Dict, List
from typing import Optional
from decimal import Decimal, ROUND_DOWN
from aiogram import Bot, Dispatcher, types
from aiogram.utils.markdown import escape_md, hbold, hlink, bold
from aiogram.dispatcher import FSMContext
from aiogram.types import ParseMode
from aiogram.utils.exceptions import CantParseEntities
from aiogram.dispatcher.filters import CommandStart, Text
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils import executor
from html import escape
from urllib.parse import quote
from aiogram.types import Message
from html import escape as escape_html  # Для HTML-экранирования
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.utils.exceptions import MessageCantBeEdited, MessageToDeleteNotFound
from aiogram.utils.exceptions import ChatNotFound, BotBlocked, MessageNotModified
from aiogram.dispatcher.handler import CancelHandler
from aiogram.utils import exceptions
from aiogram.utils.exceptions import MessageToEditNotFound


# Токен вашего бота
BOT_TOKEN = "8511850128:AAH3om4xK7FwXewfNUqRdstYer31eGW9eL0"
# Список ID владельцев
OWNER_IDS = {5439940299}

# ID канала для фастов

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Создаем блокировку для синхронизации доступа к базе данных
db_lock = asyncio.Lock()

OFFICIAL_CHAT_ID = -1002669310047

# Константы игры "Крипто-Бум"
CRYPTO_BOOM_MULTIPLIER = 1.25
CRYPTO_BOOM_WIN_CHANCE = 0.25  # 25% шанс выигрыша
CRYPTO_BOOM_LOSE_CHANCE = 0.75 # 75% шанс проигрыша
MIN_STAKE_KR = 100 #Минимальная ставка

# Словарь для хранения статистики "Крипто-Бум"
crypto_boom_stats = {"Выше": 0, "Ниже": 0}

# --- Функция для обновления статистики "Крипто-Бум" ---
async def update_crypto_boom_stats(direction):
    """Обновляет статистику выигрышей/проигрышей в игре 'Крипто-Бум'."""
    if direction in crypto_boom_stats:
        crypto_boom_stats[direction] += 1

# FSM для "Крипто-Бум"
class CryptoBoomState(FSMContext):
    user_id: int
    stake: int
    current_x: float
    position: str  # Текущее положение
    next_position: str # Следующее положение (для определения результата)
    message_id: int # ID сообщения с игрой, чтобы обновлять его
    chat_id: int # ID чата, где идет игра
    has_active_game: bool
    claimed: bool # Добавляем флаг, чтобы отслеживать, был ли приз уже получен
    last_claim_time: float # Время последней попытки забрать приз

# Добавляем словарь для хранения информации о последних попытках получения приза
last_claim_attempts = {} # user_id: (timestamp, winning_amount)

CLAIM_COOLDOWN = 1 #Задержка между попытками (в секундах)

# Константы (перенесите в файл конфигурации или переменные окружения в production)
CRASH_MIN_X = 1.01  # Минимальный множитель (икс)
CRASH_MAX_X = 10.0  # Максимальный множитель (икс)
CRASH_DURATION = 3  # Длительность анимации ракеты в секундах (минимум)
MIN_STAKE_CR = 100  # Минимальная ставка
RANDOM_CRASH_MIN = 1.00
RANDOM_CRASH_MAX = 10.0

MIN_STAKE_KB = 100

# Эмодзи
ROCKET_EMOJI = "🚀"
BOOM_EMOJI = "💥"
CHECK_MARK_EMOJI = "✅"
CROSS_MARK_EMOJI = "❌"


# --- Константы ---
DICE_GAME_TIMEOUT = 60  # Время ожидания ответа в секундах
DICE_EMOJI = "🎲"
MIN_DICE_STAKE = 100  # Минимальная ставка в кубе
active_games = {} #Dictionary to store active game message ids

# Инициализация базы данных SQLite
conn = sqlite3.connect('blaze_bot.db', check_same_thread=False)  # Добавьте check_same_thread=False
cursor = conn.cursor()

# --- Функция для получения соединения с базой данных ---
def get_db_connection():
    return sqlite3.connect('blaze_bot.db', check_same_thread=False)

# --- Функция для закрытия соединения с базой данных ---
def close_db_connection(conn):
    conn.close()

# Создание таблиц, если их нет
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0,
    last_bonus DATETIME,
    last_nasrat DATETIME,
    last_command DATETIME,
    has_miner INTEGER DEFAULT 0,
    miner_last_used DATETIME,
    sin_level INTEGER DEFAULT 1,
    sin_experience INTEGER DEFAULT 0,
    last_chip_activation DATETIME,
    big_bonus_count INTEGER DEFAULT 4,
    last_big_bonus DATETIME,
    spins INTEGER DEFAULT 0,
    has_meat_raw INTEGER DEFAULT 0,
    taxi_last_used DATETIME,
    has_taxi INTEGER DEFAULT 0,
    hide_balance INTEGER DEFAULT 0,
    g_fyn INTEGER DEFAULT 0,
    last_allowance DATETIME,
    vip_expiry DATETIME,
    mine_last_used DATETIME,
    has_pickaxe INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    registration_date TEXT,
    business_profit_stash INTEGER DEFAULT 0,
    is_verified INTEGER DEFAULT 0,
    status_id INTEGER DEFAULT 0,
    last_box DATETIME
)
""")
conn.commit()

# Добавляем колонку spins, если её нет
try:
    cursor.execute("ALTER TABLE users ADD COLUMN spins INTEGER DEFAULT 0")
    conn.commit()
except sqlite3.OperationalError:
    # колонка уже существует — игнорируем
    pass
 

# Функция для добавления колонок статистики (если их нет)
def ensure_game_columns():
    conn_local = get_db_connection()
    cur = conn_local.cursor()
    cur.execute("PRAGMA table_info(users)")
    existing = [col[1] for col in cur.fetchall()]

    cols_to_add = {
        "losp": "INTEGER DEFAULT 0",
        "winp": "INTEGER DEFAULT 0",
        "gamep": "INTEGER DEFAULT 0",
        "darkp": "INTEGER DEFAULT 0"
    }

    for col, typ in cols_to_add.items():
        if col not in existing:
            try:
                cur.execute(f"ALTER TABLE users ADD COLUMN {col} {typ}")
                conn_local.commit()
                logging.info(f"Added '{col}' column to users table.")
            except sqlite3.OperationalError as e:
                logging.error(f"Error adding column {col}: {e}")
    close_db_connection(conn_local)

# Вызов проверки/создания колонок статистики
ensure_game_columns()

# Добавляем колонку business_level в таблицу users
def add_business_level_column():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN business_level INTEGER DEFAULT 0")
        conn.commit()
        logging.info("Added 'business_level' column to the 'users' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            logging.info("'business_level' column already exists in the 'users' table.")
        else:
            logging.error(f"Error adding 'business_level' column: {e}")
    finally:
        close_db_connection(conn)

add_business_level_column()

# Добавляем колонку last_business_profit_claim в таблицу users
def add_last_business_profit_claim_column():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN last_business_profit_claim DATETIME")
        conn.commit()
        logging.info("Added 'last_business_profit_claim' column to the 'users' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            logging.info("'last_business_profit_claim' column already exists in the 'users' table.")
        else:
            logging.error(f"Error adding 'last_business_profit_claim' column: {e}")
    finally:
        close_db_connection(conn)

add_last_business_profit_claim_column()

def ensure_registered_at_column():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'registered_at' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN registered_at TEXT")
        conn.commit()
    close_db_connection(conn)

ensure_registered_at_column()


def add_losses_column():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'losses' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN losses INTEGER DEFAULT 0")
        conn.commit()
        logging.info("Added 'losses' column to the 'users' table.")
    else:
        logging.info("'losses' column already exists in the 'users' table.")
    close_db_connection(conn)

add_losses_column()


# Добавляем колонку g_fyn в таблицу users
def add_g_fyn_column():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN g_fyn INTEGER DEFAULT 0")
        conn.commit()
        logging.info("Added 'g_fyn' column to the 'users' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            logging.info("'g_fyn' column already exists in the 'users' table.")
        else:
            logging.error(f"Error adding 'g_fyn' column: {e}")
    finally:
        close_db_connection(conn)

add_g_fyn_column()

# Добавляем колонку vip_expiry в таблицу users
def add_vip_expiry_column():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN vip_expiry DATETIME")
        conn.commit()
        logging.info("Added 'vip_expiry' column to the 'users' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            logging.info("'vip_expiry' column already exists in the 'users' table.")
        else:
            logging.error(f"Error adding 'vip_expiry' column: {e}")
    finally:
        close_db_connection(conn)

add_vip_expiry_column()

# Добавляем колонку last_allowance в таблицу users
def add_last_allowance_column():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN last_allowance DATETIME")
        conn.commit()
        logging.info("Added 'last_allowance' column to the 'users' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            logging.info("'last_allowance' column already exists in the 'users' table.")
        else:
            logging.error(f"Error adding 'last_allowance' column: {e}")
    finally:
        close_db_connection(conn)

add_last_allowance_column()


cursor.execute("""
    CREATE TABLE IF NOT EXISTS fasts (
        fast_id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount INTEGER,
        activations INTEGER,
        message_id INTEGER,
        chat_id INTEGER
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS fast_claims (
        user_id INTEGER,
        fast_id INTEGER,
        PRIMARY KEY (user_id, fast_id)
    )
""")


# Добавьте создание таблицы bank_accounts
cursor.execute("""
    CREATE TABLE IF NOT EXISTS bank_accounts (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS mines_games (
        game_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        field INTEGER NOT NULL,
        stake INTEGER NOT NULL,
        mines TEXT NOT NULL,
        opened_cells TEXT,
        coefficient REAL NOT NULL,
        game_over INTEGER NOT NULL DEFAULT 0,
        claimed BOOLEAN NOT NULL DEFAULT FALSE
    )          
""")

# Таблица забаненных пользователей
cursor.execute("""
    CREATE TABLE IF NOT EXISTS banned_users (
        user_id INTEGER PRIMARY KEY
    )
""")

# Таблица промокодов
cursor.execute("""
    CREATE TABLE IF NOT EXISTS promocodes (
        code TEXT PRIMARY KEY,
        amount INTEGER,
        activations INTEGER,
        used_by TEXT DEFAULT ''
    )
""")



conn.commit()

# -------------------- Игнорирование сообщения --------------------
# Словарь для хранения времени последнего использования команды для каждого пользователя
last_command_time = {}
COMMAND_COOLDOWN = 1  # Задержка в секундах

async def is_command_allowed(user_id):
    """Проверяет, можно ли пользователю использовать команду."""
    now = datetime.now()
    if user_id in last_command_time:
        time_since_last_command = now - last_command_time[user_id]
        if time_since_last_command < timedelta(seconds=COMMAND_COOLDOWN):
            return False
    return True

async def update_last_command_time(user_id):
    """Обновляет время последнего использования команды для пользователя."""
    last_command_time[user_id] = datetime.now()

# -------------------- Утилиты для форматирования ставок --------------------
async def is_user_in_chat(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Проверяет, состоит ли пользователь в чате."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status not in (types.ChatMemberStatus.LEFT, types.ChatMemberStatus.KICKED)
    except Exception as e:
        logging.error(f"Ошибка при проверке пользователя в чате: {e}")
        return False


def format_stake(stake_str):
    """Форматирует строку ставки, заменяя 'к', 'кк', 'ккк' и т.д. на число."""
    stake_str = str(stake_str).lower().strip()  # Преобразуем в строку, в нижний регистр, убираем пробелы

    if stake_str == 'все':
        return 'все'  # Special case

    multipliers = {
        'к': 1000,
        'кк': 1000000,
        'ккк': 1000000000,
        'кккк': 1000000000000,
        'ккккк': 1000000000000000,
        'кккккк': 1000000000000000000  # Добавлено значение для 'кккккк' (миллиард миллиардов)
    }

    best_suffix = None
    for suffix in multipliers:
        if stake_str.endswith(suffix) and (best_suffix is None or len(suffix) > len(best_suffix)):
            best_suffix = suffix

    if best_suffix:
        try:
            base_value = stake_str[:-len(best_suffix)].replace(",", "")  # Убираем запятые из base_value
            base_value = float(base_value)  # Преобразуем в float
            return base_value * multipliers[best_suffix]
        except ValueError:
            return None  # Invalid format

    try:
        stake_str = stake_str.replace(",", "")  # Убираем запятые, если нет суффикса
        return float(stake_str)
    except ValueError:
        return None  # Invalid format



def format_balance(balance):
    """Форматирует баланс в строковом представлении с использованием 'к', 'кк' и т.д."""
    if balance >= 1000000000000000000:
        return f"{balance / 1000000000000000000:.1f}кккккк"  # Триллион триллионов
    elif balance >= 1000000000000000:
        return f"{balance / 1000000000000000:.1f}ккккк"  # Квадриллион
    elif balance >= 1000000000000:
        return f"{balance / 1000000000000:.1f}кккк"  # Триллион
    elif balance >= 1000000000:
        return f"{balance / 1000000000:.1f}ккк"  # Миллиард
    elif balance >= 1000000:
        return f"{balance / 1000000:.1f}кк"  # Миллион
    elif balance >= 1000:
        return f"{balance / 1000:.1f}к"  # Тысяча
    else:
        return str(int(balance))

async def get_user_balance(user_id):
    """Получает баланс пользователя из базы данных."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    close_db_connection(conn)
    if result:
        return result[0]
    else:
        return 0
    

db_lock = asyncio.Lock()

async def update_user_balance(user_id, amount):
    """Обновляет баланс пользователя в базе данных."""
    async with db_lock: #Используем блокировку для избежания конкурентного доступа
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            conn.commit()
        finally:
            close_db_connection(conn)    

async def create_user(user_id, username):
    """Создает пользователя в базе данных, если его там нет."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, balance, has_taxi, taxi_last_used) VALUES (?, ?, 0, 0, NULL)", (user_id, username))
    conn.commit()
    close_db_connection(conn)


async def get_bank_balance(user_id):
    """Получает баланс банка пользователя из базы данных."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM bank_accounts WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    close_db_connection(conn)
    if result:
        return result[0]
    else:
        return 0


async def update_bank_balance(user_id, amount):
    """Обновляет баланс банка пользователя в базе данных."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO bank_accounts (user_id, balance) VALUES (?, 0)", (user_id,))
    cursor.execute("UPDATE bank_accounts SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    close_db_connection(conn)   

async def is_user_banned(user_id):
    """Проверяет, забанен ли пользователь."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM banned_users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    close_db_connection(conn)
    return result is not None 

async def is_user_added(user_id):
    """Проверяет, был ли пользователь уже добавлен."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM added_users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result is not None
    except sqlite3.Error as e:
        logging.error(f"Ошибка при проверке пользователя в added_users: {e}")
        return False
    finally:
        close_db_connection(conn)

async def add_user_to_added(user_id):
    """Добавляет пользователя в таблицу added_users."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO added_users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        logging.info(f"Пользователь {user_id} добавлен в added_users.")
    except sqlite3.Error as e:
        logging.error(f"Ошибка при добавлении пользователя в added_users: {e}")
    finally:
        close_db_connection(conn)


async def format_time(seconds):
    """Форматирует время в минутах и секундах."""
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"

async def get_last_command_time(user_id):
    """Получает время последней активации команды из базы данных."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT last_command FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    close_db_connection(conn)
    if result and result[0]:
        return datetime.fromisoformat(result[0])
    return None

# -------------------- Функция для добавления колонки deleted (если ее нет) --------------------
async def is_user_in_chat(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Проверяет, состоит ли пользователь в чате."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        # Проверяем статус участника чата
        if member.status in (
            types.ChatMemberStatus.LEFT,
            types.ChatMemberStatus.KICKED,
            types.ChatMemberStatus.RESTRICTED, # Добавил статус RESTRICTED (ограничен)
        ):
            return False  # Пользователь покинул чат или заблокирован
        else:
            return True  # Пользователь является участником чата
    except Exception as e:
        # Обрабатываем исключения, например, когда пользователя нет в чате
        logging.error(f"Ошибка при проверке пользователя в чате: {e}")
        return False  # Считаем, что пользователя нет в чате в случае ошибки



# --- Создание пользователя если нет ---
async def create_user(user_id, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    registration_date = datetime.now().isoformat()  # Фиксируем дату регистрации ТОЛЬКО при создании
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, balance, has_taxi, taxi_last_used, losses, description, registration_date) "
        "VALUES (?, ?, 0, 0, NULL, 0, '', ?)",
        (user_id, username, registration_date)
    )
    conn.commit()
    close_db_connection(conn)


@dp.message_handler(Text(equals="+база", ignore_case=True))
async def update_database_command(message: types.Message):
    if user_id not in OWNER_IDS:
        return  # Только владелец может использовать

    sent_message = await message.answer("🔌| Обновление базы данных....")

    async with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Получаем список user_id всех, кто есть в таблице users
            cursor.execute("SELECT user_id FROM users")
            existing_users = {row[0] for row in cursor.fetchall()}

            # Предположим, что у тебя есть список user_id, которые должны быть добавлены.
            # Если нет — можно получить из других таблиц, например из squad_members, fast_claims и т.д.
            # Ниже пример: собираем user_id из squad_members, fast_claims, fast_claims_g_fyn и т.п.
            
            user_ids_to_check = set()

            # Из squad_members
            cursor.execute("SELECT DISTINCT user_id FROM squad_members")
            user_ids_to_check.update(row[0] for row in cursor.fetchall())

            # Из fast_claims
            cursor.execute("SELECT DISTINCT user_id FROM fast_claims")
            user_ids_to_check.update(row[0] for row in cursor.fetchall())

            # Из fast_claims_g_fyn
            cursor.execute("SELECT DISTINCT user_id FROM fast_claims_g_fyn")
            user_ids_to_check.update(row[0] for row in cursor.fetchall())

            # Из check_activations
            cursor.execute("SELECT DISTINCT user_id FROM check_activations")
            user_ids_to_check.update(row[0] for row in cursor.fetchall())

            # Добавь сюда другие таблицы, если нужно

            # Находим тех, кто есть в других таблицах, но отсутствует в users
            missing_users = user_ids_to_check - existing_users

            # Добавляем отсутствующих пользователей с балансом 0 и пустым username
            for missing_user_id in missing_users:
                cursor.execute(
                    "INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, 0)",
                    (missing_user_id, '')
                )
            conn.commit()

        finally:
            close_db_connection(conn)

    await sent_message.edit_text("🔋| База усмешно обновлена!")


def escape_html_tags(text):
    """Экранирует HTML-теги в тексте, чтобы избежать ошибок разбора."""
    return escape(text)


async def get_user_stats(user_id: int):
    conn_local = get_db_connection()
    cur = conn_local.cursor()
    cur.execute("SELECT balance, winp, losp, gamep, darkp FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    close_db_connection(conn_local)
    if row:
        return {
            "balance": row[0] or 0,
            "winp": row[1] or 0,
            "losp": row[2] or 0,
            "gamep": row[3] or 0,
            "darkp": row[4] or 0
        }
    else:
        return {"balance": 0, "winp": 0, "losp": 0, "gamep": 0, "darkp": 0}

async def increment_field(user_id: int, field: str, amount: int):
    """Универсальная безопасная инкрементация поля (может быть отрицательной)."""
    if field not in ("winp", "losp", "gamep", "darkp", "balance"):
        raise ValueError("Invalid field to increment")
    async with db_lock:
        conn_local = get_db_connection()
        cur = conn_local.cursor()
        cur.execute(f"UPDATE users SET {field} = COALESCE({field}, 0) + ? WHERE user_id = ?", (amount, user_id))
        conn_local.commit()
        close_db_connection(conn_local)

async def add_win_record(user_id: int, amount: int):
    if amount <= 0:
        return
    await increment_field(user_id, "winp", amount)

async def add_loss_record(user_id: int, amount: int):
    if amount <= 0:
        return
    await increment_field(user_id, "losp", amount)

async def increment_games_played(user_id: int, amount: int = 1):
    await increment_field(user_id, "gamep", amount)

async def add_dark(user_id: int, amount: int):
    await increment_field(user_id, "darkp", amount)




# ----------------------------- Система статусов -----------------------------
STATUSES = {
    0: {"name": "отсутствует", "cost": 0, "bonus_mult": 1.0, "box_mult": 1.0, "donate": False},
    1: {"name": "💸Додепер💸", "cost": 10_000, "bonus_mult": 1.1,  "box_mult": 1.11, "donate": False},
    2: {"name": "📯Ambassador📯", "cost": 100_000, "bonus_mult": 1.15, "box_mult": 1.18, "donate": False},
    3: {"name": "🏆 Legend🏆", "cost": 1_000_000, "bonus_mult": 1.2,  "box_mult": 1.23, "donate": False},
    4: {"name": "🚀Buster🚀", "cost": 7_000_000, "bonus_mult": 1.4, "box_mult": 1.5, "donate": False},
    5: {"name": "🛸NLO🛸", "cost": 17_000_000, "bonus_mult": 1.5, "box_mult": 1.6,  "donate": False},
    6: {"name": "🦈Shark🦈", "cost": 35_000_000, "bonus_mult": 2.0,  "box_mult": 2.2,  "donate": False},
    7: {"name": "🕷Sirius🕷", "cost": 90_000_000, "bonus_mult": 2.7,  "box_mult": 3.7, "donate": False},
    8: {"name": "⚜🦋Gold fly🦋⚜", "cost": 190_000_000, "bonus_mult": 5.0,  "box_mult": 7.0,  "donate": False},
    9: {"name": "♦️♠️Игроман♠️♦️", "cost": 800_000_000, "bonus_mult": 11.0,  "box_mult": 14.0,  "donate": False},
    10:{"name": "🦎Spark GD🦎", "cost": 0, "bonus_mult": 35.0, "box_mult": 36.0, "donate": True},
    11:{"name": "⚱🦎Gold Spark GD🦎⚱", "cost": 0, "bonus_mult": 67.0, "box_mult": 89.0, "donate": True},
}

def get_status_info(status_id: int):
    return STATUSES.get(status_id, STATUSES[0])

async def get_user_status(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status_id FROM users WHERE user_id = ?", (user_id,))
    r = cursor.fetchone()
    close_db_connection(cursor)
    if r and r[0] is not None:
        return int(r[0])
    return 0

async def set_user_status(user_id: int, status_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, 0)", (user_id, ""))
    cursor.execute("UPDATE users SET status_id = ? WHERE user_id = ?", (status_id, user_id))
    conn.commit()
    close_db_connection(cursor)

# ----------------------------- Покупка статуса -----------------------------
@dp.message_handler(lambda m: m.text and m.text.lower().startswith("купить "))
async def buy_status_handler(message: types.Message):
    user_id = message.from_user.id
    if not await is_command_allowed(user_id):
        return
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.reply("Использование: купить <номер_статуса> (от 1 до 9).")
        return
    try:
        idx = int(parts[1])
    except ValueError:
        await message.reply("Неверный номер статуса.")
        return
    if idx not in STATUSES:
        await message.reply("Такого статуса нет.")
        return
    status = STATUSES[idx]
    if status.get("donate", False):
        await message.reply(
            "💎❌||Этот статус можно купить лишь донатом!\n——————————\n"
            "💠Хотите преобрести его?\nОбратитесь к —> @GodHandsRus",
            parse_mode=ParseMode.HTML
        )
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    if not res:
        await message.reply("Пользователь не найден в БД. Сначала выполните /start.")
        close_db_connection(cursor)
        return
    balance = res[0] or 0
    if balance < status["cost"]:
        close_db_connection(cursor)
        await message.reply("❌|| Не хватает средств для покупки статуса!")
        return
    cursor.execute("UPDATE users SET balance = balance - ?, status_id = ? WHERE user_id = ?", (status["cost"], idx, user_id))
    conn.commit()
    close_db_connection(cursor)
    await message.reply(f"✅||Вы успешно купили статус: {escape_html(status['name'])}", parse_mode=ParseMode.HTML)
    await update_last_command_time(user_id)

# ----------------------------- Выдача донат-статусов владельцем (/std) -----------------------------
@dp.message_handler(commands=["std"])
async def std_command(message: types.Message):
    sender_id = message.from_user.id  # ID того, кто отправил команду

    if sender_id not in OWNER_IDS:
        await message.reply("❌|| У вас нет прав на эту команду.")
        return

    args = message.get_args().split()
    if len(args) < 2:
        await message.reply("Использование: /std <user_id> <статус(10 или 11)>")
        return

    try:
        target_id = int(args[0])
        status_id = int(args[1])
    except ValueError:
        await message.reply("Неверные аргументы.")
        return

    if status_id not in STATUSES or not STATUSES[status_id].get("donate", False):
        await message.reply("Можно выдавать только донат статусы 10 или 11.")
        return

    await set_user_status(target_id, status_id)
    await message.reply(
        f"✅💎|| Пользователю {target_id} был выдан донат статус: {escape_html(STATUSES[status_id]['name'])}",
        parse_mode=ParseMode.HTML
    )

# ----------------------------- Команда бокс (3x3) -----------------------------
BOX_GAMES = {}  # user_id -> game dict
BOX_COOLDOWN_HOURS = 1
BOX_MIN_CLICK_INTERVAL = 2  # сек
BOX_WIN_CELLS = 3

def make_box_keyboard(game):
    kb = InlineKeyboardMarkup(row_width=3)
    btns = []
    for i in range(9):
        if i in game['opened']:
            if i in game['winning']:
                text = "🎁"
            else:
                text = "❌"
            btns.append(InlineKeyboardButton(text=text, callback_data="box_disabled"))
        else:
            btns.append(InlineKeyboardButton(text="❓", callback_data=f"box_open:{game['token']}:{i}"))
    for r in range(0, 9, 3):
        kb.row(btns[r], btns[r+1], btns[r+2])
    return kb

@dp.message_handler(Text(equals="бокс", ignore_case=True))
async def box_command(message: types.Message):
    user_id = message.from_user.id
    if message.chat.type != types.ChatType.PRIVATE:
        await message.reply("❌|| Бокс можно активировать только в личных сообщениях с ботом.")
        return
    if not await is_command_allowed(user_id):
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT last_box, status_id FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    close_db_connection(cursor)
    last_box_val, status_id = (res[0], res[1]) if res else (None, 0)
    if last_box_val:
        last_box_dt = datetime.fromisoformat(last_box_val)
        next_allowed = last_box_dt + timedelta(hours=BOX_COOLDOWN_HOURS)
        if datetime.now() < next_allowed:
            diff = next_allowed - datetime.now()
            hours = diff.seconds // 3600 + diff.days * 24
            minutes = (diff.seconds % 3600) // 60
            await message.reply(f"❌|| Следующий бокс будет через: {hours}ч. {minutes}мин. !")
            return
    token = str(uuid.uuid4())
    winning = set(random.sample(range(9), BOX_WIN_CELLS))
    game = {
        'token': token,
        'winning': winning,
        'opened': set(),
        'total': 0,
        'last_click': 0.0,
        'message_id': None,
        'chat_id': message.chat.id,
        'status_id': status_id
    }
    BOX_GAMES[user_id] = game
    header = ""
    if status_id and status_id in STATUSES:
        box_mult = get_status_info(status_id)["box_mult"]
        header = (f"🌠||Ваш статус был задействован!\n🚀Буст бокса: {box_mult}х\n——————————\n")
    main_text = f"{header}📦Снизу предоставлены ячейки, откройте всего 3 чтобы узнать свой выйгрыш!👇"
    kb = make_box_keyboard(game)
    sent = await message.reply(main_text, reply_markup=kb, parse_mode=ParseMode.HTML)
    game['message_id'] = sent.message_id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, 0)", (user_id, ""))
    cursor.execute("UPDATE users SET last_box = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
    conn.commit()
    close_db_connection(cursor)
    await update_last_command_time(user_id)

@dp.callback_query_handler(lambda c: c.data.startswith("box_open:"))
async def box_open_callback(callback_query: CallbackQuery):
    parts = callback_query.data.split(":")
    if len(parts) != 3:
        await callback_query.answer()
        return
    token = parts[1]
    try:
        idx = int(parts[2])
    except ValueError:
        await callback_query.answer()
        return
    user_id = callback_query.from_user.id
    if user_id not in BOX_GAMES:
        await callback_query.answer("❌|| У вас нет активного бокса.", show_alert=True)
        return
    game = BOX_GAMES[user_id]
    if token != game['token']:
        await callback_query.answer("❌|| Это не ваш бокс.", show_alert=True)
        return
    now_ts = time.time()
    if now_ts - game['last_click'] < BOX_MIN_CLICK_INTERVAL:
        await callback_query.answer("❌|| Не так быстро!", show_alert=True)
        return
    game['last_click'] = now_ts
    if idx in game['opened']:
        await callback_query.answer("Эта ячейка уже открыта.")
        return
    game['opened'].add(idx)
    prize_amount = 0
    if idx in game['winning']:
        base_win = random.randint(10000, 35000)  # от 1000 до 5000
        status_mult = get_status_info(game.get('status_id', 0))["box_mult"]
        prize_amount = int(math.floor(base_win * status_mult))
        game['total'] += prize_amount
    kb = make_box_keyboard(game)
    opened_count = len(game['opened'])
    total_formatted = format_balance(game['total'])
    header = ""
    if game.get('status_id') and game['status_id'] in STATUSES:
        box_mult = get_status_info(game['status_id'])["box_mult"]
        header = (f"🌠||Ваш статус был задействован!\n🚀Буст бокса: {box_mult}х\n——————————\n")
    current_text = (f"{header}"
                    f"💰Ваш выйгрыш с бокса: {total_formatted} Spark🦎\n"
                    f"📦Открыто ячеек: {opened_count}/3")
    try:
        await bot.edit_message_text(current_text, chat_id=game['chat_id'], message_id=game['message_id'], reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        pass
    await callback_query.answer()
    if opened_count >= 3:
        if game['total'] > 0:
            formatted = format_balance(game['total'])
            final_text = f"🎉Вы получили: {formatted} Spark🦎"
        else:
            final_text = "♨️ К сожалению вы нечего не получили с бокса!"
        try:
            await bot.edit_message_text(final_text, chat_id=game['chat_id'], message_id=game['message_id'], reply_markup=None, parse_mode=ParseMode.HTML)
        except Exception:
            pass
        if game['total'] > 0:
            await update_user_balance(user_id, game['total'])
        del BOX_GAMES[user_id]

@dp.callback_query_handler(lambda c: c.data == "box_disabled")
async def box_disabled_handler(callback_query: CallbackQuery):
    await callback_query.answer()


FOOTBALL_MULTIPLIER_WIN = 1.6
FOOTBALL_MULTIPLIER_LOSE = 2.3
MIN_FOOTBALL_STAKE = 100
FOOTBALL_ANIMATION_WIN_VALUES = [3, 4, 5]
FOOTBALL_ANIMATION_LOSE_VALUES = [1, 2]
CURRENCY_EMOJI_L = "Spark🦎"

football_games = {}

class FootballState(StatesGroup):
    waiting_for_choice = State()

@dp.message_handler(Text(startswith=["футбол", "/football"], ignore_case=True), state="*")
async def football_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    try:
        if await is_user_banned(user_id):
            return await message.reply("🚫 Вы были забанены и не можете играть!")
    except Exception:
        # Если is_user_banned не определена или упала — пропускаем проверку
        pass

    parts = message.text.split()
    if len(parts) != 2:
        return await message.reply("❌ Неверный формат! Используй: футбол (ставка)")

    amount_str = parts[1]
    balance = await get_user_balance(user_id)

    if amount_str.lower() == "все":
        amount = balance
        if amount <= 0:
            return await message.reply("❌ Недостаточно средств на балансе!")
    else:
        amount = format_stake(amount_str)
        if amount is None:
            return await message.reply("❌ Неверный формат! Используй: футбол 1к или 1кк итд.")
        try:
            amount = int(amount)
        except ValueError:
            return await message.reply("❌ Неверный формат суммы!")

    if amount < MIN_FOOTBALL_STAKE:
        return await message.reply(f"❌ Минимальная ставка: {MIN_FOOTBALL_STAKE}")

    if amount <= 0:
        return await message.reply("❌ Ставка должна быть больше нуля!")

    if balance < amount:
        formatted_balance = format_balance(balance)
        return await message.reply(f"❌ Недостаточно средств на балансе! Ваш баланс: {formatted_balance}")

    # Списываем ставку
    await update_user_balance(user_id, -amount)

    # Сохраняем данные в state
    await state.update_data(stake=amount, message_id=message.message_id, chat_id=message.chat.id, user_id=user_id)
    text = (
        "🌐Параметры исхода:\n\n"
        f"✅Забил✅ — {FOOTBALL_MULTIPLIER_WIN}x к выигрышу\n"
        f"❌Не забил❌ — {FOOTBALL_MULTIPLIER_LOSE}x к выигрышу\n\n"
        f"<code>————————————</code>\n"
        "⚽️|| Выберите исход футбольного мяча:"
    )

    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(text="Забил⚽️✅", callback_data=f"football_choice_win|{user_id}"),
        types.InlineKeyboardButton(text="Не забил⚽️❌", callback_data=f"football_choice_lose|{user_id}")
    )

    sent_message = await message.reply(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await state.update_data(keyboard_message_id=sent_message.message_id)
    await FootballState.waiting_for_choice.set()

@dp.callback_query_handler(Text(startswith="football_choice_"), state=FootballState.waiting_for_choice)
async def football_choice_made(call: types.CallbackQuery, state: FSMContext):
    # callback data формат: football_choice_win|<user_id>
    try:
        parts = call.data.split("|")
        callback_key = parts[0]  # football_choice_win или football_choice_lose
        user_id_from_callback = int(parts[1])
        choice = callback_key.split("_")[2]  # win или lose
    except Exception:
        return await call.answer("Некорректные данные кнопки", show_alert=True)

    user_id = call.from_user.id
    if user_id != user_id_from_callback:
        return await call.answer("❌ Эта ставка не для вас!", show_alert=True)

    if str(user_id) in football_games:
        return await call.answer("‼️|| Вы уже сделали выбор!", show_alert=True)

    football_games[str(user_id)] = True

    data = await state.get_data()
    stake = data.get('stake')
    chat_id = data.get('chat_id')
    initial_user_id = data.get('user_id')
    keyboard_message_id = data.get('keyboard_message_id')

    if not stake:
        football_games.pop(str(user_id), None)
        await state.finish()
        return await call.answer("Ошибка: Не удалось получить размер ставки.", show_alert=True)

    # Удаляем inline сообщение с кнопками, если возможно
    try:
        await bot.delete_message(chat_id, keyboard_message_id)
    except Exception:
        # не критично
        pass

    # Отправляем бросок мяча
    sent_dice = await bot.send_dice(chat_id, emoji="⚽")
    await asyncio.sleep(4)

    # Обрабатываем результат (process_football_result обновит статистику)
    try:
        await process_football_result(sent_dice, user_id, stake, choice, data)
    finally:
        football_games.pop(str(user_id), None)
        await state.finish()

async def process_football_result(message: types.Message, user_id: int, stake: int, choice: str, data: dict):
    dice_value = getattr(message.dice, "value", None)
    if dice_value is None:
        # Защитная проверка
        dice_value = 0

    won = False
    if choice == "win" and dice_value in FOOTBALL_ANIMATION_WIN_VALUES:
        won = True
    elif choice == "lose" and dice_value in FOOTBALL_ANIMATION_LOSE_VALUES:
        won = True

    initial_user_id = data['user_id']
    try:
        user = await bot.get_chat(initial_user_id)
        username = html.escape(user.first_name or user.username or "User")
    except Exception:
        username = "User"
    profile_link = f"tg://user?id={initial_user_id}"
    user_link = f'<a href="{profile_link}">{username}</a>'

    formatted_stake = format_balance(stake)

    if won:
        if choice == "win":
            chosen_result = bold("Забил⚽️✅")
            game_result = bold("Забил⚽️✅")
            win_amount = int(stake * FOOTBALL_MULTIPLIER_WIN)
        else:
            chosen_result = bold("Не забил⚽️❌")
            game_result = bold("Не забил⚽️❌")
            win_amount = int(stake * FOOTBALL_MULTIPLIER_LOSE)

        formatted_win_amount = format_balance(win_amount)
        result_text = (
            f"🎮|| {user_link}, ваши итоги игры:\n\n"
            f"🎯||Ваш выбор:\n   <b>{chosen_result}</b>\n"
            f"⚽️||Итог игры:\n   <b>{game_result}</b>\n"
            f"<code>————————————</code>\n"
            f"💰||Ваша ставка:\n   <b>{formatted_stake}</b> {CURRENCY_EMOJI_L}\n"
            f"<code>————————————</code>\n"
            f"🎉||Выигрыш:\n   +<b>{formatted_win_amount}</b> {CURRENCY_EMOJI_L}"
        )

        # начисляем выигрыш на баланс и обновляем статистику
        try:
            await update_user_balance(user_id, win_amount)  # зачисляем выигрыш
        except Exception:
            logging.exception("Ошибка при зачислении выигрыша пользователю")

        try:
            await increment_games_played(user_id, 1)        # +1 сыграно
            await add_win_record(user_id, int(win_amount))  # фиксируем выигрыш
        except Exception:
            logging.exception("Ошибка при обновлении статистики после выигрыша")

    else:
        if choice == "win":
            chosen_result = bold("Забил⚽️✅")
            game_result = bold("Не забил⚽️❌")
        else:
            chosen_result = bold("Не забил⚽️❌")
            game_result = bold("Забил⚽️✅")

        result_text = (
            f"🎮|| {user_link}, ваши итоги игры:\n\n"
            f"🎯||Ваш выбор:\n   <b>{chosen_result}</b>\n"
            f"⚽️||Итог игры:\n   <b>{game_result}</b>\n"
            f"<code>————————————</code>\n"
            f"💰||Ваша ставка:\n   <b>{formatted_stake}</b> {CURRENCY_EMOJI_L}\n"
            f"<code>————————————</code>\n"
            f"❌||Проигрыш:\n   <b>{formatted_stake}</b> {CURRENCY_EMOJI_L}"
        )

        # обновляем статистику проигрыша: gamep +1, losp += stake
        try:
            await increment_games_played(user_id, 1)
            await add_loss_record(user_id, int(stake))
        except Exception:
            logging.exception("Ошибка при обновлении статистики после поражения")

    # Отправляем итог игроку
    try:
        await message.reply(result_text, parse_mode=ParseMode.HTML)
    except Exception:
        # Если ответ не удался, пробуем отправить в чат напрямую
        try:
            await bot.send_message(message.chat.id, result_text, parse_mode=ParseMode.HTML)
        except Exception:
            logging.exception("Не удалось отправить результат игры пользователю")



# Конфигурация игры
HACKER_LEVELS = 5
HACKER_MULTIPLIERS = [1.13, 1.55, 2.7, 4.0, 4.8]
HACKER_WIN_CHANCES = [0.7, 0.5, 0.3, 0.2, 0.1]  # шансы успеха
WITHDRAW_FEE = 0.08  # 8% комиссия за вывод при досрочном заборе
CURRENCY_NAME = "Spark🦎"
CURRENCY_EMOJI = "Spark🦎"
CLICK_COOLDOWN_SECONDS = 2  # не больше 1 клика за 2 секунды

# Эмодзи
BTC_EMOJI = "💎"
VIRUS_EMOJI = "🦠"
LOCKED_EMOJI = "🔒"
PASSED_EMOJI = "💎"
LEVEL_EMOJIS = ["1⃣", "2⃣", "3⃣", "4⃣", "5⃣"]

# Словарь активных игр: owner_id -> game_data
hacker_games = {}

def format_money_html(amount: int) -> str:
    """
    Форматирует сумму для HTML-вывода: число в жирном и эмодзи валюты.
    Экранируем вывод для безопасности.
    """
    try:
        amount = int(amount)
    except Exception:
        amount = 0
    return f"<b>{html.escape(format_balance(amount))}</b> {html.escape(CURRENCY_EMOJI)}"


def build_levels_keyboard(owner_id: int, current_level_index: int):
    """
    Строит клавиатуру уровней в нужной раскладке.
    callback_data содержит owner_id для проверки владельца.
    """
    kb = types.InlineKeyboardMarkup(row_width=2)

    def btn_text_cb(idx):
        if current_level_index >= idx:
            return f"{LEVEL_EMOJIS[idx]} Уровень {idx + 1}", f"hacker_level_{idx+1}_{owner_id}"
        else:
            return f"{LOCKED_EMOJI} Уровень {idx + 1}", f"hacker_locked_{owner_id}"

    # динамически формируем кнопки
    buttons = []
    for i in range(HACKER_LEVELS):
        t, c = btn_text_cb(i)
        buttons.append(types.InlineKeyboardButton(text=t, callback_data=c))

    # раскладка 2+2+1
    if len(buttons) >= 2:
        kb.add(buttons[0], buttons[1])
    if len(buttons) >= 4:
        kb.add(buttons[2], buttons[3])
    if len(buttons) >= 5:
        kb.add(buttons[4])

    return kb


async def send_hacker_main_message(chat, owner_id, edit_message=None):
    """Отправляет или редактирует главное сообщение игры."""
    game = hacker_games[owner_id]
    username = html.escape(game["username"])
    current_level_display = game["current_level"] + 1  # 1-based
    stake = game["stake"]
    multiplier = game["current_multiplier"]
    potential_win = int(stake * multiplier)

    stake_html = format_money_html(stake)
    potential_html = format_money_html(potential_win)

    text = (
        f"<b>💻 КРИПТО-ХАКЕР</b>\n\n"
        f"🎯 Текущий уровень: {current_level_display}/{HACKER_LEVELS}\n"
        f"💰 Текущая ставка:\n{stake_html}\n"
        f"📊 Коэффициент: {multiplier:.2f}x\n"
        f"🎯 Потенциальный выигрыш:\n+{potential_html}\n\n"
        f"Выбери уровень для взлома:\n"
        f"{BTC_EMOJI} BTC - Увеличит твой выигрыш!\n"
        f"{VIRUS_EMOJI} VIRUS - Заблокирует кошелёк!\n\n"
        f"💡 Шансы успеха по уровням:\n"
        f"• Уровень 1: {int(HACKER_WIN_CHANCES[0]*100)}% успеха ({HACKER_MULTIPLIERS[0]:.2f}x)\n"
        f"• Уровень 2: {int(HACKER_WIN_CHANCES[1]*100)}% успеха ({HACKER_MULTIPLIERS[1]:.2f}x)\n"
        f"• Уровень 3: {int(HACKER_WIN_CHANCES[2]*100)}% успеха ({HACKER_MULTIPLIERS[2]:.2f}x)\n"
        f"• Уровень 4: {int(HACKER_WIN_CHANCES[3]*100)}% успеха ({HACKER_MULTIPLIERS[3]:.2f}x)\n"
        f"• Уровень 5: {int(HACKER_WIN_CHANCES[4]*100)}% успеха ({HACKER_MULTIPLIERS[4]:.2f}x)\n\n"
        f"⚡ Риск растёт с каждым уровнем!"
    )

    kb = build_levels_keyboard(owner_id, game["current_level"])

    if edit_message:
        try:
            await edit_message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
            game["message_id"] = edit_message.message_id
        except Exception:
            logging.exception("Ошибка при редактировании сообщения игры Хакер")
            # в случае ошибки отправим новое сообщение
            sent = await chat.reply(text, reply_markup=kb, parse_mode=ParseMode.HTML)
            game["message_id"] = sent.message_id
    else:
        sent = await chat.reply(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        game["message_id"] = sent.message_id


async def start_hacker_play(message: types.Message, stake_amount: int):
    """Инициализация новой игры."""
    owner_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    username = username.replace("@", "")

    hacker_games[owner_id] = {
        "owner_id": owner_id,
        "username": username,
        "stake": stake_amount,
        "current_level": 0,  # 0-based index (первый уровень доступен)
        # теперь current_multiplier — ровно множитель выбранного пройденного уровня или 1.0 если ничего не пройдено
        "current_multiplier": 1.00,
        "current_win": stake_amount,  # начальный потенциальный выигрыш = ставка * 1.0
        "history": [],  # список строк истории "Уровень i: BTC/VIRUS"
        "message_id": None,
        "last_click_ts": 0.0,  # для ограничения кликов
        "lock": asyncio.Lock()
    }

    await send_hacker_main_message(message, owner_id)


async def _acquire_click(game) -> bool:
    """
    Атомарно проверяет и обновляет метку последнего клика.
    Возвращает True — если клик можно обработать, False — если слишком быстро.
    Важно: вызывается в обработчиках до выполнения действий.
    """
    async with game["lock"]:
        now = time.time()
        last = game.get("last_click_ts", 0)
        if now - last < CLICK_COOLDOWN_SECONDS:
            # слишком быстро, отменяем
            return False
        # разрешаем и помечаем время
        game["last_click_ts"] = now
        return True


async def _process_level_result(call: types.CallbackQuery, owner_id: int, level: int):
    """Обработка результата выбора уровня (BTC или VIRUS)."""
    game = hacker_games.get(owner_id)
    if not game:
        await call.answer("Игра не найдена или уже завершена!", show_alert=True)
        return

    # проверка права на нажатие
    if call.from_user.id != owner_id:
        await call.answer("❌ Эта кнопка не для тебя!", show_alert=True)
        return

    # rate limit: атомарно
    if not await _acquire_click(game):
        await call.answer("❌|| Не так быстро!", show_alert=True)
        return

    # Проводим попытку взлома
    chance = HACKER_WIN_CHANCES[level - 1]
    rnd = random.random()
    if rnd < chance:
        # Успех — BTC
        m = HACKER_MULTIPLIERS[level - 1]
        # устанавливаем точный множитель уровня (не накапливаем)
        game["current_multiplier"] = float(m)
        game["current_win"] = int(game["stake"] * game["current_multiplier"])
        game["history"].append(f"Уровень {level}: {BTC_EMOJI} BTC")

        stake_html = format_money_html(game["stake"])
        win_html = format_money_html(game["current_win"])

        text = (
            f"<b>{BTC_EMOJI} BTC - УСПЕХ!</b>\n\n"
            f"🎯 Уровень {level} взломан!\n"
            f"💰 Исходная ставка:\n{stake_html}\n"
            f"📊 Коэффициент: {game['current_multiplier']:.2f}x\n"
            f"💸 Текущий выигрыш:\n+{win_html}\n\n"
            f"Продолжаем взлом?"
        )

        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton(text="🎯 Следующий уровень", callback_data=f"hacker_continue_{owner_id}"),
            types.InlineKeyboardButton(text="💰 Забрать выигрыш", callback_data=f"hacker_take_{owner_id}")
        )
        try:
            await call.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except Exception:
            # если редактирование не удалось — отправим новое сообщение
            await call.message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        # Провал — VIRUS
        game["history"].append(f"Уровень {level}: {VIRUS_EMOJI} VIRUS")
        stake_html = format_money_html(game["stake"])
        text = (
            f"<b>{VIRUS_EMOJI} VIRUS - ПРОВАЛ!</b>\n\n"
            f"💻 СИСТЕМА ЗАБЛОКИРОВАНА!\n"
            f"🎯 Уровень {level} содержал вирус!\n\n"
            f"🕹 ИГРА ОКОНЧЕНА!\n"
            f"💸 Проигрыш:\n{stake_html}"
        )
        try:
            await call.message.edit_text(text, reply_markup=None, parse_mode=ParseMode.HTML)
        except Exception:
            await call.message.answer(text, parse_mode=ParseMode.HTML)
        # обновляем статистику: +1 игра, +проигрыш
        try:
            await increment_games_played(owner_id, 1)
            await add_loss_record(owner_id, int(game["stake"]))
        except Exception:
            logging.exception("Ошибка при обновлении статистики после поражения")
        # удаляем игру
        try:
            del hacker_games[owner_id]
        except KeyError:
            pass


# Обработчик команды /хакер
@dp.message_handler(Text(startswith=["хакер", "/hacker"], ignore_case=True))
async def hacker_command(message: types.Message):
    user_id = message.from_user.id

    # проверка бана
    try:
        if await is_user_banned(user_id):
            await message.reply("🚫 Вы были забанены и не можете играть!")
            return
    except Exception:
        # если функция is_user_banned не определена — пропускаем проверку
        pass

    parts = message.text.split()
    if len(parts) != 2:
        await message.reply("❌ Неверный формат! Используй: хакер (ставка)")
        return

    amount_str = parts[1]
    balance = await get_user_balance(user_id)
    formatted_balance = format_balance(balance)

    # обработка "все"
    if amount_str.lower() == "все":
        amount = balance
        if amount <= 0:
            await message.reply("❌ Недостаточно средств на балансе!")
            return
    else:
        amount = format_stake(amount_str)
        if amount is None:
            await message.reply("❌ Неверный формат! Используй: хакер 1к или 1кк итд.")
            return
        try:
            amount = int(amount)
        except Exception:
            await message.reply("❌ Неверный формат суммы!")
            return

    if amount <= 0:
        await message.reply("❌ Ставка должна быть больше нуля!")
        return

    if balance < amount:
        await message.reply(f"❌ Недостаточно средств на балансе! Ваш баланс: {formatted_balance}", parse_mode=ParseMode.HTML)
        return

    # списываем ставку
    await update_user_balance(user_id, -amount)

    # стартуем игру
    await start_hacker_play(message, amount)


# Нажатие на уровень: hacker_level_{level}_{owner_id}
@dp.callback_query_handler(Text(startswith="hacker_level_"))
async def on_hacker_level(call: types.CallbackQuery):
    try:
        parts = call.data.split("_")
        level = int(parts[2])
        owner_id = int(parts[3])
    except Exception:
        await call.answer("Некорректные данные кнопки", show_alert=True)
        return

    game = hacker_games.get(owner_id)
    if not game:
        await call.answer("Игра не найдена или закончена!", show_alert=True)
        return

    if call.from_user.id != owner_id:
        await call.answer("❌ Эта кнопка не для тебя!", show_alert=True)
        return

    # проверяем, дошёл ли игрок до этого уровня
    if level - 1 > game["current_level"]:
        await call.answer("❌|| Вы не дошли до этого уровня!", show_alert=True)
        return

    # если уровень уже пройден
    if level - 1 < game["current_level"]:
        await call.answer("✅ Этот уровень уже пройден!", show_alert=True)
        return

    # теперь проверка частоты нажатий производится в _process_level_result через _acquire_click
    await _process_level_result(call, owner_id, level)


# Нажатие на заблокированный уровень
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("hacker_locked_"))
async def on_hacker_locked(call: types.CallbackQuery):
    try:
        owner_id = int(call.data.split("_")[2])
    except Exception:
        await call.answer("Некорректные данные кнопки", show_alert=True)
        return

    game = hacker_games.get(owner_id)
    if not game:
        await call.answer("Игра не найдена или закончена!", show_alert=True)
        return

    if call.from_user.id != owner_id:
        await call.answer("❌ Эта кнопка не для тебя!", show_alert=True)
        return

    await call.answer("❌|| Вы не дошли до этого уровня!", show_alert=True)


# Продолжить: hacker_continue_{owner_id}
@dp.callback_query_handler(Text(startswith="hacker_continue_"))
async def on_hacker_continue(call: types.CallbackQuery):
    try:
        owner_id = int(call.data.split("_")[2])
    except Exception:
        await call.answer("Некорректные данные кнопки", show_alert=True)
        return

    game = hacker_games.get(owner_id)
    if not game:
        await call.answer("Игра не найдена или закончена!", show_alert=True)
        return

    if call.from_user.id != owner_id:
        await call.answer("❌ Эта кнопка не для тебя!", show_alert=True)
        return

    # проверяем частоту нажатий атомарно
    if not await _acquire_click(game):
        await call.answer("❌|| Не так быстро!", show_alert=True)
        return

    # даём доступ к следующему уровню
    if game["current_level"] < HACKER_LEVELS - 1:
        game["current_level"] += 1
        try:
            await send_hacker_main_message(call.message, owner_id, edit_message=call.message)
        except Exception:
            await send_hacker_main_message(call.message, owner_id, edit_message=None)
    else:
        # все лвлы пройдены — победа с комиссией 0%
        final_win = game["current_win"]
        await update_user_balance(owner_id, final_win)

        # обновляем статистику: +1 игра, +выигрыш
        try:
            await increment_games_played(owner_id, 1)
            await add_win_record(owner_id, int(final_win))
        except Exception:
            logging.exception("Ошибка при обновлении статистики после полной победы")

        stake_html = format_money_html(game["stake"])
        win_html = format_money_html(final_win)

        text = (
            f"<b>🏆💎 КОМПЬЮТЕР ВЗЛОМАН!</b>\n\n"
            f"💻 Все уровни взломаны!\n"
            f"💰 Исходная ставка:\n{stake_html}\n"
            f"📊 Финальный коэффициент: {game['current_multiplier']:.2f}x\n"
            f"💸🏷 Комиссия за вывод: 0%\n"
            f"🎯 Выигрыш:\n+{win_html}\n\n"
            f"📊 ИСТОРИЯ ВЗЛОМОВ:\n\n"
            f"{BTC_EMOJI}| Все уровни пройдены |{BTC_EMOJI}"
        )
        try:
            await call.message.edit_text(text, reply_markup=None, parse_mode=ParseMode.HTML)
        except Exception:
            await call.message.answer(text, parse_mode=ParseMode.HTML)
        try:
            del hacker_games[owner_id]
        except KeyError:
            pass


# Забрать: hacker_take_{owner_id}
@dp.callback_query_handler(Text(startswith="hacker_take_"))
async def on_hacker_take(call: types.CallbackQuery):
    try:
        owner_id = int(call.data.split("_")[2])
    except Exception:
        await call.answer("Некорректные данные кнопки", show_alert=True)
        return

    game = hacker_games.get(owner_id)
    if not game:
        await call.answer("Игра не найдена или закончена!", show_alert=True)
        return

    if call.from_user.id != owner_id:
        await call.answer("❌ Эта кнопка не для тебя!", show_alert=True)
        return

    # проверяем частоту нажатий атомарно
    if not await _acquire_click(game):
        await call.answer("❌|| Не так быстро!", show_alert=True)
        return

    win = game["current_win"]
    fee = int(win * WITHDRAW_FEE)
    final = win - fee

    await update_user_balance(owner_id, final)

    # обновляем статистику: +1 игра, +выигрыш (записываем ту сумму, которая была начислена на баланс)
    try:
        await increment_games_played(owner_id, 1)
        await add_win_record(owner_id, int(final))
    except Exception:
        logging.exception("Ошибка при обновлении статистики после забора выигрыша")

    stake_html = format_money_html(game["stake"])
    win_html = format_money_html(win)
    final_html = format_money_html(final)
    fee_percent = int(WITHDRAW_FEE * 100)

    history_lines = "\n".join(game["history"]) if game["history"] else "—"

    text = (
        f"<b>💰 ВЫВОД УСПЕШЕН!</b>\n\n"
        f"💻 Взломанных уровней: {len(game['history'])}\n"
        f"💰 Исходная ставка:\n{stake_html}\n"
        f"📊 Финальный коэффициент: {game['current_multiplier']:.2f}x\n"
        f"💸🏷 Комиссия за вывод: {fee_percent}%\n"
        f"🎯 Выигрыш:\n+{final_html}\n\n"
        f"📊 ИСТОРИЯ ВЗЛОМОВ:\n{history_lines}"
    )

    try:
        await call.message.edit_text(text, reply_markup=None, parse_mode=ParseMode.HTML)
    except Exception:
        await call.message.answer(text, parse_mode=ParseMode.HTML)

    try:
        del hacker_games[owner_id]
    except KeyError:
        pass



# Константы
GAMES = {}
USER_CD = {}
COOLDOWN = 2  # секунды
PASS_CHANCE = 0.6  # Вероятность, что клетка не будет миной

# Множители для каждого уровня сложности (количество мин)
multipliers = {
    1: [1.09, 1.14, 1.27, 1.43, 1.78, 2.03, 2.44, 2.89, 3.21, 4],
    2: [1.18, 1.29, 1.78, 2.11, 2.68, 3.49, 4.11, 4.59, 5.49, 6]
}


# Генерация всей клавиатуры (с блокировкой старых рядов и проверкой владельца)
def get_full_keyboard(user_id):
    game = GAMES[user_id]
    keyboard = types.InlineKeyboardMarkup(row_width=3)

    last_row_idx = len(game["cells"]) - 1  # активный ряд (последний)

    for row_idx, row in enumerate(game["cells"]):
        buttons = []
        for cell_idx, cell in enumerate(row):
            if cell["opened"]:
                text = "💥" if cell["mine"] else "💎"
                callback = None
            else:
                text = "❔"
                # Если это текущий ряд, кнопка активна только для владельца
                if row_idx == last_row_idx:
                    callback = f"diamonds_cell_{row_idx}_{cell_idx}_{user_id}"
                else:
                    callback = f"diamonds_disabled_{row_idx}_{cell_idx}_{user_id}"

            buttons.append(types.InlineKeyboardButton(
                text=text,
                callback_data=callback if callback else "ignore"
            ))
        keyboard.add(*buttons)

    # Добавляем кнопку отмены или забрать выигрыш
    if len(game["cells"]) == 1 and not any(c["opened"] for c in game["cells"][0]):
        keyboard.add(types.InlineKeyboardButton(
            text="🚫 Отменить игру",
            callback_data=f"diamonds_cancel_{user_id}"
        ))
    else:
        keyboard.add(types.InlineKeyboardButton(
            text="💰 Забрать выигрыш",
            callback_data=f"diamonds_take_{user_id}"
        ))

    return keyboard


# -------------------
# Проверка cooldown
# -------------------
def check_cd(user_id):
    now = datetime.now()
    if user_id in USER_CD and now < USER_CD[user_id]:
        return False
    USER_CD[user_id] = now + timedelta(seconds=COOLDOWN)
    return True


# Создание ряда с учётом выбранного числа мин
def create_row(num_mines: int):
    row = [{"mine": False, "opened": False} for _ in range(3)]
    # Уменьшаем шанс, что клетка будет проходной (увеличиваем шанс мины)
    num_safe = 3 - num_mines
    safe_indexes = random.sample(range(3), num_safe)  # Выбираем индексы безопасных клеток

    for idx in range(3):
        if idx not in safe_indexes:  # Если индекс не в списке безопасных, ставим мину
            row[idx]["mine"] = True

    return row


# старт игры
@dp.message_handler(Text(startswith=["алмазы", "/daimond"], ignore_case=True))
async def diamonds_game(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    username = username.replace("@", "")

    # Проверка на бан
    try:
        if await is_user_banned(user_id):
            await message.reply("🚫 Вы были забанены и не можете играть!")
            return
    except Exception:
        pass

    # Получаем баланс пользователя
    balance = await get_user_balance(user_id)
    formatted_balance = format_balance(balance) # форматируем баланс

    # Разбираем аргументы команды
    parts = message.text.split()
    if len(parts) != 2:
        await message.reply("❌ Неверный формат! Используй: алмазы (ставка)")
        return

    amount_str = parts[1]

    # Обрабатываем ставку "все"
    if amount_str.lower() == "все":
        amount = balance
        if amount <= 0:
            await message.reply("❌ Недостаточно средств на балансе!")
            return
    else:
        amount = format_stake(amount_str)
        if amount is None:
            await message.reply("❌ Неверный формат! Используй: алмазы 1к или 1кк итд.")
            return
        try:
            amount = int(amount)  # Преобразуем в целое число
        except ValueError:
            await message.reply("❌ Неверный формат суммы!")
            return

    # Проверяем баланс
    if balance < amount:
        await message.reply(text=f"❌ Недостаточно средств на балансе! Ваш баланс: {formatted_balance}", parse_mode=ParseMode.HTML)
        return

    # Списываем ставку с баланса
    await update_user_balance(user_id, -amount)

    # Инициализируем игру
    GAMES[user_id] = {
        "username": username,
        "stake": amount,
        "win": 0,
        "stage": "choose_mines"
    }

    # Создаем клавиатуру для выбора количества мин
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for i in range(1, 3):
        keyboard.insert(types.InlineKeyboardButton(
            text=f"{i} мины 💣",
            callback_data=f"diamonds_mines_{i}_{user_id}"
        ))

    sent_msg = await message.reply(
        text=f"<b>💎|| {username}</b>, вы поставили:\n<b>{format_balance(amount)}</b> Spark🦎.\n"
             "<code>·····················</code>\n"
             "<b>📌|| Выберите кол-во мин на поле:</b>",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    GAMES[user_id]["message_id"] = sent_msg.message_id


# Отмена игры (первый вариант)
@dp.callback_query_handler(Text(startswith="diamonds_cancel_"))
async def cancel_game(call: types.CallbackQuery):
    _, _, user_id = call.data.split("_")
    user_id = int(user_id)

    if call.from_user.id != user_id:
        await call.answer("❌ Эта кнопка не для тебя!", show_alert=True)
        return

    if user_id not in GAMES:
        await call.answer("❌ Игра не найдена или уже отменена!", show_alert=True)
        return

    game = GAMES[user_id]

    if call.message.message_id != game.get("message_id"):
        await call.answer("❌ Эта кнопка уже использована!", show_alert=True)
        return

    stake = game["stake"]
    await update_user_balance(user_id, stake)

    del GAMES[user_id]

    await call.message.edit_text(
        text=f"❌|| Игра отменена.\n\n<b>💸||Ставка:</b>\n<b>{format_balance(stake)}</b> Spark🦎 возвращена!",
        reply_markup=None,
        parse_mode=ParseMode.HTML
    )


# Выбор количества мин
@dp.callback_query_handler(Text(startswith="diamonds_mines_"))
async def choose_mines(call: types.CallbackQuery):
    _, _, num_mines, user_id = call.data.split("_")
    user_id = int(user_id)
    num_mines = int(num_mines)

    if call.from_user.id != user_id:
        await call.answer("❌ Эта кнопка не для тебя!", show_alert=True)
        return

    if user_id not in GAMES:
        await call.answer("❌ Игра не найдена", show_alert=True)
        return

    game = GAMES[user_id]
    game["num_mines"] = num_mines
    game["cells"] = [create_row(num_mines)]
    game["stage"] = "play"
    game["win"] = game["stake"]
    row_number = 1
    username = game["username"]

    text = (
        f"<b>💎|| {username}</b>, теперь можешь выбрать ячейку!\n"
        f"<code>·····················</code>\n"
        f"<b>💸|| Ставка:</b>\n<b>{format_balance(game['stake'])}</b> Spark🦎\n"
        f"<code>·····················</code>\n"
        f"<b>🪜|| Ряд {row_number} из 10</b>\n"
        f"<code>·····················</code>\n"
        f"<b>📈|| Множитель:</b> x1\n"
        f"<code>·····················</code>\n"
        f"<b>💰|| Текущий выигрыш:</b>\n<b>+{format_balance(game['win'])}</b> Spark🦎"
    )

    sent_msg = await call.message.edit_text(
        text=text,
        reply_markup=get_full_keyboard(user_id),
        parse_mode=ParseMode.HTML
    )
    game["message_id"] = sent_msg.message_id


# Клик по ячейке
@dp.callback_query_handler(Text(startswith="diamonds_cell_"))
async def click_cell(call: types.CallbackQuery):
    _, _, row_idx, cell_idx, game_user_id = call.data.split("_")
    row_idx, cell_idx, game_user_id = int(row_idx), int(cell_idx), int(game_user_id)

    if call.from_user.id != game_user_id:
        await call.answer("❌ Эта кнопка не для тебя!", show_alert=True)
        return

    if game_user_id not in GAMES:
        await call.answer("❌ Игра не найдена", show_alert=True)
        return

    if not check_cd(game_user_id):
        await call.answer("⏱ Подожди немного перед следующим ходом!", show_alert=True)
        return

    game = GAMES[game_user_id]
    username = game["username"]

    if row_idx != len(game["cells"]) - 1:
        await call.answer("Этот ряд уже пройден ✅", show_alert=True)
        return

    cell = game["cells"][row_idx][cell_idx]
    if cell["opened"]:
        await call.answer("Эта ячейка уже открыта!", show_alert=True)
        return

    cell["opened"] = True

    if cell["mine"]:
        text = f"<b>💢💎|| {username}</b>, ты наткнулся на мину и проиграл!\n\n<b>💸|| Ставка:</b>\n<b>{format_balance(game['stake'])}</b> Spark🦎"
        try:
            await call.message.edit_text(text=text, reply_markup=None, parse_mode=ParseMode.HTML)
        except Exception:
            await asyncio.sleep(1)
            await call.message.edit_text(text=text, reply_markup=None, parse_mode=ParseMode.HTML)
        # обновляем статистику: +1 игра, +проигрыш
        try:
            await increment_games_played(game_user_id, 1)
            await add_loss_record(game_user_id, int(game["stake"]))
        except Exception:
            logging.exception("Ошибка при обновлении статистики после поражения в алмазах")
        del GAMES[game_user_id]
        return

    row_number = len(game["cells"])
    multiplier = multipliers[game["num_mines"]][row_number - 1]
    win = int(game["stake"] * multiplier)  # Убираем копейки, округляя до целого

    game["win"] = win

    if row_number < 10:
        new_row = create_row(game["num_mines"])
        game["cells"].append(new_row)
        text = (
            f"<b>💎|| {username}</b>, теперь можешь выбрать ячейку!\n"
            f"<code>·····················</code>\n"
            f"<b>💸|| Ставка:</b>\n<b>{format_balance(game['stake'])}</b> Spark🦎\n"
            f"<code>·····················</code>\n"
            f"<b>🪜|| Ряд {row_number} из 10</b>\n"
            f"<code>·····················</code>\n"
            f"<b>📈|| Множитель: x{multiplier}</b>\n"
            f"<code>·····················</code>\n"
            f"<b>💰|| Текущий выигрыш:</b>\n<b>+{format_balance(game['win'])}</b> Spark🦎"
        )
        sent_msg = await call.message.edit_text(text=text, reply_markup=get_full_keyboard(game_user_id), parse_mode=ParseMode.HTML)
        game["message_id"] = sent_msg.message_id
    else:
        # полный проход — начисляем выигрыш и обновляем статистику
        try:
            await update_user_balance(game_user_id, game["win"])
        except Exception:
            logging.exception("Ошибка при зачислении выигрыша пользователю в алмазах")

        try:
            await increment_games_played(game_user_id, 1)
            await add_win_record(game_user_id, int(game["win"]))
        except Exception:
            logging.exception("Ошибка при обновлении статистики после полного прохождения алмазов")

        text = (
            f"<b>🎉💎|| {username}</b>, вы успешно прошли игру Алмазы!\n"
            f"<code>·····················</code>\n"
            f"<b>💸|| Ставка:</b>\n<b>{format_balance(game['stake'])}</b> Spark🦎\n"
            f"<code>·····················</code>\n"
            f"<b>🏆|| Итоговый выигрыш:</b>\n<b>+{format_balance(game['win'])}</b> Spark🦎"
        )
        try:
            await call.message.edit_text(text=text, reply_markup=None, parse_mode=ParseMode.HTML)
        except Exception:
            await asyncio.sleep(1)
            await call.message.edit_text(text=text, reply_markup=None, parse_mode=ParseMode.HTML)
        del GAMES[game_user_id]


# Забрать выигрыш
@dp.callback_query_handler(Text(startswith="diamonds_take_"))
async def take_win(call: types.CallbackQuery):
    _, _, user_id = call.data.split("_")
    user_id = int(user_id)

    if user_id not in GAMES:
        await call.answer("❌ Игра не найдена или кнопка уже использована", show_alert=True)
        return

    game = GAMES[user_id]

    if call.message.message_id != game.get("message_id"):
        await call.answer("❌ Эта кнопка уже использована", show_alert=True)
        return

    username = game["username"]

    # начисляем и обновляем статистику
    try:
        await update_user_balance(user_id, game["win"])
    except Exception:
        logging.exception("Ошибка при зачислении выигрыша при взятии в алмазах")

    try:
        await increment_games_played(user_id, 1)
        await add_win_record(user_id, int(game["win"]))
    except Exception:
        logging.exception("Ошибка при обновлении статистики после взятия выигрыша в алмазах")

    text = (
        f"<b>🏆|| {username}</b>, ты забрал выигрыш!\n"
        f"<code>·····················</code>\n"
        f"<b>💸|| Ставка:</b>\n<b>{format_balance(game['stake'])}</b> Spark🦎\n"
        f"<code>·····················</code>\n"
        f"<b>💰 Итоговый выигрыш:</b>\n<b>+{format_balance(game['win'])}</b> Spark🦎"
    )

    await call.message.edit_text(
        text=text,
        reply_markup=None,
        parse_mode=ParseMode.HTML
    )

    del GAMES[user_id]


# Заблокированные ряды
@dp.callback_query_handler(Text(startswith="diamonds_disabled_"))
async def disabled_row(call: types.CallbackQuery):
    await call.answer("Этот ряд уже пройден ✅", show_alert=True)


# Отмена игры (второй вариант — если у вас дублируется handler внизу)
@dp.callback_query_handler(Text(startswith="diamonds_cancel_"))
async def cancel_game_bottom(call: types.CallbackQuery):
    # этот handler защищён от повторного использования: если уже был использован — предыдущий сработает
    try:
        _, _, game_user_id = call.data.split("_")
        game_user_id = int(game_user_id)
    except Exception:
        return await call.answer("Некорректные данные кнопки", show_alert=True)

    # Проверяем, что кнопку нажимает владелец игры
    if call.from_user.id != game_user_id:
        await call.answer("❌ Эта кнопка не для тебя!", show_alert=True)
        return

    if game_user_id not in GAMES:
        await call.answer("❌ Игра не найдена или уже отменена!", show_alert=True)
        return

    game = GAMES[game_user_id]

    # Проверка message_id, чтобы нельзя было дважды отменить
    if call.message.message_id != game.get("message_id"):
        await call.answer("❌ Эта кнопка уже использована!", show_alert=True)
        return

    # Возвращаем ставку
    await update_user_balance(game_user_id, game["stake"])

    # Удаляем игру
    del GAMES[game_user_id]

    await call.message.edit_text(text="❌ Игра отменена", reply_markup=None)



# --- Константы ---
CHECK_CODE_LENGTH = 12
ADMIN_USER_IDS = 8276923232

# --- Функция для генерации случайного кода чека ---p


def generate_check_code(length=CHECK_CODE_LENGTH):
    """Генерирует случайный код для чека."""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# --- Функция для создания ссылки на активацию чека ---
def create_check_link(check_code):
    """Создает ссылку для активации чека через start."""
    encoded_check_code = quote(check_code)  # URL-кодируем код чека
    return f"https://t.me/SparkSGame_bot?start=check_{encoded_check_code}"

# --- Функция для проверки наличия колонки в таблице ---
async def check_column_exists(table_name, column_name):
    """Проверяет, существует ли колонка в указанной таблице."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in cursor.fetchall()]
    close_db_connection(conn)
    return column_name in columns

# --- Функция для добавления колонки в таблицу (если её нет) ---
async def add_column_if_not_exists(table_name, column_name, column_type="TEXT"):
    """Добавляет колонку в таблицу, если она еще не существует."""
    if not await check_column_exists(table_name, column_name):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            conn.commit()
            logging.info(f"Добавлена колонка '{column_name}' в таблицу '{table_name}'.")
        except Exception as e:
            logging.error(f"Ошибка при добавлении колонки '{column_name}' в таблицу '{table_name}': {e}")
        finally:
            close_db_connection(conn)
    else:
        logging.info(f"Колонка '{column_name}' уже существует в таблице '{table_name}'.")

# --- Функция для создания чека ---
async def create_check(creator_id: int, amount: int, activations: int) -> str:
    """Создает чек в базе данных и возвращает его код."""
    if amount < 100:
        return "min_amount"  # Возвращаем код ошибки, если сумма меньше 100
    if amount <= 0:
        return "invalid_amount"  # Возвращаем код ошибки, если сумма отрицательная или равна нулю

    check_code = generate_check_code()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO checks (creator_id, amount, activations, remaining_activations, code) VALUES (?, ?, ?, ?, ?)",
            (creator_id, amount, activations, activations, check_code),
        )
        conn.commit()
        return check_code
    except Exception as e:
        logging.error(f"Ошибка при создании чека в базе данных: {e}")
        return None
    finally:
        close_db_connection(conn)

# --- Функция для активации чека ---
async def activate_check(user_id: int, check_code: str) -> bool:
    """Активирует чек для пользователя, если это возможно."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Проверяем, не активировал ли пользователь уже этот чек
        cursor.execute("SELECT 1 FROM check_activations WHERE user_id = ? AND check_id = (SELECT check_id FROM checks WHERE code = ?)", (user_id, check_code))
        if cursor.fetchone():
            return False, "already_activated"

        # Получаем информацию о чеке
        cursor.execute("SELECT check_id, creator_id, amount, remaining_activations FROM checks WHERE code = ?", (check_code,))
        check_data = cursor.fetchone()

        if not check_data:
            return False, "not_found"

        check_id, creator_id, amount, remaining_activations = check_data

        if remaining_activations <= 0:
            return False, "no_activations"

        # Активируем чек
        cursor.execute("UPDATE checks SET remaining_activations = remaining_activations - 1 WHERE check_id = ?", (check_id,))
        cursor.execute("INSERT INTO check_activations (user_id, check_id) VALUES (?, ?)", (user_id, check_id))
        conn.commit()
        return True, {"check_id": check_id, "creator_id": creator_id, "amount": amount}
    except Exception as e:
        logging.error(f"Ошибка при активации чека в базе данных: {e}")
        return False, "database_error"
    finally:
        close_db_connection(conn)

# --- Функция для отправки уведомления создателю чека ---
async def send_check_activation_notification(bot: Bot, creator_id: int, activator_id: int, remaining_activations: int):
    """Отправляет уведомление создателю чека об активации."""
    try:
        activator = await bot.get_chat(activator_id)
        activator_name = activator.username or activator.first_name
        activator_link = hlink(activator_name, f"tg://user?id={activator_id}")

        text = f"<b>📥||Ваш чек успешно активировал(-а) {activator_link}!</b>\n" \
               f"<b>📦||Осталось активаций: {remaining_activations}</b> шт."
        await bot.send_message(creator_id, text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления создателю чека {creator_id}: {e}")

# --- Обработчик команды "Создать чек" ---
@dp.message_handler(Text(startswith="Создать_чек", ignore_case=True), chat_type=types.ChatType.PRIVATE)
async def create_check_command(message: Message):
    """Обрабатывает команду создания чека."""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Проверка на бан
    if await is_user_banned(user_id):
        await message.reply("❌ Вы забанены и не можете использовать эту команду.")
        return

    # Получаем аргументы команды
    try:
        args = message.text.split(maxsplit=3)
        if len(args) < 3:
            await message.reply("❌ Неверное количество аргументов. Используйте: Создать чек <сумма> <количество активаций>")
            return

        _, amount_str, activations_str = args

        # Форматируем сумму чека
        amount = format_stake(amount_str)
        if amount is None:
            await message.reply("❌ Неверный формат суммы чека. Используйте число или сокращение (1к, 1кк).")
            return

        amount = int(amount)

        # Проверяем количество активаций
        try:
            activations = int(activations_str)
            if activations <= 0:
                await message.reply("❌ Количество активаций должно быть больше нуля.")
                return
        except ValueError:
            await message.reply("❌ Неверный формат количества активаций. Используйте целое число.")
            return

        # Рассчитываем стоимость создания чека
        creation_cost = amount * activations

        # Проверяем баланс пользователя
        balance = await get_user_balance(user_id)
        if balance < creation_cost:
            await message.reply("❌|| У вас не хватает средств для создания чека!")
            return

    except ValueError:
        await message.reply("❌ Неверный формат аргументов. Используйте: Создать чек <сумма> <количество активаций>")
        return

    # Создаем чек
    check_code = await create_check(user_id, amount, activations)

    if check_code == "min_amount":
        await message.reply("Минимальная сумма создания чека 100 Spark🦎!")
        return
    if check_code == "invalid_amount":
        await message.reply("Сумма чека должна быть положительной!")
        return

    if check_code:
        # Списываем средства за создание чека
        await update_user_balance(user_id, -creation_cost)

        # Создаем ссылку на активацию чека
        check_link = create_check_link(check_code)

        # Формируем текст ответа
        text = f"<b>🧾✅|| Ваш чек успешно создан!</b>\n\n" \
               f"<b>📓||Чек-код:</b> <code>{check_code}</code>\n" \
               f"<b>📘||Активаций: {activations}</b> шт.\n" \
               f"💰||Сумма чека: <b>{format_balance(amount)}</b> Spark🦎\n" \
               f"🔥||Сумма списания за чек: <b>{format_balance(creation_cost)}</b> Spark🦎\n\n" \
               f"<b>✨||Ваша универсальная ссылка для активации чека:</b>\n" \
               f"<code>{check_link}</code>"

        await message.reply(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    else:
        await message.reply("❌ Произошла ошибка при создании чека. Попробуйте позже.")

# --- Обработчик для команды "Создать чек" в группе ---
@dp.message_handler(Text(startswith="Создать чек", ignore_case=True), chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def create_check_group_command(message: Message):
    """Обрабатывает попытку создания чека в группе."""
    await message.reply("♨️|| Создать чек можно только в лс с ботом!")

# --- Функция для добавления колонки 'code' в таблицу 'checks' (если её нет) ---
async def add_code_column_to_checks():
    """Добавляет колонку 'code' в таблицу 'checks', если её еще нет."""
    if not await check_column_exists("checks", "code"):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("ALTER TABLE checks ADD COLUMN code TEXT")
            conn.commit()
            logging.info("Добавлена колонка 'code' в таблицу 'checks'.")
        except Exception as e:
            logging.error(f"Ошибка при добавлении колонки 'code' в таблицу 'checks': {e}")
        finally:
            close_db_connection(conn)
    else:
        logging.info("Колонка 'code' уже существует в таблице 'checks'.")

# --- Функция для инициализации таблицы 'checks' и 'check_activations' ---
async def init_checks_tables():
    """Инициализирует таблицы 'checks' и 'check_activations', если их еще нет."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Создаем таблицу чеков
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                check_id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER,
                amount INTEGER,
                activations INTEGER,
                remaining_activations INTEGER,
                code TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Создаем таблицу активированных чеков пользователями
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS check_activations (
                user_id INTEGER,
                check_id INTEGER,
                activated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, check_id)
            )
        """)

        conn.commit()
        logging.info("Таблицы 'checks' и 'check_activations' успешно созданы или уже существуют.")
    except Exception as e:
        logging.error(f"Ошибка при создании таблиц 'checks' и 'check_activations': {e}")
    finally:
        close_db_connection(conn)   





# Функция очистки таблиц checks и check_activations
async def clear_checks_table(reset_autoincrement: bool = False) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Сначала очищаем таблицу активированных чеков (чтобы не было FK-проблем)
        cursor.execute("DELETE FROM check_activations")
        # Затем очищаем таблицу чеков
        cursor.execute("DELETE FROM checks")

        # Опционально: сброс автоинкремента (если используете SQLite)
        if reset_autoincrement:
            try:
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='checks'")
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='check_activations'")
            except Exception as e:
                # Если БД не SQLite или нет sqlite_sequence — проигнорируем ошибку
                logging.warning(f"Не удалось сбросить sqlite_sequence: {e}")

        conn.commit()
        logging.info("Таблицы 'checks' и 'check_activations' успешно очищены.")
        return True
    except Exception as e:
        logging.error(f"Ошибка при очистке таблиц 'checks' и 'check_activations': {e}")
        return False
    finally:
        close_db_connection(conn)

# Обработчик команды -чеки (личные сообщения)
@dp.message_handler(Text(equals="-чеки", ignore_case=True), chat_type=types.ChatType.PRIVATE)
async def clear_checks_command(message: Message):
    user_id = message.from_user.id

    # Простая проверка на владельца бота (OWNER_ID)
    if user_id not in OWNER_IDS:
        await message.reply("❌ У вас нет прав на выполнение этой операции.")
        return

    keyboard = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("Удалить все чеки ❗️", callback_data="confirm_clear_checks"),
        InlineKeyboardButton("Отмена", callback_data="cancel_clear_checks")
    )

    await message.reply(
        "Вы действительно хотите удалить все чеки? Это действие необратимо.\n\n"
        "Если вы уверены — нажмите «Удалить все чеки».",
        reply_markup=keyboard
    )

# Подтверждение удаления — также проверяем OWNER_ID внутри callback
@dp.callback_query_handler(lambda c: c.data == "confirm_clear_checks")
async def process_confirm_clear_checks(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id != OWNER_ID:
        await callback_query.answer("Нет прав на выполнение операции.", show_alert=True)
        return

    await callback_query.answer()  # убрать индикатор ожидания у пользователя
    success = await clear_checks_table()

    if success:
        try:
            await callback_query.message.edit_text("✅ Все чеки успешно удалены.")
        except Exception:
            await callback_query.message.answer("✅ Все чеки успешно удалены.")
    else:
        try:
            await callback_query.message.edit_text("❌ Ошибка при удалении чеков. Смотрите логи.")
        except Exception:
            await callback_query.message.answer("❌ Ошибка при удалении чеков. Смотрите логи.")

# Обработка отмены — тоже проверяем владельца (чтобы никто другой не мог отменять за вас)
@dp.callback_query_handler(lambda c: c.data == "cancel_clear_checks")
async def process_cancel_clear_checks(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id != OWNER_IDS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return

    await callback_query.answer()
    try:
        await callback_query.message.edit_text("Отмена удаления чеков.")
    except Exception:
        await callback_query.message.answer("Отмена удаления чеков.")



DICE_EMOJI = "🎲" # Unicode character for dice

# Регистрируем обработчик для команды "кости" или "/cubes"
@dp.message_handler(lambda message: message.text and (message.text.lower().startswith('кости') or message.text.lower().startswith('/cubes')))
async def cubes_handler(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Проверка на бан
    try:
        if await is_user_banned(user_id):
            return await message.reply("🚫 Вы забанены и не можете использовать эту команду.")
    except Exception:
        # Если is_user_banned не определена или упала — пропускаем проверку
        pass

    # Создание пользователя, если его нет
    try:
        await create_user(user_id, username)
    except Exception:
        pass

    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("⚠️ Использование: кости (ставка) (больше|меньше|равно)", parse_mode="HTML")
        return

    bet_str = parts[1].strip().lower()
    choice = parts[2].lower()

    if choice not in ["больше", "меньше", "равно"]:
        await message.reply("⚠️ Укажите один из вариантов: больше, меньше, равно", parse_mode="HTML")
        return

    # Получаем баланс пользователя
    balance = await get_user_balance(user_id)

    # Форматируем ставку
    if bet_str == 'все':
        bet = balance
        if bet <= 0:
            await message.reply("❌ Недостаточно средств.", parse_mode="HTML")
            return
    else:
        bet = format_stake(bet_str)  # Используем ваш формат стейк
        if bet is None or bet <= 0:
            await message.reply("⚠️ Некорректная ставка.", parse_mode="HTML")
            return
        bet = int(bet) #Убедитесь, что ставка - целое число

    # Проверка баланса
    if balance < bet:
        await message.reply("❌ Недостаточно средств.", parse_mode="HTML")
        return

    # Снимаем ставку с баланса
    await update_user_balance(user_id, -bet)

    # Генерируем случайное число от 2 до 12 (сумма двух костей)
    # Сделаем выпадение "равно 7" в 2 раза более вероятным, чем другие числа
    outcomes = (
        [2, 3, 4, 5, 6, 8, 9, 10, 11, 12] * 2 +  # увеличиваем вероятность "не 7"
        [7] * 4  # "7" теперь появляется в 2 раза чаще, чем остальные числа
    )
    total = random.choice(outcomes)

    if total > 7:
        result = "больше"
        symbol = "🔼"
    elif total < 7:
        result = "меньше"
        symbol = "🔽"
    else:
        result = "равно"
        symbol = "🟰"

    win = 0
    if result == choice:
        if choice == "равно":
            multiplier = 2.65
        else:
            multiplier = 1.8
        win = int(bet * multiplier)

        # Начисляем выигрыш на баланс
        try:
            await update_user_balance(user_id, win) # Обновляем баланс с выигрышем
        except Exception:
            logging.exception("Ошибка при зачислении выигрыша в кости")

        # Обновляем статистику: +1 игра, +выигрыш
        try:
            await increment_games_played(user_id, 1)
            await add_win_record(user_id, int(win))  # фиксируем зачисленную сумму
        except Exception:
            logging.exception("Ошибка при обновлении статистики после выигрыша в кости")

        title = "Ты выиграл! ✅"
        result_line = f"📊 Выигрыш: x{multiplier} / +{format_balance(win)} Spark🦎"
    else:
        # Проигрыш
        # Обновляем статистику: +1 игра, +проигрыш (ставка)
        try:
            await increment_games_played(user_id, 1)
            await add_loss_record(user_id, int(bet))
        except Exception:
            logging.exception("Ошибка при обновлении статистики после поражения в кости")

        title = "Ты проиграл! 😢"
        result_line = ""

    # Формирование текста
    text = (
        f"{title}\n\n"
        f"💸 Ставка: {format_balance(bet)} Spark🦎\n"
        f"🎲 Исход: {choice} 7\n"
        f"{result_line}\n"
        f"-----------------\n"
        f"⚡️Выпало: {result} 7 {symbol}"
    )

    # Отправляем сообщение с результатом игры
    await message.reply(text, parse_mode="HTML")



@dp.message_handler(lambda message: message.from_user.id in OWNER_IDS, commands=["panel"])
async def admin_panel_text(message: types.Message):
    panel_text = """
⚙️ Админ-панель:

💰 Выдать / Забрать — выдача или снятие монет
🎁 Донат статус 10/11 — /std
+бан — забанить игрока
+анбан — разбанить игрока
/vrf — верифицировать игрока
🏦 Балансы банка — окс
+р — рассылка сообщений
+промо — создать промокод
уснять — снять деньги у игрока по username
дж — показать балансы всех игроков
юдать — выдача монет пользователю по ID
-банки — обнулить банки игроков
обнул — обнулить все балансы
+база — обновить базу
-бизнесы — обнулить бизнесы
-чеки — обнулить все чеки
-/add_spins - выдать спины игроку
    """
    await message.reply(panel_text)

# ================== НАСТРОЙКИ HILO ==================
HILO_MIN_BET = 100
HILO_MAX_ROUNDS = 10
SUITS = ["♠️", "♥️", "♣️", "♦️"]

# Словарь для хранения активных игр. Ключ - ID игры, значение - данные игры
active_hilo_games = {}

# Словарь для отслеживания времени последнего действия пользователя
last_button_press = {}  # user_id: timestamp

# Кулдаун (в секундах)
BUTTON_COOLDOWN = 2

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================
def draw_card():
    """Возвращает случайную карту (номер и масть)."""
    return random.randint(1, 13), random.choice(SUITS)

def card_text(num, suit):
    """Форматирует карту в текст."""
    names = {1: "Туз", 11: "Валет", 12: "Дама", 13: "Король"}
    return f"{names.get(num, str(num))}{suit}"

def calculate_multiplier_fixed(card_num):
    """Фиксированные множители для карт."""
    multipliers = {
        1: (1.00, 2.00),   # Туз
        2: (1.00, 1.79),
        3: (1.00, 1.79),
        4: (1.18, 1.32),
        5: (1.26, 1.23),
        6: (1.31, 1.29),
        7: (1.32, 1.32),
        8: (1.32, 1.29),
        9: (1.34, 1.30),
        10: (1.32, 1.25),
        11: (1.79, 1.10),  # Валет
        12: (1.75, 1.12),  # Дама
        13: (1.50, 1.00)   # Король
    }
    return multipliers.get(card_num, (1.3, 1.3))

# ================== ФУНКЦИЯ ДЛЯ ФОРМАТИРОВАНИЯ ТЕКСТА ==================
def format_hilo_text(game, first_card):
    """Форматирует текст сообщения с информацией об игре."""
    first_card_text = card_text(*first_card)
    x_higher, x_lower = calculate_multiplier_fixed(first_card[0])
    lower = first_card[0] - 1
    higher = 13 - first_card[0]
    # Защита от деления на ноль (крайний случай)
    total = (lower + higher) if (lower + higher) > 0 else 1
    lower_perc = round(lower / total * 100, 2)
    higher_perc = round(higher / total * 100, 2)

    text = (
        f"🎮 Игра HiLo - Раунд {game['round']}/{HILO_MAX_ROUNDS}\n"
        f"🃏 Карта: {first_card_text}\n"
        f"💰 Ставка: {format_number(game['bet'])} Spark🦎\n\n"
        f"⬆️ Больше → {higher_perc}% (x{x_higher:.2f})\n"
        f"⬇️ Меньше → {lower_perc}% (x{x_lower:.2f})\n\n"
        "🔅 Выберите ваш ход!"
    )
    return escape_md(text)

# ================== ОБРАБОТЧИК КОМАНДЫ /hilo ==================
@dp.message_handler(Text(startswith=("хило", "/hilo"), ignore_case=True))
async def cmd_hilo(message: types.Message):
    """Обработчик команды /hilo."""
    user_id = message.from_user.id
    user_username = message.from_user.username or message.from_user.first_name

    # Проверка на бан
    try:
        if await is_user_banned(user_id):
            await message.reply("❌ Вы забанены и не можете использовать эту команду.")
            return
    except Exception:
        pass

    # Проверка на наличие активной игры
    for game_id, game in active_hilo_games.items():
        if game['user_id'] == user_id:
            await message.reply("⚠️ У вас уже есть активная игра HiLo. Завершите её или дождитесь таймаута.")
            return

    # Создание пользователя, если его нет
    try:
        await create_user(user_id, user_username)
    except Exception:
        pass

    # Получение и форматирование ставки
    try:
        stake_str = message.text.split()[1]
        # Обрабатываем "все" внутри format_stake или отдельно
        if stake_str.lower() == "все":
            balance = await get_user_balance(user_id)
            stake = balance
        else:
            stake = format_stake(stake_str)
            if stake is None:
                await message.reply("❌ Неверный формат ставки. Используйте число или сокращение (1к, 1кк).", parse_mode=ParseMode.MARKDOWN_V2)
                return
            stake = int(stake)

        if stake < HILO_MIN_BET:
            await message.reply(f"❌ Минимальная ставка: {format_number(HILO_MIN_BET)} Spark🦎", parse_mode=ParseMode.MARKDOWN_V2)
            return

    except IndexError:
        await message.reply("❌ Пожалуйста, укажите ставку после команды  хило. Пример: хило 100", parse_mode=ParseMode.MARKDOWN_V2)
        return

    # Проверка баланса
    balance = await get_user_balance(user_id)
    if balance < stake:
        await message.reply("❌ Недостаточно средств на балансе.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    # Создание ID игры
    game_id = str(uuid.uuid4())

    # Создание игры
    active_hilo_games[game_id] = {
        "user_id": user_id,
        "username": user_username,
        "stake": stake,
        "bet": stake,  # Начальная "текущая" ставка (она будет расти)
        "round": 0,
        "claimed": False,
        "message_id": None  # Добавлено для отслеживания сообщения
    }

    # Создание кнопок
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Начать", callback_data=f"hilo_start|{game_id}"),
        InlineKeyboardButton("❌ Отмена", callback_data=f"hilo_cancel|{game_id}")
    )

    # Отправка сообщения
    text = f"🎮 Начать игру HiLo на:\n{format_number(stake)} Spark🦎?\nВы готовы❓"
    sent_message = await message.reply(escape_md(text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)

    # Сохранение ID сообщения
    active_hilo_games[game_id]["message_id"] = sent_message.message_id

# ================== ОБРАБОТЧИК CALLBACK-ЗАПРОСОВ ==================
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("hilo_"))
async def callback_hilo_handler(query: CallbackQuery):
    """Обработчик callback-запросов HiLo."""
    user_id = query.from_user.id
    game_id = query.data.split("|")[-1]

    # Проверка на флуд
    if user_id in last_button_press and datetime.now().timestamp() - last_button_press[user_id] < BUTTON_COOLDOWN:
        await query.answer("⚠️ Слишком быстро! Подождите немного.", show_alert=True)
        return

    # Обновление времени последнего нажатия кнопки
    last_button_press[user_id] = datetime.now().timestamp()

    # Проверка, что игра существует
    if game_id not in active_hilo_games:
        await query.answer("⚠️ Игра не найдена или уже завершена.", show_alert=True)
        return

    game = active_hilo_games[game_id]

    # Проверка, что callback от того же пользователя, который начал игру
    if game["user_id"] != user_id:
        await query.answer("⚠️ Это не ваша игра!", show_alert=True)
        return

    action = query.data.split("|")[0]
    try:
        if action == "hilo_cancel":
            await hilo_cancel(query, game_id)
        elif action == "hilo_start":
            await hilo_start(query, game_id)
        elif action == "hilo_guess":
            await hilo_guess(query, game_id)
        elif action == "hilo_take":
            await hilo_take(query, game_id)
    except Exception as e:
        logging.error(f"Ошибка при обработке callback: {e}")
        await query.answer("⚠️ Произошла ошибка. Попробуйте позже.", show_alert=True)

# ================== ОТДЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ОБРАБОТКИ ДЕЙСТВИЙ ==================
async def hilo_cancel(query: CallbackQuery, game_id: str):
    """Отмена игры."""
    # Берём игру, защищаемся на случай, если уже удалена
    game = active_hilo_games.pop(game_id, None)
    if not game:
        await query.answer("Игра уже отменена или не найдена.", show_alert=True)
        return

    user_id = game['user_id']
    stake = game['stake']

    # Возврат ставки
    try:
        await update_user_balance(user_id, stake)
    except Exception:
        logging.exception("Ошибка при возврате ставки в hilo_cancel")

    text = "🚫 Игра отменена! Ставка возвращена."
    try:
        await bot.edit_message_text(
            text=escape_md(text),
            chat_id=query.message.chat.id,
            message_id=query.message.message_id,
            reply_markup=None,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except TelegramError as e:
        logging.error(f"Ошибка при редактировании сообщения: {e}")

    await query.answer("Игра отменена.")

async def hilo_start(query: CallbackQuery, game_id: str):
    """Начало игры."""
    game = active_hilo_games.get(game_id)
    if not game:
        await query.answer("Игра не найдена.", show_alert=True)
        return

    user_id = game['user_id']

    # Списание ставки (списываем здесь)
    try:
        await update_user_balance(user_id, -game['stake'])
    except Exception:
        logging.exception("Ошибка при списании ставки в hilo_start")

    # Начинаем игру
    first_card = draw_card()
    game['round'] = 1
    game['first_card'] = first_card
    active_hilo_games[game_id] = game

    # Создаем кнопки
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("⬆️ Больше", callback_data=f"hilo_guess|higher|{game_id}"),
        InlineKeyboardButton("⬇️ Меньше", callback_data=f"hilo_guess|lower|{game_id}"),
        InlineKeyboardButton("💵 Забрать", callback_data=f"hilo_take|{game_id}")
    )

    # Обновляем текст
    text = format_hilo_text(game, first_card)
    try:
        await bot.edit_message_text(
            text=text,
            chat_id=query.message.chat.id,
            message_id=query.message.message_id,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except TelegramError as e:
        logging.error(f"Ошибка при редактировании сообщения: {e}")

    await query.answer("Игра началась!")

async def hilo_guess(query: CallbackQuery, game_id: str):
    """Обработка выбора "Больше" или "Меньше"."""
    game = active_hilo_games.get(game_id)
    if not game:
        await query.answer("Игра не найдена.", show_alert=True)
        return

    user_id = game['user_id']
    guess = query.data.split("|")[1]
    first_card = game['first_card']
    stake = game['bet']  # Текущая ставка, которая растёт

    # Проверка на максимальное количество раундов
    if game['round'] > HILO_MAX_ROUNDS:
        await query.answer("⚠️ Достигнуто максимальное количество раундов. Заберите свой выигрыш.", show_alert=True)
        return

    # Вытягиваем новую карту
    second_card = draw_card()
    while second_card[0] == first_card[0]:
        second_card = draw_card()

    # Проверяем, угадал ли игрок
    won = (guess == "higher" and second_card[0] > first_card[0]) or \
          (guess == "lower" and second_card[0] < first_card[0])

    if won:
        # Увеличиваем раунд и ставку
        game['round'] += 1
        multiplier = calculate_multiplier_fixed(first_card[0])[0] if guess == "higher" else calculate_multiplier_fixed(first_card[0])[1]
        # Обновляем текущую ставку (и округляем до int)
        game['bet'] = int(round(stake * multiplier))
        game['first_card'] = second_card
        active_hilo_games[game_id] = game

        # Проверяем, не достиг ли игрок максимального количества раундов
        if game['round'] > HILO_MAX_ROUNDS:
            await hilo_win(query, game_id)
            return

        # Создаем новые кнопки
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("⬆️ Больше", callback_data=f"hilo_guess|higher|{game_id}"),
            InlineKeyboardButton("⬇️ Меньше", callback_data=f"hilo_guess|lower|{game_id}"),
            InlineKeyboardButton("💵 Забрать", callback_data=f"hilo_take|{game_id}")
        )

        # Обновляем текст сообщения
        text = format_hilo_text(game, second_card)
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=query.message.chat.id,
                message_id=query.message.message_id,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except TelegramError as e:
            logging.error(f"Ошибка при редактировании сообщения: {e}")

        await query.answer("Угадали! Продолжаем...")
    else:
        # Игрок проиграл
        await hilo_lose(query, game_id)

async def hilo_take(query: CallbackQuery, game_id: str):
    """Забор выигрыша."""
    # Берём игру и отмечаем, что она завершена
    game = active_hilo_games.pop(game_id, None)
    if not game:
        await query.answer("⚠️ Игра не найдена или уже завершена.", show_alert=True)
        return

    user_id = game['user_id']

    # Проверка на двойное нажатие
    if game.get('claimed', False):
        await query.answer("⚠️ Вы уже забрали свой выигрыш!", show_alert=True)
        return

    # Выдача выигрыша
    try:
        await update_user_balance(user_id, game['bet'])
    except Exception:
        logging.exception("Ошибка при зачислении выигрыша в hilo_take")

    # Отмечаем, что выигрыш получен
    game['claimed'] = True

    # Обновляем статистику: +1 игра, +выигрыш
    try:
        await increment_games_played(user_id, 1)
        await add_win_record(user_id, int(game['bet']))
    except Exception:
        logging.exception("Ошибка при обновлении статистики после взятия выигрыша в HiLo")

    text = f"💰 Вы забрали свой выигрыш: +{format_number(game['bet'])} Spark🦎!"
    try:
        await bot.edit_message_text(
            text=escape_md(text),
            chat_id=query.message.chat.id,
            message_id=query.message.message_id,
            reply_markup=None,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except TelegramError as e:
        logging.error(f"Ошибка при редактировании сообщения: {e}")

    await query.answer("Выигрыш зачислен!")

async def hilo_win(query: CallbackQuery, game_id: str):
    """Обработка выигрыша (достигнуто максимальное количество раундов)."""
    # Берём игру и удаляем
    game = active_hilo_games.pop(game_id, None)
    if not game:
        await query.answer("Игра не найдена.", show_alert=True)
        return

    user_id = game['user_id']

    # Выдача выигрыша
    try:
        await update_user_balance(user_id, game['bet'])
    except Exception:
        logging.exception("Ошибка при зачислении выигрыша в hilo_win")

    # Обновляем статистику: +1 игра, +выигрыш
    try:
        await increment_games_played(user_id, 1)
        await add_win_record(user_id, int(game['bet']))
    except Exception:
        logging.exception("Ошибка при обновлении статистики после полного выигрыша HiLo")

    text = f"🏆 Вы выиграли! Ваш выигрыш: +{format_number(game['bet'])} Spark🦎!"
    try:
        await bot.edit_message_text(
            text=escape_md(text),
            chat_id=query.message.chat.id,
            message_id=query.message.message_id,
            reply_markup=None,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except TelegramError as e:
        logging.error(f"Ошибка при редактировании сообщения: {e}")

    await query.answer("Вы выиграли!")

async def hilo_lose(query: CallbackQuery, game_id: str):
    """Обработка проигрыша."""
    # Берём игру и удаляем
    game = active_hilo_games.pop(game_id, None)
    if not game:
        await query.answer("Игра не найдена.", show_alert=True)
        return

    user_id = game.get('user_id')
    stake = game.get('stake', 0)

    text = "❌ Вы проиграли!"
    try:
        await bot.edit_message_text(
            text=escape_md(text),
            chat_id=query.message.chat.id,
            message_id=query.message.message_id,
            reply_markup=None,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except TelegramError as e:
        logging.error(f"Ошибка при редактировании сообщения: {e}")

    # Обновляем статистику: +1 игра, +проигрыш (ставка)
    try:
        if user_id:
            await increment_games_played(user_id, 1)
            await add_loss_record(user_id, int(stake))
    except Exception:
        logging.exception("Ошибка при обновлении статистики после поражения в HiLo")

    await query.answer("Вы проиграли.")



# Коэффициенты выигрыша
MURDER_MULTIPLIERS = {
    1: 2,
    2: 2.8,
    3: 3.4,
    4: 4.2,
    5: 4.8,
    6: 5.5,
    7: 6.4
}

MIN_STAKE_MURDER = 100

# Словарь для хранения активных игр мюрдер
active_murder_games = {}  # user_id: game_data


# Универсальная функция экранирования для MarkdownV2
def escape_md(text: str) -> str:
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

# Команда /мюрдер <ставка>
@dp.message_handler(Text(startswith="мюрдер", ignore_case=True))
async def murder_command(message: types.Message):
    user_id = message.from_user.id
    user_username = message.from_user.username or message.from_user.first_name

    await create_user(user_id, user_username)

    if await is_user_banned(user_id):
        await message.reply("❌ Вы забанены и не можете использовать эту команду.")
        return

    if user_id in active_murder_games:
        await message.reply("⚠️| У вас уже есть активная игра в 'Мюрдер'. Завершите её или дождитесь тайм-аута.")
        return

    try:
        stake_str = message.text.split()[1]
        stake = format_stake(stake_str)

        if stake is None:
            await message.reply("❌|| Неверный формат ставки. Используйте число или сокращение (1к, 1кк).")
            return

        if stake == 'все':
            balance = await get_user_balance(user_id)
            stake = balance
        else:
            stake = int(stake)

        if stake < MIN_STAKE_MURDER:
            await message.reply(f"❌|| Минимальная ставка: {format_number(MIN_STAKE_MURDER)}.")
            return

    except IndexError:
        await message.reply("❌|| Пожалуйста, укажите ставку после команды 'мюрдер'. Пример: мюрдер 1000")
        return

    balance = await get_user_balance(user_id)
    if balance < stake:
        await message.reply("❌|| Недостаточно средств на балансе.")
        return

    success = await safe_update_user_balance(user_id, -stake)
    if not success:
        await message.reply("❌|| Произошла ошибка при списании ставки. Попробуйте позже.")
        return

    game_data = {
        'user_id': user_id,
        'stake': stake,
        'passes': 0,
        'win_amount': 0,
        'message_id': None,
        'claimed': False,
        'task': None # Добавляем поле для хранения задачи таймаута
    }

    active_murder_games[user_id] = game_data

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("Да✅", callback_data="murder_accept"),
        InlineKeyboardButton("Отклонить❌", callback_data="murder_decline")
    )

    text = (
        f"💰|Ваша ставка: {format_number(stake)}\n"
        "---------------------\n"
        "🔥|Устроим слежку за королем?"
    )
    text = escape_md(text)

    sent_message = await message.reply(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)
    game_data['message_id'] = sent_message.message_id
    active_murder_games[user_id] = game_data

    # Запускаем таймер таймаута
    game_data['task'] = asyncio.create_task(murder_timeout(user_id, sent_message.chat.id, sent_message.message_id))
    active_murder_games[user_id] = game_data

async def murder_timeout(user_id, chat_id, message_id):
    await asyncio.sleep(60)

    if user_id in active_murder_games:
        game_data = active_murder_games.pop(user_id)
        stake = game_data['stake']
        # Возврат ставки без учета потерь (это отмена из‑за таймаута)
        await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)

        text = "⚠️| От вас давно не было активности! Все ваши средства возвращены на баланс."
        text = escape_md(text)

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=None,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except TelegramError as e:
            logging.error(f"Ошибка при редактировании сообщения: {e}")

@dp.callback_query_handler(lambda c: c.data in ["murder_accept", "murder_decline", "murder_claim"])
async def murder_action(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.message_id

    if user_id not in active_murder_games:
        await callback_query.answer("⚠️ Игра не найдена или уже завершена.", show_alert=True)
        return

    game_data = active_murder_games[user_id]
    if game_data['message_id'] != message_id:
        await callback_query.answer("⚠️ Эта кнопка от другой игры.", show_alert=True)
        return
    
    # Отменяем задачу таймаута, если она есть
    if game_data['task']:
        try:
            game_data['task'].cancel()
        except Exception:
            pass

    action = callback_query.data

    if action == "murder_decline":
        stake = game_data['stake']
        await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
        active_murder_games.pop(user_id, None)

        text = "⛔| Игра была отклонена! Ставки были возвращены."
        text = escape_md(text)

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=None,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except TelegramError as e:
            logging.error(f"Ошибка при редактировании сообщения: {e}")

    elif action == "murder_accept":
        text = "👁️‍🗨️| Вы начали приследовать короля......"
        text = escape_md(text)

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=None,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except TelegramError as e:
            logging.error(f"Ошибка при редактировании сообщения: {e}")

        await asyncio.sleep(3)
        await murder_follow(callback_query)

    elif action == "murder_claim":
        await murder_claim(callback_query)

    await callback_query.answer()

async def murder_follow(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.message_id

    if user_id not in active_murder_games:
        await callback_query.answer("⚠️ Игра не найдена или уже завершена.", show_alert=True)
        return

    game_data = active_murder_games[user_id]
    stake = game_data['stake']
    passes = game_data['passes']

    # Вычисляем шанс успеха (теперь и на первом шаге можно проиграть)
    if passes == 0:
        win_chance = 0.5
    else:
        # Шанс уменьшается с каждым проходом
        win_chance = max(0.05, 0.2 - 0.025 * (passes - 1))

    if random.random() < win_chance:
        game_data['passes'] += 1
        passes = game_data['passes']
        multiplier = MURDER_MULTIPLIERS.get(passes, 1.0)
        win_amount = round(stake * multiplier)
        game_data['win_amount'] = win_amount
        active_murder_games[user_id] = game_data

        if passes == 7:
            # Отменяем задачу таймаута, если она есть
            if game_data['task']:
                try:
                    game_data['task'].cancel()
                except Exception:
                    pass
            # Удаляем игру и выплачиваем выигрыш
            del active_murder_games[user_id]
            await safe_update_user_balance(user_id, win_amount, ignore_loss_tracking=True)

            # Обновляем статистику: +1 игра, +выигрыш
            try:
                await increment_games_played(user_id, 1)
                await add_win_record(user_id, int(win_amount))
            except Exception:
                logging.exception("Ошибка при обновлении статистики после полного выигрыша в Murder")

            text = f"💰🏆| Вы убили короля! Теперь империя в ваших руках! Ваш выигрыш: +{format_number(win_amount)}"
            text = escape_md(text)

            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=None,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            except TelegramError as e:
                logging.error(f"Ошибка при редактировании сообщения: {e}")
        else:
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("Да✅", callback_data="murder_accept"),
                InlineKeyboardButton("Забрать💰", callback_data="murder_claim")
            )
            text = (
                f"👑🟩| Король не заподозрил вас!\n"
                "——————————\n"
                f"🪜|Ступень : {passes}/{len(MURDER_MULTIPLIERS)}\n"
                "——————————\n"
                f"💰|Ваш выигрыш на данный момент: +{format_number(win_amount)}\n"
                "——————————\n"
                "🔥|Продолжаем?"
            )
            text = escape_md(text)

            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            except TelegramError as e:
                logging.error(f"Ошибка при редактировании сообщения: {e}")

            # Перезапускаем таймер таймаута
            game_data['task'] = asyncio.create_task(murder_timeout(user_id, chat_id, message_id))
            active_murder_games[user_id] = game_data

    else:
        # Отменяем задачу таймаута, если она есть
        if game_data.get('task'):
            try:
                game_data['task'].cancel()
            except Exception:
                pass
        # удаляем игру — ставка была списана при старте, проигрыш окончательный
        del active_murder_games[user_id]

        text = "❌🪓| Вы попались королю! К сожалению вы проиграли свою ставку, и скорей всего вас ждет казнь!"
        text = escape_md(text)

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=None,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except TelegramError as e:
            logging.error(f"Ошибка при редактировании сообщения: {e}")

        # Обновляем статистику: +1 игра, +проигрыш (ставка)
        try:
            await increment_games_played(user_id, 1)
            await add_loss_record(user_id, int(stake))
        except Exception:
            logging.exception("Ошибка при обновлении статистики после поражения в Murder")

    await callback_query.answer()

async def murder_claim(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.message_id

    if user_id not in active_murder_games:
        await callback_query.answer("⚠️ Игра не найдена или уже завершена.", show_alert=True)
        return

    game_data = active_murder_games[user_id]

    if game_data['message_id'] != message_id:
        await callback_query.answer("⚠️ Эта кнопка от другой игры.", show_alert=True)
        return

    if game_data['claimed']:
        await callback_query.answer("⚠️ Вы уже забрали свой выигрыш.", show_alert=True)
        return

    # Отменяем задачу таймаута, если она есть
    if game_data.get('task'):
        try:
            game_data['task'].cancel()
        except Exception:
            pass

    game_data['claimed'] = True
    active_murder_games[user_id] = game_data

    win_amount = game_data['win_amount']
    del active_murder_games[user_id]
    await safe_update_user_balance(user_id, win_amount, ignore_loss_tracking=True)

    # Обновляем статистику: +1 игра, +выигрыш
    try:
        await increment_games_played(user_id, 1)
        await add_win_record(user_id, int(win_amount))
    except Exception:
        logging.exception("Ошибка при обновлении статистики после взятия выигрыша в Murder")

    text = f"✅💰| Вы решили уйти с выигрышем: +{format_number(win_amount)}!"
    text = escape_md(text)

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=None,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except TelegramError as e:
        logging.error(f"Ошибка при редактировании сообщения: {e}")

    await callback_query.answer()


# Constants
MIN_FP = 100  # Minimum bet for the chest game
CHEST_GAME_TIMEOUT = 60  # Timeout in seconds

# Multiplier pool
MULTIPLIER_POOL = (
    [0] * 25 +  # x0 (loss)
    [0.5] * 23 +  # x0.5
    [1] * 17 +  # x1
    [2] * 12 +  # x2
    [2.5] * 6 +  # x3
    [3] * 4 +  # x4 - 💍
    [4] * 1  # x5.5 - 👑
)

# In-memory storage for active chest games
active_chest_games = {}  # {user_id: {bet, grid, message_id, chat_id}}

# Currency Emoji
REGULAR_CURRENCY_EMOJI = "🟣"

def generate_chest_grid():
    """Generates a new grid with multipliers for the chest game."""
    return random.sample(MULTIPLIER_POOL, 9)

def build_chest_keyboard():
    """Builds an inline keyboard with the chest buttons."""
    buttons = []
    for row in range(3):
        row_buttons = []
        for col in range(3):
            index = row * 3 + col
            row_buttons.append(
                InlineKeyboardButton("🧰", callback_data=f"chest_{index}"))
        buttons.append(row_buttons)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def refund_unplayed_chest_game(user_id: int, chat_id: int, message_id: int):
    """Handles refunding the bet if the user doesn't pick a chest in time."""
    if user_id in active_chest_games:
        game = active_chest_games.pop(user_id)
        bet = game["bet"]

        # Возврат ставки без учёта как проигрыш (ignore_loss_tracking=True)
        try:
            await safe_update_user_balance(user_id, bet, ignore_loss_tracking=True)
        except Exception:
            logging.exception("Ошибка при возврате ставки в refund_unplayed_chest_game")

        try:
            # Добавлено форматирование ставки при возврате
            formatted_bet = format_number(bet)
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"⌛️| Время вышло! Ставка {hbold(formatted_bet)} Spark🦎 возвращена, так как вы не выбрали сундук.",
                reply_markup=None,
                parse_mode=ParseMode.HTML
            )
        except MessageNotModified:
            pass  # Message was already edited
        except MessageToEditNotFound:
            logging.warning(f"Message with ID {message_id} not found for refund.")
        except Exception:
            logging.exception("Ошибка при редактировании сообщения refund_unplayed_chest_game")

@dp.message_handler(Text(startswith=["честы"], ignore_case=True))
@dp.message_handler(Text(startswith=["честы "], ignore_case=True))
@dp.message_handler(Text(startswith=["Честы"], ignore_case=True))
@dp.message_handler(Text(startswith=["Честы "], ignore_case=True))
async def chests_command(message: types.Message):
    """Starts a new chest game."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username or message.from_user.first_name

    # Create user if doesn't exist
    await create_user(user_id, username)

    # Check if user is banned
    if await is_user_banned(user_id):
        await message.reply("❌ Вы забанены и не можете использовать эту команду.")
        return

    # Parse the stake
    try:
        stake_str = message.text.split(maxsplit=1)[1].strip()
    except IndexError:
        await message.reply("❌|| Укажите ставку для игры в сундуки. Пример: честы 1000")
        return

    stake = format_stake(stake_str)

    if stake is None:
        await message.reply("❌|| Неверный формат ставки.")
        return

    if stake == 'все':
        balance = await get_user_balance(user_id)
        stake = balance
    else:
        try:
            stake = int(stake)
        except ValueError:
            await message.reply("❌|| Неверный формат ставки.")
            return

    # Validate stake
    if stake < MIN_FP:
        await message.reply(f"❌|| Минимальная ставка: {MIN_FP} Spark🦎")
        return

    balance = await get_user_balance(user_id)
    if stake > balance:
        await message.reply("❌|| Недостаточно средств на балансе.")
        return

    # Check for active game
    if user_id in active_chest_games:
        await message.reply("❌|| У вас уже есть активная игра. Завершите её сначала.")
        return

    # Withdraw the stake
    success = await safe_update_user_balance(user_id, -stake)
    if not success:
        await message.reply("❌|| Недостаточно средств на балансе.")
        return

    # Generate game data
    grid = generate_chest_grid()
    game_data = {
        "bet": stake,
        "grid": grid,
        "chat_id": chat_id
    }
    active_chest_games[user_id] = game_data

    # Build the keyboard
    keyboard = build_chest_keyboard()

    # Format the stake
    formatted_stake = format_number(stake)

    # Send the game message with the stake
    sent_message = await message.reply(
        f"✅🎁| Игра началась!\n💸| Ваша ставка: {hbold(formatted_stake)} Spark🦎\n\n💡| Открой одну ячейку из ниже предложенных:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML  # Enable HTML parsing for bold text
    )

    # Store message ID for later editing
    game_data["message_id"] = sent_message.message_id

    # Schedule timeout
    asyncio.create_task(
        timeout_chest_game(user_id, chat_id, sent_message.message_id, CHEST_GAME_TIMEOUT)
    )

async def timeout_chest_game(user_id: int, chat_id: int, message_id: int, timeout: int):
    """Handles the timeout for the chest game."""
    await asyncio.sleep(timeout)
    await refund_unplayed_chest_game(user_id, chat_id, message_id)

@dp.callback_query_handler(lambda c: c.data.startswith('chest_'))
async def chests_button_handler(callback_query: types.CallbackQuery):
    """Handles the selection of a chest."""
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.message_id

    if user_id not in active_chest_games:
        try:
            await bot.answer_callback_query(callback_query.id, "⛔️ У тебя нет активной игры.")
        except TelegramError:
            pass
        return

    # Убираем игру из памяти (игра считается завершенной после клика)
    game = active_chest_games.pop(user_id)
    grid = game["grid"]
    bet = game["bet"]
    index = int(callback_query.data.split("_")[1])
    multiplier = grid[index]

    # Calculate reward, rounding to the nearest integer
    reward = round(bet * multiplier)

    # Update user stats/balance and statistics
    if reward > 0:
        # Начисляем выигрыш
        try:
            await update_user_balance(user_id, reward)
        except Exception:
            logging.exception("Ошибка при зачислении выигрыша в chests_button_handler")

        # Обновляем статистику — сыграна игра и выигрыш
        try:
            await increment_games_played(user_id, 1)
            await add_win_record(user_id, int(reward))
        except Exception:
            logging.exception("Ошибка при обновлении статистики после выигрыша в сундуках")

    else:
        # Проигрыш — ставка уже списана при старте, фиксируем как проигрыш
        try:
            await increment_games_played(user_id, 1)
            await add_loss_record(user_id, int(bet))
        except Exception:
            logging.exception("Ошибка при обновлении статистики после поражения в сундуках")

    # Construct result message
    if multiplier > 0:
        reward_str = format_number(reward)
        result_text = f"🎉| Ты нашёл: x{multiplier}!\n💰| Выигрыш: +{hbold(reward_str)} Spark🦎"
    else:
        result_text = "♨️| Ты нашёл : х0!\nСундук оказался подставным.\nПопробуй ещё раз."

    # Build result keyboard (showing results)
    result_keyboard = []
    for i in range(3):
        row = []
        for j in range(3):
            val = grid[i * 3 + j]
            emoji = {
                0: "💥",
                0.5: "🎉",
                1: "💎",
                2: "🍀",
                2.5: "🎁",
                3: "💍",  # x4
                4: "👑"   # x5.5
            }.get(val, "❓")
            row.append(InlineKeyboardButton(f"{emoji} x{val}", callback_data="none"))
        result_keyboard.append(row)

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=result_text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=result_keyboard)
        )
    except MessageNotModified:
        pass
    except MessageToEditNotFound:
        logging.warning(f"Message with ID {message_id} not found for result.")
    except Exception:
        logging.exception("Ошибка при редактировании сообщения результата сундуков")

    try:
        await bot.answer_callback_query(callback_query.id)
    except TelegramError:
        pass


# Добавляем колонку description в users, если ее нет
def ensure_description_column():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'description' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN description TEXT DEFAULT ''")
        conn.commit()
        logging.info("Added 'description' column to the 'users' table.")
    close_db_connection(conn)

ensure_description_column()

# --- Глобальные переменные ---
balance_protection_disabled = False

# --- Функции работы с балансом ---
async def update_user_balance(user_id, amount):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    close_db_connection(conn)

async def safe_update_user_balance(user_id: int, amount: int, *, ignore_loss_tracking=False) -> bool:
    """
    Безопасное обновление баланса.
    - amount < 0 — списание.
    - ignore_loss_tracking=True — списание не учитывается как проигрыш.
    Возвращает True, если списание прошло, False — если заблокировано.
    """
    global balance_protection_disabled

    if amount < 0:
        if balance_protection_disabled:
            # Защита отключена, списываем без учёта проигранных
            await update_user_balance(user_id, amount)
            return True

        if ignore_loss_tracking:
            # Списание без учёта проигранных
            await update_user_balance(user_id, amount)
            return True

        # Защита включена, списание считается проигрышем — проверяем баланс и обновляем
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        if not res or res[0] < (-amount):
            close_db_connection(conn)
            return False  # Недостаточно средств

        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        cursor.execute("UPDATE users SET losses = COALESCE(losses, 0) + ? WHERE user_id = ?", (-amount, user_id))
        conn.commit()
        close_db_connection(conn)
        return True
    else:
        # Пополнение всегда разрешено
        await update_user_balance(user_id, amount)
        return True

# --- Создание пользователя если нет ---
async def create_user(user_id, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    registration_date = datetime.now().isoformat()  # Фиксируем дату регистрации ТОЛЬКО при создании
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, balance, has_taxi, taxi_last_used, losses, description, registration_date) "
        "VALUES (?, ?, 0, 0, NULL, 0, '', ?)",
        (user_id, username, registration_date)
    )
    conn.commit()
    close_db_connection(conn)

# --- Команда "пинг" ---
@dp.message_handler(Text(equals="пинг", ignore_case=True))
async def ping_command(message: types.Message):
    user_id = message.from_user.id
    user_username = message.from_user.username or message.from_user.first_name
    
    # Создаем пользователя, если его нет
    await create_user(user_id, user_username)
    
    # Проверяем, забанен ли пользователь
    if await is_user_banned(user_id):
        await message.reply("❌ Вы забанены и не можете использовать эту команду.")
        return
    
    try:
        # Засекаем время отправки
        start_time = time.time()
        
        # Отправляем тестовое сообщение
        sent_message = await message.reply("💭 Измеряю пинг...")
        
        # Вычисляем время ответа (пинг)
        end_time = time.time()
        ping_time = round((end_time - start_time) * 1000)  # В миллисекундах
        
        # Форматируем ответ
        response = f"💭| пинг-понг составляет: {hbold(ping_time)}ms"
        
        # Редактируем исходное сообщение с результатом
        await bot.edit_message_text(
            chat_id=sent_message.chat.id,
            message_id=sent_message.message_id,
            text=response,
            parse_mode=types.ParseMode.HTML
        )
        
    except Exception as e:
        logging.error(f"Ошибка в ping_command: {e}")
        await message.reply("❌|| Не удалось измерить пинг. Попробуйте позже.")


# --- Команда "выбери от X до Y" ---
@dp.message_handler(lambda message: 'выбери от' in message.text.lower() and 'до' in message.text.lower())
async def choose_number_range(message: types.Message):
    user_id = message.from_user.id
    user_username = message.from_user.username or message.from_user.first_name
    
    await create_user(user_id, user_username)
    
    if await is_user_banned(user_id):
        await message.reply("❌|| Вы забанены и не можете использовать эту команду.")
        return
    
    try:
        # Удаляем лишние пробелы и приводим к нижнему регистру
        text = ' '.join(message.text.lower().split())
        
        # Проверяем базовую структуру команды
        if not text.startswith('выбери от') or ' до ' not in text:
            raise ValueError("Неправильный формат команды")
        
        # Извлекаем части между "от" и "до"
        parts = text.split()
        from_index = parts.index('от') + 1
        to_index = parts.index('до')
        
        if from_index >= to_index:
            raise ValueError("Не найдены числа")
            
        num1_str = parts[from_index]
        num2_str = parts[to_index + 1]
        
        # Пробуем преобразовать в числа (учтём разные форматы)
        num1 = int(num1_str.replace('.', '').replace(',', ''))
        num2 = int(num2_str.replace('.', '').replace(',', ''))
        
        if num1 >= num2:
            await message.reply(
                "❌|| Первое число должно быть меньше второго!\n"
                "Пример ввода: выбери от 1 до 10"
            )
            return
            
        chosen_number = random.randint(num1, num2)
        await message.reply(f"🎲| Я выбираю {hbold(chosen_number)}", parse_mode=types.ParseMode.HTML)
        
    except ValueError:
        await message.reply(
            "❌|| Вы ввели не числа или неправильный формат команды!\n"
            "Пример ввода: выбери от 1 до 10\n"
            "Или: выбери от 5 до 100"
        )
    except Exception as e:
        logging.error(f"Ошибка в choose_number_range: {e}")
        await message.reply("❌|| Произошла ошибка при обработке команды. Попробуйте позже.")

# --- Константы игры ---
MIN_STAKE_MINES = 100
FIELD_SIZE = 25        # общее число клеток (5x5)
GRID_SIDE = 5          # сторона поля (для расчётов множителя)
NUMBER_OF_MINES = 5    # значение по умолчанию (перезапишется после выбора)
DEFAULT_COEFFICIENT = 1.0
COMMAND_COOLDOWN = 2  # Пример кулдауна (в секундах)

last_use_mines = {}  # Для кулдауна
claimed_games = {}  # Защита от повторного забора приза

# --- Таблица базовых множителей ---
BASE_MULTIPLIERS = [
    0.93, 1.01, 1.03, 1.08, 1.13, 1.19, 1.25, 1.32, 1.40, 1.48, 1.58,
    1.70, 1.83, 1.98, 2.16, 2.37, 2.64, 2.97, 3.39, 3.96,
    4.75, 5.94, 7.92, 11.87, 23.75
]



# --- Утилита для ссылки на профиль (HTML), использует first_name (display name) ---
def make_user_link_html(user_id: int, display_name: str) -> str:
    safe_name = html.escape(display_name or "User")
    return f'<a href="tg://user?id={user_id}"><b>{safe_name}</b></a>'

# --- Расчёт множителя ---
def calculate_multiplier(opened_cells_count: int, num_mines: int, total_cells: int = FIELD_SIZE) -> float:
    if opened_cells_count == total_cells - 1:
        return BASE_MULTIPLIERS[-1]
    idx = min(opened_cells_count, len(BASE_MULTIPLIERS) - 1)
    multiplier = BASE_MULTIPLIERS[idx]
    if num_mines == 2:
        multiplier += opened_cells_count * 0.08
    elif num_mines == 3:
        multiplier += opened_cells_count * 0.14
    elif num_mines == 6:
        multiplier += opened_cells_count * 0.17
    elif num_mines == 12:
        multiplier += opened_cells_count * 0.49
    return multiplier

# --- Функция для создания клавиатуры игры в мины ---
def create_mines_keyboard(user_id, game_id, field_size, opened_cells=None,
                          current_coefficient=DEFAULT_COEFFICIENT,
                          show_mines=False, has_opened_cells=False, mine_cell=None):
    if opened_cells is None:
        opened_cells = []

    keyboard = InlineKeyboardMarkup(row_width=5)
    buttons = []

    mines = []
    if show_mines:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT mines FROM mines_games WHERE game_id = ? AND user_id = ?", (game_id, user_id))
            game_data = cursor.fetchone()
            mines = list(map(int, game_data[0].split(','))) if game_data and game_data[0] else []
        except Exception as e:
            logging.exception(f"Ошибка при получении мин из БД: {e}")
            mines = []
        finally:
            close_db_connection(conn)

    for i in range(1, field_size + 1):
        if show_mines and i in mines:
            button_text = '💣'
        elif i in opened_cells:
            button_text = '💎'
        else:
            button_text = ' '

        if show_mines and mine_cell and i == mine_cell:
            button_text = '💣'

        button = InlineKeyboardButton(text=button_text, callback_data=f"mines_cell_{user_id}_{game_id}_{i}")
        buttons.append(button)

    keyboard.add(*buttons)

    if has_opened_cells and not show_mines:
        auto_button = InlineKeyboardButton(text="🔄 Автовыбор", callback_data=f"mines_auto_{user_id}_{game_id}")
        claim_button = InlineKeyboardButton(text="✅ Забрать", callback_data=f"mines_claim_{user_id}_{game_id}")
        keyboard.add(auto_button, claim_button)
    elif not show_mines:
        auto_button = InlineKeyboardButton(text="🔄 Автовыбор", callback_data=f"mines_auto_{user_id}_{game_id}")
        cancel_button = InlineKeyboardButton(text="❌ Отмена", callback_data=f"mines_cancel_{user_id}_{game_id}")
        keyboard.add(auto_button, cancel_button)

    return keyboard

# --- Клавиатура выбора кол-ва мин ---
def build_mines_choice_keyboard(user_id, game_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("1 мина 💣", callback_data=f"mines_choose_{user_id}_{game_id}_1"),
            InlineKeyboardButton("2 мины 💣", callback_data=f"mines_choose_{user_id}_{game_id}_2"),
            InlineKeyboardButton("3 мины 💣", callback_data=f"mines_choose_{user_id}_{game_id}_3")
        ],
        [
            InlineKeyboardButton("6 мин 💣", callback_data=f"mines_choose_{user_id}_{game_id}_6"),
            InlineKeyboardButton("12 мин 💣", callback_data=f"mines_choose_{user_id}_{game_id}_12")
        ]
    ])

# --- Обработчик команды "мины" ---
@dp.message_handler(Text(startswith=("мины"), ignore_case=True))
async def mines_handler(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or message.from_user.username or "Игрок"

    await create_user(user_id, first_name)

    if not await is_command_allowed(user_id):
        return

    if last_use_mines.get(user_id):
        if time.time() - last_use_mines[user_id] < COMMAND_COOLDOWN:
            return await message.reply('❌ Подождите немного перед новой игрой в мины!')
    last_use_mines[user_id] = time.time()

    arg = message.text.split()[1:]
    if len(arg) == 0:
        return await message.reply('❌ Ошибка. Используйте: <code>мины {<i>ставка</i>}</code>', parse_mode=ParseMode.HTML)

    stake_str = arg[0].lower()
    user_balance = await get_user_balance(user_id)

    # Обработка "все" и числовой ставки отдельно, с нормализацией
    if stake_str == "все":
        if user_balance < MIN_STAKE_MINES:
            return await message.reply(f"❌ Минимальная ставка: {format_number(MIN_STAKE_MINES)} Spark🦎")
        stake = user_balance
    else:
        stake = format_stake(stake_str)
        if stake is None:
            return await message.reply('❌ Ошибка. Неверный формат ставки.')
        if stake <= 0:
            return await message.reply('❌ Ошибка. Ставка должна быть больше нуля.')
        if stake < MIN_STAKE_MINES:
            return await message.reply(f"❌ Минимальная ставка: {format_number(MIN_STAKE_MINES)} Spark🦎")

    # Повторная проверка баланса (в случае concurrent изменений)
    user_balance = await get_user_balance(user_id)
    if user_balance < stake:
        return await message.reply('❌ Ошибка. Недостаточно средств на балансе.')

    success = await safe_update_user_balance(user_id, -stake)
    if not success:
        return await message.reply('❌ Ошибка при списании ставки. Попробуйте позже.')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO mines_games (user_id, field, stake, mines, opened_cells, coefficient, game_over, claimed) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, str(FIELD_SIZE), stake, '', '', DEFAULT_COEFFICIENT, 0, False)
        )
        try:
            game_id = cursor.lastrowid
        except Exception:
            game_id = 0
        conn.commit()
    except Exception as e:
        logging.exception(f"Ошибка при создании игры в БД: {e}")
        await message.reply("❌ Произошла ошибка при создании игры. Попробуйте позже.")
        try:
            await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
        except Exception:
            logging.exception("Ошибка при возврате ставки после ошибки создания игры в mines_handler")
        return
    finally:
        close_db_connection(conn)

    keyboard = build_mines_choice_keyboard(user_id, game_id)
    user_link = make_user_link_html(user_id, first_name)

    text = f"✅|| {user_link} ваша игра в мины началась!\n"
    text += "<code>·····················</code>\n"
    text += f"💰Ваша ставка:\n<b>{format_number(stake)}</b> Spark🦎\n"
    text += "<code>·····················</code>\n"
    text += "📌Выберите количество мин:"

    await message.reply(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

    await update_last_command_time(user_id)

# --- Обработчик колбэков игры в мины ---
@dp.callback_query_handler(lambda query: query.data and query.data.startswith("mines_"))
async def mines_callback_handler(query: types.CallbackQuery):
    callback_parts = query.data.split("_")
    if len(callback_parts) < 3:
        await query.answer("Ошибка данных", show_alert=True)
        return

    action = callback_parts[1]
    try:
        user_id_from_cb = int(callback_parts[2])
        game_id = int(callback_parts[3]) if len(callback_parts) >= 4 else None
    except Exception:
        await query.answer("Ошибка данных", show_alert=True)
        return

    if user_id_from_cb != query.from_user.id:
        await query.answer("❌|| Не жми на чужие кнопки!", show_alert=True)
        return

    await query.answer()

    if action == 'cell':
        if len(callback_parts) < 5:
            return await query.answer("Ошибка данных клетки", show_alert=True)
        cell_index = int(callback_parts[4])
        await process_cell_selection(query, user_id_from_cb, game_id, cell_index)
    elif action == 'auto':
        await process_auto_select(query, user_id_from_cb, game_id)
    elif action == 'claim':
        await process_claim(query, user_id_from_cb, game_id)
    elif action == 'cancel':
        await process_cancel(query, user_id_from_cb, game_id)
    elif action == 'choose':
        if len(callback_parts) < 5:
            return await query.answer("Ошибка данных выбора мин", show_alert=True)
        try:
            chosen_num = int(callback_parts[4])
        except Exception:
            return await query.answer("Неверный выбор мин", show_alert=True)

        mines = random.sample(range(1, FIELD_SIZE + 1), chosen_num)
        mines_str = ','.join(map(str, mines))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE mines_games SET mines = ?, coefficient = ? WHERE game_id = ? AND user_id = ?",
                           (mines_str, DEFAULT_COEFFICIENT, game_id, user_id_from_cb))
            conn.commit()
        except Exception as e:
            logging.exception(f"Ошибка при записи выбранных мин в БД: {e}")
            await query.answer("Ошибка при создании мин. Попробуйте ещё.", show_alert=True)
            return
        finally:
            close_db_connection(conn)

        keyboard = create_mines_keyboard(user_id_from_cb, game_id, FIELD_SIZE)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT stake FROM mines_games WHERE game_id = ? AND user_id = ?", (game_id, user_id_from_cb))
            row = cursor.fetchone()
            stake_saved = row[0] if row else 0
        except Exception:
            stake_saved = 0
        finally:
            close_db_connection(conn)

        first_name_cb = query.from_user.first_name or query.from_user.username or "Игрок"
        user_link = make_user_link_html(user_id_from_cb, first_name_cb)

        text = f"🎮|| {user_link} ваша игра в мины:\n"
        text += "<code>·····················</code>\n"
        text += f"💰Ваша ставка:\n<b>{format_number(stake_saved)}</b> Spark🦎\n"
        text += "<code>·····················</code>\n"
        text += f"💣Кол- во мин : {chosen_num}\n"
        text += "<code>·····················</code>\n"
        text += f"🔰Ваш x: {DEFAULT_COEFFICIENT:.2f}"

        try:
            await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        except Exception:
            logging.exception("Ошибка при редактировании сообщения после выбора мин")
        return

# --- Обработка выбора ячейки ---
async def process_cell_selection(query: types.CallbackQuery, user_id: int, game_id: int, cell_index: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT stake, mines, opened_cells, coefficient, game_over FROM mines_games WHERE game_id = ? AND user_id = ?", (game_id, user_id))
        game_data = cursor.fetchone()

        if not game_data:
            await query.answer("Игра не найдена!")
            return

        stake, mines_str, opened_cells_str, coefficient, game_over = game_data

        if game_over:
            await query.answer("Игра уже завершена!")
            return

        mines = list(map(int, mines_str.split(','))) if mines_str else []
        opened_cells = list(map(int, opened_cells_str.split(','))) if opened_cells_str else []

        if cell_index in opened_cells:
            await query.answer("Эта клетка уже открыта!")
            return

        opened_cells.append(cell_index)
        opened_cells_str = ','.join(map(str, opened_cells))
        has_opened_cells = True

        if cell_index in mines:
            try:
                cursor.execute("UPDATE mines_games SET game_over = 1, opened_cells = ? WHERE game_id = ?", (opened_cells_str, game_id))
                conn.commit()
            except Exception:
                logging.exception("Ошибка при обновлении статуса игры в БД (проигрыш)")

            try:
                await increment_games_played(user_id, 1)
                await add_loss_record(user_id, int(stake))
            except Exception:
                logging.exception("Ошибка при обновлении статистики после поражения в минах")

            keyboard = create_mines_keyboard(user_id, game_id, FIELD_SIZE, opened_cells, current_coefficient=coefficient, show_mines=True, has_opened_cells=False, mine_cell=cell_index)

            text = "💥|| Вы попались на мину!\n❌|| Вы проиграли!"
            try:
                await query.message.edit_text(text, reply_markup=keyboard)
            except Exception:
                logging.exception("Ошибка при редактировании сообщения при проигрыше в минах")
            return
        else:
            num_mines = len(mines) if mines else NUMBER_OF_MINES
            opened_count = len(opened_cells)
            new_coefficient = calculate_multiplier(opened_count, num_mines, FIELD_SIZE)
            new_coefficient = round(new_coefficient, 6)
            try:
                cursor.execute("UPDATE mines_games SET opened_cells = ?, coefficient = ? WHERE game_id = ?", (opened_cells_str, new_coefficient, game_id))
                conn.commit()
            except Exception:
                logging.exception("Ошибка при обновлении данных игры в БД (успешное открытие)")

            first_name_msg = query.from_user.first_name or query.from_user.username or "Игрок"
            user_link = make_user_link_html(user_id, first_name_msg)

            text = f"🎮|| {user_link} ваша игра в мины:\n"
            text += "\n"
            text += f"💰Ваша ставка:\n<b>{format_number(stake)}</b> Spark🦎\n"
            text += "<code>·····················</code>\n"
            text += f"💣Кол- во мин : {num_mines}\n"
            text += "<code>·····················</code>\n"
            text += f"🔰Ваш x : {new_coefficient:.2f}"

            keyboard = create_mines_keyboard(user_id, game_id, FIELD_SIZE, opened_cells, current_coefficient=new_coefficient, has_opened_cells=True)
            try:
                await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            except Exception:
                logging.exception("Ошибка при редактировании сообщения после открытия клетки в минах")
            return

    except Exception as e:
        logging.exception(f"Ошибка при обработке ячейки: {e}")
        await query.answer("Произошла ошибка при обработке ячейки. Попробуйте позже.")
    finally:
        close_db_connection(conn)

# --- Автовыбор ---
async def process_auto_select(query: types.CallbackQuery, user_id: int, game_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT mines, opened_cells, game_over FROM mines_games WHERE game_id = ? AND user_id = ?", (game_id, user_id))
        game_data = cursor.fetchone()

        if not game_data:
            await query.answer("Игра не найдена!")
            return

        mines_str, opened_cells_str, game_over = game_data

        if game_over:
            await query.answer("Игра уже завершена!")
            return

        mines = list(map(int, mines_str.split(','))) if mines_str else []
        opened_cells = list(map(int, opened_cells_str.split(','))) if opened_cells_str else []

        closed_cells = [i for i in range(1, FIELD_SIZE + 1) if i not in opened_cells]

        if not closed_cells:
            await query.answer("Все клетки уже открыты!")
            return

        cell_index = random.choice(closed_cells)

        await process_cell_selection(query, user_id, game_id, cell_index)
    except Exception as e:
        logging.exception(f"Ошибка при автовыборе: {e}")
        await query.answer("Произошла ошибка при автовыборе. Попробуйте позже.")
    finally:
        close_db_connection(conn)

# --- Забрать выигрыш ---
async def process_claim(query: types.CallbackQuery, user_id: int, game_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT stake, coefficient, claimed, opened_cells FROM mines_games WHERE game_id = ? AND user_id = ?", (game_id, user_id))
        game_data = cursor.fetchone()

        if not game_data:
            await query.answer("Игра не найдена!")
            return

        stake, coefficient, claimed, opened_cells_str = game_data

        if claimed:
            await query.answer("❌|| Вы уже забрали приз!", show_alert=True)
            return

        has_opened_cells = bool(opened_cells_str)

        if not has_opened_cells:
            await query.answer("Нужно открыть хотя бы одну ячейку, чтобы забрать выигрыш!", show_alert=True)
            return

        winning_amount = int(round(stake * coefficient))

        try:
            await update_user_balance(user_id, winning_amount)
        except Exception:
            logging.exception("Ошибка при зачислении выигрыша в process_claim")

        try:
            cursor.execute("UPDATE mines_games SET claimed = 1, game_over = 1 WHERE game_id = ?", (game_id,))
            conn.commit()
        except Exception:
            logging.exception("Ошибка при пометке claimed в БД (process_claim)")

        try:
            await increment_games_played(user_id, 1)
            await add_win_record(user_id, int(winning_amount))
        except Exception:
            logging.exception("Ошибка при обновлении статистики после взятия выигрыша в минах")

        try:
            await query.message.edit_text(f"✅ Вы забрали свой выигрыш:\n+{format_number(winning_amount)} Spark🦎!", reply_markup=None)
        except Exception:
            logging.exception("Ошибка при редактировании сообщения в process_claim")

    except Exception as e:
        logging.exception(f"Ошибка при заборе приза: {e}")
        await query.answer("Произошла ошибка при обработке вашего запроса. Попробуйте позже.", show_alert=True)
    finally:
        close_db_connection(conn)

# --- Отмена игры ---
async def process_cancel(query: types.CallbackQuery, user_id: int, game_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT stake, claimed FROM mines_games WHERE game_id = ? AND user_id = ?", (game_id, user_id))
        game_data = cursor.fetchone()

        if not game_data:
            await query.answer("Игра не найдена!")
            return

        stake, claimed = game_data

        if claimed:
            await query.answer("Вы уже забрали приз, отмена невозможна!")
            return

        try:
            await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
        except Exception:
            logging.exception("Ошибка при возврате ставки в process_cancel")

        try:
            cursor.execute("DELETE FROM mines_games WHERE game_id = ?", (game_id,))
            conn.commit()
        except Exception:
            logging.exception("Ошибка при удалении записи игры из БД (process_cancel)")

        try:
            await query.message.edit_text(f"❌|| Игра отменена. Ваша ставка: {format_number(stake)} Spark🦎 возвращена на баланс.", reply_markup=None)
        except Exception:
            logging.exception("Ошибка при редактировании сообщения в process_cancel")
    except Exception as e:
        logging.exception(f"Ошибка при отмене игры: {e}")
        await query.answer("Произошла ошибка при отмене игры. Попробуйте позже.")
    finally:
        close_db_connection(conn)

@dp.message_handler(Text(equals=".анлокбал", ignore_case=True))
async def unlock_balance_handler(message: types.Message):
    user_id = message.from_user.id

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET hide_balance = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    close_db_connection(conn)

    await message.reply("🔓| Ваш баланс снова доступен игрокам!")


@dp.message_handler(Text(equals=".чекбал", ignore_case=True), content_types=types.ContentTypes.ANY)
async def check_balance_handler(message: types.Message):
    if not message.reply_to_message:
        return await message.reply("❌ Необходимо ответить на сообщение пользователя, чей баланс вы хотите узнать.")

    target_user = message.reply_to_message.from_user
    target_user_id = target_user.id
    target_username = target_user.first_name

    # Проверяем, скрыт ли баланс пользователя
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT hide_balance FROM users WHERE user_id = ?", (target_user_id,))
    result = cursor.fetchone()
    close_db_connection(conn)

    if result and result[0] == 1:
        return await message.reply("🔐| Данный пользователь запретил просмотр его баланса!")

    balance = await get_user_balance(target_user_id)
    formatted_balance = format_number(balance)

    await message.reply(
        f"💳|Баланс пользователя {hbold(target_username)} равен: {hbold(formatted_balance)} Spark🦎|💳",
        parse_mode=ParseMode.HTML
    )


@dp.message_handler(Text(equals=".локбал", ignore_case=True))
async def lock_balance_handler(message: types.Message):
    user_id = message.from_user.id

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET hide_balance = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    close_db_connection(conn)

    await message.reply("✅| Ваш баланс успешно скрыт от чужих глаз!")


# --- Параметры / состояние ---
last_use = {}
values = {
    2: [32, 6, 62, 4, 2, 49, 59, 48, 63, 44, 38, 21, 32, 16, 3, 23, 44, 54, 27, 33,
        42, 11, 41, 13, 24, 17],
    3: [43, 11, 22]
}

# Минимальная ставка
MIN_STAKE_SPIN = 100
# Кулдаун для команды (используется в is_command_allowed/last_use)
COMMAND_COOLDOWN = 2

# --- Обработчик команды "спин" ---
@dp.message_handler(Text(startswith=("спин"), ignore_case=True))
async def spin_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Создаём пользователя в БД, если нужно
    try:
        await create_user(user_id, username)
    except Exception:
        logging.exception("Ошибка при create_user в spin_handler")

    # Проверка разрешения команды (кулдаун, бан и т.п.)
    try:
        if not await is_command_allowed(user_id):
            return
    except Exception:
        # Если вспомогательная функция упала — не мешаем пользователю играть
        logging.exception("Ошибка в is_command_allowed, продолжаем")

    # Дополнительный локальный кулдаун
    last_ts = last_use.get(user_id)
    if last_ts and time.time() - last_ts < COMMAND_COOLDOWN:
        try:
            await message.reply('❌ Подождите пока закончится прошлая игра❗️')
        except Exception:
            pass
        return
    last_use[user_id] = time.time()

    # Парсим аргумент ставки
    arg = message.text.split()[1:]
    if len(arg) == 0:
        return await message.reply('❌ Ошибка. Используйте: <code>спин {<i>ставка</i>}</code>', parse_mode=types.ParseMode.HTML)

    # Обработка ставки
    stake_str = arg[0].strip().lower()
    stake = None
    try:
        if stake_str in ['всё', 'все', 'всё!']:
            stake = await get_user_balance(user_id)
        else:
            # Попробуем использовать вашу функцию форматирования ставок (format_stake)
            temp = format_stake(stake_str)
            if temp is None:
                # fallback: попытка перевести напрямую в int
                stake = int(stake_str)
            else:
                stake = int(temp)
    except Exception:
        logging.exception("Ошибка при разборе ставки в spin_handler")
        return await message.reply('❌ Ошибка. Неверный формат ставки.')

    if not isinstance(stake, int) or stake <= 0:
        return await message.reply('❌ Ошибка. Ставка должна быть больше нуля.')

    # Проверка минимальной ставки
    if stake < MIN_STAKE_SPIN:
        return await message.reply(f"❌ Минимальная ставка: {format_number(MIN_STAKE_SPIN)} Spark🦎")

    # Проверяем баланс
    try:
        user_balance = await get_user_balance(user_id)
    except Exception:
        logging.exception("Ошибка при получении баланса в spin_handler")
        return await message.reply("❌ Ошибка при проверке баланса. Попробуйте позже.")

    if user_balance < stake:
        return await message.reply('❌ Ошибка. Недостаточно средств на балансе.')

    # Снимаем ставку — используем safe_update_user_balance для надежности
    try:
        success = await safe_update_user_balance(user_id, -stake)
    except Exception:
        logging.exception("Ошибка safe_update_user_balance при списании ставки в spin_handler")
        success = False

    if not success:
        return await message.reply('❌ Ошибка при списании ставки. Попробуйте позже.')

    # Отправляем анимированный спин (dice)
    try:
        casino_msg = await message.reply_dice(emoji='🎰')
        casino = casino_msg.dice
    except Exception:
        # Если не получилось отправить анимацию — всё равно симулируем случайное значение
        logging.exception("Ошибка при отправке/получении dice в spin_handler, делаем случайный результат")
        class _Dice: value = random.randint(1, 64)
        casino = _Dice()

    # Результат и начисления
    win_amount = 0
    won = False

    try:
        if casino.value in values.get(2, []):
            # небольшой выигрыш x1.2 (засчитанная сумма win_amount)
            win_amount = int(stake * 1.2)
            won = True
        elif casino.value in values.get(3, []):
            win_amount = int(stake * 1.3)
            won = True
        elif casino.value == 64:
            win_amount = int(stake * 1.6)
            won = True
        else:
            won = False
    except Exception:
        logging.exception("Ошибка при определении исхода спина")
        won = False

    if won and win_amount > 0:
        # Начисляем выигрыш
        try:
            await safe_update_user_balance(user_id, win_amount)
        except Exception:
            logging.exception("Ошибка при начислении выигрыша в spin_handler")

        # Обновляем статистику: сыграна игра и выигрыш
        try:
            await increment_games_played(user_id, 1)
            await add_win_record(user_id, int(win_amount))
        except Exception:
            logging.exception("Ошибка при обновлении статистики после выигрыша в спин")

        # Сообщение пользователю
        try:
            formatted_win_amount = format_number(win_amount)
            if casino.value in values.get(2, []):
                await message.reply(f'🎰 Вы не очень удачно прокрутили спин, но выиграли: +{hbold(formatted_win_amount)} Spark🦎 ❗️', parse_mode=types.ParseMode.HTML)
            elif casino.value in values.get(3, []):
                await message.reply(f'🎰 Вы достаточно удачно прокрутили спин и выиграли: +{hbold(formatted_win_amount)} Spark🦎 ❗️', parse_mode=types.ParseMode.HTML)
            else:
                await message.reply(f'🎰 Вы очень удачно прокрутили спин и выиграли: +{hbold(formatted_win_amount)} Spark🦎 ❗️', parse_mode=types.ParseMode.HTML)
        except Exception:
            logging.exception("Ошибка при отправке сообщения о выигрыше в spin_handler")
    else:
        # Проигрыш (ставка уже списана ранее)
        try:
            await increment_games_played(user_id, 1)
            await add_loss_record(user_id, int(stake))
        except Exception:
            logging.exception("Ошибка при обновлении статистики после проигрыша в спин")

        try:
            formatted_stake = format_number(stake)
            await message.reply(f'❌ Вам ничего не выпало, и вы проиграли: {hbold(formatted_stake)} Spark🦎 ❗️', parse_mode=types.ParseMode.HTML)
        except Exception:
            logging.exception("Ошибка при отправке сообщения о проигрыше в spin_handler")

    # Обновляем время последней успешной команды (если у вас есть такая логика)
    try:
        await update_last_command_time(user_id)
    except Exception:
        logging.exception("Ошибка при update_last_command_time в spin_handler")


async def reset_all_banks():
    """Обнуляет балансы всех пользователей в банке."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE bank_accounts SET balance = 0")
    conn.commit()
    close_db_connection(conn)

@dp.message_handler(Text(equals="-банки", ignore_case=True))
async def reset_banks_command(message: types.Message):
    user_id = message.from_user.id

    """Обработчик команды для обнуления всех банков."""
    if user_id not in OWNER_IDS:  # Только для владельца бота
        await message.reply("Вы не владелец бота.")
        return

    try:
        await reset_all_banks()
        await message.reply("Все банки были успешно обнулены.")
    except sqlite3.Error as e:
        await message.reply(f"Произошла ошибка при обнулении банков: {e}")

# -------------------- Фишки (Красное/Синее) --------------------
MIN_STAKE_FS = 100
COMMAND_COOLDOWN = 1
last_use = {}

@dp.message_handler(Text(startswith=("фишки"), ignore_case=True))
async def chips_command(message: types.Message):
    """Обработчик команды 'фишки' (ставка + выбор цвета)."""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Создаём пользователя если нужно (не жмём ошибку если упадёт)
    try:
        await create_user(user_id, username)
    except Exception:
        logging.exception("create_user в chips_command упал, продолжаем")

    # Проверка разрешения команды (кулдаун, бан и т.п.)
    try:
        if not await is_command_allowed(user_id):
            return
    except Exception:
        logging.exception("is_command_allowed упала в chips_command — продолжаем")

    # Локальный простой кулдаун
    last_ts = last_use.get(user_id)
    if last_ts and time.time() - last_ts < COMMAND_COOLDOWN:
        try:
            await message.reply("❌ Подождите немного перед новой игрой.")
        except Exception:
            pass
        return
    last_use[user_id] = time.time()

    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.reply("❌ Используйте: фишки (ставка) (красный/синий/к/с)")
            return

        stake_str = parts[1].strip().lower()
        color_choice = parts[2].strip().lower()

        # Разбор ставки: поддерживаем "все/всё" и формат_stake
        if stake_str in ("все", "всё"):
            try:
                stake = await get_user_balance(user_id)
            except Exception:
                logging.exception("Ошибка получения баланса при 'все' в chips_command")
                await message.reply("❌ Ошибка при получении баланса. Попробуйте позже.")
                return
            if stake <= 0:
                await message.reply("❌ На вашем балансе нет средств для ставки.")
                return
        else:
            # format_stake должен возвращать int или None
            try:
                parsed = format_stake(stake_str)
            except Exception:
                parsed = None
            if parsed is None:
                await message.reply("❌ Неверный формат суммы. Используйте число или сокращение (1к, 1kk).")
                return
            try:
                stake = int(parsed)
            except Exception:
                await message.reply("❌ Неверный формат суммы.")
                return

        # Проверка минимальной ставки
        if stake < MIN_STAKE_FS:
            await message.reply(f"❌ Минимальная ставка: {format_number(MIN_STAKE_FS)} Spark🦎")
            return

        # Проверка баланса
        try:
            user_balance = await get_user_balance(user_id)
        except Exception:
            logging.exception("Ошибка при получении баланса в chips_command")
            await message.reply("❌ Ошибка при проверке баланса. Попробуйте позже.")
            return

        if user_balance < stake:
            await message.reply("❌ Недостаточно средств на балансе.")
            return

        # Обработка выбора цвета
        if color_choice in ('красный', 'к'):
            user_choice = "красный"
            user_choice_emoji = "🔴"
        elif color_choice in ('синий', 'с'):
            user_choice = "синий"
            user_choice_emoji = "🔵"
        else:
            await message.reply("❌ Неверный выбор цвета. Используйте: красный/синий/к/с")
            return

        # Генерация случайного цвета
        winning_color = random.choice(["красный", "синий"])
        winning_color_emoji = "🔴" if winning_color == "красный" else "🔵"

        # Списание ставки — используем safe_update_user_balance для надёжности
        try:
            success = await safe_update_user_balance(user_id, -stake)
        except Exception:
            logging.exception("Ошибка при списании ставки в chips_command")
            success = False

        if not success:
            await message.reply("❌ Не удалось списать ставку. Попробуйте позже.")
            return

        # Результат
        # Результат
        if user_choice == winning_color:
            # Выигрыш: умножаем ставку на 1.94
            win_amount = int(stake * 1.94)  # округляем до целого числа
            try:
                await safe_update_user_balance(user_id, win_amount)
            except Exception:
                logging.exception("Ошибка при начислении выигрыша в chips_command")

            # Обновляем статистику: +1 игра, +win
            try:
                await increment_games_played(user_id, 1)
                await add_win_record(user_id, int(win_amount))
            except Exception:
                logging.exception("Ошибка при обновлении статистики после выигрыша в chips_command")

            formatted_win = format_number(win_amount)
            await message.reply(
                f"Вы загадали <b>{user_choice.capitalize()} {user_choice_emoji}</b>, а вам выпал <b>{winning_color.capitalize()} {winning_color_emoji}</b>!\n"
                f"✅ Вы угадали и выиграли: +<b>{formatted_win}</b> Spark🦎",
                parse_mode=ParseMode.HTML
            )

        else:
            # Проигрыш: ставка уже списана
            try:
                await increment_games_played(user_id, 1)
                await add_loss_record(user_id, int(stake))
            except Exception:
                logging.exception("Ошибка при обновлении статистики после поражения в chips_command")

            formatted_stake = format_number(stake)
            await message.reply(
                f"Вы загадали <b>{user_choice.capitalize()} {user_choice_emoji}</b>, а вам выпал <b>{winning_color.capitalize()} {winning_color_emoji}</b>!\n"
                f"❌ Вы не угадали и проиграли: <b>{formatted_stake}</b> Spark🦎",
                parse_mode=ParseMode.HTML
            )

        # Обновляем время последней команды (если реализовано)
        try:
            await update_last_command_time(user_id)
        except Exception:
            logging.exception("Ошибка при update_last_command_time в chips_command")

    except Exception as e:
        logging.exception(f"Непредвиденная ошибка в chips_command: {e}")
        await message.reply("❌ Произошла ошибка. Попробуйте позже.")
# -------------------- Фишки (Красное/Синее) --------------------

#-----------ВЫДАЧА--------------------------
@dp.message_handler(Text(startswith=("юдать"), ignore_case=True))
async def give_command(message: types.Message):
    """Выдача монет пользователю по ID (только для владельца)"""
    sender_id = message.from_user.id  # ID того, кто отправил команду

    # Проверка, является ли отправитель владельцем
    if sender_id not in OWNER_IDS:  # ✅ используем OWNER_IDS
        await message.reply("У вас нет прав на выполнение этой команды.")
        return

    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.reply("Используйте: юдать (сумма) (айди человека)")
            return

        stake_str = parts[1]
        receiver_id_str = parts[2]

        stake = format_stake(stake_str)
        if stake is None:
            await message.reply("Неверный формат суммы. Используйте число или сокращение (1к, 1кк).")
            return

        try:
            receiver_id = int(receiver_id_str)
        except ValueError:
            await message.reply("Неверный формат ID пользователя. Используйте число.")
            return

        # Получаем информацию о получателе (имя пользователя)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE user_id = ?", (receiver_id,))
        result = cursor.fetchone()
        close_db_connection(conn)

        if result:
            receiver_username = result[0] or "Неизвестный пользователь"
        else:
            receiver_username = "Неизвестный пользователь"

        # Обновляем баланс получателя
        await update_user_balance(receiver_id, stake)

        # Форматируем сумму для красивого отображения
        formatted_stake = "{:,}".format(stake).replace(",", ".")

        # Отправляем сообщение об успешной выдаче
        await message.reply(
            f"Владелец выдал пользователю 💼{receiver_username} (ID: {receiver_id}) деньги в размере: \n{formatted_stake} Spark🦎",
            parse_mode=types.ParseMode.HTML
        )

    except Exception as e:
        logging.error(f"Ошибка при выдаче денег: {e}")
        await message.reply("Произошла ошибка при выдаче денег. Попробуйте позже.")

#-----------ВЫДАЧА-----------------------
USERS_PER_PAGE = 30
# -------------------- Команды для владельца бота --------------------
async def generate_balances_page(page: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance FROM users")
    all_users = cursor.fetchall()
    close_db_connection(conn)

    if not all_users:
        return "В боте пока нет пользователей.", None

    total_pages = (len(all_users) - 1) // USERS_PER_PAGE + 1

    # Защита от выхода за границы
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    start = page * USERS_PER_PAGE
    end = start + USERS_PER_PAGE
    users_slice = all_users[start:end]

    text = f"💰 Балансы игроков\n"
    text += f"Страница {page+1} из {total_pages}\n\n"

    for user_id, username, balance in users_slice:
        username_display = f"@{username}" if username else f"ID:{user_id}"
        text += f"{username_display} — {format_number(balance)}\n"

    keyboard = InlineKeyboardMarkup(row_width=2)

    buttons = []
    if page > 0:
        buttons.append(
            InlineKeyboardButton("⬅️ Назад", callback_data=f"balances_{page-1}")
        )

    if page < total_pages - 1:
        buttons.append(
            InlineKeyboardButton("➡️ Вперёд", callback_data=f"balances_{page+1}")
        )

    if buttons:
        keyboard.row(*buttons)

    keyboard.add(
        InlineKeyboardButton("❌ Закрыть", callback_data="balances_close")
    )

    return text, keyboard

# ------------------ КОМАНДА ------------------

@dp.message_handler(
    lambda message: message.from_user.id in OWNER_IDS,
    Text(equals="дж", ignore_case=True)
)
async def show_all_balances(message: types.Message):
    text, keyboard = await generate_balances_page(0)
    await message.reply(text, reply_markup=keyboard)

# ------------------ ПАГИНАЦИЯ ------------------

@dp.callback_query_handler(Text(startswith="balances_"))
async def balances_pagination(callback: CallbackQuery):

    if callback.data == "balances_close":
        await callback.message.delete()
        await callback.answer()
        return

    page = int(callback.data.split("_")[1])
    text, keyboard = await generate_balances_page(page)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.message_handler(
    lambda message: message.from_user.id in OWNER_IDS,
    Text(startswith="Уснять", ignore_case=True)
)

async def withdraw_funds(message: types.Message):
    """Снимает деньги с баланса игрока, находя его по юзернейму."""
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.reply("Используйте: снять (сумма) (юзернейм)")
            return

        amount_str = parts[1]
        username = parts[2].replace("@", "")  # Убираем символ @ из юзернейма

        amount = format_stake(amount_str)
        if amount is None:
            await message.reply("Неверный формат суммы.")
            return

        if amount <= 0:
            await message.reply("Сумма должна быть больше 0.")
            return

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        user_data = cursor.fetchone()

        if not user_data:
            await message.reply("Пользователь с таким юзернеймом не найден.")
            close_db_connection(conn)
            return

        user_id = user_data[0]

        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        user_balance = cursor.fetchone()[0]

        if user_balance < amount:
            await message.reply("У пользователя недостаточно средств на балансе.")
            close_db_connection(conn)
            return
            
        await update_user_balance(user_id, -amount)
        
        close_db_connection(conn)
        await message.reply(f"Успешно снято {format_number(amount)} Spark🦎 с баланса @{username}.")
    
    except Exception as e:
        logging.error(f"Ошибка при снятии средств: {e}")
        await message.reply("Произошла ошибка при снятии средств. Попробуйте позже.")

# FSM состояния
class TakeKeyState(StatesGroup):
    waiting_for_stake = State()
    choosing_key = State()
    waiting_for_door = State()
    game_over = State()

# Словари для отслеживания активных игр и блокировок
active_games = {}   # {user_id: (message_id, chat_id, lock)}
game_locks = {}     # {user_id: asyncio.Lock()}

MIN_STAKE_GANDON = 100
GAME_TIMEOUT = 60  # сек

async def check_game_timeout(user_id: int, message_id: int, chat_id: int, state: FSMContext):
    """Проверяет таймаут игры и возвращает ставку, если игрок не ответил."""
    try:
        await asyncio.sleep(GAME_TIMEOUT)
        # Если игра всё ещё активна и message_id совпадает — таймаут
        if user_id in active_games and active_games[user_id][0] == message_id:
            data = await state.get_data()
            stake = data.get('stake')
            if stake:
                try:
                    # Возврат ставки без учета как проигрыш
                    await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
                except Exception:
                    logging.exception("Ошибка при возврате ставки в check_game_timeout")

                formatted_stake = format_number(stake)
                text = f"❌ Игра отменена по таймауту. Ставка : <b>{formatted_stake}</b> Spark🦎 возвращена на баланс."
                try:
                    await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode=types.ParseMode.HTML)
                except Exception:
                    logging.exception("Не удалось отредактировать сообщение по таймауту, пытаемся уведомить в лс")
                    try:
                        await bot.send_message(user_id, text, parse_mode=types.ParseMode.HTML)
                    except Exception:
                        logging.exception("Не удалось отправить уведомление пользователю о таймауте")

            # Завершаем FSM и очищаем данные
            try:
                await state.finish()
            except Exception:
                logging.exception("Ошибка при завершении состояния FSM в check_game_timeout")

            # Удаляем активную игру и блокировку (без попытки release)
            try:
                active_games.pop(user_id, None)
            except Exception:
                logging.exception("Ошибка при удалении active_games в check_game_timeout")

            try:
                # Удаляем ссылку на lock; сам lock при необходимости освободится автоматом, если кто-то держал его
                game_locks.pop(user_id, None)
            except Exception:
                logging.exception("Ошибка при удалении game_locks в check_game_timeout")
    except asyncio.CancelledError:
        logging.debug(f"Timeout task cancelled for user {user_id}")
    except Exception:
        logging.exception("Ошибка в check_game_timeout")

@dp.message_handler(Text(startswith=("тк", "Тк", "ТК"), ignore_case=True), state="*")
async def take_key_command(message: types.Message, state: FSMContext):
    """Начало игры Take Key."""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    try:
        await create_user(user_id, username)
    except Exception:
        logging.exception("create_user упал в take_key_command")

    # Проверка разрешения команды (кулдаун, бан, и т.д.)
    try:
        if not await is_command_allowed(user_id):
            return
    except Exception:
        logging.exception("is_command_allowed упал в take_key_command — продолжаем")

    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Используйте: тк (ставка)")
        return

    stake_str = parts[1]
    stake = format_stake(stake_str)
    if stake is None and stake_str.lower() != 'все':
        await message.reply("❌ Неверный формат ставки. Используйте число или сокращение (1к, 1кк).")
        return

    # Получаем баланс ДО списания
    try:
        user_balance = await get_user_balance(user_id)
    except Exception:
        logging.exception("Ошибка при получении баланса в take_key_command")
        await message.reply("❌ Ошибка при проверке баланса. Попробуйте позже.")
        return

    # Обрабатываем "все"
    if stake_str.lower() == 'все':
        if user_balance < MIN_STAKE_GANDON:
            await message.reply(f"❌ На вашем балансе недостаточно средств для игры. Минимальная ставка: {MIN_STAKE_GANDON}")
            return
        stake = user_balance
    else:
        if stake < MIN_STAKE_GANDON:
            await message.reply(f"❌ Минимальная ставка: {MIN_STAKE_GANDON}")
            return
        if user_balance < stake:
            await message.reply("❌ Недостаточно средств на балансе для игры.")
            return

    # Снимаем ставку (безопасно)
    try:
        success = await safe_update_user_balance(user_id, -stake)
    except Exception:
        logging.exception("Ошибка при списании ставки в take_key_command")
        success = False

    if not success:
        await message.reply("❌ Произошла ошибка при списании ставки. Попробуйте позже.")
        return

    # Сохраняем данные игры в FSM
    try:
        await state.update_data(stake=stake, game_starter_id=user_id, chosen_door=None)
    except Exception:
        logging.exception("Ошибка при записи данных в FSM в take_key_command")

    # Генерация ключей/правильной двери (ключи здесь для красоты — можно использовать иные механики)
    key1 = random.randint(1, 100)
    key2 = random.randint(1, 100)
    correct_door = random.randint(1, 3)
    try:
        await state.update_data(key1=key1, key2=key2, correct_door=correct_door, chosen_key=None)
    except Exception:
        logging.exception("Ошибка при записи ключей в FSM в take_key_command")

    formatted_stake = format_number(stake)
    try:
        current_balance = await get_user_balance(user_id)
    except Exception:
        logging.exception("Ошибка при получении баланса после списания в take_key_command")
        current_balance = None
    formatted_balance = format_number(current_balance) if current_balance is not None else "?"

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(text="Ключ #1🔑", callback_data="key_1"),
        InlineKeyboardButton(text="Ключ #2🔑", callback_data="key_2")
    )

    try:
        sent_message = await message.reply(
            "Вы начали игру в TAKE KEY!\n🔑\n"
            "------------------------\n"
            f"💰Ставка : <b>{formatted_stake}</b>\n"
            f"Ваш баланс: <b>{formatted_balance}</b> Spark🦎\n\n"
            "Бери 1 ключ из 2 предложенных 🔦",
            parse_mode=types.ParseMode.HTML,
            reply_markup=keyboard
        )
    except Exception:
        logging.exception("Ошибка при отправке стартового сообщения в take_key_command")
        # В случае ошибки возвращаем ставку
        try:
            await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
        except Exception:
            logging.exception("Ошибка при возврате ставки после ошибки отправки в take_key_command")
        return

    # Устанавливаем состояние и создаём lock
    await TakeKeyState.choosing_key.set()
    lock = asyncio.Lock()
    game_locks[user_id] = lock
    active_games[user_id] = (sent_message.message_id, sent_message.chat.id, lock)

    # Запускаем задачу таймаута
    try:
        task = asyncio.create_task(check_game_timeout(user_id, sent_message.message_id, sent_message.chat.id, state))
    except Exception:
        logging.exception("Не удалось запустить задачу таймаута в take_key_command")

@dp.callback_query_handler(lambda c: c.data.startswith("key_"), state=TakeKeyState.choosing_key)
async def choose_key(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработка выбора ключа."""
    user_id = callback_query.from_user.id
    data = await state.get_data()
    game_starter_id = data.get('game_starter_id')

    # Проверяем владельца игры
    if user_id != game_starter_id:
        await callback_query.answer("❌ Это не ваша игра!", show_alert=True)
        return

    key_number = int(callback_query.data.split("_")[1])  # 1 or 2
    chosen_key = data.get('key1') if key_number == 1 else data.get('key2')

    try:
        await state.update_data(chosen_key=chosen_key)
    except Exception:
        logging.exception("Ошибка при обновлении chosen_key в choose_key")

    try:
        await callback_query.message.edit_text(f"🚶‍➡️ Вы проходите в комнату выбора с ключем {key_number}....")
    except Exception:
        logging.exception("Не удалось отредактировать сообщение при выборе ключа")

    await callback_query.answer()
    # Удаляем запись о активной игре (переходим в следующий этап)
    active_games.pop(user_id, None)

    await asyncio.sleep(3)

    # Переходим к выбору двери
    keyboard = InlineKeyboardMarkup(row_width=3)
    keyboard.add(
        InlineKeyboardButton(text="🚪", callback_data="door_1"),
        InlineKeyboardButton(text="🚪", callback_data="door_2"),
        InlineKeyboardButton(text="🚪", callback_data="door_3")
    )

    try:
        await callback_query.message.edit_text(
            "Вы в комнате выбора!🕹\n"
            "-------------------------\n"
            "Перед вами 3 двери , но лишь одна дверь будет подходить под ваш ключ!\n"
            "-------------------------\n"
            "Выбирайте дверь!🪬",
            reply_markup=keyboard
        )
    except Exception:
        logging.exception("Не удалось отредактировать сообщение при переходе к выбору двери")

    await TakeKeyState.waiting_for_door.set()
    # Сохраняем активную игру снова с текущим message_id (чтобы таймаут работал)
    game_locks.setdefault(user_id, asyncio.Lock())
    active_games[user_id] = (callback_query.message.message_id, callback_query.message.chat.id, game_locks[user_id])
    try:
        asyncio.create_task(check_game_timeout(user_id, callback_query.message.message_id, callback_query.message.chat.id, state))
    except Exception:
        logging.exception("Не удалось запустить задачу таймаута после выбора ключа")

@dp.callback_query_handler(lambda c: c.data.startswith("door_"), state=TakeKeyState.waiting_for_door)
async def choose_door(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработка выбора двери."""
    user_id = callback_query.from_user.id
    data = await state.get_data()
    stake = data.get('stake')
    chosen_key = data.get('chosen_key')
    game_starter_id = data.get('game_starter_id')

    # Проверяем владельца игры
    if user_id != game_starter_id:
        await callback_query.answer("❌ Это не ваша игра!", show_alert=True)
        return

    # Защита от повторного выбора двери
    if data.get('chosen_door') is not None:
        await callback_query.answer("❌ Вы уже выбрали дверь!", show_alert=True)
        return

    # Получаем lock для этого пользователя
    lock = game_locks.get(user_id)
    if lock is None:
        await callback_query.answer("❌ Произошла ошибка. Попробуйте начать игру заново.", show_alert=True)
        return

    # Обрабатываем выбор внутри lock, чтобы избежать гонок
    try:
        async with lock:
            door_number = int(callback_query.data.split("_")[1])
            try:
                await state.update_data(chosen_door=door_number)
            except Exception:
                logging.exception("Ошибка при записи chosen_door в FSM")

            # Вероятности: 45% что выбранная дверь окажется 'правильной'
            doors = [1, 2, 3]
            probabilities = [0.45, 0.275, 0.275]
            correct_door = random.choices(doors, weights=probabilities, k=1)[0]

            # Удаляем активную игру (пользователь сделал выбор)
            active_games.pop(user_id, None)

            if door_number == correct_door:
                # Выигрыш
                win_multiplier = 2
                win = int(stake * win_multiplier)
                try:
                    await safe_update_user_balance(user_id, win)
                except Exception:
                    logging.exception("Ошибка при начислении выигрыша в choose_door")

                # Статистика: +1 игра и win
                try:
                    await increment_games_played(user_id, 1)
                    await add_win_record(user_id, int(win))
                except Exception:
                    logging.exception("Ошибка при обновлении статистики после выигрыша в Take Key")

                # Ответ пользователю
                try:
                    formatted_win = format_number(win)
                    current_balance = await get_user_balance(user_id)
                    formatted_balance = format_number(current_balance)
                except Exception:
                    logging.exception("Ошибка при форматировании баланса/выигрыша в choose_door")
                    formatted_win = format_number(win)
                    formatted_balance = "?"

                try:
                    await callback_query.message.edit_text(
                        "🥳 Молодец!\n"
                        "✅ Ты выбрал дверь, подходящую под твой ключ!\n\n"
                        f"💰 Твой выигрыш составляет: <b>{formatted_win}</b> Spark🦎!\n\n"
                        f"Ваш баланс: <b>{formatted_balance}</b> Spark🦎",
                        parse_mode=types.ParseMode.HTML
                    )
                except Exception:
                    logging.exception("Ошибка при отправке сообщения о выигрыше в choose_door")
            else:
                # Проигрыш — ставка уже списана ранее
                try:
                    # Статистика: +1 игра и loss
                    await increment_games_played(user_id, 1)
                    await add_loss_record(user_id, int(stake))
                except Exception:
                    logging.exception("Ошибка при обновлении статистики после поражения в Take Key")

                try:
                    formatted_loss = format_number(stake)
                    current_balance = await get_user_balance(user_id)
                    formatted_balance = format_number(current_balance)
                except Exception:
                    logging.exception("Ошибка при форматировании баланса в choose_door")
                    formatted_loss = format_number(stake)
                    formatted_balance = "?"

                try:
                    await callback_query.message.edit_text(
                        "❌ Не повезло!\n\n"
                        f"Эта дверь не подошла к твоему ключу, вы проиграли: <b>{formatted_loss}</b> Spark🦎!\n\n"
                        f"Ваш баланс: <b>{formatted_balance}</b> Spark🦎",
                        parse_mode=types.ParseMode.HTML
                    )
                except Exception:
                    logging.exception("Ошибка при отправке сообщения о поражении в choose_door")

            # Завершаем FSM успешно
            try:
                await state.finish()
            except Exception:
                logging.exception("Ошибка при завершении FSM в choose_door")

            # Очистка lock из словаря (lock уже автоматически освобождён при выходе из async with)
            game_locks.pop(user_id, None)
            active_games.pop(user_id, None)

            await callback_query.answer()
    except asyncio.CancelledError:
        logging.warning(f"Task cancelled while processing door choice for user {user_id}")
        await callback_query.answer("❌ Операция прервана. Попробуйте заново.", show_alert=True)
    except Exception:
        logging.exception("Ошибка при обработке выбора двери в choose_door")
        await callback_query.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
    finally:
        # В финале тоже удаляем записи, если остались
        game_locks.pop(user_id, None)
        active_games.pop(user_id, None)

# --- Обработчик команды 'кб' ---
@dp.message_handler(Text(startswith=("кб"), ignore_case=True))
async def crypto_boom_command(message: types.Message, state: FSMContext):
    """Обработчик команды 'кб' для начала игры 'Крипто-Бум'."""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    try:
        await create_user(user_id, username)
    except Exception:
        logging.exception("create_user упал в crypto_boom_command — продолжаем")

    # Проверка разрешения команды (кулдаун, бан и т.п.)
    try:
        if not await is_command_allowed(user_id):
            return
    except Exception:
        logging.exception("is_command_allowed упала в crypto_boom_command — продолжаем")

    # Проверка на бан
    try:
        if await is_user_banned(user_id):
            await message.reply("❌ Вы забанены и не можете использовать эту команду.")
            return
    except Exception:
        logging.exception("Ошибка при проверке бана в crypto_boom_command — продолжаем")

    # Разбор аргумента ставки
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Используйте: кб (сумма)")
        return

    stake_str = parts[1].strip().lower()
    stake = None
    try:
        if stake_str in ("все", "всё"):
            stake = await get_user_balance(user_id)
            if stake == 0:
                await message.reply("❌ На вашем балансе нет средств для ставки")
                return
        else:
            stake = format_stake(stake_str)
            if stake is None:
                await message.reply("❌ Неверный формат суммы. Используйте число или сокращение (1к, 1кк).")
                return
            stake = int(stake)
    except Exception:
        logging.exception("Ошибка при разборе ставки в crypto_boom_command")
        await message.reply("❌ Неверный формат ставки.")
        return

    # Проверки по ставке
    if stake < MIN_STAKE_KB:
        await message.reply(f"❌ Минимальная ставка: {format_number(MIN_STAKE_KB)} Spark🦎")
        return

    try:
        user_balance = await get_user_balance(user_id)
    except Exception:
        logging.exception("Ошибка получения баланса в crypto_boom_command")
        await message.reply("❌ Ошибка при проверке баланса. Попробуйте позже.")
        return

    if user_balance < stake:
        await message.reply("❌ Недостаточно средств на балансе.")
        return

    # Попытка снять ставку безопасно
    try:
        success = await safe_update_user_balance(user_id, -stake)
    except Exception:
        logging.exception("safe_update_user_balance упала при списании ставки в crypto_boom_command")
        success = False

    if not success:
        await message.reply("❌ Не удалось списать ставку. Попробуйте позже.")
        return

    # Инициализация игры: текущий коэффициент и начальная позиция
    current_x = 1.0
    position = random.choice(["Выше", "Ниже"])

    # Сохраняем данные игры в FSM
    try:
        await state.update_data(
            user_id=user_id,
            stake=stake,
            current_x=current_x,
            position=position,
            has_active_game=True,
            claimed=False,
            last_claim_time=0.0
        )
    except Exception:
        logging.exception("Ошибка записи state в crypto_boom_command")

    # Построение кнопок
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🟢Выше", callback_data="crypto_boom:Выше"),
        InlineKeyboardButton("🔴Ниже", callback_data="crypto_boom:Ниже")
    )

    # Текст и отправка
    formatted_stake = format_number(stake)
    text = (
        f"🪙Вы попали на Крипто бум!🪙\n\n"
        f"💰Ваша ставка: {hbold(formatted_stake)} Spark🦎\n\n"
        f"🔰Крипто-икс: {round(current_x, 2)}\n\n"
    )

    try:
        sent_message = await message.reply(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await state.update_data(message_id=sent_message.message_id, chat_id=sent_message.chat.id)
    except Exception:
        logging.exception("Ошибка при отправке стартового сообщения в crypto_boom_command")
        # Пробуем вернуть ставку в случае ошибки
        try:
            await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
        except Exception:
            logging.exception("Не удалось вернуть ставку после ошибки отправки стартового сообщения")
        await message.reply(f"❌ Произошла ошибка. Ставка {format_number(stake)} Spark🦎 возвращена на баланс.")
        await state.finish()
        return

    # Обновляем время последней команды (если нужно)
    try:
        await update_last_command_time(user_id)
    except Exception:
        logging.exception("Ошибка update_last_command_time в crypto_boom_command")

# --- Callback handler: выбор "Выше/Ниже" ---
@dp.callback_query_handler(Text(startswith="crypto_boom:"), state="*")
async def crypto_boom_callback(query: types.CallbackQuery, state: FSMContext):
    """Обработчик callback-запросов для кнопок 'Выше' и 'Ниже' в игре 'Крипто-Бум'."""
    user_id = query.from_user.id
    user_data = await state.get_data()

    # Проверка владельца игры
    if user_data.get("user_id") != user_id:
        await query.answer("❌ Это не ваша игра!", show_alert=True)
        return

    chosen_direction = query.data.split(":", 1)[1]
    # Если игрок нажал "Забрать" — перенаправляем к обработчику взятия
    if chosen_direction == "Забрать":
        await crypto_boom_take_callback(query, state)
        return

    stake = user_data.get("stake")
    current_x = user_data.get("current_x", 1.0)
    position = user_data.get("position")
    message_id = user_data.get("message_id")
    chat_id = user_data.get("chat_id")

    # Определяем исход раунда
    try:
        win_round = random.random() < CRYPTO_BOOM_WIN_CHANCE
    except Exception:
        logging.exception("Ошибка при генерации исхода раунда в crypto_boom_callback")
        win_round = False

    # Обновление статистики направления (вспомогательная функция может быть необязательной)
    try:
        await update_crypto_boom_stats(chosen_direction)
    except Exception:
        logging.exception("update_crypto_boom_stats упала в crypto_boom_callback — игнорируем")

    if win_round:
        # Успешный раунд: увеличиваем х
        try:
            current_x = round(current_x * CRYPTO_BOOM_MULTIPLIER, 6)
        except Exception:
            logging.exception("Ошибочный расчёт current_x; ставим fallback")
            current_x = current_x * CRYPTO_BOOM_MULTIPLIER

        # Генерируем новое положение (для показа)
        new_position = random.choice(["Выше", "Ниже"])

        # Создаём кнопки, включая "Забрать"
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🟢Выше", callback_data="crypto_boom:Выше"),
            InlineKeyboardButton("🔴Ниже", callback_data="crypto_boom:Ниже"),
            InlineKeyboardButton("Забрать ✅", callback_data="crypto_boom:Забрать")
        )

        formatted_stake = format_number(stake)
        text = (
            f"🪙Вы попали на Крипто бум!🪙\n\n"
            f"💰Ваша ставка: {hbold(formatted_stake)} Spark🦎\n\n"
            f"🔰Крипто-икс: {round(current_x, 2)}\n\n"
        )

        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup, parse_mode=ParseMode.HTML)
        except types.MessageNotModified:
            logging.debug("crypto_boom_callback: сообщение не изменилось")
        except Exception:
            logging.exception("Ошибка при редактировании сообщения в crypto_boom_callback")

        # Сохраняем новое состояние игры
        try:
            await state.update_data(current_x=current_x, position=new_position)
        except Exception:
            logging.exception("Ошибка при обновлении state после успешного раунда в crypto_boom_callback")

    else:
        # Проигрыш: игрок теряет ставку (ставка уже списана при старте)
        try:
            # Статистика: +1 сыгранная и loss (фиксируем ставку как проигрыш)
            await increment_games_played(user_id, 1)
            await add_loss_record(user_id, int(stake))
        except Exception:
            logging.exception("Ошибка при обновлении статистики после поражения в crypto_boom_callback")

        # Обновляем сообщение о проигрыше
        text = "Крипто-бум!♨️\n\nВаш курс пошел по другому положению☹️\n\nВы проиграли!❌"
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=None, parse_mode=ParseMode.HTML)
        except types.MessageNotModified:
            logging.debug("crypto_boom_callback (lose): сообщение не изменилось")
        except Exception:
            logging.exception("Ошибка при редактировании сообщения после поражения в crypto_boom_callback")

        # Завершаем состояние игры
        try:
            await state.finish()
            await state.reset_state()
        except Exception:
            logging.exception("Ошибка при завершении state после поражения в crypto_boom_callback")

    await query.answer()

# --- Обработчик 'Забрать' ---
@dp.callback_query_handler(Text(equals="crypto_boom:Забрать"), state="*")
async def crypto_boom_take_callback(query: types.CallbackQuery, state: FSMContext):
    """Обработчик callback-запроса для кнопки 'Забрать' в игре 'Крипто-Бум'."""
    user_id = query.from_user.id
    current_time = time.time()
    user_data = await state.get_data()

    # Проверка владельца игры
    if user_data.get("user_id") != user_id:
        await query.answer("❌ Это не ваша игра!", show_alert=True)
        return

    stake = user_data.get("stake")
    current_x = user_data.get("current_x", 1.0)
    position = user_data.get("position")
    message_id = user_data.get("message_id")
    chat_id = user_data.get("chat_id")
    last_claim_time = user_data.get("last_claim_time", 0.0)
    claimed = user_data.get("claimed", False)

    # Проверка частоты взятия
    if current_time - (last_claim_time or 0.0) < CLAIM_COOLDOWN:
        await query.answer("❌ Слишком часто! Подождите немного.", show_alert=True)
        return

    # Проверка повторного взятия
    if claimed:
        await query.answer("❌ Вы уже забрали свой выигрыш!", show_alert=True)
        return

    # Фиксируем, что игрок нажал "Забрать" — ставим флаг
    try:
        await state.update_data(claimed=True)
    except Exception:
        logging.exception("Не удалось установить claimed=True в crypto_boom_take_callback")

    winning_amount = int(stake * current_x)

    # Начисляем выигрыш игроку
    try:
        await safe_update_user_balance(user_id, winning_amount)
    except Exception:
        logging.exception("Ошибка при начислении выигрыша в crypto_boom_take_callback")
        # В случае критической ошибки — сообщаем, но стараемся продолжить корректно
        await query.answer("❌ Произошла ошибка при начислении выигрыша. Попробуйте позже.", show_alert=True)
        return

    # Обновляем статистику: +1 игра и win
    try:
        await increment_games_played(user_id, 1)
        await add_win_record(user_id, int(winning_amount))
    except Exception:
        logging.exception("Ошибка при обновлении статистики после взятия выигрыша в crypto_boom_take_callback")

    # Формируем и отправляем итоговое сообщение
    formatted_winning_amount = format_number(winning_amount)
    text = (
        f"Вы завершили игру Крипто-бум!🎉\n\n"
        f"🥳Вы забрали выигрыш на : {round(current_x, 2)}, вышло : {hbold(formatted_winning_amount)} Spark🦎\n\n"
        f"〽️Ваше положение было: {position}"
    )

    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=None, parse_mode=ParseMode.HTML)
    except types.MessageNotModified:
        logging.debug("crypto_boom_take_callback: сообщение не изменилось")
    except Exception:
        logging.exception("Ошибка при редактировании сообщения в crypto_boom_take_callback")

    # Обновляем время последней попытки и завершаем FSM
    try:
        await state.update_data(last_claim_time=current_time)
    except Exception:
        logging.exception("Ошибка при записи last_claim_time в state")

    try:
        await state.finish()
        await state.reset_state()
    except Exception:
        logging.exception("Ошибка при завершении state в crypto_boom_take_callback")

    await query.answer()

# --- Константы для Боулинга ---
MIN_STAKE_BOWL = 100
BOWLING_STICKER_1 = "CAACAgEAAxkBAAEOG6Zn2ZEt_y6wu2iOUj8GspE5Ul15jwAC8QgAAuN4BAABqjKl4uCyhL02BA"
BOWLING_STICKER_2 = "CAACAgEAAxkBAAEOG6hn2ZExugo55iG1HAF2_SjZP4LKkQAC8ggAAuN4BAABglobWqngICs2BA"
BOWLING_STICKER_3 = "CAACAgEAAxkBAAEOG6pn2ZE0LmWZRq6cuw__VPLLLvRSSQAC8wgAAuN4BAABCn-o3TzFXqU2BA"
BOWLING_STICKER_4 = "CAACAgEAAxkBAAEOG6xn2ZE306k3uGdHOQNjRtwq2Ysd5gAC9QgAAuN4BAAB5AABzTokMxc-NgQ"
BOWLING_STICKER_5 = "CAACAgEAAxkBAAEOG65n2ZE78xdZF-xTC_HQvttcFM5uZgAC9ggAAuN4BAABEzb0qwozWg82BA"
BOWLING_STICKER_6 = "CAACAgEAAxkBAAEOG7Bn2ZE-LdJR6p9h-bNZ3O3L9eReFAAC9wgAAuN4BAAB0SRHd-clzqg2BA"

MULTIPLIERS = {
    BOWLING_STICKER_4: 1.2,
    BOWLING_STICKER_5: 1.8,
    BOWLING_STICKER_6: 1.9
}
WINNING_STICKERS = list(MULTIPLIERS.keys())
LOSING_STICKERS = [BOWLING_STICKER_1, BOWLING_STICKER_2, BOWLING_STICKER_3]
ALL_BOWLING_STICKERS = WINNING_STICKERS + LOSING_STICKERS


# --- Активные игры ---
active_games = {}  # user_id: "bowling" или "basketball"

async def is_game_active(user_id: int) -> bool:
    return user_id in active_games

async def set_game_active(user_id: int, game_type: str):
    active_games[user_id] = game_type

async def clear_game_active(user_id: int):
    active_games.pop(user_id, None)

# format_stake предполагается в проекте; если нет — используйте свою реализацию.
# Ниже приведена сигнатура:
# def format_stake(stake_str: str) -> Optional[int]: ...

# --- Функция игры в боулинг ---
async def bowling_game(user_id: int, stake: int, message: types.Message):
    """Выполняет один раунд боулинга."""
    try:
        # Проверки минимальной ставки и баланса
        try:
            user_balance = await get_user_balance(user_id)
        except Exception:
            logging.exception("Не удалось получить баланс в bowling_game")
            await message.reply("❌ Ошибка при проверке баланса. Попробуйте позже.")
            return

        if stake < MIN_STAKE_BOWL:
            await message.reply(f"❌ Минимальная ставка: {format_number(MIN_STAKE_BOWL)} Spark🦎")
            return

        if stake > user_balance:
            await message.reply("❌ Недостаточно средств на балансе.")
            return

        # Устанавливаем активную игру
        await set_game_active(user_id, "bowling")

        # Снимаем ставку безопасно
        try:
            success = await safe_update_user_balance(user_id, -stake)
        except Exception:
            logging.exception("Ошибка safe_update_user_balance при списании в bowling_game")
            success = False

        if not success:
            await message.reply("❌ Не удалось списать ставку. Попробуйте позже.")
            return

        # Отправляем стикер "броска"
        try:
            chosen_sticker = random.choice(ALL_BOWLING_STICKERS)
            sticker_message = await message.answer_sticker(chosen_sticker)
        except Exception:
            logging.exception("Ошибка при отправке стикера в bowling_game")
            # Если не получилось отправить стикер — информируем и возвращаем ставку
            try:
                await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
            except Exception:
                logging.exception("Ошибка при возврате ставки после ошибки отправки стикера (bowling)")
            await message.reply("❌ Произошла ошибка при отправке стикера. Ставка возвращена.")
            return

        await asyncio.sleep(3)

        # Результат
        if chosen_sticker in WINNING_STICKERS:
            multiplier = MULTIPLIERS.get(chosen_sticker, 1.0)
            reward = int(round(stake * multiplier))
            try:
                await safe_update_user_balance(user_id, reward)
            except Exception:
                logging.exception("Ошибка при начислении выигрыша в bowling_game")
            result_text = f"✅ Вы выиграли: +{format_number(reward)} Spark🦎"
            # Статистика
            try:
                await increment_games_played(user_id, 1)
                await add_win_record(user_id, int(reward))
            except Exception:
                logging.exception("Ошибка при обновлении статистики после выигрыша в bowling_game")
        else:
            result_text = "❌ Вы проиграли"
            try:
                await increment_games_played(user_id, 1)
                await add_loss_record(user_id, int(stake))
            except Exception:
                logging.exception("Ошибка при обновлении статистики после поражения в bowling_game")

        # Добавляем кнопку с результатом
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(text=result_text, callback_data="bowling_result"))

        # Пытаемся подправить reply_markup у сообщения (если возможно)
        try:
            await bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=sticker_message.message_id,
                reply_markup=keyboard
            )
        except Exception:
            logging.exception("Не удалось изменить reply_markup для стикера (bowling_game). Отправляем текст.")
            await message.reply(result_text, reply_markup=keyboard)
    finally:
        # Всегда очищаем статус игры
        await clear_game_active(user_id)

# --- Команда боулинга ---
@dp.message_handler(Text(startswith="боул", ignore_case=True))
async def bowling_command(message: types.Message):
    user_id = message.from_user.id

    if await is_game_active(user_id):
        await message.reply("⏳ Дождитесь завершения предыдущей игры.")
        return

    # Проверка cooldown / разрешения
    try:
        if not await is_command_allowed(user_id):
            return
    except Exception:
        logging.exception("is_command_allowed упала в bowling_command — продолжаем")

    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("❌ Укажите ставку: боул (ставка)")
            return

        stake_str = parts[1].strip().lower()
        parsed = format_stake(stake_str)
        if parsed is None:
            await message.reply("❌ Неверный формат суммы. Используйте число или сокращение (1к, 1кк).")
            return

        if parsed == 'все':
            user_balance = await get_user_balance(user_id)
            if user_balance < MIN_STAKE_BOWL:
                await message.reply(f"❌ Минимальная ставка: {format_number(MIN_STAKE_BOWL)} Spark🦎")
                return
            stake = int(user_balance)
        else:
            stake = int(parsed)
            if stake < MIN_STAKE_BOWL:
                await message.reply(f"❌ Минимальная ставка: {format_number(MIN_STAKE_BOWL)} Spark🦎")
                return

        await update_last_command_time(user_id)
        stake = int(round(stake))
        await bowling_game(user_id, stake, message)
    except Exception:
        logging.exception("Ошибка в команде боулинга")
        await message.reply("Произошла ошибка. Попробуйте позже.")

# -------------------- Кости (Одкуб) --------------------
MIN_STAKE_O = 100


@dp.message_handler(Text(startswith=("кубик"), ignore_case=True))
async def odkub_command(message: Message):
    """Обработчик команды 'кубик'."""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Создаём пользователя (если нужно) — защищаем вызовом
    try:
        await create_user(user_id, username)
    except Exception:
        logging.exception("create_user упал в odkub_command — продолжаем")

    # Проверка разрешения команды (кулдаун, бан и т.п.)
    try:
        if not await is_command_allowed(user_id):
            return
    except Exception:
        logging.exception("is_command_allowed упала в odkub_command — продолжаем")

    # Проверка бана
    try:
        if await is_user_banned(user_id):
            await message.reply("❌ Вы забанены и не можете использовать эту команду.")
            return
    except Exception:
        logging.exception("Ошибка при проверке бана в odkub_command — продолжаем")

    stake = None
    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.reply("❌ Использование: кубик (ставка) (число 1-6 / чет / нечет)")
            return

        stake_str = parts[1].strip().lower()
        prediction = parts[2].strip().lower()

        # Разбор ставки: поддерживаем "все/всё" и format_stake
        if stake_str in ("все", "всё"):
            try:
                stake = await get_user_balance(user_id)
            except Exception:
                logging.exception("Ошибка получения баланса при 'все' в odkub_command")
                await message.reply("❌ Ошибка при получении баланса. Попробуйте позже.")
                return

            if stake <= 0:
                await message.reply("❌ На вашем балансе нет средств для ставки.")
                return
        else:
            parsed = format_stake(stake_str)
            if parsed is None:
                await message.reply("❌ Неверный формат ставки. Используйте число или сокращение (1к, 1кк).")
                return
            stake = int(parsed)

        # Проверки ставки
        if stake <= 0:
            await message.reply("❌ Ставка должна быть больше 0.")
            return

        if stake < MIN_STAKE_O:
            await message.reply(f"❌ Минимальная ставка: {format_number(MIN_STAKE_O)} Spark🦎")
            return

        try:
            user_balance = await get_user_balance(user_id)
        except Exception:
            logging.exception("Ошибка получения баланса в odkub_command")
            await message.reply("❌ Ошибка при проверке баланса. Попробуйте позже.")
            return

        if user_balance < stake:
            await message.reply("❌ Недостаточно средств на балансе.")
            return

        # Проверка корректности предсказания
        if prediction not in ['1', '2', '3', '4', '5', '6', 'чет', 'нечет']:
            await message.reply("❌ Неверное предсказание. Выберите число 1-6 или 'чет'/'нечет'.")
            return

        # Списание ставки безопасно
        try:
            success = await safe_update_user_balance(user_id, -stake)
        except Exception:
            logging.exception("Ошибка safe_update_user_balance при списании ставки в odkub_command")
            success = False

        if not success:
            await message.reply("❌ Не удалось списать ставку. Попробуйте позже.")
            return

        # Отправляем кости (dice). Если не получилось — делаем fallback на random.randint
        dice_roll = None
        try:
            sent_dice = await message.reply_dice(emoji="🎲")
            # Иногда dice может быть None (в не поддерживаемых чатах), тогда fallback ниже
            if sent_dice and getattr(sent_dice, "dice", None):
                dice_roll = sent_dice.dice.value
            else:
                # небольшой таймаут перед fallback — но сразу берём случайное
                dice_roll = random.randint(1, 6)
        except Exception:
            logging.exception("Ошибка при отправке dice в odkub_command, используем fallback random")
            dice_roll = random.randint(1, 6)
            sent_dice = None  # чтобы знать, что редактировать сообщение нельзя

        # Определяем выигрыш
        win = False
        multiplier = 0.0
        if prediction in ['1', '2', '3', '4', '5', '6']:
            if int(prediction) == dice_roll:
                win = True
                multiplier = 5.8  # двойная сумма при точном совпадении
        elif prediction == 'чет':
            if dice_roll % 2 == 0:
                win = True
                multiplier = 1.94
        elif prediction == 'нечет':
            if dice_roll % 2 != 0:
                win = True
                multiplier = 1.94

        winnings = 0
        if win and multiplier > 0:
            winnings = int(round(stake * multiplier))
            try:
                await safe_update_user_balance(user_id, winnings)
            except Exception:
                logging.exception("Ошибка при начислении выигрыша в odkub_command")
                # Если начисление проигнорировано — пытаемся вернуть ставку и сообщить
                try:
                    await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
                except Exception:
                    logging.exception("Не удалось вернуть ставку после ошибки начисления в odkub_command")
                await message.reply("❌ Произошла ошибка при начислении выигрыша. Ставка возвращена.")
                # Обновляем статистику как ошибочную (не учитываем как выигрыш)
                await update_last_command_time(user_id)
                return

        # Обновление статистики
        try:
            await increment_games_played(user_id, 1)
            if win:
                await add_win_record(user_id, int(winnings))
            else:
                await add_loss_record(user_id, int(stake))
        except Exception:
            logging.exception("Ошибка при обновлении статистики в odkub_command")

        # Подготовка клавиатуры результата
        keyboard = InlineKeyboardMarkup(row_width=1)
        if win:
            keyboard.add(InlineKeyboardButton(text=f"✅ Вы выиграли: +{format_number(winnings)}", callback_data="odkub_win"))
        else:
            keyboard.add(InlineKeyboardButton(text=f"❌ Вы проиграли: {format_number(stake)}", callback_data="odkub_lose"))

        # Немного подождём перед редактированием (если нужно)
        await asyncio.sleep(3)

        # Попытка отредактировать reply_markup у сообщения dice (если удалось его отправить)
        try:
            if sent_dice:
                await bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=sent_dice.message_id, reply_markup=keyboard)
            else:
                # Если dice не отправляли/нельзя редактировать — отправляем сообщение с результатом
                if win:
                    await message.reply(f"🎲 Выпало: {dice_roll}\n✅ Вы выиграли: +{format_number(winnings)} Spark🦎")
                else:
                    await message.reply(f"🎲 Выпало: {dice_roll}\n❌ Вы проиграли: {format_number(stake)} Spark🦎")
        except Exception:
            logging.exception("Не удалось отредактировать сообщение с результатом в odkub_command")
            # На всякий случай отправим текстовый результат
            if win:
                await message.reply(f"🎲 Выпало: {dice_roll}\n✅ Вы выиграли: +{format_number(winnings)} Spark🦎")
            else:
                await message.reply(f"🎲 Выпало: {dice_roll}\n❌ Вы проиграли: {format_number(stake)} Spark🦎")

        # Обновляем время последней команды
        try:
            await update_last_command_time(user_id)
        except Exception:
            logging.exception("Ошибка update_last_command_time в odkub_command")

    except Exception:
        logging.exception("Непредвиденная ошибка в odkub_command")
        # В случае ошибки пытаемся вернуть ставку пользователю (если она была списана)
        try:
            if stake and stake > 0:
                await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
        except Exception:
            logging.exception("Ошибка при возврате ставки после исключения в odkub_command")
        await message.reply("❌ Произошла ошибка. Ставка возвращена, попробуйте позже.")
#================ дартс =================================
#================ дартс =================================
multipliers = {
    "красное": 1.94,
    "белое": 2.9,
    "центр": 5.8,
    "мимо": 5.8
}

def parse_bet_amount(bet_str: str) -> int | None:
    """
    Преобразует строку ставки в число.
    Примеры:
        "100" -> 100
        "1к"  -> 1000
        "1кк" -> 1_000_000
        "1ккк" -> 1_000_000_000
    """
    bet_str = bet_str.lower().replace(" ", "")
    multipliers = {"к": 10**3, "м": 10**6, "г": 10**9}  # можно добавить больше сокращений

    # Проверка, если просто число
    if bet_str.isdigit():
        return int(bet_str)

    # Проверяем на окончания к/м/г
    for suffix, factor in multipliers.items():
        if bet_str.endswith(suffix):
            try:
                number_part = float(bet_str[:-len(suffix)].replace(",", "."))
                return int(round(number_part * factor))
            except ValueError:
                return None
    return None


user_cooldowns = {}
COOLDOWN = 3  # секунды

@dp.message_handler(commands=["darts"])
@dp.message_handler(lambda message: message.text.lower().startswith("дартс"))
async def darts_start(message: types.Message):
    user_id = message.from_user.id
    current_time = time.time()

    # Проверка cooldown
    if user_id in user_cooldowns:
        elapsed = current_time - user_cooldowns[user_id]
        if elapsed < COOLDOWN:
            await message.reply(f"⏱ Подожди {int(COOLDOWN - elapsed)} секунд перед следующей ставкой")
            return

    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Укажи ставку, например: /darts 100 или дартс 100")
        return

    # Парсим строку ставки
    bet_str = parts[1]  # <--- эта строка была пропущена

    bet = parse_bet_amount(bet_str)
    if bet is None or bet <= 0:
        await message.reply("❌ Неверный формат ставки. Используй число или сокращения: 1к, 1кк, 1ккк")
        return



    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row or row[0] < bet:
        await message.reply("❌ Недостаточно средств")
        return

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔴 Красное", callback_data=f"darts_красное_{bet}"),
        InlineKeyboardButton("⚪️ Белое", callback_data=f"darts_белое_{bet}"),
        InlineKeyboardButton("🎯 Центр", callback_data=f"darts_центр_{bet}"),
        InlineKeyboardButton("😯 Мимо", callback_data=f"darts_мимо_{bet}"),
        InlineKeyboardButton("❌ Отмена", callback_data=f"darts_cancel")
    )

    message_text = (
        f"💰 **Ставка:** {bet}\n"
        f"- - - - - - - - - - - - - - - - -\n"
        f"Множители:\n"
        f"🔴 Красное — х{multipliers['красное']}\n"
        f"⚪️ Белое — х{multipliers['белое']}\n"
        f"🎯 Центр — х{multipliers['центр']}\n"
        f"😯 Мимо — х{multipliers['мимо']}\n"
        f"- - - - - - - - - - - - - - - - -\n"
        f"Выбери исход 👇"
    )

    await message.reply(message_text, reply_markup=keyboard, parse_mode="Markdown")

    # Сохраняем время последней ставки
    user_cooldowns[user_id] = current_time
    
@dp.callback_query_handler(lambda c: c.data.startswith("darts_"))
async def process_darts(callback_query: types.CallbackQuery):
    data = callback_query.data.split("_")
    choice = data[1]

    if choice == "cancel":
        await callback_query.message.delete()
        return

    bet = int(data[2])
    user_id = callback_query.from_user.id

    # ... (проверка баланса и снятие ставки без изменений) ...
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row or row[0] < bet:
        await callback_query.message.delete()
        await callback_query.message.answer("❌ Недостаточно средств")
        return

    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (bet, user_id))
    conn.commit()
    await callback_query.message.delete()

    sent_dice = await callback_query.message.answer_dice(emoji="🎯")
    await asyncio.sleep(3) # Ждем окончания анимации

    # Получаем реальное значение
    dice_value = sent_dice.dice.value

    # ПРАВИЛЬНОЕ сопоставление цветов мишени Telegram
    dice_map = {
        1: "мимо",      # Промах (серый край)
        2: "красное",   # Сектор
        3: "белое",     # Сектор
        4: "красное",   # Сектор
        5: "белое",     # Сектор
        6: "центр"      # Яблочко (синий центр)
    }
    
    result_key = dice_map[dice_value]
    emoji_map = {"красное":"🔴", "белое":"⚪️", "центр":"🎯", "мимо":"😯"}

    # ... (дальше код расчета выигрыша без изменений) ...
# ... после определения result_key и emoji_map ...

    # Проверка выигрыша
    if choice == result_key or (choice == "красное" and result_key == "центр"):
        # Центр теперь считается красным
        win_amount = int(bet * multipliers[choice])
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (win_amount, user_id))
        conn.commit()
        text = (
            f"✅ Результат игры:\n"
            f"- - - - - - - - - - - - - - - - -\n"
            f"Ты выбрал: {emoji_map[choice]} {choice}\n"
            f"Выпало: {emoji_map[result_key]} {result_key}\n"
            f"🎉 Выигрыш: {win_amount} Spark🦎"
        )
    else:
        text = (
            f"✅ Результат игры:\n"
            f"- - - - - - - - - - - - - - - - -\n"
            f"Ты выбрал: {emoji_map[choice]} {choice}\n"
            f"Выпало: {emoji_map[result_key]} {result_key}\n"
            f"❌ Потеряно: {bet} Spark🦎"
        )


    await bot.send_message(chat_id=sent_dice.chat.id, text=text,
                           parse_mode="Markdown", reply_to_message_id=sent_dice.message_id)

# ----------------------------
# Хранилище спинов пользователей
user_spins: dict[int, int] = {}  # {user_id: количество_спинов}

# ----------------------------
async def get_user_spins(user_id: int) -> int:
    await ensure_user_exists(user_id)
    cursor.execute("SELECT spins FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 0

async def add_user_spins(user_id: int, count: int):
    await ensure_user_exists(user_id)
    cursor.execute("SELECT spins FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    current = result[0] if result else 0
    cursor.execute("UPDATE users SET spins = ? WHERE user_id = ?", (current + count, user_id))
    conn.commit()

async def remove_user_spin(user_id: int) -> bool:
    await ensure_user_exists(user_id)
    cursor.execute("SELECT spins FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    current = result[0] if result else 0
    if current > 0:
        cursor.execute("UPDATE users SET spins = ? WHERE user_id = ?", (current - 1, user_id))
        conn.commit()
        return True
    return False

async def ensure_user_exists(user_id: int, username: str = ""):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()



# ----------------------------
# ----------------------------
# Команда /donat (только в ЛС)
@dp.message_handler(commands=["donat"])
async def donat_handler(message: types.Message):
    # Проверяем, что чат — приватный
    if message.chat.type != "private":
        await message.reply("❌ Команду /donat можно использовать только в личных сообщениях с ботом.")
        return

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🎰 Фортуна", callback_data="donat_fortuna")
    )

    await message.reply(
        "💳 Выберите раздел доната:",
        reply_markup=keyboard
    )


# ----------------------------
# Callback для выбора раздела доната
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("donat"))
async def donat_callback_handler(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if data == "donat_fortuna":
        await show_fortuna_menu(callback_query, user_id)

    elif data == "donat_spin":
        await spin_fortuna(callback_query, user_id)

    elif data == "donat_none":
        await callback_query.answer("⚠️ Кнопка только для отображения спинов.", show_alert=True)


# ----------------------------
# ----------------------------
# Функция для добавления денег на баланс
async def add_balance(user_id: int, amount: int):
    await ensure_user_exists(user_id)
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    current_balance = result[0] if result else 0
    cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (current_balance + amount, user_id))
    conn.commit()

# ----------------------------
# ----------------------------
# ----------------------------
# Крутилка Фортуны с шансами
async def spin_fortuna(callback_query, user_id):
    import random

    # Проверяем и убираем 1 спин
    if not await remove_user_spin(user_id):
        await callback_query.answer("❌ У тебя нет спинов для кручения.", show_alert=True)
        return

    # Меняем сообщение на "крутим"
    spinning_message = await bot.edit_message_text(
        "🌀 Крутим Фортуну...",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id
    )

    # Список призов с деньгами и шансами
    prizes = [
        {"text": "1.000.000 Spark🦎", "money": 1000000, "chance": 70},
        {"text": "2.000.000 Spark🦎", "money": 2000000, "chance": 60},
        {"text": "5.000.000 Spark🦎", "money": 5000000, "chance": 45},
        {"text": "10.000.000 Spark🦎", "money": 10000000, "chance": 20},
        {"text": "100.000.000 Spark🦎", "money": 100000000, "chance": 5}
    ]

    # Определяем выигрыш по шансам
    prize = None
    while True:
        candidate = random.choice(prizes)
        roll = random.randint(1, 100)
        if roll <= candidate["chance"]:
            prize = candidate
            break

    # Ждем для анимации
    await asyncio.sleep(2)

    # Выдаём деньги
    if prize["money"] > 0:
        await add_balance(user_id, prize["money"])

    # Получаем оставшиеся спины
    spins_left = await get_user_spins(user_id)

    # Формируем текст результата
    result_text = (
        f"🎉 Поздравляем! Вы выиграли {prize['text']}!\n"
        f"🎰 Осталось спинов: {spins_left}"
    )

    # Кнопки: "купить спин" и "Ваши спины"
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(
            "💰 Купить спин (50₽ | 0.5$ | 25 звёзд)",
            url="https://t.me/Miroziskill"
        )
    )
    keyboard.add(
        InlineKeyboardButton(f"🎰 Ваши спины: {spins_left}", callback_data="donat_spin")
    )

    await bot.edit_message_text(
        result_text,
        chat_id=callback_query.message.chat.id,
        message_id=spinning_message.message_id,
        reply_markup=keyboard
    )



# ----------------------------
# Callback для кнопки "Ваши спины"
@dp.callback_query_handler(lambda c: c.data == "donat_spin")
async def callback_spin(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    await spin_fortuna(callback_query, user_id)

# ----------------------------
# Меню Фортуны с кнопкой спинов
async def show_fortuna_menu(callback_query, user_id):
    spins_count = await get_user_spins(user_id)
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(
            "💰 Купить спин (Цена 1 спина 50₽ | 0.5$ | 25 звёзд)",
            url="https://t.me/Miroziskill"
        )
    )
    keyboard.add(
        InlineKeyboardButton(f"🎰 Ваши спины: {spins_count}", callback_data="donat_spin")
    )

    prizes_text = (
        "🎁 Возможные призы Фортуны:\n"
        "1️⃣ 1.000.000 Spark🦎\n"
        "2️⃣ 2.000.000 Spark🦎\n"
        "3️⃣ 5.000.000 Spark🦎\n"
        "4️⃣ 10.000.000 Spark🦎\n"
        "5️⃣ 100.000.000 Spark🦎"
    )

    await bot.edit_message_text(
        prizes_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=keyboard
    )





# ----------------------------
@dp.message_handler(commands=["add_spins"])
async def add_spins_handler(message: types.Message):
    # Проверка прав
    if message.from_user.id not in OWNER_IDS:
        await message.reply("❌ У тебя нет прав на эту команду.")
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.reply("Использование: /add_spins <user_id> <кол-во_спинов>")
        return

    try:
        target_user = int(parts[1])
        spins = int(parts[2])
    except ValueError:
        await message.reply("❌ user_id и кол-во_спинов должны быть числами.")
        return

    # Добавляем спины через функцию с проверкой существования пользователя
    await add_user_spins(target_user, spins)

    # Получаем актуальное количество спинов
    spins_count = await get_user_spins(target_user)

    await message.reply(
        f"✅ Пользователю {target_user} выданы {spins} спинов.\n"
        f"🎰 Сейчас у него: {spins_count} спинов."
    )









# -------------------- Промокоды --------------------

# ... (Другие импорты и функции, например, get_db_connection, close_db_connection, update_user_balance, format_number)

@dp.message_handler(Text(startswith="промо", ignore_case=True))
async def activate_promo(message: types.Message):
    """Активирует промокод."""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    code = message.text.split(' ', 1)[1] if len(message.text.split()) > 1 else None

    if not code:
        await message.reply("❌Пожалуйста, укажите название промокода. Пример: `промо хенд`", parse_mode=types.ParseMode.MARKDOWN)
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # Проверка регистрации пользователя
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    user_exists = cursor.fetchone()

    if not user_exists:
        await message.reply("Пользователь не найден. Пожалуйста, используйте команду /start.")
        close_db_connection(conn)
        return

    cursor.execute("SELECT amount, activations, used_by FROM promocodes WHERE code = ?", (code,))
    result = cursor.fetchone()

    if not result:
        await message.reply("❌Промокод не найден.")
        close_db_connection(conn)
        return

    amount, activations, used_by = result

    if str(user_id) in used_by.split(','):
        await message.reply("❌Вы уже активировали этот промокод.")
        close_db_connection(conn)
        return

    if activations <= 0:
        await message.reply("❌Промокод больше не действителен (закончились активации).")
        close_db_connection(conn)
        return

    await update_user_balance(user_id, amount)

    # Обновляем информацию об использовании промокода
    used_by_list = used_by.split(',') if used_by else []
    used_by_list.append(str(user_id))
    new_used_by = ','.join(used_by_list)

    cursor.execute("UPDATE promocodes SET activations = activations - 1, used_by = ? WHERE code = ?", (new_used_by, code))
    conn.commit()
    close_db_connection(conn)

    formatted_amount = format_number(amount)

    await message.reply(f"✅💰| Вы активировали промокод на {formatted_amount} Spark🦎 с названием {code}")



@dp.message_handler(Text(startswith="+промо", ignore_case=True))
async def create_promo(message: types.Message):
    """Создает промокод (только для владельца бота)."""
    user_id = message.from_user.id

    if user_id not in OWNER_IDS:
        await message.reply("❌У вас нет прав на создание промокодов.")
        return

    args = message.text.split()
    if len(args) != 4:
        await message.reply("❌Используйте: +промо (название) (сумма) (количество активаций)")
        return

    code = args[1]
    amount_str = args[2]
    activations_str = args[3]

    amount = format_stake(amount_str)
    if amount is None:
        await message.reply("❌Неверный формат суммы.")
        return

    try:
        activations = int(activations_str)
        if activations <= 0:
            await message.reply("Количество активаций должно быть больше 0.")
            return
    except ValueError:
        await message.reply("Неверный формат количества активаций.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO promocodes (code, amount, activations) VALUES (?, ?, ?)",
            (code, amount, activations)
        )
        conn.commit()

        text = (
            "🎉 <b>Промокод успешно создан!</b>\n\n"
            f"🏷 <b>Код:</b> <code>{code}</code>\n"
            f"💰 <b>Начисление:</b> <code>{amount}</code> PLcoins\n"
            f"🔢 <b>Доступно активаций:</b> <code>{activations}</code>\n\n"
            "📋 <b>Скопируйте и отправьте для активации:</b>\n"
            f"<code>Промо {code}</code>"
        )

        await message.reply(text, parse_mode="HTML")

    except sqlite3.IntegrityError:
        await message.reply("❌ <b>Ошибка:</b> промокод с таким названием уже существует.", parse_mode="HTML")

    finally:
        close_db_connection(conn)

# -------------------- /Промокоды --------------------

LOW_BAND_CHANCE = 0.70  # 25% шанс упасть в [1.00, 1.10]
CRASH_COOLDOWN = 5  # секунды
LOW_BAND_MAX = 1.10


# Глобальные словари
crash_games = {}       # user_id -> {stake, chosen_x, ts}
crash_cooldowns = {}   # user_id -> last_time

def hbold(text: str) -> str:
    return f"<b>{text}</b>"

def generate_crash_x_simple() -> float:
    """
    25% шанс, что crash_x попадёт в [1.00, 1.10], иначе равномерно в (1.10, CRASH_MAX_X].
    Округление до 2 знаков.
    """
    if random.random() < LOW_BAND_CHANCE:
        crash_x = random.uniform(CRASH_MIN_X, LOW_BAND_MAX)
    else:
        # выбираем чуть выше 1.10, чтобы не дублировать край
        lower = LOW_BAND_MAX + 1e-9
        crash_x = random.uniform(lower, CRASH_MAX_X)
    return round(crash_x, 2)

@dp.message_handler(Text(startswith="краш", ignore_case=True))
async def crash_command(message: types.Message, state: FSMContext):
    """
    Команда: краш (ставка) (коэффициент)
    Пример: 'краш 100 2.5' или 'краш все 3.0'
    Поведение: минималистично — как в остальных играх: списание через safe_update_user_balance,
    статистика, корректное удаление активной игры. 25% шанс падения в [1.00,1.10].
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    now = time.time()

    # Создаём пользователя и проверки доступа/банов, как в других играх
    try:
        await create_user(user_id, message.from_user.username or message.from_user.first_name)
    except Exception:
        logging.exception("create_user упал в crash_command — продолжаем")

    try:
        if not await is_command_allowed(user_id):
            return
    except Exception:
        logging.exception("is_command_allowed упал в crash_command — продолжаем")

    try:
        if await is_user_banned(user_id):
            await message.reply("❌ Вы забанены и не можете использовать эту команду.")
            return
    except Exception:
        logging.exception("is_user_banned упал в crash_command — продолжаем")

    # Кулдаун
    last = crash_cooldowns.get(user_id)
    if last and now - last < CRASH_COOLDOWN:
        remaining = CRASH_COOLDOWN - (now - last)
        await message.reply(f"❌ Подождите {remaining:.1f} сек. перед новой игрой.")
        return

    # Парсинг аргументов
    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.reply("❌ Используйте: краш (ставка) (коэффициент от 1.1 до 10.0)")
            return

        stake_str = parts[1].strip().lower()
        chosen_x = float(parts[2].strip().replace(",", "."))
    except (IndexError, ValueError):
        await message.reply("❌ Используйте: краш (ставка) (коэффициент от 1.1 до 10.0)")
        return

    # Валидация коэффициента
    if not (1.1 <= chosen_x <= CRASH_MAX_X):
        await message.reply(f"❌ Коэффициент должен быть от {CRASH_MIN_X:.1f} до {CRASH_MAX_X:.1f}.")
        return

    # Разбор ставки (поддержка "все/всё")
    stake_parsed = format_stake(stake_str)
    try:
        balance = await get_user_balance(user_id)
    except Exception:
        logging.exception("Ошибка получения баланса в crash_command")
        await message.reply("❌ Ошибка при проверке баланса. Попробуйте позже.")
        return

    if stake_parsed is None:
        await message.reply("❌ Неверный формат ставки.")
        return

    if stake_parsed == 'все':
        stake = int(balance)
    else:
        try:
            stake = int(round(float(stake_parsed)))
        except Exception:
            await message.reply("❌ Неверный формат ставки.")
            return

    if stake < MIN_STAKE_CR:
        await message.reply(f"❌ Минимальная ставка: {format_number(MIN_STAKE_CR)}")
        return

    if stake <= 0:
        await message.reply("❌ Ставка должна быть больше 0.")
        return

    if stake > balance:
        await message.reply("❌ Недостаточно средств на балансе.")
        return

    # Проверяем, нет ли уже активной игры
    if user_id in crash_games:
        await message.reply("❌ У вас уже есть активная игра в краш.")
        return

    # Списание ставки безопасно
    try:
        success = await safe_update_user_balance(user_id, -stake)
    except Exception:
        logging.exception("Ошибка safe_update_user_balance при списании (crash_command)")
        success = False

    if not success:
        await message.reply("❌ Не удалось списать ставку. Попробуйте позже.")
        return

    # Сохраняем активную игру
    crash_games[user_id] = {"stake": stake, "chosen_x": chosen_x, "ts": now}

    # Фоновой обработчик результата (минималистично, как в других играх)
    async def _process_and_notify():
        try:
            crash_x = generate_crash_x_simple()
            won = crash_x >= chosen_x

            if won:
                winnings = int(round(stake * chosen_x))
                try:
                    await safe_update_user_balance(user_id, winnings)
                except Exception:
                    logging.exception("Ошибка начисления выигрыша в crash (_process_and_notify)")
                    # попытка отката: вернуть ставку
                    try:
                        await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
                    except Exception:
                        logging.exception("Не удалось вернуть ставку после ошибки начисления (crash _process_and_notify)")
                    try:
                        await bot.send_message(chat_id, "❌ Внутренняя ошибка при начислении выигрыша. Ставка возвращена.")
                    except Exception:
                        logging.exception("Не удалось уведомить пользователя о возврате ставки (crash _process_and_notify)")
                    return

                # Статистика для выигрыша
                try:
                    await increment_games_played(user_id, 1)
                    await add_win_record(user_id, int(winnings))
                except Exception:
                    logging.exception("Ошибка статистики (win) в crash _process_and_notify")

                result_text = (
                    f"ℹ️ Вы выбрали коэффициент: {chosen_x:.2f}\n"
                    f"♨️ Ракета упала на: {crash_x:.2f}\n"
                    f"{CHECK_MARK_EMOJI} | Вы долетели и выиграли: {hbold(format_number(winnings))}!"
                )
                button_text = f"{CHECK_MARK_EMOJI} Успешно"
                emoji = ROCKET_EMOJI
            else:
                # Проигрыш — ставка уже списана
                try:
                    await increment_games_played(user_id, 1)
                    await add_loss_record(user_id, int(stake))
                except Exception:
                    logging.exception("Ошибка статистики (loss) в crash _process_and_notify")

                result_text = (
                    f"ℹ️ Вы выбрали коэффициент: {chosen_x:.2f}\n"
                    f"♨️ Ракета упала на: {crash_x:.2f}\n"
                    f"{CROSS_MARK_EMOJI} | Вы не долетели и потеряли: {hbold(format_number(stake))}!"
                )
                button_text = f"{CROSS_MARK_EMOJI} Поражение"
                emoji = BOOM_EMOJI

            # Отправляем итоговый текст
            try:
                await bot.send_message(chat_id, result_text, parse_mode=types.ParseMode.HTML)
            except Exception:
                logging.exception("Не удалось отправить итоговое сообщение (crash _process_and_notify)")

            # Отправляем эмодзи + кнопка
            try:
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton(button_text, callback_data="dummy"))
                await bot.send_message(chat_id, emoji, reply_markup=kb)
            except Exception:
                logging.exception("Не удалось отправить эмодзи/кнопку (crash _process_and_notify)")

        except Exception:
            logging.exception("Непредвиденная ошибка в обработке краша (_process_and_notify)")
            # попытка вернуть ставку при фатальной ошибке
            try:
                await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
            except Exception:
                logging.exception("Не удалось вернуть ставку после фатальной ошибки (crash _process_and_notify)")
            try:
                await bot.send_message(chat_id, "❌ Произошла ошибка при обработке игры. Ставка возвращена.")
            except Exception:
                logging.exception("Не удалось уведомить пользователя о возврате ставки (crash _process_and_notify)")
        finally:
            # Гарантированно удаляем активную игру
            try:
                crash_games.pop(user_id, None)
            except Exception:
                logging.exception("Ошибка при удалении игры из crash_games в finally (crash _process_and_notify)")

    # Запускаем фоновую задачу
    try:
        asyncio.create_task(_process_and_notify())
    except Exception:
        logging.exception("Не удалось запустить background задачу для краша")
        # Возврат ставки при ошибке запуска задачи
        try:
            await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
        except Exception:
            logging.exception("Не удалось вернуть ставку после ошибки запуска задачи (crash_command)")
        crash_games.pop(user_id, None)
        await message.reply("❌ Произошла ошибка. Ставка возвращена.")
        return

    # Обновляем кулдаун и время последней команды
    crash_cooldowns[user_id] = now
    try:
        await update_last_command_time(user_id)
    except Exception:
        logging.exception("Ошибка update_last_command_time в crash_command")


# --- Команда для рассылки сообщений ---
CHAT_LINK = "https://t.me/mirozisbackagain"  #  <----  Вставьте ссылку на чат сюда

@dp.message_handler(Text(startswith='+р'))
async def broadcast_message(message: types.Message):
    sender_id = message.from_user.id  # ID того, кто отправил команду

    if sender_id not in OWNER_IDS:
        await message.reply("У вас нет прав на выполнение этой команды.")
        return

    # Получаем текст сообщения после команды
    text = message.text[2:].strip()  # Убираем "+р" из текста

    # Проверяем, начинается и заканчивается ли текст звездочкой
    if text.startswith('*') and text.endswith('*'):
        text = text[1:-1]  # Убираем звездочки
        text = hbold(text)  # Делаем текст жирным

    if not text:
        await message.reply("Пожалуйста, укажите текст для рассылки.")
        return

    # Создаем inline-кнопку
    keyboard = InlineKeyboardMarkup()
    url_button = InlineKeyboardButton(text="УЗНАТЬ", url=CHAT_LINK)
    keyboard.add(url_button)

    # Рассылка в личные сообщения
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    user_ids = [row[0] for row in cursor.fetchall()]
    close_db_connection(conn)

    for uid in user_ids:  # Используем uid для каждого пользователя
        try:
            await bot.send_message(uid, text, reply_markup=keyboard, parse_mode="HTML")
        except ChatNotFound:
            pass
        except BotBlocked:
            pass
        except TelegramError:
            pass
        await asyncio.sleep(0.05)

    await message.reply("Рассылка завершена.")





# Настройки / константы
COMMAND_COOLDOWN = 2
last_use = {}

ACTIVE_TOWER_GAMES = {}

MIN_TOWER_STAKE = 100
MAX_BOMBS = 4
DEFAULT_BOMBS = 1
TOWER_LEVELS = 10
CELLS_PER_LEVEL = 5

BOMB_CHANCE_USER = 0.24



# Утилиты
async def try_edit_message(message: types.Message, text: str = None, reply_markup: InlineKeyboardMarkup = None,
                           parse_mode: str = 'HTML', retries: int = 20) -> None:
    for attempt in range(retries):
        try:
            await message.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
            return
        except exceptions.MessageNotModified:
            logging.warning("Сообщение не изменено.")
            return
        except exceptions.TelegramAPIError as e:
            logging.error(f"Ошибка редактирования сообщения (попытка {attempt + 1}/{retries}): {e}")
            if "Too Many Requests" in str(e):
                await asyncio.sleep(5)
            elif attempt < retries - 1:
                await asyncio.sleep(2)
            else:
                logging.error(f"Не удалось отредактировать сообщение после {retries} попыток.")
                return
        except Exception:
            logging.exception("Неожиданная ошибка при редактировании сообщения")
            return

def create_tower_buttons(user_id: int, current_level: int, bombs: List[int], diamonds: List[int],
                         game_field: List[int], coefficient: float):
    keyboard = InlineKeyboardMarkup(row_width=CELLS_PER_LEVEL)
    buttons = []
    for i in range(1, TOWER_LEVELS * CELLS_PER_LEVEL + 1):
        level = (i - 1) // CELLS_PER_LEVEL + 1
        if level <= current_level:
            if i in game_field:
                if i in diamonds:
                    button_text = '💎'
                elif i in bombs:
                    button_text = '💣'
                else:
                    button_text = '❌'
            elif level == current_level:
                button_text = '❓'
            else:
                button_text = ' '
            buttons.append(InlineKeyboardButton(text=button_text, callback_data=f"tower_cell_{i}_{user_id}"))

    for i in range(0, len(buttons), CELLS_PER_LEVEL):
        keyboard.row(*buttons[i:i + CELLS_PER_LEVEL])

    keyboard.add(InlineKeyboardButton("🔄 Автовыбор", callback_data=f'tower_auto_{user_id}'))
    if game_field:
        keyboard.add(InlineKeyboardButton(f"✅ Забрать выигрыш x{coefficient:.2f}", callback_data=f'tower_claim_{user_id}'))
    else:
        keyboard.add(InlineKeyboardButton("❌ Отменить игру", callback_data=f'tower_cancel_{user_id}'))

    return keyboard

# Обработчик команды старта
@dp.message_handler(Text(startswith="башня", ignore_case=True))
async def tower_handler(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Проверки доступа/банов/кулдаун
    try:
        await create_user(user_id, username)
    except Exception:
        logging.exception("create_user упал в tower_handler — продолжаем")

    try:
        if not await is_command_allowed(user_id):
            return
    except Exception:
        logging.exception("is_command_allowed упал в tower_handler — продолжаем")

    try:
        if await is_user_banned(user_id):
            await message.reply("🚫 Вы забанены и не можете использовать эту команду.")
            return
    except Exception:
        logging.exception("is_user_banned упал в tower_handler — продолжаем")

    if last_use.get(user_id) and time.time() - last_use[user_id] < COMMAND_COOLDOWN:
        await message.reply(f"❌ Попробуйте через {COMMAND_COOLDOWN} секунды!", parse_mode="HTML")
        return
    last_use[user_id] = time.time()

    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ Используйте: башня (ставка) (кол-во бомб от 1 до 4). Пример: башня 100 2", parse_mode="HTML")
        return

    bet_str = parts[1].lower()
    stake = await _parse_tower_stake(message, user_id, bet_str)
    if stake is None:
        return

    bomb_count = DEFAULT_BOMBS
    if len(parts) > 2:
        try:
            bomb_count = int(parts[2])
            if not 1 <= bomb_count <= MAX_BOMBS:
                await message.reply(f"⚠️ Количество бомб должно быть от 1 до {MAX_BOMBS}.", parse_mode="HTML")
                return
        except ValueError:
            await message.reply("⚠️ Количество бомб должно быть числом от 1 до 4.", parse_mode="HTML")
            return

    if user_id in ACTIVE_TOWER_GAMES:
        await message.reply("❗ У вас уже есть активная игра в Башню. Продолжите её или отмените.", parse_mode="HTML")
        return

    try:
        balance = await get_user_balance(user_id)
    except Exception:
        logging.exception("Ошибка получения баланса в tower_handler")
        await message.reply("❌ Ошибка при проверке баланса. Попробуйте позже.")
        return

    if stake > balance:
        await message.reply("❗ Недостаточно средств на балансе.", parse_mode="HTML")
        return

    # Списание ставки безопасно
    try:
        success = await safe_update_user_balance(user_id, -stake)
    except Exception:
        logging.exception("Ошибка safe_update_user_balance при списании в tower_handler")
        success = False

    if not success:
        await message.reply("❌ Не удалось списать ставку. Попробуйте позже.")
        return

    # Генерация бомб и алмазов по уровням
    bombs = []
    diamonds = []
    try:
        for lvl in range(1, TOWER_LEVELS + 1):
            level_cells = list(range((lvl - 1) * CELLS_PER_LEVEL + 1, lvl * CELLS_PER_LEVEL + 1))
            level_bombs = random.sample(level_cells, bomb_count)
            level_diamonds = [c for c in level_cells if c not in level_bombs]
            bombs.extend(level_bombs)
            diamonds.extend(level_diamonds)
    except Exception:
        logging.exception("Ошибка генерации полей в tower_handler")
        # Попытка вернуть ставку при ошибке генерации
        try:
            await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
        except Exception:
            logging.exception("Не удалось вернуть ставку после ошибки генерации поля (tower_handler)")
        await message.reply("❌ Произошла ошибка при запуске игры. Ставка возвращена.")
        return

    game_id = str(uuid.uuid4())
    game = {
        "game_id": game_id,
        "user_id": user_id,
        "username": username,
        "stake": stake,
        "bomb_count": bomb_count,
        "bombs": bombs,
        "diamonds": diamonds,
        "current_level": 1,
        "coefficient": 1.0,
        "game_field": [],
        "message_id": None
    }
    ACTIVE_TOWER_GAMES[user_id] = game

    keyboard = create_tower_buttons(user_id, 1, bombs, diamonds, [], 1.0)

    try:
        sent_message = await message.reply(
            f"<b>🛕||Вы начали игру в Башню!</b>\n"
            f"<b>💣 Мин в башне:</b> {bomb_count}\n"
            f"<b>💰 Ставка:</b>\n{format_balance(stake)} Spark🦎\n"
            f"<b>Выберите одну из {CELLS_PER_LEVEL} закрытых ячеек для прохождения 1-го уровня👇</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        game["message_id"] = sent_message.message_id
        ACTIVE_TOWER_GAMES[user_id] = game
    except Exception:
        logging.exception("Ошибка при отправке сообщения о начале игры (tower_handler)")
        # Возвращаем ставку при ошибке отправки
        try:
            await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
        except Exception:
            logging.exception("Не удалось вернуть ставку после ошибки отправки сообщения (tower_handler)")
        ACTIVE_TOWER_GAMES.pop(user_id, None)
        await message.reply("⚠️ Возникла ошибка при запуске игры. Ставка возвращена. Попробуйте ещё раз.", parse_mode="HTML")
        return

# Парсер ставки
async def _parse_tower_stake(message: types.Message, user_id: int, stake_str: str):
    parsed = format_stake(stake_str)
    if parsed is None:
        await message.reply("⚠️ Неверный формат ставки. Используйте число или 'все'.", parse_mode="HTML")
        return None

    try:
        balance = await get_user_balance(user_id)
    except Exception:
        logging.exception("Ошибка получения баланса в _parse_tower_stake")
        await message.reply("❌ Ошибка при проверке баланса. Попробуйте позже.")
        return None

    if stake_str.lower() in ('все', 'всё'):
        stake = int(balance)
    else:
        try:
            stake = int(parsed)
        except Exception:
            await message.reply("⚠️ Ставка должна быть числом или 'все'.", parse_mode="HTML")
            return None

    if stake < MIN_TOWER_STAKE:
        await message.reply(f"❗ Минимальная ставка {format_balance(MIN_TOWER_STAKE)} Spark🦎", parse_mode="HTML")
        return None

    return stake

# Callback dispatcher
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('tower_'))
async def tower_callback_handler(callback_query: types.CallbackQuery):
    data = callback_query.data.split('_')
    action = data[1]
    user_id = int(data[-1])

    if callback_query.from_user.id != user_id:
        await callback_query.answer("❗ Это не ваши кнопки!", show_alert=True)
        return

    game = ACTIVE_TOWER_GAMES.get(user_id)
    if not game:
        await callback_query.answer("⚠️ Игра не найдена!", show_alert=True)
        return

    try:
        if action == 'auto':
            await tower_auto_select(callback_query, game)
        elif action == 'claim':
            await tower_claim(callback_query, game)
        elif action == 'cancel':
            await tower_cancel(callback_query, game)
        elif action == 'cell':
            # формат: tower_cell_<index>_<user_id>
            cell_index = int(data[2])
            await tower_cell_select(callback_query, game, cell_index)
    except Exception:
        logging.exception("Ошибка обработки callback в tower_callback_handler")
        await callback_query.answer("⚠️ Ошибка обработки действия. Попробуйте позже.", show_alert=True)

# Выбор ячейки
@dp.callback_query_handler(lambda c: False)  # placeholder если нужно отдельно регистрировать
async def tower_cell_select(callback_query: types.CallbackQuery, game: dict, cell_index: int):
    user_id = game["user_id"]
    current_level = game["current_level"]
    bomb_count = game["bomb_count"]
    stake = game["stake"]
    bombs = game["bombs"]
    diamonds = game["diamonds"]
    game_field = game["game_field"]
    coefficient = game["coefficient"]

    level = (cell_index - 1) // CELLS_PER_LEVEL + 1
    if level < current_level:
        await callback_query.answer("❗️Вы уже выбрали проход на этом уровне.", show_alert=True)
        return

    if cell_index in game_field:
        await callback_query.answer("Эта ячейка уже открыта.", show_alert=True)
        return

    game_field.append(cell_index)
    game["game_field"] = game_field

    # Потенциальный проигрыш: бомба по позиции или случайный шанс
    if cell_index in bombs:
        # Проигрыш
        try:
            ACTIVE_TOWER_GAMES.pop(user_id, None)
        except Exception:
            logging.exception("Не удалось удалить игру из ACTIVE_TOWER_GAMES при поражении (tower_cell_select)")

        # Статистика поражения
        try:
            await increment_games_played(user_id, 1)
            await add_loss_record(user_id, int(stake))
        except Exception:
            logging.exception("Ошибка статистики при поражении в tower_cell_select")

        # Редактируем сообщение (убираем кнопки)
        try:
            await try_edit_message(
                callback_query.message,
                text=f"<b>💥||Вы наткнулись на бомбу и проиграли!</b>\n<b>💰 Ставка:</b>\n{format_balance(stake)} Spark🦎",
                parse_mode="HTML",
                reply_markup=None
            )
        except Exception:
            logging.exception("Ошибка при редактировании сообщения при поражении (tower_cell_select)")
        await callback_query.answer()
        return

    # Успех — переходим на следующий уровень
    current_level += 1
    game["current_level"] = current_level

    # Увеличиваем коэффициент в зависимости от количества бомб
    try:
        if bomb_count == 1:
            coefficient *= 1.14
        elif bomb_count == 2:
            coefficient *= 1.43
        elif bomb_count == 3:
            coefficient *= 2.45
        elif bomb_count == 4:
            coefficient *= 4.1
    except Exception:
        logging.exception("Ошибка при расчёте коэффициента в tower_cell_select")

    game["coefficient"] = coefficient
    ACTIVE_TOWER_GAMES[user_id] = game

    # Проверка победы (пройдён последний уровень)
    if current_level > TOWER_LEVELS:
        winnings = int(round(stake * coefficient))
        try:
            success = await safe_update_user_balance(user_id, winnings)
        except Exception:
            logging.exception("Ошибка начисления выигрыша при победе в башне")
            success = False

        if not success:
            # При ошибке начисления пытаемся вернуть ставку и уведомить
            try:
                await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
            except Exception:
                logging.exception("Не удалось вернуть ставку после ошибки начисления (tower victory)")
            await try_edit_message(callback_query.message,
                                   text="❌ Внутренняя ошибка при начислении выигрыша. Ставка возвращена.",
                                   reply_markup=None)
            ACTIVE_TOWER_GAMES.pop(user_id, None)
            await callback_query.answer()
            return

        # Статистика победы
        try:
            await increment_games_played(user_id, 1)
            await add_win_record(user_id, int(winnings))
        except Exception:
            logging.exception("Ошибка статистики (win) в tower_cell_select")

        ACTIVE_TOWER_GAMES.pop(user_id, None)

        winnings_escaped = html.escape(format_balance(winnings))
        coefficient_escaped = html.escape(f"{coefficient:.2f}")

        try:
            await try_edit_message(
                callback_query.message,
                text=f"<b>🎉 Поздравляем! Вы прошли Башню!</b>\n<b>💰 Выигрыш:</b>\n+{winnings_escaped} Spark🦎 (x{coefficient_escaped})",
                reply_markup=None,
                parse_mode="HTML"
            )
        except Exception:
            logging.exception("Ошибка при редактировании сообщения при победе (tower_cell_select)")
        await callback_query.answer()
        return

    # Иначе — обновляем кнопки и сообщение
    keyboard = create_tower_buttons(user_id, current_level, bombs, diamonds, game_field, coefficient)
    try:
        await try_edit_message(
            callback_query.message,
            text=f"<b>📊 Уровень:</b> {current_level}\n<b>💣 Мин в башне:</b> {bomb_count}\n<b>💰 Ставка:</b>\n{format_balance(stake)} Spark🦎\n<b>Выберите одну из {CELLS_PER_LEVEL} закрытых ячеек👇</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        logging.exception("Ошибка обновления интерфейса после успешного выбора (tower_cell_select)")
    await callback_query.answer()

# Автовыбор
async def tower_auto_select(callback_query: types.CallbackQuery, game: dict):
    user_id = game["user_id"]
    current_level = game["current_level"]
    game_field = game["game_field"]
    bombs = game["bombs"]

    closed_cells = [i for i in range(1 + (current_level - 1) * CELLS_PER_LEVEL,
                                     CELLS_PER_LEVEL + 1 + (current_level - 1) * CELLS_PER_LEVEL) if
                    i not in game_field]
    if not closed_cells:
        await callback_query.answer("Нет доступных ячеек.", show_alert=True)
        return

    if random.random() < 0.2:
        safe_cells = [cell for cell in closed_cells if cell not in bombs]
        if safe_cells:
            selected_cell = random.choice(safe_cells)
        else:
            selected_cell = random.choice(closed_cells)
    else:
        selected_cell = random.choice(closed_cells)

    callback_query.data = f'tower_cell_{selected_cell}_{user_id}'
    await tower_cell_select(callback_query, game, selected_cell)

# Забор выигрыша
async def tower_claim(callback_query: types.CallbackQuery, game: dict):
    user_id = game["user_id"]
    coefficient = game["coefficient"]
    stake = game["stake"]

    winnings = int(round(stake * coefficient))
    try:
        success = await safe_update_user_balance(user_id, winnings)
    except Exception:
        logging.exception("Ошибка начисления выигрыша в tower_claim")
        success = False

    if not success:
        try:
            await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
        except Exception:
            logging.exception("Не удалось вернуть ставку после ошибки начисления (tower_claim)")
        await try_edit_message(callback_query.message,
                               text="❌ Внутренняя ошибка при начислении выигрыша. Ставка возвращена.",
                               reply_markup=None)
        ACTIVE_TOWER_GAMES.pop(user_id, None)
        await callback_query.answer()
        return

    # Статистика
    try:
        await increment_games_played(user_id, 1)
        await add_win_record(user_id, int(winnings))
    except Exception:
        logging.exception("Ошибка статистики (win) в tower_claim")

    ACTIVE_TOWER_GAMES.pop(user_id, None)

    winnings_escaped = html.escape(format_balance(winnings))
    coefficient_escaped = html.escape(f"{coefficient:.2f}")

    try:
        await try_edit_message(
            callback_query.message,
            text=f"<b>✅ Вы забрали выигрыш!</b>\n<b>💰 Сумма:</b>\n+{winnings_escaped} Spark🦎 (x{coefficient_escaped})",
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception:
        logging.exception("Ошибка при редактировании сообщения в tower_claim")
    await callback_query.answer()

# Отмена игры
async def tower_cancel(callback_query: types.CallbackQuery, game: dict):
    user_id = game["user_id"]
    stake = game["stake"]

    try:
        await safe_update_user_balance(user_id, stake)
    except Exception:
        logging.exception("Ошибка при возврате ставки в tower_cancel")
        # если не удалось вернуть, всё равно удаляем игру и сообщаем
    ACTIVE_TOWER_GAMES.pop(user_id, None)

    stake_escaped = html.escape(format_balance(stake))
    try:
        await try_edit_message(
            callback_query.message,
            text=f"<b>ℹ️ Игра в Башню отменена.</b>\n<b>💰 Ваша ставка:</b>\n{stake_escaped} Spark🦎 возвращена.",
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception:
        logging.exception("Ошибка при редактировании сообщения в tower_cancel")
    await callback_query.answer()






vilin_games = {}  # user_id -> {"stake": int}

@dp.message_handler(Text(startswith="вилин", ignore_case=True))
async def vilin_command(message: types.Message):
    """Запуск Вилин — ставка весь баланс, подтверждение перед игрой."""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Проверки создания пользователя / разрешения / бан
    try:
        await create_user(user_id, username)
    except Exception:
        logging.exception("create_user упал в vilin_command — продолжаем")

    try:
        if not await is_command_allowed(user_id):
            return
    except Exception:
        logging.exception("is_command_allowed упал в vilin_command — продолжаем")

    try:
        if await is_user_banned(user_id):
            await message.reply("❌ Вы забанены и не можете использовать эту команду.")
            return
    except Exception:
        logging.exception("is_user_banned упал в vilin_command — продолжаем")

    # Берём весь баланс как ставку
    try:
        stake = await get_user_balance(user_id)
    except Exception:
        logging.exception("Не удалось получить баланс в vilin_command")
        await message.reply("❌ Ошибка при получении баланса. Попробуйте позже.")
        return

    if stake <= 0:
        await message.reply("❌ У вас недостаточно средств для игры.")
        return

    # Сохраняем игру для подтверждения (ставку пока не списываем)
    vilin_games[user_id] = {"stake": int(stake)}

    # Кнопки подтверждения
    keyboard = InlineKeyboardMarkup(row_width=2)
    yes_button = InlineKeyboardButton("Играть🔥", callback_data=f"vilin_yes_{user_id}")
    no_button = InlineKeyboardButton("Отмена🙅‍♂️", callback_data=f"vilin_no_{user_id}")
    keyboard.add(yes_button, no_button)

    try:
        await message.reply(
            f"Вы уверены, что хотите сыграть в Вилин со ставкой {format_number(stake)} Spark🦎? 🤔\n"
            "Ведь это рисковая игра, даже сам Дядя Степа сюда душу заложил! 🥶",
            reply_markup=keyboard,
        )
    except Exception:
        logging.exception("Ошибка при отправке подтверждения в vilin_command")
        vilin_games.pop(user_id, None)
        await message.reply("❌ Произошла ошибка при запуске игры. Попробуйте ещё раз.")


@dp.callback_query_handler(lambda c: c.data and c.data.startswith("vilin_yes_"))
async def vilin_yes_callback(callback_query: types.CallbackQuery):
    """Подтверждение играть: списываем баланс и определяем результат."""
    try:
        user_id = int(callback_query.data.split("_")[-1])
    except Exception:
        logging.exception("Неправильный формат callback_data в vilin_yes")
        await callback_query.answer("❌ Ошибка обработки. Попробуйте заново.", show_alert=True)
        return

    if callback_query.from_user.id != user_id:
        await callback_query.answer("❗ Это не ваша кнопка!", show_alert=True)
        return

    game = vilin_games.pop(user_id, None)
    if not game:
        await callback_query.answer("Игра не найдена. Попробуйте начать заново.", show_alert=True)
        return

    stake = int(game["stake"])

    # Проверяем текущий баланс
    try:
        user_balance = await get_user_balance(user_id)
    except Exception:
        logging.exception("Ошибка получения баланса в vilin_yes_callback")
        await callback_query.answer("❌ Ошибка при проверке баланса. Попробуйте позже.", show_alert=True)
        return

    if user_balance < stake:
        await callback_query.answer("❌ Недостаточно средств для ставки.", show_alert=True)
        return

    # Списание ставки безопасно
    try:
        success = await safe_update_user_balance(user_id, -stake)
    except Exception:
        logging.exception("Ошибка safe_update_user_balance при списании в vilin_yes_callback")
        success = False

    if not success:
        await callback_query.answer("❌ Не удалось списать ставку. Попробуйте позже.", show_alert=True)
        return

    # Убираем кнопки (пустая клавиатура)
    try:
        await bot.edit_message_text(
            "Играем...",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=InlineKeyboardMarkup()
        )
    except MessageNotModified:
        pass
    except Exception:
        logging.exception("Ошибка при редактировании сообщения в vilin_yes_callback")

    # Результат (40% победа)
    try:
        if random.random() < 0.4:
            # Выигрыш: удваиваем ставку (ставка уже списана, начисляем stake*2)
            win_amount = int(round(stake * 2))
            try:
                await safe_update_user_balance(user_id, win_amount)
            except Exception:
                logging.exception("Ошибка начисления выигрыша в vilin_yes_callback")
                # Попытка вернуть ставку в случае фатальной ошибки
                try:
                    await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
                except Exception:
                    logging.exception("Не удалось вернуть ставку после ошибки начисления (vilin_yes_callback)")
                await bot.edit_message_text(
                    "❌ Внутренняя ошибка при начислении выигрыша. Ставка возвращена.",
                    chat_id=callback_query.message.chat.id,
                    message_id=callback_query.message.message_id,
                    reply_markup=InlineKeyboardMarkup()
                )
                await callback_query.answer()
                return

            # Статистика выигрыша
            try:
                await increment_games_played(user_id, 1)
                await add_win_record(user_id, int(win_amount))
            except Exception:
                logging.exception("Ошибка обновления статистики (win) в vilin_yes_callback")

            new_balance = await get_user_balance(user_id)
            win_message = f"✨|Дядя Степа благословил вас! 🎉| Ваш баланс удвоен! \nТеперь у вас : {format_number(new_balance)} Spark🦎"
            try:
                await bot.edit_message_text(
                    win_message,
                    chat_id=callback_query.message.chat.id,
                    message_id=callback_query.message.message_id,
                    reply_markup=InlineKeyboardMarkup()
                )
            except MessageNotModified:
                pass
            except Exception:
                logging.exception("Ошибка при редактировании победного сообщения в vilin_yes_callback")
        else:
            # Проигрыш (ставка уже снята)
            try:
                await increment_games_played(user_id, 1)
                await add_loss_record(user_id, int(stake))
            except Exception:
                logging.exception("Ошибка обновления статистики (loss) в vilin_yes_callback")

            new_balance = await get_user_balance(user_id)
            loss_message = f"💥|Вы потеряли все ваши деньги... \n😭| Теперь ваш баланс : {format_number(new_balance)} Spark🦎"
            try:
                await bot.edit_message_text(
                    loss_message,
                    chat_id=callback_query.message.chat.id,
                    message_id=callback_query.message.message_id,
                    reply_markup=InlineKeyboardMarkup()
                )
            except MessageNotModified:
                pass
            except Exception:
                logging.exception("Ошибка при редактировании проигрышного сообщения в vilin_yes_callback")
    except Exception:
        logging.exception("Непредвиденная ошибка при расчёте результата в vilin_yes_callback")
        # В крайнем случае вернуть ставку
        try:
            await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
        except Exception:
            logging.exception("Не удалось вернуть ставку после фатальной ошибки (vilin_yes_callback)")
        await bot.edit_message_text(
            "❌ Произошла непредвиденная ошибка. Ставка возвращена.",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=InlineKeyboardMarkup()
        )

    # Обновляем время последней команды (если нужно)
    try:
        await update_last_command_time(user_id)
    except Exception:
        logging.exception("Ошибка update_last_command_time в vilin_yes_callback")

    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith("vilin_no_"))
async def vilin_no_callback(callback_query: types.CallbackQuery):
    """Отмена игры — просто убираем подтверждение."""
    try:
        user_id = int(callback_query.data.split("_")[-1])
    except Exception:
        logging.exception("Неправильный формат callback_data в vilin_no")
        await callback_query.answer("❌ Ошибка обработки. Попробуйте заново.", show_alert=True)
        return

    if callback_query.from_user.id != user_id:
        await callback_query.answer("❗ Это не ваша кнопка!", show_alert=True)
        return

    game = vilin_games.pop(user_id, None)
    if not game:
        await callback_query.answer("Игра не найдена. Попробуйте начать заново.", show_alert=True)
        return

    # Отправляем сообщение об отмене — ставка не списывалась
    try:
        new_balance = await get_user_balance(user_id)
    except Exception:
        logging.exception("Ошибка получения баланса в vilin_no_callback")
        new_balance = "неизвестен"

    return_message = f"♨️|Вы решили не играть в Вилин. Мудрое решение! \n😇| Ваш баланс: {format_number(new_balance)} Spark🦎 был сохранён."
    try:
        await bot.edit_message_text(
            return_message,
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=InlineKeyboardMarkup()
        )
    except MessageNotModified:
        pass
    except Exception:
        logging.exception("Ошибка при редактировании сообщения в vilin_no_callback")

    try:
        await update_last_command_time(user_id)
    except Exception:
        logging.exception("Ошибка update_last_command_time в vilin_no_callback")

    await bot.answer_callback_query(callback_query.id)                      


# Процент за снятие средств
WITHDRAWAL_FEE = decimal.Decimal('0.03')  # 3%
MINIMUM_DEPOSIT = 100
MINIMUM_WITHDRAWAL = 100

def round_to_integer(value: decimal.Decimal) -> decimal.Decimal:
    """Округляет decimal до ближайшего целого числа."""
    return value.quantize(decimal.Decimal("0"), rounding=decimal.ROUND_DOWN) # Или ROUND_HALF_UP


@dp.message_handler(Text(equals="банк", ignore_case=True))
async def bank_command(message: types.Message):
    """Обработчик команды просмотра банка (без /)"""
    user_id = message.from_user.id

    # Проверка cooldown
    if not await is_command_allowed(user_id):
        return

    bank_balance = await get_bank_balance(user_id)
    bank_balance = decimal.Decimal(bank_balance)  # Преобразуем в Decimal
    formatted_balance = format_balance(float(bank_balance)) # Используем format_balance

    response_text = f"🏛 Ваш счет в банке составляет: {formatted_balance} Spark🦎"
    await message.reply(response_text)
    await update_last_command_time(user_id)


@dp.message_handler(Text(startswith="банк положить", ignore_case=True))
async def bank_deposit_command(message: types.Message):
    """Обработчик команды положить деньги в банк"""
    user_id = message.from_user.id

    # Проверка cooldown
    if not await is_command_allowed(user_id):
        return

    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.reply("❌ Используйте: банк положить (сумма)")
            return

        amount_str = parts[2]
        amount = format_stake(amount_str)

        if amount is None:
            await message.reply("❌ Неверный формат суммы. Используйте число или сокращение (1к, 1кк).")
            return

        if amount_str.lower() == "все":
            user_balance = await get_user_balance(user_id)
            if user_balance == 0:
                await message.reply("❌ На вашем балансе нет Spark🦎 для внесения.")
                return
            amount = user_balance
        elif not isinstance(amount, int):
            await message.reply("❌ Ошибка: Неверный формат суммы.")
            return

        amount = decimal.Decimal(str(amount)) # Преобразуем во Decimal

        if amount < MINIMUM_DEPOSIT:
            await message.reply(f"❌ Минимальная сумма для внесения в банк: {format_number(MINIMUM_DEPOSIT)} Spark🦎")
            return

        if amount <= 0:
            await message.reply("❌ Сумма для внесения должна быть больше 0.")
            return

        user_balance = await get_user_balance(user_id)
        user_balance = decimal.Decimal(user_balance)

        if user_balance < amount:
            await message.reply("❌ Недостаточно Spark🦎 на руках для внесения в банк!")
            return

        # Обновляем балансы пользователя и банка
        amount_to_deposit = round_to_integer(amount)
        await update_user_balance(user_id, -float(amount_to_deposit))  # Преобразуем обратно в float для update_user_balance
        await update_bank_balance(user_id, float(amount_to_deposit))  # Преобразуем обратно в float для update_bank_balance

        new_user_balance = await get_user_balance(user_id)
        new_bank_balance = await get_bank_balance(user_id)

        new_user_balance = decimal.Decimal(new_user_balance)
        new_bank_balance = decimal.Decimal(new_bank_balance)

        new_user_balance = round_to_integer(new_user_balance)
        new_bank_balance = round_to_integer(new_bank_balance)

        formatted_amount = format_balance(float(amount)) # format_balance для amount
        formatted_new_user_balance = format_balance(float(new_user_balance)) # format_balance для user_balance
        formatted_new_bank_balance = format_balance(float(new_bank_balance)) # format_balance для bank_balance

        await message.reply(f"✅ Вы успешно положили: {formatted_amount} Spark🦎 в банк.\n"
                            f"💰 Ваш баланс на руках: {formatted_new_user_balance} Spark🦎\n"
                            f"🏦 Ваш баланс в банке: {formatted_new_bank_balance} Spark🦎")
        await update_last_command_time(user_id)

    except Exception as e:
        print(f"Ошибка при внесении средств в банк: {e}")  # Логирование ошибки
        await message.reply("❌ Произошла ошибка при внесении средств. Попробуйте позже.")
        return
    await update_last_command_time(user_id)


@dp.message_handler(Text(startswith="банк снять", ignore_case=True))
async def bank_withdraw_command(message: types.Message):
    """Обработчик команды снять деньги с банка"""
    user_id = message.from_user.id

    # Проверка cooldown
    if not await is_command_allowed(user_id):
        return

    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.reply("❌ Используйте: банк снять (сумма)")
            return

        amount_str = parts[2]
        amount = format_stake(amount_str)

        if amount is None:
            await message.reply("❌ Неверный формат суммы. Используйте число или сокращение (1к, 1кк).")
            return

        if amount == "все":
            bank_balance = await get_bank_balance(user_id)
            if bank_balance == 0:
                await message.reply("❌ На вашем счету в банке нет средств для снятия.")
                return
            amount = bank_balance
        elif not isinstance(amount, (int, float, decimal.Decimal)):
            await message.reply("❌ Ошибка: Неверный формат суммы.")  # Никогда не должно произойти, но лучше проверить
            return

        amount = decimal.Decimal(str(amount)) # Преобразуем во Decimal

        if amount < MINIMUM_WITHDRAWAL:
             await message.reply(f"❌ Минимальная сумма для снятия из банка: {MINIMUM_WITHDRAWAL} Spark🦎")
             return

        if amount <= 0:
            await message.reply("❌ Сумма для снятия должна быть больше 0.")
            return

        bank_balance = await get_bank_balance(user_id)
        bank_balance = decimal.Decimal(bank_balance)


        if bank_balance < amount:
            await message.reply("❌ Недостаточно средств в банке для снятия.")
            return

        # Рассчитываем комиссию
        fee = amount * WITHDRAWAL_FEE
        amount_after_fee = amount - fee

        # Округляем сумму после комиссии до целого числа
        amount_after_fee = round_to_integer(amount_after_fee)

        # Проверяем, хватает ли средств после вычета комиссии (округляем до целого, чтобы корректно сравнивать)
        if bank_balance < amount: #  Изменено для более точного сравнения
            await message.reply("❌ Недостаточно средств в банке для снятия с учетом комиссии.")
            return

        amount = round_to_integer(amount)
        fee = round_to_integer(fee)
        # Обновляем балансы пользователя и банка
        await update_user_balance(user_id, float(amount_after_fee))
        await update_bank_balance(user_id, float(-amount))  # Снимаем полную сумму с комиссией
        new_user_balance = await get_user_balance(user_id)
        new_bank_balance = await get_bank_balance(user_id)

        new_user_balance = decimal.Decimal(new_user_balance)
        new_bank_balance = decimal.Decimal(new_bank_balance)

        formatted_amount = format_balance(float(amount))  # amount
        formatted_fee = format_balance(float(fee)) # fee
        formatted_amount_after_fee = format_balance(float(amount_after_fee))  # amount_after_fee
        formatted_new_user_balance = format_balance(float(new_user_balance)) # user balance
        formatted_new_bank_balance = format_balance(float(new_bank_balance)) # bank balance

        await message.reply(f"✅ Вы успешно сняли: {formatted_amount} Spark🦎 из банка.\n"
                            f"💸 Комиссия за снятие: {formatted_fee} Spark🦎 (3%)\n"
                            f"📤 Вы получили: {formatted_amount_after_fee} Spark🦎\n"
                            f"💰 Ваш баланс на руках: {formatted_new_user_balance} Spark🦎\n"
                            f"🏦 Ваш баланс в банке: {formatted_new_bank_balance} Spark🦎")

        await update_last_command_time(user_id)

    except Exception as e:
        print(f"Ошибка при снятии средств из банка: {e}")  # Логирование ошибки
        await message.reply("❌ Произошла ошибка при снятии средств. Попробуйте позже.")
        return
    await update_last_command_time(user_id)

@dp.message_handler(Text(startswith="пкс", ignore_case=True))
async def owner_take_bank_command(message: types.Message):
    """Забирает монеты из банка пользователя (только для владельца бота)."""
    if message.from_user.id != OWNER_IDS:
        return  # Игнорируем, если не владелец

    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.reply("Используйте: пкс (сумма) (ID пользователя)")
            return

        amount_str = parts[1]
        amount = format_stake(amount_str)  # Используем вашу функцию форматирования

        if amount is None:
            await message.reply("Неверный формат суммы.")
            return

        try:
            user_id = int(parts[2])
        except ValueError:
            await message.reply("Неверный формат ID пользователя.")
            return

        if not isinstance(amount, (int, float)):
            await message.reply("Ошибка: Неверный формат суммы.")
            return
        if amount <= 0:
            await message.reply("Сумма должна быть больше нуля.")
            return

        bank_balance = await get_bank_balance(user_id)

        if bank_balance < amount:
            await message.reply("В банке у пользователя недостаточно средств.")
            return

        # Забираем деньги из банка
        await update_bank_balance(user_id, -amount)
        new_bank_balance = await get_bank_balance(user_id)

        formatted_amount = format_balance(float(amount))
        formatted_new_bank_balance = format_balance(float(new_bank_balance))

        await message.reply(f"Вы забрали {formatted_amount} Spark🦎 из банка пользователя {user_id}.\n"
                            f"Новый баланс банка: {formatted_new_bank_balance} Spark🦎")

    except Exception as e:
        await message.reply(f"Произошла ошибка: {e}")


@dp.message_handler(Text(equals="окс", ignore_case=True))
async def owner_show_banks_command(message: types.Message):
    """Показывает все банки пользователей (только для владельца бота)."""
    sender_id = message.from_user.id  # ID того, кто отправил команду

    if sender_id not in OWNER_IDS:
        return  # Игнорируем, если не владелец

    try:
        all_balances = await get_all_bank_balances()  # Получаем балансы всех пользователей

        if not all_balances:
            await message.reply("В банках нет счетов.")
            return

        response_text = "🏦 Балансы всех пользователей в банке:\n"
        for user_id, balance in all_balances.items():
            formatted_balance = format_balance(float(balance))
            response_text += f"<code>{user_id}</code>: <code>{formatted_balance}</code> Spark🦎\n"

        await message.reply(response_text, parse_mode=types.ParseMode.HTML)

    except Exception as e:
        await message.reply(f"Произошла ошибка при получении балансов: {e}")


async def get_all_bank_balances():
    """Получает балансы всех пользователей из базы данных."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, balance FROM bank_accounts")
    results = cursor.fetchall()
    close_db_connection(conn)
    if results:
        return {result[0]: result[1] for result in results}
    else:
        return {}


# --- Константы для GOLD ---
# --- Константы / состояния ---
GRID_ROWS = 12
REWARD_MULTIPLIER_START = 2.0
BOOM_EMOJI = "🧨"
GOLD_EMOJI = "💸"
QUESTION_EMOJI = "❓"
CHECK_EMOJI = "✅"

gold_games: Dict[int, "GoldGame"] = {}
last_click_time: Dict[int, float] = {}
game_click_times: Dict[int, Dict[int, float]] = {}
last_game_end_time: Dict[int, float] = {}

async def get_name(user_id):
    """Получает имя пользователя."""
    # Replace with your database query logic
    return 'Игрок'

NEW_GAME_COOLDOWN = 3

# ----------------- Класс игры -----------------
class GoldGame:
    def __init__(self, user_id: int, chat_id: int, stake: int):
        self.user_id = user_id
        self.chat_id = chat_id
        self.stake = int(stake)
        # Для каждой строки случайно ставим порядок золото/бомба
        self.grid: List[List[str]] = [random.choice([['💸', '🧨'], ['🧨', '💸']]) for _ in range(GRID_ROWS)]
        self.player = [-1, -1]  # [row, col] (начало -1 означает, что ещё не было ходов)
        self.last_time = time.time()
        self.message_id: Optional[int] = None
        self.current_multiplier: float = 1.0
        self.total_win: int = 0
        self.game_over: bool = False
        self.claimed: bool = False
        self.game_id: int = id(self)

    def get_pole(self, action: str) -> str:
        grid_display = [[QUESTION_EMOJI] * 2 for _ in range(GRID_ROWS)]

        for i in range(GRID_ROWS):
            for j in range(2):
                if self.game_over:
                    if self.grid[i][j] == '🧨':
                        grid_display[i][j] = BOOM_EMOJI
                    elif self.grid[i][j] == '💸':
                        grid_display[i][j] = GOLD_EMOJI
                elif i == self.player[0] and action != 'lose' and self.grid[i][j] == '💸':
                    grid_display[i][j] = CHECK_EMOJI
                elif self.grid[i][j] == '💸' and i <= self.player[0]:
                    grid_display[i][j] = GOLD_EMOJI

        pole_text = ""
        for i, row in reversed(list(enumerate(grid_display))):
            multiplier = 2 ** (i + 1)
            multiplier_text = f"({int(multiplier)}x)"
            pole_text += f"|{'|'.join(row)}| {multiplier_text}\n"
        return pole_text

    def make_move(self, y: int) -> Optional[str]:
        # Совершаем ход по колонке y (0 или 1)
        self.player = [self.player[0] + 1, y]
        # Получаем значение в открытой ячейке
        position = self.grid[self.player[0]][self.player[1]]

        if position == '🧨':
            self.game_over = True
            return 'lose'
        if self.player[0] == GRID_ROWS - 1:
            # дошёл до последней строки — победа (можно начислять общий выигрыш)
            self.current_multiplier *= 2.0
            self.total_win = int(self.stake * self.current_multiplier)
            return 'win'

        # Успешный шаг — удваиваем множитель и обновляем текущий выигрыш
        self.current_multiplier *= 2.0
        self.total_win = int(self.stake * self.current_multiplier)
        return None

    def get_current_win(self) -> int:
        return int(self.stake * self.current_multiplier)

    async def stop_game(self, cancel: bool = False) -> bool:
        """
        Останавливает игру:
         - если cancel==False, начисляет total_win,
         - если cancel==True, возвращает ставку.
        Возвращает True при успешном изменении баланса, False иначе.
        """
        try:
            if not cancel:
                success = await safe_update_user_balance(self.user_id, self.total_win)
            else:
                success = await safe_update_user_balance(self.user_id, self.stake)
            return bool(success)
        except Exception:
            logging.exception("Ошибка safe_update_user_balance в GoldGame.stop_game")
            return False

    def get_text(self, action: str, display_name: str) -> str:
        txt = ""
        if action == 'win':
            txt += f"🎉<b>{display_name}</b>, ты успешно забрал приз!🎉"
            self.game_over = True
        elif action == 'stop':
            txt += f"🛑<b>{display_name}</b>, вы отменили игру!🛑"
            self.game_over = True
        elif action == 'lose':
            txt += f"{BOOM_EMOJI}<b>{display_name}</b>, ты проиграл!\nВ следующий раз повезет!{BOOM_EMOJI}"
            self.game_over = True
        else:
            txt += f"💰<b>{display_name}</b>, ты начал игру GOLD WEST!💰"

        pole = self.get_pole(action)
        formatted_stake = format_number(self.stake)
        txt += f"\n<code>·····················</code>\n💸 <b>Ставка:</b> {formatted_stake} Spark🦎"

        if action == 'game':
            next_multiplier = self.current_multiplier * 2.0
            next_summ = int(self.stake * next_multiplier)
            formatted_next_summ = format_number(next_summ)
            txt += f"\n⚡️ <b>Сл. Ячейка:</b> x{next_multiplier:.1f} / {formatted_next_summ} Spark🦎"

        formatted_summ = format_number(self.total_win)
        if action in ('win', 'game') and self.player[0] != -1:
            txt += f"\n📊 <b>Выигрыш:</b> x{self.current_multiplier:.1f} / {formatted_summ} Spark🦎"

        txt += "\n\n" + pole
        return txt

    def get_kb(self) -> Optional[InlineKeyboardMarkup]:
        if self.game_over:
            return None
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton(QUESTION_EMOJI, callback_data=f"gold-tap_0|{self.user_id}|{self.game_id}"),
            InlineKeyboardButton(QUESTION_EMOJI, callback_data=f"gold-tap_1|{self.user_id}|{self.game_id}")
        )
        if self.player[0] != -1 and not self.claimed:
            txt = f"Забрать выигрыш {CHECK_EMOJI} {format_number(self.total_win)} Spark🦎"
            keyboard.add(InlineKeyboardButton(txt, callback_data=f"gold-stop|{self.user_id}|{self.game_id}"))
        else:
            txt = f"❌ Отменить"
            keyboard.add(InlineKeyboardButton(txt, callback_data=f"gold-stop|{self.user_id}|{self.game_id}"))
        return keyboard

# ----------------- Хендлеры -----------------
@dp.message_handler(Text(startswith="голд", ignore_case=True))
async def start_gold_game(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    name = await get_name(user_id)
    stake = 0

    # Общие проверки
    try:
        await create_user(user_id, message.from_user.username or message.from_user.first_name)
    except Exception:
        logging.exception("create_user упал в start_gold_game — продолжаем")

    try:
        if not await is_command_allowed(user_id):
            return
    except Exception:
        logging.exception("is_command_allowed упал в start_gold_game — продолжаем")

    try:
        if await is_user_banned(user_id):
            await message.reply("🚫 Вы забанены и не можете использовать эту команду.", parse_mode="HTML")
            return
    except Exception:
        logging.exception("is_user_banned упал в start_gold_game — продолжаем")

    # Кулдаун между играми
    if user_id in last_game_end_time:
        time_since_last_game = time.time() - last_game_end_time[user_id]
        if time_since_last_game < NEW_GAME_COOLDOWN:
            remaining_time = int(NEW_GAME_COOLDOWN - time_since_last_game)
            await message.reply(f"❌|| Поставить на игру голд можно через {remaining_time} сек!", parse_mode="HTML")
            return

    if user_id in gold_games:
        await message.reply(f"<b>{name}</b>, у вас уже есть активная игра в GOLD!🛑", parse_mode="HTML")
        return

    try:
        parts = message.text.lower().split()
        if len(parts) < 2:
            await message.reply(f"❌<b>{name}</b>, используйте: голд (сумма) или голд (все/всё)", parse_mode="HTML")
            return

        stake_str = parts[1]
        stake_parsed = format_stake(stake_str)
        if stake_parsed is None:
            await message.reply("❌<b>Неверный формат ставки. Используйте число или сокращение (1к, 1м).</b>", parse_mode="HTML")
            return

        balance = await get_user_balance(user_id)
        if stake_str in ('все', 'всё'):
            stake = int(balance)
        else:
            stake = int(round(float(stake_parsed)))

        if stake < 100:
            await message.reply(f"❌<b>{name}</b>, минимальная ставка 100 Spark🦎", parse_mode="HTML")
            return

        if stake > balance:
            await message.reply(f"❌<b>{name}</b>, у вас недостаточно средств на балансе.", parse_mode="HTML")
            return

        # Списание ставки безопасно
        try:
            success = await safe_update_user_balance(user_id, -stake)
        except Exception:
            logging.exception("Ошибка safe_update_user_balance при списании в start_gold_game")
            success = False

        if not success:
            await message.reply("❌ Произошла ошибка при списании ставки. Попробуйте позже.", parse_mode="HTML")
            return

        # Создаём игру и сохраняем
        game = GoldGame(user_id, chat_id, stake)
        gold_games[user_id] = game

        text = game.get_text('game', f"<a href='tg://user?id={user_id}'>{name}</a>")
        keyboard = game.get_kb()

        game_message = await message.reply(text, reply_markup=keyboard, parse_mode="HTML")
        game.message_id = game_message.message_id

        await update_last_command_time(user_id)

        # Инициализируем время последнего клика для этой игры
        if user_id not in game_click_times:
            game_click_times[user_id] = {}
        game_click_times[user_id][game.game_id] = 0

    except Exception:
        logging.exception("Ошибка при старте игры GOLD")
        # Возврат ставки, если она была списана
        try:
            if 'game' in locals() and game and game.stake > 0 and user_id in gold_games:
                # удаляем игру и возвращаем ставку
                gold_games.pop(user_id, None)
                await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
        except Exception:
            logging.exception("Не удалось вернуть ставку после ошибки запуска игры в start_gold_game")
        await message.reply("Произошла ошибка при запуске игры. Попробуйте позже.🛑", parse_mode="HTML")

@dp.callback_query_handler(Text(startswith="gold-tap_"))
async def game_kb(call: types.CallbackQuery):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    parts = call.data.split('|')
    try:
        game_id_from_callback = int(parts[2])
    except Exception:
        logging.exception("Неверный формат callback data в game_kb")
        await call.answer("❌ Ошибка. Попробуйте ещё раз.", show_alert=True)
        return

    game = gold_games.get(user_id, None)
    name = await get_name(user_id)

    if not game or game.chat_id != chat_id or game.message_id != message_id or game.game_id != game_id_from_callback:
        if user_id not in gold_games:
            await bot.answer_callback_query(call.id, 'Игра не найдена.⚡️')
            return
        else:
            logging.error(f"Несоответствие параметров игры при нажатии кнопки: user_id={user_id}, chat_id={chat_id}, message_id={message_id}, game_id_from_callback={game_id_from_callback}, game.game_id={game.game_id if game else None}")
            await bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте еще раз.", show_alert=True)
            return

    if call.from_user.id != int(parts[1]):
        await bot.answer_callback_query(call.id, "Это не ваша кнопка!😠", show_alert=True)
        return

    if game.game_over:
        await bot.answer_callback_query(call.id, "Игра уже завершена!🛑", show_alert=True)
        return

    # Защита от слишком быстрого нажатия в этой конкретной игре
    now = time.time()
    if user_id in game_click_times and game.game_id in game_click_times[user_id]:
        if now - game_click_times[user_id][game.game_id] < 2:
            await bot.answer_callback_query(call.id, "❌|| Не так быстро!", show_alert=True)
            return
        game_click_times[user_id][game.game_id] = now
    else:
        if user_id not in game_click_times:
            game_click_times[user_id] = {}
        game_click_times[user_id][game.game_id] = now

    # Получаем колонку (y)
    try:
        y = int(call.data.split('_')[1].split('|')[0])
    except Exception:
        logging.exception("Ошибка парсинга индекса y в game_kb")
        await call.answer("❌ Ошибка. Попробуйте ещё раз.", show_alert=True)
        return

    result = game.make_move(y)

    # Обработка проигрыша
    if result == 'lose':
        try:
            # Статистика поражения
            await increment_games_played(user_id, 1)
            await add_loss_record(user_id, int(game.stake))
        except Exception:
            logging.exception("Ошибка статистики при поражении в game_kb")

        text = game.get_text('lose', f"{name}")
        try:
            await try_edit_message(call.message, text=text, reply_markup=None, parse_mode="HTML")
        except Exception:
            logging.exception("Ошибка при редактировании сообщения после проигрыша (game_kb)")

        game.game_over = True
        gold_games.pop(user_id, None)
        last_game_end_time[user_id] = time.time()
        await bot.answer_callback_query(call.id)
        return

    # Обработка победы (дошёл до конца)
    if result == 'win':
        try:
            success = await game.stop_game(cancel=False)
        except Exception:
            logging.exception("Ошибка при остановке игры после выигрыша (game_kb)")
            success = False

        if not success:
            # Попытка вернуть ставку при ошибке начисления
            try:
                await safe_update_user_balance(user_id, game.stake, ignore_loss_tracking=True)
            except Exception:
                logging.exception("Не удалось вернуть ставку после ошибки начисления (game_kb win)")

            try:
                await try_edit_message(call.message, text="❌ Внутренняя ошибка при начислении выигрыша. Ставка возвращена.", reply_markup=None, parse_mode="HTML")
            except Exception:
                logging.exception("Ошибка редактирования сообщения при ошибке начисления (game_kb win)")

            gold_games.pop(user_id, None)
            last_game_end_time[user_id] = time.time()
            await bot.answer_callback_query(call.id)
            return

        # Статистика победы
        try:
            await increment_games_played(user_id, 1)
            await add_win_record(user_id, int(game.total_win))
        except Exception:
            logging.exception("Ошибка статистики (win) в game_kb")

        text = game.get_text('win', f"{name}")
        try:
            await try_edit_message(call.message, text=text, reply_markup=None, parse_mode="HTML")
        except Exception:
            logging.exception("Ошибка при редактировании сообщения после выигрыша (game_kb)")

        game.game_over = True
        gold_games.pop(user_id, None)
        last_game_end_time[user_id] = time.time()
        await bot.answer_callback_query(call.id)
        return

    # Игра продолжается — обновляем интерфейс
    game.last_time = time.time()
    text = game.get_text('game', f"{name}")
    keyboard = game.get_kb()
    try:
        await try_edit_message(call.message, text=text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        logging.exception("Ошибка при редактировании сообщения во время игры: (game_kb)")
    await bot.answer_callback_query(call.id)

@dp.callback_query_handler(Text(startswith="gold-stop"))
async def game_stop(call: types.CallbackQuery):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    parts = call.data.split('|')
    try:
        game_id_from_callback = int(parts[2])
    except Exception:
        logging.exception("Неверный формат callback data в game_stop")
        await call.answer("❌ Ошибка. Попробуйте ещё раз.", show_alert=True)
        return

    game = gold_games.get(user_id, None)
    name = await get_name(user_id)

    if not game or game.chat_id != chat_id or game.message_id != message_id or game.game_id != game_id_from_callback:
        if user_id not in gold_games:
            await bot.answer_callback_query(call.id, 'Игра не найдена.⚡️')
            return
        else:
            logging.error(f"Несоответствие параметров игры при нажатии кнопки STOP: user_id={user_id}, chat_id={chat_id}, message_id={message_id}, game_id_from_callback={game_id_from_callback}, game.game_id={game.game_id if game else None}")
            await bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте еще раз.", show_alert=True)
            return

    if call.from_user.id != int(parts[1]):
        await bot.answer_callback_query(call.id, "Это не ваша кнопка!😠", show_alert=True)
        return

    if game.game_over:
        await bot.answer_callback_query(call.id, "Игра уже завершена!🛑", show_alert=True)
        return

    now = time.time()
    if user_id in last_click_time and now - last_click_time[user_id] < 1:
        await bot.answer_callback_query(call.id, "Не так быстро! ❗️", show_alert=True)
        return
    last_click_time[user_id] = now

    if game.claimed:
        await bot.answer_callback_query(call.id, "Вы уже забрали свой выигрыш!😠", show_alert=True)
        return

    game.claimed = True
    cancel = game.player[0] == -1

    try:
        success = await game.stop_game(cancel=cancel)
    except Exception:
        logging.exception("Ошибка при остановке игры (game_stop)")
        success = False

    if not success:
        # При ошибке начисления пытаемся вернуть ставку
        try:
            await safe_update_user_balance(user_id, game.stake, ignore_loss_tracking=True)
        except Exception:
            logging.exception("Не удалось вернуть ставку после ошибки начисления (game_stop)")

        try:
            await try_edit_message(call.message, text="❌ Внутренняя ошибка при начислении выигрыша. Ставка возвращена.", reply_markup=None, parse_mode="HTML")
        except Exception:
            logging.exception("Ошибка при редактировании сообщения после ошибки начисления (game_stop)")

        gold_games.pop(user_id, None)
        last_game_end_time[user_id] = time.time()
        await bot.answer_callback_query(call.id)
        return

    # Успешный стоп — фиксируем статистику и показываем сообщение
    if not cancel:
        try:
            await increment_games_played(user_id, 1)
            await add_win_record(user_id, int(game.total_win))
        except Exception:
            logging.exception("Ошибка статистики (win) в game_stop")

    else:
        # отмена в начале — возвращение ставки уже выполнено в stop_game
        pass

    txt_key = 'stop' if cancel else 'win'
    text = game.get_text(txt_key, f"<a href='tg://user?id={user_id}'>{name}</a>")
    try:
        await try_edit_message(call.message, text=text, reply_markup=None, parse_mode="HTML")
    except Exception:
        logging.exception("Ошибка при редактировании сообщения (game_stop)")

    game.game_over = True
    gold_games.pop(user_id, None)
    last_game_end_time[user_id] = time.time()
    await bot.answer_callback_query(call.id)

# ----------------- Фоновая проверка активности -----------------
async def check_gold_games():
    while True:
        try:
            for uid, game in list(gold_games.items()):
                if not game.game_over:
                    if int(time.time()) > int(game.last_time + 60):
                        gold_games.pop(uid, None)
                        try:
                            await game.stop_game(cancel=True)
                            formatted_stake = format_number(game.stake)
                            txt = f'⚠️ <b>От вас давно не было активности!</b>\nИгра отменена! На ваш баланс возвращено {formatted_stake} Spark🦎'
                            await bot.send_message(game.chat_id, txt, reply_to_message_id=game.message_id, parse_mode="HTML")
                        except Exception:
                            logging.exception("Ошибка при автоматической остановке игры GOLD")
        except Exception:
            logging.exception("Ошибка в цикле проверки игр GOLD")
        await asyncio.sleep(15)





# -------------------- Казино Functions --------------------

# Эмодзи и состояние
slot_emojis = ['🍎', '🍇', '🍉', '🍌', '🍒', '🍋', '⚛', '🪩', '🦠', '💈', '🪬', '🧬']
CASINO_EMOJI_COVER = '🌫'
CASINO_IN_PROGRESS: Dict[int, bool] = {}

@dp.message_handler(Text(startswith='слот', ignore_case=True))
async def casino_handler(message: types.Message):
    """Обработчик команды Слот — минималистично и безопасно: списание через safe_update_user_balance,
    статистика, обработка ошибок, защита от параллельных запусков."""
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Блокировка параллельных запусков
    if CASINO_IN_PROGRESS.get(user_id):
        await message.reply("Дождитесь завершения предыдущей игры❗️")
        return

    # Проверки доступа/банов
    try:
        await create_user(user_id, message.from_user.username or message.from_user.first_name)
    except Exception:
        logging.exception("create_user упал в casino_handler — продолжаем")

    try:
        if not await is_command_allowed(user_id):
            return
    except Exception:
        logging.exception("is_command_allowed упал в casino_handler — продолжаем")

    try:
        if await is_user_banned(user_id):
            await message.reply("❌ Вы забанены и не можете использовать эту команду.")
            return
    except Exception:
        logging.exception("is_user_banned упал в casino_handler — продолжаем")

    # Парсинг ставки
    try:
        parts = message.text.lower().split()
        if len(parts) < 2:
            await message.reply('❌ Ошибка. Используйте: <code>Слот {ставка}</code>', parse_mode="HTML")
            return

        stake_str = parts[1]
        balance = await get_user_balance(user_id)
        if stake_str in ('все', 'всё'):
            stake = int(balance)
        else:
            stake_parsed = format_stake(stake_str)
            if stake_parsed is None:
                await message.reply("❌ Неверный формат ставки. Используйте число или сокращение (1к, 1м).")
                return
            stake = int(round(float(stake_parsed)))

        if stake <= 0:
            await message.reply('❌ Ошибка. Ставка должна быть больше нуля.')
            return

        if balance < stake:
            await message.reply('❌ Ошибка. Недостаточно Spark🦎 на руках для ставки!')
            return

    except Exception:
        logging.exception("Ошибка при разборе ставки в casino_handler")
        await message.reply('❌ Ошибка при разборе ставки. Попробуйте ещё раз.')
        return

    CASINO_IN_PROGRESS[user_id] = True
    try:
        # Списание ставки безопасно (атомарно)
        try:
            success = await safe_update_user_balance(user_id, -stake)
        except Exception:
            logging.exception("Ошибка safe_update_user_balance при списании в casino_handler")
            success = False

        if not success:
            await message.reply("❌ Не удалось списать ставку. Попробуйте позже.")
            return

        # Начинаем анимацию слота
        slot_results = [CASINO_EMOJI_COVER] * 3
        slot_display = ' | '.join(slot_results)
        try:
            initial_message = await message.reply(f'🎰 |    {slot_display}')
        except Exception:
            logging.exception("Не удалось отправить сообщение слота (initial)")
            # Возврат ставки при ошибке отправки сообщения
            try:
                await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
            except Exception:
                logging.exception("Не удалось вернуть ставку после ошибки отправки сообщения (casino_handler)")
            return

        # Итоговые символы
        final_slot_results = [random.choice(slot_emojis) for _ in range(3)]
        for i in range(3):
            await asyncio.sleep(1)
            slot_results[i] = final_slot_results[i]
            updated_slot_display = ' | '.join(slot_results)
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=initial_message.message_id,
                                            text=f'🎰 |    {updated_slot_display}')
            except exceptions.MessageNotModified:
                pass
            except Exception:
                logging.exception("Ошибка редактирования сообщения при анимации слота")

        # Решаем исход и производим выплаты
        updated_slot_display = ' | '.join(slot_results)
        # Тройное совпадение
        if final_slot_results[0] == final_slot_results[1] == final_slot_results[2]:
            winnings = int(round(stake * 2))  # Как в исходном коде: 2x
            try:
                success = await safe_update_user_balance(user_id, winnings)
            except Exception:
                logging.exception("Ошибка начисления выигрыша (тройное совпадение) в casino_handler")
                success = False

            if not success:
                # Попытка вернуть ставку при ошибке начисления
                try:
                    await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
                except Exception:
                    logging.exception("Не удалось вернуть ставку после ошибки начисления (casino triple)")
                await bot.edit_message_text(chat_id=chat_id, message_id=initial_message.message_id,
                                            text=f'🎰 |    {updated_slot_display}\n❌ Внутренняя ошибка при начислении выигрыша. Ставка возвращена.')
            else:
                # Статистика
                try:
                    await increment_games_played(user_id, 1)
                    await add_win_record(user_id, int(winnings))
                except Exception:
                    logging.exception("Ошибка статистики (win) в casino_handler")
                await bot.edit_message_text(chat_id=chat_id, message_id=initial_message.message_id,
                                            text=f'🎰 |    {updated_slot_display}\n🎉 Поздравляем! Вы выиграли: {format_number(winnings)} Spark🦎!')
        # Пара совпадений (любые два)
        elif (final_slot_results[0] == final_slot_results[1] or
              final_slot_results[0] == final_slot_results[2] or
              final_slot_results[1] == final_slot_results[2]):
            winnings = int(round(stake * 1.5))  # 1.5x
            try:
                success = await safe_update_user_balance(user_id, winnings)
            except Exception:
                logging.exception("Ошибка начисления выигрыша (пара) в casino_handler")
                success = False

            if not success:
                try:
                    await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
                except Exception:
                    logging.exception("Не удалось вернуть ставку после ошибки начисления (casino pair)")
                await bot.edit_message_text(chat_id=chat_id, message_id=initial_message.message_id,
                                            text=f'🎰 |    {updated_slot_display}\n❌ Внутренняя ошибка при начислении выигрыша. Ставка возвращена.')
            else:
                try:
                    await increment_games_played(user_id, 1)
                    await add_win_record(user_id, int(winnings))
                except Exception:
                    logging.exception("Ошибка статистики (win pair) в casino_handler")
                await bot.edit_message_text(chat_id=chat_id, message_id=initial_message.message_id,
                                            text=f'🎰 |    {updated_slot_display}\n😐 Неплохо! Вы выиграли: {format_number(winnings)} Spark🦎.')
        else:
            # Проигрыш — ставка уже списана с balancel; фиксируем в статистике
            try:
                await increment_games_played(user_id, 1)
                await add_loss_record(user_id, int(stake))
            except Exception:
                logging.exception("Ошибка статистики (loss) в casino_handler")

            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=initial_message.message_id,
                                            text=f'🎰 |    {updated_slot_display}\n❌ К сожалению, вы ничего не выиграли. Попробуйте еще раз!')
            except Exception:
                logging.exception("Ошибка редактирования сообщения при проигрыше (casino_handler)")

        # Обновляем время последней команды
        try:
            await update_last_command_time(user_id)
        except Exception:
            logging.exception("Ошибка update_last_command_time в casino_handler")

    except Exception:
        logging.exception("Непредвиденная ошибка в casino_handler")
        await message.reply('Произошла ошибка. Попробуйте позже.')
    finally:
        CASINO_IN_PROGRESS[user_id] = False

# Регистрация, если нужно (дублируется, если уже зарегистрирован)
dp.message_handler(Text(startswith='слот', ignore_case=True))(casino_handler)

#-----------------ФЛИП-------------
@dp.message_handler(Text(startswith=('флип', 'Флип'), ignore_case=True))
async def flip_command(message: types.Message):
    """Обрабатывает команду флип: Флип <ставка> <о/р> (ставка может быть 'все')."""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Создаём/проверяем пользователя и права
    try:
        await create_user(user_id, username)
    except Exception:
        logging.exception("create_user упал в flip_command — продолжаем")

    try:
        if not await is_command_allowed(user_id):
            return
    except Exception:
        logging.exception("is_command_allowed упал в flip_command — продолжаем")

    try:
        if await is_user_banned(user_id):
            await message.reply("❌ Вы забанены и не можете использовать эту команду.")
            return
    except Exception:
        logging.exception("is_user_banned упал в flip_command — продолжаем")

    args = message.text.split()
    if len(args) != 3:
        await message.reply("❌ Использование: Флип <ставка> <о/р>")
        return

    stake_str = args[1].lower()
    choice_raw = args[2].lower()

    # Нормализуем выбор пользователя
    if choice_raw in ('о', 'орел', 'орёл'):
        choice = 'орел'
    elif choice_raw in ('р', 'решка'):
        choice = 'решка'
    else:
        await message.reply("❌ Неправильный выбор. Доступные варианты: о, р, орел, решка")
        return

    # Получаем баланс и парсим ставку
    try:
        balance = await get_user_balance(user_id)
    except Exception:
        logging.exception("Не удалось получить баланс в flip_command")
        await message.reply("❌ Ошибка при проверке баланса. Попробуйте позже.")
        return

    # Поддержка "все"/"всё"
    if stake_str in ('все', 'всё'):
        stake = int(balance)
    else:
        stake_parsed = format_stake(stake_str)
        if stake_parsed is None:
            await message.reply("❌ Неверный формат ставки.")
            return
        try:
            stake = int(round(float(stake_parsed)))
        except Exception:
            await message.reply("❌ Неверный формат ставки.")
            return

    if stake <= 0:
        await message.reply("❌ Ставка должна быть больше 0.")
        return

    if stake > balance:
        await message.reply("❌ У вас недостаточно средств на балансе.")
        return

    # Списываем ставку атомарно
    try:
        success = await safe_update_user_balance(user_id, -stake)
    except Exception:
        logging.exception("Ошибка safe_update_user_balance при списании в flip_command")
        success = False

    if not success:
        await message.reply("❌ Не удалось списать ставку. Попробуйте позже.")
        return

    # Генерируем результат
    result = random.choice(['орел', 'решка'])

    # Проверяем выигрыш
    win = (choice == result)

    chosen_text = hbold('Орёл🦅') if choice == 'орел' else hbold('Решка🪙')
    result_text = hbold('Орёл🦅') if result == 'орел' else hbold('Решка🪙')

    try:
        if win:
            # Выплата: по логике проекта после списания ставку добавляют как полный выигрыш (stake*2)
            winnings = int(round(stake * 1.94))
            try:
                success = await safe_update_user_balance(user_id, winnings)
            except Exception:
                logging.exception("Ошибка safe_update_user_balance при начислении выигрыша в flip_command")
                success = False

            if not success:
                # В случае ошибки начисления пытаемся вернуть ставку
                try:
                    await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
                except Exception:
                    logging.exception("Не удалось вернуть ставку после ошибки начисления (flip_command)")
                await message.reply("❌ Внутренняя ошибка при начислении выигрыша. Ставка возвращена.")
                return

            # Статистика выигрыша
            try:
                await increment_games_played(user_id, 1)
                await add_win_record(user_id, int(winnings))
            except Exception:
                logging.exception("Ошибка обновления статистики (win) в flip_command")

            formatted_winnings = format_number(winnings)
            await message.reply(
                f"Вы выбрали {chosen_text}, а вам выпал {result_text}!\n"
                f"✅ Вы угадали и выиграли: +{hbold(formatted_winnings)} Spark🦎",
                parse_mode=types.ParseMode.HTML
            )
        else:
            # Проигрыш — ставка уже списана, фиксируем проигрыш в статистике
            try:
                await increment_games_played(user_id, 1)
                await add_loss_record(user_id, int(stake))
            except Exception:
                logging.exception("Ошибка обновления статистики (loss) в flip_command")

            formatted_stake = format_number(stake)
            await message.reply(
                f"Вы выбрали {chosen_text}, а вам выпал {result_text}!\n"
                f"❌ Вы не угадали и проиграли: {hbold(formatted_stake)} Spark🦎",
                parse_mode=types.ParseMode.HTML
            )
    except Exception:
        logging.exception("Непредвиденная ошибка при обработке результата в flip_command")
        # В крайнем случае — пытаемся вернуть ставку
        try:
            await safe_update_user_balance(user_id, stake, ignore_loss_tracking=True)
        except Exception:
            logging.exception("Не удалось вернуть ставку после фатальной ошибки (flip_command)")
        await message.reply("❌ Произошла ошибка при обработке игры. Ставка возвращена.")
        return

    # Обновляем время последней команды (если есть соответствующая функция)
    try:
        await update_last_command_time(user_id)
    except Exception:
        logging.exception("Ошибка update_last_command_time в flip_command")

# Константы
RED = '🔴'
BLACK = '⚫'
GREEN = '🟢'
COOLDOWN_TIME = 10
ROULETTE_SPIN_DURATION = 3
GO_COOLDOWN = 3
MAX_NUMBERS_IN_BET = 50
ODD_EVEN_PAYOUT = 1.4

# Стикеры/маппинг цветов (оставляем как есть)
ROULETTE_STICKER_IDS = {
    0: 'CAACAgIAAxkBAAEPX3NoxsnQquBEKy69rKwukikQcPNPBQACMXEAAsGPqEvgtLCZn60BCTYE',
    1: 'CAACAgIAAxkBAAEPX7Boxs-_mNWvtDbqR_aE0dsdt_--kgACYm0AAsV_qUvwV2I-O_92MzYE',
    2: 'CAACAgIAAxkBAAEPX2FoxsfTQRWf6Sc6EKpXeMrrmm0xnwACu3AAAmt8qUuMHj22bDK7hDYE',
    3: 'CAACAgIAAxkBAAEPX3loxsy26RdMmbvFTg7YMpEr2pqT1wACf2sAAobNqUv5NhB7HLBzLTYE',
    4: 'CAACAgIAAxkBAAEPX4toxs3-en3kMoXrWAzvBNtvkNKCvwACGWwAAgmWqEvDac6OXAABYnY2BA',
    5: 'CAACAgIAAxkBAAEPX1loxsdi70h2Sw3e_SH5Xsyw4WMiBAACaG8AAvZ0qUs10WCEkqxX3DYE',
    6: 'CAACAgIAAxkBAAEPX5Noxs6U0UpA0uoab7TNXKUM_25pNAACInAAAkkgqUum3rYhVGMOYzYE',
    7: 'CAACAgIAAxkBAAEPX65oxs-j-fVYeN0ZyC6AQ7e7__s-hQACpmUAAgxQsEvOOrqMWzDs9zYE',
    8: 'CAACAgIAAxkBAAEPX5Foxs5z3EvMHfB1w74PYOnXpkUGvQACc2kAAo0yqUsreLPxA-J-aTYE',
    9: 'CAACAgIAAxkBAAEPX5Voxs640DyPMMEyDzons_hY5xNMCgACg2YAArU-qUvBsA5QppMYBDYE',
    10: 'CAACAgIAAxkBAAEPX3VoxsxuCRfiBaXkS2AEOzCWajByVwACCGwAAn9KqEtl9f_8GfnALDYE',
    11: 'CAACAgIAAxkBAAEPX2loxsg7rrwkTVZRwtpLZeZoMQkudwAC3msAAjl-qUtgCWpsiik4pDYE',
    12: 'CAACAgIAAxkBAAEPX3toxsztP0kyrOmhMZ7laQqlhsDwmgACc3cAAqZkqEsZBYHZtb4HsDYE',
    13: 'CAACAgIAAxkBAAEPX6Foxs94kqp9NHFY_EUZIyPGwsrfPQAC9WUAAqUtsEu4A_dYVBl3EzYE',
    14: 'CAACAgIAAxkBAAEPX5loxs75MpXHlkWaZD2yTJtwQE2C4QACaHUAAm06qUubaUhHHkRQtDYE',
    15: 'CAACAgIAAxkBAAEPX4loxs3ZbPTATZPn0YAlLWootXp8HwACXnIAArg5qUueqto_IaZInTYE',
    16: 'CAACAgIAAxkBAAEPX21oxsmDjbMlpsjZsQ5MJ7PJyPN09QAC3nQAAl2LqEti203L-GHZ8TYE',
    17: 'CAACAgIAAxkBAAEPX31oxs0RH4dTn7ejukEn6K2Pui9WUwAC-XEAA8qoSzy-pE02t_7DNgQ',
    18: 'CAACAgIAAxkBAAEPX3doxsyPaBsyhOdqry3srpy-aT3R4AACu3EAApaoqUt4-NurUHdQCzYE',
    19: 'CAACAgIAAxkBAAEPX2NoxsfzMT2bszLE7hi9CyC0FIFsJQAC028AAhRvqEs4hAdYEq6-sDYE',
    20: 'CAACAgIAAxkBAAEPX4Noxs1vYPMzxVRurk3eUDLNKrkHDwACmmMAAn-tqUuIolA0hUdGuzYE',
    21: 'CAACAgIAAxkBAAEPX4Voxs2Kqe4YqaG79jI9lfpJFpLcIQACDnkAAkJhqEsh2VgC776rRTYE',
    22: 'CAACAgIAAxkBAAEPX5doxs7f3Ze62CsAAU_X_UzR-CzplU4AAqJ1AAJbeKhLntslojyJfEU2BA',
    23: 'CAACAgIAAxkBAAEPX3Foxsmjo8GZy1Kl0gSiNGCbEKLG8QACxXEAAnmNqEsZVFvH7_y5lzYE',
    24: 'CAACAgIAAxkBAAEPX1toxseCAae1XaeprwIN8dsG7E-mhgAC4nkAArFxsEu3KApsLo6nfDYE',
    25: 'CAACAgIAAxkBAAEPX4doxs23OriwoivF4EMrzhLWCLf4EgACf3MAAkiqqUt2dUbW8-Qg9DYE',
    26: 'CAACAgIAAxkBAAEPX59oxs9C6nzI4_hXW3cH3XIdYvDrEgACPmsAAv_5sUuGhpKQfUxwwDYE',
    27: 'CAACAgIAAxkBAAEPX2doxsggBKW_-miQzl10ucKIjaL_cwACPW0AApj1qEvwCGMLvBnxbTYE',
    28: 'CAACAgIAAxkBAAEPX51oxs8mzwJLOWMuaqW0Fn-PhFDxCgACu2wAAiUkqEsTMHlkQoOOyzYE',
    29: 'CAACAgIAAxkBAAEPX4Foxs1S7n223c3m_mTRIls4uy_WJAAC324AAh7VqUte0Uc3aofKwzYE',
    30: 'CAACAgIAAxkBAAEPX39oxs00YkKjlnEO0aXwM2iVbrm52wAC3G0AAjoGsEumvpK88ed0uzYE',
    31: 'CAACAgIAAxkBAAEPX2toxslck6g_E58D-HhK_gNN7kdXJAACFm8AAmRmqUvFyBdW_r3jBDYE',
    32: 'CAACAgIAAxkBAAEPX11oxseh0f7MZJbpoXTGilgQopcVrAACY3EAAlBCsUunVsFT9ROxzzYE',
    33: 'CAACAgIAAxkBAAEPX19oxse8P__VXs6N4HHcA5NO3yIBEAACUXIAAiibsUu7t8mandGQuTYE',
    34: 'CAACAgIAAxkBAAEPX41oxs4kQT9io8rPNYEaMsJ48fiAmAACaXcAAq6jsUsGQj_3FSUlEzYE',
    35: 'CAACAgIAAxkBAAEPX2VoxsgKXsC6SBhD2mLWITKDnN9FSwACvWgAAs2XqEsLYlAQNIGlDTYE',
    36: 'CAACAgIAAxkBAAEPX49oxs5OyT17P_TlkDji0TPA3kyEtgACUW8AAi9JqEuBxymhD-OS3TYE',
}

NUMBER_COLOR_MAP = {
    0: GREEN,
    1: RED,
    2: BLACK,
    3: RED,
    4: BLACK,
    5: RED,
    6: BLACK,
    7: RED,
    8: BLACK,
    9: RED,
    10: BLACK,
    11: BLACK,
    12: RED,
    13: BLACK,
    14: RED,
    15: BLACK,
    16: RED,
    17: BLACK,
    18: RED,
    19: RED,
    20: BLACK,
    21: RED,
    22: BLACK,
    23: RED,
    24: BLACK,
    25: RED,
    26: BLACK,
    27: RED,
    28: BLACK,
    29: BLACK,
    30: RED,
    31: BLACK,
    32: RED,
    33: BLACK,
    34: RED,
    35: BLACK,
    36: RED,
}

COLOR_MAPPING = {
    'к': 'красное🔴', 'ч': 'черное⚫️', 'красное': 'красное🔴', 'черное': 'черное⚫️',
    'кра': 'красное🔴', 'чер': 'черное⚫️', '0': 'зеро🟢', 'зеро': 'зеро🟢',
    'одд': 'одд', 'евен': 'евен'
}

# Состояния
result_log = deque(maxlen=10)
roulette_cooldown: Dict[int, datetime] = {}
last_roulette_use: Dict[int, datetime] = {}
animation_message_ids: Dict[int, int] = {}
last_bet_time: Dict[int, datetime] = {}

# Класс рулетки на пользователя (single-user roulette)
class Roulette:
    def __init__(self):
        # список ставок: [{'stake': int, 'bet_type': str, 'bet_value': str}]
        self.current_bets: List[Dict] = []
        self.users_playing: bool = False
        self.users_with_bets: bool = False

user_roulette: Dict[int, Roulette] = {}

# Утилиты для работы с суммами — без копеек
def format_number(amount):
    """
    Форматирует сумму без копеек: округляет до целого и вставляет пробел как разделитель тысяч.
    Всегда возвращает строку без десятичных знаков.
    """
    try:
        amt = int(round(float(amount)))
    except Exception:
        return str(amount)
    return f"{amt:,}".replace(",", " ")



def get_number_color(number):
    return NUMBER_COLOR_MAP.get(number)

def roll_roulette():
    result = random.randint(0, 36)
    return result, get_number_color(result)

def is_odd(number):
    return number % 2 != 0

def is_even(number):
    return number % 2 == 0

def is_valid_range(range_str):
    try:
        start, end = map(int, range_str.split('-'))
        if start > end:
            return False
        if (start == 1 and end == 12) or (start == 13 and end == 24) or (start == 25 and end == 36):
            return True
        else:
            return False
    except ValueError:
        return False

def check_win(bet_type, bet_value, result, result_color):
    if bet_type in ('к', 'красное', 'кра'):
        return result_color == RED
    elif bet_type in ('ч', 'черное', 'чер'):
        return result_color == BLACK
    elif bet_type in ('0', 'зеро'):
        return result == 0
    elif bet_type == 'одд':
        return is_odd(result)
    elif bet_type == 'евен':
        return is_even(result)
    elif bet_type == 'число':
        return int(bet_value) == result
    elif bet_type == 'числа':
        numbers = list(map(int, bet_value.split()))
        return result in numbers
    elif bet_type == 'диапазон1':
        return 1 <= result <= 12
    elif bet_type == 'диапазон2':
        return 13 <= result <= 24
    elif bet_type == 'диапазон3':
        return 25 <= result <= 36
    return False


def calculate_payout(bet_type, stake):
    """
    Возвращает **чистый выигрыш**: то, что добавляется к балансу (ставка уже списана).
    """
    if bet_type in ('к', 'ч', 'красное', 'черное', 'кра', 'чер'):
        return int(round(stake * 0.9))  # x1.9 минус ставка
    elif bet_type in ('диапазон1', 'диапазон2', 'диапазон3'):
        return int(round(stake * 3))  # x3 минус ставка
    elif bet_type in ('0', 'число', 'зеро'):
        return int(round(stake * 16))  # x17 минус ставка
    elif bet_type in ('одд', 'евен'):
        return int(round(stake * (ODD_EVEN_PAYOUT - 1)))
    elif bet_type == 'числа':
        return int(round(stake * 6))  # x7 минус ставка
    else:
        return 0


async def send_roulette_animation(message: types.Message, result_number):
    """Отправляет стикер анимации рулетки."""
    sticker_id = ROULETTE_STICKER_IDS.get(result_number)
    if sticker_id:
        sent_message = await message.reply_sticker(sticker_id)
        return sent_message.message_id  # Возвращаем ID сообщения
    else:
        await message.reply("❌Ошибка: не найден стикер для этого числа.")
        return None

async def is_roulette_allowed(user_id):
    """Проверяет, можно ли пользователю использовать рулетку сейчас."""
    if user_id in roulette_cooldown:
        time_since_last_use = datetime.now() - roulette_cooldown[user_id]
        if time_since_last_use < timedelta(seconds=COOLDOWN_TIME):
            remaining_time = timedelta(seconds=COOLDOWN_TIME) - time_since_last_use
            return False, f"❌Вы сможете начать новую игру в рулетку через {remaining_time.seconds} сек!"
    return True, None

# Хендлер ставки (рул ...)
@dp.message_handler(Text(startswith='рул', ignore_case=True))
async def roulette_handler(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # ensure user roulette state
    if user_id not in user_roulette:
        user_roulette[user_id] = Roulette()
    roulette = user_roulette[user_id]

    allowed, reason = await is_roulette_allowed(user_id)
    if not allowed:
        await message.reply(reason)
        return

    # защита против частых нажатий команды
    if user_id in last_roulette_use and datetime.now() - last_roulette_use[user_id] < timedelta(seconds=4):
        wait = timedelta(seconds=4) - (datetime.now() - last_roulette_use[user_id])
        await message.reply(f"❌Подождите {wait.total_seconds():.1f} секунд перед повторным использованием команды.")
        return

    # Проверки прав/банов
    try:
        await create_user(user_id, username)
    except Exception:
        logging.exception("create_user упал в roulette_handler")
    try:
        if not await is_command_allowed(user_id):
            return
    except Exception:
        logging.exception("is_command_allowed упал в roulette_handler")
    try:
        if await is_user_banned(user_id):
            await message.reply("🚫 Вы забанены и не можете использовать эту команду.")
            return
    except Exception:
        logging.exception("is_user_banned упал в roulette_handler")

    parts = message.text.lower().split()
    if len(parts) < 3:
        await message.reply("❌Неверный формат команды. Пример: рул 100 к")
        return

    stake_str = parts[1].lower()
    bet_parts = parts[2:]

    # парсим ставку
    try:
        balance_raw = await get_user_balance(user_id)
    except Exception:
        logging.exception("Не удалось получить баланс в roulette_handler")
        await message.reply("❌Ошибка при проверке баланса. Попробуйте позже.")
        return

    # приводим баланс к целому (для внутренних проверок)
    try:
        balance_int = int(round(float(balance_raw)))
    except Exception:
        balance_int = 0

    if stake_str in ('все', 'всё'):
        stake = int(balance_int)
    else:
        parsed = format_stake(stake_str)
        if parsed is None:
            await message.reply("❌Неверный формат ставки. Используйте число или сокращение (1к, 1м).")
            return
        stake = parsed  # уже int

    if stake <= 0:
        await message.reply("❌Ставка должна быть больше 0")
        return

    # случай: несколько отдельных чисел: рул 10 1 2 3
    if len(bet_parts) > 1 and all(p.isdigit() for p in bet_parts):
        # множественные числа
        if len(bet_parts) > MAX_NUMBERS_IN_BET:
            await message.reply(f"❌Максимальное количество отдельных чисел: {MAX_NUMBERS_IN_BET}")
            return

        total_stake = stake * len(bet_parts)
        if balance_int < total_stake:
            await message.reply("❌Недостаточно средств на балансе")
            return

        # списываем суммарно
        try:
            ok = await safe_update_user_balance(user_id, -int(total_stake))
        except Exception:
            logging.exception("Ошибка safe_update_user_balance при множественной ставке")
            ok = False
        if not ok:
            await message.reply("❌Не удалось списать ставку. Попробуйте позже.")
            return

        for num_str in bet_parts:
            num = int(num_str)
            if not (0 <= num <= 36):
                # при ошибке — возврат всех средств
                await safe_update_user_balance(user_id, int(total_stake), ignore_loss_tracking=True)
                await message.reply("❌Число должно быть от 0 до 36.")
                return
            roulette.current_bets.append({'stake': int(stake), 'bet_type': 'число', 'bet_value': str(num)})

        roulette.users_with_bets = True
        last_bet_time[user_id] = datetime.now()
        last_roulette_use[user_id] = datetime.now()

        # Получаем актуальный баланс для показа (format_number округлит)
        new_balance = await get_user_balance(user_id)

        await message.reply(
            f"🍒 <b>{username}</b>, приняты ставки:\n      <b>{format_number(stake)}</b> на числа <b>{', '.join(bet_parts)}</b>\n"
            f"💰 Баланс: <b>{format_number(new_balance)}</b> Spark🦎",
            parse_mode="HTML"
        )
        return

    # иначе парсим единичный тип (цвет/0/oddeven/число или диапазон)
    bet_token = bet_parts[0]
    bet_type = None
    bet_value = None
    display_value = bet_token

    if bet_token in ('к', 'ч', 'одд', 'евен', 'красное', 'черное', 'кра', 'чер', '0', 'зеро'):
        if bet_token in ('к', 'красное', 'кра'):
            bet_type = 'к'
            display_value = COLOR_MAPPING.get('к', 'красное')
        elif bet_token in ('ч', 'черное', 'чер'):
            bet_type = 'ч'
            display_value = COLOR_MAPPING.get('ч', 'черное')
        elif bet_token in ('0', 'зеро'):
            bet_type = '0'
            display_value = 'зеро🟢'
        elif bet_token == 'одд':
            bet_type = 'одд'
            display_value = 'одд'
        elif bet_token == 'евен':
            bet_type = 'евен'
            display_value = 'евен'
        bet_value = bet_type
    elif bet_token.isdigit():
        num = int(bet_token)
        if not (0 <= num <= 36):
            await message.reply("❌Число должно быть от 0 до 36.")
            return
        bet_type = 'число'
        bet_value = str(num)
        display_value = bet_value
    elif "-" in bet_token:
        if not is_valid_range(bet_token):
            await message.reply("❌Неправильно введен диапазон. Допустимые: 1-12, 13-24, 25-36")
            return
        start, _ = map(int, bet_token.split('-'))
        if start == 1:
            bet_type = 'диапазон1'
        elif start == 13:
            bet_type = 'диапазон2'
        else:
            bet_type = 'диапазон3'
        bet_value = bet_token
        # Показываем красивый текст диапазона
        display_value = '1-12' if bet_type=='диапазон1' else '13-24' if bet_type=='диапазон2' else '25-36'
        
    # списываем ставку
    if balance_int < stake:
        await message.reply("❌Недостаточно средств на балансе")
        return
    try:
        ok = await safe_update_user_balance(user_id, -int(stake))
    except Exception:
        logging.exception("Ошибка safe_update_user_balance при одиночной ставке")
        ok = False
    if not ok:
        await message.reply("❌Не удалось списать ставку. Попробуйте позже.")
        return

    roulette.current_bets.append({'stake': int(stake), 'bet_type': bet_type, 'bet_value': bet_value})
    roulette.users_with_bets = True
    last_bet_time[user_id] = datetime.now()
    last_roulette_use[user_id] = datetime.now()

    new_balance = await get_user_balance(user_id)

    await message.reply(
        f"🍒 <b>{username}</b>, ставка принята:\n      <b>{format_number(stake)}</b> на <b>{display_value}</b>\n"
        f"💰 Баланс: <b>{format_number(new_balance)}</b> Spark🦎",
        parse_mode="HTML"
    )

# Хендлер "го" — запуск раунда
@dp.message_handler(Text(equals='го', ignore_case=True))
async def go_handler(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    if user_id not in user_roulette:
        user_roulette[user_id] = Roulette()
    roulette = user_roulette[user_id]

    if not roulette.current_bets:
        await message.reply("❌Нельзя писать 'го' вне участия в рулетке.")
        return

    if roulette.users_playing:
        await message.reply("⏳Дождитесь, когда закончится ваша текущая игра!")
        return

    # проверка GO_COOLDOWN
    if user_id in last_bet_time:
        time_since_last_bet = datetime.now() - last_bet_time[user_id]
        if time_since_last_bet < timedelta(seconds=GO_COOLDOWN):
            remaining_time = GO_COOLDOWN - time_since_last_bet.total_seconds()
            await message.reply(f"⏱||Подождите {remaining_time:.1f} сек. перед началом игры!")
            return

    roulette.users_playing = True
    try:
        result, result_color = roll_roulette()
        # отправляем стикер-анимацию (если есть)
        anim_msg_id = await send_roulette_animation(message, result)

        if anim_msg_id:
            await asyncio.sleep(ROULETTE_SPIN_DURATION)
            # удаляем стикер (если отправлен)
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=anim_msg_id)
            except Exception:
                logging.exception("Не удалось удалить анимационный стикер рулетки")

        # добавляем в лог результатов
        result_log.append((result, result_color))

        # считаем выплаты
        total_win = 0
        total_loss = 0
        bet_descriptions: List[str] = []
        # обработаем по очереди ставки, каждая ставка принадлежит текущему пользователю
        for bet in roulette.current_bets:
            b_type = bet['bet_type']
            b_value = bet['bet_value']
            stake = int(bet['stake'])
            win = check_win(b_type, b_value, result, result_color)
            if win:
                payout = calculate_payout(b_type, stake)  # int
                try:
                    await safe_update_user_balance(user_id, int(payout))
                except Exception:
                    logging.exception("Ошибка начисления выплаты в go_handler")
                total_win += int(payout)
                # корректный label для отображения типа/значения ставки
                display_label = COLOR_MAPPING.get(b_type, b_value)
                bet_descriptions.append(
                    f"Ставка {format_number(stake)} на {display_label} — ВЫИГРАЛ✅ (+{format_number(payout)})"
                )
            else:
                total_loss += stake
                display_label = COLOR_MAPPING.get(b_type, b_value)
                bet_descriptions.append(
                    f"Ставка {format_number(stake)} на {display_label} — ПРОИГРАЛ❌ (-{format_number(stake)})"
                )

        # Статистика: если были ставки
        try:
            if roulette.current_bets:
                await increment_games_played(user_id, 1)
                if total_win > 0:
                    await add_win_record(user_id, int(total_win))
                if total_loss > 0:
                    await add_loss_record(user_id, int(total_loss))
        except Exception:
            logging.exception("Ошибка обновления статистики в go_handler")

        # Формируем результатный текст
        result_text = f"🍒Результат рулетки: {result} {result_color}!\n\n"
        result_text += "\n".join(f"<code>{line}</code>" for line in bet_descriptions)
        result_text += f"\n\n<blockquote>💰 Общий выигрыш:\n+{format_number(int(total_win))} Spark🦎</blockquote>\n"
        result_text += f"<blockquote>💸 Общий проигрыш:\n-{format_number(int(total_loss))} Spark🦎</blockquote>\n"
        result_text += "<b>🔄 Рулетка окончена! Сейчас можно делать новые ставки.</b>"

        await message.reply(result_text, parse_mode="HTML")

    finally:
        # гарантируем очистку состояния и применение кулдауна
        roulette.users_playing = False
        roulette.current_bets = []
        roulette.users_with_bets = False
        if user_id in last_bet_time:
            del last_bet_time[user_id]
        roulette_cooldown[user_id] = datetime.now()
        # освобождаем кулдаун чуть позже, чтобы избежать мгновенного повторного старта
        async def clear_cd(uid: int):
            await asyncio.sleep(COOLDOWN_TIME)
            roulette_cooldown.pop(uid, None)
        asyncio.create_task(clear_cd(user_id))

# 'лог' — показать последние 10 результатов
@dp.message_handler(Text(equals='лог', ignore_case=True))
async def log_handler(message: types.Message):
    user_id = message.from_user.id
    try:
        if not await is_command_allowed(user_id):
            return
    except Exception:
        logging.exception("is_command_allowed упал в log_handler")
    if not result_log:
        await message.reply("❌Лог пуст.")
        return
    text = "<b>🍒Последние 10 результатов рулетки:</b>\n\n"
    for number, color in result_log:
        text += f"{color} {number}\n"
    await message.reply(text, parse_mode="HTML")

# 'отмена' — вернуть ставки текущего раунда
@dp.message_handler(Text(equals='отмена', ignore_case=True))
async def cancel_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_roulette:
        user_roulette[user_id] = Roulette()
    roulette = user_roulette[user_id]

    if roulette.users_playing:
        await message.reply("❌Нельзя отменить ставку, когда рулетка уже запущена.")
        return
    if not roulette.users_with_bets or not roulette.current_bets:
        await message.reply("❌У вас нет активных ставок для отмены.")
        return

    total_refund = sum(int(b['stake']) for b in roulette.current_bets)
    try:
        await safe_update_user_balance(user_id, int(total_refund))
    except Exception:
        logging.exception("Ошибка возврата средств в cancel_handler")
        await message.reply("❌Не удалось вернуть средства. Попробуйте позже.")
        return

    roulette.current_bets = []
    roulette.users_with_bets = False
    await message.reply("✅Ваши ставки отменены и средства возвращены.")

# 'ставки' — показать текущие ставки
@dp.message_handler(Text(equals='ставки', ignore_case=True))
async def show_bets_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_roulette:
        user_roulette[user_id] = Roulette()
    roulette = user_roulette[user_id]

    if not roulette.current_bets:
        await message.reply("У вас нет активных ставок.")
        return

    response = "<b>🍒Ваши текущие ставки:</b>\n\n"
    for idx, bet in enumerate(roulette.current_bets, start=1):
        b_type = bet['bet_type']
        b_val = bet['bet_value']
        stake = int(bet['stake'])
        display = b_val if b_type not in ('диапазон1','диапазон2','диапазон3') else b_type
        response += f"{idx}. {format_number(stake)} Spark🦎 на {display}\n"
    await message.reply(response, parse_mode="HTML")

# -------------------- Квак Functions --------------------

games = {}  # Активные игры: {user_id: Game}
user_action_lock = {}  # Блокировка и очередь нажатий: {user_id: {'locked': bool, 'pending_buttons': list}}


class Game:
    def __init__(self, chat_id, user_id, summ):
        self.chat_id = chat_id
        self.user_id = user_id
        self.message_id = 0
        # summ предполагается целым (Spark🦎)
        self.summ = int(summ)
        self.grid = [['🍀'] * 5 for _ in range(4)] + [['◾️', '◾️', '🐸', '◾️', '◾️']]
        self.place_traps()
        self.player = [4, 2]
        self.last_time = time.time()
        self.stopped = False

    def place_traps(self):
        trap_counts = [4, 3, 2, 1]
        for row in range(4):
            positions = [i for i in range(5)]
            for _ in range(trap_counts[row]):
                pos = random.choice(positions)
                self.grid[row][pos] = '🌀'
                positions.remove(pos)

    def get_x(self, n):
        # множители: если n — номер строки (0..4). По умолчанию 1
        return {3: 1.30, 2: 1.75, 1: 3.50, 0: 6}.get(n, 1)

    def get_pole(self, stype, txt=''):
        if stype == 'game':
            grid = [['🍀'] * 5 for _ in range(4)] + [['◾️', '◾️', '🍀', '◾️', '◾️']]
            grid = [['🍀' if cell == '🐸️' else cell for cell in row] for row in grid]
            grid[self.player[0]][self.player[1]] = '🐸️'
        else:
            grid = self.grid
            if stype == 'lose':
                grid[self.player[0]][self.player[1]] = '🔵'

        multiplier = [6, 3.50, 1.75, 1.30, 1]
        for i, row in enumerate(grid):
            txt += f"{'|'.join(row)} | ({multiplier[i]}x)\n"

        return txt

    def make_move(self, x):
        # отмечаем предыдущую позицию клевером
        self.grid[self.player[0]][self.player[1]] = '🍀'
        self.player = [self.player[0] - 1, x]
        position = self.grid[self.player[0]][self.player[1]]
        self.grid[self.player[0]][self.player[1]] = '🐸️'

        if position == '🌀':
            return 'lose'
        if self.player[0] == 0:
            return 'win'
        # иначе продолжаем игру (вернём None)
        return None

    async def stop_game(self):
        """
        Завершает игру, начисляет пользователю соответствующую сумму (включая возврат ставки при отмене).
        Возвращает int: суммарная начисленная сумма (положительное число, сколько добавлено на баланс).
        Если игра уже была завершена — возвращает 0.
        """
        if self.stopped:
            return 0
        self.stopped = True

        x = self.get_x(self.player[0])
        # используем Decimal для точности, затем приводим к int (округление)
        summ_decimal = Decimal(str(self.summ)) * Decimal(str(x))
        summ = int(round(summ_decimal))
        # защищаем от переполнения баланса: если баланс + summ < 0 (маловероятно), корректируем
        try:
            balance = await get_user_balance(self.user_id)
            try:
                balance_int = int(round(float(balance)))
            except Exception:
                balance_int = int(balance) if isinstance(balance, int) else 0
        except Exception:
            balance_int = 0

        if balance_int + summ < 0:
            # если по какой-то причине начисление сделает баланс отрицательным — согласуем
            summ = -balance_int

        # начисляем пользователю summ (может быть равен ставке при отмене)
        await update_user_balance(self.user_id, summ)

        return int(summ)

    def get_text(self, stype):
        txt = ''
        if stype == 'win':
            txt += '🤯 <b>{}, вы успешно забрали приз</b>'
        elif stype == 'stop':
            txt += '😕 <b>{}, вы отменили игру</b>'
        elif stype == 'lose':
            txt += '😭 <b>{}, Вы проиграли повезёт в след.раз</b>'
        elif stype == 'abuse':
            txt += '⚠️ <b>{}, игра завершена из-за подозрения на багюз</b>'
        else:
            txt += '🐸 <b>{}, вы начали игру КВАК</b>'

        pole = self.get_pole(stype)
        next_win = self.get_x(self.player[0] - 1)
        nsumm = int(self.summ * next_win)

        txt += f'\n💰 Ставка: <b>{self.summ}</b> Spark🦎'

        if stype == 'game':
            txt += f'\n🍀 Следующий кувшин: х{next_win}  <b>{nsumm}</b> Spark🦎'

        txt += '\n\n' + pole
        return txt

    def get_kb(self):
        keyboard = InlineKeyboardMarkup(row_width=5)
        buttons = []
        for i in range(5):
            buttons.append(InlineKeyboardButton('🍀', callback_data=f"kwak_{i}|{self.user_id}"))
        keyboard.add(*buttons)
        txt = '💰 Забрать' if self.player[0] != 4 else '❌ Отменить'
        keyboard.add(InlineKeyboardButton(txt, callback_data=f"kwak-stop|{self.user_id}"))
        return keyboard


async def end_game_abuse(user_id, call, reason_msg="Обнаружена попытка багаюза. Игра отменена."):
    game = games.get(user_id)
    if not game:
        await call.answer(reason_msg, show_alert=True)
        return

    name = await get_name(user_id)
    # возвращаем ставку
    await update_user_balance(user_id, game.summ)
    games.pop(user_id, None)
    user_action_lock.pop(user_id, None)

    try:
        await call.message.edit_text(game.get_text('abuse').format(name), parse_mode='HTML')
    except Exception:
        pass

    await call.answer(reason_msg, show_alert=True)


@dp.message_handler(Text(startswith='квак', ignore_case=True))
async def start_kwak(message: types.Message):
    user_id = message.from_user.id

    if not await is_command_allowed(user_id):
        return

    name = await get_name(user_id)
    balance = await get_user_balance(user_id)
    try:
        balance_int = int(round(float(balance)))
    except Exception:
        try:
            balance_int = int(balance)
        except Exception:
            balance_int = 0

    if user_id in games:
        await message.reply(f'❌<b>{name}, у вас уже есть активная игра</b>', parse_mode='HTML')
        return

    try:
        parts = message.text.lower().split()
        if len(parts) < 2:
            await message.reply(f'❌<b>{name}, используйте: Квак (сумма) или Квак (все/всё)</b>', parse_mode='HTML')
            return

        stake_str = parts[1]
        stake = format_stake(stake_str)
        if stake is None:
            await message.reply("❌<b>Неверный формат ставки. Используйте число или сокращение (1к, 1м).</b>", parse_mode='HTML')
            return

        if stake_str in ['все', 'всё']:
            summ = balance_int
        else:
            summ = int(stake)

    except:
        await message.reply(f'❌<b>{name}, вы не ввели ставку для игры</b>', parse_mode='HTML')
        return

    if summ < 100:
        await message.reply(f'❌<b>{name}, минимальная ставка 100 Spark🦎</b>', parse_mode='HTML')
        return

    if summ > balance_int:
        await message.reply(f'❌<b>{name}, у вас недостаточно денег</b>', parse_mode='HTML')
        return

    game = Game(message.chat.id, user_id, summ)
    games[user_id] = game

    # Логируем начало игры в статистике (gamep)
    try:
        await increment_games_played(user_id, 1)
    except Exception:
        logging.exception("increment_games_played упала в start_kwak")

    await update_user_balance(user_id, -summ)
    msg = await message.reply(game.get_text('game').format(name), reply_markup=game.get_kb(), parse_mode='HTML')
    game.message_id = msg.message_id
    await update_last_command_time(user_id)


@dp.callback_query_handler(Text(startswith='kwak_'))
async def game_kb(call: types.CallbackQuery):
    user_id = call.from_user.id

    if user_id not in games:
        await end_game_abuse(user_id, call, "❌ Игра уже завершена. Нельзя делать ход.")
        return

    if user_id not in user_action_lock:
        user_action_lock[user_id] = {'locked': False, 'pending_buttons': []}

    lock = user_action_lock[user_id]

    if lock['locked']:
        lock['pending_buttons'].append(call)
        await call.answer()
        return

    lock['locked'] = True

    game = games.get(user_id)
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    name = await get_name(user_id)

    if not game or game.chat_id != chat_id or game.message_id != message_id:
        await end_game_abuse(user_id, call, "🐸 Игра не найдена или устарела.")
        lock['locked'] = False
        return

    try:
        x = int(call.data.split('_')[1].split('|')[0])
    except Exception:
        await end_game_abuse(user_id, call, "🐸 Некорректные данные. Игра отменена.")
        lock['locked'] = False
        return

    result = game.make_move(x)

    if result == 'lose':
        # Записываем проигрыш в статистику (losp): сумма проигрыша = ставка игрока
        try:
            await add_loss_record(user_id, int(game.summ))
        except Exception:
            logging.exception("add_loss_record упала в game_kb (lose)")

        try:
            await call.message.edit_text(game.get_text('lose').format(name), parse_mode='HTML')
        except Exception:
            logging.exception("Не удалось отредактировать сообщение при проигрыше")
        games.pop(user_id, None)
        user_action_lock.pop(user_id, None)

    elif result == 'win':
        # начисление и запись выигранной суммы
        try:
            payout = await game.stop_game()  # вернёт суммы, которые начислены
        except Exception:
            logging.exception("Ошибка в game.stop_game при win")
            payout = 0

        try:
            await call.message.edit_text(game.get_text('win').format(name), parse_mode='HTML')
        except Exception:
            logging.exception("Не удалось отредактировать сообщение при выигрыше")

        # логируем выигрыш (winp) — передаём сумму, начисленную пользователю
        if payout and payout > 0:
            try:
                await add_win_record(user_id, int(payout))
            except Exception:
                logging.exception("add_win_record упала в game_kb (win)")

        games.pop(user_id, None)
        user_action_lock.pop(user_id, None)

    else:
        try:
            await call.message.edit_text(game.get_text('game').format(name), reply_markup=game.get_kb(), parse_mode='HTML')
        except Exception:
            logging.exception("Не удалось обновить сообщение игры (продолжается)")

    game.last_time = time.time()
    await bot.answer_callback_query(call.id)

    # обработка очереди нажатий
    if user_id in user_action_lock:
        lock = user_action_lock[user_id]
        if lock['pending_buttons']:
            next_call = random.choice(lock['pending_buttons'])
            lock['pending_buttons'].clear()
            lock['locked'] = False
            await game_kb(next_call)
        else:
            lock['locked'] = False


@dp.callback_query_handler(Text(startswith='kwak-stop'))
async def game_stop(call: types.CallbackQuery):
    user_id = call.from_user.id

    if user_id not in games:
        await end_game_abuse(user_id, call, "❌ Нельзя забрать после завершения игры!")
        return

    if user_id not in user_action_lock:
        user_action_lock[user_id] = {'locked': False, 'pending_buttons': []}

    lock = user_action_lock[user_id]

    if lock['locked']:
        lock['pending_buttons'].append(call)
        await call.answer()
        return

    lock['locked'] = True

    game = games.get(user_id)
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    name = await get_name(user_id)

    if not game or game.chat_id != chat_id or game.message_id != message_id:
        await end_game_abuse(user_id, call, "🐸 Игра не найдена или устарела.")
        lock['locked'] = False
        return

    # завершаем игру и получаем сумму, которая была начислена (refund или payout)
    try:
        payout = await game.stop_game()
    except Exception:
        logging.exception("Ошибка в game.stop_game при stop")
        payout = 0

    # определяем тип завершения для текста
    if game.player[0] == 4:
        txt = 'stop'  # отмена — вернули ставку
    else:
        txt = 'win'  # игрок забрал приз

    try:
        await call.message.edit_text(game.get_text(txt).format(name), parse_mode='HTML')
    except Exception:
        logging.exception("Не удалось отредактировать сообщение при stop/win")

    # если это был выигрыш — логируем выигранную сумму (winp)
    if txt == 'win' and payout and payout > 0:
        try:
            await add_win_record(user_id, int(payout))
        except Exception:
            logging.exception("add_win_record упала в game_stop")

    games.pop(user_id, None)
    user_action_lock.pop(user_id, None)

    await bot.answer_callback_query(call.id)

    if user_id in user_action_lock:
        lock = user_action_lock[user_id]
        if lock['pending_buttons']:
            next_call = random.choice(lock['pending_buttons'])
            lock['pending_buttons'].clear()
            lock['locked'] = False
            if next_call.data.startswith('kwak-stop'):
                await game_stop(next_call)
            else:
                await game_kb(next_call)
        else:
            lock['locked'] = False


async def check_game():
    while True:
        for user_id, game in list(games.items()):
            if int(time.time()) > int(game.last_time + 60) and not game.stopped:
                games.pop(user_id, None)
                user_action_lock.pop(user_id, None)
                try:
                    payout = await game.stop_game()  # возвращаем ставку
                    txt = f'⚠️ От вас давно не было активности!\nИгра отменена! На ваш баланс возвращено {game.summ} Spark🦎'
                    await bot.send_message(game.chat_id, txt, reply_to_message_id=game.message_id, parse_mode='HTML')
                except Exception as e:
                    logging.error(f"Ошибка при отмене игры: {e}")
        await asyncio.sleep(15)



# Константа для стартового баланса
START_BALANCE = 100000

# Переменная для хранения username бота
BOT_USERNAME = None


async def get_bot_username():
    """Получает username бота из Telegram API."""
    global BOT_USERNAME
    if BOT_USERNAME is None:
        bot_info = await bot.get_me()
        BOT_USERNAME = bot_info.username
    return BOT_USERNAME


# -------------------- Хэндлеры --------------------

# --- Обработчик команды "/start" ---
@dp.message_handler(CommandStart())
async def start_command(message: types.Message):
    """Обработчик команды /start, обрабатывает как активацию чека, так и обычный запуск."""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Проверка на бан
    if await is_user_banned(user_id):
        await message.reply("❌ Вы забанены и не можете использовать эту команду.")
        return

    args = message.get_args()

    if args and args.startswith("check_"):
        # Обработка активации чека
        try:
            check_code = args[len("check_"):]
            check_code = check_code.replace("%20", " ")  # Декодируем URL

            if message.chat.type != types.ChatType.PRIVATE:
                await message.reply("🅾||Вы не можете активировать чек, так как не являетесь человеком!")
                return

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT creator_id FROM checks WHERE code = ?", (check_code,))
            check_data = cursor.fetchone()
            close_db_connection(conn)

            if check_data and check_data[0] == user_id:
                await message.reply("🛑|| Вы не можете активировать чек, так как являетесь его создателем!")
                return

            success, result = await activate_check(user_id, check_code)

            if success:
                amount = result["amount"]
                creator_id = result["creator_id"]

                await update_user_balance(user_id, amount)

                creator = await bot.get_chat(creator_id)
                creator_name = creator.username or creator.first_name
                creator_link = hlink(creator_name, f"tg://user?id={creator_id}")

                text = f"<b>🎫|| Вы успешно активировали чек от {creator_link}!</b>\n" \
                       f"💰||Сумма получения: <b>+{format_balance(amount)}</b> Spark🦎\n" \
                       f"<b>📓||Чек-код:</b> <code>{check_code}</code>"

                photo_path = "C:/Users/nikita/Pictures/ящ.jpg"  # Замени на свой путь

                with open(photo_path, "rb") as photo:
                    await bot.send_photo(chat_id=message.chat.id, photo=photo)  # Отправляем фото как отдельное сообщение

                await message.reply(text, parse_mode=ParseMode.HTML)  # Отправляем текст

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT remaining_activations FROM checks WHERE code = ?", (check_code,))
                remaining_activations = cursor.fetchone()[0]
                close_db_connection(conn)

                await send_check_activation_notification(bot, creator_id, user_id, remaining_activations)
            else:
                if result == "already_activated":
                    await message.reply("❌||Вы уже активировали этот чек!")
                elif result == "not_found":
                    await message.reply("❌|| Чек не найден или не существует.")
                elif result == "no_activations":
                    await message.reply("❌|| У этого чека больше нет активаций.")
                else:
                    await message.reply("❌|| Произошла ошибка при активации чека. Попробуйте позже.")
        except Exception as e:
            logging.error(f"Ошибка при обработке активации чека: {e}")
            await message.reply("❌|| Произошла ошибка при обработке чека. Попробуйте позже.")

    else:
        # Обработка обычного запуска
        # Проверка cooldown
        if not await is_command_allowed(user_id):
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        # Проверяем, есть ли пользователь в базе
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if not result:
            # Пользователь отсутствует — создаём с датой регистрации (записываем дату ТОЛЬКО ПРИ СОЗДАНИИ)
            registration_date = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO users (user_id, username, balance, last_command, registration_date) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, START_BALANCE, datetime.now().isoformat(), registration_date)
            )
            conn.commit()

            # Оповещение о начислении баланса
            await message.reply(
                f"🎉 Приветствуем нового игрока! 🎉\n\nВам начислено +{START_BALANCE:,} Spark🦎 на стартовый баланс!\nУдачи в играх!",
                parse_mode=ParseMode.HTML
            )

            # Оповещение в чат
            try:
                await bot.send_message(message.chat.id, f"✨ Новый игрок {message.from_user.first_name} получил стартовый бонус! ✨", parse_mode=ParseMode.HTML)
            except Exception as e:
                logging.warning(f"Не удалось отправить сообщение в чат: {e}")
        else:
            # Пользователь уже есть — дату регистрации не трогаем!
            escaped_name = escape_html_tags(message.from_user.first_name)
            await message.reply(f"С возвращением, {escaped_name}! 😉", parse_mode=ParseMode.HTML)

        close_db_connection(conn)

        # Создаем кнопки
        keyboard = InlineKeyboardMarkup()
        bot_username = await get_bot_username()  # Получаем username бота
        add_to_chat_button = InlineKeyboardButton("Добавить бота в чат 🚀", url=f"https://t.me/{bot_username}?startgroup=true")
        keyboard.add(add_to_chat_button)

        await message.reply(
            f"<i>💚Приветствуем в Spark!</i>\n<b>Сдесь ты можешь хорошо провести время с друзьями!🦎</b>\n\n<b>-Не знаешь с чего начать❓</b>\nВоспользуйся командой <b>помощь</b> чтобы узнать все доступные команды и функции бота!🎍\n<b>-Зашёл бот❓</b>\nТогда можешь добавить его в свой чат если хочешь!🎮",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

        await update_last_command_time(user_id)  # Обновляем время последней команды


@dp.message_handler(Text(startswith="помощь", ignore_case=True))
async def help_command(message: types.Message):
    """Обработчик команды  (без /)"""
    user_id = message.from_user.id

    keyboard = InlineKeyboardMarkup(row_width=2)
    games_button = InlineKeyboardButton("🎮 Игры", callback_data=f"help_games:{user_id}")
    main_button = InlineKeyboardButton("⚙️ Основное", callback_data=f"help_main:{user_id}")
    unique_button = InlineKeyboardButton("🔥 Уникальное", callback_data=f"help_unique:{user_id}")
    jobs_button = InlineKeyboardButton("📓 Статусы", callback_data=f"help_jobs:{user_id}")  # Новая кнопка
    keyboard.add(games_button, main_button, unique_button, jobs_button)

    agreement_button = InlineKeyboardButton("📝 Соглашения", callback_data=f"help_agreement:{user_id}")
    keyboard.add(agreement_button)  # Отдельная кнопка снизу

    await message.reply("🔎Выберите нужный пункт🔍", reply_markup=keyboard)


@dp.callback_query_handler(Text(startswith="help_main:"))
async def help_main_callback(callback_query: types.CallbackQuery):
    """Обработчик кнопки "Основное" в помощи"""
    user_id = int(callback_query.data.split(":")[1])
    if callback_query.from_user.id != user_id:
        await callback_query.answer("Это не ваша кнопка!", show_alert=True)
        return

    await bot.answer_callback_query(callback_query.id)
    help_text = """
⚙️ <b>Основные команды:</b>

<blockquote>- 💰<b>б</b>: Узнать свой баланс.
- 🏆<b>топ</b>: Посмотреть топ игроков.
- 🧰<b>бизнес</b>: Посмотреть характеристики своего бизнеса.
- 🏛<b>банк</b>: Посмотреть счет банка.
- 💡<b>банк положить (сумма)</b>: Пополнить счет банка
- 💡<b>банк снять (сумма)</b>: снять со счет банка
- 🎁<b>бонус</b>: Получить ежедневный бонус.
- 📦<b>бокс</b>: Открыть денежный бокс.
- 🫆<b>+ник (сам ник)</b>: Создать никнейм для топа.
- 💸<b>дать</b>: Передать деньги игроку.
- Ⓜ️<b>промо (название)</b>: Активировать промокод.
- 👤<b>профиль </b>: Посмотреть свой профиль.
- 🎲<b>выбери от (число) до (число)</b>: Рандомайзер.</blockquote>
    """
    keyboard = InlineKeyboardMarkup()
    back_button = InlineKeyboardButton("⬅ Назад", callback_data=f"help_back:{user_id}")
    keyboard.add(back_button)
    try:
        await bot.edit_message_text(help_text,
                                    chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    parse_mode=types.ParseMode.HTML,
                                    reply_markup=keyboard)
    except MessageNotModified:
        pass  # Сообщение не изменилось, ничего не делаем
    except Exception as e:
        logging.error(f"Error editing message: {e}")

@dp.callback_query_handler(Text(startswith="help_games:"))
async def help_games_callback(callback_query: types.CallbackQuery):
    """Обработчик кнопки "Игры" в помощи"""
    user_id = int(callback_query.data.split(":")[1])
    if callback_query.from_user.id != user_id:
        await callback_query.answer("Это не ваша кнопка!", show_alert=True)
        return
    await bot.answer_callback_query(callback_query.id)
    help_text = """
🎮 <b>Игровые команды:</b>

<blockquote>- 🏹<b>охота (ставка)</b>: Игра в охоту.
- 🃏<b>бж (ставка)</b>: Игра в Блэк Джек.
- 🪜<b>башня (ставка) (кол-во мин от 1 до 4)</b>: Игра в башню.
- 🎲<b>кости (ставка) (б/м/с)</b>: Игра в кости.
- ✅❌<b>вилин</b>: Игра во все или нечего.
- ⚫️🔴🟢<b>рул (ставка) (тип ставки)</b>: Игра в рулетку.
- 💈<b>слот (ставка) </b>: Игра в слот-машину.
- 💣<b>мины (ставка)</b>: Игра в Мины.
- 🟡<b>голд (ставка)</b>: Игра в лавину монет.
- 🐸<b>квак (ставка)</b>: Игра в Квак.
- 🚀<b>краш (ставка)</b>: Игра в Краш.
- 🪙<b>флип (ставка) (о/р)</b>: Игра в монетку.
- 🎲<b>кубик (ставка)</b>: Игра в кубик.
- 🎳<b>боул (ставка)</b>: Игра в боулинг.
- 🧨📊<b>кб (ставка)</b>: Игра в Крипто-бум.
- 🏀<b>баскет (ставка)</b>: Игра в баскетбол.
- 🔑<b>тк (ставка)</b>: Игра в возьми ключ.
- 🔴🔵<b>фишки (ставка) (красный/синий)</b>: Игра в фишки.
- 🎰<b>спин (ставка) </b>: Игра в спин.
- 🎁<b>честы (ставка) </b>: Игра в сундуки удачи.
- 👑🪓<b>мюрдер (ставка) </b>: Игра в приследование короля.
- 🃏<b>хило (ставка) </b>: Игра в Hilo.
- 💎<b>алмазы (ставка) </b>: Игра в алмазы.
- 💻<b>хакер (ставка) </b>: Игра во взлом системы.
- ⚽️<b>футбол (ставка) </b>: Игра в футбол.
- 🎯<b>дартс (ставка)</b>: Игра в дартс.
</blockquote>
    """
    keyboard = InlineKeyboardMarkup()
    back_button = InlineKeyboardButton("⬅ Назад", callback_data=f"help_back:{user_id}")
    keyboard.add(back_button)

    try:
        await bot.edit_message_text(help_text,
                                    chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    parse_mode=types.ParseMode.HTML,
                                    reply_markup=keyboard)
    except MessageNotModified:
        pass
    except Exception as e:
        logging.error(f"Error editing message: {e}")


@dp.callback_query_handler(Text(startswith="help_unique:"))
async def help_unique_callback(callback_query: types.CallbackQuery):
    """Обработчик кнопки "Уникальное" в помощи"""
    user_id = int(callback_query.data.split(":")[1])
    if callback_query.from_user.id != user_id:
        await callback_query.answer("Это не ваша кнопка!", show_alert=True)
        return

    await bot.answer_callback_query(callback_query.id)
    help_text = """
🔥 Уникальные команды:

<blockquote>- 🧾<b>Создать_чек</b>: создать свой уникальный чек.
- 💳<b>.чекбал</b>: даёт возможность просматривать чужие балансы ответом на сообщение.
- 🔒<b>.локбал</b>: скрывает баланс от чужих глаз.
- 🔓<b>.анлокбал</b>: открывает баланс в общий доступ.</blockquote>\n\n
- <b>Version</b>: 2.0.0
    """
    keyboard = InlineKeyboardMarkup()
    back_button = InlineKeyboardButton("⬅️ Назад", callback_data=f"help_back:{user_id}")
    keyboard.add(back_button)

    try:
        await bot.edit_message_text(help_text,
                                    chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    parse_mode=types.ParseMode.HTML,
                                    reply_markup=keyboard)
    except MessageNotModified:
        pass
    except Exception as e:
        logging.error(f"Error editing message: {e}")



@dp.callback_query_handler(Text(startswith="help_jobs:"))
async def help_jobs_callback(callback_query: types.CallbackQuery):
    """Обработчик кнопки "Работы" в помощи"""
    user_id = int(callback_query.data.split(":")[1])
    if callback_query.from_user.id != user_id:
        await callback_query.answer("Это не ваша кнопка!", show_alert=True)
        return

    await bot.answer_callback_query(callback_query.id)
    help_text = """
    📓 <b>Статусы:</b>
<blockquote>- 1 — 💸Додепер💸 — стоимость 10 000 — приносит 1.10× к бонусу и 1.11× к боксу\n\n
 - 2 — 📯Ambassador📯 — 100 000 — приносит 1.15× к бонусу и 1.18× к боксу\n\n
 - 3 — 🏆 Legend🏆 — 1 000 000 — приносит 1.20× к бонусу и 1.23× к боксу\n\n
 - 4 — 🚀Buster🚀 — 7 000 000 — приносит 1.40× к бонусу и 1.50× к боксу\n\n
 - 5 — 🛸NLO🛸 — 17 000 000 — приносит 1.50× к бонусу и 1.60× к боксу\n\n
 - 6 — 🦈Shark🦈 — 35 000 000 — приносит 2.00× к бонусу и 2.20× к боксу\n\n
 - 7 — 🕷Sirius🕷 — 90 000 000 — приносит 2.70× к бонусу и 3.70× к боксу\n\n
 - 8 — ⚜️🦋Gold fly🦋⚜️ — 190 000 000 — приносит 5.00× к бонусу и 7.00× к боксу\n\n
 - 9 — ♦️♠️Игроман♠️♦️ — 800 000 000 — приносит 11.00× к бонусу и 14.00× к боксу\n\n
 - 10 — 🦎Spark GD🦎 (донат) — стоимость 0 — приносит 35.00× к бонусу и 36.00× к боксу\n\n
 - 11 — ⚱️🦎Gold Spark GD🦎⚱️ (донат) — стоимость 0 — приносит 67.00× к бонусу и 89.00× к боксу\n\n
 - Чтобы купить статус используйте: купить ( нумирация статуса от 1 до 11)</blockquote>

    """

    keyboard = InlineKeyboardMarkup()
    back_button = InlineKeyboardButton("⬅ Назад", callback_data=f"help_back:{user_id}")
    keyboard.add(back_button)

    try:
        await bot.edit_message_text(help_text,
                                    chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    parse_mode=types.ParseMode.HTML,
                                    reply_markup=keyboard)
    except MessageNotModified:
        pass
    except Exception as e:
        logging.error(f"Error editing message: {e}")


@dp.callback_query_handler(Text(startswith="help_agreement:"))
async def help_agreement_callback(callback_query: types.CallbackQuery):
    """Обработчик кнопки "Соглашения" в помощи"""
    user_id = int(callback_query.data.split(":")[1])
    if callback_query.from_user.id != user_id:
        await callback_query.answer("Это не ваша кнопка!", show_alert=True)
        return

    await bot.answer_callback_query(callback_query.id)
    help_text = """
📝 <b>Здравствуйте!</b>

Это сотрудничество SparkHelp!
Просим вас прочитать эти условия пользования:
<blockquote>1. Мы не несем ответственность за добавление и создание админом нашего бота! Все зависит от вас
2. Прочитать правила основного чата, да бы избежать наказания
3. Просим не обманывать людей на валюту! Это будет караться наказанием!
4. Все найденые баги просим сообщять владельцу бота, чтобы получить за него вознаграждение!
5. Обход правил будет караться баном в боте!
6. Остерегайтесь копий настоящего бота, внимательно осмотрите нашего бота по описанию и юзернейму!
7. Мы не несём ответственность за вашу психику и нервы! Мы не принуждаем заниматься лудоманством, это все на ваш интерес!</blockquote>

Удачи! Уважаемые игроки Spark'a!
    """

    keyboard = InlineKeyboardMarkup()
    back_button = InlineKeyboardButton("⬅ Назад", callback_data=f"help_back:{user_id}")
    keyboard.add(back_button)

    try:
        await bot.edit_message_text(help_text,
                                    chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    parse_mode=types.ParseMode.HTML,
                                    reply_markup=keyboard)
    except MessageNotModified:
        pass
    except Exception as e:
        logging.error(f"Error editing message: {e}")


@dp.callback_query_handler(Text(startswith="help_back:"))
async def help_back_callback(callback_query: types.CallbackQuery):
    """Обработчик кнопки "Назад" в помощи"""
    user_id = int(callback_query.data.split(":")[1])
    if callback_query.from_user.id != user_id:
        await callback_query.answer("Это не ваша кнопка!", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(row_width=2)
    games_button = InlineKeyboardButton("🎮 Игры", callback_data=f"help_games:{user_id}")
    main_button = InlineKeyboardButton("⚙️ Основное", callback_data=f"help_main:{user_id}")
    unique_button = InlineKeyboardButton("🔥 Уникальное", callback_data=f"help_unique:{user_id}")
    jobs_button = InlineKeyboardButton("📓 Статусы", callback_data=f"help_jobs:{user_id}")  # Добавляем кнопку
    keyboard.add(games_button, main_button, unique_button, jobs_button)

    agreement_button = InlineKeyboardButton("📝 Соглашения", callback_data=f"help_agreement:{user_id}")
    keyboard.add(agreement_button)

    try:
        await bot.edit_message_text("🔎Выберите нужный пункт🔍",
                                    chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    reply_markup=keyboard)
        await bot.answer_callback_query(callback_query.id)
    except MessageNotModified:
        pass
    except Exception as e:
        logging.error(f"Error editing message: {e}")


async def is_verified(user_id: int) -> bool:
    """Проверяет, является ли пользователь верифицированным."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT is_verified FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            return bool(result[0])  # Преобразуем к булеву типу
        else:
            return False  # Пользователь не найден, значит, не верифицирован
    finally:
        close_db_connection(conn)


async def set_verification_status(user_id: int, verified: bool):
    """Устанавливает статус верификации для пользователя."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET is_verified = ? WHERE user_id = ?", (int(verified), user_id))  # Сохраняем как целое число (0 или 1)
        conn.commit()
    finally:
        close_db_connection(conn)


@dp.message_handler(commands=["vrf"])
async def verify_command(message: types.Message):
    """Обработчик команды /vrf для выдачи верификации пользователю."""

    sender_id = message.from_user.id  # ID того, кто отправил команду

    if sender_id not in OWNER_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    try:
        user_id_to_verify = int(message.text.split()[1])  # ID пользователя, которого верифицируем
    except (IndexError, ValueError):
        await message.reply("Используйте команду в формате: /vrf [айди пользователя]")
        return

    await set_verification_status(user_id_to_verify, True)
    await message.reply(f"Пользователь с ID {user_id_to_verify} успешно верифицирован.")


# Обновлённый handler для "б" (баланс)
@dp.message_handler(Text(equals="б", ignore_case=True))
async def balance_command(message: types.Message):
    user_id = message.from_user.id
    if not await is_command_allowed(user_id):
        return

    conn_local = get_db_connection()
    cur = conn_local.cursor()
    cur.execute("SELECT balance, winp, losp, gamep, darkp FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    close_db_connection(conn_local)

    if not row:
        await message.reply("Пользователь не найден. Пожалуйста, используйте команду /start.")
        await update_last_command_time(user_id)
        return

    balance, winp, losp, gamep, darkp = (row[0] or 0, row[1] or 0, row[2] or 0, row[3] or 0, row[4] or 0)

    # Имя + ссылка на профиль, жирным
    name = message.from_user.first_name or message.from_user.username or "User"
    name_html = f'<a href="tg://user?id={user_id}"><b>{escape_html(name)}</b></a>'

    text = (
        f"💰 {name_html}, ваш баланс: {format_balance(balance)} Spark🦎\n"
        f"·····················\n"
        f"🚀 Сыграно игр: {int(gamep)}\n"
        f"·····················\n"
        f"🛡 Проиграно Spark🦎: {format_balance(losp)}\n"
        f"🪅 Выйграно Spark🦎: {format_balance(winp)}\n"
    )

    await message.reply(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    await update_last_command_time(user_id)


# Новый handler для "профиль" (без слеша) — добавлены все поля из баланса
@dp.message_handler(Text(equals="профиль", ignore_case=True))
async def profile_command(message: types.Message):
    user_id = message.from_user.id
    if not await is_command_allowed(user_id):
        return

    conn_local = get_db_connection()
    cur = conn_local.cursor()
    # Берём баланс + остальные поля
    cur.execute("SELECT balance, status_id, winp, losp, gamep, darkp FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    close_db_connection(conn_local)

    if not row:
        await message.reply("Пользователь не найден. Пожалуйста, используйте команду /start.")
        await update_last_command_time(user_id)
        return

    balance, status_id, winp, losp, gamep, darkp = (
        row[0] or 0,
        row[1] or 0,
        row[2] or 0,
        row[3] or 0,
        row[4] or 0,
        row[5] or 0,
    )

    # Получаем текст статуса (если у вас есть get_status_info/STATUSES)
    try:
        status_info = get_status_info(status_id or 0)
        status_text = escape_html(status_info["name"])
    except Exception:
        status_text = "отсутствует"

    name = message.from_user.first_name or message.from_user.username or "User"
    name_html = f'<a href="tg://user?id={user_id}"><b>{escape_html(name)}</b></a>'

    text = (
        f"<i>▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄</i>\n"
        f"👤 {name_html}, ваша общая статистика:\n\n"
        f"🫧Ваш статус:\n<b>{status_text}</b>\n\n"
        f"🆔Ваш айди: <code>{user_id}</code>\n\n"
        f"<code>💰Баланс Spark🦎: {format_balance(balance)}</code>\n"
        f"<code>🚀Сыграно игр: {int(gamep)}</code>\n"
        f"<code>🪅Выйграно Spark🦎: {format_balance(winp)}</code>\n"
        f"<code>🛡Проиграно Spark🦎: {format_balance(losp)}</code>\n\n"
        f"⚫️Dark-coins⚫️: <b>{int(darkp)}</b>\n"
        f"<i>▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄</i>"
    )

    await message.reply(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    await update_last_command_time(user_id)


#-----------ПЕРЕДАЧКА--------------------------
@dp.message_handler(Text(startswith=("дать"), ignore_case=True))
async def transfer_command(message: types.Message):
    """Обработчик команды передачи денег с комиссией 15%"""
    sender_id = message.from_user.id
    sender_username = message.from_user.username or message.from_user.first_name

    # Проверка, является ли отправитель человеком
    if message.from_user.is_bot:
        await message.reply("❌|| Вы не являетесь человеком чтобы передать деньги!")
        return

    # Проверка cooldown
    if not await is_command_allowed(sender_id):
        return

    # Проверка, ответ на сообщение
    if not message.reply_to_message:
        await message.reply("❌Эта команда должна быть ответом на сообщение пользователя, которому вы хотите передать деньги.")
        return

    receiver_msg = message.reply_to_message
    receiver_user = receiver_msg.from_user

    # Проверка, что получатель существует и не бот
    if not receiver_user:
        await message.reply("❌Невозможно определить пользователя, которому вы хотите передать деньги.")
        return
    if receiver_user.is_bot:
        await message.reply("❌|| Нельзя передавать деньги боту!")
        return

    # Проверка на sender_chat (если сообщение от канала/группы)
    if getattr(receiver_msg, 'sender_chat', None):
        chat_type = getattr(receiver_msg.sender_chat, 'type', None)
        if chat_type in ("group", "supergroup", "channel"):
            await message.reply("❌|| Нельзя передавать деньги группе или каналу!")
            return

    receiver_id = receiver_user.id
    receiver_username = receiver_user.username or receiver_user.first_name

    # Проверка регистрации получателя
    if not await is_user_registered(receiver_id):
        await message.reply("❌|| Вы не можете передать деньги незарегистрированному человеку!")
        return

    if receiver_id == sender_id:
        await message.reply("❌Вы не можете передать деньги самому себе.")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("❌Используйте: дать (сумма)")
            return

        stake_str = parts[1].lower()  # Сумма передачи

        if stake_str == 'все':
            stake = await get_user_balance(sender_id)
            if stake == 0:
                await message.reply("❌На вашем балансе нет средств для передачи")
                return
        else:
            stake = format_stake(stake_str)  # Форматируем строку ставки
            if stake is None:
                await message.reply("❌Неверный формат суммы. Используйте число или сокращение (1к, 1кк, 1м).")
                return
            if stake <= 0:
                await message.reply("❌Сумма передачи должна быть больше 0.")
                return

            sender_balance = await get_user_balance(sender_id)
            if sender_balance < stake:
                await message.reply("❌Недостаточно средств на балансе для перевода.")
                return

        # Вычисляем комиссию 15%
        commission = stake * 0.15
        amount_to_receiver = stake - commission

        # Обновляем балансы
        await update_user_balance(sender_id, -stake)
        await update_user_balance(receiver_id, amount_to_receiver)

        formatted_stake = format_balance(amount_to_receiver)
        formatted_commission = format_balance(commission)

        # Сообщение об успешной передаче
        await message.reply(
            f"✅💸|<i>{sender_username}</i> <b>успешно передал</b> пользователю <i>{receiver_username}</i>:\n"
            f"<b>{formatted_stake}</b> Spark🦎 (с комиссией 15% = {formatted_commission})",
            parse_mode=types.ParseMode.HTML
        )

        await update_last_command_time(sender_id)

    except Exception as e:
        logging.error(f"Ошибка при передаче денег: {e}")
        await message.reply("Произошла ошибка при передаче денег. Попробуйте позже.")


DATABASE_NAME = "blaze_bot.db"  # Замените на имя вашей базы данных

async def is_user_registered(user_id: int) -> bool:
    """Проверяет, зарегистрирован ли пользователь в базе данных."""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None  # Возвращает True, если пользователь найден
    except Exception as e:
        logging.error(f"Ошибка при проверке регистрации пользователя: {e}")
        return False  # В случае ошибки считаем, что пользователь не зарегистрирован

#-----------ПЕРЕДАЧКА-----------------------

numbers_emoji = ['0️⃣', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']


@dp.message_handler(Text(equals="топ", ignore_case=True))
async def balance_command(message: types.Message):
    """Обработчик команды топ (без /) с визуалом из другого кода."""
    user_id = message.from_user.id

    # Проверка cooldown
    if not await is_command_allowed(user_id):
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT user_id, username, balance FROM users ORDER BY balance DESC LIMIT 10")
    results = cursor.fetchall()

    if results:
        top_text = "👤Всего пользователей: {}\n".format(total_users)
        top_text += "💸Топ 10 богатых пользователей:\n\n"

        for index, (user_id, username, balance) in enumerate(results):
            emoji = ''.join(numbers_emoji[int(i)] for i in str(index + 1)) #Эмоджи нумерация
            formatted_balance = format_balance(balance)
            top_text += f"{emoji}. <i><b>{username}</b></i> — <i>{formatted_balance} Spark🦎</i>\n" # Никакой ссылки

        await message.reply(top_text, parse_mode=types.ParseMode.HTML, disable_web_page_preview=True) # disable_web_page_preview=True Чтобы не было превью
    else:
        await message.reply("Топ пуст. 😔")

    await update_last_command_time(user_id)  # Обновляем время последней команды


@dp.message_handler(lambda message: len(message.text.split()) > 0 and message.text.split()[0].startswith('+ник'))
async def set_nickname(message: types.Message):
    """Обработчик команды установки/изменения ника"""
    user_id = message.from_user.id
    parts = message.text.split()

    if len(parts) > 1:
        nickname = parts[1]
        if len(nickname) <= 10:
            # Обновляем ник в базе данных
            cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (nickname, user_id))
            conn.commit()  # Не забудьте закоммитить изменения

            await message.reply(f"Ник успешно изменен на: {nickname}")
        else:
            await message.reply("❌Ник не должен превышать 10 символов.")
    else:
        await message.reply("❌Пожалуйста, укажите ник после команды +ник (например, +ник (самник) ).")

# Словарь призов
PRIZES = {
    "💎": 55000,
    "🧿": 65000,
    "💈": 13000,
    "🎀": 25000,
    "🎉": 44000,
    "🥰": 50000,
    "🥳": 14000,
    "☠": 100,
    "🎃": 23000,
    "👀": 35000,
    "🎩": 11000,
    "👑": 10000,
}
BONUS_EMOJIS = list(PRIZES.keys())
SELECTED_EMOJIS = {}

@dp.message_handler(Text(equals="бонус", ignore_case=True))
async def bonus_command(message: types.Message):
    user_id = message.from_user.id
    if message.chat.type != types.ChatType.PRIVATE:
        await message.reply("❌|| Бонус можно активировать только в личных сообщениях с ботом.")
        return
    if not await is_command_allowed(user_id):
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    close_db_connection(cursor)
    if res and res[0]:
        last_bonus = datetime.fromisoformat(res[0])
        next_bonus_time = last_bonus + timedelta(minutes=20)  # было hours=5 -> теперь minutes=20
        if datetime.now() < next_bonus_time:
            time_left = next_bonus_time - datetime.now()
            total_seconds = int(time_left.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            await message.reply(f"Еще рано! ⏰ Осталось {minutes}м {seconds}с.")
            return

    keyboard = types.InlineKeyboardMarkup(row_width=3)
    buttons = [types.InlineKeyboardButton(text="🎁", callback_data=f"bonus:{i}") for i in range(3)]
    keyboard.add(*buttons)

    await message.reply("✅🎁| Вы активировали свой бонус!\nВыберите из 3-ёх нижеприведенных смайликов только один 👇", reply_markup=keyboard)
    SELECTED_EMOJIS[message.from_user.id] = None

@dp.callback_query_handler(lambda c: c.data.startswith('bonus:'))
async def bonus_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id in SELECTED_EMOJIS and SELECTED_EMOJIS[user_id] is not None:
        await callback_query.answer("❌|| Вы уже выбрали свой бонус!  Нельзя выбирать несколько бонусов.")
        return
    button_index = int(callback_query.data.split(":")[1])
    SELECTED_EMOJIS[user_id] = button_index
    emoji = random.choice(BONUS_EMOJIS)
    base_prize = PRIZES.get(emoji, 0)
    status_id = await get_user_status(user_id)
    status_info = get_status_info(status_id)
    bonus_mult = status_info["bonus_mult"]
    final_prize = int(math.floor(base_prize * bonus_mult))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, 0)", (user_id, ""))
    cursor.execute("UPDATE users SET balance = balance + ?, last_bonus = ?, last_command = ? WHERE user_id = ?",
                   (final_prize, datetime.now().isoformat(), datetime.now().isoformat(), user_id))
    conn.commit()
    close_db_connection(cursor)

    formatted_amount = "{:,}".format(final_prize).replace(",", ".")
    header = ""
    if status_id and status_id in STATUSES:
        header = (f"🌠||Ваш статус был задействован!\n"
                  f"🚀Буст бонуса : {bonus_mult}х\n"
                  f"——————————\n")
    text = (f"{header}"
            f"✅| Вы открыли свой бонус!\nВыпавший смайлик: {emoji}, за него вам дали: +{formatted_amount} Spark🦎")
    await bot.answer_callback_query(callback_query.id)
    try:
        await callback_query.message.edit_text(text, parse_mode=ParseMode.HTML)
    except Exception:
        await callback_query.message.reply(text, parse_mode=ParseMode.HTML)
    await update_last_command_time(user_id)

@dp.message_handler(Text(startswith="охота", ignore_case=True))
async def hunt_command(message: types.Message):
    """Обработчик команды охоты (без /). Работает с целыми суммами и логирует статистику (gamep/winp/losp)."""
    user_id = message.from_user.id

    # Проверка cooldown / прав
    if not await is_command_allowed(user_id):
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("❌Используйте: охота (ставка)")
            return

        stake_str = parts[1].lower()

        # Получаем баланс и приводим к целому
        balance_raw = await get_user_balance(user_id)
        try:
            balance = int(round(float(balance_raw)))
        except Exception:
            try:
                balance = int(balance_raw)
            except Exception:
                balance = 0

        # Парсим ставку
        if stake_str in ('все', 'всё'):
            stake = int(balance)
        else:
            parsed = format_stake(stake_str)
            if parsed is None:
                await message.reply("❌Неверный формат ставки. Используйте число или сокращение (1к, 1м).")
                return
            stake = int(parsed)

        # Валидации
        if stake <= 0:
            await message.reply("❌Ставка должна быть больше нуля.")
            return
        if stake < 100:
            await message.reply("❌Минимальная ставка для охоты 100 Spark🦎")
            return
        if stake > balance:
            await message.reply("❌Недостаточно средств.")
            return

    except (IndexError, ValueError):
        await message.reply("❌Используйте: охота (ставка)")
        return

    # Снимаем ставку (безопасно)
    try:
        ok = await safe_update_user_balance(user_id, -int(stake))
    except Exception:
        logging.exception("Ошибка списания ставки в охоте")
        ok = False

    if not ok:
        # Попытка альтернативного вызова (если safe_update нет)
        try:
            await update_user_balance(user_id, -int(stake))
            ok = True
        except Exception:
            logging.exception("Альтернативное списание ставки провалено")
            ok = False

    if not ok:
        await message.reply("❌Не удалось списать ставку. Попробуйте позже.")
        return

    # Логируем начало игры
    try:
        await increment_games_played(user_id, 1)
    except Exception:
        logging.exception("increment_games_played упала в охоте")

    hunt_message = await message.reply("🔫💥Вы сделали выстрел....")
    await asyncio.sleep(3)

    winning_animals = {
        "Олень": {"multiplier": 1.2, "win_text": "Попали в оленя! Отличный выстрел! 🦌 Вы выиграли +{win_amount} Spark🦎"},
        "Кабан": {"multiplier": 1.4, "win_text": "Кабан повержен! Хороший улов! 🐗 Вы выиграли +{win_amount} Spark🦎"},
        "Лось": {"multiplier": 2, "win_text": "Огромный лось! Победа! 🦌 Вы выиграли +{win_amount} Spark🦎"},
        "Медведь": {"multiplier": 2, "win_text": "Медведь повержен! Большая удача! 🐻 Вы выиграли +{win_amount} Spark🦎"},
        "Волк": {"multiplier": 1.7, "win_text": "Волк убит! Неплохо! 🐺 Вы выиграли +{win_amount} Spark🦎"},
        "Лиса": {"multiplier": 1.6, "win_text": "Лисица поймана! Хороший трофей! 🦊 Вы выиграли +{win_amount} Spark🦎"},
        "Рысь": {"multiplier": 2.3, "win_text": "Рысь поймана! Отличный трофей! 😼 Вы выиграли +{win_amount} Spark🦎"},
        "Бобр": {"multiplier": 2, "win_text": "Бобер пойман! Неплохой улов! 🦫 Вы выиграли +{win_amount} Spark🦎"},
        "Обезьяна": {"multiplier": 2, "win_text": "Обезьяна схвачена за хвост! Ловкие руки! 🐒 Вы выиграли +{win_amount} Spark🦎"},
        "Росомаха": {"multiplier": 2, "win_text": "Росомаха повержена! Редкая добыча! 🦡 Вы выиграли +{win_amount} Spark🦎"},
    }

    losing_animals = {
        "Ворона": "Промах! Ворона улетела. 🐦",
        "Заяц": "Мимо! Заяц удрал ноги пока ты целился. 🐇",
        "Орел": "Не попал! Орел слишком быстрый чтоб подстрелить его. 🦅",
        "Белка": "Не попали! Белка скрылась. 🐿️",
        "Еж": "Промах! Еж свернулся клубком. 🦔",
        "Мышь": "Мимо! Мышь скрылась в траве. 🐭",
        "Лягушка": "Не попали! Лягушка ускользла. 🐸",
        "Змея": "Неудача! Змея впилась в вашу ногу отравив вас. 🐍",
        "Утка": "Мимо! Утка улетела в пруд. 🦆",
        "Сова": "Не видно! Сова улетела в лес и исчезла меж деревьев. 🦉"
    }

    # Результат
    if random.random() < 0.39:  # 39% шанс на выигрыш
        animal = random.choice(list(winning_animals.keys()))
        multiplier = winning_animals[animal]["multiplier"]
        win_amount = int(round(stake * multiplier))

        # Начисляем выигрыш
        try:
            ok_add = await safe_update_user_balance(user_id, int(win_amount))
        except Exception:
            logging.exception("Ошибка начисления выигрыша в охоте")
            ok_add = False

        if not ok_add:
            try:
                await update_user_balance(user_id, int(win_amount))
            except Exception:
                logging.exception("Альтернативное начисление выигрыша провалено")

        # Логируем выигрыш в статистике (winp)
        try:
            await add_win_record(user_id, int(win_amount))
        except Exception:
            logging.exception("add_win_record упала в охоте")

        try:
            text = winning_animals[animal]['win_text'].format(win_amount=win_amount)
            await bot.edit_message_text(text, chat_id=message.chat.id, message_id=hunt_message.message_id)
        except Exception as e:
            logging.error(f"Error editing message (win): {e}")

    else:
        # Логируем проигрыш в статистике (losp)
        try:
            await add_loss_record(user_id, int(stake))
        except Exception:
            logging.exception("add_loss_record упала в охоте")

        animal = random.choice(list(losing_animals.keys()))
        try:
            await bot.edit_message_text(losing_animals[animal], chat_id=message.chat.id, message_id=hunt_message.message_id)
        except Exception as e:
            logging.error(f"Error editing message (lose): {e}")

    # Обновляем время последней команды
    try:
        await update_last_command_time(user_id)
    except Exception:
        logging.exception("update_last_command_time упала в охоте")
# --- Блэкджек ---

blackjack_games = {}  # Словарь для хранения игр blackjack. {user_id: {game_data}}

def create_deck():
    suits = ['❤️', '♦️', '♣️', '♠️']
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    deck = [(rank, suit) for suit in suits for rank in ranks]
    random.shuffle(deck)
    return deck

def deal_card(deck):
    if deck:
        return deck.pop()
    else:
        return None

def calculate_score(cards):
    score = 0
    aces = 0
    for rank, suit in cards:
        if rank in ['J', 'Q', 'K', '10']:
            score += 10
        elif rank == 'A':
            score += 11
            aces += 1
        else:
            try:
                score += int(rank)
            except ValueError:
                logging.error(f"Некорректный ранг карты: {rank}")
                return -999
    while score > 21 and aces > 0:
        score -= 10
        aces -= 1
    return score

def card_to_string(card):
    rank, suit = card
    return f"{rank}{suit}"

@dp.message_handler(Text(startswith="бж", ignore_case=True))
async def blackjack_command(message: types.Message):
    user_id = message.from_user.id

    if not await is_command_allowed(user_id):
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("❌Используйте: бж (ставка)")
            return

        stake_str = parts[1].lower()
        balance_raw = await get_user_balance(user_id)
        try:
            balance = int(round(float(balance_raw)))
        except Exception:
            try:
                balance = int(balance_raw)
            except Exception:
                balance = 0

        if stake_str in ('все', 'всё'):
            stake = int(balance)
        else:
            stake = format_stake(stake_str)
            if stake is not None:
                stake = int(stake)

        if stake is None:
            await message.reply("❌Неверный формат ставки. Используйте число или сокращение (1к, 1м).")
            return

        if stake < 100:
            await message.reply("❌Минимальная ставка для блэкджека 100 Spark🦎")
            return

        if stake <= 0:
            await message.reply("❌Ставка должна быть больше нуля.")
            return

        if stake > balance:
            await message.reply("❌Недостаточно средств. 😔")
            return

    except (IndexError, ValueError):
        await message.reply("❌Используйте: бж (ставка)")
        return

    # Снятие ставки — через безопасный updater
    try:
        ok = await safe_update_user_balance(user_id, -int(stake))
    except Exception:
        logging.exception("Ошибка safe_update_user_balance при списании ставки в блэкджеке")
        ok = False

    if not ok:
        try:
            await update_user_balance(user_id, -int(stake))
            ok = True
        except Exception:
            logging.exception("Альтернативное списание ставки провалено в блэкджеке")
            ok = False

    if not ok:
        await message.reply("❌Не удалось списать ставку. Попробуйте позже.")
        return

    # Логируем начало игры (gamep)
    try:
        await increment_games_played(user_id, 1)
    except Exception:
        logging.exception("increment_games_played упала в блэкджеке")

    deck = create_deck()
    user_cards = []
    bot_cards = []

    for _ in range(2):
        user_cards.append(deal_card(deck))
        bot_cards.append(deal_card(deck))

    user_score = calculate_score(user_cards)
    bot_score = calculate_score(bot_cards)

    game_data = {
        "deck": deck,
        "user_cards": user_cards,
        "bot_cards": bot_cards,
        "user_score": user_score,
        "bot_score": bot_score,
        "stake": int(stake),
        "user_id": user_id,
        "stand_used": False
    }
    blackjack_games[user_id] = game_data

    keyboard = InlineKeyboardMarkup(row_width=2)
    hit_button = InlineKeyboardButton("➕ Еще", callback_data=f"bj_hit:{user_id}")
    stand_button = InlineKeyboardButton("🛑 Стоп", callback_data=f"bj_stand:{user_id}")
    keyboard.add(hit_button, stand_button)

    message_text = (f"Ваши карты: {', '.join([card_to_string(c) for c in user_cards])} ({user_score} очков)\n"
                    f"Карты бота: {card_to_string(bot_cards[0])}, ?")
    bj_message = await message.reply(message_text, reply_markup=keyboard)

    blackjack_games[user_id]["message_id"] = bj_message.message_id
    try:
        await update_last_command_time(user_id)
    except Exception:
        logging.exception("update_last_command_time упала в blackjack_command")

@dp.callback_query_handler(Text(startswith="bj_hit:"))
async def hit_callback(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split(":")[1])

    if callback_query.from_user.id != user_id:
        await callback_query.answer("Это не ваша кнопка!", show_alert=True)
        return

    if user_id not in blackjack_games:
        await callback_query.answer("Игра не найдена. Начните новую игру.")
        return

    game_data = blackjack_games[user_id]
    deck = game_data["deck"]
    user_cards = game_data["user_cards"]
    bot_cards = game_data["bot_cards"]
    user_score = game_data["user_score"]
    stake = game_data["stake"]
    message_id = game_data["message_id"]

    new_card = deal_card(deck)
    if new_card:
        user_cards.append(new_card)
        user_score = calculate_score(user_cards)

        game_data["user_cards"] = user_cards
        game_data["user_score"] = user_score
        blackjack_games[user_id] = game_data

        if user_score > 21:
            await game_end("Перебор! Вы проиграли. 😭", callback_query.message.chat.id, message_id,
                           user_cards, bot_cards, user_score, game_data["bot_score"], stake, user_id)
            return

        message_text = (f"Ваши карты: {', '.join([card_to_string(c) for c in user_cards])} ({user_score} очков)\n"
                        f"Карты бота: {card_to_string(bot_cards[0])}, ?")
        keyboard = InlineKeyboardMarkup(row_width=2)
        hit_button = InlineKeyboardButton("➕ Еще", callback_data=f"bj_hit:{user_id}")
        stand_button = InlineKeyboardButton("🛑 Стоп", callback_data=f"bj_stand:{user_id}")
        keyboard.add(hit_button, stand_button)

        try:
            await bot.edit_message_text(message_text,
                                        chat_id=callback_query.message.chat.id,
                                        message_id=message_id,
                                        reply_markup=keyboard)
        except MessageNotModified:
            pass
        except Exception as e:
            logging.error(f"Error editing message: {e}")

        await bot.answer_callback_query(callback_query.id)
    else:
        await bot.answer_callback_query(callback_query.id, "В колоде больше нет карт!", show_alert=True)

@dp.callback_query_handler(Text(startswith="bj_stand:"))
async def stand_callback(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split(":")[1])

    if callback_query.from_user.id != user_id:
        await callback_query.answer("Это не ваша кнопка!", show_alert=True)
        return

    if user_id not in blackjack_games:
        await callback_query.answer("Игра не найдена. Начните новую игру.")
        return

    game_data = blackjack_games[user_id]

    if game_data.get("stand_used", False):
        await callback_query.answer("Вы уже нажали кнопку 'Стоп'!", show_alert=True)
        return

    game_data["stand_used"] = True
    blackjack_games[user_id] = game_data

    deck = game_data["deck"]
    bot_cards = game_data["bot_cards"]
    bot_score = game_data["bot_score"]
    message_id = game_data["message_id"]

    while bot_score < 17:
        new_card = deal_card(deck)
        if new_card:
            bot_cards.append(new_card)
            bot_score = calculate_score(bot_cards)
        else:
            logging.warning("У бота закончились карты в колоде")
            break

    game_data["bot_cards"] = bot_cards
    game_data["bot_score"] = bot_score
    blackjack_games[user_id] = game_data

    await game_end(None, callback_query.message.chat.id, message_id,
                   game_data["user_cards"], bot_cards, game_data["user_score"], bot_score, game_data["stake"], user_id)
    await bot.answer_callback_query(callback_query.id)

async def game_end(result_text, chat_id, message_id, user_cards, bot_cards, user_score, bot_score, stake, user_id):
    winner = None
    if bot_score > 21:
        winner = "user"
    elif user_score > 21:
        winner = "bot"
    elif bot_score > user_score:
        winner = "bot"
    elif user_score > bot_score:
        winner = "user"
    else:
        winner = "draw"

    win_amount = 0

    if not result_text:
        if winner == "user":
            # win_amount — сумма, которую начисляем на баланс (включая ставку, как в исходнике)
            if user_score == 21 and len(user_cards) == 2:
                result_text = "Блэкджек! Вы выиграли! 🎉"
                win_amount = stake * 1.8
            else:
                result_text = "Вы выиграли! 🎉"
                win_amount = stake * 1.4
        elif winner == "bot":
            result_text = "Вы проиграли. 😭"
            win_amount = 0
        else:
            result_text = "Ничья! Ставка возвращена. 🤝"
            win_amount = stake

    win_amount = int(round(win_amount))

    if win_amount > 0 and winner == "user":
        result_text += f" Ваш приз: {win_amount} Spark🦎"

    message_text = (f"Ваши карты: {', '.join([card_to_string(c) for c in user_cards])} ({user_score} очков)\n"
                    f"Карты бота: {', '.join([card_to_string(c) for c in bot_cards])} ({bot_score} очков)\n\n"
                    f"{result_text}")

    keyboard = InlineKeyboardMarkup()
    try:
        await bot.edit_message_text(message_text, chat_id=chat_id, message_id=message_id, reply_markup=keyboard)
    except MessageNotModified:
        pass
    except Exception as e:
        logging.error(f"Error editing message: {e}")

    # Начисления и запись статистики
    if winner == "user":
        # Начисляем выигрыш
        try:
            ok_add = await safe_update_user_balance(user_id, int(win_amount))
        except Exception:
            logging.exception("Ошибка safe_update_user_balance при начислении выигрыша в блэкджеке")
            ok_add = False

        if not ok_add:
            try:
                await update_user_balance(user_id, int(win_amount))
            except Exception:
                logging.exception("Альтернативное начисление выигрыша провалено в блэкджеке")

        # Записываем выигрыш в статистику (winp)
        if win_amount > 0:
            try:
                await add_win_record(user_id, int(win_amount))
            except Exception:
                logging.exception("add_win_record упала в блэкджеке")

    elif winner == "draw":
        # Возвращаем ставку пользователю
        try:
            ok_refund = await safe_update_user_balance(user_id, int(win_amount))  # win_amount == stake
        except Exception:
            logging.exception("Ошибка safe_update_user_balance при возврате ставки в блэкджеке")
            ok_refund = False

        if not ok_refund:
            try:
                await update_user_balance(user_id, int(win_amount))
            except Exception:
                logging.exception("Альтернативный возврат ставки провален в блэкджеке")

        # Ничья — обычно не считаем winp; можно логировать отдельно при необходимости

    elif winner == "bot":
        # Проигрыш — ставка уже списана при старте, просто логируем lossp
        try:
            await add_loss_record(user_id, int(stake))
        except Exception:
            logging.exception("add_loss_record упала в блэкджеке")

    # Удаляем игру из памяти
    if user_id in blackjack_games:
        del blackjack_games[user_id]
    else:
        logging.warning(f"Игра для user_id {user_id} не найдена для удаления.")

# -------------------- Новые команды --------------------






@dp.message_handler(Text(startswith="Выдать", ignore_case=True))
async def give_command(message: types.Message):
    """Обработчик команды выдачи"""
    user_id = message.from_user.id

    if not await is_command_allowed(user_id):
        return

    # Проверка прав для нескольких владельцев
    if user_id not in OWNER_IDS:
        await message.reply("У вас нет прав на эту команду. 🚫")
        return

    if not message.reply_to_message:
        await message.reply("Команда должна быть ответом на сообщение пользователя, которому нужно выдать средства.")
        return

    try:
        stake_str = message.text.split()[1]
        amount = format_stake(stake_str)
        if amount is None:
            raise ValueError("Некорректный формат суммы.")
    except (IndexError, ValueError) as e:
        await message.reply(f"Используйте: Выдать (сумма) в ответ на сообщение пользователя. Ошибка: {e}")
        return

    receiver_id = message.reply_to_message.from_user.id
    receiver_username = message.reply_to_message.from_user.username or message.reply_to_message.from_user.first_name
    owner_username = message.from_user.username or message.from_user.first_name

    cursor.execute(
        "UPDATE users SET balance = balance + ?, last_command = ? WHERE user_id = ?",
        (amount, datetime.now().isoformat(), receiver_id)
    )
    conn.commit()

    formatted_amount = format_balance(amount)  # Используем format_balance для сокращенного представления
    reply_text = (
        f"👑От: {owner_username}\n"
        f"🎩Кому: {receiver_username}\n"
        f"💎Выдано: +{formatted_amount} Spark🦎"
    )

    await message.reply(reply_text, parse_mode=types.ParseMode.HTML)
    await update_last_command_time(user_id)



@dp.message_handler(Text(startswith="Забрать", ignore_case=True))
async def take_command(message: types.Message):
    """Обработчик команды забрать"""
    user_id = message.from_user.id

    if not await is_command_allowed(user_id):
        return

    if user_id not in OWNER_IDS:
        await message.reply("У вас нет прав на эту команду. 🚫")
        return

    if not message.reply_to_message:
        await message.reply("Команда должна быть ответом на сообщение пользователя, у которого нужно забрать средства.")
        return

    try:
        amount_str = message.text.split()[1]
        try:
            amount = float(amount_str)  # Разрешаем дробные числа
        except ValueError:
            await message.reply("Некорректный формат суммы. Используйте число (например, 0.29288228).")
            return
        if amount <= 0:
            await message.reply("Сумма должна быть положительной.")
            return

    except (IndexError) as e:
        await message.reply(f"Используйте: Забрать (сумма) в ответ на сообщение пользователя. Ошибка: {e}")
        return

    target_id = message.reply_to_message.from_user.id
    target_username = message.reply_to_message.from_user.username or message.reply_to_message.from_user.first_name
    owner_username = message.from_user.username or message.from_user.first_name

    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (target_id,))
    result = cursor.fetchone()

    if not result or result[0] < amount:
        await message.reply("У пользователя недостаточно средств.")
        return

    cursor.execute("UPDATE users SET balance = balance - ?, last_command = ? WHERE user_id = ?", (amount, datetime.now().isoformat(), target_id))
    conn.commit()

    formatted_amount = "{:,.8f}".format(amount).replace(",", " ").replace(".", ",")[:15]  # Форматируем до 8 знаков после запятой,  убираем лишние символы
    reply_text = (
        f"👑Забрал: <b>{owner_username}</b>\n"
        f"🔥У кого: <b>{target_username}</b>\n"
        f"Забрано: {formatted_amount} Spark🦎"
    )

    await message.reply(reply_text, parse_mode=types.ParseMode.HTML)
    await update_last_command_time(user_id)

@dp.message_handler(Text(equals="Обнул", ignore_case=True))
async def reset_balances_command(message: types.Message):
    """Обработчик команды обнуления балансов"""
    user_id = message.from_user.id

    # Проверка cooldown
    if not await is_command_allowed(user_id):
        return

    if user_id not in OWNER_IDS:
        await message.reply("У вас нет прав на эту команду. 🚫")
        return

    cursor.execute("UPDATE users SET balance = 0")
    conn.commit()
    await message.reply("Балансы всех пользователей успешно обнулены. ✅")
    await update_last_command_time(user_id)  # Обновляем время последней команды

@dp.message_handler(Text(startswith='+бан'))
async def ban_user(message: types.Message):
    sender_id = message.from_user.id  # кто отправил команду

    if sender_id not in OWNER_IDS:
        await message.reply("У вас нет прав на выполнение этой команды.")
        return

    try:
        target_user_id = int(message.text[4:].strip())
    except ValueError:
        await message.reply("Неверный формат ID пользователя.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO banned_users (user_id) VALUES (?)", (target_user_id,))
        conn.commit()
        await message.reply(f"Пользователь с ID {target_user_id} забанен.")
    except sqlite3.IntegrityError:
        await message.reply(f"Пользователь с ID {target_user_id} уже забанен.")
    finally:
        close_db_connection(conn)


@dp.message_handler(Text(startswith='+анбан'))
async def unban_user(message: types.Message):
    sender_id = message.from_user.id

    if sender_id not in OWNER_IDS:
        await message.reply("У вас нет прав на выполнение этой команды.")
        return

    try:
        target_user_id = int(message.text[7:].strip())
    except ValueError:
        await message.reply("Неверный формат ID пользователя.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM banned_users WHERE user_id = ?", (target_user_id,))
    conn.commit()
    if cursor.rowcount > 0:
        await message.reply(f"Пользователь с ID {target_user_id} разбанен.")
    else:
        await message.reply(f"Пользователь с ID {target_user_id} не был забанен.")
    close_db_connection(conn)

# Middleware для проверки, забанен ли пользователь
class BannedUserMiddleware(BaseMiddleware):  #  <---  Наследуемся от BaseMiddleware
    async def on_process_message(self, message: types.Message, data: dict):
        user_id = message.from_user.id
        if await is_user_banned(user_id):
            raise CancelHandler()

    async def on_process_callback_query(self, call: types.CallbackQuery, data: dict):
        user_id = call.from_user.id
        if await is_user_banned(user_id):
            await call.answer("Вы забанены и не можете использовать этого бота.")
            raise CancelHandler()

dp.middleware.setup(BannedUserMiddleware()) 


# --- Функция для регистрации обработчиков ---
def register_check_handlers(dp: Dispatcher, bot: Bot):
    """Регистрирует обработчики для системы чеков."""
    dp.register_message_handler(create_check_command)
    dp.register_message_handler(create_check_group_command, chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
# -------------------- Обработчик ошибок --------------------

@dp.errors_handler()
async def errors_handler(update: types.Update, exception: Exception):
    """Логирует ошибки."""
    logging.exception(f"Update: {update}\nException: {exception}")
    return True

# -------------------- Запуск бота --------------------

async def on_startup(dp):
    print("BLAZE IS BOT STARTED🟢")
    # Запуск фоновой задачи для проверки игр Квак
    asyncio.create_task(check_game())   
    # Запуск фоновой задачи для проверки игр GOLD
    asyncio.create_task(check_gold_games())      
    # Установка команд в меню бота
    await dp.bot.set_my_commands([
        types.BotCommand("start", "Запустить бота"),
    ])


@dp.callback_query_handler()
async def check_callback_user(callback_query: types.CallbackQuery):
    """Глобальная проверка пользователя для callback_query."""
    try:
        # Проверяем, есть ли user_id в callback_data
        if 'user_id' in callback_query.data:
            expected_user_id = int(callback_query.data.split(":")[1])
            if callback_query.from_user.id != expected_user_id:
                await callback_query.answer("Это не ваша кнопка!", show_alert=True)
                return True  # Прерываем дальнейшую обработку

        # Проверка для fast_claim
        if "fast_claim" in callback_query.data:
            fast_id = int(callback_query.data.split(":")[1])
            cursor.execute("SELECT chat_id FROM fasts WHERE fast_id = ?", (fast_id,))
            result = cursor.fetchone()
            if result:
                chat_id = result[0]
                # Разрешаем нажатие только в канале с фастом
                if callback_query.message.chat.id != chat_id:
                    await callback_query.answer("Забрать фаст можно только в канале!", show_alert=True)
                    return True  # Прерываем дальнейшую обработку

        # Если callback_data не содержит user_id, пропускаем проверку
        return False  # Разрешаем дальнейшую обработку
    except IndexError:
        logging.warning(f"Некорректные callback_data: {callback_query.data}")
        await callback_query.answer("Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        return True #Прерываем дальнейшую обработку


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup) 
