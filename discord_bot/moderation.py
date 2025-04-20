
import re
import datetime
import asyncio
import disnake
from disnake.ext import commands
import emoji
import logging
import sqlite3

GLOBAL_BANNED_WORDS = ["пидор", "пидорас", "педераст", "пидераст", "пидрила", "педик", "гомик", "гомосек",
                        "нигер", "негр","кацап", "москаль", "русня","хохол","жид","хач",
                        "глиномес", "чурка"]
CAPS_THRESHOLD = 0.7
MAX_EMOJIS = 10
SPAM_INTERVAL = 3
FLOOD_THRESHOLD = 5
MUTE_MINUTES = 5
URL_REGEX = r"https?://\S+"

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
        self.user_message_cache = {}

    def setup_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_settings (
                guild_id INTEGER PRIMARY KEY,
                banned_words TEXT,
                moderation_enabled BOOLEAN DEFAULT TRUE,
                warn_duration INTEGER DEFAULT 10,
                mute_duration INTEGER DEFAULT 60,
                check_links BOOLEAN DEFAULT TRUE,
                check_caps BOOLEAN DEFAULT TRUE,
                check_emojis BOOLEAN DEFAULT TRUE,
                check_spam_and_flood BOOLEAN DEFAULT TRUE,
                ignored_global_words TEXT DEFAULT '',
                infractions_valid_days INTEGER DEFAULT 30,
            )
            CREATE TABLE IF NOT EXISTS infractions (
                user_id BIGINT,
                guild_id BIGINT,
                message TEXT,
                timestamp TEXT
            );
        """)
        conn.commit()
        conn.close()

    def get_db_connection(self):
        return sqlite3.connect(self.db_path)

    def normalize_text(self, text):
        return re.sub(r"[^а-яa-z0-9\s]", "", text.lower())

    async def check_banned_words(self, message, banned_words):
        content = self.normalize_text(message.content)
        for word in banned_words:
            if word in content:
                return f"Запрещённое слово: `{word}`"
        return None

    async def check_links(self, message):
        if re.search(URL_REGEX, message.content):
            return "Отправка ссылок запрещена"
        return None

    async def check_caps(self, message):
        if len(message.content) < 10:
            return None
        letters = [c for c in message.content if c.isalpha()]
        if letters and sum(1 for c in letters if c.isupper()) / len(letters) > CAPS_THRESHOLD:
            return "Слишком много ЗАГЛАВНЫХ букв"
        return None

    async def check_emojis(self, message):
        emoji_count = sum(1 for c in message.content if c in emoji.EMOJI_DATA)
        if emoji_count > MAX_EMOJIS:
            return f"Слишком много эмодзи (макс. {MAX_EMOJIS})"
        return None
    
    async def check_spam_and_flood(self, message):
        now = datetime.datetime.utcnow().timestamp()
        uid = message.author.id

        if uid not in self.user_message_cache:
            self.user_message_cache[uid] = []

        self.user_message_cache[uid] = [
            (ts, msg) for ts, msg in self.user_message_cache[uid] if now - ts < 5
        ]
        self.user_message_cache[uid].append((now, message.content))

        # Повтор одного и того же
        messages = [msg for ts, msg in self.user_message_cache[uid]]
        if messages.count(message.content) > 2:
            return "Повторяющиеся сообщения (спам)"

        # Флуд
        if len(self.user_message_cache[uid]) > FLOOD_THRESHOLD:
            return "Слишком много сообщений за короткое время (флуд)"

        return None

    async def check_banned_words(self, message, banned_words):
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

    def get_user_infractions(user_id: int, guild_id: int, db_path: str = "database.db") -> List[Tuple[str, str]]:
        """
        Возвращает список нарушений пользователя в гильдии.
        
        :param user_id: ID пользователя (Discord user ID)
        :param guild_id: ID гильдии
        :param db_path: Путь к SQLite-базе данных
        :return: Список кортежей (message, timestamp)
        """
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT message, timestamp FROM infractions
                WHERE user_id = ? AND guild_id = ?
                ORDER BY timestamp DESC
            """, (user_id, guild_id))

            results = cursor.fetchall()
            conn.close()
            return results

        except Exception as e:
            logging.error(f"Ошибка при получении нарушений: {e}", exc_info=True)
            return []

    async def handle_violation(self, message, reason, conn=None, cursor=None, mute_minutes=MUTE_MINUTES):
        try:
            await message.delete()
        except disnake.Forbidden:
            pass
        # Логирование (если подключена БД)
        if conn and cursor:
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor.execute(
                "INSERT INTO infractions (user_id, guild_id, message, timestamp) VALUES (?, ?, ?, ?)",
                (message.author.id, message.guild.id, message.content, timestamp)
            )
            conn.commit()
        infractions = self.get_user_infractions(message.author.id, message.guild.id)
        await self.ensure_ban_system(message.guild)
        
        if len(infractions) <= 2:
            # Замутить пользователя за первое и второе нарушение
            muted_role = disnake.utils.get(message.guild.roles, name="Muted")
            if muted_role:
                await message.author.add_roles(muted_role)
                await message.author.send(f"Вы замьючены на {mute_minutes} минут из-за нарушения правил сервера.\nПричина: {reason}")
        else:
            logging.error("Не удалось найти роль 'Muted' для мута пользователя.")
        if len(infractions) >= 3:
            # Забанить пользователя за третье нарушение
            banned_role = disnake.utils.get(message.guild.roles, name="Banned")
            if banned_role:
                await message.author.add_roles(banned_role)
                await message.author.send(f"Вы забанены из-за нарушения правил сервера.\nПричина: {reason}")
        else:
            logging.error("Не удалось найти роль 'Banned' для бана пользователя.")


    async def ensure_ban_system(guild: disnake.Guild):
        """
        Проверяет наличие канала для апелляций, а также создает роли 'Banned' и 'Muted',
        если они отсутствуют на сервере.
        """
        # Проверка или создание роли 'Banned'
        banned_role = disnake.utils.get(guild.roles, name="Banned")
        if not banned_role:
            try:
                banned_role = await guild.create_role(name="Banned", reason="Автоматическое создание роли для забаненных пользователей.")
                logging.info(f"На сервере '{guild.name}' создана роль 'Banned'.")
                for channel in guild.channels:
                    try:
                        await channel.set_permissions(banned_role, send_messages=False, add_reactions=False, connect=False, speak=False)
                    except disnake.Forbidden:
                        logging.warning(f"Нет прав для настройки разрешений в канале '{channel.name}' на сервере '{guild.name}'.")
                    except Exception as e:
                        logging.error(f"Ошибка при настройке разрешений для роли 'Banned' в канале '{channel.name}' на сервере '{guild.name}': {e}")
            except disnake.Forbidden:
                logging.error(f"Нет прав для создания роли 'Banned' на сервере '{guild.name}'.")
            except Exception as e:
                logging.error(f"Ошибка при создании роли 'Banned' на сервере '{guild.name}': {e}")

        # Проверка или создание роли 'Muted'
        muted_role = disnake.utils.get(guild.roles, name="Muted")
        if not muted_role:
            try:
                muted_role = await guild.create_role(name="Muted", reason="Автоматическое создание роли для замьюченных пользователей.")
                logging.info(f"На сервере '{guild.name}' создана роль 'Muted'.")
                # Настройка прав для роли 'Muted' по умолчанию
                for channel in guild.channels:
                    try:
                        await channel.set_permissions(muted_role, send_messages=False, add_reactions=False, connect=False, speak=False)
                    except disnake.Forbidden:
                        logging.warning(f"Нет прав для настройки разрешений в канале '{channel.name}' на сервере '{guild.name}'.")
                    except Exception as e:
                        logging.error(f"Ошибка при настройке разрешений для роли 'Muted' в канале '{channel.name}' на сервере '{guild.name}': {e}")
            except disnake.Forbidden:
                logging.error(f"Нет прав для создания роли 'Muted' на сервере '{guild.name}'.")
            except Exception as e:
                logging.error(f"Ошибка при создании роли 'Muted' на сервере '{guild.name}': {e}")

        # Проверка или создание канала 'апелляции'
        appeal_channel = disnake.utils.get(guild.text_channels, name="апелляции")
        if not appeal_channel:
            try:
                overwrites = {
                    guild.default_role: disnake.PermissionOverwrite(read_messages=False),
                    banned_role: disnake.PermissionOverwrite(read_messages=True, send_messages=True) if banned_role else disnake.PermissionOverwrite(read_messages=False, send_messages=False),
                    muted_role: disnake.PermissionOverwrite(read_messages=False, send_messages=False) if muted_role else disnake.PermissionOverwrite(read_messages=False, send_messages=False),
                    guild.me: disnake.PermissionOverwrite(read_messages=True, send_messages=True)  # Разрешения для бота
                }
                appeal_channel = await guild.create_text_channel("апелляции", overwrites=overwrites, reason="Автоматическое создание канала для апелляций.")
                logging.info(f"На сервере '{guild.name}' создан канал 'апелляции'.")
                await appeal_channel.send(
                    "**Этот канал предназначен для подачи апелляций на бан.**\n"
                    "Если вы были забанены, вы можете описать здесь свою ситуацию для рассмотрения администрацией."
                )
            except disnake.Forbidden:
                logging.error(f"Нет прав для создания канала 'апелляции' на сервере '{guild.name}'.")
            except Exception as e:
                logging.error(f"Ошибка при создании канала 'апелляции' на сервере '{guild.name}': {e}")
        elif banned_role and appeal_channel.overwrites_for(banned_role).send_messages is False:
            # Обновление прав для роли 'Banned', если канал уже существует
            try:
                await appeal_channel.set_permissions(banned_role, read_messages=True, send_messages=True)
            except disnake.Forbidden:
                logging.warning(f"Нет прав для обновления разрешений роли 'Banned' в канале 'апелляции' на сервере '{guild.name}'.")
            except Exception as e:
                logging.error(f"Ошибка при обновлении разрешений роли 'Banned' в канале 'апелляции' на сервере '{guild.name}': {e}")
        elif muted_role and (appeal_channel.overwrites_for(muted_role).read_messages is not True or appeal_channel.overwrites_for(muted_role).send_messages is not True):
            # Обновление прав для роли 'Muted', если канал уже существует
            try:
                await appeal_channel.set_permissions(muted_role, read_messages=True, send_messages=True)
            except disnake.Forbidden:
                logging.warning(f"Нет прав для обновления разрешений роли 'Muted' в канале 'апелляции' на сервере '{guild.name}'.")
            except Exception as e:
                logging.error(f"Ошибка при обновлении разрешений роли 'Muted' в канале 'апелляции' на сервере '{guild.name}': {e}")

    @commands.Cog.listener()
    async def on_guid_join(self):
        await self.ensure_ban_system()

    @commands.Cog.listener()
    async def on_message(self, message):
        logging.info(f"on_message вызван: guild_id={message.guild.id if message.guild else None}, author={message.author}")
        if message.author.bot or not message.guild:
            logging.debug(f"Сообщение от бота или не в гильдии, пропуск: author={message.author}, guild={message.guild}")
            return

        conn = self.get_db_connection()
        cursor = conn.cursor()
        logging.debug(f"Выполняется запрос к БД для guild_id: {message.guild.id}")
        cursor.execute("SELECT moderation_enabled, banned_words, check_links, check_caps, check_emojis, check_spam_and_flood FROM server_settings WHERE guild_id = ?", (message.guild.id,))
        result = cursor.fetchone()
        logging.debug(f"Результат запроса к БД для guild_id {message.guild.id}: {result}")
        conn.close()

        moderation_enabled = result[0]
        banned_words_str = result[1]
        check_links = result[2]
        check_caps = result[3]
        check_emojis = result[4]
        check_spam = result[5]

        if not result:
            logging.debug(f"Нет настроек для guild_id: {message.guild.id}, пропуск.")
            return
        
        local_banned_words = banned_words_str.split(',') if banned_words_str else []
        banned_words = local_banned_words + GLOBAL_BANNED_WORDS
        logging.debug(f"Активные запрещенные слова для guild_id {message.guild.id}: {banned_words}")

        if moderation_enabled:
            logging.debug(f"Проверка запрещенных слов для guild_id {message.guild.id}")
            check_banned_words_result = await self.check_banned_words(message, banned_words)
            await self.handle_violation(message, check_banned_words_result)

        if check_links:
            logging.debug(f"Проверка на ссылки для guild_id {message.guild.id}")
            check_links_result = await self.check_links(message)
            await self.handle_violation(message, check_links_result)

        if check_caps:
            logging.debug(f"Проверка на заглавные буквы для guild_id {message.guild.id}")
            check_caps_result = await self.check_caps(message)
            await self.handle_violation(message, check_caps_result)

        if check_emojis:
            logging.debug(f"Проверка на эмодзи для guild_id {message.guild.id}")
            check_emojis_result = await self.check_emojis(message)
            await self.handle_violation(message, check_emojis_result)

        if check_spam:
            logging.debug(f"Проверка на спам для guild_id {message.guild.id}")
            check_spam_result = await self.check_spam_and_flood(message)
            await self.handle_violation(message, check_spam_result)

        logging.debug(f"Проверки для user_id {message.author.id} в сервере {ctx.guild.name} guild_id {message.guild.id}) завершены.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def moderation_toggle(self, ctx, state: str):
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
        logging.info(f"Автомодерация {'включена' if enabled else 'выключена'} для сервера {ctx.guild.name} guild_id {ctx.guild.id}.")

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

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def check_caps_toggle(self, ctx, state: str):
        if state.lower() not in ["on", "off"]:
            await ctx.send("Используйте 'on' или 'off'")
            return

        enabled = state.lower() == "on"
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO server_settings (guild_id, check_caps)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET check_caps = excluded.check_caps
        """, (ctx.guild.id, enabled))
        conn.commit()
        conn.close()
        await ctx.send(f"Проверка заглавных букв {'включена' if enabled else 'выключена'}.")
        logging.info(f"Проверка заглавных букв {'включена' if enabled else 'выключена'} для сервера {ctx.guild.name} guild_id {ctx.guild.id}.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def check_emojis_toggle(self, ctx, state: str):
        if state.lower() not in ["on", "off"]:
            await ctx.send("Используйте 'on' или 'off'")
            return

        enabled = state.lower() == "on"
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO server_settings (guild_id, check_emojis)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET check_emojis = excluded.check_emojis
        """, (ctx.guild.id, enabled))
        conn.commit()
        conn.close()
        await ctx.send(f"Проверка эмодзи {'включена' if enabled else 'выключена'}.")
        logging.info(f"Проверка эмодзи {'включена' if enabled else 'выключена'} для сервера {ctx.guild.name} guild_id {ctx.guild.id}.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def check_spam_toggle(self, ctx, state: str):
        if state.lower() not in ["on", "off"]:
            await ctx.send("Используйте 'on' или 'off'")
            return

        enabled = state.lower() == "on"
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO server_settings (guild_id, check_spam)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET check_spam = excluded.check_spam
        """, (ctx.guild.id, enabled))
        conn.commit()
        conn.close()
        await ctx.send(f"Проверка на спам {'включена' if enabled else 'выключена'}.")
        logging.info(f"Проверка на спам {'включена' if enabled else 'выключена'} для сервера {ctx.guild.name} guild_id {ctx.guild.id}.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def check_links_toggle(self, ctx, state: str):
        if state.lower() not in ["on", "off"]:
            await ctx.send("Используйте 'on' или 'off'")
            return

        enabled = state.lower() == "on"
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO server_settings (guild_id, check_links)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET check_links = excluded.check_links
        """, (ctx.guild.id, enabled))
        conn.commit()
        conn.close()
        await ctx.send(f"Проверка на ссылки {'включена' if enabled else 'выключена'}.")
        logging.info(f"Проверка на ссылки {'включена' if enabled else 'выключена'} для сервера {ctx.guild.name} guild_id {ctx.guild.id}.") 

def setup(bot):
    bot.add_cog(Moderation(bot))