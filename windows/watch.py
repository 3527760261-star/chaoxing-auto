# -*- coding: utf-8 -*-
"""值守循环（windows/watch.py）。

每小时一轮：巡检 -> 填答 -> 播放心理课视频。
--once 只跑单轮；--interval 秒可配（默认 3600）。
单轮超时用 subprocess timeout 落实：本脚本作为父进程时，
用超时跑 do_homework.py / watch_video.py 子进程，超时即杀掉、记日志、等下一轮。

铁律见 common/__init__.py：有 1 道不确定就只暂时保存，绝不提交半份作业；
遇人工确认项立刻停手。

用法：
  python watch.py --once            # 单轮（计划任务每小时调的就是这个）
  python watch.py                   # 一直循环，每小时一轮
  python watch.py --interval 1800   # 每半小时一轮
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as win_config  # noqa: E402
from common.config_base import ROUND_TIMEOUT  # noqa: E402
from common.logging_setup import setup_logging, log_round_summary  # noqa: E402

HERE = Path(__file__).resolve().parent


def run_step(script, timeout):
    """跑一个子脚本，超时用 subprocess timeout 杀掉；返回 (returncode, timed_out)。"""
    try:
        proc = subprocess.run([sys.executable, str(HERE / script)],
                              timeout=timeout, capture_output=False)
        return proc.returncode, False
    except subprocess.TimeoutExpired:
        return None, True


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
    win_config.ensure_dirs()
    logger = setup_logging()
    if args.once:
        one_round(logger)
        return 0
    while True:
        one_round(logger)
        logger.info("下一轮在 %s 秒后开始", args.interval)
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
