@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在找 Python...
python --version >nul 2>&1
if errorlevel 1 (
echo 找不到 Python！请先到 python.org 安装 Python 3.10+，安装时勾选 Add to PATH。
pause
exit /b 1
)
echo 正在安装 playwright...
pip install playwright
if errorlevel 1 (
echo pip 安装失败，请检查网络后重试。
pause
exit /b 1
)
echo 正在安装 Edge 浏览器驱动...
python -m playwright install msedge
echo.
echo 依赖安装完成，接下来跑自测：
python "%~dp0tools\selftest.py"
pause
