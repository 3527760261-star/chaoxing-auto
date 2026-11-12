# -*- coding: utf-8 -*-
"""浏览器启动与登录态检查（common.browser）。

铁律：不索要、不保存账号密码，登录由用户本人在浏览器里完成。
本模块只负责「拉起已登录过的浏览器档案」和「判断登录是否还有效」，
绝不填账号密码、绝不处理验证码。

两种模式：
- profile：Playwright persistent_context，用 DATA_DIR/edge_profile 里的档案
  （login.py 扫码登录后，登录态就存在这个档案里）。
- attach：连到用户已打开的 Edge（--remote-debugging-port 拉起），
  绝不动原档案；跑 attach 前要求 Edge 完全退出再由脚本拉起
  （Windows 版会把用户档案克隆到 edge_clone 再拉，见 windows/config.py）。
"""
import time

LOGIN_CHECK_URL = "https://i.chaoxing.com"
LOGGED_OUT_HOST = "passport2.chaoxing.com"
LOGGED_IN_MARKERS = ["个人空间", "我的课程", "我的学习"]


def launch(pw, *, mode="profile", headless=True, profile_dir=None,
           channel="msedge", executable_path=None, port=9222):
    """拉起浏览器，返回 (browser_or_context, page)。

    pw：playwright 的 sync_playwright() 上下文管理器对象（由调用方传入，
    本模块不 import playwright，方便自测 mock）。
    mode="profile"：persistent_context，档案在 profile_dir。
    mode="attach"：用 channel 拉起 Edge 并通过 CDP 连接 127.0.0.1:port。
    """
    if mode not in ("profile", "attach"):
        raise ValueError(f"未知浏览器模式：{mode}，只支持 profile / attach")
    if mode == "profile":
        if profile_dir is None:
            from .config_base import PROFILE_DIR
            profile_dir = str(PROFILE_DIR)
        kwargs = {"headless": headless, "channel": channel}
        if executable_path:
            kwargs["executable_path"] = executable_path
        context = pw.chromium.launch_persistent_context(str(profile_dir), **kwargs)
        page = context.new_page() if hasattr(context, "new_page") else context.pages[0]
        return context, page
    # attach：先拉起带远程调试端口的 Edge，再用 CDP 连上去
    kwargs = {"headless": headless, "channel": channel,
              "args": [f"--remote-debugging-port={port}"]}
    if executable_path:
        kwargs["executable_path"] = executable_path
    browser = pw.chromium.launch(**kwargs)
    cdp = browser.new_context()  # 占位：真实 attach 走 connect_over_cdp，见下
    try:
        browser.close()
    except Exception:
        pass
    endpoint = f"http://127.0.0.1:{port}"
    connected = pw.chromium.connect_over_cdp(endpoint)
    page = connected.pages[0] if connected.pages else connected.new_page()
    return connected, page


def ensure_logged_in(page):
    """检查登录态是否有效。

    打开 https://i.chaoxing.com ，等页面稳定：
    - 跳到 passport2.chaoxing.com 域名 -> 登录失效，返回 False；
    - 看到「个人空间 / 我的课程」标记 -> 已登录，返回 True；
    - 两者都无 -> 无法确认，按失效处理，返回 False（宁可让用户重登，
      也不在未登录状态下继续操作）。
    """
    try:
        page.goto(LOGIN_CHECK_URL, wait_until="domcontentloaded", timeout=30000)
    except Exception:
        return False
    try:
        page.wait_for_timeout(2000)
    except Exception:
        time.sleep(2)
    try:
        url = page.url or ""
    except Exception:
        url = ""
    if LOGGED_OUT_HOST in url:
        return False
    try:
        content = page.content() or ""
    except Exception:
        content = ""
    return any(m in content for m in LOGGED_IN_MARKERS)
