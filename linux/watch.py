# -*- coding: utf-8 -*-
"""值守循环（linux/watch.py）。

每小时一轮：巡检 -> 填答 -> 播放心理课视频。
--once 只跑单轮；--interval 秒可配（默认 3600）。
单轮超时用 signal.alarm 落实（Linux 专属写法，Windows 版用 subprocess timeout）：
给子进程设独立进程组，超时先 SIGALRM 触发，再 kill 整个进程组、记日志、等下一轮。
signal 只在主线程生效，本脚本全程跑在主线程。

铁律见 common/__init__.py：有 1 道不确定就只暂时保存，绝不提交半份作业；
遇人工确认项立刻停手。

用法：
  python3 watch.py --once            # 单轮（systemd timer / crontab 每小时调的就是这个）
  python3 watch.py                   # 一直循环，每小时一轮
  python3 watch.py --interval 1800   # 每半小时一轮
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

import config as linux_config  # noqa: E402
from common.config_base import ROUND_TIMEOUT  # noqa: E402
from common.logging_setup import setup_logging, log_round_summary  # noqa: E402

HERE = Path(__file__).resolve().parent


class RoundTimeout(Exception):
    """单轮超时（由 SIGALRM 处理器抛出）。"""


def _alarm_handler(signum, frame):
    raise RoundTimeout()


def run_step(script, timeout):
    """跑一个子脚本，单轮超时用 signal.alarm 杀掉整个进程组。

    返回 (returncode, timed_out)。超时时杀进程组（子进程可能还拉着浏览器），
    记日志后由调用方决定等下一轮。
    """
    proc = subprocess.Popen([sys.executable, str(HERE / script)],
                            start_new_session=True)
    signal.alarm(timeout)
    try:
        rc = proc.wait()
        return rc, False
    except RoundTimeout:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        proc.wait()
        return None, True
    finally:
        signal.alarm(0)


def one_round(logger):
    """单轮：填答 + 视频（巡检包含在 do_homework 内部流程里，scan.json 由 scan.py 更新）。"""
    logger.info("值守单轮开始")
    rc, timed_out = run_step("do_homework.py", ROUND_TIMEOUT)
    logger.info("do_homework.py 返回 %s（超时=%s）", rc, timed_out)
    if timed_out:
        log_round_summary({"round": "watch", "step": "do_homework", "status": "timeout"})
        return
    rc, timed_out = run_step("watch_video.py", ROUND_TIMEOUT)
    logger.info("watch_video.py 返回 %s（超时=%s）", rc, timed_out)
    log_round_summary({"round": "watch", "step": "all",
                       "status": "timeout" if timed_out else "ok"})
    logger.info("值守单轮结束")


def main():
    ap = argparse.ArgumentParser(description="学习通值守循环（每小时一轮）")
    ap.add_argument("--once", action="store_true", help="只跑单轮")
    ap.add_argument("--interval", type=int, default=3600, help="循环间隔（秒），默认 3600")
    args = ap.parse_args()
    linux_config.ensure_dirs()
    logger = setup_logging()
    # SIGALRM 处理器只装一次（只在主线程生效，本脚本全程在主线程跑）。
    signal.signal(signal.SIGALRM, _alarm_handler)
    if args.once:
        one_round(logger)
        return 0
    while True:
        one_round(logger)
        logger.info("下一轮在 %s 秒后开始", args.interval)
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
