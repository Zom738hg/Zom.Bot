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
    print("Database initialized")


# ================= LANGUAGE DETECTION =================
def detect_language(text: str):
    text = text.lower()

    ua_words = ["що", "привіт", "вмієш", "дякую", "як", "допомога"]
    ru_words = ["что", "привет", "умеешь", "спасибо", "как", "помощь"]

    if any(w in text for w in ua_words):
        return "ua"
    if any(w in text for w in ru_words):
        return "ru"
    return "en"


# ================= MESSAGE EVENT =================
@bot.event
async def on_message(message):

    if message.author.bot:
        return

    # ===== DB counter =====
    try:
        async with aiosqlite.connect(DB) as db:
            await db.execute("""
            INSERT INTO users (user_id, messages, respect)
            VALUES (?, 1, 0)
            ON CONFLICT(user_id)
            DO UPDATE SET messages = messages + 1
            """, (message.author.id,))
            await db.commit()
    except:
        pass

# ================= MENTION LOGIC =================
if bot.user in message.mentions:

    text = message.content.lower()
    language = detect_language(text)

    now = time.time()

    user_spam[message.author.id].append(now)

    user_spam[message.author.id] = [
        t for t in user_spam[message.author.id]
        if now - t < 30
    ]

    spam_count = len(user_spam[message.author.id])

    # ================= YES / NO / MAYBE =================
    yes_words = ["yes", "так", "да", "ага"]
    no_words = ["no", "ні", "нет", "не"]
    maybe_words = ["maybe", "можливо", "возможно", "хз"]

    if any(w in text for w in yes_words):

        if language == "ua":
            reply = "Так "
        elif language == "ru":
            reply = "Да "
        else:
            reply = "Yes "

    elif any(w in text for w in no_words):

        if language == "ua":
            reply = "Ні "
        elif language == "ru":
            reply = "Нет "
        else:
            reply = "No "

    elif any(w in text for w in maybe_words):

        if language == "ua":
            reply = "Можливо "
        elif language == "ru":
            reply = "Возможно "
        else:
            reply = "Maybe "

    # ================= WHAT CAN YOU DO =================
    elif "what can you do" in text or "що ти вмієш" in text or "что ты умеешь" in text:

        if language == "ua":
            reply = "Я вмію працювати з повідомленнями, рейтингом і respect."
        elif language == "ru":
            reply = "Я умею работать с сообщениями, рейтингом и respect."
        else:
            reply = "I can handle messages, ranking and respect system."

        # ===== WHAT CAN YOU DO =====
        if "what can you do" in text or "що ти вмієш" in text or "что ты умеешь" in text:

            if language == "ua":
                reply = "Я вмію: рахувати повідомлення, рейтинг, respect і відповідати."
            elif language == "ru":
                reply = "Я умею: считать сообщения, рейтинг, respect и отвечать."
            else:
                reply = "I can track messages, ranking, respect system and respond."

        # ===== SPAM MODE =====
        elif spam_count >= 20:

            if language == "ua":
                reply = "СТОПЕ"
            elif language == "ru":
                reply = "ТЫ ЗАЕБАЛ ХВАТИТ СПАМИТЬ"
            else:
                reply = "You're sending too many messages. Slow down."

        # ===== NORMAL AI STYLE =====
        else:
            replies = {
                "ua": ["Я тут.", "Слухаю.", "Чим допомогти?", "Так?"],
                "ru": ["Я тута.", "Чо надо.", "Чо надо?", "Да?"],
                "en": ["I'm here.", "Yes?", "What do you need?", "I'm listening."]
            }

            reply = random.choice(replies[language])

        await message.reply(reply)

    await bot.process_commands(message)


# ================= PANEL =================
class Panel(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Top Messages", style=discord.ButtonStyle.green)
    async def top_messages(self, interaction, button):

        async with aiosqlite.connect(DB) as db:
            cursor = await db.execute("""
            SELECT user_id, messages FROM users
            ORDER BY messages DESC LIMIT 10
            """)
            rows = await cursor.fetchall()

        text = "TOP MESSAGES\n\n"

        for i, (uid, msg) in enumerate(rows, 1):
            try:
                user = await bot.fetch_user(uid)
                text += f"{i}. {user.name} - {msg}\n"
            except:
                text += f"{i}. Unknown - {msg}\n"

        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="Top Respect", style=discord.ButtonStyle.blurple)
    async def top_respect(self, interaction, button):

        async with aiosqlite.connect(DB) as db:
            cursor = await db.execute("""
            SELECT user_id, respect FROM users
            ORDER BY respect DESC LIMIT 10
            """)
            rows = await cursor.fetchall()

        text = "TOP RESPECT\n\n"

        for i, (uid, r) in enumerate(rows, 1):
            try:
                user = await bot.fetch_user(uid)
                text += f"{i}. {user.name} - {r}\n"
            except:
                text += f"{i}. Unknown - {r}\n"

        await interaction.response.send_message(text, ephemeral=True)


# ================= COMMANDS =================
@bot.command()
async def panel(ctx):
    await ctx.send("Dashboard", view=Panel())


@bot.command()
async def help(ctx):
    await ctx.send("""
COMMANDS:
!panel - open dashboard
!respect @user amount - admin only
""")


@bot.command()
@commands.has_permissions(administrator=True)
async def respect(ctx, member: discord.Member, amount: int):

    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO users (user_id, messages, respect)
        VALUES (?, 0, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET respect = respect + ?
        """, (member.id, amount, amount))
        await db.commit()

    await ctx.send(f"{member.mention} got {amount} respect.")


# ================= READY =================
@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Game(name="Ranking System")
    )
    print(f"Logged in as {bot.user}")


bot.run(TOKEN)
