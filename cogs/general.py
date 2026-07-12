import discord
from discord.ext import commands


class General(commands.Cog):
    """General utility commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context) -> None:
        latency = self.bot.latency * 1000
        await ctx.send(f"PONG! {latency:.0f}ms")

    @commands.command(name="helpme")
    async def helpme(self, ctx: commands.Context) -> None:
        embed = discord.Embed(title="MrBoBot 명령어", color=0x5865F2)
        embed.add_field(
            name="음악",
            value=(
                "`/play` 검색어 또는 URL 재생\n"
                "`/search` 검색 결과에서 선택 재생\n"
                "`/queue` 큐 보기 및 관리\n"
                "`/pause`, `/resume`, `/skip`, `/stop`\n"
                "`/remove`, `/clear`, `/shuffle`, `/now`"
            ),
            inline=False,
        )
        embed.add_field(name="일반", value="`!ping`, `!helpme`, `!hello`", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="hello")
    async def hello(self, ctx: commands.Context) -> None:
        await ctx.send("안녕하세요!")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
