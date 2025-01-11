# commands/music.py
import discord
from discord.ext import commands
from discord.ui import Button, View
from utils.youtube import get_youtube_info

music_queue = []
current_song_title = None

def setup_music_commands(bot):
    @bot.command(name='play')
    async def play(ctx, *, search: str):
        global current_song_title
        info = get_youtube_info(search)
        url = info['webpage_url']
        title = info['title']
        thumbnail = info['thumbnail']
        voice_channel = ctx.author.voice.channel

        if not ctx.voice_client:
            await voice_channel.connect()

        if ctx.voice_client.is_playing():
            music_queue.append((title, url))
            await ctx.send(f"**{title}** added to the queue.")
            return

        ctx.voice_client.stop()
        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        YDL_OPTIONS = {'format': "bestaudio"}
        vc = ctx.voice_client

        with discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS) as audio_source:
            vc.play(audio_source, after=lambda e: check_queue(ctx))

        current_song_title = title

        # Embed 생성
        embed = discord.Embed(title="Now Playing", description=f"[{title}]({url})", color=discord.Color.blue())
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
                check_queue(ctx)

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

    def check_queue(ctx):
        global current_song_title
        if len(music_queue) > 0:
            next_song = music_queue.pop(0)
            bot.loop.create_task(play(ctx, search=next_song[1]))
        else:
            current_song_title = None
