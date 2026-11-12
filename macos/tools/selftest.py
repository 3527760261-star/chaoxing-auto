# -*- coding: utf-8 -*-
"""自测（macos/tools/selftest.py）。

不登录、不联网，不依赖 Playwright 是否安装：用本地 mock 页面对象与
mock 答案提供方（注入固定答案字典）验证
提交门、save_only 路径、答案提供方协议、无答案时的等待行为、
状态去重、选择器 fallback、macOS 路径与配置、通知转义、启动器与 plist。
至少 12 项断言，输出 PASS/FAIL/SKIP 汇总，退出码 0=无失败 / 1=有失败。

答案提供方协议（lookup）直接测 common/answer_provider.py。
- answer_assignment 的集成项（mock 提供方 + mock 页面）只在
  common/homework.py 的签名已接受 provider 参数时跑；旧签名时记 SKIP，
  不伪造通过、不测旧接口。

用法：python3 macos/tools/selftest.py
"""
import importlib.util
import json
import os
import plistlib
import sys
import tempfile
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MACOS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(MACOS_DIR))

# Playwright 未装时先打桩，保证 do_homework.py 能导入（自测不启动浏览器）。
if importlib.util.find_spec("playwright") is None:
    _pw = types.ModuleType("playwright")
    _pw_sync = types.ModuleType("playwright.sync_api")
    _pw_sync.sync_playwright = lambda: None
    sys.modules.setdefault("playwright", _pw)
    sys.modules.setdefault("playwright.sync_api", _pw_sync)

import config as mac_config  # noqa: E402
import do_homework  # noqa: E402
import notify as notify_mod  # noqa: E402
from common.config_base import (ConfigError, VIDEO_DONE_RATIO,  # noqa: E402
                               is_placeholder_id, is_skipped_class,
                               load_config, reset_config_cache)
from common.homework import answer_assignment  # noqa: E402
from common.selectors import SELECTORS, QUESTIONS_JS  # noqa: E402
from common.state import mark_done, is_done, seed_state  # noqa: E402
from common.submit_gate import QuestionResult, decide, summarize  # noqa: E402

PASSED = []
FAILED = []
SKIPPED = []


def check(name, cond, detail=""):
    (PASSED if cond else FAILED).append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" —— {detail}" if detail and not cond else ""))


def skip(name, reason):
    SKIPPED.append(name)
    print(f"[SKIP] {name} —— {reason}")


# ---------------------------------------------------------------------------
# Mock 答案提供方（注入固定答案字典，不发任何网络请求）
# ---------------------------------------------------------------------------
class MockAnswerProvider:
    """{qnum: ("certain", 答案) 或 ("uncertain", 原因)}，并记录每次 lookup 入参。"""

    def __init__(self, answers):
        self.answers = dict(answers or {})
        self.calls = []

    def lookup(self, qnum, stem, qtype):
        self.calls.append((qnum, stem, qtype))
        return self.answers.get(qnum, ("uncertain", f"第 {qnum} 题未提供答案"))


# ---------------------------------------------------------------------------
# Mock 页面对象（模拟 Playwright Page 的最小接口）
# ---------------------------------------------------------------------------
class _PopupCtx:
    def __enter__(self):
        raise RuntimeError("mock: no popup")

    def __exit__(self, *a):
        return False


class _MockElement:
    def __init__(self, page, text=""):
        self._page = page
        self._text = text

    def click(self, timeout=None):
        self._page.clicked_buttons.append(self._text)

    def inner_text(self):
        return self._text

    def fill(self, value, timeout=None):
        self._page.filled.append(value)

    def screenshot(self):
        return b"fake-png-bytes"


class _MockLocator:
    def __init__(self, page, selector):
        self._page = page
        self.selector = selector

    @property
    def first(self):
        return _MockElement(self._page, self.selector)

    def nth(self, i):
        if "option" in self.selector:
            label = "ABCD"[i]
            el = _MockElement(self._page, f"{label} 示例选项{label}")

            def _click(timeout=None, _label=label):
                self._page.clicked_options.append(_label)
            el.click = _click
            return el
        return _MockElement(self._page, self.selector)

    def count(self):
        s = self.selector
        if "option" in s:
            return 4
        if "暂时保存" in s:
            return 1
        if s in ("button:has-text('提交')", "a:has-text('提交')"):
            return 1
        if "确认" in s or "确定" in s:
            return 0
        if "input[type='text']" in s:
            return 0
        return 1

    def click(self, timeout=None):
        self._page.clicked_buttons.append(self.selector)

    def screenshot(self):
        return b"fake-png-bytes"


def _two_text_questions():
    return [
        {"qnum": 1, "qtype": "单选题", "stem": "示例以下哪项是假题目",
         "options": [], "blanks": [], "has_image": False},
        {"qnum": 2, "qtype": "单选题", "stem": "示例第二道假题目选什么",
         "options": [], "blanks": [], "has_image": False},
    ]


class MockPage:
    """evaluate 按点击顺序返回每题选中态（第 i 次点击属于第 i 题）。"""

    def __init__(self, questions=None):
        self.questions = questions if questions is not None else _two_text_questions()
        self.clicked_options = []  # 按作答顺序记录每次点击的选项
        self.clicked_buttons = []
        self.filled = []
        self.url = "https://mooc1-2.chaoxing.com/work/test"

    def goto(self, url, wait_until=None, timeout=None):
        return None

    def reload(self, wait_until=None):
        return None

    def wait_for_timeout(self, ms):
        return None

    def close(self):
        return None

    def content(self):
        return "提交成功" if any("提交" in b for b in self.clicked_buttons) else ""

    def expect_popup(self):
        return _PopupCtx()

    def locator(self, selector):
        return _MockLocator(self, selector)

    def evaluate(self, js):
        out = []
        for i, q in enumerate(self.questions):
            picked = self.clicked_options[i] if i < len(self.clicked_options) else None
            opts = [{"label": l, "text": f"{l} 示例选项{l}",
                     "checked": l == picked} for l in "ABCD"]
            out.append({"qnum": q["qnum"], "qtype": q["qtype"], "stem": q["stem"],
                        "options": opts, "blanks": [],
                        "has_image": q.get("has_image", False)})
        return json.dumps(out)


def _provider_module():
    """答案提供方实现：common/answer_provider.py。"""
    import common.answer_provider as cap
    return cap, "common/answer_provider.py"


def main():
    print("自测开始：不登录、不联网、不依赖 Playwright\n")

    # -- 1-5 提交门 ---------------------------------------------------------
    d = decide([QuestionResult(1, True), QuestionResult(2, True)])
    check("提交门：全部有把握才 submit", d.action == "submit", d.action)
    d = decide([QuestionResult(1, True), QuestionResult(2, False, "题干对不上")])
    check("提交门：1 道不确定就 temp_save", d.action == "temp_save", d.action)
    check("提交门：不确定题号列出 [2]", d.uncertain_qnums == [2], str(d.uncertain_qnums))
    d = decide([])
    check("提交门：0 题不提交（防空卷）", d.action == "temp_save", d.action)
    check("提交门：summarize 含不确定题号",
          "2" in summarize(decide([QuestionResult(2, False, "x")])))

    # -- 6-12 答案提供方协议（字典版 + JSON 文件版）-------------------------
    prov_mod, prov_src = _provider_module()
    print(f"答案提供方实现来源：{prov_src}")
    DictProvider = prov_mod.DictAnswerProvider
    JsonProvider = prov_mod.JsonFileAnswerProvider
    p = DictProvider({1: "B", 2: {"answer": "C", "certain": True}})
    check("提供方：字符串写法返回 certain",
          p.lookup(1, "题干", "单选题") == ("certain", "B"), str(p.lookup(1, "", "")))
    check("提供方：字典写法 certain=true 返回 certain",
          p.lookup(2, "题干", "单选题") == ("certain", "C"))
    check("提供方：没写进文件的题判 uncertain",
          p.lookup(3, "题干", "单选题")[0] == "uncertain")
    p2 = DictProvider({1: {"answer": "A", "certain": False}, 2: {"answer": "", "certain": True}})
    check("提供方：certain=false 判 uncertain",
          p2.lookup(1, "题干", "单选题")[0] == "uncertain")
    check("提供方：空答案判 uncertain",
          p2.lookup(2, "题干", "单选题")[0] == "uncertain")
    with tempfile.TemporaryDirectory() as td:
        jf = Path(td) / "answers.json"
        jf.write_text(json.dumps({"1": "B", "2": {"answer": "C", "certain": True},
                                  "3": {"answer": "A", "certain": False}}),
                        encoding="utf-8")
        jp = JsonProvider(jf)
        check("提供方：JSON 文件字符串写法返回 certain",
              jp.lookup(1, "题干", "单选题") == ("certain", "B"))
        check("提供方：JSON 文件字典写法返回 certain",
              jp.lookup(2, "题干", "单选题") == ("certain", "C"))
        check("提供方：JSON 文件 certain=false 判 uncertain",
              jp.lookup(3, "题干", "单选题")[0] == "uncertain")
        try:
            JsonProvider(Path(td) / "nope.json")
            check("提供方：答案文件不存在时抛错", False, "未抛错")
        except FileNotFoundError:
            check("提供方：答案文件不存在时抛错", True)
        bad = Path(td) / "bad.json"
        bad.write_text("{不是 json", encoding="utf-8")
        try:
            JsonProvider(bad)
            check("提供方：答案文件 JSON 损坏时抛错", False, "未抛错")
        except ValueError:
            check("提供方：答案文件 JSON 损坏时抛错", True)
    if prov_src.startswith("common/"):
        check("提供方：common 实现已落地", True)
    else:
        skip("提供方：common 实现已落地", "common/answer_provider.py 尚未落地，本次测垫片")

    # -- 13-14 状态去重 -----------------------------------------------------
    st = json.loads(seed_state())
    check("状态：seed_state 四个空列表",
          all(st[k] == [] for k in ("completed_workids", "completed_assignments_by_title",
                                     "completed_video_ids", "completed_video_chapters")))
    check("状态：首次 mark_done 返回 True，重复返回 False 且不重复",
          mark_done(st, "workid", "W1") is True
          and mark_done(st, "workid", "W1") is False
          and st["completed_workids"] == ["W1"] and is_done(st, "workid", "W1"))

    # -- 15-17 选择器与配置 --------------------------------------------------
    check("选择器：关键选择器各有 2-3 个 fallback",
          all(len(SELECTORS[k]) >= 2 for k in
              ("temp_save_button", "submit_button", "fill_blank_input", "question_block")))
    check("选择器：QUESTIONS_JS 提取题号/题型/题干/选项/图片标记",
          all(w in QUESTIONS_JS for w in ("qnum", "qtype", "stem", "options", "has_image")))
    # -- 配置加载：缺 config.py 时报错提示清晰、示例配置能加载、SKIP 生效 --
    with tempfile.TemporaryDirectory() as td:
        missing = Path(td) / "config.py"
        try:
            load_config(config_path=missing, force=True)
            check("配置：缺 config.py 时抛 ConfigError", False, "未抛错")
        except ConfigError as e:
            check("配置：缺 config.py 时报错提示清晰",
                  "config.example.py" in str(e) and "config.py" in str(e), str(e))
        cfg_path = Path(td) / "cfg.py"
        cfg_path.write_text(
            'COURSES = {"ai": {"name": "示例课", "courseid": "000000001", '
            '"clazzid": "000000011", "do_homework": True, "do_video": False}}\n'
            'CPI = "000000000"\n'
            'SKIP_CLAZZIDS = {"000000009"}\n', encoding="utf-8")
        cfg = load_config(config_path=cfg_path, force=True)
        check("配置：示例配置能加载",
              cfg.courses["ai"]["courseid"] == "000000001"
              and cfg.cpi == "000000000", str(cfg))
        check("配置：SKIP 生效（在 SKIP 里跳过，不在不跳过）",
              is_skipped_class({"clazzid": "000000009"}, cfg.skip_clazzids)
              and not is_skipped_class({"clazzid": "000000011"}, cfg.skip_clazzids))
        cfg2_path = Path(td) / "cfg2.py"
        cfg2_path.write_text(
            'COURSES = {"ai": {"name": "示例课", "courseid": "000000001", '
            '"clazzid": "000000011", "do_homework": True, "do_video": False}}\n'
            'CPI = "000000000"\n', encoding="utf-8")
        cfg2 = load_config(config_path=cfg2_path, force=True)
        check("配置：不写 SKIP_CLAZZIDS 时默认空集",
              cfg2.skip_clazzids == set()
              and not is_skipped_class({"clazzid": "000000009"}, cfg2.skip_clazzids))
        bad_path = Path(td) / "bad.py"
        bad_path.write_text('CPI = "000000000"\n', encoding="utf-8")
        try:
            load_config(config_path=bad_path, force=True)
            check("配置：缺 COURSES 时抛 ConfigError", False, "未抛错")
        except ConfigError:
            check("配置：缺 COURSES 时抛 ConfigError", True)
        reset_config_cache()
    check("配置：占位符 ID 能识别（00000000 开头 / <...>）",
          is_placeholder_id("000000001") and is_placeholder_id("<courseid>")
          and not is_placeholder_id("123456789"))
    check("配置：提交门逻辑不受影响",
          decide([QuestionResult(1, True)]).action == "submit")
    check("配置：视频 96% 停（VIDEO_DONE_RATIO=0.96）", VIDEO_DONE_RATIO == 0.96)

    # -- 18-24 macOS 路径与配置 ---------------------------------------------
    check("macOS：DATA_DIR 默认 ~/.cxauto",
          mac_config.DATA_DIR == Path.home() / ".cxauto", str(mac_config.DATA_DIR))
    check("macOS：登录态档案是 browser_profile",
          mac_config.PROFILE_DIR == mac_config.DATA_DIR / "browser_profile",
          str(mac_config.PROFILE_DIR))
    cfg_src = (MACOS_DIR / "config.py").read_text(encoding="utf-8")
    check("macOS：config.py 不写死用户名（无 /Users/duzou 字面量）",
          "/Users/duzou" not in cfg_src)
    check("macOS：浏览器默认 channel=msedge，HEADLESS 默认开",
          mac_config.CHANNEL == "msedge" and mac_config.HEADLESS is True,
          f"channel={mac_config.CHANNEL} headless={mac_config.HEADLESS}")
    old_edge_app = os.environ.get("CX_EDGE_APP")
    try:
        with tempfile.TemporaryDirectory() as td:
            os.environ["CX_EDGE_APP"] = str(Path(td) / "NoSuch.app")
            check("macOS：Edge 未装时 edge_installed()=False",
                  mac_config.edge_installed() is False)
            check("macOS：Edge 未装时回退自带 Chromium（channel=None）",
                  mac_config.resolve_browser_channel("msedge") is None)
            bundle = Path(td) / "Microsoft Edge.app" / "Contents" / "MacOS"
            bundle.mkdir(parents=True)
            (bundle / "Microsoft Edge").write_text("fake", encoding="utf-8")
            os.environ["CX_EDGE_APP"] = str(Path(td) / "Microsoft Edge.app")
            check("macOS：Edge 已装时 edge_installed()=True",
                  mac_config.edge_installed() is True)
            check("macOS：Edge 已装时 channel=msedge",
                  mac_config.resolve_browser_channel("msedge") == "msedge")
    finally:
        if old_edge_app is None:
            os.environ.pop("CX_EDGE_APP", None)
        else:
            os.environ["CX_EDGE_APP"] = old_edge_app

    # -- 25-26 通知 ---------------------------------------------------------
    orig_is_macos = notify_mod._is_macos
    orig_run = notify_mod.subprocess.run
    try:
        notify_mod._is_macos = lambda: False
        check("通知：非 macOS 时静默不做（返回 False）",
              notify_mod.notify("标题", "内容") is False)
        captured = {}

        def _fake_run(cmd, **kw):
            captured["cmd"] = cmd
            return None
        notify_mod._is_macos = lambda: True
        notify_mod.subprocess.run = _fake_run
        ok = notify_mod.notify('标"题', '内"容\\')
        check("通知：引号/反斜杠做转义后才拼进 osascript",
              ok is True and captured["cmd"][0] == "osascript"
              and '\\"' in captured["cmd"][2], str(captured.get("cmd")))
    finally:
        notify_mod._is_macos = orig_is_macos
        notify_mod.subprocess.run = orig_run

    # -- 27-29 启动器与定时 --------------------------------------------------
    launchers = ["00_安装依赖", "1_登录", "2_巡检", "3_填答", "4_心理课视频", "5_值守", "6_自测"]
    missing = [n for n in launchers
               if not (MACOS_DIR / f"{n}.command").is_file()
               or not (MACOS_DIR / f"{n}.sh").is_file()]
    check("启动器：7 个 .command 与 7 个 .sh 都在",
          not missing, f"缺失：{missing}")
    bad = [n for n in launchers
           if "python3" not in (MACOS_DIR / f"{n}.sh").read_text(encoding="utf-8")]
    check("启动器：.sh 里都调 python3", not bad, f"异常：{bad}")
    plist_path = MACOS_DIR / "launchd" / "com.cxauto.watch.plist"
    try:
        plist = plistlib.loads(plist_path.read_bytes())
        check("定时：launchd plist 可解析且每小时跑 watch.py --once",
              plist.get("Label") == "com.cxauto.watch"
              and plist.get("StartInterval") == 3600
              and "watch.py" in " ".join(plist.get("ProgramArguments", []))
              and "--once" in " ".join(plist.get("ProgramArguments", [])),
              str(plist.get("ProgramArguments")))
    except Exception as e:
        check("定时：launchd plist 可解析且每小时跑 watch.py --once", False, repr(e))

    # -- 30-34 do_homework 接线（不启动浏览器）------------------------------
    check("接线：--answers 默认不给",
          do_homework.parse_args([]).answers is None)
    check("接线：--answers 能解析出路径",
          do_homework.parse_args(["--answers", "answers.json"]).answers == "answers.json")
    check("接线：不给 --answers 时 load_provider 返回 None（只巡检与报告）",
          do_homework.load_provider(None) is None)
    try:
        do_homework.load_provider("no-such-answers.json")
        check("接线：--answers 指到不存在的文件时启动前抛错", False, "未抛错")
    except FileNotFoundError:
        check("接线：--answers 指到不存在的文件时启动前抛错", True)
    row = do_homework.awaiting_answers_row(
        {"name": "AI通识"}, {"title": "示例作业一", "workid": "W1"})
    check("接线：无答案时报告行是 awaiting_answers 且写明待外部提供答案",
          row["action"] == "awaiting_answers" and "待外部提供答案" in row["note"]
          and row["answered"] == 0, str(row))
    check("接线：provider_supported() 返回布尔值",
          isinstance(do_homework.provider_supported(), bool))

    # -- 35-38 answer_assignment 集成（只在 common 新接口落地时跑）----------
    import inspect as _inspect
    if "provider" in _inspect.signature(answer_assignment).parameters:
        try:
            # 只有 q1 有把握：q2 不确定 -> 只暂时保存，绝不点提交
            prov1 = MockAnswerProvider({1: ("certain", "A"),
                                        2: ("uncertain", "第 2 题未提供答案")})
            page = MockPage()
            res = answer_assignment(page, {"title": "示例作业一",
                                           "url": "https://example.test/w1",
                                           "workid": "W1"}, prov1)
            check("集成 save_only：1 道不确定时 action=temp_saved",
                  res["action"] == "temp_saved", str(res))
            check("集成 save_only：绝不点提交按钮",
                  not any("提交" in b for b in page.clicked_buttons),
                  str(page.clicked_buttons))
            check("集成 save_only：点了「暂时保存」",
                  any("暂时保存" in b for b in page.clicked_buttons),
                  str(page.clicked_buttons))
            check("集成：lookup 按 (qnum, stem, qtype) 被调用",
                  all(len(c) == 3 for c in prov1.calls) and len(prov1.calls) == 2,
                  str(prov1.calls))
            # 两题都有把握 -> 提交
            prov2 = MockAnswerProvider({1: ("certain", "A"), 2: ("certain", "B")})
            page2 = MockPage()
            res2 = answer_assignment(page2, {"title": "示例作业二",
                                             "url": "https://example.test/w2",
                                             "workid": "W2"}, prov2)
            check("集成 submit：全部有把握时 action=submitted",
                  res2["action"] == "submitted", str(res2))
            check("集成 submit：点了提交按钮",
                  any("提交" in b for b in page2.clicked_buttons),
                  str(page2.clicked_buttons))
            # provider=None -> 等待答案
            page3 = MockPage()
            res3 = answer_assignment(page3, {"title": "示例作业三",
                                             "url": "https://example.test/w3",
                                             "workid": "W3"}, None)
            check("集成：provider=None 时 awaiting_answers 且写明待外部提供答案",
                  res3.get("action") == "awaiting_answers"
                  and "待外部提供答案" in res3.get("note", ""),
                  str(res3))
        except Exception as e:
            check("集成：mock 提供方走通 answer_assignment", False, repr(e))
    else:
        skip("集成 save_only：1 道不确定时 action=temp_saved",
             "common/homework.py 仍是旧签名，未接受 provider 参数")
        skip("集成 save_only：绝不点提交按钮", "同上")
        skip("集成 save_only：点了「暂时保存」", "同上")
        skip("集成：lookup 按 (qnum, stem, qtype) 被调用", "同上")
        skip("集成 submit：全部有把握时 action=submitted", "同上")
        skip("集成 submit：点了提交按钮", "同上")
        skip("集成：provider=None 时 awaiting_answers 且写明待外部提供答案", "同上")

    # -- 39 macOS 树里不含已废弃的旧设计词汇（用拼接构造，避免自测源码本身命中）
    banned = ["sol" + "ver", "rel" + "ay", "DOUBAO" + "_API_KEY",
              "Ar" + "k", "中" + "转"]
    hits = []
    for p in MACOS_DIR.rglob("*"):
        if p.is_file() and p.suffix in (".py", ".sh", ".command", ".md", ".plist", ".json"):
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:
                continue
            for tok in banned:
                if tok in text:
                    hits.append(f"{p.relative_to(MACOS_DIR)}:{tok}")
    check("清理：macos/ 全树不含已废弃的旧设计词汇", not hits, "; ".join(hits))

    # -- 40 seed_state.json 模板文件 -----------------------------------------
    seed_file = MACOS_DIR / "seed_state.json"
    try:
        seed_data = json.loads(seed_file.read_text(encoding="utf-8"))
        check("模板：macos/seed_state.json 是四个空列表",
              all(seed_data.get(k) == [] for k in
                  ("completed_workids", "completed_assignments_by_title",
                   "completed_video_ids", "completed_video_chapters")))
    except Exception as e:
        check("模板：macos/seed_state.json 是四个空列表", False, repr(e))

    total = len(PASSED) + len(FAILED)
    print(f"\n汇总：PASS {len(PASSED)} / FAIL {len(FAILED)}，共 {total} 项"
          + (f"；SKIP {len(SKIPPED)} 项（见上）" if SKIPPED else ""))
    if FAILED:
        print("失败项：" + "；".join(FAILED))
        return 1
    if SKIPPED:
        print("全部通过（SKIP 项为等另一路 common 改动落地后补测，已注明原因）。")
    else:
        print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
