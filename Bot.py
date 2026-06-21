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

================= DATABASE =================

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

================= STARTUP =================

@bot.event
async def setup_hook():
await init_db()
print("Database initialized")

================= LANGUAGE =================

def detect_language(text: str):
text = text.lower()

ua_words = [
    "що", "привіт", "допомога",
    "вмієш", "як", "дякую"
]

ru_words = [
    "что", "привет", "помощь",
    "умеешь", "как", "спасибо"
]

if any(word in text for word in ua_words):
    return "ua"

if any(word in text for word in ru_words):
    return "ru"

return "en"
================= MESSAGE EVENT =================

@bot.event
async def on_message(message):

if message.author.bot:
    return

# message counter
try:
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO users (user_id, messages, respect)
        VALUES (?, 1, 0)
        ON CONFLICT(user_id)
        DO UPDATE SET messages = messages + 1
        """, (message.author.id,))
        await db.commit()

except Exception as e:
    print(e)

# mention replies
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

    if (
        "what can you do" in text
        or "що ти вмієш" in text
        or "что ты умеешь" in text
    ):

        if language == "ua":
            reply = (
                "Я можу:\n"
                "• Рахувати повідомлення\n"
                "• Вести рейтинг активності\n"
                "• Видавати respect\n"
                "• Показувати топ користувачів\n"
                "• Відповідати на згадування"
            )

        elif language == "ru":
            reply = (
                "Я умею:\n"
                "• Считать сообщения\n"
                "• Вести рейтинг активности\n"
                "• Выдавать respect\n"
                "• Показывать топ пользователей\n"
                "• Отвечать на упоминания"
            )

        else:
            reply = (
                "I can:\n"
                "• Track messages\n"
                "• Track activity\n"
                "• Give respect points\n"
                "• Show leaderboards\n"
                "• Respond to mentions"
            )

    elif spam_count >= 20:

        if language == "ua":
            reply = "ХВАТІТ"
        elif language == "ru":
            reply = "СУКА ЧО ТАК МНОГО МЕНШЕ ПИШИ"
        else:
            reply = "You're sending too many messages. Slow down."

    else:

        replies = {
            "ua": [
                "чо надо?",
                "Я тут.",
                "Слухаю.",
                "Чим допомогти?",
                "Так?"
            ],
            "ru": [
                "Чо надо?",
                "Я тута.",
                "Слушаю.",
                "Чо надо?",
                "Да?"
            ],
            "en": [
                "What do you need?",
                "I'm here.",
                "I'm listening.",
                "How can I help?",
                "Yes?"
            ]
        }

        reply = random.choice(replies[language])

    await message.reply(reply)

await bot.process_commands(message)
================= PANEL =================

class Panel(discord.ui.View):

def __init__(self):
    super().__init__(timeout=None)

@discord.ui.button(
    label="Top Messages",
    style=discord.ButtonStyle.green
)
async def top_messages(self, interaction, button):

    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("""
        SELECT user_id, messages
        FROM users
        ORDER BY messages DESC
        LIMIT 10
        """)

        rows = await cursor.fetchall()

    text = "TOP MESSAGES\n\n"

    for i, (uid, msg) in enumerate(rows, 1):

        try:
            user = await bot.fetch_user(uid)
            text += f"{i}. {user.name} - {msg}\n"
        except:
            text += f"{i}. Unknown User - {msg}\n"

    await interaction.response.send_message(
        text,
        ephemeral=True
    )

@discord.ui.button(
    label="Top Respect",
    style=discord.ButtonStyle.blurple
)
async def top_respect(self, interaction, button):

    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("""
        SELECT user_id, respect
        FROM users
        ORDER BY respect DESC
        LIMIT 10
        """)

        rows = await cursor.fetchall()

    text = "TOP RESPECT\n\n"

    for i, (uid, respect) in enumerate(rows, 1):

        try:
            user = await bot.fetch_user(uid)
            text += f"{i}. {user.name} - {respect}\n"
        except:
            text += f"{i}. Unknown User - {respect}\n"

    await interaction.response.send_message(
        text,
        ephemeral=True
    )
================= COMMANDS =================

@bot.command()
async def panel(ctx):
await ctx.send("Dashboard", view=Panel())

@bot.command()
async def help(ctx):
await ctx.send("""
COMMANDS

!panel
Open dashboard

!respect @user amount
Give respect (Admin only)
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

await ctx.send(
    f"{member.mention} received {amount} respect."
)
================= READY =================

@bot.event
async def on_ready():

await bot.change_presence(
    activity=discord.Game(
        name="Ranking System"
    )
)

print(f"Logged in as {bot.user}")

bot.run(TOKEN)
