import disnake
import asyncio
import yt_dlp
import logging
from disnake.ext import commands

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logging.info(f"Music Cog инициализирован: bot={self.bot.user.name if self.bot.user else 'None'}")
        self.queues = {}
        self.FFMPEG_OPTIONS = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn"
        }

    @commands.command(name="play", aliases=["играй", "пуск"])
    async def play(self, ctx, *, query):
        logging.info(f"Команда play вызвана: guild_id={ctx.guild.id}, author={ctx.author.name}, query='{query}'")

        if not ctx.author.voice:
            await ctx.send("Ты не в голосовом канале!")
            logging.warning(f"Пользователь {ctx.author.name} не в голосовом канале.")
            return

        voice_channel = ctx.author.voice.channel
        logging.info(f"Голосовой канал: {voice_channel.name}")

        try:
            if not ctx.voice_client:
                voice_client = await voice_channel.connect()
                logging.info(f"Подключен к голосовому каналу: {voice_client.channel.name}")
            elif ctx.voice_client.channel != voice_channel:
                await ctx.voice_client.move_to(voice_channel)
                logging.info(f"Перемещен в голосовой канал: {voice_client.channel.name}")
            else:
                voice_client = ctx.voice_client
        except Exception as e:
            logging.error(f"Ошибка подключения к голосовому каналу: {e}", exc_info=True)
            await ctx.send("Не удалось подключиться к голосовому каналу.")
            return

        searching_message = await ctx.send(f"🔎 Поиск трека: `{query}`...")
        result = await self.search_youtube(query)
        await searching_message.delete()
        if not result:
            await ctx.send("Не удалось найти трек.")
            logging.warning(f"Не удалось найти трек по запросу: '{query}'")
            return

        url, title, video_url = result
        queue = self.get_queue(ctx.guild.id)
        queue.append((url, title, video_url))
        logging.info(f"Трек добавлен в очередь: title='{title}', размер очереди: {len(queue)}")

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

    async def search_youtube(self, query):
        """Ищет видео и возвращает его URL, название и URL страницы."""
        ydl_opts = {"format": "bestaudio", "noplaylist": True}
        logging.info(f"Поиск на YouTube: query='{query}'")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, f"ytsearch:{query}", download=False)
                if info and "entries" in info and info["entries"]:
                    video = info["entries"][0]
                    url = video.get("url")
                    if not url:
                        formats = video.get("formats")
                        if formats:
                            url = formats[0].get("url")
                    title = video.get("title")
                    webpage_url = video.get("webpage_url")
                    logging.info(f"Найдено видео: title='{title}', url='{webpage_url}'")
                    return url, title, webpage_url
                else:
                    logging.info(f"Видео не найдено по запросу: '{query}'")
                    return None
        except Exception as e:
            logging.error(f"Ошибка поиска на YouTube для '{query}': {e}", exc_info=True)
            return None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member == self.bot.user or not before.channel:
            return
        voice_client = disnake.utils.get(self.bot.voice_clients, guild=member.guild)
        if voice_client and voice_client.channel == before.channel:
            if len(before.channel.members) == 1 and member == self.bot.user and not after.channel:
                logging.info("Бот покинул голосовой канал.")
                if guild_id := voice_client.guild.id in self.queues:
                    self.queues[guild_id] = []
                    logging.info(f"Очередь очищена для guild_id: {guild_id} после выхода бота.")
                return
            elif len(before.channel.members) == 1 and after.channel != before.channel and member != self.bot.user:
                logging.info("Бот один в канале, запуск таймера отключения.")
                await asyncio.sleep(10)
                if voice_client and len(voice_client.channel.members) == 1 and voice_client.channel.members[0] == self.bot.user:
                    await voice_client.disconnect()
                    logging.info("Бот отключился, так как в канале никого нет.")

    async def play_next(self, ctx):
        guild_id = ctx.guild.id
        logging.info(f"play_next вызван: guild_id={guild_id}, voice_client={'подключен' if ctx.voice_client and ctx.voice_client.is_connected() else 'не подключен'}")
        queue = self.get_queue(guild_id)
        logging.info(f"Текущая очередь (размер: {len(queue)}): {queue}")
        if queue:
            url, title, video_url = queue.pop(0)
            logging.info(f"Воспроизведение: title='{title}', url='{video_url}'")
            try:
                if ctx.voice_client is None or not ctx.voice_client.is_connected():
                    logging.warning("Бот не подключен к голосовому каналу, воспроизведение невозможно.")
                    return
                source = disnake.FFmpegPCMAudio(url, **self.FFMPEG_OPTIONS)
                ctx.voice_client.play(source, after=lambda e: self.bot.loop.create_task(self.play_next(ctx)))
                await ctx.send(f"Сейчас играет: [{title}]({video_url})")
                logging.info(f"Начато воспроизведение: title='{title}'")
            except Exception as e:
                logging.error(f"Ошибка при воспроизведении: {e}", exc_info=True)
        else:
            logging.info(f"Очередь пуста для guild_id: {guild_id}, остановка.")
            if ctx.voice_client and ctx.voice_client.is_connected():
                await ctx.voice_client.disconnect()
                logging.info(f"Бот отключился от голосового канала в guild_id: {guild_id} из-за пустой очереди.")

    @commands.command()
    async def queue(self, ctx):
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        logging.info(f"Команда queue вызвана: guild_id={guild_id}, размер очереди: {len(queue)}")
        if not queue:
            await ctx.send("Очередь пуста.")
            logging.info(f"Очередь пуста для guild_id: {guild_id}.")
        else:
            queue_list = '\n'.join([f"{i+1}. [{title}]({video_url})" for i, (_, title, video_url) in enumerate(queue)])
            await ctx.send(f"Текущая очередь:\n{queue_list}")
            logging.info(f"Показана очередь для guild_id: {guild_id}.")

    @commands.command()
    async def skip(self, ctx):
        logging.info(f"Команда skip вызвана: guild_id={ctx.guild.id}, играет ли: {ctx.voice_client and ctx.voice_client.is_playing()}")
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏭ Пропущено!")
            logging.info("Трек пропущен, вызов play_next.")
        else:
            await ctx.send("Сейчас ничего не играет.")
            logging.info("Попытка пропустить, но ничего не играет.")

    @commands.command()
    async def remove(self, ctx, index: int):
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        logging.info(f"Команда remove вызвана: guild_id={guild_id}, index={index}, размер очереди до удаления: {len(queue)}")
        if 1 <= index <= len(queue):
            removed = queue.pop(index - 1)
            await ctx.send(f'❌ Удалено из очереди: {removed[1]}')
            logging.info(f"Трек удален: title='{removed[1]}', размер очереди после удаления: {len(queue)}")
        else:
            await ctx.send("Неверный номер трека!")
            logging.warning(f"Неверный номер трека для удаления: {index}")

    @commands.command()
    async def stop(self, ctx):
        logging.info(f"Команда stop вызвана: guild_id={ctx.guild.id}, voice_client={'подключен' if ctx.voice_client and ctx.voice_client.is_connected() else 'не подключен'}")
        if ctx.voice_client and ctx.voice_client.is_connected():
            ctx.voice_client.stop()
            self.queues[ctx.guild.id] = []
            await ctx.send("⏹️ Музыка остановлена и очередь очищена.", delete_after=10)
            logging.info(f"Музыка остановлена и очередь очищена для guild_id: {ctx.guild.id}.")
        else:
            await ctx.send("Бот не подключен к голосовому каналу.")
            logging.info("Попытка остановить, но бот не подключен к голосовому каналу.")

def setup(bot):
    logging.info("Вызвана функция setup для Music Cog.")
    bot.add_cog(Music(bot))
    logging.info("Music Cog добавлен в бота.")