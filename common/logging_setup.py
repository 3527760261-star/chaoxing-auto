# -*- coding: utf-8 -*-
"""日志（common.logging_setup）。

- setup_logging()：日志写 DATA_DIR/logs/run.log（滚动追加），
  同时在控制台输出简要行。
- log_round_summary(summary)：每轮结论追加一行 JSON 到 logs/summary.jsonl，
  便于值守循环事后复盘（哪一轮、哪门课、什么动作、有无异常）。
"""
import json
import logging
import datetime
from pathlib import Path


def setup_logging(name="cxauto"):
    """配置并返回 logger。重复调用不重复加 handler。"""
    from .config_base import LOG_DIR
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(LOG_DIR / "run.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


def log_round_summary(summary):
    """每轮结论写一行 JSONL。summary 是 dict，自动补时间戳。"""
    from .config_base import LOG_DIR
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {"time": datetime.datetime.now().isoformat(timespec="seconds")}
    record.update(summary or {})
    path = LOG_DIR / "summary.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path
