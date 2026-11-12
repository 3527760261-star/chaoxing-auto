# -*- coding: utf-8 -*-
"""心理课视频（linux/watch_video.py）。

只播放心理课（psy，do_video=True）的任务点视频：原速、页面静音、
看到 96% 即停，回章节页复核任务点 d/t 是否 +1，未 +1 报告「播放未计入」不再重播。
遇弹题/人脸/拖动验证立刻停手。

用法：python3 watch_video.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

import config as linux_config  # noqa: E402
from common.browser import launch, ensure_logged_in  # noqa: E402
from common.logging_setup import setup_logging, log_round_summary  # noqa: E402
from common.state import load_state, save_state  # noqa: E402
from common.video import play_video_tasks  # noqa: E402


def main():
    linux_config.ensure_dirs()
    logger = setup_logging()
    state = load_state()
    course = linux_config.COURSES["psy"]
    if linux_config.base.is_placeholder_id(course.get("courseid")):
        print("心理课课程 ID 还是占位符，请先填 config.py")
        return 1
    with sync_playwright() as pw:
        ctx, page = launch(pw, mode="profile", headless=linux_config.HEADLESS,
                           profile_dir=str(linux_config.PROFILE_DIR),
                           **linux_config.chromium_launch_kwargs())
        if not ensure_logged_in(page):
            print("登录失效：请先跑 1_登录.sh 重新扫码登录。")
            return 1
        reports = play_video_tasks(page, course, state)
        for r in reports:
            print(f"[{r['action']}] {r.get('chapter','')}：{r['note']}")
        try:
            ctx.close()
        except Exception:
            pass
    save_state(state)
    log_round_summary({"round": "watch_video", "reports": reports})
    return 0


if __name__ == "__main__":
    sys.exit(main())
