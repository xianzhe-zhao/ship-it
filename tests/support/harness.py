#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.7.1 测试支撑：进程内脚本调用、批量 git fixture、慢测试标记（C9）。

三条提速措施（均不改变被测脚本语义）：
1. 进程内调用：v4.7.0 逐用例 `python script.py`，Windows 单次启动约 1 秒，
   几百次调用把全量拖到 8 分钟以上。脚本 main(argv) 只依赖 cwd 与文件，
   同一进程内 chdir + 重定向 stdout/stderr 等价，退出码语义不变。
2. 固定仓库根：fixture 的 cwd 就是仓库根，脚本 detect_repo_root() 被固定为
   cwd，省掉每次调用一次 `git rev-parse`（Windows 单次 git 启动约 0.8 秒）。
   路径越界校验仍以 cwd 为根，`..` 用例语义不变。
3. 批量 git fixture：`git init` 用一次生成的骨架复制；多个提交用一次
   `git fast-import` 写入（含 `--export-marks` 取回 commit sha），避免逐提交
   `git add` + `git commit`。只读 git 结果按 (repo, args) 缓存，提交后失效。

@slow：只打标记，不改变 unittest 执行；`tests/run_suite.py --fast` 按标记过滤。
"""

from __future__ import annotations

import atexit
import datetime
import importlib.util
import inspect
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "ship-it" / "scripts"
FAST = os.environ.get("SHIP_IT_FAST") == "1"
GIT = shutil.which("git")

_MODULES = {}
_GIT_SKELETON = None
_GIT_CACHE = {}
_CACHE_ROOT = None
_CACHE = {}


# ---------------------------------------------------------------------------
# 进程内脚本调用
# ---------------------------------------------------------------------------

def load_script(script):
    """按路径加载脚本模块（缓存）；detect_repo_root 固定为 cwd（见模块注释）。"""
    path = Path(script).resolve()
    key = str(path)
    module = _MODULES.get(key)
    if module is None:
        if not path.is_file():
            raise FileNotFoundError("缺少脚本：" + key)
        name = "shipit_script_" + str(abs(hash(key)))
        spec = importlib.util.spec_from_file_location(name, key)
        if spec is None or spec.loader is None:
            raise ImportError("无法加载脚本：" + key)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, "detect_repo_root"):
            module.detect_repo_root = _cwd_root
        if hasattr(module, "run_git"):
            module.run_git = _cached_run_git(module.run_git)
        _MODULES[key] = module
    return module


def _cwd_root():
    return Path(os.getcwd()).resolve()


_NAME_MAPS = {}
_BLOB_MAPS = {}


def _spec_blob_map(root, head, spec_rel):
    """一次 git cat-file --batch 取所有改过 spec 的提交内容，替代逐提交 git show。"""
    key = (str(Path(root).resolve()), head, spec_rel)
    if key in _BLOB_MAPS:
        return _BLOB_MAPS[key]
    names = _name_only_map(root, head)
    commits = [commit for commit, files in names.items() if spec_rel in files]
    mapping = {}
    if commits:
        request = "".join("%s:%s\n" % (commit, spec_rel) for commit in commits).encode("utf-8")
        result = subprocess.run([GIT, "-C", str(root), "cat-file", "--batch"],
                                input=request, capture_output=True)
        data = result.stdout or b""
        index = 0
        for commit in commits:
            newline = data.find(b"\n", index)
            if newline < 0:
                break
            header = data[index:newline].decode("utf-8", "replace").split()
            index = newline + 1
            if len(header) < 3 or header[1] != "blob":
                continue
            size = int(header[2])
            mapping[commit] = data[index:index + size].decode("utf-8", "replace")
            index += size + 1
    _BLOB_MAPS[key] = mapping
    return mapping




def _name_only_map(root, head):
    """一次 git log 取 HEAD 可达每个提交的变更文件，替代逐提交 git show。"""
    key = (str(Path(root).resolve()), head)
    if key in _NAME_MAPS:
        return _NAME_MAPS[key]
    result = subprocess.run(
        [GIT, "-C", str(root), "log", "--format=@@%H", "--name-only", "--no-renames", "HEAD"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    mapping = {}
    current = None
    for line in (result.stdout or "").splitlines():
        if line.startswith("@@"):
            current = line[2:].strip()
            mapping.setdefault(current, [])
        elif line.strip() and current:
            mapping[current].append(line.strip().replace("\\", "/"))
    _NAME_MAPS[key] = mapping
    return mapping

def _cached_run_git(original):
    """只读 git 结果缓存：key=(仓库 HEAD, 命令)。

    脚本的 git 命令只读历史（show/rev-list/diff/cat-file/merge-base/log），
    结果只取决于 HEAD 与对象库；fixture 复制出的仓库 HEAD 相同，可跨路径复用。
    新提交改变 HEAD，天然换 key；clear_git_cache() 仍保留给显式失效。
    """
    cache = {}

    def wrapper(root, arguments, **kwargs):
        if kwargs.get("env") is not None:
            return original(root, arguments, **kwargs)
        head = _repo_head(root)
        if (len(arguments) == 5 and arguments[0] == "show"
                and arguments[1] == "--name-only"
                and arguments[2] == "--pretty=format:"
                and arguments[3] == "--no-renames"):
            mapping = _name_only_map(root, head)
            commit = str(arguments[4])
            if commit in mapping:
                return 0, "\n".join(mapping[commit]), ""
        if (len(arguments) == 2 and arguments[0] == "show"
                and ":" in str(arguments[1])):
            commit, path = str(arguments[1]).split(":", 1)
            if path.startswith("ship-it/docs/specs/"):
                blobs = _spec_blob_map(root, head, path)
                if commit in blobs:
                    return 0, blobs[commit], ""
        key = (head or str(Path(root).resolve()), tuple(str(item) for item in arguments))
        if key not in cache:
            cache[key] = original(root, arguments)
        return cache[key]

    wrapper.cache = cache
    return wrapper


def clear_git_cache():
    for module in _MODULES.values():
        runner = getattr(module, "run_git", None)
        cache = getattr(runner, "cache", None)
        if cache is not None:
            cache.clear()


def invoke_script(script, args, cwd):
    """进程内运行脚本，返回 CompletedProcess 兼容对象（returncode/stdout/stderr）。"""
    script = Path(script)
    module = load_script(script)
    argv = [str(item) for item in args]
    old_cwd = os.getcwd()
    old_stdout, old_stderr, old_argv = sys.stdout, sys.stderr, sys.argv
    out, err = io.StringIO(), io.StringIO()
    code = 0
    try:
        os.chdir(str(cwd))
        sys.stdout, sys.stderr = out, err
        sys.argv = [str(script)] + argv
        try:
            if hasattr(module, "main"):
                if len(inspect.signature(module.main).parameters) == 0:
                    result = module.main()
                else:
                    result = module.main(argv)
            else:
                import runpy
                runpy.run_path(str(script), run_name="__main__")
                result = 0
        except SystemExit as exc:
            result = exc.code
        if result is None:
            code = 0
        elif isinstance(result, int):
            code = result
        else:
            code = 1
    finally:
        os.chdir(old_cwd)
        sys.stdout, sys.stderr, sys.argv = old_stdout, old_stderr, old_argv
    return SimpleNamespace(returncode=code, stdout=out.getvalue(), stderr=err.getvalue())


# ---------------------------------------------------------------------------
# 批量 git fixture
# ---------------------------------------------------------------------------

def _git_skeleton():
    """一次 git init 生成的 .git 骨架，之后复制使用（不再逐 fixture init）。"""
    global _GIT_SKELETON
    if _GIT_SKELETON is None:
        if not GIT:
            raise unittest_skip("需要 git 命令")
        directory = Path(tempfile.mkdtemp(prefix="shipit-git-skeleton-"))
        atexit.register(shutil.rmtree, str(directory), True)
        subprocess.run([GIT, "init", "-q", str(directory)], check=True,
                       capture_output=True)
        config = directory / ".git" / "config"
        text = config.read_text(encoding="utf-8")
        text += "[user]\n\tname = tester\n\temail = tester@example.com\n"
        text += "[core]\n\tautocrlf = false\n"
        config.write_text(text, encoding="utf-8")
        _GIT_SKELETON = directory / ".git"
    return _GIT_SKELETON


def unittest_skip(message):
    import unittest
    raise unittest.SkipTest(message)


def ensure_git(root):
    """复制 .git 骨架；无 git 命令时跳过（测试会显式 skip）。"""
    git_dir = Path(root) / ".git"
    if git_dir.exists():
        return
    shutil.copytree(str(_git_skeleton()), str(git_dir))


def _iso_parts(when):
    stamp = datetime.datetime.fromisoformat(when)
    return int(stamp.timestamp()), stamp.strftime("%z")


def _head_ref(root):
    head = (Path(root) / ".git" / "HEAD").read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        return head[5:].strip()
    return "refs/heads/master"


def _data_block(payload):
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    return b"data " + str(len(raw)).encode("ascii") + b"\n" + raw + b"\n"


def build_history(root, commits):
    """一次 git fast-import 写入整段线性历史，返回每个提交的 sha。

    commits: [{"message": str, "when": ISO8601, "files": {rel: text}}]，
    files 是该提交的完整快照（调用方自行累积）。最后提交的文件会写回工作区。
    """
    ensure_git(root)
    root = Path(root)
    ref = _head_ref(root)
    marks = root / ".git" / "shipit-marks"
    chunks = []
    for index, commit in enumerate(commits, 1):
        epoch, tz = _iso_parts(commit["when"])
        chunks.append(("commit " + ref + "\nmark :%d\n" % index).encode("utf-8"))
        chunks.append(("author tester <tester@example.com> %d %s\n" % (epoch, tz)).encode("utf-8"))
        chunks.append(("committer tester <tester@example.com> %d %s\n" % (epoch, tz)).encode("utf-8"))
        chunks.append(_data_block(commit["message"]))
        if index > 1:
            chunks.append(("from :%d\n" % (index - 1)).encode("utf-8"))
        chunks.append(b"deleteall\n")
        for rel, text in commit["files"].items():
            path = rel.replace("\\", "/")
            chunks.append(("M 100644 inline " + path + "\n").encode("utf-8"))
            chunks.append(_data_block(text))
    result = subprocess.run(
        [GIT, "-C", str(root), "fast-import", "--quiet", "--export-marks=" + str(marks)],
        input=b"".join(chunks), capture_output=True,
    )
    if result.returncode != 0:
        raise AssertionError("git fast-import 失败：\n" + result.stderr.decode("utf-8", "replace"))
    mapping = {}
    if marks.is_file():
        for line in marks.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0].startswith(":"):
                mapping[int(parts[0][1:])] = parts[1]
        marks.unlink()
    clear_git_cache()
    for rel, text in commits[-1]["files"].items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    return [mapping.get(index, "") for index in range(1, len(commits) + 1)]


def _repo_head(root):
    """读 .git/HEAD 指向的 commit sha（不启动 git）。"""
    git = Path(root) / ".git"
    head_file = git / "HEAD"
    if not head_file.is_file():
        return ""
    head = head_file.read_text(encoding="utf-8").strip()
    if not head.startswith("ref: "):
        return head
    ref = head[5:].strip()
    loose = git / ref
    if loose.is_file():
        return loose.read_text(encoding="utf-8").strip()
    packed = git / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if len(parts) == 2 and parts[1] == ref:
                return parts[0]
    return ""

def _ref_sha(root, ref):
    """读 loose ref / packed-refs 得到 commit sha（避免为取父提交再起 git）。"""
    root = Path(root)
    loose = root / ".git" / ref
    if loose.is_file():
        return loose.read_text(encoding="utf-8").strip()
    packed = root / ".git" / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if len(parts) == 2 and parts[1] == ref:
                return parts[0]
    return ""

def commit_worktree(root, message, when):
    """把当前工作区（除 .git）整体提交为一个新 commit；返回 sha。"""
    root = Path(root)
    files = {}
    for path in sorted(root.rglob("*")):
        if ".git" in path.parts or not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        files[rel] = path.read_text(encoding="utf-8")
    ensure_git(root)
    ref = _head_ref(root)
    marks = root / ".git" / "shipit-marks"
    epoch, tz = _iso_parts(when)
    chunks = [("commit " + ref + "\nmark :1\n").encode("utf-8")]
    chunks.append(("author tester <tester@example.com> %d %s\n" % (epoch, tz)).encode("utf-8"))
    chunks.append(("committer tester <tester@example.com> %d %s\n" % (epoch, tz)).encode("utf-8"))
    chunks.append(_data_block(message))
    parent = _ref_sha(root, ref)
    if parent:
        chunks.append(("from " + parent + "\n").encode("utf-8"))
    chunks.append(b"deleteall\n")
    for rel, text in files.items():
        chunks.append(("M 100644 inline " + rel + "\n").encode("utf-8"))
        chunks.append(_data_block(text))
    result = subprocess.run(
        [GIT, "-C", str(root), "fast-import", "--quiet", "--export-marks=" + str(marks)],
        input=b"".join(chunks), capture_output=True,
    )
    if result.returncode != 0:
        raise AssertionError("git fast-import 失败：\n" + result.stderr.decode("utf-8", "replace"))
    sha = ""
    if marks.is_file():
        for line in marks.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0] == ":1":
                sha = parts[1]
        marks.unlink()
    clear_git_cache()
    return sha


def copy_repo(source, destination):
    """复制已构建的 fixture 仓库（含 .git 与工作区）。"""
    shutil.copytree(str(source), str(destination), dirs_exist_ok=True)


def cached_repo(key, builder, destination):
    """同 key 只构建一次；之后复制到 destination。返回 builder 的元数据。"""
    global _CACHE_ROOT
    if _CACHE_ROOT is None:
        _CACHE_ROOT = Path(tempfile.mkdtemp(prefix="shipit-fixtures-"))
        atexit.register(shutil.rmtree, str(_CACHE_ROOT), True)
    entry = _CACHE.get(key)
    if entry is None:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", key)
        directory = _CACHE_ROOT / safe
        directory.mkdir(parents=True, exist_ok=True)
        metadata = builder(directory)
        entry = (directory, metadata)
        _CACHE[key] = entry
    copy_repo(entry[0], destination)
    return entry[1]


# ---------------------------------------------------------------------------
# 慢测试标记（C9）
# ---------------------------------------------------------------------------

def slow(test):
    """标记慢测试；run_suite.py --fast 会排除带 __slow__ 的用例。"""
    test.__slow__ = True
    return test


def is_slow(test):
    """unittest 传入的是 TestCase 实例；标记在类方法上。"""
    if getattr(test, "__slow__", False):
        return True
    function = getattr(test, "__func__", None)
    if function is None:
        name = getattr(test, "_testMethodName", "")
        function = getattr(type(test), name, None) if name else None
    return bool(getattr(function, "__slow__", False))
