#!/bin/bash
# chaoxing-auto macOS：心理课视频（页面静音、原速、看到 96% 停、回章节页复核任务点）
cd "$(dirname "$0")"
python3 watch_video.py
echo
read -p "按回车关闭窗口：" _
