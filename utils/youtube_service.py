import yt_dlp

class YouTubeService:
    """
    YouTube 검색/스트림 URL 추출을 담당하는 서비스 클래스.
    """
    YDL_OPTS = {
        'format': 'bestaudio/best',
        'noplaylist': True,
    }

    @classmethod
    def search(cls, query: str) -> dict:
        """
        검색어로 유튜브 동영상 정보 반환 (ytsearch).
        """
        with yt_dlp.YoutubeDL(cls.YDL_OPTS) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            return info['entries'][0]

    @classmethod
    def get_stream_url(cls, video_url: str) -> str:
        """
        실제 오디오 스트림 URL만 추출.
        """
        with yt_dlp.YoutubeDL(cls.YDL_OPTS) as ydl:
            info = ydl.extract_info(video_url, download=False)
            # audio-only 포맷 선택
            for f in info['formats']:
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    return f['url']
            return info['url']
