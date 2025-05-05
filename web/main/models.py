from django.db import models
from django.utils import timezone

class TrialPeriod(models.Model):
    discord_user = models.OneToOneField('users.DiscordUser', on_delete=models.CASCADE, related_name='trial', verbose_name='Пользователь Discord')
    start_date = models.DateTimeField(default=timezone.now, verbose_name='Дата начала')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='Дата окончания')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    def __str__(self):
        return f"Пробный период для {self.discord_user}"

    class Meta:
        verbose_name = 'Пробный период'
        verbose_name_plural = 'Пробные периоды'

class Referral(models.Model):
    referrer = models.ForeignKey('users.DiscordUser', on_delete=models.CASCADE, related_name='referrals_sent', verbose_name='Пригласивший')
    referred = models.ForeignKey('users.DiscordUser', on_delete=models.CASCADE, related_name='referrals_received', verbose_name='Приглашенный')
    referral_date = models.DateTimeField(auto_now_add=True, verbose_name='Дата приглашения')
    is_paid = models.BooleanField(default=False, verbose_name='Реферал оплатил')
    reward_given = models.BooleanField(default=False, verbose_name='Награда выдана')

    def __str__(self):
        return f"{self.referrer} пригласил {self.referred}"

    class Meta:
        verbose_name = 'Реферальная связь'
        verbose_name_plural = 'Реферальные связи'
        unique_together = ('referrer', 'referred')