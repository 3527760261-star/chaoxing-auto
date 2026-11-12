# -*- coding: utf-8 -*-
"""已完成状态（common.state）。

state 结构（version 1）：
{
  "version": 1,
  "completed_workids": [],               # 已交作业的 workid
  "completed_assignments_by_title": [],  # 已交作业的标题（workid 拿不到时用标题去重）
  "completed_video_ids": [],             # 已看完的视频 id
  "completed_video_chapters": [],        # 已完成任务点的章节标识
}
只追加、不删除；去重靠「在不在列表里」判断，绝不重复提交同一份作业。
"""
import json
from pathlib import Path

EMPTY_STATE = {
    "version": 1,
    "completed_workids": [],
    "completed_assignments_by_title": [],
    "completed_video_ids": [],
    "completed_video_chapters": [],
}

_KIND_TO_KEY = {
    "workid": "completed_workids",
    "assignment_title": "completed_assignments_by_title",
    "video_id": "completed_video_ids",
    "video_chapter": "completed_video_chapters",
}


def seed_state():
    """返回四个空列表的模板 JSON 字符串（供 seed_state.json / 初始化复用）。"""
    return json.dumps(EMPTY_STATE, ensure_ascii=False, indent=2)


def load_state(path=None):
    """读 state 文件；不存在或损坏时返回空模板（不抛错、不丢旧记录——
    损坏时调用方应在日志里记一笔，见 logging_setup）。"""
    from .config_base import STATE_FILE
    p = Path(path) if path else STATE_FILE
    if not p.is_file():
        return {k: list(v) for k, v in EMPTY_STATE.items()}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {k: list(v) for k, v in EMPTY_STATE.items()}
    out = {k: list(v) for k, v in EMPTY_STATE.items()}
    for k, v in (data or {}).items():
        if k in out and isinstance(v, list):
            out[k] = v
    out["version"] = 1
    return out


def save_state(state, path=None):
    """写 state 文件（先写临时文件再替换，避免中途断电写坏）。"""
    from .config_base import STATE_FILE
    p = Path(path) if path else STATE_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)
    return p


def mark_done(state, kind, key):
    """把 key 记为已完成（已存在则不动）；返回 True 表示本次新记入。"""
    field = _KIND_TO_KEY.get(kind)
    if field is None:
        raise ValueError(f"未知 kind：{kind}，可选 {_KIND_TO_KEY.keys()}")
    if key in state[field]:
        return False
    state[field].append(key)
    return True


def is_done(state, kind, key):
    """查 key 是否已完成。"""
    field = _KIND_TO_KEY.get(kind)
    if field is None:
        raise ValueError(f"未知 kind：{kind}，可选 {_KIND_TO_KEY.keys()}")
    return key in state[field]
