#!/usr/bin/env bash
# 扫码登录（有头模式）。无显示器的服务器见 linux/README.md「服务器无显示器首次登录」。
cd "$(dirname "$0")"
python3 login.py "$@"
