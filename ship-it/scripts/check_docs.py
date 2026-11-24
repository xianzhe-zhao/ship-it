#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_docs.py — 全文一致性与去废话闸门（v5.1.0 / C18）：退出码即结论。

用法：
    python ship-it/scripts/check_docs.py --root .
    python ship-it/scripts/check_docs.py --root . --json
    python ship-it/scripts/check_docs.py --root . --spec docs/specs/<spec>.md

扫描集（相对 --root）：
    ship-it/SKILL.md、README.md、ship-it/references/spec-template.md、
    ship-it/references/team-mode.md、当前 spec、ship-it/CHANGELOG.md、
    CHANGELOG.md、docs/deploy-runbook.md。

判定（非 allowlist 命中即 FAIL）：
    stale         旧口径词 / 过期 C-A 计数 / 旧 stage 列表 / 过期测试计数
    duplicate     规范化后 >=30 字符且出现 >=2 次
    long          单行 > --max-line（docs 默认 500；spec 800，C11 条款上限）；4.7.0 CHANGELOG 区块 >300 字符
    contradiction 版本三处 / 9 步 / README 重复 URL / 模板 §2 §9 / 同文件相反口径（仅真正相反：同一对象被要求互斥状态）
    allowlist     历史 CHANGELOG（4.7.0 之前）、spec 修订说明/冲突表/旧口径表/边界表、
                  canonical 签约验收提醒语、git clone URL

退出码：0 = 通过；1 = 有错误（不得交付）。所有路径 resolve() 后必须在仓库根内（C13）。
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCAN_FILES = [
    "ship-it/SKILL.md",
    "README.md",
    "ship-it/references/spec-template.md",
    "ship-it/references/team-mode.md",
    "<SPEC>",  # 占位符，由 resolve_spec 动态选取的 spec 替换
    "ship-it/CHANGELOG.md",
    "CHANGELOG.md",
    "docs/deploy-runbook.md",
]
DEFAULT_SPEC = "<SPEC>"  # 占位符；resolve_spec 动态选取文件名版本号最高者
CHANGELOG_FILES = ("ship-it/CHANGELOG.md", "CHANGELOG.md")
EXPECTED_VERSION = "5.1.0"
EXPECTED_STEPS = 9
DEFAULT_MAX_LINE = 500
SPEC_MAX_LINE = 800  # C11：每条条款 ≤800 字符；已签约 spec 不再改行
DUPLICATE_MIN_CHARS = 30
CHANGELOG_47_LIMIT = 300
CHANGELOG_MAJOR_LIMIT = 600  # major 版本（主版本号变更，如 5.0.0）变更多，放宽到 600
CANONICAL_MARKER = "刚才的说明可能造成误解"

HEADING_RE = re.compile(r"^(#{1,6})\s")
FENCE_RE = re.compile(r"^\s*(`{3}|~~~)")
SKILL_VERSION_RE = re.compile(r"^version\s*[:：]\s*(\d+\.\d+\.\d+)\s*$")
SECTION_VERSION_RE = re.compile(r"^##\s+v?(\d+\.\d+\.\d+)\b")
ROW_VERSION_RE = re.compile(r"^\|\s*v?(\d+\.\d+\.\d+)\s*\|")
CLAUSE_HEADING_RE = re.compile(r"^#{2,6}\s*C(\d+)\b")
ACCEPT_ITEM_RE = re.compile(r"^\s*[-*]\s*\[[ xX]\]\s*A(\d+)\b")
STAGE_WORD = r"(?:draft|spec|verify|accept|start|pause|sign)"
STAGE_LIST_RE = re.compile(r"(" + STAGE_WORD + r"(?:\s*[/|、,，]\s*" + STAGE_WORD + r")+)")
STAGE_TOKEN_RE = re.compile(STAGE_WORD)
OLD_SPEC_STAGE_RE = re.compile(r"--stage\s+spec\s*\|\s*verify(?!\s*\|\s*accept)")
OLD_ROLES_STAGE_RE = re.compile(r"--stage\s+sign\s*\|\s*verify\s*\|\s*accept(?!\s*\|)")
CLAUSE_RANGE_RE = re.compile(r"C1\s*(?:[–\-—~]|\.{2,}|至)\s*C?(\d+)")
ACCEPT_RANGE_RE = re.compile(r"A1\s*(?:[–\-—~]|\.{2,}|至)\s*A?(\d+)")
STEP_RE = re.compile(r"(\d+)\s*步(?:编号|工作流|流程|不跳步|契约流程|契约)")
URL_RE = re.compile(r"https?://[^\s)\]}>\"']+")
CLONE_URL_RE = re.compile(r"\bgit\s+clone\s+\S+")
TABLE_SEP_RE = re.compile(r"^\|?\s*:?-{3,}")
EARLY_RE = re.compile(r"(首轮|started_at|启动时间|首个实现提交|首次提交|实现首次提交)[^。；\n]{0,30}(早于|之前)")
LATE_RE = re.compile(r"(首轮|(?<![A-Za-z_])started_at|启动时间|首个实现提交|首次提交|实现首次提交)[^。；\n]{0,30}(晚于|之后)")

NEGATION_WORDS = ("不得", "禁止", "不允许", "严禁", "不能", "不可", "勿")
VIOLATION_WORDS = (
    "FAIL", "违规", "未获授权", "废止", "作废", "取代", "旧口径",
    "已删", "移除", "不再", "禁止", "不得", "不允许", "严禁", "未停住",
)

# (报告名, 正则, guard)；guard=negation 时跳过“不得/禁止…”与失败示例语境。
STALE_PHRASES = [
    ("用户确认 = 签约", re.compile(r"用户确认\s*[=＝]\s*签约"), "plain"),
    ("接受多种验收表述", re.compile(r"接受多种验收表述"), "plain"),
    ("接受任何明确表示验收通过", re.compile(r"接受任何明确表示验收通过"), "plain"),
    ("用户明确表示通过", re.compile(r"用户明确表示通过"), "plain"),
    ("主脑自做（旧口径）", re.compile(r"主脑自做"), "negation"),
    ("主脑内联（旧口径）", re.compile(r"主脑内联"), "negation"),
    ("同类失败一次（旧口径）", re.compile(r"同类失败一次"), "negation"),
    ("含糊同意判定表", re.compile(r"含糊同意判定表"), "plain"),
    ("入口三处", re.compile(r"入口三处"), "plain"),
    ("侧栏+仪表盘+移动底栏", re.compile(r"侧栏\s*[+＋]\s*仪表盘\s*[+＋]\s*移动底栏"), "plain"),
    ("expect-lines-min 1400", re.compile(r"expect-lines-min\s*1400"), "plain"),
    ("过期测试计数 0/13", re.compile(r"(?<![\d/])0/13(?![\d/])"), "plain"),
    ("过期测试计数 0/15", re.compile(r"(?<![\d/])0/15(?![\d/])"), "plain"),
    ("过期测试计数 0/16", re.compile(r"(?<![\d/])0/16(?![\d/])"), "plain"),
    ("过期测试计数 13 tests", re.compile(r"(?<![\d/])13\s+tests?\b"), "plain"),
    ("过期测试计数 Ran 13", re.compile(r"\bRan\s+13\b"), "plain"),
]


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------

def normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def is_inside(path, root):
    try:
        child = os.path.normcase(os.path.realpath(str(path)))
        parent = os.path.normcase(os.path.realpath(str(root)))
        return os.path.commonpath([child, parent]) == parent
    except (ValueError, OSError):
        return False


def rel_posix(path, root):
    return os.path.relpath(str(path), str(root)).replace("\\", "/")


def read_utf8(path):
    try:
        with open(str(path), "r", encoding="utf-8-sig", newline="") as handle:
            return handle.read(), None
    except UnicodeDecodeError as exc:
        return None, "不是合法 UTF-8：%s" % exc
    except OSError as exc:
        return None, "读取失败：%s" % exc


def heading_level(line):
    match = HEADING_RE.match(line)
    return len(match.group(1)) if match else 0


def section_end(lines, start, level):
    for index in range(start + 1, len(lines)):
        current = heading_level(lines[index])
        if current and current <= level:
            return index
    return len(lines)


def version_tuple(value):
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", value or "")
    if not match:
        return None
    return tuple(int(item) for item in match.groups())


def is_historical(value):
    current = version_tuple(EXPECTED_VERSION)
    parsed = version_tuple(value)
    return bool(parsed and current and parsed < current)


def has_violation_context(line):
    return any(word in line for word in VIOLATION_WORDS)


def is_negated(line, start):
    prefix = line[max(0, start - 12):start]
    return any(word in prefix for word in NEGATION_WORDS)


def line_allowed(lineno, regions):
    for start, end, reason in regions:
        if start <= lineno <= end:
            return reason
    return None


# ---------------------------------------------------------------------------
# allowlist 区域
# ---------------------------------------------------------------------------

def spec_regions(lines):
    regions = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("> **修订"):
            regions.append((index + 1, index + 1, "spec 修订说明"))
            continue
        if stripped.startswith("- **优化说明**"):
            end = len(lines)
            for nxt in range(index + 1, len(lines)):
                if lines[nxt].strip().startswith("- **") or heading_level(lines[nxt]):
                    end = nxt
                    break
            regions.append((index + 1, end, "spec §1 优化说明（旧口径/历史说明）"))
            continue
        if stripped.startswith("- **现状基线"):
            regions.append((index + 1, index + 1, "spec §2 现状基线（Step 3 前旧实现）"))
            continue
        level = heading_level(line)
        if not level:
            continue
        if "冲突与裁定" in line:
            regions.append((index + 1, section_end(lines, index, level), "spec 冲突表"))
        elif "旧口径" in line:
            regions.append((index + 1, section_end(lines, index, level), "spec 旧口径表"))
        elif "边界与异常" in line:
            regions.append((index + 1, section_end(lines, index, level), "spec 边界表"))
        elif re.match(r"^##\s*8[.、\s]", line):
            regions.append((index + 1, section_end(lines, index, level), "spec §8 三问状态机"))
    return regions


def changelog_regions(rel, lines):
    regions = []
    for index, line in enumerate(lines):
        match = SECTION_VERSION_RE.match(line)
        if match and is_historical(match.group(1)):
            regions.append((index + 1, section_end(lines, index, 2), "历史 CHANGELOG（4.7.0 之前）"))
    if rel == "CHANGELOG.md":
        for index, line in enumerate(lines):
            match = ROW_VERSION_RE.match(line)
            if match and is_historical(match.group(1)):
                regions.append((index + 1, index + 1, "历史 CHANGELOG（4.7.0 之前）"))
    return regions


# ---------------------------------------------------------------------------
# spec 与文档加载
# ---------------------------------------------------------------------------

def parse_spec_version_from_name(name):
    """解析 spec 文件名中的版本号 v\d+.\d+.\d+，返回 (major, minor, patch) 元组；无则返回 None。"""
    m = re.search(r'v(\d+)\.(\d+)\.(\d+)', name)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def resolve_spec(root, spec_arg, errors, warnings):
    if spec_arg:
        path = Path(str(spec_arg))
        if not path.is_absolute():
            path = root / path
        real = Path(os.path.realpath(str(path)))
        if not is_inside(real, root):
            errors.append("--spec 越出仓库根（C13）：%s 解析为 %s" % (spec_arg, real))
            return None
        if not real.is_file():
            errors.append("--spec 不存在：%s" % spec_arg)
            return None
        return rel_posix(real, root)
    # 默认：扫 docs/specs/*.md，取文件名版本号最高者（SemVer）；并列取文件名日期最新；
    # 无版本号降级取文件名日期最新（同一天取 mtime 最新）
    candidates = []
    specs_dir = root / "docs" / "specs"
    if specs_dir.is_dir():
        for item in sorted(specs_dir.glob("*.md")):
            if re.match(r"^\d{4}-\d{2}-\d{2}-", item.name):
                candidates.append(item)
    if not candidates:
        warnings.append("docs/specs 下没有日期命名的 spec，跳过条款/验收计数检查")
        return None
    # 优先按文件名版本号选；无版本号的 spec 不参与版本号比较
    with_version = [(parse_spec_version_from_name(c.name), c) for c in candidates]
    versioned = [(v, c) for v, c in with_version if v is not None]
    if versioned:
        # 取版本号最高；并列取文件名日期最新（candidates 已按名称 sorted，后者更大）
        best = max(versioned, key=lambda vc: (vc[0], vc[1].name))[1]
    else:
        # 全部无版本号：降级取文件名日期最新（同一天取 mtime 最新）
        warnings.append("docs/specs 下 spec 均无文件名版本号，降级取文件名日期最新（同一天取 mtime 最新）")
        best = max(candidates, key=lambda c: (c.name, c.stat().st_mtime))
    real = Path(os.path.realpath(str(best)))
    if not is_inside(real, root):
        errors.append("spec 越出仓库根（C13）：%s" % real)
        return None
    return rel_posix(real, root)


def load_documents(root, spec_rel, errors, warnings, allowlist):
    documents = []
    scan_list = []
    for rel in SCAN_FILES:
        if rel == DEFAULT_SPEC:
            if spec_rel:
                scan_list.append(spec_rel)
        else:
            scan_list.append(rel)
    if spec_rel and spec_rel not in scan_list:
        scan_list.append(spec_rel)

    for rel in scan_list:
        real = Path(os.path.realpath(str(root / rel)))
        if not is_inside(real, root):
            errors.append("%s 越出仓库根（符号链接逃逸）：%s" % (rel, real))
            continue
        if not real.is_file():
            warnings.append("缺少扫描文件：%s（C18 要求纳入体检）" % rel)
            continue
        text, read_error = read_utf8(real)
        if read_error:
            errors.append("%s 读取失败：%s" % (rel, read_error))
            continue
        lines = normalize_newlines(text).split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        if rel in CHANGELOG_FILES:
            regions = changelog_regions(rel, lines)
        elif rel == spec_rel:
            regions = spec_regions(lines)
        else:
            regions = []
        for start, end, reason in regions:
            allowlist.append({
                "file": rel,
                "start": start,
                "end": end,
                "reason": reason,
                "kind": "region",
            })
        documents.append({"rel": rel, "path": real, "lines": lines, "regions": regions})
        for index, line in enumerate(lines, start=1):
            if CANONICAL_MARKER in line:
                allowlist.append({
                    "file": rel,
                    "line": index,
                    "reason": "canonical 签约/验收提醒语",
                    "kind": "canonical",
                })
            elif CLONE_URL_RE.search(line):
                allowlist.append({
                    "file": rel,
                    "line": index,
                    "reason": "git clone URL",
                    "kind": "url",
                })
    return documents


def spec_counts(lines):
    clauses = []
    acceptance = []
    for line in lines:
        match = CLAUSE_HEADING_RE.match(line)
        if match:
            clauses.append(int(match.group(1)))
        match = ACCEPT_ITEM_RE.match(line)
        if match:
            acceptance.append(int(match.group(1)))
    return (max(clauses) if clauses else 0), (max(acceptance) if acceptance else 0)


# ---------------------------------------------------------------------------
# 单文件扫描
# ---------------------------------------------------------------------------

def detect_script(line, start, end):
    before = line[max(0, start - 60):start]
    after = line[end:end + 60]
    positions = {}
    for name in ("check_spec", "check_roles"):
        pos = before.rfind(name)
        if pos != -1:
            positions[name] = pos
    if positions:
        return max(positions, key=positions.get)
    if "check_spec" in after:
        return "check_spec"
    if "check_roles" in after:
        return "check_roles"
    return None


def scan_document(doc, clause_count, acceptance_count, max_line, stale, long_items, contradictions):
    rel = doc["rel"]
    lines = doc["lines"]
    regions = doc["regions"]
    policy = {
        "self_do_pos": False,
        "self_do_neg": False,
        "inline_pos": False,
        "inline_neg": False,
        "once_rule": False,
        "three_rule": False,
        "early": set(),
        "late": set(),
        "first_draft": False,
        "first_signed": False,
        "latest_draft": False,
        "latest_signed": False,
    }

    for index, line in enumerate(lines, start=1):
        if FENCE_RE.match(line):
            continue
        if line_allowed(index, regions):
            continue
        if CANONICAL_MARKER in line:
            continue

        # 1) 旧口径短语
        reported = set()
        for name, pattern, guard in STALE_PHRASES:
            for match in pattern.finditer(line):
                if guard == "negation" and (is_negated(line, match.start()) or has_violation_context(line)):
                    continue
                if name in reported:
                    continue
                reported.add(name)
                stale.append({
                    "file": rel,
                    "line": index,
                    "pattern": name,
                    "text": line.strip()[:160],
                })

        # 2) 过期 C-A 全量计数
        if clause_count:
            for match in CLAUSE_RANGE_RE.finditer(line):
                if int(match.group(1)) != clause_count:
                    stale.append({
                        "file": rel,
                        "line": index,
                        "pattern": "过期 C 计数 %s（当前 C1–C%d）" % (match.group(0), clause_count),
                        "text": line.strip()[:160],
                    })
        if acceptance_count:
            for match in ACCEPT_RANGE_RE.finditer(line):
                if int(match.group(1)) != acceptance_count:
                    stale.append({
                        "file": rel,
                        "line": index,
                        "pattern": "过期 A 计数 %s（当前 A1–A%d）" % (match.group(0), acceptance_count),
                        "text": line.strip()[:160],
                    })

        # 3) 旧 stage 列表
        if OLD_SPEC_STAGE_RE.search(line):
            stale.append({
                "file": rel,
                "line": index,
                "pattern": "旧 check_spec 两阶段 --stage spec|verify（缺 draft）",
                "text": line.strip()[:160],
            })
        if OLD_ROLES_STAGE_RE.search(line):
            stale.append({
                "file": rel,
                "line": index,
                "pattern": "旧 check_roles 三阶段 --stage sign|verify|accept（缺 start/pause）",
                "text": line.strip()[:160],
            })
        for match in STAGE_LIST_RE.finditer(line):
            if "四阶段" in line:
                break
            tokens = set(STAGE_TOKEN_RE.findall(match.group(1)))
            if len(tokens) < 2:
                continue
            script = detect_script(line, match.start(), match.end())
            if script == "check_spec":
                missing = sorted({"draft", "spec", "verify", "accept"} - tokens)
                if missing:
                    stale.append({
                        "file": rel,
                        "line": index,
                        "pattern": "check_spec 阶段列表缺 " + "/".join(missing),
                        "text": line.strip()[:160],
                    })
            elif script == "check_roles":
                missing = sorted({"start", "pause"} - tokens)
                if missing:
                    stale.append({
                        "file": rel,
                        "line": index,
                        "pattern": "check_roles 阶段列表缺 " + "/".join(missing),
                        "text": line.strip()[:160],
                    })

        # 4) 9 步编号
        for match in STEP_RE.finditer(line):
            if int(match.group(1)) != EXPECTED_STEPS:
                contradictions.append({
                    "concept": "steps",
                    "values": {rel: match.group(0)},
                    "message": "%s:%d 出现 %r；流程必须为 %d 步（C12）" % (rel, index, match.group(0), EXPECTED_STEPS),
                })

        # 5) 长行
        length = len(line.rstrip())
        if length > max_line:
            long_items.append({
                "kind": "line",
                "file": rel,
                "line": index,
                "length": length,
                "limit": max_line,
            })

        # 6) 同文件相反口径（主脑自做 / 主脑内联 / 失败重试 / 开工时序 / 首次-最新）
        if "主脑自做" in line:
            if is_negated(line, line.find("主脑自做")) or has_violation_context(line):
                policy["self_do_neg"] = True
            else:
                policy["self_do_pos"] = True
        if "主脑内联" in line:
            if is_negated(line, line.find("主脑内联")) or has_violation_context(line):
                policy["inline_neg"] = True
            else:
                policy["inline_pos"] = True
        if "同类失败一次" in line and not has_violation_context(line):
            policy["once_rule"] = True
        if re.search(r"3\s*次(?:尝试|后换新)|三次尝试", line):
            policy["three_rule"] = True
        early_match = EARLY_RE.search(line)
        if early_match and not has_violation_context(line):
            policy["early"].add(early_match.group(1))
        late_match = LATE_RE.search(line)
        if late_match and not has_violation_context(line):
            policy["late"].add(late_match.group(1))
        if not has_violation_context(line):
            for subject, key in (("首次提交", "first"), ("最新提交", "latest")):
                if subject not in line:
                    continue
                if re.search(r"draft|草稿", line):
                    policy[key + "_draft"] = True
                elif re.search(r"signed|已签约", line):
                    policy[key + "_signed"] = True

    # 同文件口径冲突
    for subject, key in (("首次提交", "first"), ("最新提交", "latest")):
        if policy[key + "_draft"] and policy[key + "_signed"]:
            contradictions.append({
                "concept": "first-latest",
                "values": {rel: subject + " draft vs signed"},
                "message": "%s 对“%s”同时要求 draft 与 signed 两种互斥状态" % (rel, subject),
            })
    if policy["self_do_pos"] and policy["self_do_neg"]:
        contradictions.append({
            "concept": "self-do",
            "values": {rel: "主脑自做 vs 不得主脑自做"},
            "message": "%s 同时出现“主脑自做”与“不得主脑自做”两种口径" % rel,
        })
    if policy["inline_pos"] and policy["inline_neg"]:
        contradictions.append({
            "concept": "inline",
            "values": {rel: "主脑内联 vs 不得内联"},
            "message": "%s 同时出现“主脑内联”与“不得内联”两种口径" % rel,
        })
    if policy["once_rule"] and policy["three_rule"]:
        contradictions.append({
            "concept": "retry",
            "values": {rel: "同类失败一次 vs 3 次尝试"},
            "message": "%s 同时出现“同类失败一次”与“3 次尝试”两种口径" % rel,
        })
    shared_timing = policy["early"] & policy["late"]
    if shared_timing:
        contradictions.append({
            "concept": "start-timing",
            "values": {rel: "、".join(sorted(shared_timing))},
            "message": "%s 同一对象（%s）同时出现“早于”与“晚于”两种口径" % (
                rel, "、".join(sorted(shared_timing))),
        })

    # README 重复 URL
    if rel == "README.md":
        counts = {}
        for index, line in enumerate(lines, start=1):
            for match in URL_RE.finditer(line):
                url = match.group(0).rstrip("。，；、.,;")
                counts.setdefault(url, []).append(index)
        for url, locations in sorted(counts.items()):
            if len(locations) >= 2:
                contradictions.append({
                    "concept": "readme-url",
                    "values": {rel: url},
                    "message": "README 重复 URL（%d 次）：%s（行 %s）" % (
                        len(locations), url, ",".join(str(item) for item in locations[:8])),
                })

    # spec-template §2 / §9
    if rel == "ship-it/references/spec-template.md":
        section2 = []
        section9 = []
        inside2 = False
        inside9 = False
        for index, line in enumerate(lines, start=1):
            if re.match(r"^##\s*2[.\s、]", line):
                inside2, inside9 = True, False
                continue
            if re.match(r"^##\s*9[.\s、]", line):
                inside9, inside2 = True, False
                continue
            if re.match(r"^##\s*\d", line):
                inside2, inside9 = False, False
            if inside2:
                section2.append((index, line))
            if inside9:
                section9.append((index, line))
        for index, line in section2:
            if re.match(r"^\s*[-*]\s+\*\*C\d+", line):
                contradictions.append({
                    "concept": "template-section2-c-tag",
                    "values": {rel: line.strip()[:120]},
                    "message": "%s:%d 模板 §2 仍用 C 编号流程规则（必须 P1..Pn）" % (rel, index),
                })
        if section2 and not any("P1" in line for _index, line in section2):
            contradictions.append({
                "concept": "template-section2-p-rules",
                "values": {rel: "P1"},
                "message": "%s §2 未使用 P1..Pn 流程规则编号" % rel,
            })
        header = None
        for _index, line in section9:
            stripped = line.strip()
            if stripped.startswith("|") and not TABLE_SEP_RE.match(stripped):
                header = stripped
                break
        if header:
            columns = [cell.strip() for cell in header.strip("|").split("|")]
            required = ["条款", "用例名", "用例文件", "结果", "路径真实性"]
            if columns != required:
                contradictions.append({
                    "concept": "template-section9-columns",
                    "values": {rel: "|".join(columns)},
                    "message": "%s §9 核销表必须 5 列（条款/用例名/用例文件/结果/路径真实性），实际：%s" % (
                        rel, "/".join(columns)),
                })


# ---------------------------------------------------------------------------
# 重复 / 版本 / CHANGELOG 长度
# ---------------------------------------------------------------------------

def normalize_text(line):
    value = line.strip()
    value = re.sub(r"^[\s>*+\-]+", "", value)
    value = re.sub(r"^\d+[.)、]\s*", "", value)
    value = value.replace("`", "").replace("*", "").replace("_", " ")
    value = value.strip("|").strip()
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value


def is_command_like(text):
    lowered = text.strip().lower()
    prefixes = ("python ", "python3 ", "py ", "git ", "pwsh", "powershell", "$ ", ".\\", "cd ", "pip ", "npm ", "pnpm ")
    return lowered.startswith(prefixes)


def is_url_only(line):
    stripped = line.strip()
    return bool(re.fullmatch(r"(?:https?://\S+|<https?://\S+>|\[[^\]]*\]\([^)]+\))", stripped))


def collect_duplicates(documents, spec_rel=None):
    TEMPLATE_REL = "ship-it/references/spec-template.md"
    seen = {}
    for doc in documents:
        rel = doc["rel"]
        lines = doc["lines"]
        regions = doc["regions"]
        in_fence = False
        for index, line in enumerate(lines, start=1):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if line_allowed(index, regions):
                continue
            if CANONICAL_MARKER in line:
                continue
            if CLONE_URL_RE.search(line):
                continue
            if heading_level(line):
                continue
            if is_url_only(line):
                continue
            stripped = line.strip()
            if TABLE_SEP_RE.match(stripped):
                continue
            normalized = normalize_text(line)
            if len(normalized) < DUPLICATE_MIN_CHARS:
                continue
            if not re.search(r"[\w\u4e00-\u9fff]", normalized):
                continue
            if is_command_like(normalized):
                continue
            seen.setdefault(normalized, []).append((rel, index))

    duplicates = []
    for normalized, occurrences in seen.items():
        if len(occurrences) < 2:
            continue
        # 跳过只发生在 spec 与 spec-template 之间的重复（spec 基于模板，固有重复）
        locs = set(item[0] for item in occurrences)
        if spec_rel and locs <= {spec_rel, TEMPLATE_REL} and len(locs) == 2:
            continue
        locations = sorted(set(item[0] for item in occurrences))
        duplicates.append({
            "normalized": normalized[:160],
            "files": locations,
            "lines": [{"file": rel, "line": line} for rel, line in occurrences[:12]],
            "message": "重复（规范化后 >=%d 字符，出现 %d 次）：%s；位置 %s" % (
                DUPLICATE_MIN_CHARS,
                len(occurrences),
                normalized[:80],
                "、".join("%s:%d" % (rel, line) for rel, line in occurrences[:6]),
            ),
        })
    return duplicates


def extract_version(rel, lines):
    if rel == "ship-it/SKILL.md":
        for line in lines[:20]:
            match = SKILL_VERSION_RE.match(line.strip())
            if match:
                return match.group(1)
    elif rel == "ship-it/CHANGELOG.md":
        for line in lines:
            match = SECTION_VERSION_RE.match(line)
            if match:
                return match.group(1)
    elif rel == "CHANGELOG.md":
        for line in lines:
            match = ROW_VERSION_RE.match(line)
            if match:
                return match.group(1)
        for line in lines:
            match = SECTION_VERSION_RE.match(line)
            if match:
                return match.group(1)
    return None


def check_versions(documents, contradictions, warnings):
    versions = {}
    for doc in documents:
        value = extract_version(doc["rel"], doc["lines"])
        if value:
            versions[doc["rel"]] = value
    if len(versions) >= 2:
        if len(set(versions.values())) > 1:
            contradictions.append({
                "concept": "version",
                "values": versions,
                "message": "版本三处不一致：%s" % "、".join("%s=%s" % (rel, value) for rel, value in sorted(versions.items())),
            })
        elif any(value != EXPECTED_VERSION for value in versions.values()):
            contradictions.append({
                "concept": "version",
                "values": versions,
                "message": "版本三处必须均为 v%s（C12），实际：%s" % (
                    EXPECTED_VERSION, "、".join(sorted(set(versions.values())))),
            })
    elif len(versions) == 1:
        warnings.append("版本三处未找齐（仅 %s），跳过版本一致性检查" % list(versions)[0])
    else:
        warnings.append("版本三处未找齐（SKILL/ship-it CHANGELOG/根 CHANGELOG 均缺失），跳过版本一致性检查")


def changelog_47_block(rel, lines):
    start = None
    if rel == "CHANGELOG.md":
        for line in lines:
            match = ROW_VERSION_RE.match(line)
            if match and match.group(1) == EXPECTED_VERSION:
                return [line]
    for index, line in enumerate(lines):
        match = SECTION_VERSION_RE.match(line)
        if match and match.group(1) == EXPECTED_VERSION:
            start = index
            break
    if start is None:
        return None
    end = section_end(lines, start, 2)
    return lines[start + 1:end]


def check_changelog_length(documents, long_items, warnings):
    # major 版本（主版本号变更）变更条目多，放宽字符上限；patch/minor 维持 300。
    current = version_tuple(EXPECTED_VERSION)
    limit = CHANGELOG_MAJOR_LIMIT if (current and current[0] >= 5) else CHANGELOG_47_LIMIT
    for doc in documents:
        rel = doc["rel"]
        if rel not in CHANGELOG_FILES:
            continue
        block = changelog_47_block(rel, doc["lines"])
        if block is None:
            warnings.append("%s 未找到 %s 版本区块（4.7.0 <=300 字符检查跳过）" % (rel, EXPECTED_VERSION))
            continue
        compact = re.sub(r"\s+", "", "".join(block))
        if len(compact) > limit:
            long_items.append({
                "kind": "changelog",
                "file": rel,
                "length": len(compact),
                "limit": limit,
            })


# ---------------------------------------------------------------------------
# 根路径
# ---------------------------------------------------------------------------

def find_repo_root(start):
    current = Path(os.path.realpath(str(start)))
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def resolve_root(raw, cwd):
    path = Path(str(raw))
    if not path.is_absolute():
        path = cwd / path
    real = Path(os.path.realpath(str(path)))
    repo = find_repo_root(cwd)
    if repo is not None:
        if not is_inside(real, repo):
            return None, "--root 越出仓库根（C13）：%s 解析为 %s，仓库根 %s" % (raw, real, repo)
    else:
        cwd_real = Path(os.path.realpath(str(cwd)))
        if not is_inside(real, cwd_real):
            return None, "--root 越出当前目录（C13）：%s 解析为 %s" % (raw, real)
    if not real.is_dir():
        return None, "--root 不是目录：%s（解析为 %s）" % (raw, real)
    return real, None


# ---------------------------------------------------------------------------
# C23：跨文件角色硬属性一致性（角色卡 / 能力表 / 矩阵 / 失败处理表 4 处）
# ---------------------------------------------------------------------------

# 8 个权威角色名（与 references/role-glossary.md 对齐）。
ROLE_HARD_NAMES = [
    "主脑",
    "需求分析师",
    "后端开发",
    "前端开发",
    "代码安全员",
    "监察员",
    "测试员",
    "裁判员",
]

# 形态硬属性归一化：把一段形态描述压成单一硬属性 token。
#   session   = 会话本身（主脑专属）
#   teammate  = 持久 teammate（含"持久 teammate"/"teammate 常驻"/"teammate 创建"等正向表述）
#   subagent  = 一次性 subagent
#   None      = 该处未表达该角色的形态硬属性（不参与一致性比较，避免误报）
FORM_SESSION = "session"
FORM_TEAMMATE = "teammate"
FORM_SUBAGENT = "subagent"


def _normalize_form_token(cell):
    """把形态单元格/字段压成硬属性 token；无法判定返回 None。"""
    if not cell:
        return None
    text = cell.strip()
    if not text:
        return None
    if "会话本身" in text:
        return FORM_SESSION
    if "持久 teammate" in text or "持久teammate" in text:
        return FORM_TEAMMATE
    if "teammate" in text:
        return FORM_TEAMMATE
    if "subagent" in text:
        return FORM_SUBAGENT
    return None


def _extract_capability_forms(team_mode_text):
    """位置 1：能力要求表（## 角色能力要求表）的 形态 列。返回 {角色: token}。"""
    lines = team_mode_text.split("\n")
    forms = {}
    in_table = False
    header_seen = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and "角色能力要求表" in stripped:
            in_table = True
            continue
        if in_table and stripped.startswith("## "):
            break
        if not in_table:
            continue
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not header_seen:
            if cells and cells[0] == "角色" and "形态" in cells:
                header_seen = True
            continue
        if all(set(c) <= set("-:") for c in cells if c):
            continue
        if len(cells) >= 3:
            role = cells[0].split("（")[0].strip()
            form = _normalize_form_token(cells[2])
            if role in ROLE_HARD_NAMES and form is not None:
                forms[role] = form
    return forms


def _extract_card_forms(team_mode_text):
    """位置 2：角色卡的 - **形态**： 字段。返回 {角色: token}。"""
    lines = team_mode_text.split("\n")
    forms = {}
    current_role = None
    for line in lines:
        heading = re.match(r"^###\s+(.+?)(?:（|$)", line)
        if heading:
            current_role = heading.group(1).strip()
            continue
        match = re.match(r"^\s*-\s*\*\*形态\*\*[：:]\s*(.+)$", line)
        if match and current_role in ROLE_HARD_NAMES:
            form = _normalize_form_token(match.group(1))
            if form is not None:
                forms[current_role] = form
    return forms


def _extract_matrix_forms(team_mode_text):
    """位置 3：角色按需启用矩阵。

    矩阵的"形态"列描述改动规模（0/1/2/3），不承载每个角色的形态硬属性；
    故此处对所有角色返回 {}（不参与一致性比较），避免把"规模形态"误判为
    "角色形态"而制造假阳性。
    """
    return {}


_FAILURE_FORM_RE = re.compile(
    r"(主脑|需求分析师|后端开发|前端开发|代码安全员|监察员|测试员|裁判员)"
    r"\s+(subagent|teammate)"
)


def _extract_failure_forms(team_mode_text):
    """位置 4：失败处理与降级表。仅当某行把某角色与 subagent/teammate 直接关联时采信。"""
    lines = team_mode_text.split("\n")
    forms = {}
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and "失败处理" in stripped:
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if not in_section:
            continue
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        for match in _FAILURE_FORM_RE.finditer(stripped):
            role = match.group(1)
            kind = match.group(2)
            if role in ROLE_HARD_NAMES:
                forms[role] = FORM_TEAMMATE if kind == "teammate" else FORM_SUBAGENT
    return forms


def check_role_hard_attributes(documents, errors, warnings):
    """C23：对每个角色抽取 4 处形态硬属性做相等判断；不一致即 FAIL。

    4 处 = 角色卡 / 能力表 / 矩阵 / 失败处理表。某处未表达该角色形态时记 None，
    不参与比较（防止"未提"被误判为"矛盾"）；仅当 ≥2 处给出不同具体 token 才判矛盾。
    职责边界红线（只读/可写、不审代码/不测试）同理：仅检测同角色同红线的相反口径。
    """
    team_doc = None
    for doc in documents:
        if doc["rel"] == "ship-it/references/team-mode.md":
            team_doc = doc
            break
    if team_doc is None:
        warnings.append("C23：未找到 ship-it/references/team-mode.md，跳过角色硬属性一致性检测")
        return
    text = "\n".join(team_doc["lines"])

    sources = {
        "能力表": _extract_capability_forms(text),
        "角色卡": _extract_card_forms(text),
        "矩阵": _extract_matrix_forms(text),
        "失败处理表": _extract_failure_forms(text),
    }

    for role in ROLE_HARD_NAMES:
        tokens = {}
        for src_name, mapping in sources.items():
            token = mapping.get(role)
            if token is not None:
                tokens[src_name] = token
        distinct = set(tokens.values())
        if len(distinct) > 1:
            detail = "、".join(
                "%s=%s" % (src, tok) for src, tok in sorted(tokens.items())
            )
            errors.append(
                "C23 角色硬属性不一致：%s 的形态在多处口径冲突（%s）——形态硬属性（持久 teammate vs 一次性 subagent vs 会话本身）必须一致"
                % (role, detail)
            )

# ---------------------------------------------------------------------------
# C17 需求分析师 grill-me 四机制校验（扫描 team-mode.md 需求分析师卡）
# ---------------------------------------------------------------------------

# C17 四机制关键词：决策树 + 分轮追问 + 推荐答案 + 事实/决策分离 + 澄清完成判据。
# 缺任一即 FAIL（C17 失败行为：check_docs.py FAIL）。
C17_MECHANISM_KEYWORDS = (
    "决策树",
    "分轮追问",
    "推荐答案",
    "事实",
    "澄清完成",
)


def check_analyst_grill_mechanisms(documents, errors, warnings):
    """C17：扫描 team-mode.md 需求分析师卡是否含 grill-me 四机制关键词。

    四机制=决策树标依赖+分轮追问+每问附推荐答案+事实/决策分离；外加澄清完成判据。
    缺任一即 FAIL。仅扫需求分析师角色卡（### 需求分析师 到下一个 ### 之间）。
    """
    team_doc = None
    for doc in documents:
        if doc["rel"] == "ship-it/references/team-mode.md":
            team_doc = doc
            break
    if team_doc is None:
        return  # check_role_hard_attributes 已 WARN 缺 team-mode.md
    lines = team_doc["lines"]
    # 定位需求分析师角色卡正文（### 需求分析师 到下一个同级或更高级标题前）。
    start = None
    for index, line in enumerate(lines):
        if re.match(r"^###\s+需求分析师\s*$", line):
            start = index + 1
            break
    if start is None:
        errors.append("C17：team-mode.md 缺少「### 需求分析师」角色卡（无法校验 grill-me 四机制）")
        return
    end = len(lines)
    for index in range(start, len(lines)):
        if re.match(r"^#{1,3}\s+", lines[index]):
            end = index
            break
    card_body = "\n".join(lines[start:end])
    missing = [kw for kw in C17_MECHANISM_KEYWORDS if kw not in card_body]
    if missing:
        errors.append(
            "C17 需求分析师卡缺 grill-me 四机制关键词：%s（需含 决策树/分轮追问/推荐答案/事实/澄清完成）"
            % "、".join(missing)
        )


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(description="全文一致性与去废话闸门（v4.7.2 / C18）")
    parser.add_argument("--root", default=".", help="仓库根（默认当前目录）")
    parser.add_argument("--spec", help="当前 spec 路径（默认 docs/specs 下日期最大的 spec）")
    parser.add_argument("--max-line", type=int, default=DEFAULT_MAX_LINE, help="长行阈值（docs 默认 500 字符；spec 用 800，C11 条款上限）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser


def emit(result, args):
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("root   : %s" % result["root"])
        print("spec   : %s" % (result["spec"] or "（无）"))
        print("文件   : %s" % ("、".join(result["files"]) or "（无）"))
        stats = result["stats"]
        print("统计   : %d 文件 / %d 行 / C1–C%d / A1–A%d" % (
            stats["files"], stats["lines"], stats["clause_count"], stats["acceptance_count"]))
        for item in result["stale"]:
            print("STALE  : %s:%d [%s] %s" % (item["file"], item["line"], item["pattern"], item["text"]))
        for item in result["contradictions"]:
            print("CONTRA : %s" % item["message"])
        for item in result["duplicates"]:
            print("DUP    : %s" % item["message"])
        for item in result["long"]:
            if item["kind"] == "line":
                print("LONG   : %s:%d 长度 %d > %d" % (item["file"], item["line"], item["length"], item["limit"]))
            else:
                print("LONG   : %s %s 区块 %d 字符 > %d" % (item["file"], EXPECTED_VERSION, item["length"], item["limit"]))
        for item in result["allowlist"]:
            if item["kind"] == "region":
                print("ALLOW  : %s:%s-%s %s" % (item["file"], item["start"], item["end"], item["reason"]))
            else:
                print("ALLOW  : %s:%s %s" % (item["file"], item["line"], item["reason"]))
        for warning in result["warnings"]:
            print("WARN   : %s" % warning)
        for error in result["errors"]:
            print("ERROR  : %s" % error)
        print("结果   : %s（%d 错误 / %d 警告）" % (
            "PASS" if result["ok"] else "FAIL", len(result["errors"]), len(result["warnings"])))
    return 0 if result["ok"] else 1


def main(argv=None):
    args = build_parser().parse_args(argv)
    errors = []
    warnings = []
    stale = []
    duplicates = []
    long_items = []
    contradictions = []
    allowlist = []

    result = {
        "ok": False,
        "root": "",
        "spec": "",
        "files": [],
        "stale": stale,
        "duplicates": duplicates,
        "duplicate": duplicates,
        "long": long_items,
        "contradictions": contradictions,
        "contradiction": contradictions,
        "allowlist": allowlist,
        "stats": {},
        "errors": errors,
        "warnings": warnings,
    }

    cwd = Path(os.getcwd())
    root, root_error = resolve_root(args.root, cwd)
    if root_error:
        errors.append(root_error)
        result["stats"] = {
            "files": 0, "lines": 0, "stale": 0, "duplicates": 0, "duplicate": 0,
            "long": 0, "contradictions": 0, "contradiction": 0,
            "clause_count": 0, "acceptance_count": 0, "allowlist": 0,
        }
        return emit(result, args)
    result["root"] = str(root)

    spec_rel = resolve_spec(root, args.spec, errors, warnings)
    result["spec"] = spec_rel or ""
    documents = load_documents(root, spec_rel, errors, warnings, allowlist)
    result["files"] = [doc["rel"] for doc in documents]

    clause_count = 0
    acceptance_count = 0
    for doc in documents:
        if doc["rel"] == spec_rel:
            clause_count, acceptance_count = spec_counts(doc["lines"])

    for doc in documents:
        limit = max(args.max_line, SPEC_MAX_LINE) if doc["rel"] == spec_rel else args.max_line
        scan_document(doc, clause_count, acceptance_count, limit, stale, long_items, contradictions)

    duplicates.extend(collect_duplicates(documents, spec_rel))
    check_versions(documents, contradictions, warnings)
    check_changelog_length(documents, long_items, warnings)
    check_role_hard_attributes(documents, errors, warnings)
    check_analyst_grill_mechanisms(documents, errors, warnings)

    stale.sort(key=lambda item: (item["file"], item["line"], item["pattern"]))
    duplicates.sort(key=lambda item: item["message"])
    long_items.sort(key=lambda item: (item["file"], item.get("line", 0), item["kind"]))
    contradictions.sort(key=lambda item: item["message"])
    allowlist.sort(key=lambda item: (item["file"], item.get("start", item.get("line", 0)), item["kind"]))

    for item in stale:
        errors.append("旧口径/过期计数：%s:%d [%s] %s" % (
            item["file"], item["line"], item["pattern"], item["text"]))
    for item in contradictions:
        errors.append("矛盾：%s" % item["message"])
    for item in duplicates:
        errors.append("重复：%s" % item["message"])
    for item in long_items:
        if item["kind"] == "line":
            errors.append("超长行：%s:%d 长度 %d > %d" % (
                item["file"], item["line"], item["length"], item["limit"]))
        else:
            errors.append("超长：%s 的 %s 区块 %d 字符 > %d" % (
                item["file"], EXPECTED_VERSION, item["length"], item["limit"]))

    result["stats"] = {
        "files": len(documents),
        "lines": sum(len(doc["lines"]) for doc in documents),
        "stale": len(stale),
        "duplicates": len(duplicates),
        "duplicate": len(duplicates),
        "long": len(long_items),
        "contradictions": len(contradictions),
        "contradiction": len(contradictions),
        "clause_count": clause_count,
        "acceptance_count": acceptance_count,
        "allowlist": len(allowlist),
    }
    result["ok"] = not errors
    return emit(result, args)


if __name__ == "__main__":
    sys.exit(main())
