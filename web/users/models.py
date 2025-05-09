
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver

class CustomUser(AbstractUser):
    """
    Расширенная модель пользователя с дополнительными полями
    """
    GENDER_CHOICES = [
        ('M', 'Мужской'),
        ('F', 'Женский'),
        ('O', 'Другое')
    ]

    # Персональная информация
    middle_name = models.CharField(
        max_length=150, 
        blank=True, 
        verbose_name='Отчество'
    )
    gender = models.CharField(
        max_length=1, 
        choices=GENDER_CHOICES, 
        blank=True, 
        null=True
    )
    birth_date = models.DateField(
        null=True, 
        blank=True, 
        verbose_name='Дата рождения'
    )

    # Финансовая информация
    balance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00, 
        verbose_name='Баланс'
    )

    def __str__(self):
        return self.username

class DiscordUser(models.Model):
    """
    Расширенная информация о Discord-пользователе
    """
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='discord_profile'
    )
    discord_id = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name='ID в Discord'
    )
    discord_username = models.CharField(
        max_length=100, 
        verbose_name='Имя пользователя в Discord'
    )
    avatar_url = models.URLField(
        blank=True, 
        null=True, 
        verbose_name='URL аватара'
    )
    is_verified = models.BooleanField(
        default=False, 
        verbose_name='Верификация в Discord'
    )

    def __str__(self):
        return f"{self.discord_username} ({self.discord_id})"

class MinecraftUser(models.Model):
    """
    Информация о Minecraft-профиле пользователя
    """
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='minecraft_profile'
    )
    java_nickname = models.CharField(max_length=16, blank=True, null=True, verbose_name='Никнейм Java')
    bedrock_nickname = models.CharField(max_length=32, blank=True, null=True, verbose_name='Никнейм Bedrock')
    xuid = models.CharField(max_length=32, blank=True, null=True, verbose_name='XUID Bedrock')
    floodgate_uuid = models.UUIDField(null=True, blank=True, verbose_name='Floodgate UUID')
    last_server_join = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name='Последнее подключение к серверу'
    )

    def __str__(self):
        if self.java_nickname:
            return f"{self.java_nickname} (Java)"
        elif self.bedrock_nickname:
            return f"{self.bedrock_nickname} (Bedrock)"
        return f"ID: {self.user.username}"

class CurrencyTransaction(models.Model):
    """
    Транзакции пользователя
    """
    TRANSACTION_TYPES = [
        ('deposit', 'Пополнение'),
        ('withdrawal', 'Списание'),
        ('reward', 'Награда'),
        ('penalty', 'Штраф')
    ]

    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='transactions'
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2
    )
    transaction_type = models.CharField(
        max_length=20, 
        choices=TRANSACTION_TYPES
    )
    description = models.TextField(
        blank=True, 
        null=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.transaction_type}: {self.amount}"