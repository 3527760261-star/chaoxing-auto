# -*- coding: utf-8 -*-
"""Linux 版配置（linux/config.py）。

从 common.config_base 继承并做 Linux 默认：
- DATA_DIR：环境变量 CX_DATA_DIR > $XDG_DATA_HOME/cxauto（已设置时）
  > ~/.cxauto；遵循 XDG 规范
- 浏览器优先用系统 Chromium（见 resolve_chromium() 的三种情况），
  HEADLESS 默认 1（有头=0 / 无头=1）
- 登录态进 DATA_DIR/browser_profile（与 Windows 的 edge_profile 区分开）
- 没有 settings.json / attach 模式：Linux 只用 profile 模式，
  行为用环境变量 CX_HEADLESS / CX_CHROMIUM_PATH 调整

用户自己的值填仓库根 config.py（由 config.example.py 复制），不要提交真实值。
"""
import os
import shutil
import sys
from pathlib import Path

LINUX_DIR = Path(__file__).resolve().parent
REPO_ROOT = LINUX_DIR.parent
sys.path.insert(0, str(REPO_ROOT))


def _resolve_data_dir(env=None):
    """算 DATA_DIR（纯函数，可单测）：

    CX_DATA_DIR > $XDG_DATA_HOME/cxauto（已设置时） > ~/.cxauto。
    """
    env = os.environ if env is None else env
    if env.get("CX_DATA_DIR"):
        return Path(env["CX_DATA_DIR"]).expanduser()
    xdg = env.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg).expanduser() / "cxauto"
    return Path.home() / ".cxauto"


def _headless_from_env(env=None):
    """HEADLESS 默认 1：CX_HEADLESS=0 才有头（纯函数，可单测）。"""
    env = os.environ if env is None else env
    return env.get("CX_HEADLESS", "1") == "1"


# 在 common.config_base 导入前把算好的 DATA_DIR 写进环境变量，
# 这样 config_base 里的 STATE_FILE / SCAN_FILE / REPORTS_DIR / LOG_DIR / SHOT_DIR
# 全部落在同一个数据目录下（config_base 本身只认 CX_DATA_DIR）。
if not os.environ.get("CX_DATA_DIR"):
    os.environ["CX_DATA_DIR"] = str(_resolve_data_dir())

from common import config_base as base  # noqa: E402

# Linux 默认（环境变量优先）
DATA_DIR = base.DATA_DIR
PROFILE_DIR = DATA_DIR / "browser_profile"  # 登录态在这里（Linux 不用 edge_profile 这个名）
STATE_FILE = base.STATE_FILE
SCAN_FILE = base.SCAN_FILE
REPORTS_DIR = base.REPORTS_DIR
LOG_DIR = base.LOG_DIR
SHOT_DIR = base.SHOT_DIR

HEADLESS = _headless_from_env()

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

# 系统 Chromium 候选路径（按顺序取存在的那个）。
CHROMIUM_CANDIDATES = ("/usr/bin/chromium", "/usr/bin/chromium-browser")


def _pick_chromium(candidates, which):
    """选 Chromium 启动方式（纯函数，可单测），三种情况：

    1. /usr/bin/chromium 或 /usr/bin/chromium-browser 存在（可执行）
       -> {"executable_path": 该路径}；
    2. 上面两个都不在，但 PATH 里能找到 chromium / chromium-browser
       -> {"channel": "chromium"}（Playwright 按 channel 找系统 Chromium）；
    3. 都没有 -> {}（回退 Playwright 自带 Chromium，需先跑
       python3 -m playwright install chromium）。
    """
    for cand in candidates:
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return {"executable_path": cand}
    if which("chromium") or which("chromium-browser"):
        return {"channel": "chromium"}
    return {}


def resolve_chromium():
    """按本机实际情况选 Chromium 启动方式。

    环境变量 CX_CHROMIUM_PATH 优先：指向一个可执行的 Chromium 二进制
    （如 /usr/bin/chromium 或 /snap/bin/chromium），直接用它。
    """
    override = os.environ.get("CX_CHROMIUM_PATH")
    if override and os.path.isfile(override) and os.access(override, os.X_OK):
        return {"executable_path": override}
    return _pick_chromium(CHROMIUM_CANDIDATES, shutil.which)


def chromium_launch_kwargs():
    """传给 common.browser.launch 的 Chromium 参数。

    恒含 "channel" 键：channel 与 executable_path 二选一，
    两个都没有时 channel=None（Playwright 会忽略 None 值），
    绝不能让 launch() 的默认 channel="msedge" 在 Linux 上生效。
    """
    kw = resolve_chromium()
    out = {"channel": None}
    out.update(kw)
    return out


def ensure_dirs():
    """创建 DATA_DIR 下全部子目录（Linux 用 browser_profile，不建 edge_profile）。"""
    for d in (DATA_DIR, PROFILE_DIR, REPORTS_DIR, LOG_DIR, SHOT_DIR):
        d.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
