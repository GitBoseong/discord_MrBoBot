<<<<<<< HEAD
from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

# 봇 토큰 가져오기
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not DISCORD_BOT_TOKEN:
    print("Error: DISCORD_BOT_TOKEN is not set in .env file.")
=======
#config.py

import os
from dotenv import load_dotenv

load_dotenv()

# Discord
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# FFmpeg 옵션
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}
>>>>>>> master
