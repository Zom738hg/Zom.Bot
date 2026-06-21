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
rage_users = {}

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

    # ================= DB COUNTER =================
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO users (user_id, messages, respect)
        VALUES (?, 1, 0)
        ON CONFLICT(user_id)
        DO UPDATE SET messages = messages + 1
        """, (user_id,))
        await db.commit()

    # ================= EXPIRE RAGE =================
    if user_id in rage_users and now > rage_users[user_id]:
        del rage_users[user_id]

    reply = None

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
                "иди нахуй",
                "заебал",
                "."
            ])

        # ================= TRIGGER RAGE =================
        elif count >= 3:
            rage_users[user_id] = now + 10

            reply = random.choice([
                "ТА ТЫ ЗАЕБАЛ",
                "ЗАВАЛИ ЕБАЛО",
                "я найду тебя и разобью ебальник. гатовь сраку, мы едем тебя бить публично"
            ])

        # ================= NORMAL =================
        else:
            clean = text.replace(f"<@{bot.user.id}>", "").strip()

            if "?" in text:
                reply = random.choice([
                    "Да",
                    "Нет",
                    "Возможно"
                ])

            elif clean == "":
                reply = random.choice([
                    "Я тута",
                    "Чо надо",
                    "Да?"
                ])

            else:
                reply = random.choice([
                    "Говори",
                    "Я слушаю",
                    "Я тута"
                ])

    # ================= FIX: NO DOUBLE REPLY =================
    if reply:
        try:
            await message.reply(reply, mention_author=False)
        except:
            pass

    await bot.process_commands(message)

# ================= PANEL =================
class Panel(discord.ui.View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="Top Messages", style=discord.ButtonStyle.green)
    async def top_messages(self, interaction, button):

        async with aiosqlite.connect(DB) as db:
            rows = await (await db.execute("""
                SELECT user_id, messages FROM users
                ORDER BY messages DESC LIMIT 10
            """)).fetchall()

        text = "TOP MESSAGES:\n"
        for i, (uid, msg) in enumerate(rows, 1):
            user = await bot.fetch_user(uid)
            text += f"{i}. {user.name} - {msg}\n"

        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="Top Respect", style=discord.ButtonStyle.blurple)
    async def top_respect(self, interaction, button):

        async with aiosqlite.connect(DB) as db:
            rows = await (await db.execute("""
                SELECT user_id, respect FROM users
                ORDER BY respect DESC LIMIT 10
            """)).fetchall()

        text = "TOP RESPECT:\n"
        for i, (uid, r) in enumerate(rows, 1):
            user = await bot.fetch_user(uid)
            text += f"{i}. {user.name} - {r}\n"

        await interaction.response.send_message(text, ephemeral=True)

# ================= COMMANDS =================
@bot.command()
async def panel(ctx):
    await ctx.send("PANEL:", view=Panel())

@bot.command()
async def help(ctx):
    await ctx.send("""
КОМАНДЫ:
!panel - статистика
!respect @user amount - выдать уважение (admin only)
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

    await ctx.send(f"{member} получил {amount} respect")

# ================= READY =================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.run(TOKEN)
