import discord
from discord.ext import commands
import aiosqlite
import os
from dotenv import load_dotenv
import random
import time
from collections import defaultdict

# ================= LOAD TOKEN =================
load_dotenv()
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN not found in .env")

DB = "stats.db"

# ================= INTENTS (FIXED) =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

# ================= SPAM SYSTEM =================
user_spam = defaultdict(list)

# ================= DATABASE =================
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            messages INTEGER DEFAULT 0,
            respect INTEGER DEFAULT 0
        )
        """)
        await db.commit()

@bot.event
async def setup_hook():
    await init_db()
    print("DB ready")

# ================= ON MESSAGE =================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # ===== DB MESSAGE COUNT =====
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO users (user_id, messages, respect)
        VALUES (?, 1, 0)
        ON CONFLICT(user_id)
        DO UPDATE SET messages = messages + 1
        """, (message.author.id,))
        await db.commit()

    # ===== BOT MENTION SYSTEM =====
    if bot.user in message.mentions:

        text = message.content.lower()
        now = time.time()

        user_spam[message.author.id].append(now)

        # keep last 30 sec
        user_spam[message.author.id] = [
            t for t in user_spam[message.author.id] if now - t < 30
        ]

        spam_count = len(user_spam[message.author.id])

        # ===== QUESTION MODE =====
        if "?" in text:
            reply = random.choice(["да", "нет", "может"])

        # ===== SPAM MODE =====
        elif spam_count > 5:
            reply = random.choice([
                "Хватит спамить.",
                "ЗАТКНИСЬ УЖЕ",
                "ТЫ ЗАЕБАЛ",
                "ХВАТИТ БЛЯТЬ",
                "Я ТЕБЕ НЕ ЧАТ ГПТ Я НЕ БУДУ ТЕРПЕТЬ"
            ])

        # ===== NORMAL MODE =====
        else:
            reply = random.choice(["да", "нет", "может"])

        await message.reply(reply)

    await bot.process_commands(message)

# ================= READY =================
@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Game(name="AI Bot Running")
    )
    print(f"Logged in as {bot.user}")

bot.run(TOKEN)
