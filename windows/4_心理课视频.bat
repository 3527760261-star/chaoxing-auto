@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 原速播放、页面静音，看到 96%% 即停，复核任务点是否 +1。
python "%~dp0watch_video.py"
pause
