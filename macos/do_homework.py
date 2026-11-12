# -*- coding: utf-8 -*-
"""填答作业（macos/do_homework.py）。

本脚本只做机械层：巡检 -> 按外部传入的答案填表 -> 暂时保存 ->
重载核对 -> 提交门判定 -> 全部有把握才提交，否则只暂时保存并列出
不确定题号 -> 写 CSV 报告。脚本本身不解题、不调用任何外部解题服务。

答案来源（--answers <path.json>）：
  答案由操作者用的智能体另外提供（比如用仓库 doubao/ 下的提示词让
  豆包来答，再把答案写进 JSON 交给脚本），格式见 answers/README.md：
  {"<题号>": "B"} 或 {"<题号>": {"answer": "B", "certain": true}}；
  没把握的题不写进文件或 certain 写 false。
  不给 --answers 时只做巡检与报告，不填题、不提交，每份作业记
  awaiting_answers（报告里写明「待外部提供答案」）。

铁律：正式计分考试、补考、竞赛卷一律不代答；有 1 道不确定就绝不提交半份作业；
不代签到；不绕过人脸/弹题/验证；不索要账号密码。

关键异常（登录失效、提交状态无法确认）会弹 macOS 通知；正常轮次静默，只写日志。

用法：
  python3 do_homework.py                     # 只巡检与报告，不填题
  python3 do_homework.py --answers ~/.cxauto/answers.json
"""
import argparse
import datetime
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

import config as mac_config  # noqa: E402
from common.browser import ensure_logged_in  # noqa: E402
from notify import notify  # noqa: E402
from common.homework import scan_course_homework, answer_assignment  # noqa: E402
from common.logging_setup import setup_logging, log_round_summary  # noqa: E402
from common.report import write_report, append_daily_note  # noqa: E402
from common.state import load_state, save_state, is_done, mark_done  # noqa: E402

from common.answer_provider import JsonFileAnswerProvider  # noqa: E402


def parse_args(argv=None):
    """解析命令行参数（抽成函数，方便自测不启动浏览器测解析）。"""
    ap = argparse.ArgumentParser(description="学习通填答作业（只做机械层，答案外部传入）")
    ap.add_argument("--answers", default=None,
                    help="答案 JSON 文件路径；不给则只巡检与报告，不填题")
    return ap.parse_args(argv)


def resolve_answers_path(raw):
    """解析 --answers 路径：原样优先；相对路径不存在时再试 DATA_DIR 下同名文件。"""
    p = Path(raw).expanduser()
    if p.is_file():
        return p
    if not p.is_absolute():
        alt = mac_config.DATA_DIR / p
        if alt.is_file():
            return alt
    return p  # 不存在时原样返回，由 JsonFileAnswerProvider 抛明确错误


def load_provider(answers_arg):
    """按 --answers 建答案提供方；不给 --answers 返回 None（只巡检与报告）。"""
    if not answers_arg:
        return None
    return JsonFileAnswerProvider(resolve_answers_path(answers_arg))


def provider_supported():
    """当前 common/homework.py 的 answer_assignment 是否接受答案提供方参数。

    另一路正在把 answer_assignment 的签名改成接受 provider 参数；
    未改好之前返回 False，调用方退回「只巡检与报告」，不等不猜、不静默失败。
    """
    try:
        return "provider" in inspect.signature(answer_assignment).parameters
    except Exception:
        return False


def awaiting_answers_row(course, hw):
    """无答案可填时的一行报告（纯函数，不碰浏览器，方便自测）。"""
    return {
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "course": course.get("name"),
        "title": hw.get("title", ""),
        "total": 0,
        "answered": 0,
        "uncertain_qnums": "",
        "action": "awaiting_answers",
        "verified": False,
        "note": "待外部提供答案：未传 --answers 答案文件，未作答、未提交",
    }


def main(argv=None):
    args = parse_args(argv)
    mac_config.ensure_dirs()
    logger = setup_logging()
    settings = mac_config.load_settings()
    try:
        provider = load_provider(args.answers)
    except (FileNotFoundError, ValueError) as e:
        print(f"答案文件有问题，立即停下：{e}")
        return 1
    if provider is None:
        print("未传 --answers：本次只做巡检与报告，不填题、不提交。")
    elif not provider_supported():
        print("common/homework.py 尚未更新到答案提供方接口（另一路进行中），"
              "本次只做巡检与报告，不填题。")
        provider = None
    else:
        print(f"答案已就绪：{getattr(provider, 'path', args.answers)}")
    state = load_state()
    rows = []
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
        for key, course in mac_config.COURSES.items():
            if mac_config.base.is_skipped_class(course):
                print(f"[{key}] 假班（clazzid={course.get('clazzid')}），照旧跳过")
                continue
            if not course.get("do_homework"):
                continue
            if mac_config.base.is_placeholder_id(course.get("courseid")):
                print(f"[{key}] 课程 ID 还是占位符，跳过（请先填 config.py）")
                continue
            for hw in scan_course_homework(page, course):
                if hw.get("status") in ("已完成", "待批阅", "读取失败"):
                    continue
                if hw.get("workid") and is_done(state, "workid", hw["workid"]):
                    continue
                if is_done(state, "assignment_title", hw.get("title", "")):
                    continue
                if provider is None:
                    rows.append(awaiting_answers_row(course, hw))
                    print(f"[{course.get('name')}] {hw.get('title')}：待外部提供答案")
                    continue
                res = answer_assignment(page, hw, provider)
                if res["action"] == "submitted" and hw.get("workid"):
                    mark_done(state, "workid", hw["workid"])
                if res["action"] == "submitted":
                    mark_done(state, "assignment_title", hw.get("title", ""))
                if "未见提交成功标记" in res.get("note", ""):
                    notify("学习通自动助手：提交状态无法确认",
                           f"《{res['title']}》已点提交但未见提交成功标记，请人工复核。")
                    logger.warning("提交状态无法确认：%s", res["title"])
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
        path = write_report(rows, mac_config.REPORTS_DIR / f"homework_{stamp}.csv")
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
