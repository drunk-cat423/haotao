# -*- coding: utf-8 -*-
"""
快手账号工具统一入口.

    python ks.py login <账号> [--timeout=300]     扫码登录并登记
    python ks.py accounts                        已登记账号列表
    python ks.py info <账号>                     重新抓用户信息
    python ks.py publish <账号> <视频> [标题] [描述]
    python ks.py cookie <账号>                   导出 cookie 给纯算用
"""
import json
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ks_common import (load_accounts, PROFILES_DIR, BASE)


def cmd_login(args):
    from ks_login import login_qr
    acc = args[0] if args else "default"
    timeout = 300
    for a in args:
        if a.startswith("--timeout="):
            timeout = int(a.split("=")[1])
    info, cp, _ = login_qr(acc, timeout=timeout)
    if info:
        print(json.dumps(info, ensure_ascii=False, indent=2)[:2500])
        return 0
    return 1


def cmd_accounts(_):
    accs = load_accounts()
    if not accs:
        print("(无登记账号 — 先 ks.py login <名字>)")
        return 0
    for a in accs:
        ui = a.get("user_info") or {}
        nick = ui.get("nickname") or (ui.get("api") or {}).get("nickname") or "?"
        uid = (ui.get("api") or {}).get("userId") or ui.get("ls_uid") or "?"
        print(f"- {a['profile']:12s} 昵称:{nick}  uid:{uid}  登录:{a.get('login_at')}")
    return 0


def cmd_info(args):
    from ks_userinfo import fetch_user_info
    acc = args[0] if args else "default"
    info = fetch_user_info(acc)
    print(json.dumps(info or {}, ensure_ascii=False, indent=2)[:3000])
    return 0 if info else 1


def cmd_publish(args):
    from ks_publish import publish
    dry = "--dry-run" in args
    args = [a for a in args if not a.startswith("--")]
    if len(args) < 2:
        print("用法: ks.py publish <账号> <视频.mp4> [标题] [描述] [--dry-run]")
        return 2
    ok = publish(args[0], args[1],
                 args[2] if len(args) > 2 else "",
                 args[3] if len(args) > 3 else "",
                 dry_run=dry)
    return 0 if ok else 1


def cmd_cookie(args):
    acc = args[0] if args else "default"
    cp = os.path.join(PROFILES_DIR, acc + ".cookie.txt")
    if not os.path.exists(cp):
        print(f"(无 {cp} — 先 login)")
        return 1
    # 同步到纯算读取位置
    dst = os.path.join(BASE, "..", "pure", "run", "cookie.txt")
    open(dst, "w", encoding="utf-8").write(open(cp, encoding="utf-8").read())
    print(f"cookie -> {dst} (ks_pure.py 直接可用)")
    return 0


CMDS = {"login": cmd_login, "accounts": cmd_accounts, "info": cmd_info,
        "publish": cmd_publish, "cookie": cmd_cookie}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        return 2
    return CMDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
