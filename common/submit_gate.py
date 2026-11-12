# -*- coding: utf-8 -*-
"""提交门（common.submit_gate）。纯逻辑，不依赖 Playwright，可离线单测。

铁律（本次新规则，取代旧的「永不提交」）：
- 只有一份作业全部题目都有把握答案（不确定数=0）时才自动点提交；
- 只要有 1 道不确定，就只点「暂时保存」，并在报告里列出不确定题号，
  绝不提交半份作业。
- 提交前必须重载页面核对答案已保留（核对逻辑在 common/homework.py，
  本模块只做「能不能提交」的判定）。

调用方唯一合法的提交路径：decide() 返回 action="submit" 时，
才允许点击「提交」按钮并确认提交确认弹窗；其余任何路径都不许点提交
（见 common/selectors.py 的 FORBIDDEN_CLICK_WORDS 说明与自测 save_only 项）。
"""
from dataclasses import dataclass, field


@dataclass
class QuestionResult:
    """一道题的作答结果。"""
    qnum: int
    certain: bool
    note: str = ""  # 不确定时写原因；有把握时可写所用答案摘要
    answer: str = ""  # 有把握时记录外部提供的答案（供重载核对复用）


@dataclass
class SubmitDecision:
    """提交门判定结果。"""
    action: str  # "submit" | "temp_save"
    uncertain_qnums: list = field(default_factory=list)
    reason: str = ""


def decide(results):
    """判定一份作业能不能提交。

    规则：题目数 > 0 且全部 certain 才 submit，否则 temp_save。
    空作业（0 题）不提交——可能是页面提取失败，提交空卷比不交更糟。
    """
    results = list(results or [])
    if not results:
        return SubmitDecision(
            action="temp_save",
            uncertain_qnums=[],
            reason="未提取到任何题目，无法判定，暂不提交（只保存）",
        )
    uncertain = sorted(r.qnum for r in results if not r.certain)
    if uncertain:
        return SubmitDecision(
            action="temp_save",
            uncertain_qnums=uncertain,
            reason=f"共 {len(results)} 题，其中 {len(uncertain)} 题不确定"
                   f"（题号：{', '.join(map(str, uncertain))}），只暂时保存，绝不提交半份作业",
        )
    return SubmitDecision(
        action="submit",
        uncertain_qnums=[],
        reason=f"共 {len(results)} 题，全部有把握，可以提交",
    )


def summarize(decision):
    """把判定结果写成一行报告文字（供 CSV / 每日检查记录复用）。"""
    if decision.action == "submit":
        return f"提交门：通过（{decision.reason}）"
    return (f"提交门：不通过，只暂时保存"
            f"（不确定题号：{', '.join(map(str, decision.uncertain_qnums)) or '无'}；"
            f"{decision.reason}）")
