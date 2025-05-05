# payment/tasks.py
from celery import shared_task
from django.utils import timezone
from .models import UserSubscription

@shared_task
def deactivate_expired_subscriptions():
    now = timezone.now()
    expired_subscriptions = UserSubscription.objects.filter(
        is_active=True,
        end_date__lt=now
    )
    for subscription in expired_subscriptions:
        subscription.is_active = False
        subscription.save()
        print(f"Деактивирована подписка пользователя {subscription.user.username} (ID: {subscription.id})")

    return f"Обработано {expired_subscriptions.count()} просроченных подписок."