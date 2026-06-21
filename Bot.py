import discord
from discord.ext import commands
import aiosqlite
import os
from dotenv import load_dotenv
import random
import time
from collections import defaultdict

load_dotenv()
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN not found!")

DB = "stats.db"

intents = discord.Intents.all()

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

# ================= MAIN LOGIC =================
@bot.event
async def on_message(message):

    if message.author.bot:
        return

    # ===== DB counter =====
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO users (user_id, messages, respect)
        VALUES (?, 1, 0)
        ON CONFLICT(user_id)
        DO UPDATE SET messages = messages + 1
        """, (message.author.id,))
        await db.commit()

    # ===== BOT MENTION =====
    if bot.user in message.mentions:

        text = message.content.lower()

        now = time.time()

        user_spam[message.author.id].append(now)

        # keep last 30 sec
        user_spam[message.author.id] = [
            t for t in user_spam[message.author.id]
            if now - t < 30
        ]

        spam_count = len(user_spam[message.author.id])

        # ================= YES/NO/MAYBE MODE =================
        if "?" in text:

            replies = ["да", "нет", "может"]
            reply = random.choice(replies)

        # ================= SPAM MODE (AGGRESSIVE) =================
        elif spam_count > 5:

            insults = [
                "Эй, ты че, тормоз? Дай мне передохнуть.",
                "ХВАТИТ СПАМИТЬ, Я НЕ КРУГЛОСУТОЧНЫЙ ЧАТ БЛЯТЬ",
                "Еще раз напишешь — игнор включу нахуй.",
                "ДА ТЫ ЗАЕБАЛ СУКА",
                "Успокойся уже."
            ]

            reply = random.choice(insults)

        # ================= NORMAL =================
        else:
            reply = random.choice([
                "да",
                "нет",
                "может"
            ])

        await message.reply(reply)

    await bot.process_commands(message)

# ================= READY =================
@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Game(name="Russian AI Bot")
    )
    print(f"Logged in as {bot.user}")

bot.run(TOKEN)
