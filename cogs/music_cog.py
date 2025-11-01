# cogs/music.py

import os
import asyncio
from typing import Dict, List
from datetime import timedelta

import discord
from discord.ext import commands, tasks
from discord import FFmpegPCMAudio
from discord.ui import View, Button

from config import FFMPEG_OPTIONS
from utils.youtube import search_youtube_info


def utcnow():
    # discord.utils.utcnow()가 권장됨 (discord.py 2.x)
    return discord.utils.utcnow()


class Music(commands.Cog):
    """음악 재생 + 자동 나가기(3분 무활동, 혼자 남으면 즉시 종료)"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # guild.id -> queue(list[info])
        self.queue: Dict[int, List[dict]] = {}

        # guild.id -> 마지막 활동 시각
        self.last_active: Dict[int, discord.utils.datetime] = {}

        # 자동 나가기 타임아웃(초). .env 에서 AUTO_LEAVE_SECONDS로 조절 가능 (기본 180)
        self.inactive_timeout = int(os.getenv("AUTO_LEAVE_SECONDS", "180"))

        # 주기적 점검 태스크 시작
        self._auto_leave_task.start()

    # ----------------------------
    # 내부 유틸
    # ----------------------------
    def _touch_activity(self, guild_id: int) -> None:
        self.last_active[guild_id] = utcnow()

    def _inactive_for(self, guild_id: int) -> float:
        last = self.last_active.get(guild_id)
        if not last:
            return float("inf")
        return (utcnow() - last).total_seconds()

    async def _disconnect_if_inactive(self, vc: discord.VoiceClient):
        """무활동 시간이 임계치 초과 시 또는 혼자 남으면 종료"""
        guild = vc.guild
        gid = guild.id

        # 1) 채널에 혼자 남았으면 즉시 나가기
        #    (유저가 모두 나간 경우)
        if vc.channel and len([m for m in vc.channel.members if not m.bot]) == 0:
            await vc.disconnect()
            print(f"[AutoLeave] {guild.name}: 채널에 유저 없음 → 즉시 나감")
            return

        # 2) 재생/일시정지 모두 아닌 상태가 일정 시간 지속되면 나가기
        if not vc.is_playing() and not vc.is_paused():
            if self._inactive_for(gid) > self.inactive_timeout:
                await vc.disconnect()
                print(f"[AutoLeave] {guild.name}: {self.inactive_timeout}s 무활동 → 자동 나감")

    # ----------------------------
    # 주기 태스크
    # ----------------------------
    @tasks.loop(seconds=15)
    async def _auto_leave_task(self):
        """15초마다 모든 길드의 보이스 상태 확인"""
        for vc in list(self.bot.voice_clients):
            try:
                await self._disconnect_if_inactive(vc)
            except Exception as e:
                print(f"[AutoLeave] 점검 중 오류: {e}")

    @_auto_leave_task.before_loop
    async def _before_auto_leave(self):
        await self.bot.wait_until_ready()

    # ----------------------------
    # 재생 / 큐
    # ----------------------------
    async def _play_track(self, interaction_or_ctx, info: dict):
        """오디오 재생 + 임베드 & 버튼"""
        # 컨텍스트 분기
        if isinstance(interaction_or_ctx, discord.Interaction):
            guild = interaction_or_ctx.guild
            channel = interaction_or_ctx.channel
            user = interaction_or_ctx.user
        else:
            guild = interaction_or_ctx.guild
            channel = interaction_or_ctx.channel
            user = interaction_or_ctx.author

        gid = guild.id
        vc = guild.voice_client

        # after 콜백: 다음 곡 재생 예약
        def _after_play(error):
            if error:
                print(f"[Music] 플레이 중 에러: {error}")
            # 재생 끝났으니 활동 시각 갱신(끝남 시점 기준)
            self._touch_activity(gid)
            asyncio.run_coroutine_threadsafe(self._play_next(interaction_or_ctx), self.bot.loop)

        vc.play(FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=_after_play)

        # 재생 시작 시점에 활동 갱신
        self._touch_activity(gid)

        # 임베드 + 버튼 UI
        embed = discord.Embed(title=info.get('title', 'Unknown'),
                              url=f"https://youtu.be/{info.get('id')}")
        if thumb := info.get('thumbnail'):
            embed.set_thumbnail(url=thumb)
        embed.add_field(name="요청자", value=user.mention)

        view = View()
        view.add_item(Button(label="⏸️ 일시정지", style=discord.ButtonStyle.secondary, custom_id="pause"))
        view.add_item(Button(label="▶️ 재개",   style=discord.ButtonStyle.secondary, custom_id="resume"))
        view.add_item(Button(label="⏹️ 정지",   style=discord.ButtonStyle.danger,    custom_id="stop"))
        view.add_item(Button(label="⏭️ 다음곡", style=discord.ButtonStyle.primary,  custom_id="skip"))

        await channel.send(embed=embed, view=view)

    async def _play_next(self, interaction_or_ctx):
        """트랙 종료 후 큐에서 다음 곡 재생"""
        guild = interaction_or_ctx.guild if isinstance(interaction_or_ctx, discord.Interaction) else interaction_or_ctx.guild
        gid = guild.id
        q = self.queue.get(gid, [])
        if not q:
            # 큐가 비었으면 활동 시간만 갱신(대기 시작)
            self._touch_activity(gid)
            return
        next_info = q.pop(0)
        self.queue[gid] = q
        await self._play_track(interaction_or_ctx, next_info)

    # ----------------------------
    # 명령어
    # ----------------------------
    @commands.command(name='join')
    async def join(self, ctx: commands.Context):
        """봇을 음성 채널에 참여시킵니다."""
        if ctx.author.voice and ctx.author.voice.channel:
            vc = ctx.voice_client
            if not vc:
                vc = await ctx.author.voice.channel.connect()
            await ctx.send(f"✅ 연결됨: {vc.channel}")
            self._touch_activity(ctx.guild.id)
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
        """!play <검색어> 또는 <URL>"""
        if query is None:
            return await ctx.send("❌ 사용법: `!play <검색어>`")

        # 음성 채널 연결 보장
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
        vc = ctx.voice_client
        gid = ctx.guild.id

        info = search_youtube_info(query)

        if vc.is_playing() or vc.is_paused():
            self.queue.setdefault(gid, []).append(info)
            await ctx.send(f"➕ 대기열에 추가: `{info.get('title','Unknown')}`")
            # 활동 갱신
            self._touch_activity(gid)
        else:
            await self._play_track(ctx, info)

    @commands.command(name='queue')
    async def _queue(self, ctx: commands.Context):
        q = self.queue.get(ctx.guild.id, [])
        if q:
            msg = '\n'.join(f"{i+1}. {item.get('title','Unknown')}" for i, item in enumerate(q))
            await ctx.send(f"🎵 대기열:\n{msg}")
        else:
            await ctx.send("대기열이 비어있습니다.")
        self._touch_activity(ctx.guild.id)

    @commands.command(name='clear')
    async def clear(self, ctx: commands.Context):
        self.queue[ctx.guild.id] = []
        await ctx.send("🗑️ 대기열을 비웠습니다.")
        self._touch_activity(ctx.guild.id)

    # ----------------------------
    # 버튼 인터랙션
    # ----------------------------
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        custom_id = interaction.data.get('custom_id') if interaction.data else None
        if custom_id not in {'pause', 'resume', 'stop', 'skip'}:
            return

        guild = interaction.guild
        vc = guild.voice_client if guild else None
        gid = guild.id if guild else 0

        if not vc:
            return await interaction.response.send_message("❌ 봇이 음성 채널에 없습니다.", ephemeral=True)

        # 각 버튼 처리
        if custom_id == 'pause' and vc.is_playing():
            vc.pause()
            self._touch_activity(gid)
            return await interaction.response.send_message("⏸️ 일시정지했습니다.", ephemeral=True)

        if custom_id == 'resume' and vc.is_paused():
            vc.resume()
            self._touch_activity(gid)
            return await interaction.response.send_message("▶️ 재개했습니다.", ephemeral=True)

        if custom_id == 'stop':
            vc.stop()
            self._touch_activity(gid)
            return await interaction.response.send_message("⏹️ 재생을 중단했습니다.", ephemeral=True)

        if custom_id == 'skip':
            q = self.queue.get(gid, [])
            if not q:
                return await interaction.response.send_message("⚠️ 더 재생할 곡이 없습니다.", ephemeral=True)
            vc.stop()  # after 콜백에서 next가 이어짐
            self._touch_activity(gid)
            return await interaction.response.send_message("⏭️ 다음곡으로 넘어갑니다.", ephemeral=True)

    # ----------------------------
    # 음성 상태 이벤트: 혼자 남으면 즉시 나가기
    # ----------------------------
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        # 유저가 나가거나 이동했을 때 체크 (봇은 무시)
        if member.bot:
            return
        guild = member.guild
        vc = guild.voice_client
        if not vc or not vc.channel:
            return
        try:
            # 채널에 봇만 남았으면 즉시 나가기
            if len([m for m in vc.channel.members if not m.bot]) == 0:
                await vc.disconnect()
                print(f"[AutoLeave] {guild.name}: 유저 없음 감지 → 즉시 나감")
        except Exception as e:
            print(f"[AutoLeave] on_voice_state_update 오류: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
