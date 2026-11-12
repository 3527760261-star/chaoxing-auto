# -*- coding: utf-8 -*-
"""macOS 通知（macos/notify.py）。

关键异常才弹通知（登录失效、提交状态无法确认、视频未计入）；
正常轮次静默，只写日志。

实现：osascript display notification。非 macOS（自测在 Linux 上跑时）
直接返回 False，什么都不做；osascript 失败也只返回 False，不抛错、
不中断主流程。消息里的引号/反斜杠做转义，防止拼进 AppleScript 出错。
"""
import subprocess
import sys


def _is_macos():
    return sys.platform == "darwin"


def _escape_applescript(text):
    return str(text).replace("\\", "\\\\").replace('"', '\\"')


def notify(title, message):
    """弹一条 macOS 通知。

    返回 True=已发出，False=未发出（非 macOS，或 osascript 调用失败）。
    """
    if not _is_macos():
        return False
    script = ('display notification "%s" with title "%s"'
              % (_escape_applescript(message), _escape_applescript(title)))
    try:
        subprocess.run(["osascript", "-e", script], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=10)
        return True
    except Exception:
        return False
