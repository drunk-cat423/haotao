#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境自检 — 跑一遍确认 Node/Python/依赖/配置都齐"""
import json
import os
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
OK, WARN, ERR = "[OK]", "[!!]", "[--]"


def check(name, fn):
    try:
        res = fn()
        print(f"  {OK} {name}: {res}")
        return True
    except Exception as e:
        print(f"  {ERR} {name}: {e}")
        return False


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("== ai-reverse-pure 环境自检 ==")
    ok = True

    ok &= check("python>=3.9", lambda: f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    ok &= check("node", lambda: subprocess.check_output(["node", "--version"], text=True).strip())

    def _cf():
        try:
            import curl_cffi
            return curl_cffi.__version__
        except ImportError:
            raise RuntimeError("pip install curl_cffi")
    ok &= check("curl_cffi", _cf)

    cfg = os.path.join(BASE, "config")
    def _dy_ck():
        p = os.path.join(cfg, "douyin.cookie.txt")
        if not os.path.exists(p):
            raise RuntimeError("缺 config/douyin.cookie.txt (见 .example)")
        c = open(p, encoding="utf-8").read()
        return f"{len(c)} chars" if "sessionid" in c or "msToken" in c else "内容不像cookie"
    print("  -- 凭证检查 --")
    ok &= check("douyin.cookie.txt", _dy_ck)

    def _dy_sj():
        p = os.path.join(cfg, "session.secrets.json")
        if not os.path.exists(p):
            raise RuntimeError("缺 config/session.secrets.json (见 .example)")
        s = json.load(open(p, encoding="utf-8"))
        need = ["ua", "uifid", "webid"]
        miss = [k for k in need if not s.get(k)]
        if miss:
            raise RuntimeError(f"缺字段: {miss}")
        return f"{len(s)} fields"
    ok &= check("session.secrets.json", _dy_sj)

    def _ks_ck():
        p = os.path.join(cfg, "kuaishou.cookie.txt")
        if not os.path.exists(p):
            raise RuntimeError("缺 config/kuaishou.cookie.txt (见 .example)")
        return "ok"
    ok &= check("kuaishou.cookie.txt", _ks_ck)

    print("== 结果:", "全部就绪" if ok else "有缺项 — 对照上面补齐 ==")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
