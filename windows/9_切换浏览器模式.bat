@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo
echo 1 = profile（默认）：用独立档案 edge_profile，登录态存在里面
echo 2 = attach：克隆你的 Edge 档案到 edge_clone 再拉起，绝不动原档案
echo 注意：跑 attach 前请先完全退出 Edge。
set /p choice=请输入 1 或 2：
if "%choice%"=="1" (
python -c "import json; p=r'%~dp0settings.json'; json.dump({'mode':'profile','headless':True,'channel':'msedge','edge_port':9222}, open(p,'w',encoding='utf-8'), ensure_ascii=False, indent=2)"
echo 已切换为 profile 模式。
) else if "%choice%"=="2" (
python -c "import json; p=r'%~dp0settings.json'; json.dump({'mode':'attach','headless':True,'channel':'msedge','edge_port':9222}, open(p,'w',encoding='utf-8'), ensure_ascii=False, indent=2)"
echo 已切换为 attach 模式。跑之前请先完全退出 Edge。
) else (
echo 输入无效，未切换。
)
pause
