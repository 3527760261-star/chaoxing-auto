@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 只读巡检三门课的作业和任务点，不作答、不提交。
python "%~dp0scan.py"
pause
