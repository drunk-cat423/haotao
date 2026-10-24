#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开箱即用 demo — 抖音搜3条 + 快手搜3条, 打印标题+链接"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "douyin"))
sys.path.insert(0, os.path.join(BASE, "kuaishou"))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def douyin_demo(kw):
    from dy_abogus import DouyinPure
    print("== 抖音 (a_bogus 纯算) ==")
    with DouyinPure() as c:
        items, _ = c.search(kw, pages=1)
        for it in items[:3]:
            aw = it.get("aweme_info") or {}
            links = DouyinPure.video_links(it)
            print(" -", (aw.get("desc") or "")[:36])
            print("   page:", links["page_url"])
            print("   dl:", (links["hd"] or links["sd"] or links["dl"] or [""])[0][:90])
        print(f"   ({len(items)} items total)")


def kuaishou_demo(kw):
    from ks_pure import KuaishouPure
    print("== 快手 (__NS_hxfalcon 纯算) ==")
    with KuaishouPure() as c:
        feeds, _ = c.search(kw, pages=1)
    for it in feeds[:3]:
        ph = it.get("photo") or {}
        print(" -", (ph.get("caption") or "")[:36])
        print("   id:", ph.get("id"), "| dur:", round(ph.get("duration", 0) / 1000, 1), "s")
    print(f"   ({len(feeds)} feeds total)")


def main():
    kw = sys.argv[1] if len(sys.argv) > 1 else "篮球"
    try:
        douyin_demo(kw)
    except Exception as e:
        print("  douyin err:", e)
    print()
    try:
        kuaishou_demo(kw)
    except Exception as e:
        print("  kuaishou err:", e)


if __name__ == "__main__":
    main()
