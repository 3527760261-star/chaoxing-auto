# -*- coding: utf-8 -*-
"""填答作业（windows/do_homework.py）。

流程：巡检 -> 按外部答案填答 -> 暂时保存 -> 重载核对 -> 提交门判定
-> 全部有把握才提交，否则只暂时保存并列出不确定题号 -> 写 CSV 报告。

脚本只做机械层，不做任何模型调用、不猜题。答案由操作者用的智能体
（比如用仓库 doubao/ 下的豆包提示词让豆包来答）提供，写进 JSON 文件
（格式见 answers/README.md），再用 --answers 传入：
    python do_homework.py --answers answers.json
不给 --answers 时只做巡检与报告，不填题、不保存、不提交
（每份作业在报告里记为 awaiting_answers，并写明「待外部提供答案」）。

铁律：正式计分考试、补考、竞赛卷一律不代答；有 1 道不确定就绝不提交半份作业；
不代签到；不绕过人脸/弹题/验证；不索要账号密码。

用法：python do_homework.py [--answers <答案 JSON>]
"""
import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

import config as win_config  # noqa: E402
from common.answer_provider import JsonFileAnswerProvider  # noqa: E402
from common.browser import launch, ensure_logged_in  # noqa: E402
from common.config_base import ensure_dirs  # noqa: E402
from common.homework import scan_course_homework, answer_assignment  # noqa: E402
from common.logging_setup import setup_logging, log_round_summary  # noqa: E402
from common.report import write_report, append_daily_note  # noqa: E402
from common.state import load_state, save_state, is_done, mark_done  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="学习通作业填答（答案由外部 JSON 传入）")
    parser.add_argument("--answers", default=None,
                        help="答案 JSON 文件路径（格式见 answers/README.md）；"
                             "不给时只做巡检与报告，不填题")
    args = parser.parse_args(argv)
    ensure_dirs()
    logger = setup_logging()
    settings = win_config.load_settings()
    provider = None
    if args.answers:
        try:
            provider = JsonFileAnswerProvider(args.answers)
        except (OSError, ValueError) as e:
            print(f"答案文件读入失败，立即停下：{e}")
            return 1
        print(f"答案已从外部文件载入：{args.answers}")
    else:
        print("未给 --answers：本轮只做巡检与报告，不填题、不保存、不提交。")
        print("要填答，请先让智能体（见仓库 doubao/ 下的豆包提示词）答题、"
              "把答案写进 JSON，再跑 do_homework.py --answers <答案 JSON>。")
    state = load_state()
    rows = []
    with sync_playwright() as pw:
        ctx, page = launch(pw, mode=settings.get("mode", "profile"),
                           headless=settings.get("headless", True),
                           profile_dir=str(win_config.PROFILE_DIR),
                           channel=settings.get("channel", "msedge"),
                           port=settings.get("edge_port", 9222))
        if not ensure_logged_in(page):
            print("登录失效：请先跑 1_登录.bat 重新扫码登录。")
            return 1
        for key, course in win_config.COURSES.items():
            if win_config.base.is_skipped_class(course):
                print(f"[{key}] 假班（clazzid={course.get('clazzid')}），照旧跳过")
                continue
            if not course.get("do_homework"):
                continue
            if win_config.base.is_placeholder_id(course.get("courseid")):
                print(f"[{key}] 课程 ID 还是占位符，跳过（请先填 config.py）")
                continue
            for hw in scan_course_homework(page, course):
                if hw.get("status") in ("已完成", "待批阅", "读取失败"):
                    continue
                if hw.get("workid") and is_done(state, "workid", hw["workid"]):
                    continue
                if is_done(state, "assignment_title", hw.get("title", "")):
                    continue
                res = answer_assignment(page, hw, provider)
                if res["action"] == "submitted" and hw.get("workid"):
                    mark_done(state, "workid", hw["workid"])
                if res["action"] == "submitted":
                    mark_done(state, "assignment_title", hw.get("title", ""))
                rows.append({
                    "time": datetime.datetime.now().isoformat(timespec="seconds"),
                    "course": course.get("name"),
                    "title": res["title"],
                    "total": res["total"],
                    "answered": res["answered"],
                    "uncertain_qnums": ",".join(map(str, res["uncertain_qnums"])),
                    "action": res["action"],
                    "status": res.get("status", res["action"]),
                    "verified": res["verified"],
                    "note": res["note"],
                })
                print(f"[{course.get('name')}] {res['title']}：{res['action']}，"
                      f"不确定题号 {res['uncertain_qnums'] or '无'}")
        try:
            ctx.close()
        except Exception:
            pass
    save_state(state)
    if rows:
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = write_report(rows, win_config.REPORTS_DIR / f"homework_{stamp}.csv")
        print(f"报告已写：{path}")
        append_daily_note("\n".join(
            f"- {r['course']}《{r['title']}》：{r['action']}，"
            f"不确定题号 {r['uncertain_qnums'] or '无'}"
            for r in rows))
    log_round_summary({"round": "do_homework", "rows": len(rows),
                       "submitted": sum(1 for r in rows if r["action"] == "submitted"),
                       "temp_saved": sum(1 for r in rows if r["action"] == "temp_saved"),
                       "awaiting_answers": sum(1 for r in rows if r["action"] == "awaiting_answers")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
