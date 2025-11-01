@echo off
REM === MrBoBot 실행 스크립트 ===

REM 배치파일이 있는 폴더로 이동
cd /d "%~dp0"

REM venv 활성화
call venv\Scripts\activate.bat

REM 봇 실행
python bot.py

REM 창이 닫히지 않도록
pause
