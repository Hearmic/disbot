from django.contrib import admin
from .models import CustomUser, DiscordUser, MinecraftUser

admin.site.register(CustomUser)
admin.site.register(DiscordUser)
admin.site.register(MinecraftUser)

