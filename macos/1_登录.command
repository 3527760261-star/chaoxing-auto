#!/bin/bash
# 双击入口：转调同名 .sh（逻辑只在 .sh 里一份，避免两份漂移）
cd "$(dirname "$0")"
exec bash "./1_登录.sh"
