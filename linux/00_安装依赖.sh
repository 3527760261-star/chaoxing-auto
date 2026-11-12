#!/usr/bin/env bash
# 学习通自动助手 · Linux 版：安装依赖
# 检查 python3/pip -> pip install playwright -> 装 Chromium -> 跑自测
set -e
cd "$(dirname "$0")"
echo "正在找 python3..."
command -v python3 >/dev/null 2>&1 || { echo "找不到 python3！请先装 Python 3.10+（Debian/Ubuntu：sudo apt install python3 python3-pip）。"; exit 1; }
python3 --version
echo "正在找 pip..."
python3 -m pip --version >/dev/null 2>&1 || { echo "找不到 pip！Debian/Ubuntu：sudo apt install python3-pip"; exit 1; }
echo "正在安装 playwright（Python 库）..."
python3 -m pip install playwright
echo "正在安装 Playwright 自带 Chromium（若已装系统 Chromium，可跳过这步）..."
echo "注意：--with-deps 需要 sudo 装系统依赖包；无 sudo 权限时去掉 --with-deps 再跑："
echo "  python3 -m playwright install chromium"
python3 -m playwright install chromium --with-deps || python3 -m playwright install chromium
echo
echo "依赖安装完成，接下来跑自测："
python3 tools/selftest.py
