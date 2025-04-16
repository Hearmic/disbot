import disnake
import asyncio
import yt_dlp
import logging
from disnake.ext import commands

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logging.info(f"Music Cog инициализирован: bot={self.bot}")
        self.queues = {}
        self.FFMPEG_OPTIONS = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn"
        }

    @commands.command(name="play", aliases=["играй", "пуск"])
    async def play(self, ctx, *, query):
        logging.info(f"Команда play вызвана: ctx.guild.id={ctx.guild.id}, ctx.author={ctx.author}, query='{query}'")

        # Проверка: в голосовом ли канале пользователь
        if not ctx.author.voice:
            await ctx.send("Ты не в голосовом канале!")
            logging.warning(f"Пользователь {ctx.author} не в голосовом канале.")
            return

        voice_channel = ctx.author.voice.channel
        logging.info(f"Голосовой канал пользователя: {voice_channel}")

        try:
            if not ctx.voice_client:
                voice_client = await voice_channel.connect()
            else:
                voice_client = ctx.voice_client
            logging.info(f"Подключен к голосовому каналу: {voice_client}")
        except Exception as e:
            logging.error(f"Ошибка при подключении к голосовому каналу: {e}", exc_info=True)
            await ctx.send("Не удалось подключиться к голосовому каналу.")
            return

        result = await self.search_youtube(query)
        if not result or not result[0]:
            await ctx.send("Не удалось найти трек.")
            logging.warning(f"Не удалось найти трек по запросу: '{query}'")
            return

        url, title, video_url = result
        queue = self.get_queue(ctx.guild.id)
        queue.append((url, title, video_url))
        logging.info(f"Трек добавлен в очередь: title='{title}', текущая очередь: {queue}")

        if not voice_client.is_playing():
            logging.info("Воспроизведение не запущено, вызов play_next.")
            await self.play_next(ctx)
        else:
            await ctx.send(f"Добавлено в очередь: [{title}]({video_url})")
            logging.info(f"Трек добавлен в очередь, воспроизведение уже идет.")

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = []
            logging.info(f"Создана новая очередь для guild_id: {guild_id}")
        return self.queues[guild_id]

    async def _extract_info(self, ydl, query):
        """Helper function to run extract_info in a separate thread."""
        return ydl.extract_info(query, download=False)

    async def search_youtube(self, query):
        """Ищет видео и возвращает его URL и название."""
        ydl_opts = {"format": "bestaudio", "noplaylist": True}
        logging.info(f"Поиск на YouTube: query='{query}'")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)
                logging.info(f"Результат поиска info: {info}")
                if info and "entries" in info and info["entries"]:
                    video = info["entries"][0]
                    url = video.get("url")
                    title = video.get("title")
                    webpage_url = video.get("webpage_url")
                    logging.info(f"Найдено видео: url={url}, title={title}, webpage_url={webpage_url}")
                    return url, title, webpage_url
                else:
                    logging.info(f"Видео не найдено по запросу: '{query}'")
                    return None, None, None
        except Exception as e:
            logging.error(f"Ошибка при поиске на YouTube для запроса '{query}': {e}", exc_info=True)
            return None, None, None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member == self.bot.user or not before.channel:
            return
        voice_client = disnake.utils.get(self.bot.voice_clients, guild=member.guild)
        if voice_client:
            logging.info(f"on_voice_state_update: member={member}, before={before.channel}, after={after.channel}, voice_client.channel={voice_client.channel}, len(before.channel.members)={len(before.channel.members) if before.channel else 0}")
            if before.channel and len(before.channel.members) == 1 and member == voice_client.channel.members[0] and after.channel != before.channel:
                logging.info("Бот один в канале, запуск таймера отключения.")
                await asyncio.sleep(10)
                if voice_client and len(voice_client.channel.members) == 1 and voice_client.channel.members[0] == self.bot.user:
                    await voice_client.disconnect()
                    logging.info("Бот отключился, так как в канале никого нет.")

    async def play_next(self, ctx):
        guild_id = ctx.guild.id
        logging.info(f"play_next вызван для guild_id: {guild_id}, voice_client={ctx.voice_client}")
        queue = self.get_queue(guild_id)
        logging.info(f"Текущая очередь для guild_id {guild_id}: {queue}")
        if queue:
            url, title, video_url = queue.pop(0)
            logging.info(f"Из очереди извлечен: url={url}, title={title}, video_url={video_url}")
            try:
                ctx.voice_client.play(
                    disnake.FFmpegPCMAudio(url, **self.FFMPEG_OPTIONS),
                    after=lambda e: self.bot.loop.create_task(self.play_next(ctx))
                )
                await ctx.send(f"Сейчас играет: [{title}]({video_url})")
                logging.info(f"Начато воспроизведение: title={title}, voice_client.is_playing()={ctx.voice_client.is_playing()}")
            except Exception as e:
                logging.error(f"Ошибка при воспроизведении: {e}", exc_info=True)
        else:
            logging.info(f"Очередь пуста для guild_id: {guild_id}, воспроизведение остановлено.")
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
                logging.info(f"Бот отключился от голосового канала в guild_id: {guild_id} из-за пустой очереди.")

        @commands.command()
        async def queue(self, ctx):
            guild_id = ctx.guild.id
            queue = self.get_queue(guild_id)
            logging.info(f"Команда queue вызвана для guild_id: {guild_id}, очередь: {queue}")
            if not queue:
                await ctx.send("Очередь пуста.")
                logging.info(f"Очередь пуста для guild_id: {guild_id}.")
            else:
                queue_list = '\n'.join([f"{i+1}. [{title}]({video_url})" for i, (_, title, video_url) in enumerate(queue)])
                await ctx.send(f"Текущая очередь:\n{queue_list}")
                logging.info(f"Показана очередь для guild_id: {guild_id}:\n{queue_list}")

    @commands.command()
    async def skip(self, ctx):
        logging.info(f"Команда skip вызвана: ctx.guild.id={ctx.guild.id}, voice_client.is_playing()={ctx.voice_client and ctx.voice_client.is_playing()}")
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏭ Пропущено!")
            await self.play_next(ctx)
            logging.info("Трек пропущен, вызов play_next.")
        else:
            await ctx.send("Сейчас ничего не играет.")
            logging.info("Попытка пропустить, но ничего не играет.")

    @commands.command()
    async def remove(self, ctx, index: int):
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        logging.info(f"Команда remove вызвана для guild_id: {guild_id}, index={index}, очередь: {queue}")
        if 1 <= index <= len(queue):
            removed = queue.pop(index - 1)
            await ctx.send(f'❌ Удалено из очереди: {removed[1]}')
            logging.info(f"Трек удален из очереди: title='{removed[1]}', новая очередь: {queue}")
        else:
            await ctx.send("Неверный номер трека!")
            logging.warning(f"Неверный номер трека для удаления: {index}")

    @commands.command()
    async def stop(self, ctx):
        logging.info(f"Команда stop вызвана: ctx.guild.id={ctx.guild.id}, voice_client={ctx.voice_client}")
        if ctx.voice_client:
            ctx.voice_client.stop()
            self.queues[ctx.guild.id] = []
            await ctx.send("⏹️ Музыка остановлена и очередь очищена.")
            logging.info(f"Музыка остановлена и очередь очищена для guild_id: {ctx.guild.id}.")
        else:
            await ctx.send("Бот не подключен к голосовому каналу.")
            logging.info("Попытка остановить, но бот не подключен к голосовому каналу.")

def setup(bot):
    logging.info("Вызвана функция setup для Music Cog.")
    bot.add_cog(Music(bot))
    logging.info("Music Cog добавлен в бота.")
