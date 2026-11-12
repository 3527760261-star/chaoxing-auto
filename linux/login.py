# -*- coding: utf-8 -*-
"""扫码登录（linux/login.py）。

铁律：不索要、不保存账号密码，登录由用户本人在浏览器里完成。
本脚本只拉起有头浏览器打开学习通登录页，用户自己扫码登录，
并勾选「下次自动登录」；登录态进 ~/.cxauto/browser_profile（profile 模式档案）。
跑完请确认：能打开 https://i.chaoxing.com 看到「个人空间」再关窗口。

无显示器的服务器上首次登录，二选一：
1. 本机跑 login.py：把仓库复制到有显示器的 Linux 桌面跑一遍，
   再把 ~/.cxauto/browser_profile 整个目录拷回服务器的 ~/.cxauto/ 下；
2. X 转发：ssh -X user@服务器 登录后跑本脚本（有头模式，DISPLAY 经 X 转发），
   即 python3 login.py --headless 0。

用法：
  python3 login.py               # 有头打开浏览器，扫码登录
  python3 login.py --headless 0  # 同上（显式有头，用于 X 转发场景说明）
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

import config as linux_config  # noqa: E402
from common.browser import launch, ensure_logged_in  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="学习通扫码登录（Linux 版）")
    ap.add_argument("--headless", choices=("0", "1"), default="0",
                    help="0=有头（默认，扫码要用），1=无头")
    args = ap.parse_args()
    headless = args.headless == "1"
    if not headless and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        print("【提示】当前没有 DISPLAY / WAYLAND_DISPLAY，有头浏览器可能打不开。")
        print("  无显示器的服务器请二选一：")
        print("  1. 在有显示器的本机跑 login.py，再把 ~/.cxauto/browser_profile 拷回服务器；")
        print("  2. 用 ssh -X 连上服务器后再跑 python3 login.py --headless 0（X 转发）。")
    linux_config.ensure_dirs()
    print("【登录】正在拉起 Chromium（有头模式），请在浏览器里自己扫码登录学习通，")
    print("      并勾选「下次自动登录」。登录态会保存在 ~/.cxauto/browser_profile 里。")
    print("      本脚本绝不问你要账号密码。")
    with sync_playwright() as pw:
        ctx, page = launch(pw, mode="profile", headless=headless,
                           profile_dir=str(linux_config.PROFILE_DIR),
                           **linux_config.chromium_launch_kwargs())
        page.goto("https://passport2.chaoxing.com/login", wait_until="domcontentloaded")
        print("请扫码登录（已勾「下次自动登录」为佳）。登录完成后按回车确认……")
        input("登录完成后按回车：")
        if ensure_logged_in(page):
            print("登录成功：已看到个人空间标记，登录态已保存。")
        else:
            print("未确认到登录成功：请检查浏览器里是否已登录，再跑一次 1_登录.sh。")
        try:
            ctx.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
