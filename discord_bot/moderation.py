from unidecode import unidecode
import disnake
from disnake.ext import commands
import sqlite3
import logging

OBFUSCATION_MAP = {
    "0": "о", "1": "и", "2": "з", "3": "з", "4": "а", "5": "с", "6": "б", "7": "т", "8": "в", "9": "г",
    "@": "а", "$": "с", "!": "и", "|": "и", "€": "е", "₽": "р", " ": "",
    "`": "", "'": "", "‘": "", "*": "", "~": "", "^": "", "&": "", "#": "", "?": "", "%": "", "+": "",
    ".": "", ",": "", "-": "", "_": "", "=": "", "(": "", ")": "", "[": "", "]": "", "{": "", "}": "",
    "<": "", ">": "", "/": "", "\\": "", '"': "",

    "a": "а", "b": "в", "c": "с", "e": "е", "f": "ф", "g": "г", "h": "н", "i": "и", "j": "й", "k": "к", "l": "л",
    "m": "м", "n": "н", "o": "о", "p": "р", "q": "к", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в", "w": "ш",
    "x": "х", "y": "у", "z": "з",

    "А": "а", "В": "в", "Е": "е", "К": "к", "М": "м", "Н": "н", "О": "о", "Р": "р", "С": "с", "Т": "т", "Х": "х"
}

GLOBAL_BANNED_WORDS = ["пидор", "пидорас", "педераст", "пидераст", "пидрила", "педик", "гомик", "гомосек",
                        "нигер", "негр","кацап", "москаль", "русня","хохол","жид","хач",
                        "глиномес", "чурка"]

class Moderation(commands.Cog):
    def __init__(self, bot):
        logging.info("Вызов __init__ для Moderation")
        self.bot = bot
        logging.info(f"Bot в __init__: {self.bot}")
        self.db_path = "data/bot.db"
        logging.info(f"DB path в __init__: {self.db_path}")
        try:
            self.setup_database()
            logging.info("setup_database успешно завершен")
        except Exception as e:
            logging.error(f"Ошибка в setup_database: {e}", exc_info=True)
        logging.info("Выход из __init__ для Moderation")

    def setup_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_settings (
                guild_id INTEGER PRIMARY KEY,
                banned_words TEXT,
                moderation_enabled BOOLEAN DEFAULT FALSE
            )
        """)
        conn.commit()
        conn.close()

    def get_db_connection(self):
        return sqlite3.connect(self.db_path)

    def normalize_text(self, text: str) -> str:
        """Удаляет повторы и заменяет зашифрованные символы"""
        text = unidecode(text).lower()
        result = ""
        last_char = ""
        repeat_count = 0

        for char in text:
            norm_char = OBFUSCATION_MAP.get(char, char)
            if norm_char == last_char:
                repeat_count += 1
                if repeat_count < 3:
                    result += norm_char
            else:
                result += norm_char
                last_char = norm_char
                repeat_count = 1
        return result

    @commands.Cog.listener()
    async def on_message(self, message):
        logging.info(f"on_message вызван: guild_id={message.guild.id if message.guild else None}, author={message.author}")
        if message.author.bot or not message.guild:
            logging.debug(f"Сообщение от бота или не в гильдии, пропуск: author={message.author}, guild={message.guild}")
            return

        conn = self.get_db_connection()
        cursor = conn.cursor()
        logging.debug(f"Выполняется запрос к БД для guild_id: {message.guild.id}")
        cursor.execute("SELECT moderation_enabled, banned_words FROM server_settings WHERE guild_id = ?", (message.guild.id,))
        result = cursor.fetchone()
        logging.debug(f"Результат запроса к БД для guild_id {message.guild.id}: {result}")
        conn.close()

        if not result or not result[0]:
            logging.debug(f"Модерация выключена или нет настроек для guild_id: {message.guild.id}, пропуск.")
            return

        moderation_enabled = result[0]
        banned_words_str = result[1]
        local_banned_words = banned_words_str.split(',') if banned_words_str else []
        banned_words = local_banned_words + GLOBAL_BANNED_WORDS
        logging.debug(f"Активные запрещенные слова для guild_id {message.guild.id}: {banned_words}")

        normalized_content = self.normalize_text(message.content)
        logging.debug(f"Нормализованное содержимое сообщения: '{normalized_content}'")

        for word in banned_words:
            if word in normalized_content:
                logging.warning(f"Обнаружено запрещенное слово '{word}' в сообщении от {message.author} в guild_id {message.guild.id}.")
                try:
                    await message.delete()
                    logging.info(f"Сообщение от {message.author} удалено.")
                except disnake.Forbidden:
                    logging.warning(f"Нет прав на удаление сообщения от {message.author} в guild_id {message.guild.id}.")
                except Exception as e:
                    logging.error(f"Ошибка при удалении сообщения от {message.author}: {e}", exc_info=True)

                appeal_channel = disnake.utils.get(message.guild.channels, name="appeal")
                if not appeal_channel:
                    try:
                        appeal_channel = await message.guild.create_text_channel("appeal")
                        logging.info(f"Создан канал 'appeal' в guild_id {message.guild.id}.")
                    except disnake.Forbidden:
                        logging.warning(f"Нет прав на создание канала 'appeal' в guild_id {message.guild.id}.")
                    except Exception as e:
                        logging.error(f"Ошибка при создании канала 'appeal': {e}", exc_info=True)
                else:
                    logging.debug(f"Канал 'appeal' уже существует в guild_id {message.guild.id}: {appeal_channel.id}")

                banned_role = disnake.utils.get(message.guild.roles, name="Banned")
                if not banned_role:
                    try:
                        banned_role = await message.guild.create_role(name="Banned")
                        logging.info(f"Создана роль 'Banned' в guild_id {message.guild.id}.")
                    except disnake.Forbidden:
                        logging.warning(f"Нет прав на создание роли 'Banned' в guild_id {message.guild.id}.")
                    except Exception as e:
                        logging.error(f"Ошибка при создании роли 'Banned': {e}", exc_info=True)
                else:
                    logging.debug(f"Роль 'Banned' уже существует в guild_id {message.guild.id}: {banned_role.id}")

                try:
                    await message.author.add_roles(banned_role)
                    logging.info(f"Пользователю {message.author} добавлена роль 'Banned'.")
                except disnake.Forbidden:
                    logging.warning(f"Нет прав на добавление роли 'Banned' пользователю {message.author} в guild_id {message.guild.id}.")
                except Exception as e:
                    logging.error(f"Ошибка при добавлении роли 'Banned' пользователю {message.author}: {e}", exc_info=True)

                try:
                    await message.channel.send(f"{message.author.mention} получил ограничение и доступ только к каналу {appeal_channel.mention}.")
                    logging.info(f"Отправлено сообщение о бане пользователю {message.author} в канал {message.channel.id}.")
                except disnake.Forbidden:
                    logging.warning(f"Нет прав на отправку сообщения в канал {message.channel.id} в guild_id {message.guild.id}.")
                except Exception as e:
                    logging.error(f"Ошибка при отправке сообщения о бане пользователю {message.author}: {e}", exc_info=True)
                return

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_moderation(self, ctx, state: str):
        if state.lower() not in ["on", "off"]:
            await ctx.send("Используйте 'on' или 'off'")
            return

        enabled = state.lower() == "on"
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO server_settings (guild_id, moderation_enabled)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET moderation_enabled = excluded.moderation_enabled
        """, (ctx.guild.id, enabled))
        conn.commit()
        conn.close()
        await ctx.send(f"Автомодерация {'включена' if enabled else 'выключена'}.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_banned_words(self, ctx, *, words: str):
        """Добавление запрещенных слов на сервере"""
        word_list = [word.strip().lower() for word in words.split(',') if word.strip()]
        words_cleaned = ','.join(word_list)
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO server_settings (guild_id, banned_words)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET banned_words = excluded.banned_words
        """, (ctx.guild.id, words_cleaned))
        conn.commit()
        conn.close()
        await ctx.send(f"Запрещённые слова обновлены: {', '.join(word_list)}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def show_banned_words(self, ctx):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT banned_words FROM server_settings WHERE guild_id = ?", (ctx.guild.id,))
        result = cursor.fetchone()
        conn.close()

        local_words = result[0].split(',') if result and result[0] else []
        local_display = ', '.join(local_words) if local_words else "нет"
        global_display = ', '.join(GLOBAL_BANNED_WORDS)

        await ctx.send(f"**Глобальные запрещённые слова:** {global_display}\n**Локальные запрещённые слова:** {local_display}")

    async def ensure_ban_system(self, guild: disnake.Guild):
        banned_role = disnake.utils.get(guild.roles, name="Banned")
        if not banned_role:
            banned_role = await guild.create_role(name="Banned")

        appeal_channel = disnake.utils.get(guild.channels, name="appeal")
        if not appeal_channel:
            appeal_channel = await guild.create_text_channel("appeal")

        for channel in guild.channels:
            if channel.name == "appeal":
                continue

            perms = disnake.PermissionOverwrite()
            perms.read_messages = False
            perms.send_messages = False
            await channel.set_permissions(banned_role, overwrite=perms)

        perms = disnake.PermissionOverwrite()
        perms.read_messages = True
        perms.send_messages = True
        await appeal_channel.set_permissions(banned_role, overwrite=perms)
    
def setup(bot):
    bot.add_cog(Moderation(bot))