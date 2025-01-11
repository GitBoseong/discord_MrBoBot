# commands/general.py
from discord.ext import commands

def setup_general_commands(bot):
    @bot.command(name='hello')
    async def hello(ctx):
        await ctx.send("안녕하세요! Mr.Bo입니다.")

    @bot.command(name='leave')
    async def leave(ctx):
        await ctx.voice_client.disconnect()
        await ctx.send("음성 채널에서 나왔습니다.")
