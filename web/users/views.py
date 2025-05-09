import requests
from django.conf import settings
from .models import DiscordUser
from django.shortcuts import render, redirect
from .forms import MinecraftInfoForm
from .models import MinecraftUser
from allauth.account.decorators import login_required
from django.contrib.auth import login
from users.models import CustomUser
import logging

logging.basicConfig(level=logging.INFO)

def discord_login(request):
    authorize_url = f'{settings.DISCORD_AUTHORIZE_URL}?client_id={settings.DISCORD_CLIENT_ID}&redirect_uri={settings.DISCORD_REDIRECT_URI}&response_type=code&scope={settings.DISCORD_SCOPES}'
    return redirect(authorize_url)

def discord_callback(request):
    code = request.GET.get('code')
    if code:
        token_data = {
            'client_id': settings.DISCORD_CLIENT_ID,
            'client_secret': settings.DISCORD_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': settings.DISCORD_REDIRECT_URI,
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response = requests.post(settings.DISCORD_TOKEN_URL, data=token_data, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        token = response.json().get('access_token')

        if token:
            user_headers = {
                'Authorization': f'Bearer {token}'
            }
            user_response = requests.get(settings.DISCORD_API_URL + '/users/@me', headers=user_headers)
            user_response.raise_for_status()
            user_data = user_response.json()
            logging.info(f"Данные пользователя Discord: {user_data}")

            discord_id = user_data.get('id')
            discord_username = user_data.get('username')
            email = user_data.get('email')
            avatar = user_data.get('avatar')
            is_verified = user_data.get('verified', False)  # По умолчанию False, если отсутствует

            avatar_url = None
            if avatar:
                avatar_format = 'gif' if avatar.startswith('a_') else 'png'
                avatar_url = f'https://cdn.discordapp.com/avatars/{discord_id}/{avatar}.{avatar_format}'

            try:
                discord_user = DiscordUser.objects.get(discord_id=discord_id)
                # Обновляем всю доступную информацию пользователя Discord
                discord_user.discord_username = discord_username
                discord_user.avatar_url = avatar_url
                discord_user.is_verified = is_verified
                discord_user.user.email = email # Обновляем email связанного пользователя Django
                discord_user.user.save()
                discord_user.save()
                user = discord_user.user
                login(request, user, backend='allauth.account.auth_backends.AuthenticationBackend')
                return redirect('some_success_url')
            except DiscordUser.DoesNotExist:
                # Создаем нового пользователя Django
                new_user = CustomUser.objects.create_user(username=discord_username, email=email)
                new_user.save()
                # Создаем связанный DiscordUser со всей доступной информацией
                discord_user = DiscordUser.objects.create(
                    user=new_user,
                    discord_id=discord_id,
                    discord_username=discord_username,
                    avatar_url=avatar_url,
                    is_verified=is_verified,
                )
                login(request, new_user, backend='allauth.account.auth_backends.AuthenticationBackend')
                return redirect('some_success_url')
        else:
            return redirect('some_failure_url')
    else:
        return redirect('some_failure_url')


def join_discord_server(request):
    discord_invite_link = 'https://discord.gg/EtCRhQaAXB' 
    return render(request, 'users/join_discord.html', {'invite_link': discord_invite_link})

def xuid_to_uuid(xuid):
    """Преобразует XUID в UUID Java-версии по формуле Floodgate."""
    hex_xuid = hex(xuid)[2:].zfill(16)
    return f"00000000-0000-0000-{hex_xuid[:4]}-{hex_xuid[4:]}"

@login_required
def minecraft_info_form_view(request):
    if request.method == 'POST':
        form = MinecraftInfoForm(request.POST)
        if form.is_valid():
            platform = form.cleaned_data['platform']
            java_nickname = form.cleaned_data['java_nickname']
            bedrock_nickname = form.cleaned_data['bedrock_nickname']

            minecraft_user, created = MinecraftUser.objects.get_or_create(discord_user=request.user.discorduser)
            minecraft_user.java_nickname = java_nickname
            minecraft_user.bedrock_nickname = bedrock_nickname

            if platform == 'bedrock' and bedrock_nickname:
                headers = {
                    'X-AUTH': settings.XBOX_API_KEY
                }
                try:
                    response = requests.get(f'{XBOX_API_BASE_URL}/xuid/{bedrock_nickname}', headers=headers)
                    response.raise_for_status()
                    xuid_data = response.json()
                    xuid = xuid_data.get('xuid')
                    if xuid:
                        minecraft_user.floodgate_uuid = xuid_to_uuid(int(xuid))
                    else:
                        logging.info(f"Не удалось получить XUID для никнейма: {bedrock_nickname}")
                except requests.exceptions.RequestException as e:
                    logging.error(f"Ошибка при запросе к Xbox API: {e}")

            minecraft_user.save()

            # Активация пробного периода сразу после ввода информации
            trial = TrialPeriod.objects.create(discord_user=request.user.discorduser)
            trial.end_date = timezone.now() + timezone.timedelta(days=30)
            trial.save()

            try:
                with MCRcon(RCON_HOST, RCON_PORT, RCON_PASSWORD) as mcr:
                    if platform == 'java' and java_nickname:
                        response = mcr.command(f"whitelist add {java_nickname}")
                        logging.info(f"RCON response (whitelist add {java_nickname}): {response}")
                        # Выдача роли Discord
                        bot = commands.Bot(command_prefix="!") # Префикс не важен, мы не будем использовать команды
                        async def give_discord_role():
                            try:
                                guild = bot.get_guild(settings.DISCORD_GUILD_ID) # ID вашего Discord сервера
                                member = await guild.fetch_member(discord_user.discord_id)
                                if member:
                                    role = guild.get_role(JAVA_TRIAL_ROLE_ID)
                                    if role:
                                        await member.add_roles(role)
                                        logging.info(f"Выдана роль Trial Java пользователю {discord_user.username}")
                                    else:
                                        logging.info(f"Роль Trial Java с ID {JAVA_TRIAL_ROLE_ID} не найдена.")
                                else:
                                    logging.info(f"Пользователь с ID {discord_user.discord_id} не найден на сервере Discord.")
                            except disnake.HTTPException as e:
                                logging.error(f"Ошибка при выдаче роли Discord: {e}")
                            finally:
                                await bot.close()
                        bot.loop.run_until_complete(give_discord_role())

                    elif platform == 'bedrock' and bedrock_nickname:
                        response = mcr.command(f"fwhitelist add {bedrock_nickname}")
                        print(f"RCON response (fwhitelist add {bedrock_nickname}): {response}")
                        # Выдача роли Discord
                        bot = commands.Bot(command_prefix="!")
                        async def give_discord_role():
                            try:
                                guild = bot.get_guild(settings.DISCORD_GUILD_ID)
                                member = await guild.fetch_member(discord_user.discord_id)
                                if member:
                                    role = guild.get_role(BEDROCK_TRIAL_ROLE_ID)
                                    if role:
                                        await member.add_roles(role)
                                        print(f"Выдана роль Trial Bedrock пользователю {discord_user.username}")
                                    else:
                                        print(f"Роль Trial Bedrock с ID {BEDROCK_TRIAL_ROLE_ID} не найдена.")
                                else:
                                    print(f"Пользователь с ID {discord_user.discord_id} не найден на сервере Discord.")
                            except disnake.HTTPException as e:
                                print(f"Ошибка при выдаче роли Discord: {e}")
                            finally:
                                await bot.close()
                        bot.loop.run_until_complete(give_discord_role())

            except Exception as e:
                print(f"Ошибка при взаимодействии с RCON или Discord: {e}")

            return redirect('trial_started_page')
    else:
        form = MinecraftInfoForm()

    return render(request, 'users/minecraft_info_form.html', {'form': form})