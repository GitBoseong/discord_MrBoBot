from yt_dlp import YoutubeDL

# YDL_OPTS = {
#     'format': 'bestaudio/best',
#     'noplaylist': True,
#     'quiet': True,
#     'default_search': 'ytsearch1',
# }

YDL_OPTS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    # 아래 옵션들이 스트리밍 문제를 줄여줍니다
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    # 최근 이슈 대응을 위한 인자
    'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
}

def search_youtube_info(query: str) -> dict:
    """
    검색어로 가장 유사한 YouTube 동영상의 정보 딕셔너리를 반환합니다.
    """
    with YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(query, download=False)
        if 'entries' in info:
            return info['entries'][0]
        return info

# 편의를 위해 간단 스트림 URL만 가져오는 함수도 제공

def search_youtube(query: str) -> str:
    """
    검색어로 가장 유사한 YouTube 동영상의 스트림 URL을 반환합니다.
    """
    info = search_youtube_info(query)
    return info.get('url')