# -*- coding: utf-8 -*-
"""视频任务点（common.video）。

铁律（违反就停手）：
- 只看老师布置的课程任务点视频；不代签到；不绕过人脸识别、弹题、
  拖动验证、验证码；平台要求人工确认时立刻停下。
- 播放器静音只动页面 video.muted=true，不动系统音量；原速播放，不倍速。
- 视频看到 96%（VIDEO_DONE_RATIO）即停；单视频超时 VIDEO_MAX_HOURS 即停。
- 回章节页复核任务点 d/t 是否 +1，未 +1 报告「第 x.x 章播放未计入」，
  不再重播（重播也大概率不计入，还浪费时间）。
"""
import re
import time

from .config_base import VIDEO_DONE_RATIO, POLL_SEC, VIDEO_MAX_HOURS

HUMAN_CHECK_WORDS = ["人脸", "弹题", "拖动验证", "验证码", "滑块", "身份验证"]


def _read_task_points(page):
    """读章节页任务点计数 d/t，返回 (done, total)；读不到返回 (None, None)。"""
    try:
        text = page.content() or ""
    except Exception:
        return (None, None)
    m = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if not m:
        return (None, None)
    return (int(m.group(1)), int(m.group(2)))


def check_task_points(page, course):
    """查一门课的任务点完成情况，返回 (done, total)；读不到返回 (0, 0) 并记日志。"""
    from .config_base import course_url
    url = course.get("url") or course_url(course.get("courseid"),
                                          course.get("clazzid"))
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_timeout(3000)
    except Exception:
        time.sleep(3)
    done, total = _read_task_points(page)
    if done is None:
        return (0, 0)
    return (done, total)


def _human_check_needed(page):
    try:
        content = page.content() or ""
    except Exception:
        content = ""
    return [w for w in HUMAN_CHECK_WORDS if w in content]


def play_video_tasks(page, course, state):
    """逐章播放带任务点的视频。返回报告字典列表，每章一项。

    每项 {chapter, video_id, action, note}，
    action: "done" | "not_counted" | "stopped" | "skipped"。
    未计入（d/t 未 +1）只报告，不重播；遇弹题/人脸/验证立刻停手返回。
    """
    from .logging_setup import setup_logging
    logger = setup_logging()
    reports = []
    done_before, total = check_task_points(page, course)
    if total and done_before >= total:
        reports.append({"chapter": "", "video_id": "",
                        "action": "skipped", "note": "任务点已全部完成"})
        return reports

    # 取章节列表：每章 {name, url, video_id}
    try:
        chapters = page.evaluate(
            """() => {
              const links = document.querySelectorAll(
                "a[href*='video'], [class*='chapter'] a, .chapter a");
              return [...links].map((a) => ({
                name: (a.innerText || "").trim(),
                url: a.href || "",
                video_id: (a.href.match(/videoId=(\\d+)/) || [])[1] || "",
              })).filter((c) => c.url);
            }"""
        ) or []
    except Exception:
        chapters = []
    if not chapters:
        reports.append({"chapter": "", "video_id": "", "action": "stopped",
                        "note": "未找到章节列表，未播放"})
        return reports

    from .state import is_done, mark_done
    for ch in chapters:
        name = ch.get("name", "")
        vid = ch.get("video_id", "")
        if vid and is_done(state, "video_id", vid):
            continue
        page.goto(ch.get("url", ""), wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_timeout(3000)
        except Exception:
            time.sleep(3)
        hits = _human_check_needed(page)
        if hits:
            reports.append({"chapter": name, "video_id": vid, "action": "stopped",
                            "note": f"出现人工确认项（{','.join(hits)}），立刻停手"})
            logger.warning("视频遇人工确认 %s，停手：%s", hits, name)
            break
        # 页面播放器静音（只动 video.muted，不动系统音量），原速播放
        try:
            page.evaluate(
                """() => {
                  const v = document.querySelector("video");
                  if (v) { v.muted = true; v.playbackRate = 1; v.play(); }
                }"""
            )
        except Exception as e:
            reports.append({"chapter": name, "video_id": vid, "action": "stopped",
                            "note": f"播放器操作失败：{e}"})
            continue
        start = time.time()
        reached = False
        while time.time() - start < VIDEO_MAX_HOURS * 3600:
            try:
                prog = page.evaluate(
                    """() => {
                      const v = document.querySelector("video");
                      if (!v || !v.duration) return 0;
                      return v.currentTime / v.duration;
                    }"""
                )
            except Exception:
                prog = 0
            if isinstance(prog, (int, float)) and prog >= VIDEO_DONE_RATIO:
                reached = True
                break
            hits = _human_check_needed(page)
            if hits:
                reports.append({"chapter": name, "video_id": vid, "action": "stopped",
                                "note": f"播放中出现人工确认项（{','.join(hits)}），立刻停手"})
                return reports
            try:
                page.wait_for_timeout(POLL_SEC * 1000)
            except Exception:
                time.sleep(POLL_SEC)
        if not reached:
            reports.append({"chapter": name, "video_id": vid, "action": "stopped",
                            "note": f"播放超时（>{VIDEO_MAX_HOURS} 小时）或进度读不到，停手"})
            continue
        # 回章节页复核 d/t 是否 +1
        done_after, _ = check_task_points(page, course)
        if done_after > done_before:
            done_before = done_after
            if vid:
                mark_done(state, "video_id", vid)
            mark_done(state, "video_chapter", name)
            reports.append({"chapter": name, "video_id": vid, "action": "done",
                            "note": f"已看到 {int(VIDEO_DONE_RATIO * 100)}%，任务点 {done_before}/{total}"})
        else:
            reports.append({"chapter": name, "video_id": vid, "action": "not_counted",
                            "note": f"第 {name} 章播放未计入（任务点仍为 {done_before}/{total}），不再重播"})
            logger.warning("视频未计入，不再重播：%s", name)
    return reports
