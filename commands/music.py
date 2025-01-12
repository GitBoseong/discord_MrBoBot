import discord
from discord.ext import commands
from discord.ui import Button, View
from yt_dlp import YoutubeDL

music_queue = []
current_song_title = None

# YouTube에서 스트림 URL을 가져오는 함수
def get_stream_url(youtube_url, format_id="140"):
    """YouTube에서 지정된 형식의 스트림 URL 가져오기"""
    ydl_opts = {
        'format': format_id,  # 오디오 스트림 포맷
        'quiet': True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        return info['url'], info['title'], info['thumbnail']

# Discord 봇 명령어 설정
def setup_music_commands(bot):
    @bot.command(name='play')
    async def play(ctx, *, search: str):
        global current_song_title
        # 스트림 URL, 제목, 썸네일 가져오기
        stream_url, title, thumbnail = get_stream_url(search)
        voice_channel = ctx.author.voice.channel

        # 음성 채널에 연결
        if not ctx.voice_client:
            await voice_channel.connect()

        # 현재 재생 중일 경우 대기열에 추가
        if ctx.voice_client.is_playing():
            music_queue.append((title, stream_url))
            await ctx.send(f"**{title}** added to the queue.")
            return

        # 새로운 곡 재생
        ctx.voice_client.stop()
        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -user_agent "Mozilla/5.0"',
            'options': '-vn'
        }
        vc = ctx.voice_client
        audio_source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
        vc.play(audio_source, after=lambda e: bot.loop.create_task(check_queue(ctx)))

        current_song_title = title

        # Embed 생성
        embed = discord.Embed(title="Now Playing", description=f"[{title}]({search})", color=discord.Color.blue())
        embed.set_thumbnail(url=thumbnail)

        # 버튼 생성
        stop_button = Button(label="Stop", style=discord.ButtonStyle.danger)
        pause_button = Button(label="Pause", style=discord.ButtonStyle.primary)
        resume_button = Button(label="Resume", style=discord.ButtonStyle.success)
        skip_button = Button(label="Skip", style=discord.ButtonStyle.secondary)

        # 버튼 콜백 함수
        async def stop_callback(interaction):
            vc.stop()
            await interaction.response.send_message("음악이 종료되었습니다.")

        async def pause_callback(interaction):
            if vc and vc.is_playing():
                vc.pause()
                await interaction.response.send_message("음악 재생이 중지되었습니다.")
            else:
                await interaction.response.send_message("음악이 재생 중이 아닙니다.")

        async def resume_callback(interaction):
            if vc and vc.is_paused():
                vc.resume()
                await interaction.response.send_message("음악 재생이 재개되었습니다.")
            else:
                await interaction.response.send_message("재생 중지된 음악이 없습니다.")

        async def skip_callback(interaction):
            global current_song_title
            if vc.is_playing():
                skipped_song_title = current_song_title
                vc.stop()
                current_song_title = None
                await interaction.response.send_message(f"**{skipped_song_title}** has been skipped.")
                await check_queue(ctx)

        # 버튼에 콜백 연결
        stop_button.callback = stop_callback
        pause_button.callback = pause_callback
        resume_button.callback = resume_callback
        skip_button.callback = skip_callback

        # View에 버튼 추가
        view = View()
        view.add_item(stop_button)
        view.add_item(pause_button)
        view.add_item(resume_button)
        view.add_item(skip_button)

        await ctx.send(embed=embed, view=view)

    @bot.command(name='playlist')
    async def playlist(ctx):
        if len(music_queue) == 0:
            await ctx.send("The playlist is empty.")
        else:
            queue_list = "\n".join([f"{index+1}. {song[0]}" for index, song in enumerate(music_queue)])
            await ctx.send(f"**Playlist:**\n{queue_list}")

    @bot.command(name='remove')
    async def remove(ctx, position: int):
        if 0 < position <= len(music_queue):
            removed_song = music_queue.pop(position - 1)
            await ctx.send(f"**{removed_song[0]}** has been removed from the queue.")
        else:
            await ctx.send("Invalid position. Please provide a valid number from the playlist.")

    @bot.command(name='help')
    async def help_command(ctx):
        help_text = (
            "**Commands:**\n"
            "`!play <song>` - Play a song or add it to the queue.\n"
            "`!playlist` - Show the current music queue.\n"
            "`!remove <number>` - Remove a specific song from the queue.\n"
            "`!stop` - Stop the current song.\n"
            "`!pause` - Pause the current song.\n"
            "`!resume` - Resume the paused song.\n"
            "`!skip` - Skip the current song."
        )
        await ctx.send(help_text)

    async def check_queue(ctx):
        """재생 대기열을 확인하고 다음 곡 재생"""
        global current_song_title
        if len(music_queue) > 0:
            next_song = music_queue.pop(0)
            current_song_title = next_song[0]

            FFMPEG_OPTIONS = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -user_agent "Mozilla/5.0"',
                'options': '-vn'
            }
            vc = ctx.voice_client
            audio_source = discord.FFmpegPCMAudio(next_song[1], **FFMPEG_OPTIONS)
            vc.play(audio_source, after=lambda e: bot.loop.create_task(check_queue(ctx)))

            await ctx.send(f"Now playing: **{current_song_title}**")
        else:
            current_song_title = None
            await ctx.send("Queue is now empty.")
