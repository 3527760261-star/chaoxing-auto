#!/bin/bash
# chaoxing-auto macOS：扫码登录（本脚本不问账号密码，登录由你本人在浏览器里完成）
cd "$(dirname "$0")"
python3 login.py
echo
read -p "按回车关闭窗口：" _
