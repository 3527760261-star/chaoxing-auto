# -*- coding: utf-8 -*-
"""报告（common.report）。

- write_report(rows, path)：写 CSV 明细（每轮作业/视频处理结果一行）。
- append_daily_note(text)：往 DATA_DIR/每日检查记录.md 追加一笔；
  调用方只在「有新增/异常」时调用，无事不写，避免流水账。
"""
import csv
import datetime
from pathlib import Path

REPORT_FIELDS = ["time", "course", "title", "total", "answered",
                 "uncertain_qnums", "action", "verified", "note"]


def write_report(rows, path):
    """写 CSV 明细。rows 是 dict 列表，缺的列留空；返回写出的路径。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=REPORT_FIELDS)
        w.writeheader()
        for r in rows or []:
            w.writerow({k: r.get(k, "") for k in REPORT_FIELDS})
    return path


def append_daily_note(text):
    """往 DATA_DIR/每日检查记录.md 追加一笔（带日期标题）。返回文件路径。"""
    from .config_base import DATA_DIR
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "每日检查记录.md"
    today = datetime.date.today().isoformat()
    now = datetime.datetime.now().strftime("%H:%M")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {today} {now}\n\n{text.strip()}\n")
    return path
