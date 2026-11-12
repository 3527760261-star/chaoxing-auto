# -*- coding: utf-8 -*-
"""选择器与题目提取 JS（common.selectors）。

每个关键选择器给 2-3 个 fallback：学习通页面结构常变，
按顺序逐个尝试，第一个命中（元素存在且可见）的为准。
不要用脆弱的绝对路径定位题目，优先用文本特征。
"""
from .config_base import FORBIDDEN_CLICK_WORDS  # noqa: F401  (禁点词集中定义于此)

# 选择器：每个键对应一个候选列表，按顺序尝试。
SELECTORS = {
    # 作业列表
    "homework_list": [
        ".homework-list li",
        "[class*='homework'] li",
        ".work-list li",
    ],
    "homework_item_title": [
        ".homework-list li .title",
        "[class*='homework'] [class*='title']",
        ".work-list li a",
    ],
    "homework_status": [
        ".homework-list li .status",
        "[class*='homework'] [class*='status']",
        ".work-list li .state",
    ],
    # 分页
    "pagination_next": [
        "a.next",
        ".pagination .next",
        "a:has-text('下一页')",
    ],
    "pagination_pages": [
        ".pagination a",
        "[class*='page'] a",
    ],
    # 题目块
    "question_block": [
        ".question",
        "[class*='question']",
        ".topic",
    ],
    "question_number": [
        ".question .num",
        "[class*='question'] [class*='num']",
        ".topic .num",
    ],
    "question_stem": [
        ".question .stem",
        "[class*='question'] [class*='stem']",
        ".topic .stem",
    ],
    # 选项（单选/判断/多选）
    "option_item": [
        ".question .option",
        "[class*='question'] [class*='option']",
        ".topic .option",
    ],
    "option_input": [
        ".question input[type='radio']",
        ".question input[type='checkbox']",
        "[class*='question'] input[type='radio']",
        "[class*='question'] input[type='checkbox']",
    ],
    # 填空输入框
    "fill_blank_input": [
        ".question input[type='text']",
        "[class*='question'] input[type='text']",
        ".topic input[type='text']",
    ],
    # 「暂时保存」按钮：安全操作，任何路径都可点
    "temp_save_button": [
        "button:has-text('暂时保存')",
        "a:has-text('暂时保存')",
        "[class*='save']:has-text('暂时保存')",
    ],
    # 「提交」按钮：危险操作，仅 submit_gate.decide() 通过后的
    # submit_with_gate 路径可用，其余任何路径禁止点击。
    "submit_button": [
        "button:has-text('提交')",
        "a:has-text('提交')",
        "[class*='submit']:has-text('提交')",
    ],
    # 视频
    "video_element": [
        "video",
        ".video-player video",
    ],
    "player_mute_button": [
        ".video-player [class*='mute']",
        "button[title*='静音']",
        ".prism-volume",
    ],
    # 任务点计数 d/t（如 "3/5"）：done/total
    "task_point_count": [
        "[class*='task'] [class*='count']",
        ".task-point",
        "[class*='point']",
    ],
}


def first_matching_selector(page, key):
    """在 page 上按顺序尝试 SELECTORS[key]，返回第一个命中元素的选择器。

    page 只需实现 locator(selector).count() / first 语义
    （Playwright Page 或自测 mock 均可）。命中不了返回 None。
    """
    for sel in SELECTORS.get(key, []):
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                return sel
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# QUESTIONS_JS：从作业页 DOM 提取题号/题型/题干/选项/当前选中态。
# 尽量用文本特征（题号数字、题型关键词、选项字母）而非绝对路径，
# 以便页面结构微调后仍能工作。返回 JSON 字符串。
# ---------------------------------------------------------------------------
QUESTIONS_JS = r"""
() => {
  const text = (el) => (el ? el.innerText.trim() : "");
  const blocks = document.querySelectorAll(
    ".question, [class*='question'], .topic"
  );
  const out = [];
  blocks.forEach((b, i) => {
    const raw = text(b);
    // 题号：块内第一个「数字 + 、/.」或 data 属性；取不到则按顺序编号
    const numMatch = raw.match(/^\\s*(\\d+)\\s*[、.．]/)
      || b.getAttribute("data-num") || b.getAttribute("data-qnum");
    const qnum = numMatch ? parseInt(String(numMatch).replace(/\\D/g, ""), 10) : i + 1;
    // 题型：按关键词判断
    let qtype = "未知";
    if (/多选/.test(raw)) qtype = "多选题";
    else if (/单选/.test(raw)) qtype = "单选题";
    else if (/判断/.test(raw)) qtype = "判断题";
    else if (/填空/.test(raw)) qtype = "填空题";
    else if (b.querySelector("input[type='checkbox']")) qtype = "多选题";
    else if (b.querySelector("input[type='text']")) qtype = "填空题";
    else if (b.querySelector("input[type='radio']")) qtype = "单选题";
    // 题干：去掉题号与题型标记后的首段文字
    const stemEl = b.querySelector(".stem, [class*='stem'], .title, [class*='title']");
    let stem = text(stemEl) || raw.split("\\n")[0] || "";
    stem = stem.replace(/^\\s*\\d+\\s*[、.．]\\s*/, "")
               .replace(/^(单选题|多选题|判断题|填空题)\\s*/, "");
    // 选项：每项 {label: "A", text: "...", checked: bool}
    const options = [];
    b.querySelectorAll(".option, [class*='option'], label").forEach((o) => {
      const ot = text(o);
      const m = ot.match(/^\\s*([A-D])\\s*[、.．\\s]/);
      const input = o.querySelector("input") || o;
      if (m || o.querySelector("input[type='radio'], input[type='checkbox']")) {
        options.push({
          label: m ? m[1] : "",
          text: ot,
          checked: !!(input && input.checked),
        });
      }
    });
    // 填空当前值
    const blanks = [...b.querySelectorAll("input[type='text']")].map((x) => x.value || "");
    out.push({ qnum, qtype, stem, options, blanks, has_image: !!b.querySelector("img"), raw: raw.slice(0, 500) });
  });
  return JSON.stringify(out);
}
"""
