from django.db import models

class Payment(models.Model):
    discord_user = models.ForeignKey('users.DiscordUser', on_delete=models.CASCADE, related_name='payments', verbose_name='Пользователь Discord')
    payment_id = models.CharField(max_length=255, unique=True, verbose_name='ID платежа')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Сумма')
    payment_date = models.DateTimeField(auto_now_add=True, verbose_name='Дата платежа')
    payment_method = models.CharField(max_length=100, verbose_name='Способ оплаты')
    status = models.CharField(max_length=50, verbose_name='Статус')

    def __str__(self):
        return f"Платеж {self.payment_id} от {self.discord_user}"

    class Meta:
        verbose_name = 'Платеж'
        verbose_name_plural = 'Платежи'

class Tariff(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название тарифа')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    duration = models.IntegerField(verbose_name='Длительность в днях')
    description = models.TextField(blank=True, verbose_name='Описание')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Тариф'
        verbose_name_plural = 'Тарифы'

class UserSubscription(models.Model):
    user = models.ForeignKey('users.DiscordUser', on_delete=models.CASCADE, verbose_name='Пользователь Discord')
    tariff = models.ForeignKey(Tariff, on_delete=models.CASCADE, verbose_name='Тариф')
    start_date = models.DateTimeField(auto_now_add=True, verbose_name='Дата начала')
    end_date = models.DateTimeField(verbose_name='Дата окончания')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    payment_id = models.CharField(max_length=255, blank=True, null=True, verbose_name='ID платежа') # Для отслеживания в платежной системе

    def __str__(self):
        return f'{self.user.username} - {self.tariff.name} до {self.end_date}'

    class Meta:
        verbose_name = 'Подписка пользователя'
        verbose_name_plural = 'Подписки пользователей'