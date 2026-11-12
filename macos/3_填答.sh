#!/bin/bash
# chaoxing-auto macOS：填答作业（只做机械层，答案外部传入）
# - ~/.cxauto/answers.json 存在时自动用它当 --answers；
# - 不存在时只做巡检与报告，不填题（报告里记 awaiting_answers）。
# 答案文件做法见 README「答案从哪里来」：先让智能体答题，再把答案写进 JSON。
cd "$(dirname "$0")"
ANSWERS="$HOME/.cxauto/answers.json"
if [ -f "$ANSWERS" ]; then
  echo "检测到答案文件：$ANSWERS，用它填答。"
  python3 do_homework.py --answers "$ANSWERS"
else
  echo "未检测到答案文件（$ANSWERS 不存在）：本次只做巡检与报告，不填题。"
  echo "要填题：先按 README「答案从哪里来」准备好 answers.json，再双击本文件；"
  echo "或在终端跑：python3 do_homework.py --answers <你的答案文件路径>"
  python3 do_homework.py
fi
echo
read -p "按回车关闭窗口：" _
