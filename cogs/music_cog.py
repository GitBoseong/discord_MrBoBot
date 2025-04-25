import discord
import asyncio
from discord.ext import commands
import youtube_dl

# ─── 유튜브 DL 옵션 (오디오 전용) ────────────────────────────────────
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    # 기타 youtube_dl 옵션을 필요에 따라 추가
}

# ─── FFmpeg 재접속 옵션 ─────────────────────────────────────────────
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

class MusicCog(commands.Cog):
    """
    음악 재생, 큐 관리, 버튼 인터랙션을 담당하는 Cog.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queue: list[tuple[str, str]] = []  # (제목, URL)
        self.current_title: str | None = None

    @commands.command(name='play')
    async def play(self, ctx: commands.Context, *, search: str):
        """
        검색어 또는 URL로 노래를 재생하거나 큐에 추가.
        """
        # 1) 검색어 → 정보 조회
        if search.startswith(('http://', 'https://')):
            title = search
            url = search
        else:
            # YouTubeService.search()를 사용하던 부분 대신, 직접 URL로 검색하거나
            await ctx.send("⚠️ 검색 기능은 현재 URL 입력만 지원합니다.")
            return

        # 2) 음성 채널 입장 확인
        voice = ctx.voice_client
        if not voice:
            if ctx.author.voice and ctx.author.voice.channel:
                voice = await ctx.author.voice.channel.connect()
            else:
                await ctx.send("⚠️ 먼저 음성 채널에 입장해주세요.")
                return

        # 3) 이미 재생 중이면 큐에 추가
        if voice.is_playing():
            self.queue.append((title, url))
            await ctx.send(f"➕ **{title}** 큐에 추가되었습니다.")
            return

        # 4) 바로 재생
        await self._start_play(ctx, voice, title, url)

    async def _start_play(
        self,
        ctx: commands.Context,
        voice: discord.VoiceClient,
        title: str,
        url: str
    ):
        """FFmpegPCMAudio 생성→재생, 임베드+버튼 전송."""
        # 유튜브 DL로 스트림 정보 추출
        with youtube_dl.YoutubeDL(YTDL_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)

        # 비디오 없는 오디오 전용 스트림, HLS 매니페스트 제외
        audio_format = next(
            f for f in info['formats']
            if f.get('vcodec') == 'none'
            and f.get('acodec') != 'none'
            and not f['url'].endswith('.m3u8')
        )
        stream_url = audio_format['url']

        # FFmpegPCMAudio에 재접속 옵션 주입
        source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
        voice.play(source, after=lambda e: self._after_play(ctx, e))

        self.current_title = title

        # Now Playing 임베드
        embed = discord.Embed(title="▶️ Now Playing", description=f"[{title}]({url})")
        await ctx.send(embed=embed)

    def _after_play(self, ctx: commands.Context, error):
        """
        재생 종료 후 대기열 확인.
        """
        if error:
            print(f"[MusicCog] playback error: {error}")
        if self.queue:
            title, url = self.queue.pop(0)
            coro = self.play(ctx, search=url)
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
        else:
            self.current_title = None

    @commands.command(name='playlist')
    async def playlist(self, ctx: commands.Context):
        """현재 대기열 표시."""
        if not self.queue:
            await ctx.send("📭 대기열이 비어 있습니다.")
        else:
            lines = [f"{i+1}. {t}" for i, (t, _) in enumerate(self.queue)]
            await ctx.send("**📜 Playlist:**\n" + "\n".join(lines))

    @commands.command(name='remove')
    async def remove(self, ctx: commands.Context, position: int):
        """큐에서 특정 곡 제거."""
        if 1 <= position <= len(self.queue):
            title, _ = self.queue.pop(position-1)
            await ctx.send(f"❌ **{title}** 을(를) 제거했습니다.")
        else:
            await ctx.send("⚠️ 유효한 번호를 입력해주세요.")


# async setup 함수로 변경
async def setup(bot: commands.Bot):
    """Extension 로드 시 호출되는 비동기 setup 함수"""
    await bot.add_cog(MusicCog(bot))
