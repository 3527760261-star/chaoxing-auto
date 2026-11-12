#!/usr/bin/env bash
# 值守循环：每小时一轮巡检 - 填答 - 播放心理课视频。按 Ctrl+C 停止。
cd "$(dirname "$0")"
echo "每小时一轮：巡检 - 填答 - 播放心理课视频。按 Ctrl+C 停止。"
python3 watch.py "$@"
