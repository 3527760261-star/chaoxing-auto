# -*- coding: utf-8 -*-
"""自测（linux/tools/selftest.py）。

不登录、不联网，不依赖 Playwright 是否安装：用本地 mock 页面对象与
mock 答案提供方（注入固定答案字典）验证
提交门、外部答案接口、无答案时只巡检、save_only 路径、图片题、
状态去重、选择器 fallback、Linux 路径与 Chromium 定位。
至少 12 项断言，输出 PASS/FAIL 汇总，退出码 0=全过 / 1=有失败。

本文件不含任何模型调用配置；禁词检查（见末尾）覆盖 linux/ 下的运行期
.py 文件，tools/ 自身除外（禁词表本身由拼接构造，避免字面量误伤）。

用法：python3 linux/tools/selftest.py
"""
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LINUX_DIR = REPO_ROOT / "linux"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(LINUX_DIR))

from common.answer_provider import DictAnswerProvider, JsonFileAnswerProvider  # noqa: E402
from common.config_base import (ConfigError, VIDEO_DONE_RATIO,  # noqa: E402
                               is_placeholder_id, is_skipped_class,
                               load_config, reset_config_cache)
from common.homework import answer_assignment  # noqa: E402
from common.selectors import SELECTORS, QUESTIONS_JS  # noqa: E402
from common.state import mark_done, is_done, seed_state  # noqa: E402
from common.submit_gate import QuestionResult, decide, summarize  # noqa: E402
import config as linux_config  # noqa: E402

PASSED = []
FAILED = []


def check(name, cond, detail=""):
    (PASSED if cond else FAILED).append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" —— {detail}" if detail and not cond else ""))


# ---------------------------------------------------------------------------
# Mock 答案提供方（注入固定答案字典，不发任何网络请求、不调任何模型）
# ---------------------------------------------------------------------------
class FakeProvider:
    """{qnum: ("certain", 答案) 或 ("uncertain", 原因)}，并记录每次查题。"""

    def __init__(self, answers):
        self.answers = dict(answers or {})
        self.calls = []

    def lookup(self, qnum, stem, qtype):
        self.calls.append((qnum, stem, qtype))
        return self.answers.get(qnum, ("uncertain", f"第 {qnum} 题未给答案"))


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
        self.goto_calls = []
        self.url = "https://mooc1-2.chaoxing.com/work/test"

    def goto(self, url, wait_until=None, timeout=None):
        self.goto_calls.append(url)
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

    # -- 6-10 外部答案接口：内存字典 ----------------------------------------
    p = DictAnswerProvider({"1": "B", "2": {"answer": "AC", "certain": True},
                            "3": {"answer": "A", "certain": False}, "4": ""})
    check("答案接口：字典字符串答案判 certain",
          p.lookup(1, "题干", "单选题") == ("certain", "B"))
    check("答案接口：字典 {answer, certain:true} 判 certain",
          p.lookup(2, "题干", "多选题") == ("certain", "AC"))
    check("答案接口：certain 为 false 判 uncertain、留空",
          p.lookup(3, "题干", "单选题")[0] == "uncertain")
    check("答案接口：空答案判 uncertain",
          p.lookup(4, "题干", "单选题")[0] == "uncertain")
    check("答案接口：字典里没有的题判 uncertain、不猜",
          p.lookup(99, "题干", "单选题")[0] == "uncertain")

    # -- 11-15 外部答案接口：JSON 文件 --------------------------------------
    with tempfile.TemporaryDirectory() as td:
        good = Path(td) / "answers.json"
        good.write_text(json.dumps({"1": "B", "2": {"answer": "对", "certain": True}},
                                   ensure_ascii=False), encoding="utf-8")
        jp = JsonFileAnswerProvider(good)
        check("答案接口：JSON 文件字符串答案判 certain",
              jp.lookup(1, "题干", "单选题") == ("certain", "B"))
        check("答案接口：JSON 文件 {answer, certain:true} 判 certain",
              jp.lookup(2, "题干", "判断题") == ("certain", "对"))
        check("答案接口：JSON 文件里没有的题判 uncertain",
              jp.lookup(5, "题干", "单选题")[0] == "uncertain")
        try:
            JsonFileAnswerProvider(Path(td) / "不存在.json")
            check("答案接口：答案文件不存在时抛错、不静默跳过", False, "未抛错")
        except FileNotFoundError:
            check("答案接口：答案文件不存在时抛错、不静默跳过", True)
        bad = Path(td) / "bad.json"
        bad.write_text("{不是合法 JSON", encoding="utf-8")
        try:
            JsonFileAnswerProvider(bad)
            check("答案接口：非法 JSON 抛错", False, "未抛错")
        except ValueError:
            check("答案接口：非法 JSON 抛错", True)
        not_obj = Path(td) / "list.json"
        not_obj.write_text('["A", "B"]', encoding="utf-8")
        try:
            JsonFileAnswerProvider(not_obj)
            check("答案接口：顶层非对象抛错", False, "未抛错")
        except ValueError:
            check("答案接口：顶层非对象抛错", True)

    # -- 16-17 状态去重 -----------------------------------------------------
    st = json.loads(seed_state())
    check("状态：seed_state 四个空列表",
          all(st[k] == [] for k in ("completed_workids", "completed_assignments_by_title",
                                     "completed_video_ids", "completed_video_chapters")))
    check("状态：首次 mark_done 返回 True，重复返回 False 且不重复",
          mark_done(st, "workid", "W1") is True
          and mark_done(st, "workid", "W1") is False
          and st["completed_workids"] == ["W1"] and is_done(st, "workid", "W1"))

    # -- 18-22 选择器与配置 --------------------------------------------------
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

    # -- 23-32 作答路径（mock 页面 + mock 答案提供方）-----------------------
    # 无答案（provider=None）：不打开作业页、不填题，状态 awaiting_answers
    page0 = MockPage()
    res0 = answer_assignment(page0, {"title": "示例作业零", "url": "https://example.test/w0",
                                     "workid": "W0"}, None)
    check("无答案：provider 为 None 时 action=awaiting_answers",
          res0["action"] == "awaiting_answers" and res0["status"] == "awaiting_answers",
          str(res0))
    check("无答案：不打开作业页、不填题",
          page0.goto_calls == [] and page0.clicked_options == []
          and "待外部提供答案" in res0["note"], str(res0))
    # 只有 q1 有把握：q2 不确定 -> 只暂时保存，绝不点提交
    prov1 = FakeProvider({1: ("certain", "A"),
                          2: ("uncertain", "第 2 题模型把握不足，不猜")})
    page = MockPage()
    res = answer_assignment(page, {"title": "示例作业一", "url": "https://example.test/w1",
                                   "workid": "W1"}, prov1)
    check("save_only：1 道不确定时 action=temp_saved",
          res["action"] == "temp_saved", str(res))
    check("save_only：绝不点提交按钮",
          not any("提交" in b for b in page.clicked_buttons), str(page.clicked_buttons))
    check("save_only：点了「暂时保存」",
          any("暂时保存" in b for b in page.clicked_buttons), str(page.clicked_buttons))
    check("save_only：报告列出不确定题号 [2]",
          res["uncertain_qnums"] == [2], str(res["uncertain_qnums"]))
    # 两题都有把握 -> 提交
    prov2 = FakeProvider({1: ("certain", "A"), 2: ("certain", "B")})
    page2 = MockPage()
    res2 = answer_assignment(page2, {"title": "示例作业二", "url": "https://example.test/w2",
                                     "workid": "W2"}, prov2)
    check("submit 路径：全部有把握时 action=submitted",
          res2["action"] == "submitted", str(res2))
    check("submit 路径：点了提交按钮",
          any("提交" in b for b in page2.clicked_buttons), str(page2.clicked_buttons))
    # 考试标题跳过
    page3 = MockPage()
    res3 = answer_assignment(page3, {"title": "期末考试（示例）", "url": "https://example.test/w3",
                                     "workid": "W3"}, prov2)
    check("铁律：考试标题跳过、不作答",
          res3["status"] == "skipped" and page3.goto_calls == [], str(res3))
    # 图片题同样按题号向提供方查答案
    img_q = [{"qnum": 1, "qtype": "单选题", "stem": "公式题（图片）",
              "options": [], "blanks": [], "has_image": True}]
    prov4 = FakeProvider({1: ("certain", "C")})
    page4 = MockPage(questions=img_q)
    res4 = answer_assignment(page4, {"title": "示例公式作业", "url": "https://example.test/w4",
                                     "workid": "W4"}, prov4)
    check("图片题：按题号向提供方查答案",
          prov4.calls == [(1, "公式题（图片）", "单选题")], str(prov4.calls))
    check("图片题：有把握时正常填答并提交",
          res4["action"] == "submitted" and res4["answered"] == 1, str(res4))

    # -- 33-37 Linux 路径与配置 ---------------------------------------------
    check("Linux 路径：CX_DATA_DIR 优先",
          linux_config._resolve_data_dir({"CX_DATA_DIR": "/tmp/cxdata",
                                          "XDG_DATA_HOME": "/tmp/xdg"})
          == Path("/tmp/cxdata"))
    check("Linux 路径：XDG_DATA_HOME 已设置时用 $XDG_DATA_HOME/cxauto",
          linux_config._resolve_data_dir({"XDG_DATA_HOME": "/tmp/xdg"})
          == Path("/tmp/xdg/cxauto"))
    check("Linux 路径：都不设时默认 ~/.cxauto",
          linux_config._resolve_data_dir({}) == Path.home() / ".cxauto")
    check("Linux 配置：HEADLESS 默认 1（无头）",
          linux_config._headless_from_env({}) is True
          and linux_config._headless_from_env({"CX_HEADLESS": "0"}) is False)
    check("Linux 配置：登录态目录是 browser_profile（不在仓库里）",
          linux_config.PROFILE_DIR.name == "browser_profile"
          and linux_config.PROFILE_DIR.parent == linux_config.DATA_DIR)

    # -- 38-43 Chromium 定位：三个分支 ---------------------------------------
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        chromium = td / "chromium"
        chromium.write_text("#!/bin/sh\n", encoding="utf-8")
        chromium.chmod(0o755)
        check("Chromium：/usr/bin/chromium 存在时用 executable_path",
              linux_config._pick_chromium([str(chromium), "/usr/bin/chromium-browser"],
                                          lambda name: None)
              == {"executable_path": str(chromium)})
        browser = td / "chromium-browser"
        browser.write_text("#!/bin/sh\n", encoding="utf-8")
        browser.chmod(0o755)
        check("Chromium：只有 chromium-browser 时取存在的那个",
              linux_config._pick_chromium(["/nonexistent/chromium", str(browser)],
                                          lambda name: None)
              == {"executable_path": str(browser)})
        check("Chromium：两个都不在、PATH 里能找到时用 channel=chromium",
              linux_config._pick_chromium(["/nonexistent/chromium",
                                           "/nonexistent/chromium-browser"],
                                          lambda name: "/usr/bin/chromium" if name == "chromium" else None)
              == {"channel": "chromium"})
        check("Chromium：都没有时回退 Playwright 自带 Chromium",
              linux_config._pick_chromium(["/nonexistent/chromium",
                                           "/nonexistent/chromium-browser"],
                                          lambda name: None) == {})
        old = os.environ.get("CX_CHROMIUM_PATH")
        os.environ["CX_CHROMIUM_PATH"] = str(browser)
        try:
            check("Chromium：CX_CHROMIUM_PATH 环境变量优先",
                  linux_config.resolve_chromium() == {"executable_path": str(browser)})
        finally:
            if old is None:
                os.environ.pop("CX_CHROMIUM_PATH", None)
            else:
                os.environ["CX_CHROMIUM_PATH"] = old
    kw = linux_config.chromium_launch_kwargs()
    check("Chromium：launch 参数恒含 channel 键（绝不默认 msedge）",
          "channel" in kw, str(kw))

    # -- 44-47 仓库文件完整性 -------------------------------------------------
    seed_file = LINUX_DIR / "seed_state.json"
    check("文件：linux/seed_state.json 与 common.state.seed_state() 一致",
          seed_file.is_file()
          and json.loads(seed_file.read_text(encoding="utf-8")) == json.loads(seed_state()))
    launchers = ["00_安装依赖.sh", "1_登录.sh", "2_巡检.sh", "3_填答.sh",
                 "4_心理课视频.sh", "5_值守.sh", "6_自测.sh"]
    check("文件：7 个启动器 .sh 都存在且可执行",
          all((LINUX_DIR / s).is_file() and os.access(LINUX_DIR / s, os.X_OK)
              for s in launchers),
          str([s for s in launchers if not os.access(LINUX_DIR / s, os.X_OK)]))
    svc = LINUX_DIR / "systemd" / "cxauto-watch.service"
    tmr = LINUX_DIR / "systemd" / "cxauto-watch.timer"
    check("文件：systemd service/timer 存在且 timer 每小时跑 watch.py --once",
          svc.is_file() and tmr.is_file()
          and "watch.py --once" in svc.read_text(encoding="utf-8")
          and "OnCalendar" in tmr.read_text(encoding="utf-8"))
    readme = (LINUX_DIR / "README.md").read_text(encoding="utf-8")
    check("文档：README 写清答案来源（doubao/ 提示词 + --answers）",
          "doubao/" in readme and "--answers" in readme)
    check("文档：README 写清 systemd 与 chromium-browser 安装",
          "systemd" in readme and "chromium-browser" in readme)

    # -- 48 运行期 .py 不含模型配置相关词 ------------------------------------
    # 禁词表由拼接构造：本文件自身也不出现这些词的字面量。
    banned = ["sol" + "ver", "Sol" + "ver", "rel" + "ay", "Rel" + "ay",
              "DOUBAO" + "_API_KEY", "A" + "rk", "中" + "转"]
    runtime_files = ["config.py", "login.py", "scan.py", "do_homework.py",
                     "watch_video.py", "watch.py"]
    bad = {}
    for name in runtime_files:
        text = (LINUX_DIR / name).read_text(encoding="utf-8")
        hits = [w for w in banned if w in text]
        if hits:
            bad[name] = hits
    check("安全：linux/ 运行期代码不含模型配置相关词", not bad, str(bad))

    print(f"\n汇总：PASS {len(PASSED)} / FAIL {len(FAILED)}，共 {len(PASSED) + len(FAILED)} 项")
    if FAILED:
        print("失败项：" + "；".join(FAILED))
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
