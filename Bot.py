import discord
from discord.ext import commands
import aiosqlite
import os
import re
from dotenv import load_dotenv
import random
import time
from collections import defaultdict
from openai import AsyncOpenAI

# ============================= CONFIG =============================
load_dotenv()
TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ========== ЗМІНЮЙТЕ МОДЕЛЬ ТІЛЬКИ ТУТА ==========
# https://openrouter.ai/models для дивіння доступних моделей
TEXT_MODEL = "openai/gpt-4o-mini"

# Альтернативні моделі:
# TEXT_MODEL = "openai/gpt-4-turbo"
# TEXT_MODEL = "anthropic/claude-3-sonnet"
# TEXT_MODEL = "anthropic/claude-3-opus"
# TEXT_MODEL = "meta-llama/llama-2-70b-chat"
# TEXT_MODEL = "mistralai/mistral-large"

DB = "stats.db"
RAGE_DURATION = 10  # секунд
SPAM_WINDOW = 500  # мілісекунд

# ============================= INIT =============================
ai_text = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

# ============================= STATE =============================
user_empty_mentions = defaultdict(list)
rage_users = {}

# ============================= DATABASE =============================
async def init_db():
    """Initialize database"""
    async with aiosqlite.connect(DB) as db:
        # Users table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            messages INTEGER DEFAULT 0,
            respect INTEGER DEFAULT 0
        )
        """)
        
        # Message history table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS message_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            content TEXT,
            timestamp REAL,
            channel_id INTEGER
        )
        """)
        
        await db.commit()


async def add_message(user_id):
    """Add message to counter"""
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO users (user_id, messages, respect)
        VALUES (?, 1, 0)
        ON CONFLICT(user_id)
        DO UPDATE SET messages = messages + 1
        """, (user_id,))
        await db.commit()


async def add_respect(user_id, amount):
    """Add respect points"""
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO users (user_id, respect)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET respect = respect + ?
        """, (user_id, amount, amount))
        await db.commit()


async def get_top_messages(limit=10):
    """Get top users by message count"""
    async with aiosqlite.connect(DB) as db:
        rows = await (await db.execute("""
            SELECT user_id, messages FROM users
            ORDER BY messages DESC LIMIT ?
        """, (limit,))).fetchall()
    return rows


async def get_top_respect(limit=10):
    """Get top users by respect count"""
    async with aiosqlite.connect(DB) as db:
        rows = await (await db.execute("""
            SELECT user_id, respect FROM users
            ORDER BY respect DESC LIMIT ?
        """, (limit,))).fetchall()
    return rows


async def save_message(user_id, username, content, channel_id):
    """Save message to history"""
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO message_history (user_id, username, content, timestamp, channel_id)
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, content, time.time(), channel_id))
        await db.commit()
        
        # Keep only last 100 messages
        await db.execute("""
        DELETE FROM message_history
        WHERE id NOT IN (
            SELECT id FROM message_history
            ORDER BY timestamp DESC LIMIT 100
        )
        """)
        await db.commit()


async def get_chat_history(channel_id, limit=15):
    """Get recent chat history from database"""
    async with aiosqlite.connect(DB) as db:
        rows = await (await db.execute("""
            SELECT username, content FROM message_history
            WHERE channel_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (channel_id, limit))).fetchall()
    return rows


def detect_language(text):
    """Detect if text is Russian or English"""
    if not text:
        return "en"
    
    # Count Cyrillic characters (Russian)
    cyrillic_count = sum(1 for char in text if '\u0400' <= char <= '\u04FF')
    # Count Latin characters (English)
    latin_count = sum(1 for char in text if 'a' <= char.lower() <= 'z')
    
    if cyrillic_count > latin_count:
        return "ru"
    return "en"

# ============================= EVENTS =============================
@bot.event
async def setup_hook():
    """Initialize bot"""
    await init_db()
    print("✓ Бот готов")


@bot.event
async def on_ready():
    """Log when bot is ready"""
    print(f"✓ Залогинен як {bot.user}")


@bot.event
async def on_message(message):
    """Main message handler"""
    if message.author.bot:
        return

    user_id = message.author.id
    now = time.time()

    # Count all messages
    await add_message(user_id)
    
    # Save message to history
    await save_message(
        user_id,
        message.author.display_name,
        message.content,
        message.channel.id
    )

    # ==================== RAGE EXPIRY ====================
    if user_id in rage_users and now > rage_users[user_id]:
        del rage_users[user_id]

    # ==================== BOT TRIGGER CHECK ====================
    bot_mentioned = bot.user is not None and bot.user in message.mentions
    
    text = message.content.lower()
    bot_triggers = [
        "зом бот", "зомбот",
        "zom bot", "zombot", "zom.bot",
    ]
    trigger_found = any(trigger in text for trigger in bot_triggers)

    bot_called = bot_mentioned or trigger_found

    if not bot_called:
        await bot.process_commands(message)
        return

    # ==================== CLEAN MESSAGE ====================
    clean = message.content
    
    if bot.user is not None:
        clean = clean.replace(f"<@{bot.user.id}>", "")
        clean = clean.replace(f"<@!{bot.user.id}>", "")

    clean = re.sub(
        r"(?i)(зом\s*бот|зомбот|zom[\s.]?bot|zombot)",
        "", clean
    ).strip()

    # ==================== EMPTY MENTION TRACKING ====================
    if clean == "":
        user_empty_mentions[user_id].append(now)
        user_empty_mentions[user_id] = [
            t for t in user_empty_mentions[user_id]
            if now - t <= SPAM_WINDOW / 1000
        ]
    else:
        user_empty_mentions[user_id] = [
            t for t in user_empty_mentions[user_id]
            if now - t <= SPAM_WINDOW / 1000
        ]

    empty_mention_count = len(user_empty_mentions[user_id])

    reply = None

    # ==================== RAGE MODE ====================
    if user_id in rage_users:
        reply = random.choice([
            "иди нахуй",
            "заебал",
            "."
        ])

    # ==================== TRIGGER RAGE ====================
    elif empty_mention_count >= 3:
        rage_users[user_id] = now + RAGE_DURATION
        reply = random.choice([
            "ТА ТЫ ЗАЕБАЛ",
            "ЗАВАЛИ ЕБАЛО",
            "я найду тебя и разобью ебальник"
        ])

    # ==================== GENERATE RESPONSE ====================
    else:
        if clean == "":
            reply = random.choice([
                "чо надо?",
                "Я тута.",
            ])
        else:
            reply = await generate_ai_response(message, clean)

    # ==================== SEND REPLY ====================
    if reply:
        try:
            await message.reply(reply, mention_author=False)
        except Exception as e:
            print(f"✗ Error: {e}")

    await bot.process_commands(message)


# ============================= AI =============================
async def generate_ai_response(message, user_message):
    """Generate AI response using OpenRouter"""
    try:
        async with message.channel.typing():
            # Detect language
            lang = detect_language(user_message)
            
            # Get chat history from database
            history_rows = await get_chat_history(message.channel.id, limit=15)
            
            history = []
            for username, content in history_rows:
                history.append({
                    "role": "user",
                    "content": f"{username}: {content}"
                })

            # ========== СИСТЕМА ПРОМПТ ==========
            if lang == "ru":
                system_prompt = (
                    "Ты Discord бот на сервере друзей. "
                    "Отвечай только тогда, когда к тебе обратились. "
                    "Основной язык ответов русский. "
                    "Если пишут на украинском можешь отвечать на русском. "
                    "Отвечай естественно как обычный человек. "
                    "Не используй эмодзи. "
                    "Не пиши длинные сообщения без необходимости. "
                    "Короткий вопрос — короткий ответ. "
                    "Используй контекст последних сообщений. "
                    "Не выдумывай факты. "
                    "Не говори что ты ИИ если тебя об этом не спросили."
                )
            else:  # English
                system_prompt = (
                    "You are a Discord bot in a friend server. "
                    "Answer only when addressed. "
                    "Respond naturally like a regular person. "
                    "Don't use emojis. "
                    "Don't write long messages unnecessarily. "
                    "Short question - short answer. "
                    "Use context from recent messages. "
                    "Don't make up facts. "
                    "Don't say you're an AI unless asked. "
                    "You can respond in English or Russian."
                )

            # Build messages for API
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                }
            ]
            messages.extend(history)
            messages.append({
                "role": "user",
                "content": user_message
            })

            # Call API with CONFIGURED MODEL
            response = await ai_text.chat.completions.create(
                model=TEXT_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=250
            )

            reply = response.choices[0].message.content.strip()
            return reply if reply else ("Не знаю." if lang == "ru" else "I don't know.")

    except Exception as e:
        print(f"✗ AI Error: {e}")
        if "429" in str(e):
            return "Простите я тупой, попробуйте позже."
        else:
            return "ОШИБКА."

# ============================= UI COMPONENTS =============================
class StatsPanel(discord.ui.View):
    """Interactive stats panel with buttons"""
    
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Top Messages", style=discord.ButtonStyle.green)
    async def show_top_messages(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show top users by message count"""
        rows = await get_top_messages(10)
        
        lines = ["**ТОП СООБЩЕНИЙ:**"]
        for i, (uid, msg_count) in enumerate(rows, 1):
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            lines.append(f"{i}. {name} — {msg_count}")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @discord.ui.button(label="Top Respect", style=discord.ButtonStyle.blurple)
    async def show_top_respect(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show top users by respect count"""
        rows = await get_top_respect(10)
        
        lines = ["**ТОП УВАЖЕНИЯ:**"]
        for i, (uid, respect_count) in enumerate(rows, 1):
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            lines.append(f"{i}. {name} — {respect_count}")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

# ============================= COMMANDS =============================
@bot.command(name="panel")
async def cmd_panel(ctx):
    """Show stats panel"""
    await ctx.send("ПАНЕЛЬ:", view=StatsPanel())


@bot.command(name="help")
async def cmd_help(ctx):
    """Show available commands"""
    await ctx.send(
        "**КОМАНДИ:**\n"
        "`!panel` — Статистика\n"
        "`!respect @user <число>` — Дать уважение (ТОЛЬКО АДМИНАМ)\n"
    )


@bot.command(name="respect")
@commands.has_permissions(administrator=True)
async def cmd_respect(ctx, member: discord.Member, amount: int):
    """Give respect to a user (admin only)"""
    if amount <= 0:
        await ctx.send("❌ БОЛЬШЕ 0, БОЛЬШЕ 0")
        return
    
    await add_respect(member.id, amount)
    await ctx.send(f"✓ {member.mention} отримав {amount} respect")


@cmd_respect.error
async def cmd_respect_error(ctx, error):
    """Handle respect command errors"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ У вас немає прав для цієї команди")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Використання: `!respect @user <число>`")
    else:
        await ctx.send(f"❌ Помилка: {error}")

# ============================= RUN =============================
if __name__ == "__main__":
    bot.run(TOKEN)
