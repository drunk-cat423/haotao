#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_creds.py —— 从已登录的浏览器 profile 自动提取凭证, 生成 config/ 下全部文件.

用法:
    # 指纹浏览器/Firefox (cookies.sqlite 明文, 直接读)
    python extract_creds.py --douyin-profile ../douyin_profile --kuaishou-profile ../ks_profile --fp-file profile1.txt

    # 自动探测当前目录/上级目录下的 *_profile
    python extract_creds.py

说明:
    - Firefox/指纹浏览器: cookie 存 profile/cookies.sqlite (sqlite 明文)
    - 会先生成临时副本再读, 不锁浏览器
    - uifid/verifyFp/fp/webid/msToken 都从 cookie/JWT 直接解出
    - ua 从指纹文件 useragent= 行或 --ua 传入
"""

import argparse
import base64
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(BASE, "config")


def read_cookies(profile_dir, domain):
    """Firefox cookies.sqlite -> [(name, value, host)]"""
    src = os.path.join(profile_dir, "cookies.sqlite")
    if not os.path.exists(src):
        return []
    tmp = tempfile.mktemp(suffix=".sqlite")
    shutil.copy(src, tmp)
    try:
        con = sqlite3.connect(tmp)
        rows = con.execute(
            "SELECT name, value, host FROM moz_cookies WHERE host LIKE ?",
            (f"%{domain}%",),
        ).fetchall()
        con.close()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return rows


def cookie_string(rows):
    return "; ".join(f"{n}={v}" for n, v, _ in rows)


def get_cookie(rows, *names):
    low = {n.lower(): v for n, v, _ in rows}
    for name in names:
        if name.lower() in low:
            return low[name.lower()]
    return ""


def jwt_payload(token):
    try:
        mid = token.split(".")[1]
        mid += "=" * (-len(mid) % 4)
        return json.loads(base64.urlsafe_b64decode(mid))
    except Exception:
        return {}


def ua_from_fp(fp_file):
    if not fp_file or not os.path.exists(fp_file):
        return ""
    for line in open(fp_file, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*useragent\s*[:=]\s*(.+)", line, re.I)
        if m:
            return m.group(1).strip()
    return ""


def find_profiles():
    """当前目录及上两级找 *_profile / cookies.sqlite 所在目录"""
    roots = [BASE, os.path.dirname(BASE), os.path.join(BASE, "..", "..")]
    found = {"douyin": None, "kuaishou": None}
    for r in roots:
        if not os.path.isdir(r):
            continue
        for name in os.listdir(r):
            p = os.path.join(r, name)
            if not os.path.isdir(p):
                continue
            if os.path.exists(os.path.join(p, "cookies.sqlite")):
                low = name.lower()
                if ("douyin" in low or "dy" in low) and not found["douyin"]:
                    found["douyin"] = p
                elif ("kuaishou" in low or "ks" in low or "kwai" in low) and not found["kuaishou"]:
                    found["kuaishou"] = p
                elif not found["douyin"]:
                    found["douyin"] = p  # 兜底
    return found


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="提取浏览器凭证 -> config/")
    ap.add_argument("--douyin-profile", help="抖音登录的浏览器 profile 目录")
    ap.add_argument("--kuaishou-profile", help="快手登录的浏览器 profile 目录")
    ap.add_argument("--profile", help="通用: 两平台共用一个 profile")
    ap.add_argument("--fp-file", help="指纹文件 (含 useragent= 行)")
    ap.add_argument("--ua", help="直接指定 UA")
    args = ap.parse_args()

    os.makedirs(CONFIG, exist_ok=True)
    found = find_profiles()
    dy_prof = args.douyin_profile or args.profile or found["douyin"]
    ks_prof = args.kuaishou_profile or args.profile or found["kuaishou"]

    ok = []
    # ---------- 抖音 ----------
    if dy_prof:
        rows = read_cookies(dy_prof, "douyin.com")
        if rows:
            out = os.path.join(CONFIG, "douyin.cookie.txt")
            open(out, "w", encoding="utf-8").write(cookie_string(rows))
            ok.append(f"douyin.cookie.txt <- {len(rows)} cookies  (from {dy_prof})")

            # uifid: UIFID / UIFID_TEMP
            uifid = get_cookie(rows, "UIFID", "UIFID_TEMP", "uifid")
            # webid: web_sign_token JWT -> id
            wst = get_cookie(rows, "web_sign_token")
            webid = (jwt_payload(wst).get("id") or "")
            if not webid:
                for n, v, _ in rows:
                    if re.fullmatch(r"\d{15,25}", v) and "webid" in n.lower():
                        webid = v
            # verifyFp/fp: s_v_web_id
            svw = get_cookie(rows, "s_v_web_id")
            ms_token = get_cookie(rows, "msToken")
            ua = args.ua or ua_from_fp(args.fp_file)

            secrets = {
                "ua": ua or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "uifid": uifid,
                "webid": webid,
                "verify_fp": svw,
                "fp": svw,
                "msToken": ms_token,
                "browser_version": "138.0.0.0",
                "browser_language": "zh-CN",
                "browser_name": "Chrome",
                "browser_platform": "Win32",
                "screen_width": "1920",
                "screen_height": "1080",
                "device_memory": "8",
                "cpu_core_num": "16",
                "os_name": "Windows",
                "os_version": "10",
                "endpoint": "general",
            }
            # 合并已有 secrets (保留非抽取字段)
            sj_path = os.path.join(CONFIG, "session.secrets.json")
            if os.path.exists(sj_path):
                try:
                    old = json.load(open(sj_path, encoding="utf-8"))
                    old.update({k: v for k, v in secrets.items() if v})
                    secrets = old
                except Exception:
                    pass
            json.dump(secrets, open(sj_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            miss = [k for k in ("uifid", "webid", "verify_fp") if not secrets.get(k)]
            ok.append(f"session.secrets.json  uifid={uifid[:20]}... webid={webid} msToken={'Y' if ms_token else 'N'}"
                      + (f"  [缺: {miss}]" if miss else ""))
        else:
            print(f"[skip] {dy_prof} 无 douyin.com cookies")

    # ---------- 快手 ----------
    if ks_prof:
        rows = read_cookies(ks_prof, "kuaishou.com")
        if rows:
            out = os.path.join(CONFIG, "kuaishou.cookie.txt")
            open(out, "w", encoding="utf-8").write(cookie_string(rows))
            ok.append(f"kuaishou.cookie.txt <- {len(rows)} cookies  (from {ks_prof})")
        else:
            print(f"[skip] {ks_prof} 无 kuaishou.com cookies")

    print("== 提取结果 ==")
    for line in ok:
        print(" ", line)
    if not ok:
        print("  没抽到任何东西 — 检查 --profile 路径或把 profile 放到本目录/上级目录")
    else:
        print("== 下一步: python check_env.py && python demo.py 篮球 ==")


if __name__ == "__main__":
    main()
