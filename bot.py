# cogs/music_cog.py

import discord
from discord.ext import commands
import youtube_dl

# ─── 재접속 옵션 정의 ─────────────────────────────────────────────
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    # ...기타 youtube_dl 옵션...
}

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def play(self, ctx, url: str):
        # 1) 음성 채널에 연결
        if not ctx.author.voice:
            return await ctx.send("먼저 음성 채널에 들어가 있어야 해요.")
        vc = await ctx.author.voice.channel.connect()

        # 2) youtube_dl 로 오디오 URL 추출
        with youtube_dl.YoutubeDL(YTDL_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['formats'][0]['url']

        # 3) FFmpegPCMAudio 에 재접속 옵션 주입
        source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS)

        # 4) 재생
        vc.play(source, after=lambda e: print("Playback finished.", e))
        await ctx.send(f"재생 시작: {info.get('title')}")

def setup(bot):
    bot.add_cog(MusicCog(bot))
