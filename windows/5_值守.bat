@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 每小时一轮：巡检 - 填答 - 播放心理课视频。按 Ctrl+C 停止。
python "%~dp0watch.py"
pause
