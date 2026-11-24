#!/usr/bin/env python3
# -*- coding: utf-8 *-
"""watchdog_daemon.py — C34 团队模式行为机器校验：独立常驻后台巡视程序。

不依赖 subagent 唤醒，Python3 标准库零依赖。每 N 秒机械巡视：
  1. 读 list_agents 状态（从最近 patrol 轮次的成员/状态记录解析；脚本无法直调 DSH 工具）
  2. 查产出文件是否落盘（docs/reviews/ 下预期报告）
  3. 查超时（角色 running 超阈值无产出更新）
  4. 追加 patrol log（## 第 N 轮 格式，不破坏现有 patrol 结构）
  5. 监察员 inactive 超阈值（默认 10 分钟）时报警（写 alarm 到 patrol log）

只做机械检查，不做分析判断（分析判断仍归监察员 subagent）。

用法：
    python ship-it/scripts/watchdog_daemon.py --date 2026-11-23 --interval 60   # 常驻
    python ship-it/scripts/watchdog_daemon.py --date 2026-11-23 --once          # 巡视一次后退出（自检）
    WATCHDOG_INTERVAL=30 python ship-it/scripts/watchdog_daemon.py --date 2026-11-23

退出码：0 = 正常巡视并落盘；1 = 参数错误/致命错误。Ctrl-C 优雅退出。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEFAULT_INTERVAL = 60
DEFAULT_AUDITOR_TIMEOUT = 600  # 监察员 inactive 超阈值报警（秒，默认 10 分钟）
DEFAULT_RUNNING_TIMEOUT = 1800  # 角色 running 无产出更新超阈值（秒，默认 30 分钟）

# patrol log 轮次标题正则（与 check_roles.py ROUND_RE 对齐）
ROUND_RE = re.compile(r"^##\s*第\s*(\d+)\s*轮\s*[\u2014\u2013\-:\uff1a]?\s*(.*)$")
# 顶层 last_active_at（JSON 数组或单值）
LAST_ACTIVE_TOP_RE = re.compile(r"(?m)^-\s*last_active_at[：:]\s*(.+)$")
# 轮次内 last_active_at
LAST_ACTIVE_ROUND_RE = re.compile(r"(?m)^-\s*last_active_at[：:]\s*(\S+)")
# 成员/状态行（patrol 轮次内）
MEMBER_STATUS_RE = re.compile(r"(?m)^-\s*成员[/／]?状态[^：:]*[：:]\s*(.+)$")


def local_now_iso() -> str:
    """当前本地时间 ISO8601 带时区。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_iso(value: str):
    """解析 ISO8601 时间为 aware datetime；失败返回 None。"""
    if not value:
        return None
    text = value.strip().strip("`*").strip()
    if not text:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?", text)
    if not match:
        return None
    raw = match.group(0).replace(" ", "T")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    raw = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", raw)
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt


def detect_repo_root(start: Path) -> Path:
    """向上找仓库根（含 ship-it/scripts 的目录）。"""
    cur = start.resolve()
    for _ in range(10):
        if (cur / "ship-it" / "scripts").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start.resolve()


def read_utf8(path: Path):
    try:
        with open(str(path), "r", encoding="utf-8-sig", newline="") as h:
            return h.read(), None
    except UnicodeDecodeError as e:
        return None, "不是合法 UTF-8：%s" % e
    except OSError as e:
        return None, "读取失败：%s" % e


def parse_last_round(patrol_text: str):
    """返回 (轮次号, 轮次正文) 或 (None, "")。"""
    lines = patrol_text.replace("\r\n", "\n").split("\n")
    rounds = []
    for i, line in enumerate(lines):
        m = ROUND_RE.match(line)
        if m:
            rounds.append((int(m.group(1)), i))
    if not rounds:
        return None, ""
    num, start = rounds[-1]
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^##\s", lines[i]):
            end = i
            break
    return num, "\n".join(lines[start:end])


def parse_top_last_active(patrol_text: str):
    """解析顶层 last_active_at（JSON 数组或单值），返回最大 aware datetime 或 None。"""
    m = LAST_ACTIVE_TOP_RE.search(patrol_text)
    if not m:
        return None
    raw = m.group(1).strip()
    stamps = []
    if raw.startswith("["):
        try:
            for item in json.loads(raw):
                dt = parse_iso(str(item))
                if dt:
                    stamps.append(dt)
        except ValueError:
            pass
    else:
        dt = parse_iso(raw)
        if dt:
            stamps.append(dt)
    return max(stamps) if stamps else None


def parse_member_status(round_body: str):
    """从轮次正文解析成员/状态行，返回原始字符串或 None。"""
    m = MEMBER_STATUS_RE.search(round_body)
    return m.group(1).strip() if m else None


def parse_round_last_active(round_body: str):
    """解析轮次内 last_active_at，返回 aware datetime 或 None。"""
    m = LAST_ACTIVE_ROUND_RE.search(round_body)
    return parse_iso(m.group(1)) if m else None


def list_review_files(root: Path, date: str):
    """列出 docs/reviews/ 下 <date>-*.md 文件，返回 {filename: mtime_datetime}。"""
    rev_dir = root / "docs" / "reviews"
    result = {}
    if not rev_dir.is_dir():
        return result
    for entry in rev_dir.iterdir():
        if entry.is_file() and entry.name.startswith(date + "-") and entry.name.endswith(".md"):
            try:
                mtime = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc).astimezone()
                result[entry.name] = mtime
            except OSError:
                pass
    return result


def classify_members(member_line: str):
    """从成员/状态行粗分 running / inactive 角色名列表（机械解析，不做判断）。"""
    running = []
    inactive = []
    if not member_line:
        return running, inactive
    # 常见格式："running = lead、judge、monitor；security/dev/tester 未派发" 或 "dev-script2 running；judge inactive"
    # 机械抓取 running/inactive 关键词附近的角色名（中英文字母数字-_.）
    for seg in re.split(r"[；;,，。\n]", member_line):
        seg_lower = seg.lower()
        names = re.findall(r"([A-Za-z][A-Za-z0-9_-]*|[\u4e00-\u9fff]+)", seg)
        names = [n for n in names if n not in ("running", "inactive", "未派发", "状态", "成员")]
        if "inactive" in seg_lower:
            inactive.extend(names)
        elif "running" in seg_lower:
            running.extend(names)
    return running, inactive


def patrol_round_count(patrol_text: str) -> int:
    """返回现有 patrol 最大轮次号（逐行匹配，与 check_roles 一致）。"""
    nums = []
    for line in patrol_text.replace("\r\n", "\n").split("\n"):
        m = ROUND_RE.match(line)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) if nums else 0


def append_patrol_round(patrol_path: Path, round_num: int, timestamp: str,
                        trigger: str, members: str, evidence: list,
                        anomalies: list, actions: list, alarm: str = "") -> None:
    """追加一轮到 patrol log（## 第 N 轮 格式），并在结论节前插入。"""
    text, err = read_utf8(patrol_path)
    if err:
        text = ""
    lines = []
    lines.append("")
    lines.append("## 第 %d 轮 — %s" % (round_num, timestamp))
    lines.append("- last_active_at：%s" % timestamp)
    lines.append("- trigger：%s" % trigger)
    lines.append("- 成员/状态：%s" % members)
    lines.append("- 证据：")
    for i, ev in enumerate(evidence, 1):
        lines.append("  %d. %s" % (i, ev))
    if alarm:
        lines.append("- ALARM：%s" % alarm)
    lines.append("- 异常：%s" % ("、".join(anomalies) if anomalies else "无"))
    lines.append("- 动作：%s" % ("、".join(actions) if actions else "继续巡视"))
    block = "\n".join(lines) + "\n"
    # 在结论节前插入；若无结论节则追加到末尾
    concl_match = re.search(r"(?m)^##\s*结论\b", text)
    if concl_match:
        new_text = text[:concl_match.start()] + block + text[concl_match.start():]
    else:
        new_text = text.rstrip() + "\n" + block
    with open(str(patrol_path), "w", encoding="utf-8", newline="\n") as h:
        h.write(new_text)


def update_top_last_active(patrol_path: Path, timestamp: str) -> None:
    """把顶层 last_active_at 的 JSON 数组追加一个时间戳（机械刷新）。"""
    text, err = read_utf8(patrol_path)
    if err:
        return
    m = LAST_ACTIVE_TOP_RE.search(text)
    if not m:
        return
    raw = m.group(1).strip()
    if raw.startswith("["):
        try:
            arr = json.loads(raw)
            if isinstance(arr, list) and timestamp not in arr:
                arr.append(timestamp)
                new_line = "- last_active_at：" + json.dumps(arr, ensure_ascii=False)
                text = text[:m.start()] + new_line + text[m.end():]
                with open(str(patrol_path), "w", encoding="utf-8", newline="\n") as h:
                    h.write(text)
        except ValueError:
            pass


def bump_top_round_count(patrol_path: Path) -> None:
    """把顶层 轮次：N 字段 +1（与实际轮次标题数保持一致，避免 check_roles 不一致报错）。"""
    text, err = read_utf8(patrol_path)
    if err:
        return
    m = re.search(r"(?m)^-\s*轮次[：:]\s*(\d+)\s*$", text)
    if not m:
        return
    new_count = int(m.group(1)) + 1
    new_line = "- 轮次：%d" % new_count
    text = text[:m.start()] + new_line + text[m.end():]
    with open(str(patrol_path), "w", encoding="utf-8", newline="\n") as h:
        h.write(text)


def run_once(root: Path, date: str, auditor_timeout: int, running_timeout: int) -> dict:
    """巡视一次，返回结果 dict（机械检查，不做分析判断）。"""
    patrol_path = root / "docs" / "reviews" / ("%s-auditor-patrol.md" % date)
    now = datetime.now().astimezone()
    now_iso = now.isoformat(timespec="seconds")
    result = {
        "timestamp": now_iso,
        "patrol_exists": patrol_path.is_file(),
        "members_running": [],
        "members_inactive": [],
        "member_line": "",
        "review_files": {},
        "auditor_inactive_seconds": None,
        "alarm": "",
        "anomalies": [],
        "evidence": [],
    }
    # 1. 读 list_agents 状态：从最近 patrol 轮次的成员/状态行解析（脚本无法直调 DSH 工具）
    if patrol_path.is_file():
        text, err = read_utf8(patrol_path)
        if err is None:
            num, body = parse_last_round(text)
            result["last_round"] = num
            member_line = parse_member_status(body) or "（最近轮次无成员/状态记录）"
            result["member_line"] = member_line
            running, inactive = classify_members(member_line)
            result["members_running"] = running
            result["members_inactive"] = inactive
            # 监察员（auditor/monitor）inactive 时长：取顶层 last_active_at 与当前差
            top_active = parse_top_last_active(text)
            if top_active is not None:
                delta = (now - top_active).total_seconds()
                result["auditor_inactive_seconds"] = int(delta)
                # 判断监察员是否在 inactive 列表或最近无活动
                auditor_idle = any(n.lower() in ("auditor", "monitor", "监察员") for n in inactive)
                if delta > auditor_timeout or auditor_idle:
                    result["alarm"] = ("监察员 inactive %d 秒 > %d 秒阈值（C34：团队模式期间监察员不得 inactive，提示主脑唤醒）"
                                        % (int(delta), auditor_timeout))
            else:
                result["anomalies"].append("patrol 顶层 last_active_at 缺失或无法解析")
        else:
            result["anomalies"].append("patrol 读取失败：%s" % err)
    else:
        result["anomalies"].append("patrol log 不存在：%s" % patrol_path.name)

    # 2. 查产出文件是否落盘
    review_files = list_review_files(root, date)
    result["review_files"] = {name: mt.isoformat(timespec="seconds") for name, mt in review_files.items()}
    result["evidence"].append("docs/reviews/ 下 %s-* 文件 %d 个：%s" % (
        date, len(review_files), "、".join(sorted(review_files)[:8])))

    # 3. 查超时：running 角色无产出更新（机械：检查最近报告文件 mtime 与当前差）
    newest_report = max(review_files.values()) if review_files else None
    if newest_report is not None:
        report_age = (now - newest_report).total_seconds()
        result["evidence"].append("最新报告 %s mtime 距今 %d 秒" % (
            max(review_files, key=review_files.get), int(report_age)))
        if result["members_running"] and report_age > running_timeout:
            result["anomalies"].append("running 角色无产出更新 %d 秒 > %d 秒" % (int(report_age), running_timeout))
    else:
        result["evidence"].append("无 %s-* 报告文件" % date)

    # 4. 追加 patrol log（由调用方执行，此处只返回数据）
    return result


def build_round_fields(result: dict, round_num: int) -> tuple:
    """把 run_once 结果组装成 (trigger, members, evidence, anomalies, actions, alarm)。"""
    trigger = "watchdog_daemon 机械巡视（C34；不依赖 subagent 唤醒）"
    members = result.get("member_line") or "（无最近轮次成员/状态记录）"
    evidence = result.get("evidence", [])
    if "last_round" in result:
        evidence.insert(0, "基于 patrol 第 %d 轮成员/状态解析（脚本无法直调 list_agents，从 patrol log 取最近记录）" % result["last_round"])
    anomalies = result.get("anomalies", [])
    actions = ["机械巡视结果已追加；分析判断归监察员 subagent"]
    if result.get("alarm"):
        actions.append("ALARM 已写入：提示主脑唤醒监察员恢复常驻")
    return trigger, members, evidence, anomalies, actions, result.get("alarm", "")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="C34 watchdog_daemon：团队模式行为机器校验常驻巡视")
    parser.add_argument("--date", required=True, help="审查日期 YYYY-MM-DD（patrol log 文件名前缀）")
    parser.add_argument("--interval", type=int, default=None, help="巡视间隔秒（默认 60，可被 WATCHDOG_INTERVAL 覆盖）")
    parser.add_argument("--once", action="store_true", help="巡视一次后退出（自检用）")
    parser.add_argument("--auditor-timeout", type=int, default=DEFAULT_AUDITOR_TIMEOUT, help="监察员 inactive 报警阈值秒（默认 600）")
    parser.add_argument("--running-timeout", type=int, default=DEFAULT_RUNNING_TIMEOUT, help="running 角色无产出超阈值秒（默认 1800）")
    parser.add_argument("--root", default=None, help="仓库根（默认自动探测）")
    args = parser.parse_args(argv)

    # 日期校验
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print("ERROR: --date 必须是 YYYY-MM-DD：%s" % args.date)
        return 1

    interval = args.interval if args.interval is not None else int(os.environ.get("WATCHDOG_INTERVAL", str(DEFAULT_INTERVAL)))
    if interval < 5:
        print("ERROR: --interval 不得小于 5 秒：%d" % interval)
        return 1

    root = Path(args.root) if args.root else detect_repo_root(Path(__file__))
    if not (root / "ship-it" / "scripts").is_dir():
        print("ERROR: 未找到仓库根（缺 ship-it/scripts）：%s" % root)
        return 1

    patrol_path = root / "docs" / "reviews" / ("%s-auditor-patrol.md" % args.date)
    if not patrol_path.is_file():
        print("ERROR: patrol log 不存在：%s（watchdog_daemon 需已有 patrol log 才能追加）" % patrol_path)
        return 1

    stopping = {"flag": False}
    def handle_sig(signum, frame):
        stopping["flag"] = True
    signal.signal(signal.SIGINT, handle_sig)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_sig)

    print("watchdog_daemon 启动：root=%s date=%s interval=%ds once=%s" % (
        root, args.date, interval, args.once))
    cycle = 0
    while not stopping["flag"]:
        cycle += 1
        result = run_once(root, args.date, args.auditor_timeout, args.running_timeout)
        round_num = patrol_round_count(read_utf8(patrol_path)[0] or "") + 1
        trigger, members, evidence, anomalies, actions, alarm = build_round_fields(result, round_num)
        append_patrol_round(patrol_path, round_num, result["timestamp"],
                            trigger, members, evidence, anomalies, actions, alarm)
        update_top_last_active(patrol_path, result["timestamp"])
        bump_top_round_count(patrol_path)
        print("[%s] 第 %d 轮巡视落盘：%s%s" % (
            result["timestamp"], round_num, patrol_path.name,
            " ALARM=%s" % alarm if alarm else ""))
        if args.once:
            break
        # 等待下一轮（可被信号打断）
        slept = 0
        while slept < interval and not stopping["flag"]:
            time.sleep(min(1, interval - slept))
            slept += 1
    print("watchdog_daemon 退出（cycle=%d）" % cycle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
