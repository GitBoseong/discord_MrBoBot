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

from utils.formatting import clamp_title, fmt_duration
from discord.ui import View, button


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
        self.now_msg: Dict[int, discord.Message] = {}   # 길드별 NowPlaying 메시지
        self.current: Dict[int, dict] = {}              # 현재 트랙 info
        self.started_at: Dict[int, discord.utils.datetime] = {}  # 시작 시각(선택)


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
    async def _play_track(self, interaction_or_ctx, info: dict, *, new_request=False):
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

        # 요청자 표시 저장
        info["requester_mention"] = user.mention
        self.current[gid] = info

        # after 콜백: 다음 곡 재생 예약
        def _after_play(error):
            if error:
                print(f"[Music] 플레이 중 에러: {error}")
            self._touch_activity(gid)
            asyncio.run_coroutine_threadsafe(self._play_next(interaction_or_ctx), self.bot.loop)

        vc.play(FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=_after_play)

        # 재생 시작 시점 활동 갱신
        self._touch_activity(gid)

        # ▶ NowPlaying 카드: 새 요청이면 새 메시지, 자동이면 edit
        embed, view = self._build_nowplaying(guild, info, paused=False)

        if new_request:  # 새 요청이면 항상 새 메시지 생성
            self.now_msg[gid] = await channel.send(embed=embed, view=view)
        else:
            prev = self.now_msg.get(gid)
            if prev:
                try:
                    await prev.edit(embed=embed, view=view)
                except discord.HTTPException:
                    self.now_msg[gid] = await channel.send(embed=embed, view=view)
            else:
                self.now_msg[gid] = await channel.send(embed=embed, view=view)

        # 상태표시(현재 곡 제목)
        try:
            await self.bot.change_presence(
                activity=discord.Activity(type=discord.ActivityType.listening, name=info.get("title", "Music"))
            )
        except Exception:
            pass

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
        # 다음 곡 재생 시도 (새 메시지로 표시)
        await self._play_track(interaction_or_ctx, next_info, new_request=True)
        
    async def ctrl_pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client if interaction.guild else None
        if vc and vc.is_playing():
            vc.pause()
            self._touch_activity(interaction.guild.id)
            await interaction.response.send_message("⏸️ 일시정지했습니다.", ephemeral=True)
            await self._update_nowplaying(interaction.guild, paused=True)

    async def ctrl_resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client if interaction.guild else None
        if vc and vc.is_paused():
            vc.resume()
            self._touch_activity(interaction.guild.id)
            await interaction.response.send_message("▶️ 재개했습니다.", ephemeral=True)
            await self._update_nowplaying(interaction.guild, paused=False)

    async def ctrl_stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client if interaction.guild else None
        if vc:
            vc.stop()
            self._touch_activity(interaction.guild.id)
            await interaction.response.send_message("⏹️ 재생을 중단했습니다.", ephemeral=True)
            await self._update_nowplaying(interaction.guild, paused=False)

    async def ctrl_skip(self, interaction: discord.Interaction):
        guild = interaction.guild
        gid = guild.id
        q = self.queue.get(gid, [])
        if not q:
            return await interaction.response.send_message("⚠️ 더 재생할 곡이 없습니다.", ephemeral=True)
        vc = guild.voice_client
        if vc:
            vc.stop()  # after에서 _play_next 호출됨
        self._touch_activity(gid)
        await interaction.response.send_message("⏭️ 다음곡으로 넘어갑니다.", ephemeral=True)


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
            await self._play_track(ctx, info, new_request=True)

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

    def _build_nowplaying(self, guild: discord.Guild, info: dict, paused: bool = False) -> tuple[discord.Embed, View]:
        title = clamp_title(info.get("title", "Unknown"))
        yt_id = info.get("id")
        url = f"https://youtu.be/{yt_id}" if yt_id else info.get("url")
        thumb = info.get("thumbnail")
        requester = info.get("requester_mention", "Unknown")

        embed = discord.Embed(title=title, url=url, color=0x5865F2)
        if thumb:
            embed.set_thumbnail(url=thumb)
        embed.add_field(name="🎧 요청자", value=requester, inline=True)
        # info.get("duration") 있으면 초 단위로 넣어두세요(없어도 동작)
        embed.add_field(name="⏱ 길이", value=fmt_duration(info.get("duration")), inline=True)

        qlen = len(self.queue.get(guild.id, []))
        state = "일시정지" if paused else "재생 중"
        embed.set_footer(text=f"{state} · 대기열 {qlen}곡")

        view = PlayerControls(self, guild.id, paused=paused)
        return embed, view

    async def _update_nowplaying(self, guild: discord.Guild, paused: bool = False):
        msg = self.now_msg.get(guild.id)
        info = self.current.get(guild.id)
        if not (msg and info):
            return
        embed, view = self._build_nowplaying(guild, info, paused=paused)
        try:
            await msg.edit(embed=embed, view=view)
        except discord.HTTPException:
            pass

    
async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))


class PlayerControls(View):
    """재생 컨트롤 View: 콜백을 Music Cog 메서드로 위임"""
    def __init__(self, cog: "Music", guild_id: int, paused: bool):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        # 버튼 상태 토글
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "ctrl_pause":
                    child.disabled = paused
                elif child.custom_id == "ctrl_resume":
                    child.disabled = not paused

    @button(label="⏸️ 일시정지", style=discord.ButtonStyle.secondary, custom_id="ctrl_pause")
    async def _pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.ctrl_pause(interaction)

    @button(label="▶️ 재개", style=discord.ButtonStyle.secondary, custom_id="ctrl_resume")
    async def _resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.ctrl_resume(interaction)

    @button(label="⏹️ 정지", style=discord.ButtonStyle.danger, custom_id="ctrl_stop")
    async def _stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.ctrl_stop(interaction)

    @button(label="⏭️ 다음곡", style=discord.ButtonStyle.primary, custom_id="ctrl_skip")
    async def _skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.ctrl_skip(interaction)
