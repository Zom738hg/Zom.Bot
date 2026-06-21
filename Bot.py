import discord
from discord.ext import commands
import aiosqlite
import os
from dotenv import load_dotenv
import random

# ================= LOAD TOKEN =================
load_dotenv()
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN not found in environment variables!")

DB = "stats.db"

# ================= INTENTS =================
intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

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

# ================= STARTUP =================
@bot.event
async def setup_hook():
    await init_db()
    print("Database initialized")

# ================= MESSAGE HANDLER =================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

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
        print(f"Database Error: {e}")

    # ================= BOT MENTION REPLIES =================
    if bot.user in message.mentions:

        text = message.content.lower()

        toxic_words = [
            "idiot",
            "stupid",
            "dumb",
            "loser",
            "trash"
        ]

        is_toxic = any(word in text for word in toxic_words)

        normal_replies = [
            "What do you need?",
            "I'm here.",
            "Yes?",
            "Go ahead.",
            "I'm listening.",
            "How can I help?",
            "What's up?",
            "Tell me."
        ]

        toxic_replies = [
            "Maybe.",
            "No.",
            "Yes.",
            "I don't know.",
            "Probably."
        ]

        if is_toxic:
            reply = random.choice(toxic_replies)
        else:
            reply = random.choice(normal_replies)

        await message.reply(reply)

    await bot.process_commands(message)

# ================= PANEL =================
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

        text = "🏆 TOP MESSAGES\n\n"

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

        text = "⭐ TOP RESPECT\n\n"

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

# ================= COMMANDS =================
@bot.command()
async def panel(ctx):
    await ctx.send(
        "📊 Dashboard",
        view=Panel()
    )

@bot.command()
async def help(ctx):
    await ctx.send("""
📖 COMMANDS

!panel
Open dashboard

!respect @user amount
Give respect (Admin only)
""")

@bot.command()
@commands.has_permissions(administrator=True)
async def respect(ctx, member: discord.Member, amount: int):

    try:
        async with aiosqlite.connect(DB) as db:
            await db.execute("""
            INSERT INTO users (user_id, messages, respect)
            VALUES (?, 0, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET respect = respect + ?
            """, (member.id, amount, amount))

            await db.commit()

        await ctx.send(
            f"⭐ {member.mention} received {amount} respect."
        )

    except Exception as e:
        print(e)
        await ctx.send("Error.")

# ================= READY =================
@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Game(name="Ranking System")
    )

    print(f"Logged in as {bot.user}")

# ================= START BOT =================
bot.run(TOKEN)
