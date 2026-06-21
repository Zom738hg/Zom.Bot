import discord
from discord.ext import commands
import aiosqlite
import os
from dotenv import load_dotenv

# ================= LOAD TOKEN =================
load_dotenv()
TOKEN = os.getenv("TOKEN")

DB = "stats.db"

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

# ================= SAFE DATABASE INIT =================
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            messages INTEGER DEFAULT 0,
            respect INTEGER DEFAULT 0
        )
        """)

        # 🔥 SAFE MIGRATION (додає тільки якщо нема)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN messages INTEGER DEFAULT 0")
        except:
            pass

        try:
            await db.execute("ALTER TABLE users ADD COLUMN respect INTEGER DEFAULT 0")
        except:
            pass

        await db.commit()

# ================= SETUP =================
@bot.event
async def setup_hook():
    await init_db()
    await bot.tree.sync()
    print("Bot ready + DB safe")

# ================= SAFE MESSAGE HANDLER =================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    try:
        async with aiosqlite.connect(DB) as db:
            await db.execute("""
            INSERT INTO users (user_id, messages)
            VALUES (?, 1)
            ON CONFLICT(user_id)
            DO UPDATE SET messages = messages + 1
            """, (message.author.id,))
            await db.commit()

    except Exception as e:
        print(f"[DB ERROR] {e}")

    await bot.process_commands(message)

# ================= PANEL =================
class Panel(discord.ui.View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="Top Messages", style=discord.ButtonStyle.green)
    async def top_messages(self, interaction: discord.Interaction, button: discord.ui.Button):

        async with aiosqlite.connect(DB) as db:
            cursor = await db.execute("""
            SELECT user_id, messages FROM users
            ORDER BY messages DESC LIMIT 10
            """)
            rows = await cursor.fetchall()

        text = "🏆 TOP MESSAGES:\n"
        for i, (uid, msg) in enumerate(rows, 1):
            user = await bot.fetch_user(uid)
            text += f"{i}. {user.name} - {msg}\n"

        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="Top Respect", style=discord.ButtonStyle.blurple)
    async def top_respect(self, interaction: discord.Interaction, button: discord.ui.Button):

        async with aiosqlite.connect(DB) as db:
            cursor = await db.execute("""
            SELECT user_id, respect FROM users
            ORDER BY respect DESC LIMIT 10
            """)
            rows = await cursor.fetchall()

        text = "⭐ TOP RESPECT:\n"
        for i, (uid, r) in enumerate(rows, 1):
            user = await bot.fetch_user(uid)
            text += f"{i}. {user.name} - {r}\n"

        await interaction.response.send_message(text, ephemeral=True)

# ================= COMMANDS =================
@bot.command()
async def panel(ctx):
    await ctx.send("📊 Dashboard:", view=Panel())

@bot.command()
async def help(ctx):
    await ctx.send("""
📜 COMMANDS:
!panel - open dashboard
!topmessages - top users
!toprespect - respect leaderboard
!respect @user amount - give respect
""")

@bot.command()
@commands.has_permissions(administrator=True)
async def respect(ctx, member: discord.Member, amount: int):

    try:
        async with aiosqlite.connect(DB) as db:
            await db.execute("""
            INSERT INTO users (user_id, respect)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET respect = respect + ?
            """, (member.id, amount, amount))
            await db.commit()

        await ctx.send(f"⭐ {member.mention} +{amount} respect")

    except Exception as e:
        await ctx.send("❌ Error occurred")
        print(e)

# ================= START =================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.run(TOKEN)
