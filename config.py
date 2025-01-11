from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

# 봇 토큰 가져오기
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not DISCORD_BOT_TOKEN:
    print("Error: DISCORD_BOT_TOKEN is not set in .env file.")
