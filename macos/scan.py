# -*- coding: utf-8 -*-
"""只读巡检（macos/scan.py）。

巡检三门课（ai / math / psy）的作业列表与任务点，只读不写、不作答、不提交。
结果写 DATA_DIR/scan.json（~/.cxauto/scan.json），并在控制台打印摘要。
遇假班（clazzid 在 SKIP_CLAZZIDS 里）跳过。

用法：python3 scan.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

import config as mac_config  # noqa: E402
from common.browser import ensure_logged_in  # noqa: E402
from notify import notify  # noqa: E402
from common.homework import scan_course_homework  # noqa: E402
from common.video import check_task_points  # noqa: E402


def run_scan(page):
    """巡检三门课，返回结果 dict（也供 do_homework.py / watch.py 复用）。"""
    out = {"courses": {}}
    for key, course in mac_config.COURSES.items():
        if mac_config.base.is_skipped_class(course):
            out["courses"][key] = {"error": f"假班（clazzid={course.get('clazzid')}），照旧跳过"}
            continue
        if mac_config.base.is_placeholder_id(course.get("courseid")):
            out["courses"][key] = {"error": "课程 ID 还是占位符，请先填 config.py"}
            continue
        hw = scan_course_homework(page, course)
        done, total = (0, 0)
        if course.get("do_video"):
            done, total = check_task_points(page, course)
        out["courses"][key] = {
            "name": course.get("name"),
            "homework": hw,
            "task_points": {"done": done, "total": total},
        }
    return out


def main():
    mac_config.ensure_dirs()
    settings = mac_config.load_settings()
    with sync_playwright() as pw:
        ctx, page = mac_config.launch_browser(
            pw, mode=settings.get("mode", "profile"),
            headless=settings.get("headless", True),
            profile_dir=str(mac_config.PROFILE_DIR),
            channel=settings.get("channel", "msedge"),
            port=settings.get("edge_port", 9222))
        if not ensure_logged_in(page):
            print("登录失效：请先跑 1_登录.command 重新扫码登录。")
            notify("学习通自动助手：登录失效", "请跑 1_登录.command 重新扫码登录。")
            return 1
        result = run_scan(page)
        mac_config.SCAN_FILE.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        for key, c in result["courses"].items():
            if "error" in c:
                print(f"[{key}] {c['error']}")
                continue
            tp = c["task_points"]
            print(f"[{key} {c['name']}] 任务点 {tp['done']}/{tp['total']}，作业 {len(c['homework'])} 项")
            for hw in c["homework"]:
                print(f"    - {hw.get('title')}（{hw.get('status')}）")
        print(f"巡检结果已写：{mac_config.SCAN_FILE}")
        try:
            ctx.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
