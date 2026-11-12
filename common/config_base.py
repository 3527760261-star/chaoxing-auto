# -*- coding: utf-8 -*-
"""共享配置基底（common.config_base）。

铁律（违反就停手）：
1. 只处理老师布置的虚拟题库作业/课程任务点；正式计分考试、补考、竞赛卷一律不代答。
2. 提交门：全部题目都有把握（不确定数=0）才提交；有 1 道不确定就只「暂时保存」，
   绝不提交半份作业；提交前必须重载页面核对答案已保留。
3. 不代签到；不绕过人脸识别、弹题、拖动验证、验证码；平台要求人工确认时立刻停下。
4. 不索要、不保存账号密码，登录由用户本人在浏览器里完成。

课程信息不在这里写死：每个用户在仓库根目录放自己的 config.py
（从 config.example.py 复制），课程表 COURSES、cpi、要跳过的假班
SKIP_CLAZZIDS 都从那里加载（load_config），找不到 config.py 时报清晰的错。
电话、邮箱、密码、cookie、登录态这些绝不进仓库——仓库本来就不需要它们。
"""
import dataclasses
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 数据目录
#   优先级：环境变量 CX_DATA_DIR > Windows 默认 %LOCALAPPDATA%/cxauto
#          > 其它系统默认 ~/.cxauto
# ---------------------------------------------------------------------------
if os.environ.get("CX_DATA_DIR"):
    DATA_DIR = Path(os.environ["CX_DATA_DIR"]).expanduser()
elif os.name == "nt":
    DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "cxauto"
else:
    DATA_DIR = Path.home() / ".cxauto"

PROFILE_DIR = DATA_DIR / "edge_profile"      # profile 模式的浏览器档案
STATE_FILE = DATA_DIR / "state.json"         # 已完成作业 / 视频的状态
SCAN_FILE = DATA_DIR / "scan.json"           # 最近一次巡检结果
REPORTS_DIR = DATA_DIR / "reports"           # 每轮 CSV 明细
LOG_DIR = DATA_DIR / "logs"                  # run.log / summary.jsonl
SHOT_DIR = DATA_DIR / "shots"                # 异常截图

# ---------------------------------------------------------------------------
# 用户课程配置：从仓库根 config.py 加载，不写死任何真实值
# ---------------------------------------------------------------------------

# config.example.py 里的示例 ID 都以这 8 个 0 开头（如 000000001）；
# 真实学习通课程号是 9 位数字，不会以 8 个 0 开头，所以可用来识别占位符。
EXAMPLE_ID_PREFIX = "00000000"


class ConfigError(Exception):
    """用户配置缺失或无效：config.py 找不到、读不懂或缺字段。"""


@dataclasses.dataclass
class UserConfig:
    """从用户 config.py 加载的课程配置。"""
    courses: dict
    cpi: str
    skip_clazzids: set = dataclasses.field(default_factory=set)


_MISSING_CONFIG_HINT = (
    "找不到用户配置文件 config.py：请把仓库根目录的 config.example.py "
    "复制为 config.py，再填入你自己的课程号（courseid/clazzid/cpi，"
    "都在学习通课程页 URL 里找，见仓库根 README「填你自己的课程信息」一节）；"
    "也可以用环境变量 CX_CONFIG_PATH 指定配置文件的位置。"
)

_CONFIG_CACHE = {}


def is_placeholder_id(value):
    """是不是占位符课程号：<...> 或示例数字（00000000 开头）。"""
    v = str(value or "")
    return v.startswith("<") or v.startswith(EXAMPLE_ID_PREFIX)


def _resolve_config_path(explicit=None):
    """算出要用的配置文件路径（只算路径，不读文件）。

    优先级：显式传入的 config_path > 环境变量 CX_CONFIG_PATH
    > DATA_DIR/config.py（存在才用） > 仓库根 config.py（存在才用）。
    显式路径 / CX_CONFIG_PATH 指向的文件不存在时也原样返回，
    由 load_config() 报「文件不存在」的错，不静默换别的配置。
    都没有时返回 None。
    """
    if explicit is not None:
        return Path(explicit).expanduser()
    if os.environ.get("CX_CONFIG_PATH"):
        return Path(os.environ["CX_CONFIG_PATH"]).expanduser()
    for cand in (DATA_DIR / "config.py",
                 Path(__file__).resolve().parent.parent / "config.py"):
        if cand.is_file():
            return cand
    return None


def _load_config_module(path):
    """把 config.py 当作 Python 模块加载；读不懂就抛 ConfigError。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_cx_user_config", path)
    if spec is None or spec.loader is None:
        raise ConfigError(f"读不懂配置文件：{path}。{_MISSING_CONFIG_HINT}")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        raise ConfigError(
            f"配置文件执行失败：{path}：{e}。请对照 config.example.py 检查格式。"
        ) from e
    return mod


def _normalize_courses(raw):
    """校验并规范化 COURSES：每门课必须有 courseid/clazzid。"""
    if not isinstance(raw, dict) or not raw:
        raise ConfigError(
            "config.py 里 COURSES 必须是非空字典："
            "每门课 {name, courseid, clazzid, do_homework, do_video}。"
        )
    courses = {}
    for key, item in raw.items():
        if not isinstance(item, dict):
            raise ConfigError(f"config.py 里 COURSES[{key!r}] 必须是字典。")
        courseid = str(item.get("courseid") or "")
        clazzid = str(item.get("clazzid") or "")
        if not courseid or not clazzid:
            raise ConfigError(
                f"config.py 里 COURSES[{key!r}] 缺 courseid 或 clazzid。"
            )
        courses[key] = {
            "name": item.get("name") or key,
            "courseid": courseid,
            "clazzid": clazzid,
            "do_homework": bool(item.get("do_homework", False)),
            "do_video": bool(item.get("do_video", False)),
        }
    return courses


def load_config(config_path=None, force=False):
    """加载用户课程配置（按路径缓存，同一进程里只读一次）。

    查找顺序：显式 config_path > 环境变量 CX_CONFIG_PATH
    > DATA_DIR/config.py > 仓库根 config.py。
    找不到文件时抛 ConfigError（带清晰的修复指引）；
    文件里缺 COURSES/CPI 或格式不对时同样抛 ConfigError。
    force=True 时忽略缓存重读（自测用）。
    """
    path = _resolve_config_path(config_path)
    if path is None:
        raise ConfigError(_MISSING_CONFIG_HINT)
    key = str(path)
    if not force and key in _CONFIG_CACHE:
        return _CONFIG_CACHE[key]
    if not path.is_file():
        raise ConfigError(f"配置文件不存在：{path}。{_MISSING_CONFIG_HINT}")
    mod = _load_config_module(path)
    courses = _normalize_courses(getattr(mod, "COURSES", None))
    cpi = getattr(mod, "CPI", None)
    if not cpi or not str(cpi).strip():
        raise ConfigError(
            f"config.py 里缺 CPI：{path}。CPI 是你自己的固定值，"
            "在学习通课程页 URL 里找。"
        )
    skip = getattr(mod, "SKIP_CLAZZIDS", set()) or set()
    if isinstance(skip, (str, bytes)):
        skip = {skip}
    try:
        skip_clazzids = {str(s) for s in skip}
    except TypeError:
        raise ConfigError(
            f"config.py 里 SKIP_CLAZZIDS 必须是集合/列表：{path}。"
        ) from None
    cfg = UserConfig(courses=courses, cpi=str(cpi), skip_clazzids=skip_clazzids)
    _CONFIG_CACHE[key] = cfg
    return cfg


def reset_config_cache():
    """清空 load_config 的缓存（自测用；正常运行不需要调）。"""
    _CONFIG_CACHE.clear()


def get_courses():
    """用户配置里的课程表（COURSES）。"""
    return load_config().courses


def get_cpi():
    """用户配置里的 cpi。"""
    return load_config().cpi


def get_skip_clazzids():
    """用户配置里要跳过的假班 clazzid 集合（默认空）。"""
    return load_config().skip_clazzids


def is_skipped_class(course, skip_clazzids=None):
    """该课程是不是要跳过的假班（clazzid 在 SKIP_CLAZZIDS 里）。"""
    if skip_clazzids is None:
        skip_clazzids = load_config().skip_clazzids
    return str(course.get("clazzid", "")) in {str(s) for s in skip_clazzids}


def course_url(courseid, clazzid, cpi=None):
    """拼学习通课程页 URL。cpi 不传时用用户配置里的 CPI。"""
    if cpi is None:
        cpi = load_config().cpi
    return (
        "https://mooc1-2.chaoxing.com/visit/stucoursemiddle"
        f"?courseid={courseid}&clazzid={clazzid}&cpi={cpi}&ut=s"
    )


# ---------------------------------------------------------------------------
# 行为参数（已验证的设计思路：视频看到 96% 即停）
# ---------------------------------------------------------------------------
VIDEO_DONE_RATIO = 0.96   # 视频 currentTime/duration 达到 96% 即视为看完，停播
POLL_SEC = 20             # 视频播放轮询间隔（秒）
VIDEO_MAX_HOURS = 1.3     # 单个视频最长播放时长（小时），超时停手
ROUND_TIMEOUT = 900       # 单轮巡检+填答+播放总超时（秒），Windows 值守循环用 subprocess timeout 落实

# ---------------------------------------------------------------------------
# 铁律与禁点词
# ---------------------------------------------------------------------------
IRON_RULES = [
    "只处理老师布置的虚拟题库作业/课程任务点；正式计分考试、补考、竞赛卷一律不代答。",
    "提交门：全部题目都有把握（不确定数=0）才自动提交；有 1 道不确定就只点「暂时保存」，绝不提交半份作业；提交前必须重载页面核对答案已保留。",
    "不代签到；不绕过人脸识别、弹题、拖动验证、验证码；平台要求人工确认时立刻停下。",
    "不索要、不保存账号密码，登录由用户本人在浏览器里完成。",
    "电话、邮箱、密码、cookie、登录态绝不进仓库；token/cookie 只放本机数据目录。",
]

# 含这些词的按钮/链接默认禁止点击；唯一例外是 submit_gate.decide() 通过后
# 的 submit_with_gate 路径（见 common/homework.py）。
FORBIDDEN_CLICK_WORDS = ["提交", "交卷", "submit", "Submit", "SUBMIT", "确认提交"]


def ensure_dirs():
    """创建 DATA_DIR 下全部子目录。"""
    for d in (DATA_DIR, PROFILE_DIR, REPORTS_DIR, LOG_DIR, SHOT_DIR):
        d.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def seed_state_if_missing():
    """STATE_FILE 不存在时写入四个空列表的模板；已存在则不动（绝不覆盖真实记录）。"""
    from .state import seed_state

    ensure_dirs()
    if not STATE_FILE.exists():
        STATE_FILE.write_text(seed_state(), encoding="utf-8")
    return STATE_FILE
