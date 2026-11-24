#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_roles.py — 独立审查 / 开工 / 暂停闸门（v4.7.1）：退出码即结论。

用法：
    python check_roles.py --date 2026-11-19 --stage start
    python check_roles.py --date 2026-11-19 --stage pause --spec docs/specs/2026-11-19-xxx.md
    python check_roles.py --date 2026-11-19 --stage sign|verify|accept [--reviews-dir docs/reviews] [--spec ...]
    python check_roles.py --date 2026-11-19 --stage verify --json

阶段（§3 阶段表）：
    start   <date>-auditor-start.md + <date>-auditor-patrol.md
            （start artifact 早于第一个实现提交与 tmp/first-write.json；轮次 >=3；间隔 <=5 分钟或事前声明事件触发）
    pause   --spec 必填；spec status: paused；<date>-pause.md 且 mtime < spec mtime；
            结束指令清单 / 新派发=0 / 旧契约停止 / 产出保留 / 未停住项 / 恢复条件；
            spec_before_revision/hash/snapshot 绑定暂停前 spec 快照
    sign    <date>-referee-J1.md（spec_revision / spec_hash / 汇总来源）
    verify  J1/J3/security/auditor + referee/security/auditor-start + patrol + failure log
    accept  verify 全部 + <date>-referee-J4.md

固定字段：
    报告    角色 / 审查者 / 会话标识 / 未参与编码声明 / 未参与 spec 编写声明 / 结论 /
            证据 / spec_revision / spec_hash / 汇总来源（报告路径或叶子会话，C12）
    start   角色 / 审查者 / 会话标识 / 启动时间 / spec_revision / spec_hash /
            未参与编码声明 / 未参与 spec 编写声明
    patrol  启动时间 / 巡检间隔 / 轮次（>=3，每轮 trigger/成员/证据/异常/动作）/ 末轮 last_active_at（C11）/ 结论
    failure task / subagent / failure_class / attempt / 证据 / 动作 / 结论

退出码：0 = 通过；1 = 有错误。路径：--reviews-dir / --spec resolve() 后必须在仓库根内。
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_hash import hash_for_scope, scope_for_text  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE_REPORTS = {
    "sign": [("referee", "referee-J1")],
    "verify": [
        ("referee", "referee-J1"),
        ("referee", "referee-J3"),
        ("security", "security"),
        ("auditor", "auditor"),
    ],
    "accept": [
        ("referee", "referee-J1"),
        ("referee", "referee-J3"),
        ("security", "security"),
        ("auditor", "auditor"),
        ("referee", "referee-J4"),
    ],
}
START_FILES = [
    ("referee", "referee-start"),
    ("security", "security-start"),
    ("auditor", "auditor-start"),
]
ROLE_ORDER = ["referee", "security", "auditor"]
ROLE_ALIASES = {
    "referee": "referee",
    "\u88c1\u5224\u5458": "referee",
    "judge": "referee",
    "security": "security",
    "\u4ee3\u7801\u5b89\u5168\u5458": "security",
    "\u5b89\u5168": "security",
    "auditor": "auditor",
    "\u5ba1\u8ba1\u5458": "auditor",
    "\u5ba1\u67e5\u5458": "auditor",
    "audit": "auditor",
    "\u76d1\u5bdf\u5458": "auditor",
}
SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|token|access[_-]?key|private[_-]?key|client[_-]?secret)\s*[:=]"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}"),
]
PATH_LINE_RE = re.compile(r"[A-Za-z0-9_./\\-]+\.(?:py|md|json|txt|ps1|sh|ya?ml|toml|cfg|ini|js|ts|tsx|jsx|html|css|sql|log)\s*:\s*\d+")
ANY_LINE_RE = re.compile(r":\d+")
CMD_RE = re.compile(r"(?:\u547d\u4ee4|cmd|exit|\u9000\u51fa\u7801|\u8fd4\u56de\u7801).{0,24}\b\d+\b", re.IGNORECASE)
ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")
HEX64_RE = re.compile(r"[0-9a-fA-F]{64}")
ROUND_RE = re.compile(r"^##\s*\u7b2c\s*(\d+)\s*\u8f6e\s*[\u2014\u2013\-:\uff1a]?\s*(.*)$")
HEADING_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$")
BACKTICK = chr(96)
REPORT_PATH_RE = re.compile(r"(?<![A-Za-z0-9_./:-])((?:\./)?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\.(?:md|json|txt|log|py))")
TEST_FINISHED_RE = re.compile(r"(?m)^\s*[-*]?\s*run_finished(?:_at)?\s*[：:]\s*(\S+)")
LEAF_SUMMARY_TOKENS = ("无子代理报告", "叶子会话")
C11_MIN_REVISION = 4
C11_TOLERANCE = timedelta(minutes=5)
V472_FROM = date(2026, 11, 21)
ROLE_DISPATCH_KEYS = ("dev", "tester", "security", "referee", "auditor")
DISPATCH_SOURCES = ("reuse", "new_missing", "new_overflow", "new_independent", "new_replace")


def read_first_write_time(marker_raw, root, errors, warnings):
    """读 tmp/first-write.json，返回 aware datetime 或 None。"""
    marker_path = resolve_in_root(marker_raw, root, "first-write marker", errors, must_exist=True)
    if marker_path is None:
        return None
    marker_text, marker_error = read_utf8(marker_path)
    if marker_error:
        errors.append("first-write 标记读取失败：%s" % marker_error)
        return None
    try:
        record = json.loads(marker_text)
    except ValueError as exc:
        errors.append("first-write 标记不是合法 JSON：%s" % exc)
        return None
    if not isinstance(record, dict):
        errors.append("first-write 标记必须是 JSON 对象")
        return None
    raw_time = str(record.get("first_write_at", "")).strip()
    parsed_time = parse_time(raw_time)
    first_write_time = to_aware(parsed_time)
    if not first_write_time or parsed_time is None or parsed_time.tzinfo is None:
        errors.append("first-write 标记缺少或时间非法：first_write_at=%r（ISO8601 带时区，如 2026-11-20T10:50:00+08:00）" % raw_time)
        return None
    raw_path = str(record.get("path", "")).strip()
    parts = Path(raw_path.replace("\\", "/")).parts if raw_path else ()
    if not raw_path:
        errors.append("first-write 标记缺少 path（首个写任务的目标文件）")
    elif Path(raw_path).is_absolute() or raw_path.startswith(("/", "\\")) or ".." in parts:
        errors.append("first-write 标记 path 必须是仓库相对路径：%r" % raw_path)
    warnings.append("first-write 标记：path=%s first_write_at=%s" % (raw_path or "（空）", first_write_time.isoformat()))
    return first_write_time


def read_test_report_finished(root, report_raw, errors, warnings):
    """读测试报告所有 run_finished(_at) 的最大值；返回 aware datetime 或 None。"""
    report_path = resolve_in_root(report_raw, root, "test report", errors, must_exist=True)
    if report_path is None:
        return None
    report_text, read_error = read_utf8(report_path)
    if read_error:
        errors.append("测试报告读取失败：%s" % read_error)
        return None
    values = []
    for match in TEST_FINISHED_RE.finditer(normalize_newlines(report_text)):
        stamp = to_aware(parse_time(match.group(1)))
        if stamp is not None:
            values.append(stamp)
    if not values:
        errors.append("测试报告缺少 run_finished_at：%s（C11 需要运行窗口）" % report_raw)
        return None
    return max(values)


def last_round_body(text):
    lines = normalize_newlines(text).split("\n")
    rounds = []
    for index, line in enumerate(lines):
        match = ROUND_RE.match(line)
        if match:
            rounds.append((int(match.group(1)), index))
    if not rounds:
        return ""
    start = rounds[-1][1]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if re.match(r"^##\s", lines[index]):
            end = index
            break
    return "\n".join(lines[start + 1:end])


def check_patrol_liveness(filename, text, threshold, errors):
    """C11：末轮 last_active_at 必须 >= threshold。"""
    body = last_round_body(text)
    raw = extract_field(body, "last_active_at")
    if not raw:
        raw = extract_field_line(text, "last_active_at")
    if not raw:
        errors.append("%s 末轮缺少 last_active_at（C11：监察员活跃时间必须落盘）" % filename)
        return
    value = strip_cell(raw)
    if value.startswith("["):
        try:
            values = [to_aware(parse_time(str(item))) for item in json.loads(value)]
            values = [item for item in values if item is not None]
            last_active = max(values) if values else None
        except (ValueError, TypeError):
            last_active = None
    else:
        last_active = to_aware(parse_time(value))
    if last_active is None:
        errors.append("%s 末轮 last_active_at 时间非法：%r（ISO8601 带时区）" % (filename, raw))
        return
    if threshold is not None and last_active < threshold:
        errors.append("%s 末轮 last_active_at %s 早于阈值 %s（C11：max(first_write_at, test_run_finished)-5min）" % (
            filename, last_active.isoformat(), threshold.isoformat()))


def _require_c11(spec):
    revision = str(spec.get("revision") or "").strip()
    try:
        return int(revision) >= C11_MIN_REVISION
    except ValueError:
        return False


def _require_v472(spec):
    name = Path(str(spec.get("rel") or spec.get("path") or "")).name
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})-", name)
    if not match:
        return False
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3))) >= V472_FROM
    except ValueError:
        return False


def _json_field(text, name):
    raw = extract_field_line(text, name)
    if not raw:
        return None, raw
    value = strip_cell(raw)
    try:
        return json.loads(value), value
    except ValueError:
        return None, value


def _iso_list(value):
    if isinstance(value, list):
        return [to_aware(parse_time(str(item))) for item in value]
    if isinstance(value, str):
        parts = re.split(r"[、,，;；\s]+", value.strip())
        return [to_aware(parse_time(item)) for item in parts if item]
    return []


def _time_field_list(text, names):
    for name in names:
        raw = extract_field_line(text, name)
        if not raw:
            continue
        value = strip_cell(raw)
        if value.startswith("["):
            try:
                data = json.loads(value)
            except ValueError:
                return None
            return [to_aware(parse_time(str(item))) for item in data]
        return [to_aware(parse_time(item)) for item in re.split(r"[、,，;；\s]+", value) if item]
    return []


def check_patrol_v472(filename, text, spec, root, errors, warnings, c12_threshold=None, require_c12=False):
    """C8/C12/C13：reviewer_dispatch、role_dispatch、last_active_at、汇总来源。"""
    if not _require_v472(spec):
        return
    dispatch = extract_field_line(text, "reviewer_dispatch")
    if not dispatch or not strip_cell(dispatch):
        errors.append("%s 缺少 C8 字段：reviewer_dispatch（每 step 唤醒记录）" % filename)

    role_data, role_raw = _json_field(text, "role_dispatch")
    if role_data is None:
        errors.append("%s 缺少或无法解析 C13 字段：role_dispatch（JSON：{角色:{dispatch_at,source}}）" % filename)
        role_data = {}
    elif not isinstance(role_data, dict):
        errors.append("%s 的 role_dispatch 必须是 JSON 对象" % filename)
        role_data = {}
    dispatch_times = []
    non_reviewer_times = []
    for role in ROLE_DISPATCH_KEYS:
        item = role_data.get(role)
        if not isinstance(item, dict):
            errors.append("%s 的 role_dispatch 缺角色或结构非法：%s" % (filename, role))
            continue
        stamp = to_aware(parse_time(str(item.get("dispatch_at", ""))))
        if stamp is None:
            errors.append("%s 的 role_dispatch.%s.dispatch_at 缺失或时间非法" % (filename, role))
        else:
            dispatch_times.append(stamp)
            if role != "auditor":
                non_reviewer_times.append(stamp)
        source = str(item.get("source", "")).strip()
        if source not in DISPATCH_SOURCES:
            errors.append("%s 的 role_dispatch.%s.source 非法：%r（允许 %s）" % (
                filename, role, source, "/".join(DISPATCH_SOURCES)))
        elif source.startswith("new_") and not str(item.get("reason", "")).strip():
            errors.append("%s 的 role_dispatch.%s 为 %s 但缺少 reason（C13）" % (filename, role, source))

    if require_c12:
        reviewer_at = to_aware(parse_time(str(extract_field_line(text, "reviewer_dispatch_at") or "")))
        if reviewer_at is None:
            errors.append("%s 缺少 C12 字段：reviewer_dispatch_at" % filename)
        elif non_reviewer_times and reviewer_at >= min(non_reviewer_times):
            errors.append("%s 的 reviewer_dispatch_at %s 不早于最早非 reviewer 角色派发 %s（C12 顺序）" % (
                filename, reviewer_at.isoformat(), min(non_reviewer_times).isoformat()))
        heartbeat_at = to_aware(parse_time(str(extract_field_line(text, "heartbeat_effective_at") or "")))
        if heartbeat_at is None:
            errors.append("%s 缺少 C12 字段：heartbeat_effective_at（当前心跳机制生效时间）" % filename)

        active_raw, _ = _json_field(text, "last_active_at")
        active_values = [item for item in _iso_list(active_raw) if item is not None]
        if not active_values:
            errors.append("%s 缺少或无法解析 C12 字段：last_active_at（轮次时间戳列表）" % filename)
        elif c12_threshold is not None and max(active_values) < c12_threshold:
            errors.append("%s 的 last_active_at 末值 %s 早于阈值 %s（C12 新鲜度）" % (
                filename, max(active_values).isoformat(), c12_threshold.isoformat()))

        pause_values = _time_field_list(text, ("reviewer_pause", "pause"))
        resume_values = _time_field_list(text, ("reviewer_resume", "resume"))
        if pause_values is None or resume_values is None:
            errors.append("%s 的 pause/resume 时间格式非法（C12）" % filename)
            pause_values, resume_values = [], []
        if len(pause_values) != len(resume_values):
            errors.append("%s 的 pause/resume 数量不匹配（C12）" % filename)
        pause_segments = []
        for pause_at, resume_at in zip(pause_values, resume_values):
            if pause_at is None or resume_at is None or resume_at < pause_at:
                errors.append("%s 的 pause/resume 区间非法（C12）" % filename)
                continue
            pause_segments.append((pause_at, resume_at))

        round_times = []
        for line in normalize_newlines(text).split("\n"):
            match = ROUND_RE.match(line)
            if match:
                stamp = to_aware(parse_time(match.group(2)))
                if stamp is not None and (heartbeat_at is None or stamp >= heartbeat_at):
                    if not any(pause_at <= stamp <= resume_at for pause_at, resume_at in pause_segments):
                        round_times.append(stamp)
        for index in range(1, len(round_times)):
            previous, current = round_times[index - 1], round_times[index]
            crosses_pause = any(previous < resume_at and current > pause_at for pause_at, resume_at in pause_segments)
            if crosses_pause:
                continue
            gap = (current - previous).total_seconds()
            if gap > 60:
                errors.append("%s 第 %d 轮与第 %d 轮间隔 %d 秒 > 60 秒（C12）" % (
                    filename, index, index + 1, int(gap)))

        summary_data, summary_raw = _json_field(text, "汇总来源")
        if not isinstance(summary_data, dict):
            errors.append("%s 缺少或无法解析 C12 字段：汇总来源（JSON：{角色:报告路径}）" % filename)
        else:
            for role in ROLE_DISPATCH_KEYS:
                rel_path = summary_data.get(role)
                if not isinstance(rel_path, str) or not rel_path.strip():
                    errors.append("%s 的汇总来源缺角色或路径为空：%s（C12）" % (filename, role))
                    continue
                real = Path(os.path.realpath(str(Path(root) / rel_path.strip())))
                if not is_inside(real, root) or not real.is_file():
                    errors.append("%s 的汇总来源.%s 路径不存在或越界：%s（C12）" % (filename, role, rel_path))


def extract_report_paths(summary):
    paths = []
    for match in REPORT_PATH_RE.finditer(summary):
        value = match.group(1)
        if value.startswith("./"):
            value = value[2:]
        if value not in paths:
            paths.append(value)
    return paths


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------

def normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


SECTION1_RE = re.compile(r"^##\s*1[.\u3001\s]")
SECTION9_RE = re.compile(r"^##\s*9[.\u3001\s]")
ACCEPTANCE_CHECK_RE = re.compile(r"^(\s*[-*]\s+\[)[xX](\]\s+\*{0,2}A\d+\b)")


def normalize_acceptance_marks(lines):
    """代码层归一化：- [x] A<n> / - [X] A<n> → - [ ] A<n>；只动 A 行，§9 已排除。"""
    return [ACCEPTANCE_CHECK_RE.sub(r"\1 \2", line) for line in lines]


def signing_body(text):
    """§§1–8 签约正文：## 1. 行到 ## 9. 前一行，按行 \n 连接（CRLF→LF），不额外追加尾随换行。"""
    lines = normalize_newlines(text).split("\n")
    start = None
    for index, line in enumerate(lines):
        if SECTION1_RE.match(line):
            start = index
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if SECTION9_RE.match(lines[index]):
            end = index
            break
    return "\n".join(normalize_acceptance_marks(lines[start:end]))


def signing_hash(text):
    return sha256_hex(signing_body(text))


def sha256_file(path):
    digest = hashlib.sha256()
    with open(str(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strip_cell(value):
    text = (value or "").strip()
    if len(text) >= 2 and text[0] == BACKTICK and text[-1] == BACKTICK:
        text = text[1:-1].strip()
    text = text.strip("*").strip()
    return text


def detect_repo_root():
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(Path.cwd()),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return Path(os.path.realpath(proc.stdout.strip()))
    except OSError:
        pass
    return Path(os.path.realpath(str(Path.cwd())))


def is_inside(path, root):
    try:
        child = os.path.normcase(os.path.realpath(str(path)))
        parent = os.path.normcase(os.path.realpath(str(root)))
        return os.path.commonpath([child, parent]) == parent
    except (ValueError, OSError):
        return False


def resolve_in_root(raw, root, label, errors, must_exist=True, want_dir=False):
    path = Path(str(raw))
    if not path.is_absolute():
        path = Path.cwd() / path
    real = Path(os.path.realpath(str(path)))
    if not is_inside(real, root):
        errors.append("%s 越出仓库根：%s（解析为 %s）；拒绝 .. 越界、绝对路径越界、符号链接逃逸" % (label, raw, real))
        return None
    if must_exist and not real.exists():
        errors.append("%s 不存在：%s" % (label, raw))
        return None
    if must_exist and want_dir and not real.is_dir():
        errors.append("%s 不是目录：%s" % (label, raw))
        return None
    if must_exist and (not want_dir) and not real.is_file():
        errors.append("%s 不是文件：%s" % (label, raw))
        return None
    return real


def read_utf8(path):
    try:
        with open(str(path), "r", encoding="utf-8-sig", newline="") as handle:
            return handle.read(), None
    except UnicodeDecodeError as exc:
        return None, "不是合法 UTF-8：%s" % exc
    except OSError as exc:
        return None, "读取失败：%s" % exc


def unquote_value(value):
    text = (value or "").strip()
    pairs = {'"': '"', "'": "'", "\u201c": "\u201d", "\u2018": "\u2019"}
    if len(text) >= 2 and text[0] in pairs and text[-1] == pairs[text[0]]:
        text = text[1:-1]
    return text.strip()


def split_front_matter(text):
    normalized = normalize_newlines(text)
    lines = normalized.split("\n")
    info = {"has": False, "fm": {}, "body": normalized}
    if not lines or lines[0].strip() != "---":
        return info
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return info
    fm = {}
    for line in lines[1:end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        fm[key.strip()] = unquote_value(strip_cell(value))
    info["has"] = True
    info["fm"] = fm
    info["body"] = "\n".join(lines[end + 1:])
    return info


def heading_sections(lines):
    headings = []
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2).strip()))
    sections = []
    for position, (start, level, title) in enumerate(headings):
        end = len(lines)
        for later in headings[position + 1:]:
            if later[1] <= level:
                end = later[0]
                break
        sections.append((title, start + 1, end))
    return sections


def extract_field_line(text, name):
    """取字段所在整行冒号后的全部内容（不因分号截断；用于汇总来源等自由文本）。"""
    pattern = re.compile(
        r"(?m)^\s*[-*]?\s*(?:\*\*)?\s*" + re.escape(name) + r"\s*(?:\*\*)?\s*[：:]\s*(.*)$"
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def extract_field(text, name):
    """逐行取值：冒号后只取同行内容，trim 后返回；空值行返回空串（不得吞下一行）。"""
    pattern = re.compile(
        r"(?:^|[\s>|；;：:])(?:\*\*|`)?\s*" + re.escape(name) + r"\s*(?:\*\*|`)?\s*[：:][ \t]*([^\n；;|]*?)[ \t]*(?=[；;|\n]|$)",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1).strip()


START_FIELD_ALIASES = {
    "角色": ["角色", "role"],
    "审查者": ["审查者", "reviewer"],
    "会话标识": ["会话标识", "session"],
    "启动时间": ["启动时间", "started_at"],
}


def extract_field_any(text, names):
    for name in names:
        value = extract_field(text, name)
        if value is not None and value.strip():
            return value
    return None


def extract_hash(value):
    if not value:
        return None
    match = HEX64_RE.search(value)
    if match:
        return match.group(0).lower()
    return strip_cell(value).lower()


def extract_int(value):
    if not value:
        return None
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def parse_time(value):
    if not value:
        return None
    text = strip_cell(value)
    match = ISO_RE.search(text)
    if match:
        raw = match.group(0).replace(" ", "T")
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        raw = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", raw)
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None
    match = re.search(r"\b(\d{10,13})\b", text)
    if match:
        number = int(match.group(1))
        if number > 10 ** 12:
            number = number / 1000.0
        return datetime.fromtimestamp(number, tz=timezone.utc)
    return None


def to_aware(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return value


def local_tz():
    return datetime.now().astimezone().tzinfo


def is_affirmative(value):
    text = (value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if text.startswith("\u5426") or lowered.startswith("no") or lowered.startswith("false"):
        return False
    if text.startswith("\u662f") or "\u672a\u53c2\u4e0e" in text or lowered.startswith("yes") or lowered.startswith("true"):
        return True
    return None


def verdict_ok(value):
    text = (value or "").strip().upper()
    if not text.startswith("PASS"):
        return False
    return "BLOCK" not in text and "DEVIATION" not in text


def scan_secrets(text):
    hits = []
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            line_number = text.count("\n", 0, match.start()) + 1
            hits.append((line_number, match.group(0)))
    return hits


def run_git(root, arguments):
    try:
        proc = subprocess.run(
            ["git", "-C", str(root)] + list(arguments),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except OSError as exc:
        return 1, "", str(exc)


def rel_posix(path, root):
    return os.path.relpath(str(path), str(root)).replace("\\", "/")


def is_impl_path(path):
    item = path.replace("\\", "/")
    if item.startswith("docs/specs/") or item.startswith("docs/reviews/"):
        return False
    if item == "CHANGELOG.md":
        return False
    return True


def changed_files(root, commit):
    code, out, _err = run_git(root, ["show", "--name-only", "--pretty=format:", "--no-renames", commit])
    if code != 0:
        return None
    return [line.strip().replace("\\", "/") for line in out.split("\n") if line.strip()]


def first_impl_commit(root, spec_rel):
    """返回 (commit, aware_datetime) 或 (None, None)。范围：spec 最新提交..HEAD。"""
    code, out, _err = run_git(root, ["log", "-1", "--format=%H", "--", spec_rel])
    if code != 0 or not out.strip():
        return None, None
    spec_commit = out.strip().split("\n")[0].strip()
    code, out, _err = run_git(root, ["rev-list", "--reverse", "%s..HEAD" % spec_commit])
    if code != 0:
        return None, None
    for commit in [line.strip() for line in out.split("\n") if line.strip()]:
        files = changed_files(root, commit)
        if files is None:
            continue
        if any(is_impl_path(item) for item in files):
            code, when, _err = run_git(root, ["show", "-s", "--format=%cI", commit])
            if code == 0 and when.strip():
                return commit, to_aware(parse_time(when.strip()))
            return commit, None
    return None, None


# ---------------------------------------------------------------------------
# spec / 报告解析
# ---------------------------------------------------------------------------

def resolve_spec(args, root, errors, required=False):
    if args.spec:
        return resolve_in_root(args.spec, root, "spec 路径", errors, must_exist=True)
    pattern = "docs/specs/%s-*.md" % args.date
    candidates = sorted(Path(root).glob(pattern))
    if len(candidates) == 1:
        return Path(os.path.realpath(str(candidates[0])))
    if not candidates:
        message = "未找到 %s 的 spec（%s）；请用 --spec 指定" % (args.date, pattern)
        if required:
            errors.append(message)
        else:
            errors.append(message)
        return None
    errors.append("找到多个 %s 的 spec：%s；请用 --spec 指定唯一契约" % (args.date, "、".join(item.name for item in candidates)))
    return None


def load_spec(spec_real, errors):
    text, read_error = read_utf8(spec_real)
    if read_error:
        errors.append("spec 读取失败：%s" % read_error)
        return None
    info = split_front_matter(text)
    if not info["has"]:
        errors.append("spec 缺少 front matter：%s" % spec_real)
        return None
    return {
        "path": spec_real,
        "rel": rel_posix(spec_real, spec_real.parents[len(spec_real.parents) - 1]),
        "fm": info["fm"],
        "body_hash": signing_hash(text),
        "revision": strip_cell(info["fm"].get("spec_revision", "")),
        "status": strip_cell(info["fm"].get("status", "")),
    }


def check_spec_binding(text, spec, label, errors):
    revision = extract_field(text, "spec_revision")
    hash_value = extract_hash(extract_field(text, "spec_hash"))
    if revision is None or not revision.strip():
        errors.append("%s 缺少字段：spec_revision" % label)
    else:
        revision = strip_cell(revision)
        if spec.get("revision") and revision != spec["revision"]:
            errors.append("%s 的 spec_revision=%s 与 spec 当前值 %s 不一致" % (label, revision, spec["revision"]))
    if not hash_value:
        errors.append("%s 缺少字段：spec_hash" % label)
    elif hash_value != spec["body_hash"]:
        errors.append("%s 的 spec_hash 与当前 spec §§1–8 SHA-256 不一致（报告 = %s，当前 = %s）；§§1–8 改动后旧报告不得复用" % (label, hash_value, spec["body_hash"]))
    return revision, hash_value


def check_secret_scan(text, label, errors):
    hits = scan_secrets(text)
    if hits:
        errors.append("%s 含密钥模式：第 %s 行 %r（报告不得含真实密钥值）" % (
            label,
            ",".join(str(item[0]) for item in hits[:5]),
            hits[0][1],
        ))


# ---------------------------------------------------------------------------
# 报告校验（sign / verify / accept）
# ---------------------------------------------------------------------------

def check_review_report(filename, text, expected_role, spec, errors, warnings, identities, state, root):
    lines = normalize_newlines(text).split("\n")
    sections = heading_sections(lines)
    prefix = filename

    role_raw = extract_field(text, "角色")
    role = ROLE_ALIASES.get((strip_cell(role_raw) or "").lower())
    if not role_raw:
        errors.append("%s 缺少字段：角色" % prefix)
    elif role is None:
        errors.append("%s 角色值无法识别：%s（referee/security/auditor）" % (prefix, role_raw))
    elif role != expected_role:
        errors.append("%s 角色应为 %s，实际 %s" % (prefix, expected_role, role))

    reviewer = strip_cell(extract_field(text, "审查者"))
    session = strip_cell(extract_field(text, "会话标识"))
    if not reviewer:
        errors.append("%s 缺少字段：审查者" % prefix)
    if not session:
        errors.append("%s 缺少字段：会话标识" % prefix)

    for name in ("未参与编码声明", "未参与 spec 编写声明"):
        value = extract_field(text, name)
        state_value = is_affirmative(value)
        if state_value is None:
            errors.append("%s %s 缺失或不明确：%r" % (prefix, name, value))
        elif name == "未参与编码声明" and state_value is False:
            errors.append("%s 声明参与了编码：执行者不得作为审查者（C5）" % prefix)
        elif name == "未参与 spec 编写声明":
            if state_value:
                state["spec_untouched_true"] += 1
            else:
                warnings.append("%s 声明参与了 spec 编写（C5 要求至少 1 名未参与）" % prefix)

    verdict = extract_field(text, "结论")
    if not verdict_ok(verdict):
        errors.append("%s 结论必须为 PASS，实际：%r" % (prefix, verdict))

    check_spec_binding(text, spec, prefix, errors)

    summary = extract_field_line(text, "汇总来源")
    summary_text = strip_cell(summary or "")
    if not summary_text:
        errors.append("%s 缺少字段：汇总来源（监察员是唯一汇总接口；子代理报告路径/ID 列表）" % prefix)
    else:
        leaf_summary = any(token in summary_text for token in LEAF_SUMMARY_TOKENS)
        report_paths = extract_report_paths(summary_text)
        if not report_paths and not leaf_summary:
            errors.append("%s 汇总来源必须列子代理报告路径/ID（无子代理时写“无子代理报告（叶子会话）”）" % prefix)
        for rel_path in report_paths:
            real = Path(os.path.realpath(str(Path(root) / rel_path)))
            if not is_inside(real, root) or not real.is_file():
                errors.append("%s 汇总来源路径不存在或越界：%s" % (prefix, rel_path))

    evidence = None
    for title, start, end in sections:
        if "证据" in title:
            evidence = [line.strip() for line in lines[start:end] if line.strip()]
            break
    if evidence is None:
        errors.append("%s 缺少 证据 节" % prefix)
        evidence = []
    qualified = [item for item in evidence if ANY_LINE_RE.search(item) or CMD_RE.search(item)]
    if len(qualified) < 3:
        errors.append("%s 证据不足：需要 >=3 条 path:line 或 命令+退出码，实际 %d 条" % (prefix, len(qualified)))
    if evidence and not any(PATH_LINE_RE.search(item) for item in evidence):
        errors.append("%s 证据缺少可追溯的 path:line（至少 1 条带文件路径）" % prefix)

    check_secret_scan(text, prefix, errors)

    if role and reviewer and session:
        identities[role]["reviewers"].add(reviewer.lower())
        identities[role]["sessions"].add(session.lower())


# ---------------------------------------------------------------------------
# start artifact / patrol
# ---------------------------------------------------------------------------

def check_start_artifact(filename, text, expected_role, spec, errors, warnings, first_impl_time, state, first_write_time=None):
    prefix = filename
    role_raw = extract_field_any(text, START_FIELD_ALIASES["角色"])
    role = ROLE_ALIASES.get((strip_cell(role_raw) or "").lower())
    if not role_raw:
        errors.append("%s 缺少字段：角色（或 role）" % prefix)
    elif role is None:
        errors.append("%s 角色值无法识别：%s（referee/security/auditor）" % (prefix, role_raw))
    elif role != expected_role:
        errors.append("%s 角色应为 %s，实际 %s" % (prefix, expected_role, role))

    reviewer = strip_cell(extract_field_any(text, START_FIELD_ALIASES["审查者"]))
    session = strip_cell(extract_field_any(text, START_FIELD_ALIASES["会话标识"]))
    if not reviewer:
        errors.append("%s 缺少字段：审查者（或 reviewer）" % prefix)
    if not session:
        errors.append("%s 缺少字段：会话标识（或 session）" % prefix)

    started_raw = extract_field_any(text, START_FIELD_ALIASES["启动时间"])
    started = to_aware(parse_time(started_raw))
    if not started:
        errors.append("%s 缺少字段或时间格式非法：启动时间（ISO8601，如 2026-11-19T12:37:07+08:00）" % prefix)
    elif first_impl_time is not None and started >= first_impl_time:
        errors.append("%s 的启动时间 %s 不早于第一个实现提交 %s（开工后补派 = FAIL）" % (
            prefix, started.isoformat(), first_impl_time.isoformat()))
    if started is not None and first_write_time is not None and started >= first_write_time:
        errors.append("%s 的启动时间 %s 不早于 first-write 标记 %s（C6：start 必须早于首个写任务）" % (
            prefix, started.isoformat(), first_write_time.isoformat()))

    check_spec_binding(text, spec, prefix, errors)

    for name in ("未参与编码声明", "未参与 spec 编写声明"):
        value = extract_field(text, name)
        state_value = is_affirmative(value)
        if state_value is None:
            errors.append("%s %s 缺失或不明确：%r" % (prefix, name, value))
        elif state_value is False:
            errors.append("%s 声明参与了%s：start artifact 必须由独立只读角色本人写" % (prefix, "编码" if "编码" in name else " spec 编写"))

    check_secret_scan(text, prefix, errors)

    state["starts"][expected_role] = {
        "reviewer": reviewer.lower() if reviewer else "",
        "session": session.lower() if session else "",
        "started": started,
    }


def check_patrol(filename, text, spec, errors, warnings, first_impl_time, start_state, first_write_time=None, last_active_threshold=None):
    prefix = filename
    normalized = normalize_newlines(text)
    lines = normalized.split("\n")

    started = to_aware(parse_time(extract_field(text, "启动时间")))
    if not started:
        errors.append("%s 缺少字段或时间格式非法：启动时间" % prefix)
    elif first_impl_time is not None and started >= first_impl_time:
        errors.append("%s 的启动时间 %s 不早于第一个实现提交 %s（C14）" % (
            prefix, started.isoformat(), first_impl_time.isoformat()))
    if started is not None and first_write_time is not None and started >= first_write_time:
        errors.append("%s 的启动时间 %s 不早于 first-write 标记 %s（C6）" % (
            prefix, started.isoformat(), first_write_time.isoformat()))

    interval_text = extract_field(text, "巡检间隔") or ""
    if not interval_text:
        errors.append("%s 缺少字段：巡检间隔（定时或事前声明事件触发）" % prefix)
    event_trigger = "事件触发" in interval_text

    rounds = []
    for index, line in enumerate(lines):
        match = ROUND_RE.match(line)
        if match:
            rounds.append((int(match.group(1)), index, match.group(2)))
    round_numbers = [item[0] for item in rounds]
    if len(set(round_numbers)) < 3:
        errors.append("%s 轮次不足：需要 >=3 轮（C14），实际 %d 轮" % (prefix, len(set(round_numbers))))
    if len(set(round_numbers)) != len(round_numbers):
        errors.append("%s 轮次编号重复：%s" % (prefix, round_numbers))

    declared_rounds = extract_int(extract_field(text, "轮次"))
    if declared_rounds is not None and declared_rounds != len(set(round_numbers)):
        errors.append("%s 声明的轮次 %s 与实际轮次标题数 %d 不一致" % (prefix, declared_rounds, len(set(round_numbers))))

    round_times = []
    for position, (number, index, rest) in enumerate(rounds):
        end = rounds[position + 1][1] if position + 1 < len(rounds) else len(lines)
        body = "\n".join(lines[index + 1:end])
        stamp = to_aware(parse_time(rest))
        if stamp is None:
            stamp = to_aware(parse_time(body))
        if stamp is None:
            errors.append("%s 第 %d 轮缺少时间（标题或轮次正文内需 ISO8601）" % (prefix, number))
        else:
            round_times.append((number, stamp))
        for label in ("trigger", "成员", "证据", "异常", "动作"):
            if label not in body and label.upper() not in body.upper():
                errors.append("%s 第 %d 轮缺少字段：%s" % (prefix, number, label))

    if round_times:
        first_number, first_time = round_times[0]
        if started is not None and first_time < started:
            errors.append("%s 首轮时间 %s 早于启动时间 %s" % (prefix, first_time.isoformat(), started.isoformat()))
        if first_impl_time is not None and first_time >= first_impl_time:
            errors.append("%s 首轮时间 %s 不早于第一个实现提交 %s（C14）" % (
                prefix, first_time.isoformat(), first_impl_time.isoformat()))
        if first_write_time is not None and first_time >= first_write_time:
            errors.append("%s 首轮时间 %s 不早于 first-write 标记 %s（C6）" % (
                prefix, first_time.isoformat(), first_write_time.isoformat()))
        for index in range(1, len(round_times)):
            gap = (round_times[index][1] - round_times[index - 1][1]).total_seconds()
            if gap > 300 and not event_trigger:
                errors.append("%s 第 %d 轮与第 %d 轮间隔 %d 秒 > 300 秒，且未事前声明事件触发（C14）" % (
                    prefix, round_times[index - 1][0], round_times[index][0], int(gap)))

    conclusion = None
    sections = heading_sections(lines)
    for title, start, end in sections:
        if "结论" in title:
            for line in lines[start:end]:
                if line.strip():
                    conclusion = line.strip()
                    break
            break
    if conclusion is None:
        errors.append("%s 缺少 结论 节" % prefix)
    elif not verdict_ok(conclusion):
        errors.append("%s 结论必须为 PASS，实际：%r" % (prefix, conclusion))

    check_secret_scan(text, prefix, errors)

    reviewer = strip_cell(extract_field_any(text, START_FIELD_ALIASES["审查者"])).lower()
    session = strip_cell(extract_field_any(text, START_FIELD_ALIASES["会话标识"])).lower()
    if not reviewer:
        errors.append("%s 缺少字段：审查者" % prefix)
    if not session:
        errors.append("%s 缺少字段：会话标识" % prefix)
    auditor = start_state["starts"].get("auditor") or {}
    if reviewer and auditor.get("reviewer") and reviewer != auditor["reviewer"]:
        errors.append("%s 的审查者 %s 与 auditor-start 的 %s 不一致（patrol 必须由该监察员本人写）" % (
            prefix, reviewer, auditor["reviewer"]))
    if session and auditor.get("session") and session != auditor["session"]:
        errors.append("%s 的会话标识与 auditor-start 不一致（同一监察员）" % prefix)
    if last_active_threshold is not None:
        check_patrol_liveness(filename, text, last_active_threshold, errors)


# ---------------------------------------------------------------------------
# pause
# ---------------------------------------------------------------------------

def check_pause(filename, text, spec_real, spec, errors, warnings, root):
    prefix = filename
    if spec.get("status") != "paused":
        errors.append("spec status 必须为 paused（C16），实际：%s" % (spec.get("status") or "（空）"))
    try:
        pause_mtime = Path(filename).stat().st_mtime
        spec_mtime = Path(spec_real).stat().st_mtime
    except OSError as exc:
        errors.append("无法读取 pause/spec 的 mtime：%s" % exc)
        return
    if not pause_mtime < spec_mtime:
        errors.append("pause.md mtime 必须早于 spec mtime（先暂停后改 spec；C16），实际 pause=%s spec=%s" % (
            datetime.fromtimestamp(pause_mtime).isoformat(),
            datetime.fromtimestamp(spec_mtime).isoformat(),
        ))

    for label in ("暂停时间", "触发原话", "活跃成员", "结束指令清单", "旧契约停止", "产出保留", "未停住项", "恢复条件"):
        if label not in text:
            errors.append("%s 缺少字段：%s" % (prefix, label))
    if not re.search(r"新派发\s*[=＝:：]\s*0", text):
        errors.append("%s 缺少字段或值非 0：新派发=0" % prefix)

    marker = text.find("结束指令清单")
    if marker >= 0:
        tail = text[marker:]
        rows = 0
        for line in tail.split("\n")[1:20]:
            stripped = line.strip()
            if stripped.startswith("|") and "---" not in stripped:
                rows += 1
            elif stripped.startswith(("- ", "* ")):
                rows += 1
        if rows == 0:
            errors.append("%s 结束指令清单为空（需要目标/时间/确认）" % prefix)

    # C7：pause 记录变更前契约，不要求等于当前 spec
    revision = strip_cell(extract_field(text, "spec_before_revision") or "")
    hash_value = extract_hash(extract_field(text, "spec_before_hash") or "")
    snapshot_raw = strip_cell(extract_field(text, "spec_before_snapshot") or "")
    snapshot_raw = strip_cell(snapshot_raw.strip("。；;，, "))
    missing = []
    if not revision:
        missing.append("spec_before_revision")
    if not hash_value:
        missing.append("spec_before_hash")
    if not snapshot_raw:
        missing.append("spec_before_snapshot")
    if missing:
        errors.append("%s 缺少 C7 字段：%s（pause.md 必须记录暂停前 spec 的 revision/hash/snapshot）" % (
            prefix, "、".join(missing)))

    snapshot_path = None
    if snapshot_raw:
        snapshot_path = resolve_in_root(snapshot_raw, root, "spec_before_snapshot", errors, must_exist=True)
    else:
        candidates = []
        if revision:
            candidates.append("tmp/spec-before-%s.md" % revision)
        if spec.get("revision"):
            candidates.append("tmp/spec-before-%s.md" % spec["revision"])
        for candidate in candidates:
            real = Path(os.path.realpath(str(Path(root) / candidate)))
            if is_inside(real, root) and real.is_file():
                snapshot_path = real
                break
        if snapshot_path is None and candidates:
            errors.append("%s 找不到 C7 快照：%s" % (prefix, "、".join(candidates)))

    if snapshot_path is not None:
        snapshot_text, read_error = read_utf8(snapshot_path)
        if read_error:
            errors.append("%s 的 C7 快照读取失败：%s" % (prefix, read_error))
        else:
            snapshot_scope = scope_for_text(snapshot_text, Path(spec_real).name)
            snapshot_hash = hash_for_scope(snapshot_text, snapshot_scope) if snapshot_scope else signing_hash(snapshot_text)
            if hash_value and snapshot_hash != hash_value:
                errors.append("%s 的 spec_before_hash 与快照签名 hash 不一致（记录=%s，快照=%s，scope=%s）" % (
                    prefix, hash_value, snapshot_hash, snapshot_scope or "legacy"))
            snapshot_info = split_front_matter(snapshot_text)
            snapshot_revision = strip_cell(snapshot_info["fm"].get("spec_revision", ""))
            if revision and snapshot_revision and snapshot_revision != revision:
                errors.append("%s 的 spec_before_revision=%s 与快照 front matter spec_revision=%s 不一致" % (
                    prefix, revision, snapshot_revision))

    check_secret_scan(text, prefix, errors)


# ---------------------------------------------------------------------------
# failure log（C17）
# ---------------------------------------------------------------------------

FAILURE_FIELDS = ["task", "subagent", "failure_class", "attempt", "证据", "动作", "结论"]


def check_failure_log(filename, text, errors, warnings):
    prefix = filename
    check_secret_scan(text, prefix, errors)
    normalized = normalize_newlines(text)
    if "无失败" in normalized or "0 次失败" in normalized:
        return
    starts = [match.start() for match in re.finditer(r"(?m)^\s*(?:[-*]\s+)?(?:\*\*)?task(?:\*\*)?\s*[：:]", normalized)]
    if not starts:
        errors.append("%s 无失败记录，也未声明“无失败”；failure log 是硬证据（C17）" % prefix)
        return
    records = 0
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(normalized)
        block = normalized[start:end]
        values = {}
        for name in FAILURE_FIELDS:
            pattern = re.compile(
                r"(?m)^\s*(?:[-*]\s+)?(?:\*\*)?\s*" + re.escape(name) + r"\s*(?:\*\*)?\s*[：:]\s*(.+?)\s*$"
            )
            match = pattern.search(block)
            if match:
                values[name] = match.group(1).strip()
        missing = [name for name in FAILURE_FIELDS if not values.get(name)]
        if missing:
            errors.append("%s 第 %d 条失败记录缺字段：%s" % (prefix, records + 1, "、".join(missing)))
            continue
        records += 1
        failure_class = values["failure_class"].lower()
        attempt = extract_int(values["attempt"])
        if "dispatch_failed" not in failure_class and "execution_failed" not in failure_class:
            errors.append("%s 第 %d 条 failure_class 非法：%s（dispatch_failed/execution_failed）" % (
                prefix, records, values["failure_class"]))
        if attempt is None:
            errors.append("%s 第 %d 条 attempt 不是整数：%s" % (prefix, records, values["attempt"]))
        else:
            if "dispatch_failed" in failure_class and attempt != 1:
                errors.append("%s 第 %d 条派发失败 attempt=%d：派发失败 1 次后必须换新子智能体（C17），3 次空转 = FAIL" % (
                    prefix, records, attempt))
            if "execution_failed" in failure_class and attempt > 3:
                errors.append("%s 第 %d 条执行失败 attempt=%d：执行失败最多 3 次尝试（初次+2 重试，C17）" % (
                    prefix, records, attempt))
        action = values.get("动作", "") + " " + values.get("结论", "")
        if re.search(r"主脑(自做|执行|代做|自行执行)", action) and "用户授权" not in action:
            errors.append("%s 第 %d 条记录显示主脑自做且无用户显式授权（C17）" % (prefix, records))
    if records == 0:
        errors.append("%s 没有可解析的失败记录（schema：task/subagent/failure_class/attempt/证据/动作/结论）" % prefix)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(description="校验独立审查 / 开工 / 暂停闸门（start/pause/sign/verify/accept）")
    parser.add_argument("--date", required=True, help="审查日期，格式 YYYY-MM-DD")
    parser.add_argument("--stage", required=True, choices=["start", "pause", "sign", "verify", "accept"], help="闸门阶段")
    parser.add_argument("--reviews-dir", default="docs/reviews", help="审查报告目录（默认 docs/reviews）")
    parser.add_argument("--spec", help="spec 路径（默认 docs/specs/<date>-*.md）")
    parser.add_argument("--first-write", default="tmp/first-write.json", help="C6 首写标记（默认 tmp/first-write.json）")
    parser.add_argument("--test-report", help="C11 测试报告（默认 docs/reviews/<date>-test-report.md）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser


def emit(result, as_json):
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("date   : %s" % result["date"])
        print("stage  : %s" % result["stage"])
        print("reviews: %s" % result["reviews_dir"])
        print("spec   : %s" % result["spec"])
        print("报告   : %s" % ("、".join(result["required"]) or "（无）"))
        for report in result["reports"]:
            status = "PASS" if report.get("ok") else "FAIL"
            print("  - %-34s %s 证据 %s" % (report["file"], status, report.get("evidence_count", "-")))
        for warning in result["warnings"]:
            print("WARN   : %s" % warning)
        for error in result["errors"]:
            print("ERROR  : %s" % error)
        print("结果   : %s（%d 错误 / %d 警告）" % ("PASS" if result["ok"] else "FAIL", len(result["errors"]), len(result["warnings"])))
    return 0 if result["ok"] else 1


def main(argv=None):
    args = build_parser().parse_args(argv)
    errors = []
    warnings = []
    reports = []
    result = {
        "date": args.date,
        "stage": args.stage,
        "reviews_dir": args.reviews_dir,
        "spec": "",
        "required": [],
        "reports": reports,
        "errors": errors,
        "warnings": warnings,
        "ok": False,
    }

    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        errors.append("--date 必须是 YYYY-MM-DD：%s" % args.date)
        return emit(result, args.json)

    root = detect_repo_root()
    reviews_real = resolve_in_root(args.reviews_dir, root, "reviews-dir", errors, must_exist=True, want_dir=True)
    if reviews_real is None:
        return emit(result, args.json)
    result["reviews_dir"] = str(reviews_real)

    if args.stage == "pause" and not args.spec:
        errors.append("--stage pause 必须提供 --spec <spec>（C16）")
        return emit(result, args.json)
    spec_real = resolve_spec(args, root, errors)
    spec = None
    if spec_real is not None:
        result["spec"] = str(spec_real)
        spec = load_spec(spec_real, errors)
        if spec is not None:
            spec["rel"] = rel_posix(spec_real, root)
    if spec is None:
        return emit(result, args.json)

    identities = {role: {"reviewers": set(), "sessions": set()} for role in ROLE_ORDER}
    state = {"spec_untouched_true": 0, "starts": {}}

    def report_entry(filename, role):
        entry = {"file": filename, "role": role, "ok": False, "evidence_count": 0}
        reports.append(entry)
        result["required"].append(filename)
        return entry

    def read_required(filename, entry):
        path = reviews_real / filename
        real = Path(os.path.realpath(str(path)))
        if not is_inside(real, root):
            errors.append("%s 越出仓库根（符号链接逃逸）：%s" % (filename, real))
            return None
        if not real.is_file():
            errors.append("缺文件：%s（--stage %s 必需）" % (filename, args.stage))
            return None
        text, read_error = read_utf8(real)
        if read_error:
            errors.append("%s 读取失败：%s" % (filename, read_error))
            return None
        return text

    if args.stage == "start":
        first_write_time = read_first_write_time(args.first_write, root, errors, warnings)
        require_c11 = _require_c11(spec)
        patrol_liveness_threshold = None
        if require_c11:
            if first_write_time is None:
                errors.append("C11 无法计算阈值：first-write 标记缺失或非法")
            else:
                patrol_liveness_threshold = first_write_time - C11_TOLERANCE

        first_commit, first_time = first_impl_commit(root, spec["rel"])
        if first_commit is None:
            warnings.append("尚无实现提交（%s..HEAD 无实现文件提交），跳过 start/首轮早于实现的时序校验" % spec["rel"])
        else:
            warnings.append("第一个实现提交：%s（%s）" % (first_commit[:12], first_time.isoformat() if first_time else "时间未知"))

        for expected_role, suffix in START_FILES:
            filename = "%s-%s.md" % (args.date, suffix)
            entry = report_entry(filename, expected_role)
            text = read_required(filename, entry)
            if text is None:
                continue
            check_start_artifact(filename, text, expected_role, spec, errors, warnings, first_time, state, first_write_time)
            entry["ok"] = True

        patrol_name = "%s-auditor-patrol.md" % args.date
        entry = report_entry(patrol_name, "auditor")
        text = read_required(patrol_name, entry)
        if text is not None:
            check_patrol(patrol_name, text, spec, errors, warnings, first_time, state, first_write_time, patrol_liveness_threshold)
            check_patrol_v472(patrol_name, text, spec, root, errors, warnings, require_c12=False)
            entry["ok"] = True

    elif args.stage == "pause":
        pause_name = "%s-pause.md" % args.date
        entry = report_entry(pause_name, "auditor")
        text = read_required(pause_name, entry)
        if text is not None:
            check_pause(str(reviews_real / pause_name), text, spec_real, spec, errors, warnings, root)
            entry["ok"] = True

    else:
        for expected_role, suffix in STAGE_REPORTS[args.stage]:
            filename = "%s-%s.md" % (args.date, suffix)
            entry = report_entry(filename, expected_role)
            text = read_required(filename, entry)
            if text is None:
                continue
            before = len(errors)
            check_review_report(filename, text, expected_role, spec, errors, warnings, identities, state, root)
            entry["ok"] = len(errors) == before
            evidence_lines = [line for line in normalize_newlines(text).split("\n")]
            entry["evidence_count"] = len([line for line in evidence_lines if ANY_LINE_RE.search(line) or CMD_RE.search(line)])

        if args.stage in ("verify", "accept"):
            first_commit, first_time = first_impl_commit(root, spec["rel"])
            require_c11 = _require_c11(spec)
            require_v472 = _require_v472(spec)
            patrol_liveness_threshold = None
            c12_threshold = None
            if require_c11 or require_v472:
                first_write_time = read_first_write_time(args.first_write, root, errors, warnings)
                report_raw = args.test_report or "docs/reviews/%s-test-report.md" % args.date
                test_finished = read_test_report_finished(root, report_raw, errors, warnings)
                if first_write_time is not None and test_finished is not None:
                    anchor = max(first_write_time, test_finished)
                    if require_c11:
                        patrol_liveness_threshold = anchor - C11_TOLERANCE
                    if require_v472:
                        c12_threshold = anchor - timedelta(seconds=60)
                else:
                    errors.append("C11/C12 无法计算阈值：first-write 标记或测试报告 run_finished_at 缺失")
            for expected_role, suffix in START_FILES:
                filename = "%s-%s.md" % (args.date, suffix)
                entry = report_entry(filename, expected_role)
                text = read_required(filename, entry)
                if text is None:
                    continue
                check_start_artifact(filename, text, expected_role, spec, errors, warnings, first_time, state)
                entry["ok"] = True
            patrol_name = "%s-auditor-patrol.md" % args.date
            entry = report_entry(patrol_name, "auditor")
            text = read_required(patrol_name, entry)
            if text is not None:
                check_patrol(patrol_name, text, spec, errors, warnings, first_time, state, None, patrol_liveness_threshold)
                check_patrol_v472(patrol_name, text, spec, root, errors, warnings, c12_threshold, require_c12=True)
                entry["ok"] = True
            failure_name = "%s-failure-log.md" % args.date
            entry = report_entry(failure_name, "auditor")
            text = read_required(failure_name, entry)
            if text is not None:
                check_failure_log(failure_name, text, errors, warnings)
                entry["ok"] = True

        for left in range(len(ROLE_ORDER)):
            for right in range(left + 1, len(ROLE_ORDER)):
                role_a, role_b = ROLE_ORDER[left], ROLE_ORDER[right]
                shared_reviewers = identities[role_a]["reviewers"] & identities[role_b]["reviewers"]
                if shared_reviewers:
                    errors.append("%s 与 %s 的审查者相同：%s（三类角色身份必须两两不同）" % (
                        role_a, role_b, "、".join(sorted(shared_reviewers))))
                shared_sessions = identities[role_a]["sessions"] & identities[role_b]["sessions"]
                if shared_sessions:
                    errors.append("%s 与 %s 的会话标识相同：%s（三类角色身份必须两两不同）" % (
                        role_a, role_b, "、".join(sorted(shared_sessions))))

        if args.stage in ("verify", "accept") and state["spec_untouched_true"] == 0:
            errors.append("没有任何报告声明“未参与 spec 编写”（C5 要求至少 1 名）")

    result["ok"] = not errors
    return emit(result, args.json)


if __name__ == "__main__":
    sys.exit(main())
