# bot.py

import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

# 1) .env 로드
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN이 설정되지 않았습니다.")

# 2) Bot 클래스 서브클래싱
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Cog 자동 로드
        for cog in ("cogs.music_cog", "cogs.general_cog"):
            await self.load_extension(cog)
            print(f"[OK] Loaded {cog}")

bot = MyBot()

@bot.event
async def on_ready():
    print(f"{bot.user} 봇이 준비되었습니다.")

# 3) 봇 실행
bot.run(TOKEN)
