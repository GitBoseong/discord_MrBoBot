<<<<<<< HEAD
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
=======
# music_cog.py

import discord
from discord.ext import commands
from discord import FFmpegPCMAudio
from discord.ui import View, Button
from config import FFMPEG_OPTIONS
from utils.youtube import search_youtube_info
import asyncio  # 추가

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild.id 별로 대기열을 리스트로 관리
        self.queue: dict[int, list[dict]] = {}

    async def _play_track(self, interaction_or_ctx, info: dict):
        """실제 오디오 재생 및 임베드+버튼 메시지 전송"""
        # guild, channel, vc 얻기
        if isinstance(interaction_or_ctx, discord.Interaction):
            guild = interaction_or_ctx.guild
            channel = interaction_or_ctx.channel
            user = interaction_or_ctx.user
        else:
            guild = interaction_or_ctx.guild
            channel = interaction_or_ctx.channel
            user = interaction_or_ctx.author

        vc = guild.voice_client

        # after 콜백: 노래 끝나면 _play_next 스케줄
        def _after_play(error):
            # 오류가 있으면 로그
            if error:
                print(f"[Music Cog] 플레이 중 에러: {error}")
            # 코루틴 스케줄링
            asyncio.run_coroutine_threadsafe(
                self._play_next(interaction_or_ctx),
                self.bot.loop
            )

        # 재생
        vc.play(
            FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS),
            after=_after_play
        )

        # 임베드 + 버튼
        embed = discord.Embed(
            title=info.get('title', 'Unknown'),
            url=f"https://youtu.be/{info.get('id')}"
        )
        if thumb := info.get('thumbnail'):
            embed.set_thumbnail(url=thumb)
        embed.add_field(name="요청자", value=user.mention)

        view = View()
        view.add_item(Button(label="⏸️ 일시정지", style=discord.ButtonStyle.secondary, custom_id="pause"))
        view.add_item(Button(label="▶️ 재개", style=discord.ButtonStyle.secondary, custom_id="resume"))
        view.add_item(Button(label="⏹️ 정지", style=discord.ButtonStyle.danger,    custom_id="stop"))
        view.add_item(Button(label="⏭️ 다음곡", style=discord.ButtonStyle.primary,  custom_id="skip"))

        await channel.send(embed=embed, view=view)

    async def _play_next(self, interaction_or_ctx):
        """현재 재생이 끝난 후 큐에서 다음 곡 꺼내서 재생"""
        # guild, channel 얻기
        if isinstance(interaction_or_ctx, discord.Interaction):
            guild = interaction_or_ctx.guild
            channel = interaction_or_ctx.channel
        else:
            guild = interaction_or_ctx.guild
            channel = interaction_or_ctx.channel

        gid = guild.id
        q = self.queue.get(gid, [])
        if not q:
            # 큐가 비어 있으면 아무 것도 안 함
            return

        # 다음 곡
        next_info = q.pop(0)
        self.queue[gid] = q
        # 재생
        await self._play_track(interaction_or_ctx, next_info)

    @commands.command(name='join')
    async def join(self, ctx: commands.Context):
        """봇을 음성 채널에 참여시킵니다."""
        if ctx.author.voice and ctx.author.voice.channel:
            vc = ctx.voice_client
            if not vc:
                vc = await ctx.author.voice.channel.connect()
            await ctx.send(f"✅ 연결됨: {vc.channel}")
        else:
            await ctx.send("❌ 음성 채널에 먼저 들어가 있어야 합니다.")

    @commands.command(name='leave')
    async def leave(self, ctx: commands.Context):
        """봇을 음성 채널에서 나가게 합니다."""
        vc = ctx.voice_client
        if vc:
            await vc.disconnect()
            await ctx.send("👋 나갔습니다.")
        else:
            await ctx.send("❌ 봇이 음성 채널에 없습니다.")

    @commands.command(name='play')
    async def play(self, ctx: commands.Context, *, query: str = None):
        """!play <검색어> 또는 <URL> 형태로 음악을 재생합니다."""
        if query is None:
            return await ctx.send("❌ 사용법: `!play <검색어>`")

        # (1) 음성 채널 연결 확인
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
        vc = ctx.voice_client
        gid = ctx.guild.id

        # (2) 검색 및 정보 획득
        info = search_youtube_info(query)

        # (3) 재생 중이면 큐에 추가
        if vc.is_playing() or vc.is_paused():
            self.queue.setdefault(gid, []).append(info)
            await ctx.send(f"➕ 대기열에 추가: `{info.get('title','Unknown')}`")
        else:
            # 바로 재생
            await self._play_track(ctx, info)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """버튼 클릭 이벤트 핸들러"""
        custom_id = interaction.data.get('custom_id')
        guild = interaction.guild
        vc = guild.voice_client
        gid = guild.id

        if custom_id in ['pause', 'resume', 'stop', 'skip']:
            if not vc:
                return await interaction.response.send_message("❌ 봇이 음성 채널에 없습니다.", ephemeral=True)

            if custom_id == 'pause' and vc.is_playing():
                vc.pause()
                return await interaction.response.send_message("⏸️ 일시정지했습니다.", ephemeral=True)

            if custom_id == 'resume' and vc.is_paused():
                vc.resume()
                return await interaction.response.send_message("▶️ 재개했습니다.", ephemeral=True)

            if custom_id == 'stop':
                vc.stop()
                # self.queue[gid] = []  # 필요시 큐 비우기
                return await interaction.response.send_message("⏹️ 재생을 중단했습니다.", ephemeral=True)

            if custom_id == 'skip':
                q = self.queue.get(gid, [])
                if not q:
                    return await interaction.response.send_message("⚠️ 더 재생할 곡이 없습니다.", ephemeral=True)

                vc.stop()
                next_info = q.pop(0)
                self.queue[gid] = q
                await interaction.response.send_message(f"⏭️ 다음곡 재생: `{next_info.get('title','Unknown')}`", ephemeral=True)
                await self._play_track(interaction, next_info)

    @commands.command(name='queue')
    async def _queue(self, ctx: commands.Context):
        q = self.queue.get(ctx.guild.id, [])
        if q:
            msg = '\n'.join(f"{i+1}. {item.get('title','Unknown')}" for i, item in enumerate(q))
            await ctx.send(f"🎵 대기열:\n{msg}")
        else:
            await ctx.send("대기열이 비어있습니다.")

    @commands.command(name='clear')
    async def clear(self, ctx: commands.Context):
        self.queue[ctx.guild.id] = []
        await ctx.send("🗑️ 대기열을 비웠습니다.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
>>>>>>> master
