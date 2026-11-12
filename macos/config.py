# -*- coding: utf-8 -*-
"""macOS 版配置（macos/config.py）。

从 common.config_base 继承并做 macOS 默认：
- DATA_DIR 默认 ~/.cxauto（即 /Users/<用户名>/.cxauto，用 Path.home() / expanduser
  解析，用户名绝不写死在代码里；可用环境变量 CX_DATA_DIR 覆盖）
- 登录态进 DATA_DIR/browser_profile（macOS 版与 Windows 的 edge_profile 区分开）
- 浏览器优先用本机已装的 Microsoft Edge for Mac（channel="msedge"）；
  若未装 Edge，回退 Playwright 自带 Chromium（见 resolve_browser_channel /
  launch_browser），并在 README 写清两种情况
- HEADLESS 默认 1（有头=0 / 无头=1，可用环境变量 CX_HEADLESS 改）

本脚本只做机械层：不调用任何外部解题服务、不保存任何凭证配置。
答案由操作者用的智能体另外提供，见 do_homework.py 的 --answers 与 README。
用户自己的值填仓库根 config.py（由 config.example.py 复制），不要提交真实值。
"""
import json
import os
import sys
from pathlib import Path

MACOS_DIR = Path(__file__).resolve().parent
REPO_ROOT = MACOS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from common import config_base as base  # noqa: E402

# macOS 默认数据目录：~/.cxauto（expanduser，不写死用户名）
DATA_DIR = Path(os.environ["CX_DATA_DIR"]).expanduser() if os.environ.get("CX_DATA_DIR") else Path.home() / ".cxauto"
PROFILE_DIR = DATA_DIR / "browser_profile"  # macOS 版登录态档案（Windows 版叫 edge_profile）
STATE_FILE = DATA_DIR / "state.json"
SCAN_FILE = DATA_DIR / "scan.json"
REPORTS_DIR = DATA_DIR / "reports"
LOG_DIR = DATA_DIR / "logs"
SHOT_DIR = DATA_DIR / "shots"

CHANNEL = os.environ.get("CX_CHANNEL", "msedge")
EDGE_PORT = int(os.environ.get("CX_EDGE_PORT", "9222"))
HEADLESS = os.environ.get("CX_HEADLESS", "1") == "1"

def __getattr__(name):
    """课程信息按需从用户 config.py 加载（common.config_base.load_config）。

    导入本模块时不读用户配置，所以自测、--help 这类不需要课程信息的操作
    在没有 config.py 时也能跑；第一次用到 COURSES/CPI/SKIP_CLAZZIDS 时
    才加载，缺 config.py 就报清晰的错（去复制 config.example.py）。
    """
    if name in ("COURSES", "CPI", "SKIP_CLAZZIDS"):
        cfg = base.load_config()
        return {"COURSES": cfg.courses, "CPI": cfg.cpi,
                "SKIP_CLAZZIDS": cfg.skip_clazzids}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


VIDEO_DONE_RATIO = base.VIDEO_DONE_RATIO
POLL_SEC = base.POLL_SEC
VIDEO_MAX_HOURS = base.VIDEO_MAX_HOURS
ROUND_TIMEOUT = base.ROUND_TIMEOUT
IRON_RULES = base.IRON_RULES
FORBIDDEN_CLICK_WORDS = base.FORBIDDEN_CLICK_WORDS

SETTINGS_FILE = MACOS_DIR / "settings.json"
DEFAULT_SETTINGS = {"mode": "profile", "headless": True, "channel": "msedge",
                    "edge_port": 9222}


def load_settings():
    """读 settings.json；缺失返回默认（profile / 有头由调用方决定）。"""
    if SETTINGS_FILE.is_file():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            out = dict(DEFAULT_SETTINGS)
            out.update(data or {})
            return out
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings):
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    return SETTINGS_FILE


def ensure_dirs():
    """创建 DATA_DIR 下全部子目录（用 macOS 版的 PROFILE_DIR）。"""
    for d in (DATA_DIR, PROFILE_DIR, REPORTS_DIR, LOG_DIR, SHOT_DIR):
        d.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


# ---------------------------------------------------------------------------
# Edge for Mac 检测与回退
# ---------------------------------------------------------------------------
def edge_app_path():
    """Edge for Mac 的应用包路径（可用 CX_EDGE_APP 覆盖，方便自测）。"""
    return Path(os.environ.get("CX_EDGE_APP", "/Applications/Microsoft Edge.app"))


def edge_installed():
    """本机是否装了 Microsoft Edge for Mac。"""
    return (edge_app_path() / "Contents" / "MacOS" / "Microsoft Edge").is_file()


def resolve_browser_channel(channel="msedge"):
    """解析浏览器 channel：

    - 要 msedge 且本机装了 Edge -> 返回 "msedge"；
    - 要 msedge 但本机没装 Edge -> 返回 None，调用方改用 Playwright 自带 Chromium；
    - 其它 channel 原样返回。
    """
    if channel == "msedge" and not edge_installed():
        return None
    return channel


def launch_browser(pw, *, mode="profile", headless=True, profile_dir=None,
                   channel="msedge", port=9222):
    """macOS 版浏览器拉起（common.browser.launch 的包装）。

    profile 模式 + channel="msedge" + 本机未装 Edge 时，回退到 Playwright
    自带 Chromium（不传 channel），并打印提示；其余情况走 common.browser.launch。
    attach 模式要求 Edge 已装，未装时直接报错（不要静默换模式）。
    """
    from common.browser import launch as _launch
    if profile_dir is None:
        profile_dir = str(PROFILE_DIR)
    if mode == "profile" and resolve_browser_channel(channel) is None:
        print("未检测到 Microsoft Edge for Mac（/Applications/Microsoft Edge.app），"
              "回退到 Playwright 自带 Chromium。想用 Edge 请先安装 Edge for Mac。")
        context = pw.chromium.launch_persistent_context(str(profile_dir),
                                                        headless=headless)
        page = context.new_page() if hasattr(context, "new_page") else context.pages[0]
        return context, page
    if mode == "attach" and resolve_browser_channel(channel) is None:
        raise RuntimeError(
            "attach 模式需要 Microsoft Edge for Mac，但本机未检测到 "
            "（/Applications/Microsoft Edge.app 不存在）。"
            "请安装 Edge for Mac，或改用 profile 模式（回退 Chromium）。")
    return _launch(pw, mode=mode, headless=headless, profile_dir=profile_dir,
                   channel=channel, port=port)
