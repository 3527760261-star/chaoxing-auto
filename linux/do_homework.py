# -*- coding: utf-8 -*-
"""填答作业（linux/do_homework.py）。

流程：巡检 -> 按外部答案填答 -> 暂时保存 -> 重载核对 -> 提交门判定
-> 全部有把握才提交，否则只暂时保存并列出不确定题号 -> 写 CSV 报告。

脚本只做机械层，不调用任何模型、不猜题。答案由操作者用的智能体提供
（例如用仓库 doubao/ 下的提示词让豆包来答），写进 JSON 文件后用
--answers <path.json> 传入；不给 --answers 时只做巡检与报告，不填题。
答案 JSON 格式见 common/answer_provider.py：
  {"<题号>": "B"} 或 {"<题号>": {"answer": "B", "certain": true}}；
文件里没有的题、certain 为 false 的题一律留空，绝不猜。

铁律：正式计分考试、补考、竞赛卷一律不代答；有 1 道不确定就绝不提交半份作业；
不代签到；不绕过人脸/弹题/验证；不索要账号密码。

用法：
  python3 do_homework.py                                  # 只巡检、不填题
  python3 do_homework.py --answers ~/.cxauto/answers.json  # 按 JSON 答案填答
  python3 do_homework.py --answers answers.json            # 相对路径先在当前目录找，
                                                            # 找不到再到 ~/.cxauto/ 下找
"""
import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

import config as linux_config  # noqa: E402
from common.answer_provider import JsonFileAnswerProvider  # noqa: E402
from common.browser import launch, ensure_logged_in  # noqa: E402
from common.homework import scan_course_homework, answer_assignment  # noqa: E402
from common.logging_setup import setup_logging, log_round_summary  # noqa: E402
from common.report import write_report, append_daily_note  # noqa: E402
from common.state import load_state, save_state, is_done, mark_done  # noqa: E402


def resolve_answers_path(raw):
    """解析 --answers 给的路径：绝对路径或当前目录下存在就直接用；
    相对路径在当前目录找不到时，到 DATA_DIR（~/.cxauto）下找。"""
    p = Path(raw).expanduser()
    if p.is_absolute() or p.exists():
        return p
    cand = linux_config.DATA_DIR / raw
    return cand if cand.exists() else p


def load_provider(answers_arg):
    """--answers 未给返回 None（只巡检、不填题）；给了则读 JSON 文件。
    文件不存在 / 不是合法 JSON 时抛错，由调用方停下。"""
    if not answers_arg:
        return None
    path = resolve_answers_path(answers_arg)
    return JsonFileAnswerProvider(path)


def main():
    ap = argparse.ArgumentParser(description="学习通填答作业（Linux 版，只做机械层）")
    ap.add_argument("--answers", default=None,
                    help="答案 JSON 文件路径（见 common/answer_provider.py）；"
                         "不给则只巡检、不填题")
    args = ap.parse_args()
    linux_config.ensure_dirs()
    logger = setup_logging()
    try:
        provider = load_provider(args.answers)
    except FileNotFoundError as e:
        print(f"答案文件不存在，立即停下：{e}")
        return 1
    except ValueError as e:
        print(f"答案文件有问题，立即停下：{e}")
        return 1
    if provider is None:
        print("未给 --answers：只做巡检与报告，不填题、不保存、不提交。")
        print("答案由操作者用的智能体提供（见 linux/README.md），写进 JSON 后用")
        print("  python3 do_homework.py --answers ~/.cxauto/answers.json  传入。")
    else:
        print(f"答案已载入：{provider.path}")
    state = load_state()
    rows = []
    with sync_playwright() as pw:
        ctx, page = launch(pw, mode="profile", headless=linux_config.HEADLESS,
                           profile_dir=str(linux_config.PROFILE_DIR),
                           **linux_config.chromium_launch_kwargs())
        if not ensure_logged_in(page):
            print("登录失效：请先跑 1_登录.sh 重新扫码登录。")
            return 1
        for key, course in linux_config.COURSES.items():
            if linux_config.base.is_skipped_class(course):
                print(f"[{key}] 假班（clazzid={course.get('clazzid')}），照旧跳过")
                continue
            if not course.get("do_homework"):
                continue
            if linux_config.base.is_placeholder_id(course.get("courseid")):
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
        path = write_report(rows, linux_config.REPORTS_DIR / f"homework_{stamp}.csv")
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
