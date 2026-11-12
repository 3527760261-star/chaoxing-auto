# -*- coding: utf-8 -*-
"""外部答案提供方（common.answer_provider）。

脚本只做机械层，不做任何模型调用、不猜题。答案由操作者用的智能体
（例如用仓库 `doubao/` 下的豆包提示词让豆包来答）提供，写进 JSON 文件，
再由 `do_homework.py --answers <path.json>` 传入。

协议：AnswerProvider.lookup(qnum, stem, qtype) 返回
  ("certain", 答案)   —— 有把握的答案，可以填；
  ("uncertain", 原因) —— 没把握 / 没给答案，该题留空。
调用方（common.homework.answer_assignment）只认这个返回值：
certain 才填，uncertain 一律留空，由提交门决定只「暂时保存」不提交。
"""
import json
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class AnswerProvider(Protocol):
    """答案提供方协议：按题号查答案，只返回有把握 / 没把握两种结论。"""

    def lookup(self, qnum, stem, qtype):
        """返回 ("certain", 答案) 或 ("uncertain", 原因)。

        qnum：题号（int）；stem：题干文字（图片题可能为空）；
        qtype：题型，如「单选题」「多选题」「判断题」「填空题」。
        """
        ...


def _uncertain(qnum):
    return ("uncertain", f"第 {qnum} 题暂无有把握的外部答案，留空")


def _from_value(qnum, value):
    """把一条 JSON/字典里的值转成 ("certain", 答案) 或 ("uncertain", 原因)。

    接受两种写法：
    - 字符串：{"1": "B"}，表示有把握的答案；
    - 字典：{"1": {"answer": "B", "certain": true}}，certain 为 true 才算有把握。
    空答案、certain 为 false（或缺失）、其它类型的值一律判 uncertain。
    """
    if isinstance(value, str):
        answer = value.strip()
        return ("certain", answer) if answer else _uncertain(qnum)
    if isinstance(value, dict):
        if value.get("certain") is not True:
            return _uncertain(qnum)
        answer = str(value.get("answer", "")).strip()
        return ("certain", answer) if answer else _uncertain(qnum)
    return _uncertain(qnum)


class DictAnswerProvider:
    """内存字典答案提供方：{题号: 答案}，答案字符串表示有把握。

    题号可用 int 或 str 作键；字典里没有的题返回 uncertain。
    供自测 mock 与调用方程序化注入答案使用。
    """

    def __init__(self, answers):
        self._answers = {str(k): v for k, v in dict(answers or {}).items()}

    def lookup(self, qnum, stem, qtype):
        value = self._answers.get(str(qnum))
        if value is None:
            return _uncertain(qnum)
        return _from_value(qnum, value)


class JsonFileAnswerProvider:
    """JSON 文件答案提供方：读一个 JSON 文件，格式见 answers/README.md。

    {"<题号>": "B"} 或 {"<题号>": {"answer": "B", "certain": true}}。
    文件里没有的题、certain 为 false 的题一律返回 ("uncertain", ...)。
    文件不存在、JSON 解析失败时构造即抛错（调用方据此停下，不静默跳过）。
    """

    def __init__(self, path):
        path = Path(path)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"答案文件不是合法 JSON：{path}（{e}）") from e
        if not isinstance(data, dict):
            raise ValueError(f"答案文件顶层必须是 JSON 对象（题号 -> 答案）：{path}")
        self._path = path
        self._answers = {str(k): v for k, v in data.items()}

    @property
    def path(self):
        return self._path

    def lookup(self, qnum, stem, qtype):
        value = self._answers.get(str(qnum))
        if value is None:
            return _uncertain(qnum)
        return _from_value(qnum, value)
