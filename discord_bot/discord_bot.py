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
    cursor.execute('''CREATE TABLE IF NOT EXISTS server_settings (
        guild_id BIGINT PRIMARY KEY,
        moderation_enabled BOOLEAN DEFAULT 1,
        warn_duration INTEGER DEFAULT 10,
        mute_duration INTEGER DEFAULT 60,
        banned_words TEXT DEFAULT '',
        ignored_global_words TEXT DEFAULT ''
    )''')
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