@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 巡检 - 按答案清单填答 - 暂时保存 - 重载核对 - 提交门判定。
echo 铁律：有 1 道不确定就只暂时保存，绝不提交半份作业。
python "%~dp0do_homework.py"
pause
