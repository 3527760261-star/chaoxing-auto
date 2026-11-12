@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 将打开 Edge，请自己扫码登录学习通，并勾选「下次自动登录」。
echo 本脚本绝不问你要账号密码。
python "%~dp0login.py"
pause
