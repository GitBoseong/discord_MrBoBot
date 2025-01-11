# utils/youtube.py
import yt_dlp

def get_youtube_info(search):
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(f"ytsearch:{search}", download=False)
        return info_dict['entries'][0]
