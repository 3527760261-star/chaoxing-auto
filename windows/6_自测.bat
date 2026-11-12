@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 不登录、不联网，用本地 mock 验证提交门、答案匹配、状态去重。
python "%~dp0tools\selftest.py"
pause
