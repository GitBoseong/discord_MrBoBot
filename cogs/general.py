#general.py
import discord
from discord.ext import commands

class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='ping')
    async def ping(self, ctx: commands.Context):
        """봇의 응답속도를 확인합니다."""
        latency = self.bot.latency * 1000
        await ctx.send(f"🏓 PONG! {latency:.0f}ms")

    @commands.command(name='helpme')
    async def helpme(self, ctx: commands.Context):
        """기본 명령어 목록을 보여줍니다."""
        cmds = [c.name for c in self.bot.commands]
        await ctx.send(f"사용 가능한 명령어: {', '.join(cmds)}")

async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))