from django.urls import path
from . import views

urlpatterns = [
    path('login/discord/', views.discord_login, name='discord_login'),
    path('login/discord/callback/', views.discord_callback, name='discord_callback'),
    path('join/discord/', views.join_discord_server, name='join_discord_server'),
    path('minecraft-info/', views.minecraft_info_form_view, name='minecraft_info_form'),
]