#!/bin/bash
# chaoxing-auto macOS：自测（不登录、不联网，用本地 mock 验证）
cd "$(dirname "$0")"
python3 tools/selftest.py
echo
read -p "按回车关闭窗口：" _
