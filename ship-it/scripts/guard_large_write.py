#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guard_large_write.py — 大文件写保护（v4.7.0）：写前备份、写后按基线校验、失败立即恢复。

用法：
    python guard_large_write.py prepare <file> [--backup <path>] [--manifest <path>]
    python guard_large_write.py check   <file> [--allow-shrink N] [--tail-marker <text>]
    python guard_large_write.py restore <file> [--manifest <path>]
    python guard_large_write.py check <file> --json

规则：
    prepare  记录基线 path/sha256/bytes/lines/tail，并复制备份；manifest 与备份必须在仓库根内
    check    校验 UTF-8、无 U+FFFD、行数 >= 基线 - allow-shrink（默认 0）、尾部标记在最后 20 行、非空；
             删除 >100 行必须显式 --allow-shrink N
    restore  只从 prepare 生成的 --manifest 恢复；备份 sha256 必须等于基线
退出码：0 = 通过；1 = 有错误。失败时打印可直接执行的 restore 命令。
"""

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TOOL_NAME = "guard_large_write"
TOOL_VERSION = 1
TAIL_LINES = 5
TAIL_WINDOW = 20
LARGE_SHRINK = 100


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


def resolve_in_root(raw, root, label, errors, must_exist=False, want_dir=False):
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


def rel_posix(path, root):
    return os.path.relpath(str(path), str(root)).replace("\\", "/")


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def decode_utf8(raw):
    try:
        return raw.decode("utf-8"), None
    except UnicodeDecodeError as exc:
        return None, "不是合法 UTF-8：%s" % exc


def count_lines(text):
    return len(text.splitlines())


def tail_lines(text):
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    tail = [line[:200] for line in lines[-TAIL_LINES:]]
    return tail


def load_manifest(path, errors):
    try:
        with io.open(str(path), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        errors.append("manifest 读取失败：%s（%s）" % (path, exc))
        return None
    if not isinstance(data, dict) or data.get("tool") != TOOL_NAME:
        errors.append("manifest 不是 prepare 生成的格式：%s" % path)
        return None
    if data.get("version") != TOOL_VERSION:
        errors.append("manifest 版本不支持：%r" % data.get("version"))
        return None
    for key in ("path", "sha256", "bytes", "lines", "backup"):
        if key not in data:
            errors.append("manifest 缺字段：%s" % key)
            return None
    for key in ("bytes", "lines"):
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors.append("manifest 字段 %s 必须是非负整数：%r（manifest 可能被篡改）" % (key, value))
            return None
    if not isinstance(data.get("path"), str) or not isinstance(data.get("backup"), str):
        errors.append("manifest 字段 path/backup 必须是字符串")
        return None
    if not isinstance(data.get("sha256"), str) or not re.fullmatch(r"[0-9a-fA-F]{64}", data.get("sha256", "")):
        errors.append("manifest 字段 sha256 不是 64 位十六进制：%r" % data.get("sha256"))
        return None
    return data


def restore_command(root, target, manifest):
    script = Path(os.path.realpath(str(Path(__file__))))
    if is_inside(script, root):
        script_text = rel_posix(script, root)
    else:
        script_text = str(script)
    return 'python "%s" restore "%s" --manifest "%s"' % (
        script_text,
        rel_posix(target, root),
        rel_posix(manifest, root),
    )


def write_json(path, data):
    with io.open(str(path), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=2))
        handle.write("\n")


def emit(result, as_json, errors, warnings, target=None, manifest=None, root=None):
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("action : %s" % result.get("action"))
        print("file   : %s" % result.get("file"))
        print("manifest: %s" % result.get("manifest"))
        print("backup : %s" % result.get("backup"))
        baseline = result.get("baseline") or {}
        current = result.get("current") or {}
        if baseline:
            print("baseline: %s 行 / %s 字节 / sha256 %s" % (baseline.get("lines"), baseline.get("bytes"), baseline.get("sha256")))
        if current:
            print("current : %s 行 / %s 字节 / sha256 %s" % (current.get("lines"), current.get("bytes"), current.get("sha256")))
        for warning in warnings:
            print("WARN   : %s" % warning)
        for error in errors:
            print("ERROR  : %s" % error)
        if errors and target is not None and manifest is not None and root is not None:
            print("恢复命令: %s" % restore_command(root, target, manifest))
        print("结果   : %s（%d 错误 / %d 警告）" % ("PASS" if result["ok"] else "FAIL", len(errors), len(warnings)))
    return 0 if result["ok"] else 1


def action_prepare(args, root, errors, warnings, result):
    target = resolve_in_root(args.file, root, "目标文件", errors, must_exist=True)
    if target is None:
        return 1
    manifest_raw = args.manifest if args.manifest else str(target) + ".guard.json"
    backup_raw = args.backup if args.backup else str(target) + ".bak"
    manifest = resolve_in_root(manifest_raw, root, "manifest", errors)
    backup = resolve_in_root(backup_raw, root, "备份文件", errors)
    if manifest is None or backup is None:
        return 1
    result["file"] = str(target)
    result["manifest"] = str(manifest)
    result["backup"] = str(backup)
    if manifest == target or backup == target:
        errors.append("manifest/备份路径不得与目标文件相同")
        return 1

    try:
        raw = target.read_bytes()
    except OSError as exc:
        errors.append("读取目标文件失败：%s" % exc)
        return 1
    text, decode_error = decode_utf8(raw)
    if decode_error:
        errors.append("目标文件%s（prepare 只接受 UTF-8 文本）" % decode_error)
        return 1
    if "\ufffd" in text:
        errors.append("目标文件已含 U+FFFD 替换字符，先修复编码再 prepare")
        return 1
    lines = count_lines(text)
    if lines == 0:
        errors.append("目标文件为空，无法建立基线")
        return 1

    if manifest.exists():
        existing = load_manifest(manifest, [])
        if existing is None:
            errors.append("manifest 已存在且无法解析：%s；先 restore 或手动删除后再 prepare" % manifest)
            return 1
        if existing.get("sha256") != sha256_bytes(raw):
            errors.append("manifest 已存在且与当前文件不一致：%s；先 restore 或手动删除后再 prepare" % manifest)
            return 1
        warnings.append("manifest 已存在且基线一致，刷新备份与 manifest")

    tail = tail_lines(text)
    marker = (args.tail_marker or "").strip() or (tail[-1] if tail else "")
    manifest_data = {
        "tool": TOOL_NAME,
        "version": TOOL_VERSION,
        "path": rel_posix(target, root),
        "sha256": sha256_bytes(raw),
        "bytes": len(raw),
        "lines": lines,
        "tail": tail,
        "tail_marker": marker,
        "backup": rel_posix(backup, root),
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    try:
        backup.write_bytes(raw)
        write_json(manifest, manifest_data)
    except OSError as exc:
        errors.append("写入备份/manifest 失败：%s" % exc)
        return 1
    result["baseline"] = {
        "lines": lines,
        "bytes": len(raw),
        "sha256": manifest_data["sha256"],
        "tail_marker": marker,
    }
    return 0


def action_check(args, root, errors, warnings, result):
    target = resolve_in_root(args.file, root, "目标文件", errors, must_exist=True)
    if target is None:
        return 1
    manifest_raw = args.manifest if args.manifest else str(target) + ".guard.json"
    manifest = resolve_in_root(manifest_raw, root, "manifest", errors, must_exist=True)
    if manifest is None:
        return 1
    result["file"] = str(target)
    result["manifest"] = str(manifest)
    data = load_manifest(manifest, errors)
    if data is None:
        return 1
    backup = resolve_in_root(root / data["backup"], root, "备份文件", errors, must_exist=True)
    if backup is None:
        return 1
    result["backup"] = str(backup)

    manifest_target = Path(os.path.realpath(str(root / data["path"])))
    if manifest_target != target:
        errors.append("manifest 与目标文件不匹配：manifest=%s，目标=%s" % (manifest_target, target))
        return 1
    if sha256_bytes(backup.read_bytes()) != data["sha256"]:
        errors.append("备份文件与 manifest 的 sha256 不一致：%s" % backup)
        return 1

    try:
        raw = target.read_bytes()
    except OSError as exc:
        errors.append("读取目标文件失败：%s" % exc)
        return 1
    text, decode_error = decode_utf8(raw)
    if decode_error:
        errors.append("目标文件%s" % decode_error)
        return 1
    if "\ufffd" in text:
        errors.append("目标文件含 U+FFFD 替换字符（写入已破坏编码）")
    lines = count_lines(text)
    if lines == 0 or not text.strip():
        errors.append("目标文件为空（基线 %d 行）" % data["lines"])
    shrink = int(data["lines"]) - lines
    allow = int(args.allow_shrink or 0)
    if allow < 0:
        errors.append("--allow-shrink 不能为负数：%d" % allow)
        allow = 0
    if shrink > LARGE_SHRINK and allow <= 0:
        errors.append("删除 %d 行（> %d）必须显式 --allow-shrink N 并人工确认" % (shrink, LARGE_SHRINK))
    if lines < int(data["lines"]) - allow:
        errors.append("行数 %d < 基线 %d - 允许缩水 %d（删除了 %d 行）" % (lines, int(data["lines"]), allow, shrink))

    marker = (args.tail_marker or "").strip() or (data.get("tail_marker") or "")
    if not marker:
        tail = data.get("tail") or []
        marker = tail[-1] if tail else ""
    if not marker:
        errors.append("manifest 没有尾部标记，无法校验尾部完整性")
    else:
        window = text.split("\n")[-TAIL_WINDOW:]
        if not any(marker in line for line in window):
            errors.append("尾部标记在最后 %d 行中缺失：%s" % (TAIL_WINDOW, marker[:80]))

    result["baseline"] = {
        "lines": data["lines"],
        "bytes": data["bytes"],
        "sha256": data["sha256"],
        "tail_marker": data.get("tail_marker", ""),
    }
    result["current"] = {"lines": lines, "bytes": len(raw), "sha256": sha256_bytes(raw)}
    return 0


def action_restore(args, root, errors, warnings, result):
    target = resolve_in_root(args.file, root, "目标文件", errors)
    if target is None:
        return 1
    manifest_raw = args.manifest if args.manifest else str(target) + ".guard.json"
    manifest = resolve_in_root(manifest_raw, root, "manifest", errors, must_exist=True)
    if manifest is None:
        return 1
    result["file"] = str(target)
    result["manifest"] = str(manifest)
    data = load_manifest(manifest, errors)
    if data is None:
        return 1
    if Path(os.path.realpath(str(root / data["path"]))) != target:
        errors.append("manifest 与目标文件不匹配：manifest=%s，目标=%s" % (root / data["path"], target))
        return 1
    backup = resolve_in_root(root / data["backup"], root, "备份文件", errors, must_exist=True)
    if backup is None:
        return 1
    result["backup"] = str(backup)
    try:
        raw = backup.read_bytes()
    except OSError as exc:
        errors.append("读取备份失败：%s" % exc)
        return 1
    if sha256_bytes(raw) != data["sha256"]:
        errors.append("备份 sha256 与 manifest 不一致，拒绝恢复：%s" % backup)
        return 1
    try:
        target.write_bytes(raw)
    except OSError as exc:
        errors.append("恢复写入失败：%s" % exc)
        return 1
    if sha256_bytes(target.read_bytes()) != data["sha256"]:
        errors.append("恢复后 sha256 仍与基线不一致：%s" % target)
        return 1
    result["current"] = {"lines": int(data["lines"]), "bytes": int(data["bytes"]), "sha256": data["sha256"]}
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="大文件写保护：prepare / check / restore")
    parser.add_argument("action", choices=["prepare", "check", "restore"], help="动作")
    parser.add_argument("file", help="目标文件")
    parser.add_argument("--backup", help="备份路径（默认 <file>.bak）")
    parser.add_argument("--manifest", help="manifest 路径（默认 <file>.guard.json）")
    parser.add_argument("--allow-shrink", type=int, default=0, help="允许缩水的行数（默认 0）")
    parser.add_argument("--tail-marker", help="尾部标记文本（默认基线最后一个非空行）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    errors = []
    warnings = []
    root = detect_repo_root()
    result = {
        "action": args.action,
        "file": args.file,
        "manifest": "",
        "backup": "",
        "errors": errors,
        "warnings": warnings,
        "ok": False,
    }
    if args.action == "prepare":
        action_prepare(args, root, errors, warnings, result)
    elif args.action == "check":
        action_check(args, root, errors, warnings, result)
    else:
        action_restore(args, root, errors, warnings, result)
    result["ok"] = not errors
    manifest_path = Path(result["manifest"]) if result.get("manifest") else None
    target_path = Path(result["file"]) if result.get("file") else None
    return emit(result, args.json, errors, warnings, target_path, manifest_path, root)


if __name__ == "__main__":
    sys.exit(main())
