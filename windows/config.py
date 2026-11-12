# -*- coding: utf-8 -*-
"""Windows 版配置（windows/config.py）。

从 common.config_base 继承并做 Windows 默认：
- DATA_DIR 默认 %LOCALAPPDATA%/cxauto（可用环境变量 CX_DATA_DIR 覆盖）
- channel="msedge"，EDGE_PORT 默认 9222，HEADLESS 默认 1（有头=0 / 无头=1）
- 保留 profile / attach 两种模式，写 settings.json 切换（9_切换浏览器模式.bat）

attach 模式：克隆用户 Edge 档案到 edge_clone，用 --remote-debugging-port 拉起，
绝不动原档案；跑 attach 前要求 Edge 完全退出。
用户自己的值填仓库根 config.py（由 config.example.py 复制），不要提交真实值。
"""
import json
import os
import sys
from pathlib import Path

WINDOWS_DIR = Path(__file__).resolve().parent
REPO_ROOT = WINDOWS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from common import config_base as base  # noqa: E402

# Windows 默认（环境变量优先）
DATA_DIR = base.DATA_DIR
PROFILE_DIR = base.PROFILE_DIR
STATE_FILE = base.STATE_FILE
SCAN_FILE = base.SCAN_FILE
REPORTS_DIR = base.REPORTS_DIR
LOG_DIR = base.LOG_DIR
SHOT_DIR = base.SHOT_DIR

CHANNEL = os.environ.get("CX_CHANNEL", "msedge")
EDGE_PORT = int(os.environ.get("CX_EDGE_PORT", "9222"))
HEADLESS = os.environ.get("CX_HEADLESS", "1") == "1"
EDGE_CLONE_DIR = DATA_DIR / "edge_clone"   # attach 模式用的档案克隆，绝不动原档案

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

SETTINGS_FILE = WINDOWS_DIR / "settings.json"
DEFAULT_SETTINGS = {"mode": "profile", "headless": True, "channel": "msedge",
                    "edge_port": 9222}


def load_settings():
    """读 settings.json（9_切换浏览器模式.bat 写入）；缺失返回默认。"""
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
    base.ensure_dirs()
    EDGE_CLONE_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
