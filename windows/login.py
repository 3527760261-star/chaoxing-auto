# -*- coding: utf-8 -*-
"""扫码登录（windows/login.py）。

铁律：不索要、不保存账号密码，登录由用户本人在浏览器里完成。
本脚本只拉起有头浏览器打开学习通登录页，用户自己扫码登录，
并勾选「下次自动登录」；登录态进 edge_profile（profile 模式档案）。
跑完请确认：能打开 https://i.chaoxing.com 看到「个人空间」再关窗口。

用法：python login.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

import config as win_config  # noqa: E402
from common.browser import launch, ensure_logged_in  # noqa: E402
from common.config_base import ensure_dirs  # noqa: E402


def main():
    ensure_dirs()
    print("【登录】正在拉起 Edge（有头模式），请在浏览器里自己扫码登录学习通，")
    print("      并勾选「下次自动登录」。登录态会保存在 edge_profile 里。")
    print("      本脚本绝不问你要账号密码。")
    settings = win_config.load_settings()
    with sync_playwright() as pw:
        ctx, page = launch(pw, mode=settings.get("mode", "profile"), headless=False,
                           profile_dir=str(win_config.PROFILE_DIR),
                           channel=settings.get("channel", "msedge"),
                           port=settings.get("edge_port", 9222))
        page.goto("https://passport2.chaoxing.com/login", wait_until="domcontentloaded")
        print("请扫码登录（已勾「下次自动登录」为佳）。登录完成后按回车确认……")
        input("登录完成后按回车：")
        if ensure_logged_in(page):
            print("登录成功：已看到个人空间标记，登录态已保存。")
        else:
            print("未确认到登录成功：请检查浏览器里是否已登录，再跑一次 1_登录.bat。")
        try:
            ctx.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
