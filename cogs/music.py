import asyncio
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Button, Select, View

from config import FFMPEG_OPTIONS
from utils.formatting import clamp_title, fmt_duration
from utils.youtube import get_youtube_info, search_youtube


AUTO_LEAVE_SECONDS = 180
MAX_QUEUE_DISPLAY = 10


@dataclass
class Track:
    title: str
    stream_url: str
    webpage_url: str
    thumbnail: Optional[str]
    duration: Optional[int]
    requester_id: int
    requester_name: str
    query: str

    @classmethod
    def from_info(cls, info: dict, requester: discord.abc.User, query: str) -> "Track":
        return cls(
            title=info.get("title") or "Unknown title",
            stream_url=info.get("url") or "",
            webpage_url=info.get("webpage_url") or info.get("original_url") or query,
            thumbnail=info.get("thumbnail"),
            duration=info.get("duration"),
            requester_id=requester.id,
            requester_name=requester.display_name,
            query=query,
        )


class GuildMusicState:
    def __init__(self) -> None:
        self.queue: List[Track] = []
        self.current: Optional[Track] = None
        self.now_message: Optional[discord.Message] = None
        self.text_channel: Optional[discord.abc.Messageable] = None
        self.last_active = discord.utils.utcnow()
        self.lock = asyncio.Lock()

    def touch(self) -> None:
        self.last_active = discord.utils.utcnow()


class Music(commands.Cog):
    """Music playback, YouTube search, queue management, and player controls."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.states: Dict[int, GuildMusicState] = {}
        self.inactive_timeout = AUTO_LEAVE_SECONDS
        self._auto_leave_task.start()

    def cog_unload(self) -> None:
        self._auto_leave_task.cancel()

    def state_for(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self.states:
            self.states[guild_id] = GuildMusicState()
        return self.states[guild_id]

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        message = f"명령 처리 중 문제가 생겼어요: {error}"
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def ensure_voice(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        if not interaction.guild:
            await self._reply(interaction, "서버 안에서만 사용할 수 있어요.", ephemeral=True)
            return None

        user = interaction.user
        if not isinstance(user, discord.Member) or not user.voice or not user.voice.channel:
            await self._reply(interaction, "먼저 음성 채널에 들어가 주세요.", ephemeral=True)
            return None

        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.channel != user.voice.channel:
            await voice_client.move_to(user.voice.channel)
            return voice_client

        if not voice_client:
            voice_client = await user.voice.channel.connect()

        self.state_for(interaction.guild.id).touch()
        return voice_client

    async def _reply(
        self,
        interaction: discord.Interaction,
        content: Optional[str] = None,
        *,
        embed: Optional[discord.Embed] = None,
        view: Optional[View] = None,
        ephemeral: bool = False,
    ) -> None:
        kwargs = {"ephemeral": ephemeral}
        if content is not None:
            kwargs["content"] = content
        if embed is not None:
            kwargs["embed"] = embed
        if view is not None:
            kwargs["view"] = view

        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)

    async def _load_track(self, query: str, requester: discord.abc.User) -> Track:
        info = await asyncio.to_thread(get_youtube_info, query)
        return Track.from_info(info, requester, query)

    async def _search_tracks(
        self, query: str, requester: discord.abc.User, limit: int = 5
    ) -> List[Track]:
        infos = await asyncio.to_thread(search_youtube, query, limit)
        return [Track.from_info(info, requester, query) for info in infos if info and info.get("url")]

    async def enqueue_or_play(
        self, interaction: discord.Interaction, track: Track, *, announce: bool = True
    ) -> None:
        if not interaction.guild:
            return

        voice_client = await self.ensure_voice(interaction)
        if not voice_client:
            return

        state = self.state_for(interaction.guild.id)
        state.text_channel = interaction.channel

        async with state.lock:
            if voice_client.is_playing() or voice_client.is_paused() or state.current:
                state.queue.append(track)
                state.touch()
                if announce:
                    await self._reply(
                        interaction,
                        f"큐에 추가했어요: **{clamp_title(track.title)}** "
                        f"(`{fmt_duration(track.duration)}`)",
                    )
                await self._update_nowplaying(interaction.guild)
                return

            if announce and not interaction.response.is_done():
                await interaction.response.defer()
            await self._start_track(interaction.guild, voice_client, track, state)
            if announce:
                await self._reply(
                    interaction,
                    f"재생할게요: **{clamp_title(track.title)}** (`{fmt_duration(track.duration)}`)",
                )

    async def _start_track(
        self,
        guild: discord.Guild,
        voice_client: discord.VoiceClient,
        track: Track,
        state: GuildMusicState,
    ) -> None:
        if not track.stream_url:
            refreshed = await asyncio.to_thread(get_youtube_info, track.webpage_url or track.query)
            track.stream_url = refreshed.get("url") or track.stream_url

        state.current = track
        state.touch()

        def after_play(error: Optional[Exception]) -> None:
            if error:
                print(f"[Music] playback error in {guild.name}: {error}")
            asyncio.run_coroutine_threadsafe(self._play_next(guild), self.bot.loop)

        source = discord.FFmpegPCMAudio(track.stream_url, **FFMPEG_OPTIONS)
        voice_client.play(source, after=after_play)
        await self._send_nowplaying(guild, paused=False)
        await self._set_presence(track)

    async def _play_next(self, guild: discord.Guild) -> None:
        state = self.state_for(guild.id)
        async with state.lock:
            state.current = None
            voice_client = guild.voice_client
            if not voice_client:
                return

            if not state.queue:
                state.touch()
                await self._update_nowplaying(guild, paused=False)
                return

            next_track = state.queue.pop(0)
            await self._start_track(guild, voice_client, next_track, state)

    async def _set_presence(self, track: Optional[Track]) -> None:
        try:
            if track:
                await self.bot.change_presence(
                    activity=discord.Activity(
                        type=discord.ActivityType.listening,
                        name=clamp_title(track.title, 48),
                    )
                )
            else:
                await self.bot.change_presence(activity=None)
        except discord.HTTPException:
            pass

    def _player_embed(self, guild: discord.Guild, paused: bool = False) -> discord.Embed:
        state = self.state_for(guild.id)
        track = state.current

        if not track:
            embed = discord.Embed(title="재생 대기 중", description="큐가 비어 있어요.", color=0x2ECC71)
            embed.set_footer(text="음악을 찾으려면 /play 또는 /search 를 사용하세요.")
            return embed

        embed = discord.Embed(
            title=clamp_title(track.title),
            url=track.webpage_url,
            color=0x5865F2,
        )
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        embed.add_field(name="요청자", value=track.requester_name, inline=True)
        embed.add_field(name="길이", value=fmt_duration(track.duration), inline=True)
        embed.add_field(name="큐", value=f"{len(state.queue)}곡 대기 중", inline=True)

        if state.queue:
            upcoming = "\n".join(
                f"`{idx}.` {clamp_title(item.title, 55)}"
                for idx, item in enumerate(state.queue[:5], start=1)
            )
            embed.add_field(name="다음 곡", value=upcoming, inline=False)

        embed.set_footer(text="일시정지됨" if paused else "재생 중")
        return embed

    async def _send_nowplaying(self, guild: discord.Guild, paused: bool = False) -> None:
        state = self.state_for(guild.id)
        if not state.text_channel:
            return

        embed = self._player_embed(guild, paused)
        view = PlayerControls(self, guild.id, paused=paused)
        state.now_message = await state.text_channel.send(embed=embed, view=view)

    async def _update_nowplaying(self, guild: discord.Guild, paused: bool = False) -> None:
        state = self.state_for(guild.id)
        if state.now_message:
            try:
                embed = self._player_embed(guild, paused)
                view = PlayerControls(self, guild.id, paused=paused)
                await state.now_message.edit(embed=embed, view=view)
                return
            except discord.HTTPException:
                state.now_message = None

        await self._send_nowplaying(guild, paused=paused)

    async def pause_player(self, interaction: discord.Interaction) -> None:
        voice_client = interaction.guild.voice_client if interaction.guild else None
        if not voice_client or not voice_client.is_playing():
            await self._reply(interaction, "지금 재생 중인 곡이 없어요.", ephemeral=True)
            return
        voice_client.pause()
        self.state_for(interaction.guild.id).touch()
        await self._reply(interaction, "일시정지했어요.", ephemeral=True)
        await self._update_nowplaying(interaction.guild, paused=True)

    async def resume_player(self, interaction: discord.Interaction) -> None:
        voice_client = interaction.guild.voice_client if interaction.guild else None
        if not voice_client or not voice_client.is_paused():
            await self._reply(interaction, "일시정지된 곡이 없어요.", ephemeral=True)
            return
        voice_client.resume()
        self.state_for(interaction.guild.id).touch()
        await self._reply(interaction, "다시 재생할게요.", ephemeral=True)
        await self._update_nowplaying(interaction.guild, paused=False)

    async def skip_player(self, interaction: discord.Interaction) -> None:
        voice_client = interaction.guild.voice_client if interaction.guild else None
        if not voice_client or not (voice_client.is_playing() or voice_client.is_paused()):
            await self._reply(interaction, "넘길 곡이 없어요.", ephemeral=True)
            return
        voice_client.stop()
        self.state_for(interaction.guild.id).touch()
        await self._reply(interaction, "다음 곡으로 넘겼어요.", ephemeral=True)

    async def stop_player(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        voice_client = interaction.guild.voice_client
        state = self.state_for(interaction.guild.id)
        state.queue.clear()
        state.current = None
        state.touch()

        if voice_client:
            voice_client.stop()
            await voice_client.disconnect()

        await self._set_presence(None)
        await self._reply(interaction, "재생을 멈추고 큐를 비웠어요.", ephemeral=True)
        await self._update_nowplaying(interaction.guild)

    async def show_queue(self, interaction: discord.Interaction, *, ephemeral: bool = False) -> None:
        if not interaction.guild:
            return
        state = self.state_for(interaction.guild.id)
        embed = discord.Embed(title="음악 큐", color=0x2ECC71)

        if state.current:
            embed.add_field(
                name="지금 재생",
                value=f"{clamp_title(state.current.title, 70)} (`{fmt_duration(state.current.duration)}`)",
                inline=False,
            )

        if state.queue:
            rows = []
            for idx, track in enumerate(state.queue[:MAX_QUEUE_DISPLAY], start=1):
                rows.append(f"`{idx}.` {clamp_title(track.title, 60)} (`{fmt_duration(track.duration)}`)")
            if len(state.queue) > MAX_QUEUE_DISPLAY:
                rows.append(f"...외 {len(state.queue) - MAX_QUEUE_DISPLAY}곡")
            embed.add_field(name="대기열", value="\n".join(rows), inline=False)
        else:
            embed.add_field(name="대기열", value="비어 있어요.", inline=False)

        view = QueueControls(self, interaction.guild.id) if state.queue else None
        await self._reply(interaction, embed=embed, view=view, ephemeral=ephemeral)

    @tasks.loop(seconds=15)
    async def _auto_leave_task(self) -> None:
        for voice_client in list(self.bot.voice_clients):
            guild = voice_client.guild
            state = self.state_for(guild.id)
            humans = [member for member in voice_client.channel.members if not member.bot]

            if not humans:
                await voice_client.disconnect()
                state.current = None
                state.queue.clear()
                state.touch()
                continue

            inactive_for = (discord.utils.utcnow() - state.last_active).total_seconds()
            if not voice_client.is_playing() and not voice_client.is_paused() and inactive_for > self.inactive_timeout:
                await voice_client.disconnect()
                state.current = None

    @_auto_leave_task.before_loop
    async def _before_auto_leave(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot:
            return
        voice_client = member.guild.voice_client
        if not voice_client or not voice_client.channel:
            return
        humans = [item for item in voice_client.channel.members if not item.bot]
        if not humans:
            state = self.state_for(member.guild.id)
            state.queue.clear()
            state.current = None
            await voice_client.disconnect()

    @app_commands.command(name="play", description="YouTube URL 또는 검색어로 음악을 재생합니다.")
    @app_commands.describe(query="검색어 또는 YouTube URL")
    async def slash_play(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        track = await self._load_track(query, interaction.user)
        await self.enqueue_or_play(interaction, track, announce=True)

    @app_commands.command(name="search", description="YouTube 검색 결과에서 골라 재생합니다.")
    @app_commands.describe(query="검색어")
    async def slash_search(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer(ephemeral=True)
        tracks = await self._search_tracks(query, interaction.user)
        if not tracks:
            await interaction.followup.send("검색 결과를 찾지 못했어요.", ephemeral=True)
            return

        embed = discord.Embed(
            title="검색 결과",
            description="재생할 곡을 선택하세요.",
            color=0x5865F2,
        )
        for idx, track in enumerate(tracks, start=1):
            embed.add_field(
                name=f"{idx}. {clamp_title(track.title, 55)}",
                value=fmt_duration(track.duration),
                inline=False,
            )
        await interaction.followup.send(
            embed=embed,
            view=SearchResults(self, interaction.guild_id, tracks),
            ephemeral=True,
        )

    @app_commands.command(name="queue", description="현재 재생 중인 곡과 대기열을 봅니다.")
    async def slash_queue(self, interaction: discord.Interaction) -> None:
        await self.show_queue(interaction)

    @app_commands.command(name="now", description="현재 재생 중인 곡을 표시합니다.")
    async def slash_now(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        embed = self._player_embed(interaction.guild)
        await self._reply(interaction, embed=embed)

    @app_commands.command(name="pause", description="현재 곡을 일시정지합니다.")
    async def slash_pause(self, interaction: discord.Interaction) -> None:
        await self.pause_player(interaction)

    @app_commands.command(name="resume", description="일시정지된 곡을 다시 재생합니다.")
    async def slash_resume(self, interaction: discord.Interaction) -> None:
        await self.resume_player(interaction)

    @app_commands.command(name="skip", description="현재 곡을 넘깁니다.")
    async def slash_skip(self, interaction: discord.Interaction) -> None:
        await self.skip_player(interaction)

    @app_commands.command(name="stop", description="재생을 멈추고 음성 채널에서 나갑니다.")
    async def slash_stop(self, interaction: discord.Interaction) -> None:
        await self.stop_player(interaction)

    @app_commands.command(name="clear", description="대기열을 모두 비웁니다.")
    async def slash_clear(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        state = self.state_for(interaction.guild.id)
        state.queue.clear()
        state.touch()
        await self._reply(interaction, "큐를 비웠어요.", ephemeral=True)
        await self._update_nowplaying(interaction.guild)

    @app_commands.command(name="remove", description="대기열에서 특정 번호의 곡을 제거합니다.")
    @app_commands.describe(index="큐 번호")
    async def slash_remove(self, interaction: discord.Interaction, index: app_commands.Range[int, 1, 100]) -> None:
        if not interaction.guild:
            return
        state = self.state_for(interaction.guild.id)
        if index > len(state.queue):
            await self._reply(interaction, "해당 번호의 곡이 큐에 없어요.", ephemeral=True)
            return
        removed = state.queue.pop(index - 1)
        state.touch()
        await self._reply(interaction, f"제거했어요: **{clamp_title(removed.title)}**", ephemeral=True)
        await self._update_nowplaying(interaction.guild)

    @app_commands.command(name="shuffle", description="대기열 순서를 섞습니다.")
    async def slash_shuffle(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        state = self.state_for(interaction.guild.id)
        if len(state.queue) < 2:
            await self._reply(interaction, "섞을 곡이 충분하지 않아요.", ephemeral=True)
            return
        random.shuffle(state.queue)
        state.touch()
        await self._reply(interaction, "큐를 섞었어요.", ephemeral=True)
        await self._update_nowplaying(interaction.guild)


class PlayerControls(View):
    def __init__(self, cog: Music, guild_id: int, paused: bool = False) -> None:
        super().__init__(timeout=600)
        self.cog = cog
        self.guild_id = guild_id

        for child in self.children:
            if isinstance(child, Button):
                if child.custom_id == "music:pause":
                    child.disabled = paused
                elif child.custom_id == "music:resume":
                    child.disabled = not paused

    @discord.ui.button(label="일시정지", style=discord.ButtonStyle.secondary, custom_id="music:pause")
    async def pause(self, interaction: discord.Interaction, button: Button) -> None:
        await self.cog.pause_player(interaction)

    @discord.ui.button(label="다시 재생", style=discord.ButtonStyle.secondary, custom_id="music:resume")
    async def resume(self, interaction: discord.Interaction, button: Button) -> None:
        await self.cog.resume_player(interaction)

    @discord.ui.button(label="넘기기", style=discord.ButtonStyle.primary, custom_id="music:skip")
    async def skip(self, interaction: discord.Interaction, button: Button) -> None:
        await self.cog.skip_player(interaction)

    @discord.ui.button(label="큐 보기", style=discord.ButtonStyle.secondary, custom_id="music:queue")
    async def queue(self, interaction: discord.Interaction, button: Button) -> None:
        await self.cog.show_queue(interaction, ephemeral=True)

    @discord.ui.button(label="정지", style=discord.ButtonStyle.danger, custom_id="music:stop")
    async def stop(self, interaction: discord.Interaction, button: Button) -> None:
        await self.cog.stop_player(interaction)


class SearchResults(View):
    def __init__(self, cog: Music, guild_id: Optional[int], tracks: Sequence[Track]) -> None:
        super().__init__(timeout=120)
        self.cog = cog
        self.guild_id = guild_id
        self.tracks = list(tracks)
        self.add_item(SearchSelect(cog, self.tracks))


class SearchSelect(Select):
    def __init__(self, cog: Music, tracks: Sequence[Track]) -> None:
        self.cog = cog
        self.tracks = list(tracks)
        options = [
            discord.SelectOption(
                label=clamp_title(track.title, 90),
                description=fmt_duration(track.duration),
                value=str(index),
            )
            for index, track in enumerate(self.tracks)
        ]
        super().__init__(placeholder="재생할 곡 선택", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        track = self.tracks[int(self.values[0])]
        await interaction.response.defer(ephemeral=True)
        await self.cog.enqueue_or_play(interaction, track, announce=False)
        await interaction.followup.send(f"선택했어요: **{clamp_title(track.title)}**", ephemeral=True)


class QueueControls(View):
    def __init__(self, cog: Music, guild_id: int) -> None:
        super().__init__(timeout=120)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="첫 곡 제거", style=discord.ButtonStyle.secondary, custom_id="queue:remove_first")
    async def remove_first(self, interaction: discord.Interaction, button: Button) -> None:
        if not interaction.guild:
            return
        state = self.cog.state_for(interaction.guild.id)
        if not state.queue:
            await self.cog._reply(interaction, "큐가 비어 있어요.", ephemeral=True)
            return
        removed = state.queue.pop(0)
        state.touch()
        await self.cog._reply(interaction, f"제거했어요: **{clamp_title(removed.title)}**", ephemeral=True)
        await self.cog._update_nowplaying(interaction.guild)

    @discord.ui.button(label="섞기", style=discord.ButtonStyle.secondary, custom_id="queue:shuffle")
    async def shuffle(self, interaction: discord.Interaction, button: Button) -> None:
        if not interaction.guild:
            return
        state = self.cog.state_for(interaction.guild.id)
        random.shuffle(state.queue)
        state.touch()
        await self.cog._reply(interaction, "큐를 섞었어요.", ephemeral=True)
        await self.cog._update_nowplaying(interaction.guild)

    @discord.ui.button(label="모두 비우기", style=discord.ButtonStyle.danger, custom_id="queue:clear")
    async def clear(self, interaction: discord.Interaction, button: Button) -> None:
        if not interaction.guild:
            return
        state = self.cog.state_for(interaction.guild.id)
        state.queue.clear()
        state.touch()
        await self.cog._reply(interaction, "큐를 비웠어요.", ephemeral=True)
        await self.cog._update_nowplaying(interaction.guild)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
