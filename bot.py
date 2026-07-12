import asyncio
from pathlib import Path

import discord
from discord.ext import commands

from config import DISCORD_TOKEN


BASE_DIR = Path(__file__).resolve().parent
COGS_DIR = BASE_DIR / "cogs"

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as exc:
        print(f"Failed to sync slash commands: {exc}")


async def load_cogs() -> None:
    for path in COGS_DIR.glob("*.py"):
        if path.name == "__init__.py":
            continue

        cog_name = path.stem
        try:
            await bot.load_extension(f"cogs.{cog_name}")
            print(f"Loaded cog: cogs.{cog_name}")
        except Exception as exc:
            print(f"Failed to load cog {cog_name}: {exc}")


async def main() -> None:
    if not DISCORD_TOKEN:
        raise RuntimeError(".env 파일에 DISCORD_TOKEN을 설정해 주세요.")

    async with bot:
        await load_cogs()
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
