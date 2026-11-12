@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 将注册计划任务，每小时跑一次 watch.py --once。
echo 需要管理员权限；如果弹 UAC，请点「是」。
schtasks /create /tn "ChaoxingAutoWatch" /tr "\"%~dp0watch.py\" --once" /sc hourly /mo 1 /f
if errorlevel 1 (
echo 注册失败：请右键本 bat 选择「以管理员身份运行」再试。
pause
exit /b 1
)
echo 注册成功：每小时自动跑一轮（单轮超时 900 秒自动结束）。
echo 注意：计划任务跑的是 python 脚本，请确认.py 已关联 Python；否则把 /tr 改成 python.exe 的完整路径加脚本路径。
pause
