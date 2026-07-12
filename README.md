# MrBoBot

Discord 음성 채널에서 YouTube 음악을 검색, 재생, 일시정지, 넘기기, 정지하고 큐를 관리하는 음악 봇입니다.

## 주요 기능

- `/play`로 YouTube URL 또는 검색어 즉시 재생
- `/search`로 검색 결과 5개 중 선택 재생
- 재생 메시지의 버튼으로 일시정지, 다시 재생, 넘기기, 정지, 큐 보기
- `/queue`, `/remove`, `/clear`, `/shuffle`로 큐 관리
- 음성 채널에 사람이 없거나 일정 시간 비활성 상태면 자동 퇴장

## 명령어

| 명령어 | 설명 |
| --- | --- |
| `/play <검색어 또는 URL>` | 곡을 바로 재생하거나 큐에 추가합니다. |
| `/search <검색어>` | YouTube 검색 결과에서 곡을 골라 재생합니다. |
| `/queue` | 현재 곡과 대기열을 보여줍니다. |
| `/now` | 현재 재생 중인 곡을 보여줍니다. |
| `/pause` | 현재 곡을 일시정지합니다. |
| `/resume` | 일시정지된 곡을 다시 재생합니다. |
| `/skip` | 현재 곡을 넘깁니다. |
| `/stop` | 재생을 멈추고 큐를 비운 뒤 음성 채널에서 나갑니다. |
| `/remove <번호>` | 큐에서 해당 번호의 곡을 제거합니다. |
| `/clear` | 큐를 모두 비웁니다. |
| `/shuffle` | 큐 순서를 섞습니다. |
| `!helpme` | 간단한 도움말을 보여줍니다. |

## 설치 및 실행

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

`.env` 파일에 Discord 봇 토큰을 설정합니다.

```env
DISCORD_TOKEN=your_discord_bot_token
```

봇을 실행합니다.

```bash
python bot.py
```

처음 실행하거나 명령어가 바뀐 뒤에는 Discord의 `/` 명령 목록에 반영되기까지 잠시 걸릴 수 있습니다.
