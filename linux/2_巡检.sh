#!/usr/bin/env bash
# 只读巡检三门课 + 心理课任务点，不作答、不提交。
cd "$(dirname "$0")"
python3 scan.py
