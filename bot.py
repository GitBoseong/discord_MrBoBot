# bot.py
import discord
from discord.ext import commands
from commands.music import setup_music_commands
from commands.general import setup_general_commands
from config import DISCORD_BOT_TOKEN  # config.py에서 로드된 토큰 가져오기

# Bot 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 명령어 로드
def setup_commands():
    # Initialize music-related commands
    try:
        setup_music_commands(bot)
        print("Music commands loaded successfully.")
    except Exception as e:
        print(f"Error loading music commands: {e}")

    # Initialize general-purpose commands
    try:
        setup_general_commands(bot)
        print("General commands loaded successfully.")
    except Exception as e:
        print(f"Error loading general commands: {e}")

# 봇 시작
@bot.event
async def on_ready():
    print(f'{bot.user} 봇이 준비되었습니다.')

if __name__ == "__main__":
    setup_commands()
    bot.run(DISCORD_BOT_TOKEN)  # 환경 변수 대신 config.py에서 로드된 토큰 사용
