# -*- coding: utf-8 -*-
"""值守循环（macos/watch.py）。

每小时一轮：巡检 -> 填答 -> 播放心理课视频。
--once 只跑单轮；--interval 秒可配（默认 3600）；
--answers <path.json> 会透传给 do_homework.py（不给则每轮只巡检与报告，不填题）。

单轮超时两层落实：
1. 每个子步骤用 subprocess 超时（ROUND_TIMEOUT 秒）跑，超时杀掉整个进程组；
2. 外层用 signal.alarm 做看门狗（只在 Unix 主线程可用）：超时杀掉当前
   子进程并记日志，等下一轮，不卡死循环。

铁律见 common/__init__.py：有 1 道不确定就只暂时保存，绝不提交半份作业；
遇人工确认项立刻停手。单轮超时会弹 macOS 通知；正常轮次静默，只写日志。

用法：
  python3 watch.py --once            # 单轮（launchd / crontab 每小时调的就是这个）
  python3 watch.py                   # 一直循环，每小时一轮
  python3 watch.py --interval 1800   # 每半小时一轮
  python3 watch.py --once --answers ~/.cxauto/answers.json
"""
import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as mac_config  # noqa: E402
from common.config_base import ROUND_TIMEOUT  # noqa: E402
from notify import notify  # noqa: E402
from common.logging_setup import setup_logging, log_round_summary  # noqa: E402

HERE = Path(__file__).resolve().parent
_CURRENT_PROC = None


class RoundTimeout(Exception):
    """单轮超时（signal.alarm 看门狗触发）。"""


def _alarm_handler(signum, frame):
    """看门狗：杀掉当前子进程组，抛 RoundTimeout 让 one_round 收尾。"""
    global _CURRENT_PROC
    proc = _CURRENT_PROC
    if proc is not None and proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    raise RoundTimeout("单轮超时（signal.alarm 看门狗）")


def run_step(script, timeout, extra_args=None):
    """跑一个子脚本，超时用 subprocess 超时杀掉整个进程组。

    返回 (returncode, timed_out)。start_new_session=True 让子进程自成
    进程组，超时时 killpg 能连同它拉起的浏览器一起杀掉。
    """
    global _CURRENT_PROC
    cmd = [sys.executable, str(HERE / script)] + list(extra_args or [])
    proc = subprocess.Popen(cmd, start_new_session=True)
    _CURRENT_PROC = proc
    try:
        rc = proc.wait(timeout=timeout)
        return rc, False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            proc.wait(timeout=10)
        except Exception:
            pass
        return None, True
    finally:
        _CURRENT_PROC = None


def one_round(logger, answers=None):
    """单轮：填答 + 视频（巡检包含在 do_homework 内部流程里，scan.json 由 scan.py 更新）。"""
    logger.info("值守单轮开始")
    old_handler = None
    use_alarm = hasattr(signal, "alarm")
    if use_alarm:
        old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
        signal.alarm(ROUND_TIMEOUT * 2)
    try:
        hw_args = ["--answers", answers] if answers else []
        rc, timed_out = run_step("do_homework.py", ROUND_TIMEOUT, hw_args)
        logger.info("do_homework.py 返回 %s（超时=%s）", rc, timed_out)
        if timed_out:
            notify("学习通自动助手：单轮超时", "do_homework.py 单轮超时，已停下等下一轮。")
            log_round_summary({"round": "watch", "step": "do_homework", "status": "timeout"})
            return
        rc, timed_out = run_step("watch_video.py", ROUND_TIMEOUT)
        logger.info("watch_video.py 返回 %s（超时=%s）", rc, timed_out)
        if timed_out:
            notify("学习通自动助手：单轮超时", "watch_video.py 单轮超时，已停下等下一轮。")
        log_round_summary({"round": "watch", "step": "all",
                           "status": "timeout" if timed_out else "ok"})
    except RoundTimeout:
        logger.warning("值守单轮超时（alarm 看门狗），已杀掉当前子进程，等下一轮")
        notify("学习通自动助手：单轮超时", "值守单轮超时，已停下等下一轮。")
        log_round_summary({"round": "watch", "step": "all", "status": "alarm_timeout"})
    finally:
        if use_alarm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    logger.info("值守单轮结束")


def main(argv=None):
    ap = argparse.ArgumentParser(description="学习通值守循环（每小时一轮）")
    ap.add_argument("--once", action="store_true", help="只跑单轮")
    ap.add_argument("--interval", type=int, default=3600, help="循环间隔（秒），默认 3600")
    ap.add_argument("--answers", default=None,
                    help="答案 JSON 文件路径，透传给 do_homework.py；不给则只巡检与报告")
    args = ap.parse_args(argv)
    mac_config.ensure_dirs()
    logger = setup_logging()
    if args.once:
        one_round(logger, answers=args.answers)
        return 0
    while True:
        one_round(logger, answers=args.answers)
        logger.info("下一轮在 %s 秒后开始", args.interval)
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            logger.info("值守循环被手动停止")
            return 0


if __name__ == "__main__":
    sys.exit(main())
