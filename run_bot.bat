@echo off
REM === MrBoBot 실행 스크립트 ===

REM 현재 배치파일이 위치한 디렉터리로 이동
cd /d "%~dp0"

REM 가상환경 활성화
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [오류] 가상환경(venv)이 존재하지 않습니다.
    pause
    exit /b
)

REM 봇 실행
python bot.py

