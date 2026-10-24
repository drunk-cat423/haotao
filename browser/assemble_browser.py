#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重组 ruyipage-with-browser.zip —— 把 .001/.002/.003 分片拼回完整 zip.

用法:
    python browser/assemble_browser.py          # 输出 browser/ruyipage-with-browser.zip
    然后解压到任意位置即可用 ruyipage 打开指纹浏览器.
"""
import glob
import hashlib
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ruyipage-with-browser.zip")


def main():
    parts = sorted(glob.glob(os.path.join(HERE, "ruyipage-with-browser.zip.*")))
    if not parts:
        print("没找到分片 ruyipage-with-browser.zip.001/.002/...")
        sys.exit(1)
    print("分片:", [os.path.basename(p) for p in parts])
    h = hashlib.sha256()
    total = 0
    with open(OUT, "wb") as w:
        for p in parts:
            data = open(p, "rb").read()
            w.write(data)
            h.update(data)
            total += len(data)
    print(f"重组完成: {OUT}  ({total / 1024 / 1024:.1f} MB)")
    print(f"sha256: {h.hexdigest()}")
    try:
        with zipfile.ZipFile(OUT) as z:
            bad = z.testzip()
            if bad:
                print("zip 校验失败:", bad)
                sys.exit(1)
        print("zip 校验通过, 可以解压")
    except zipfile.BadZipFile as e:
        print("zip 文件损坏:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
