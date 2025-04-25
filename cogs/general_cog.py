# cogs/general_cog.py

import discord
from discord.ext import commands

class GeneralCog(commands.Cog):
    """일반 명령어(hello, leave 등)를 담당하는 Cog."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='hello')
    async def hello(self, ctx: commands.Context):
        await ctx.send("안녕하세요! Mr.Bo입니다.")

    @commands.command(name='leave')
    async def leave(self, ctx: commands.Context):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("✅ 음성 채널에서 나왔습니다.")
        else:
            await ctx.send("⚠️ 아직 음성 채널에 없습니다.")

# async setup 함수로 변경
async def setup(bot: commands.Bot):
    """Extension 로드 시 호출되는 비동기 setup 함수"""
    await bot.add_cog(GeneralCog(bot))
