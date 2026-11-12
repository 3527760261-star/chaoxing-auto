#!/bin/bash
# chaoxing-auto macOS：值守循环（每小时一轮：巡检 → 填答 → 心理课视频）
# 前台一直跑，按 Ctrl+C 停止。长期无人值守请用 launchd（见 launchd/ 与 README）。
# 答案文件：~/.cxauto/answers.json 存在时自动透传给填答步骤。
cd "$(dirname "$0")"
ANSWERS="$HOME/.cxauto/answers.json"
if [ -f "$ANSWERS" ]; then
  echo "检测到答案文件：$ANSWERS，值守每轮都会用它填答。"
  python3 watch.py --answers "$ANSWERS"
else
  echo "未检测到答案文件（$ANSWERS 不存在）：值守每轮只做巡检与报告，不填题。"
  python3 watch.py
fi
