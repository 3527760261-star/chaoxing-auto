# -*- coding: utf-8 -*-
"""自测（windows/tools/selftest.py）。

不登录、不联网，不依赖 Playwright 是否安装：用本地 mock 页面对象与
mock 答案提供方（注入固定答案字典，不发任何网络请求、不调任何模型）验证
提交门、save_only 路径、无 provider 时的 awaiting_answers、答案提供方
（字典 / JSON 文件）、状态去重、选择器 fallback。
至少 12 项断言，输出 PASS/FAIL 汇总，退出码 0=全过 / 1=有失败。

用法：python windows/tools/selftest.py
"""
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "windows"))

from common.answer_provider import (DictAnswerProvider,  # noqa: E402
                                     JsonFileAnswerProvider)
from common.config_base import (ConfigError, VIDEO_DONE_RATIO,  # noqa: E402
                               is_placeholder_id, is_skipped_class,
                               load_config, reset_config_cache)
from common.homework import answer_assignment  # noqa: E402
from common.selectors import SELECTORS, QUESTIONS_JS  # noqa: E402
from common.state import mark_done, is_done, seed_state  # noqa: E402
from common.submit_gate import QuestionResult, decide, summarize  # noqa: E402

PASSED = []
FAILED = []


def check(name, cond, detail=""):
    (PASSED if cond else FAILED).append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" —— {detail}" if detail and not cond else ""))


# ---------------------------------------------------------------------------
# Mock 答案提供方（注入固定答案字典，不调模型、不发网络请求）
# ---------------------------------------------------------------------------
class FakeAnswerProvider:
    """{qnum: ("certain", 答案) 或 ("uncertain", 原因)}，记录每次查题。"""

    def __init__(self, answers):
        self.answers = dict(answers or {})
        self.lookup_calls = []

    def lookup(self, qnum, stem, qtype):
        self.lookup_calls.append(qnum)
        return self.answers.get(qnum, ("uncertain", f"第 {qnum} 题 mock 未给答案"))


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


def main():
    print("自测开始：不登录、不联网、不依赖 Playwright、不调模型\n")

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

    # -- 6-11 答案提供方：字典与 JSON 文件 -----------------------------------
    dp = DictAnswerProvider({1: "A", 2: {"answer": "B", "certain": True},
                             3: {"answer": "C", "certain": False}})
    check("provider：字典里有把握的答案返回 certain",
          dp.lookup(1, "示例题", "单选题") == ("certain", "A"))
    check("provider：字典 {answer, certain:true} 返回 certain",
          dp.lookup(2, "示例题", "单选题") == ("certain", "B"))
    check("provider：certain 为 false 的题返回 uncertain",
          dp.lookup(3, "示例题", "单选题")[0] == "uncertain")
    check("provider：字典里没有的题返回 uncertain",
          dp.lookup(9, "示例题", "单选题")[0] == "uncertain")
    with tempfile.TemporaryDirectory() as td:
        jf = Path(td) / "answers.json"
        jf.write_text(json.dumps({"1": "B",
                                  "2": {"answer": "C", "certain": True},
                                  "3": {"answer": "D", "certain": False},
                                  "4": ""}, ensure_ascii=False), encoding="utf-8")
        jp = JsonFileAnswerProvider(jf)
        check("provider：JSON 字符串写法返回 certain",
              jp.lookup(1, "示例题", "单选题") == ("certain", "B"))
        check("provider：JSON {answer, certain:true} 返回 certain",
              jp.lookup(2, "示例题", "单选题") == ("certain", "C"))
        check("provider：JSON 里 certain 为 false 的题返回 uncertain",
              jp.lookup(3, "示例题", "单选题")[0] == "uncertain")
        check("provider：JSON 里空答案的题返回 uncertain",
              jp.lookup(4, "示例题", "单选题")[0] == "uncertain")
        check("provider：JSON 文件里没有的题返回 uncertain",
              jp.lookup(5, "示例题", "单选题")[0] == "uncertain")
        bad = Path(td) / "bad.json"
        bad.write_text("{不是合法 JSON", encoding="utf-8")
        try:
            JsonFileAnswerProvider(bad)
            check("provider：非法 JSON 文件构造时抛错", False, "未抛错")
        except ValueError:
            check("provider：非法 JSON 文件构造时抛错", True)
        try:
            JsonFileAnswerProvider(Path(td) / "不存在.json")
            check("provider：不存在的答案文件构造时抛错", False, "未抛错")
        except FileNotFoundError:
            check("provider：不存在的答案文件构造时抛错", True)

    # -- 12-13 状态去重 -----------------------------------------------------
    st = json.loads(seed_state())
    check("状态：seed_state 四个空列表",
          all(st[k] == [] for k in ("completed_workids", "completed_assignments_by_title",
                                     "completed_video_ids", "completed_video_chapters")))
    check("状态：首次 mark_done 返回 True，重复返回 False 且不重复",
          mark_done(st, "workid", "W1") is True
          and mark_done(st, "workid", "W1") is False
          and st["completed_workids"] == ["W1"] and is_done(st, "workid", "W1"))

    # -- 14-18 选择器与配置 --------------------------------------------------
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

    # -- 19-22 save_only / submit 路径（mock 页面 + mock provider）----------
    # 只有 q1 有把握：q2 不确定 -> 只暂时保存，绝不点提交
    provider1 = FakeAnswerProvider({1: ("certain", "A"),
                                    2: ("uncertain", "第 2 题暂无有把握的答案，留空")})
    page = MockPage()
    res = answer_assignment(page, {"title": "示例作业一", "url": "https://example.test/w1",
                                   "workid": "W1"}, provider1)
    check("save_only：1 道不确定时 action=temp_saved",
          res["action"] == "temp_saved", str(res))
    check("save_only：绝不点提交按钮",
          not any("提交" in b for b in page.clicked_buttons), str(page.clicked_buttons))
    check("save_only：点了「暂时保存」",
          any("暂时保存" in b for b in page.clicked_buttons), str(page.clicked_buttons))
    check("save_only：报告列出不确定题号 [2]",
          res["uncertain_qnums"] == [2], str(res["uncertain_qnums"]))
    # 两题都有把握 -> 提交
    provider2 = FakeAnswerProvider({1: ("certain", "A"), 2: ("certain", "B")})
    page2 = MockPage()
    res2 = answer_assignment(page2, {"title": "示例作业二", "url": "https://example.test/w2",
                                     "workid": "W2"}, provider2)
    check("submit 路径：全部有把握时 action=submitted",
          res2["action"] == "submitted", str(res2))
    check("submit 路径：点了提交按钮",
          any("提交" in b for b in page2.clicked_buttons), str(page2.clicked_buttons))

    # -- 23-24 无 provider 时返回 awaiting_answers 且不填题 ------------------
    page4 = MockPage()
    res4 = answer_assignment(page4, {"title": "示例作业三", "url": "https://example.test/w4",
                                     "workid": "W4"}, None)
    check("无 provider：返回 awaiting_answers",
          res4["status"] == "awaiting_answers" and res4["action"] == "awaiting_answers",
          str(res4))
    check("无 provider：报告写明「待外部提供答案」",
          "待外部提供答案" in res4["note"], res4["note"])
    check("无 provider：不点任何选项、不点保存、不点提交",
          page4.clicked_options == [] and page4.clicked_buttons == [],
          f"options={page4.clicked_options} buttons={page4.clicked_buttons}")

    # -- 25-26 图片题同样按题号向 provider 查答案 ---------------------------
    img_q = [{"qnum": 1, "qtype": "单选题", "stem": "公式题（图片）",
              "options": [], "blanks": [], "has_image": True}]
    provider3 = FakeAnswerProvider({1: ("certain", "C")})
    page3 = MockPage(questions=img_q)
    res3 = answer_assignment(page3, {"title": "示例公式作业", "url": "https://example.test/w3",
                                     "workid": "W3"}, provider3)
    check("图片题：按题号向 provider 查答案（lookup 被调用）",
          provider3.lookup_calls == [1], str(provider3.lookup_calls))
    check("图片题：有把握时正常填答并提交",
          res3["action"] == "submitted" and res3["answered"] == 1, str(res3))

    print(f"\n汇总：PASS {len(PASSED)} / FAIL {len(FAILED)}，共 {len(PASSED) + len(FAILED)} 项")
    if FAILED:
        print("失败项：" + "；".join(FAILED))
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
