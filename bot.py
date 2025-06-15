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