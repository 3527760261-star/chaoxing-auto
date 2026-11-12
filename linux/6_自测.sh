#!/usr/bin/env bash
# 自测：不登录、不联网，mock 自测（提交门 / 外部答案接口 / 状态去重 / Linux 配置）。
cd "$(dirname "$0")"
python3 tools/selftest.py
