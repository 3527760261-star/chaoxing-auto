@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在删除 ChaoxingAutoWatch...
schtasks /delete /tn "ChaoxingAutoWatch" /f
if errorlevel 1 (
echo 删除失败：可能任务不存在，或请右键以管理员身份运行。
pause
exit /b 1
)
echo 已删除每小时计划任务。
pause
