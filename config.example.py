# -*- coding: utf-8 -*-
"""用户配置示例（config.example.py）。

使用方法：
1. 把本文件复制为仓库根目录的 config.py（不要把 config.py 提交到仓库，
   已被仓库根 .gitignore 覆盖）；
2. 把下面 COURSES 里的三门课换成你自己的课：courseid、clazzid、cpi
   都在学习通课程页 URL 里找——打开一门课，地址栏形如：
   https://mooc1.chaoxing.com/visit/stucoursemiddle?courseid=<你的 courseid>&clazzid=<你的 clazzid>&cpi=<你的 cpi>&...
   三门课的 cpi 是同一个值（你自己的固定值）；
3. 有同名假班要跳过时，把它的 clazzid 写进下面的 SKIP_CLAZZIDS；
4. 再跑 6_自测、2_巡检。

示例值说明：下面所有 ID 都是明显是示例的数字（000000001 这类），
不是真实课程号。直接拿示例值跑，脚本会提示「课程 ID 还是占位符」。

答案不在这里配：脚本不做任何模型调用，答案由操作者用的智能体
（比如用仓库 doubao/ 下的豆包提示词让豆包来答）提供，写进 JSON 文件，
跑填答时用 `do_homework.py --answers <答案 JSON>` 传入（格式见 answers/README.md）。
不给 --answers 时只做巡检与报告，不填题。

电话、邮箱、密码、cookie、登录态绝不进仓库——仓库本来就不需要它们。
"""
# 课程表：键是脚本内部用的代号（ai / math / psy），每门课写你自己的值。
# do_homework=True 表示这门课要做作业；do_video=True 表示要看章节视频任务点。
COURSES = {
    "ai": {
        "name": "AI通识",
        "courseid": "000000001",
        "clazzid": "000000011",
        "do_homework": True,
        "do_video": False,
    },
    "math": {
        "name": "高数A1",
        "courseid": "000000002",
        "clazzid": "000000022",
        "do_homework": True,
        "do_video": False,
    },
    "psy": {
        "name": "心理课",
        "courseid": "000000003",
        "clazzid": "000000033",
        "do_homework": True,
        "do_video": True,
    },
}

# 你的 cpi（学习通课程页 URL 里的 cpi，三门课通用）。
CPI = "000000000"

# 要跳过的假班 clazzid 集合（默认空）。比如心理课有两个同名班，
# 只想处理其中一个时，把另一个班的 clazzid 写进来：
# SKIP_CLAZZIDS = {"000000009"}
SKIP_CLAZZIDS = set()
