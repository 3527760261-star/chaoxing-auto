#!/usr/bin/env bash
# 填答作业。不带参数只巡检、不填题；带答案文件则按答案填答：
#   ./3_填答.sh --answers ~/.cxauto/answers.json
# 答案由操作者用的智能体提供（见 linux/README.md「答案从哪里来」），脚本本身不管模型。
cd "$(dirname "$0")"
python3 do_homework.py "$@"
