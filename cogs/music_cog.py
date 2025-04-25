# cogs/music_cog.py

import discord
import asyncio
from discord.ext import commands
from utils.youtube_service import YouTubeService

class MusicCog(commands.Cog):
    """
    음악 재생, 큐 관리, 버튼 인터랙션을 담당하는 Cog.
    """
    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }

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
            info = {'webpage_url': search, 'title': search, 'thumbnail': None}
        else:
            info = YouTubeService.search(search)
        url = info['webpage_url']
        title = info['title']
        thumb = info.get('thumbnail')

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
        await self._start_play(ctx, voice, title, url, thumb)

    async def _start_play(
        self,
        ctx: commands.Context,
        voice: discord.VoiceClient,
        title: str,
        url: str,
        thumbnail: str | None
    ):
        """FFmpegPCMAudio 생성→재생, 임베드+버튼 전송."""
        stream_url = YouTubeService.get_stream_url(url)
        source = discord.FFmpegPCMAudio(stream_url, **self.FFMPEG_OPTIONS)
        voice.play(source, after=lambda e: self._after_play(ctx, e))

        self.current_title = title

        # Now Playing 임베드
        embed = discord.Embed(title="▶️ Now Playing", description=f"[{title}]({url})")
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)

        # 버튼 뷰
        view = discord.ui.View(timeout=None)
        for label, style, cid in [
            ("⏸️ Pause", discord.ButtonStyle.secondary, "pause"),
            ("▶️ Resume", discord.ButtonStyle.secondary, "resume"),
            ("⏭️ Skip", discord.ButtonStyle.primary, "skip"),
            ("⏹️ Stop", discord.ButtonStyle.danger, "stop"),
        ]:
            btn = discord.ui.Button(label=label, style=style, custom_id=cid)
            btn.callback = self._make_button_callback(voice)
            view.add_item(btn)

        await ctx.send(embed=embed, view=view)

    def _make_button_callback(self, voice: discord.VoiceClient):
        async def callback(interaction: discord.Interaction):
            cid = interaction.data['custom_id']
            if cid == "pause" and voice.is_playing():
                voice.pause()
                await interaction.response.send_message("⏸️ 재생 일시정지", ephemeral=True)
            elif cid == "resume" and voice.is_paused():
                voice.resume()
                await interaction.response.send_message("▶️ 재생 재개", ephemeral=True)
            elif cid == "skip":
                skipped = self.current_title
                voice.stop()
                await interaction.response.send_message(f"⏭️ **{skipped}** 스킵", ephemeral=True)
            elif cid == "stop":
                voice.stop()
                await interaction.response.send_message("⏹️ 재생 종료", ephemeral=True)
        return callback

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
