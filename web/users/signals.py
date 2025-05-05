# users/signals.py
from django.dispatch import receiver
from allauth.account.signals import user_signed_up
from allauth.socialaccount.models import SocialAccount, SocialToken
import requests
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

DISCORD_SERVER_ID = '1342493775632797799'
DISCORD_API_BASE_URL = 'https://discord.com/api/v10'
DISCORD_GUILDS_URL = f'{DISCORD_API_BASE_URL}/users/@me/guilds'

@receiver(user_signed_up)
def check_discord_guild(request, user, **kwargs):
    social_account = SocialAccount.objects.filter(user=user, provider='discord').first()
    if social_account:
        social_token = SocialToken.objects.filter(account=social_account).first()
        if social_token:
            headers = {
                'Authorization': f'Bearer {social_token.token}'
            }
            response = requests.get(settings.DISCORD_GUILDS_URL, headers=headers)
            response.raise_for_status()
            guilds_data = response.json()

            is_member = False
            for guild in guilds_data:
                if guild.get('id') == DISCORD_SERVER_ID:
                    is_member = True
                    break

            if not is_member:
                # Пользователь не состоит на сервере, перенаправляем его на страницу с просьбой присоединиться
                return redirect(reverse('join_discord_server')) # Создадим этот URL и представление позже
        else:
            print("Social token not found for Discord user.")
    else:
        print("Discord social account not found for user.")

    return None # Если пользователь состоит на сервере или произошла ошибка, продолжаем обычный поток