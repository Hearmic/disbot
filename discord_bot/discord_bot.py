import disnake
import sqlite3
import os
import logging
from dotenv import load_dotenv
from disnake.ext import commands

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)

# Проверяем opus
if not disnake.opus.is_loaded():
    try:
        opus_path = os.getenv('OPUS_PATH')
        logging.info(f"Путь к Opus: {opus_path}")
        disnake.opus.load_opus(opus_path)
    except Exception as e:
        logging.error(f"Ошибка загрузки Opus: {e}")

# Конфигурация бота
intents = disnake.Intents.all()
intents.message_content = True
bot = commands.Bot(command_prefix=['!', 'бобик '], intents=intents)

# Подключение к БД
conn = sqlite3.connect('data/bot.db')
cursor = conn.cursor()

async def load_cogs():
    for filename in os.listdir('.'):
        if filename.endswith('.py') and filename != 'discord_bot.py':
            cog_name = filename[:-3]
            logging.info(f"Попытка загрузить ког: {cog_name}")
            try:
                bot.load_extension(cog_name)
                logging.info(f"Загружен ког: {cog_name}")
            except Exception as e:
                logging.error(f"Ошибка загрузки кога {cog_name}: {e}", exc_info=True)

@bot.event
async def on_ready():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bans (
        guild_id BIGINT,
        user_id BIGINT,
        username TEXT,
        reason TEXT,
        PRIMARY KEY (guild_id, user_id)
    )
    """)
    cursor.execute('''CREATE TABLE IF NOT EXISTS server_settings (
        guild_id BIGINT PRIMARY KEY,
        moderation_enabled BOOLEAN DEFAULT 1,
        warn_duration INTEGER DEFAULT 10,
        mute_duration INTEGER DEFAULT 60,
        banned_words TEXT DEFAULT '',
        ignored_global_words TEXT DEFAULT ''
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS infractions (
        user_id BIGINT,
        guild_id BIGINT,
        message TEXT,
        timestamp TEXT
    );''')
    conn.commit()
    await load_cogs()
    await bot._sync_application_commands()
    logging.info(f'{bot.user.name} готов!')

# Общие команды
@bot.command()
async def ping(ctx):
    await ctx.reply(f'Понг! {round(bot.latency * 1000)} мс')

@bot.command()
async def info(ctx):
    """Показывает список всех команд бота."""
    commands_list = "\n".join([f"`{command.name}` - {command.help}" for command in bot.commands])
    await ctx.send(f"**Список команд:**\n{commands_list}")

# Команды администраторов
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: disnake.Member, *, reason: str = "Причина не указана"):
    try:
        if member.id == bot.user.id:
            await ctx.send("Невозможно забанить этого бота!")
            return
        if member.top_role > ctx.guild.me.top_role:
            await ctx.send("Невозможно забанить этого пользователя!")
            return
        if member.id == ctx.author.id:
            await ctx.send("Невозможно забанить самого себя!")
            return
        await member.ban(reason=reason)
        cursor.execute("INSERT INTO bans (user_id, username, reason) VALUES (?, ?, ?)", (member.id, str(member), reason))
        await ctx.send(f"{member.mention} был забанен. Причина: {reason}. ID: {member.id}")
    except disnake.ext.commands.errors.MemberNotFound:
        await ctx.send("Пользователь не найден. Пожалуйста, проверьте правильность упоминания.")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    """Разбанивает пользователя по его ID и снимает роль Banned."""
    
    guild = ctx.guild
    
    try:
        # Ищем пользователя по ID в списке забаненных
        banned_user = await guild.fetch_ban(user_id)
        
        # Получаем роль Banned
        banned_role = disnake.utils.get(guild.roles, name="Banned")
        if not banned_role:
            await ctx.send("Роль Banned не найдена.")
            return
        
        # Получаем аккаунт пользователя
        member = disnake.utils.get(guild.members, id=user_id)

        # Удаляем роль Banned, если она есть
        if member:
            if banned_role in member.roles:
                await member.remove_roles(banned_role)
                await ctx.send(f"Роль Banned была удалена с пользователя {banned_user.user.mention}.")
            else:
                await ctx.send(f"У пользователя {banned_user.user.mention} нет роли Banned.")
        # Разбаниваем пользователя
            await guild.unban(banned_user.user)
            await ctx.send(f"{banned_user.user.mention} был разбанен.")
    
    except disnake.NotFound:
        await ctx.send(f"Пользователь с ID {user_id} не найден в списке забаненных.")

@bot.command()
async def banned(ctx):
    """Показывает список забаненных пользователей."""
    cursor.execute("SELECT user_id, reason FROM bans")
    bans = cursor.fetchall()
    if bans:
        msg = "**Забаненные пользователи:**\n" + "\n".join(
            [f"🔹 {b[1]} (ID: {b[0]}) — Причина: {b[2]}" for b in bans]
        )
    else:
        msg = "Список забаненных пуст."
    await ctx.send(msg)

@bot.slash_command(name='ban', description='Бан пользователя')
async def slash_ban(interaction, member: disnake.Member, reason: str = "Причина не указана"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("У тебя нет прав использовать эту команду.", ephemeral=True)
        return
    await member.ban(reason=reason)
    cursor.execute("INSERT INTO bans (user_id, reason) VALUES (?, ?)", (member.id, reason))
    conn.commit()
    await interaction.response.send_message(f"{member.mention} был забанен. Причина: {reason}")

@bot.slash_command(name='unban', description='Разбан пользователя')
async def slash_unban(interaction, user_id: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("У тебя нет прав использовать эту команду.", ephemeral=True)
        return
    user = await bot.fetch_user(user_id)
    await interaction.guild.unban(user)
    cursor.execute("DELETE FROM bans WHERE user_id = ?", (user_id,))
    conn.commit()
    await interaction.response.send_message(f"{user.mention} был разбанен.")

@bot.slash_command(name='banned', description='Показывает список забаненных пользователей')
async def slash_banned(interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("У тебя нет прав использовать эту команду.", ephemeral=True)
        return
    cursor.execute("SELECT user_id, reason FROM bans")
    bans = cursor.fetchall()
    if bans:
        msg = "Забаненные пользователи:\n" + "\n".join([f"ID: {b[0]}, Причина: {b[1]}" for b in bans])
    else:
        msg = "Список забаненных пуст."
    await interaction.response.send_message(msg)

@bot.slash_command()
async def user(interaction, member: disnake.Member):
    await interaction.response.send_message(f"Тег пользователя: {member}\nID: {member.id}")

# Запуск бота


if __name__ == "__main__":
    TOKEN = os.getenv('TOKEN')
    try:
        bot.run(TOKEN)
    except Exception as e:
        logging.exception(f"Произошла ошибка: {e}")