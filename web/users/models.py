from django.db import models

# users/models.py
from django.db import models
from django.utils import timezone

class DiscordUser(models.Model):
    discord_id = models.BigIntegerField(unique=True, verbose_name='Discord ID')
    username = models.CharField(max_length=255, verbose_name='Имя пользователя Discord')
    email = models.EmailField(blank=True, null=True, verbose_name='Email Discord')
    joined_discord_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата присоединения к Discord')

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = 'Пользователь Discord'
        verbose_name_plural = 'Пользователи Discord'

class MinecraftUser(models.Model):
    discord_user = models.OneToOneField(DiscordUser, on_delete=models.CASCADE, related_name='minecraft_info', verbose_name='Пользователь Discord')
    java_nickname = models.CharField(max_length=16, blank=True, null=True, verbose_name='Никнейм Java')
    bedrock_nickname = models.CharField(max_length=32, blank=True, null=True, verbose_name='Никнейм Bedrock')
    xuid = models.CharField(max_length=32, blank=True, null=True, verbose_name='XUID Bedrock')
    floodgate_uuid = models.UUIDField(null=True, blank=True, verbose_name='Floodgate UUID')

    def __str__(self):
        if self.java_nickname:
            return f"{self.java_nickname} (Java)"
        elif self.bedrock_nickname:
            return f"{self.bedrock_nickname} (Bedrock)"
        return f"ID: {self.discord_user.discord_id}"

    class Meta:
        verbose_name = 'Пользователь Minecraft'
        verbose_name_plural = 'Пользователи Minecraft'