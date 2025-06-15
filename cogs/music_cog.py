# music_cog.py

import discord
from discord.ext import commands
from discord import FFmpegPCMAudio
from discord.ui import View, Button
from config import FFMPEG_OPTIONS
from utils.youtube import search_youtube_info

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild.id 별로 대기열을 리스트로 관리
        self.queue: dict[int, list[dict]] = {}

    async def _play_track(self, interaction_or_ctx, info: dict):
        """실제 오디오 재생 및 임베드+버튼 메시지 전송"""
        # interaction 또는 ctx 로부터 guild, vc, 채널 가져오기
        if isinstance(interaction_or_ctx, discord.Interaction):
            guild = interaction_or_ctx.guild
            channel = interaction_or_ctx.channel
        else:
            guild = interaction_or_ctx.guild
            channel = interaction_or_ctx.channel

        vc = guild.voice_client
        # 똑같이 VC 연결은 이미 되어 있다고 가정
        
        # 재생
        vc.play(FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS))

        # 임베드 + 버튼
        embed = discord.Embed(
            title=info.get('title', 'Unknown'),
            url=f"https://youtu.be/{info.get('id')}"
        )
        if thumb := info.get('thumbnail'):
            embed.set_thumbnail(url=thumb)
        embed.add_field(name="요청자", value=interaction_or_ctx.user.mention if isinstance(interaction_or_ctx, discord.Interaction) else interaction_or_ctx.author.mention)

        view = View()
        view.add_item(Button(label="⏸️ 일시정지", style=discord.ButtonStyle.secondary, custom_id="pause"))
        view.add_item(Button(label="▶️ 재개", style=discord.ButtonStyle.secondary, custom_id="resume"))
        view.add_item(Button(label="⏹️ 정지", style=discord.ButtonStyle.danger,    custom_id="stop"))
        view.add_item(Button(label="⏭️ 다음곡", style=discord.ButtonStyle.primary,  custom_id="skip"))

        await channel.send(embed=embed, view=view)

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
        if vc.is_playing():
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
            # 재생 전 확인
            if not vc:
                return await interaction.response.send_message("❌ 봇이 음성 채널에 없습니다.", ephemeral=True)

            # 일시정지
            if custom_id == 'pause' and vc.is_playing():
                vc.pause()
                return await interaction.response.send_message("⏸️ 일시정지했습니다.", ephemeral=True)

            # 재개
            if custom_id == 'resume' and vc.is_paused():
                vc.resume()
                return await interaction.response.send_message("▶️ 재개했습니다.", ephemeral=True)

            # 정지
            if custom_id == 'stop':
                vc.stop()
                # 선택적으로 큐도 비우고 싶다면:
                # self.queue[gid] = []
                return await interaction.response.send_message("⏹️ 재생을 중단했습니다.", ephemeral=True)

            # 다음곡
            if custom_id == 'skip':
                # 큐에 곡이 있는지
                q = self.queue.get(gid, [])
                if not q:
                    return await interaction.response.send_message("⚠️ 더 재생할 곡이 없습니다.", ephemeral=True)

                # 현재 재생 중지
                vc.stop()
                # 큐 맨 앞 곡 꺼내서 재생
                next_info = q.pop(0)
                # 남은 큐 갱신
                self.queue[gid] = q
                # 새 곡 재생 및 메시지
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
