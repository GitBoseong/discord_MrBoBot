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
