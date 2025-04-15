from disnake.ext import commands

class MinimalCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

def setup(bot):
    bot.add_cog(MinimalCog(bot))