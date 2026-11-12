# -*- coding: utf-8 -*-
"""作业巡检与填答（common.homework）。

答案由外部传入（common.answer_provider.AnswerProvider），脚本本身不做
任何模型调用、不猜题：每道题按题号向 provider 查答案，provider 返回
("certain", 答案) 才填，("uncertain", 原因) 则留空。

铁律（违反就停手）：
1. 只处理老师布置的虚拟题库作业/课程任务点；正式计分考试、补考、竞赛卷
   一律不代答——标题含「考试/补考/竞赛/期末考试/期中考试」等词的直接跳过。
2. 提交门：全部题目有把握才提交；有 1 道不确定就只「暂时保存」，
   绝不提交半份作业；提交前必须重载页面核对答案已保留。
3. 不代签到；不绕过人脸识别、弹题、拖动验证、验证码；平台要求人工确认时立刻停下。
4. 只有 submit_gate.decide() 返回 submit 的路径才允许点「提交」按钮
   并确认提交确认弹窗；其余任何路径都不许点提交。

流程：scan_course_homework 巡检 -> answer_assignment 填答
（新标签 -> 提取题目 -> 向 provider 查答案 -> 按答案作答 -> 暂时保存
 -> 重载核对 -> 提交门判定 -> 可提交才点提交并确认弹窗 -> 最终核对
 -> 返回报告字典）。
provider 为 None 时跳过作答，返回状态 awaiting_answers，并在报告里
写明「待外部提供答案」——不填题、不保存、不提交。
"""
import json
import re
import time

from .selectors import SELECTORS, QUESTIONS_JS, first_matching_selector
from .submit_gate import QuestionResult, decide, summarize

# 标题含这些词的一律视为正式考试/竞赛，不代答，直接跳过。
EXAM_TITLE_WORDS = ["考试", "补考", "竞赛", "期末", "期中", "测验", "统考"]
# 页面出现这些词说明要人工确认/验证，立刻停手。
HUMAN_CHECK_WORDS = ["人脸", "弹题", "拖动验证", "验证码", "滑块", "身份验证"]


def _click_first(page, key):
    """按 SELECTORS[key] 的 fallback 顺序点第一个能点的元素；都点不到返回 False。"""
    for sel in SELECTORS.get(key, []):
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                loc.first.click(timeout=5000)
                return True
        except Exception:
            continue
    return False


def _extract_questions(page):
    """用 QUESTIONS_JS 提取当前作业页的题目；失败返回空列表。"""
    try:
        raw = page.evaluate(QUESTIONS_JS)
        data = json.loads(raw) if isinstance(raw, str) else raw
        return data if isinstance(data, list) else []
    except Exception:
        return []


def scan_course_homework(page, course):
    """巡检一门课的作业列表。

    返回作业列表，每项含 title / workid / url / status
    （已完成 / 待批阅 / 未交 / 未开始 / 开始时间）。
    翻完所有分页；列表空白时刷新重试一次，仍空则报读取失败
    （返回 {"error": "读取失败", ...} 的单项列表，调用方据此写报告、不静默跳过）。
    """
    from .config_base import course_url
    url = course.get("url") or course_url(course.get("courseid"),
                                          course.get("clazzid"))
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_timeout(3000)
    except Exception:
        time.sleep(3)

    def _read_list():
        items = []
        try:
            raw = page.evaluate(
                """() => {
                  const rows = document.querySelectorAll(
                    ".homework-list li, [class*='homework'] li, .work-list li");
                  return [...rows].map((li) => ({
                    title: (li.innerText || "").split("\\n")[0].trim(),
                    text: li.innerText || "",
                    href: (li.querySelector("a") || {}).href || "",
                  }));
                }"""
            )
        except Exception:
            return []
        for r in raw or []:
            title = r.get("title", "")
            if not title:
                continue
            href = r.get("href", "")
            m = re.search(r"workId=(\d+)", href) or re.search(r"workid=(\d+)", href)
            text = r.get("text", "")
            if "已完成" in text or "已提交" in text:
                status = "已完成"
            elif "待批阅" in text:
                status = "待批阅"
            elif "未交" in text:
                status = "未交"
            else:
                status = "未开始"
            start_m = re.search(r"(\d{4}-\d{2}-\d{2}[^\\n]*)", text)
            items.append({
                "title": title,
                "workid": m.group(1) if m else "",
                "url": href,
                "status": status,
                "start_time": start_m.group(1) if start_m else "",
            })
        return items

    items = _read_list()
    # 翻完所有分页
    for _ in range(20):
        if not _click_first(page, "pagination_next"):
            break
        try:
            page.wait_for_timeout(2000)
        except Exception:
            time.sleep(2)
        items.extend(_read_list())
    # 列表空白时刷新重试一次
    if not items:
        try:
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
        except Exception:
            time.sleep(3)
        items = _read_list()
    if not items:
        return [{"title": "", "workid": "", "url": "", "status": "读取失败",
                 "start_time": "", "error": f"{course.get('name','')} 作业列表读取失败"}]
    # 按标题去重（翻页时同一页可能重复读到）
    seen, out = set(), []
    for it in items:
        key = it.get("workid") or it.get("title")
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def _is_exam_title(title):
    return any(w in (title or "") for w in EXAM_TITLE_WORDS)


def _human_check_needed(page):
    """页面是否出现需要人工确认/验证的提示。"""
    try:
        content = page.content() or ""
    except Exception:
        content = ""
    return [w for w in HUMAN_CHECK_WORDS if w in content]


def _lookup_one(q, provider):
    """向外部答案提供方查一道题。返回 ("certain", 答案) 或 ("uncertain", 原因)。

    只按题号查（provider.lookup(qnum, stem, qtype)）；题干是图片的题
    （如高数公式题）同样按题号查，查不到 / 没把握就判 uncertain、留空，不猜。
    """
    qnum, stem, qtype = q.get("qnum"), q.get("stem", ""), q.get("qtype", "")
    return provider.lookup(qnum, stem, qtype)


def _answer_one_question(page, q, provider, answers_map):
    """查外部答案 + 按答案作答一道题。返回 QuestionResult；uncertain 的题留空。"""
    qnum = q.get("qnum")
    status, value = _lookup_one(q, provider)
    if status != "certain":
        return QuestionResult(qnum=qnum, certain=False, note=value)
    answer = str(value).strip()
    qtype = q.get("qtype", "")
    try:
        if qtype in ("单选题", "判断题"):
            _click_option(page, q, answer)
        elif qtype == "多选题":
            for ch in re.findall(r"[A-D]", answer.upper()):
                _click_option(page, q, ch)
        elif qtype == "填空题":
            _fill_blanks(page, q, answer)
        else:
            # 题型未知：按选项字母能点的就点，点不到判不确定
            if re.search(r"[A-D]", answer.upper()):
                _click_option(page, q, answer)
            else:
                return QuestionResult(qnum=qnum, certain=False,
                                      note=f"第 {qnum} 题题型未知，无法作答")
    except Exception as e:
        return QuestionResult(qnum=qnum, certain=False, note=f"第 {qnum} 题作答异常：{e}")
    answers_map[qnum] = (qtype, answer)
    return QuestionResult(qnum=qnum, certain=True, note=f"答案：{answer}", answer=answer)


def _click_option(page, q, answer):
    """在题目块内按选项字母/文字点选。找不到可点选项时抛错，调用方判不确定。"""
    label = re.search(r"[A-D]", str(answer).upper())
    target = label.group(0) if label else str(answer).strip()
    clicked = False
    for sel in SELECTORS["option_item"]:
        try:
            loc = page.locator(sel)
            n = loc.count()
        except Exception:
            continue
        for i in range(n):
            try:
                item = loc.nth(i)
                txt = item.inner_text() or ""
                if txt.strip().startswith(target) or target in txt:
                    item.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                continue
        if clicked:
            break
    if not clicked:
        # 退路：按文字精确匹配整个页面内的选项
        page.locator(f"text={target}").first.click(timeout=5000)


def _fill_blanks(page, q, answer):
    """填空：答案按逗号/分号/顿号拆成多空，依次填入输入框。"""
    parts = [p.strip() for p in re.split(r"[,;；、]", str(answer)) if p.strip()]
    inputs = page.locator(SELECTORS["fill_blank_input"][0])
    for i, part in enumerate(parts):
        try:
            inputs.nth(i).fill(part, timeout=5000)
        except Exception:
            page.locator(SELECTORS["fill_blank_input"][1]).nth(i).fill(part, timeout=5000)


def _verify_saved(page, questions, answers_map):
    """重载后核对：每题当前选中态/填空值是否与外部答案一致。

    answers_map：{qnum: (qtype, answer)}，只含作答时有把握的题。
    返回 (verified: bool, mismatched_qnums: list)。
    """
    saved = _extract_questions(page)
    by_num = {q.get("qnum"): q for q in saved}
    mismatched = []
    for q in questions:
        qnum = q.get("qnum")
        cur = by_num.get(qnum)
        if cur is None:
            mismatched.append(qnum)
            continue
        if qnum not in answers_map:
            continue  # 不确定题本来就没答，不计入核对
        qtype, answer = answers_map[qnum]
        if qtype == "填空题":
            want = [p.strip() for p in re.split(r"[,;；、]", answer) if p.strip()]
            if [b.strip() for b in cur.get("blanks", [])] != want:
                mismatched.append(qnum)
        else:
            want_labels = set(re.findall(r"[A-D]", answer.upper()))
            got_labels = {o.get("label") for o in cur.get("options", []) if o.get("checked")}
            if want_labels and want_labels != got_labels:
                mismatched.append(qnum)
    return (not mismatched, mismatched)


def answer_assignment(page, assignment, provider=None):
    """填答一份作业，返回报告字典。

    {title, total, answered, uncertain_qnums, action, status,
     verified: bool, note}
    action="submitted" 只在提交门通过且最终核对通过时出现。
    provider：外部答案提供方（common.answer_provider.AnswerProvider，
    如 JsonFileAnswerProvider / DictAnswerProvider；自测用 mock provider 注入）。
    provider 为 None 时跳过作答：不打开作业页、不填题、不保存、不提交，
    返回 status="awaiting_answers"，note 写明「待外部提供答案」。
    """
    title = assignment.get("title", "")
    result = {"title": title, "total": 0, "answered": 0,
              "uncertain_qnums": [], "action": "temp_saved",
              "status": "temp_saved",
              "verified": False, "note": ""}
    if _is_exam_title(title):
        result["status"] = "skipped"
        result["note"] = "标题含考试/竞赛关键词，按铁律跳过，不代答"
        return result
    if provider is None:
        result["action"] = "awaiting_answers"
        result["status"] = "awaiting_answers"
        result["note"] = "待外部提供答案：未传入答案（do_homework.py --answers <答案 JSON>），未填题、未保存、未提交"
        return result

    # 1. 打开作业（window.open 新标签优先用 expect_popup，否则同页打开）
    work_page = page
    try:
        with page.expect_popup() as pop:
            page.goto(assignment.get("url", ""), wait_until="domcontentloaded", timeout=60000)
        work_page = pop.value
    except Exception:
        try:
            page.goto(assignment.get("url", ""), wait_until="domcontentloaded", timeout=60000)
            work_page = page
        except Exception as e:
            result["status"] = "skipped"
            result["note"] = f"打开作业失败：{e}"
            return result
    try:
        work_page.wait_for_timeout(3000)
    except Exception:
        time.sleep(3)

    # 2. 人工确认检查
    hits = _human_check_needed(work_page)
    if hits:
        result["status"] = "skipped"
        result["note"] = f"页面出现人工确认项（{','.join(hits)}），立刻停手，未作答"
        return result

    # 3. 提取题目并向 provider 查答案、作答
    questions = _extract_questions(work_page)
    result["total"] = len(questions)
    if not questions:
        result["status"] = "skipped"
        result["note"] = "未提取到题目，未作答"
        return result
    answers_map = {}
    results = [_answer_one_question(work_page, q, provider, answers_map) for q in questions]
    result["answered"] = sum(1 for r in results if r.certain)
    result["uncertain_qnums"] = sorted(r.qnum for r in results if not r.certain)

    # 4. 点「暂时保存」（无论能否提交都先保存）
    _click_first(work_page, "temp_save_button")
    try:
        work_page.wait_for_timeout(2000)
    except Exception:
        time.sleep(2)

    # 5. 提交前必须重载页面核对答案已保留
    try:
        work_page.reload(wait_until="domcontentloaded")
        work_page.wait_for_timeout(2000)
    except Exception:
        time.sleep(2)
    verified, mismatched = _verify_saved(work_page, questions, answers_map)
    result["verified"] = verified
    if not verified:
        result["note"] = (f"重载核对发现答案未保留（题号：{', '.join(map(str, mismatched))}），"
                          "只暂时保存，不提交")
        return result

    # 6. 提交门判定——唯一能点「提交」的地方
    decision = decide(results)
    result["note"] = summarize(decision)
    result["status"] = result["action"]  # temp_saved：只暂时保存，绝不提交半份作业
    if decision.action != "submit":
        return result

    # 7. submit_with_gate 路径：点提交，并只在提交门通过时确认提交确认弹窗
    if not _click_first(work_page, "submit_button"):
        result["note"] += "；提交按钮未找到，未提交"
        return result
    try:
        work_page.wait_for_timeout(2000)
        # 确认弹窗：只点「确认/确定/提交」，且只在提交门已通过的前提下
        for sel in ["button:has-text('确认')", "button:has-text('确定')",
                    "button:has-text('提交')"]:
            try:
                loc = work_page.locator(sel)
                if loc.count() > 0:
                    loc.first.click(timeout=5000)
                    break
            except Exception:
                continue
    except Exception:
        pass
    try:
        work_page.wait_for_timeout(2000)
    except Exception:
        time.sleep(2)
    # 8. 最终核对：页面出现「已提交/提交成功」才算 submitted
    try:
        content = work_page.content() or ""
    except Exception:
        content = ""
    if "已提交" in content or "提交成功" in content:
        result["action"] = "submitted"
        result["status"] = "submitted"
    else:
        result["note"] += "；已点提交但未见提交成功标记，请人工复核"
    try:
        work_page.close()
    except Exception:
        pass
    return result
