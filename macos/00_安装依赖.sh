#!/bin/bash
# chaoxing-auto macOS：安装依赖
# 找 Python3 → pip install playwright → 装浏览器驱动（Chromium；Edge 已装则另装 msedge）→ 跑自测
# 双击 00_安装依赖.command 即可跑本文件。首次跑完请继续看 README 的五分钟上手。
cd "$(dirname "$0")"
echo "正在找 Python3..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "找不到 python3！请先安装 Python 3.10+（python.org 下载，或 brew install python），再双击本文件。"
  read -p "按回车退出：" _
  exit 1
fi
python3 --version
echo "正在安装 playwright..."
python3 -m pip install playwright || {
  echo "pip 安装失败，请检查网络后重试。"
  read -p "按回车退出：" _
  exit 1
}
echo "正在安装浏览器驱动（Playwright 自带 Chromium）..."
python3 -m playwright install chromium
echo "正在安装 Edge 驱动（若本机没装 Edge for Mac，这一步失败也不要紧，会回退到自带 Chromium）..."
python3 -m playwright install msedge || echo "msedge 驱动安装失败或本机未装 Edge，之后会回退到自带 Chromium，可继续。"
echo
echo "依赖安装完成，接下来跑自测："
python3 tools/selftest.py
echo "完成。"
read -p "按回车关闭窗口：" _
