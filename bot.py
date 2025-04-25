import os
from dotenv import load_dotenv
import discord
from discord.ext import commands

# .env에서 토큰 로드
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN이 설정되지 않았습니다.")

# Bot 초기화
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Cog 자동 로드
for cog in ("cogs.music_cog", "cogs.general_cog"):
    try:
        bot.load_extension(cog)
        print(f"[OK] Loaded {cog}")
    except Exception as e:
        print(f"[ERR] Failed loading {cog}: {e}")

@bot.event
async def on_ready():
    print(f"{bot.user} 봇이 준비되었습니다.")

bot.run(TOKEN)
