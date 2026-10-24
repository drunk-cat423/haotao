#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dy_abogus.py —— 抖音搜索 真·纯算客户端

签名实现: dy_abogus_signer.js (bdms.js 独立运行, 无浏览器/无握手/无网络)
依赖:   Node>=18 + `pip install curl_cffi`
数据流: python -> node 签名守护进程(stdin/stdout) -> 带 a_bogus 的 URL -> curl_cffi 请求

用法:
    python dy_abogus.py search 篮球 [-n 20] [-o out.json]
    python dy_abogus.py sign '<URL>'
    python dy_abogus.py download out.json ./videos

库调用:
    from dy_abogus import DouyinPure
    with DouyinPure() as c:
        items, raws = c.search("篮球", pages=2)
"""

import json
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
SIGNER = os.path.join(_HERE, "dy_abogus_signer.js")
SECRETS_FILE = os.path.join(_HERE, "../pure/local/session.secrets.json")
COOKIE_FILE = os.path.join(_HERE, "../pure/run/cookie.txt")

EP = "https://www.douyin.com/aweme/v1/web/general/search/single/"
UA_FALLBACK = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _load_secrets():
    try:
        return json.load(open(SECRETS_FILE, encoding="utf-8"))
    except Exception:
        return {}


def _load_cookie():
    try:
        return open(COOKIE_FILE, encoding="utf-8").read().strip()
    except Exception:
        return ""


class _Signer:
    """常驻 node 签名守护: stdin 发 URL, stdout 收签名 URL"""

    def __init__(self):
        self.proc = subprocess.Popen(
            ["node", SIGNER],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            cwd=_HERE, text=True, encoding="utf-8", errors="replace",
        )
        time.sleep(2.2)  # bdms 初始化窗口

    def sign(self, url: str) -> str:
        self.proc.stdin.write(url + "\n")
        self.proc.stdin.flush()
        out = self.proc.stdout.readline().strip()
        return out or url

    def sign_search(self, keyword: str, offset: int, count: int) -> str:
        self.proc.stdin.write(f"SEARCH {keyword} {offset} {count}\n")
        self.proc.stdin.flush()
        return self.proc.stdout.readline().strip()

    def close(self):
        try:
            self.proc.terminate()
        except Exception:
            pass


class DouyinPure:
    def __init__(self, cookie=None, ua=None, impersonate="chrome131"):
        self.secrets = _load_secrets()
        self.cookie = cookie if cookie is not None else _load_cookie()
        self.ua = ua or self.secrets.get("ua") or UA_FALLBACK
        self.impersonate = impersonate
        self.signer = _Signer()
        self._last_search_id = ""

    def close(self):
        self.signer.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    # ---- http ----
    def _fetch(self, url: str, retries: int = 2):
        from curl_cffi import requests as cr
        headers = {
            "User-Agent": self.ua,
            "Cookie": self.cookie,
            "Referer": "https://www.douyin.com/search/x",
            "Accept": "application/json, text/plain, */*",
        }
        last = None
        for _ in range(retries):
            try:
                r = cr.get(url, headers=headers, impersonate=self.impersonate, timeout=20)
                if r.status_code == 200:
                    return r.json()
                last = {"http": r.status_code, "body": r.text[:200]}
            except Exception as e:
                last = {"err": str(e)}
            time.sleep(1.5)
        return last or {}

    # ---- search ----
    def search(self, keyword: str, pages: int = 1, count: int = 12):
        """翻页搜索. 返回 (items, raws). items 含 aweme_info/download 直链."""
        all_items, raws = [], []
        offset, search_id = 0, ""
        for _ in range(pages):
            url = self.signer.sign_search(keyword, offset, count)
            if search_id:
                # 翻页链: 服务端用 search_id(=log_pb.impr_id) 去重/续页
                url += "&search_id=" + search_id
            j = self._fetch(url)
            raws.append(j)
            data = j.get("data") or []
            all_items.extend(data)
            lp = j.get("log_pb") or {}
            search_id = lp.get("impr_id") or search_id
            if not j.get("has_more"):
                break
            offset += len(data) or count
            time.sleep(1.5)
        return all_items, raws

    # ---- helpers ----
    @staticmethod
    def video_links(item: dict) -> dict:
        """从条目提取视频链接: page_url + 多档 MP4 直链 + 封面"""
        aw = item.get("aweme_info") or {}
        vid = (aw.get("video") or {})
        out = {"page_url": "", "sd": [], "hd": [], "dl": [], "cover": []}
        aid = aw.get("aweme_id")
        if aid:
            out["page_url"] = f"https://www.douyin.com/video/{aid}"
        pa = vid.get("play_addr") or {}
        if pa.get("url_list"):
            out["sd"] = list(pa["url_list"])
        pa_hd = vid.get("play_addr_265") or vid.get("play_addr_h264") or {}
        if pa_hd.get("url_list"):
            out["hd"] = list(pa_hd["url_list"])
        dl = vid.get("download_addr") or {}
        if dl.get("url_list"):
            out["dl"] = list(dl["url_list"])
        cov = vid.get("cover") or vid.get("origin_cover") or {}
        if cov.get("url_list"):
            out["cover"] = list(cov["url_list"])
        return out

    def download(self, url: str, dest: str, headers_extra=None):
        from curl_cffi import requests as cr
        h = {"User-Agent": self.ua, "Referer": "https://www.douyin.com/"}
        if headers_extra:
            h.update(headers_extra)
        r = cr.get(url, headers=h, impersonate=self.impersonate, timeout=60, stream=True)
        n = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                n += len(chunk)
        return n


def _fmt_item(it):
    aw = it.get("aweme_info") or {}
    v = DouyinPure.video_links(it)
    return {
        "id": aw.get("aweme_id"),
        "desc": aw.get("desc"),
        "author": (aw.get("author") or {}).get("nickname"),
        "digg": (aw.get("statistics") or {}).get("digg_count"),
        "page_url": v["page_url"],
        "download": {k: v[k] for k in ("sd", "hd", "dl")},
        "cover": v["cover"],
    }


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd, rest = args[0], args[1:]
    with DouyinPure() as c:
        if cmd == "sign":
            url = rest[0] if rest else ""
            print(c.signer.sign(url))
            return
        if cmd == "search":
            kw = rest[0] if rest else "篮球"
            pages, out = 1, None
            i = 1
            while i < len(rest):
                if rest[i] == "-n":
                    n = int(rest[i + 1]); pages = max(1, n // 12 + (1 if n % 12 else 0)); i += 2
                elif rest[i] == "-o":
                    out = rest[i + 1]; i += 2
                elif rest[i] == "--raw":
                    i += 1
                else:
                    i += 1
            items, raws = c.search(kw, pages=pages)
            rows = [_fmt_item(it) for it in items]
            print(f"total={len(rows)} pages={len(raws)}")
            for r in rows:
                print("-", r["desc"], "|", r["author"], "| digg:", r["digg"])
                if r["page_url"]:
                    print("  page:", r["page_url"])
                dl = (r["download"].get("hd") or r["download"].get("sd") or r["download"].get("dl") or [])
                if dl:
                    print("  dl:", dl[0])
                if r["cover"]:
                    print("  cover:", r["cover"][0])
            if out:
                json.dump({"items": rows, "raw": raws}, open(out, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
                print("saved ->", out)
            return
        if cmd == "download":
            src, dest = rest[0], (rest[1] if len(rest) > 1 else "./videos")
            os.makedirs(dest, exist_ok=True)
            data = json.load(open(src, encoding="utf-8"))
            n_ok = 0
            for i, it in enumerate(data.get("items") or []):
                dl = (it.get("download") or {})
                url = (dl.get("hd") or dl.get("sd") or dl.get("dl") or [None])[0]
                if not url:
                    continue
                fn = os.path.join(dest, f"{i:03d}_{(it.get('id') or 'x')}.mp4")
                try:
                    sz = c.download(url, fn)
                    n_ok += 1
                    print(f"  {fn} {sz//1024}KB")
                except Exception as e:
                    print("  err", i, e)
                time.sleep(0.5)
            print(f"done {n_ok} files")
            return
        print("unknown cmd:", cmd)


if __name__ == "__main__":
    main()
