<<<<<<< HEAD
# bot.py

import os
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

# 3) 봇 실행 — 이 줄이 반드시 있어야 스크립트가 종료되지 않고 디스코드에 연결됩니다!
bot.run(TOKEN)
=======
#bot.py

import asyncio
import discord
from discord.ext import commands
import os

from config import DISCORD_TOKEN

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

async def load_cogs():
    # cogs 디렉터리에서 모든 .py 파일을 찾아 자동으로 로드합니다.
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and filename != '__init__.py':
            cog_name = filename[:-3]
            try:
                await bot.load_extension(f'cogs.{cog_name}')
                print(f"Loaded cog: cogs.{cog_name}")
            except Exception as e:
                print(f"Failed to load cog {cog_name}: {e}")

async def main():
    async with bot:
        await load_cogs()
        await bot.start(DISCORD_TOKEN)

if __name__ == '__main__':
    asyncio.run(main())
>>>>>>> master
