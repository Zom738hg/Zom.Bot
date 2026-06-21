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

DB = "stats.db"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

# ================= SYSTEMS =================
user_mentions = defaultdict(list)
rage_users = {}  # user_id -> timestamp (until when angry)

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

# ================= START =================
@bot.event
async def setup_hook():
    await init_db()
    print("Bot ready")

# ================= MESSAGE HANDLER =================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id
    now = time.time()

    # ===== DB COUNTER =====
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO users (user_id, messages, respect)
        VALUES (?, 1, 0)
        ON CONFLICT(user_id)
        DO UPDATE SET messages = messages + 1
        """, (user_id,))
        await db.commit()

    # ================= CHECK RAGE EXPIRE =================
    if user_id in rage_users:
        if now > rage_users[user_id]:
            del rage_users[user_id]

    # ================= BOT MENTION =================
    if bot.user in message.mentions:

        text = message.content.lower()

        # ================= SPAM TRACK =================
        user_mentions[user_id].append(now)

        user_mentions[user_id] = [
            t for t in user_mentions[user_id] if now - t <= 20
        ]

        count = len(user_mentions[user_id])

        # ================= RAGE MODE =================
        if user_id in rage_users:
            reply = random.choice([
                "Отстань.",
                "ты заебал",
                "хватит",
            ])

        # ================= TRIGGER RAGE =================
        elif count >= 3:
            rage_users[user_id] = now + 10  # 10 секунд злости

            reply = random.choice([
                "ТА ТЫ ЗАЕБАЛ",
                "ХВАТИТ ЕПТ ТВОЮ МАТЬ",
                "Я ТЕБЕ НЕ БАБКА В ТРАМВАЕ ЧТОБ БЕСИТЬ",
                "я еду к тебе домой гатов сраку"
            ])

        # ================= NORMAL =================
        else:
            clean_text = text.replace(f"<@{bot.user.id}>", "").strip()

            if "?" in text:
                reply = random.choice([
                    "Да",
                    "Нет",
                    "Возможно.",
                    "Я не уверен."
                ])

            elif clean_text == "":
                reply = random.choice([
                    "чо надо",
                    "Да?",
                ])

            else:
                reply = random.choice([
                    "Говори.",
                    "Я тута.",
                    "Чо надо?"
                ])

        await message.reply(reply)

    await bot.process_commands(message)

# ================= COMMANDS =================
@bot.command()
async def help(ctx):
    await ctx.send("""
КОМАНДЫ:

!respect @user amount - выдать уважение (только админы)
""")

@bot.command()
@commands.has_permissions(administrator=True)
async def respect(ctx, member: discord.Member, amount: int):

    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO users (user_id, respect)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET respect = respect + ?
        """, (member.id, amount, amount))
        await db.commit()

    await ctx.send(f"Пользователь {member} получил {amount} уважения")

# ================= READY =================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.run(TOKEN)
