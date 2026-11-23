#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install-hooks.py — C10：安装 ship-it pre-commit hook（pre_commit_check.py install-hooks 的薄包装）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pre_commit_check


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    return pre_commit_check.main(["install-hooks"] + args)


if __name__ == "__main__":
    raise SystemExit(main())
