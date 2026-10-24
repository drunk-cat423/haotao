#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抖音纯算搜索客户端 —— 无浏览器.

架构:
  1. Node 签名守护进程 (dy_signer.js): 本地加载 webmssdk+glue+bdms 全套 JSVM
     补环境, 经 /web/common + /web/r/token 预热拿到动态 msToken,
     之后对任意 URL 纯算注入 a_bogus/msToken/uifid/webid.
  2. Python 侧用 curl_cffi 模拟浏览器 TLS 指纹发请求.

依赖: node >= 18, pip install curl_cffi

用法:
    python dy_pure.py search 篮球            # 一页10条
    python dy_pure.py search 篮球 -n 20      # 翻页到20条
    python dy_pure.py sign "<url>"          # 只签名

库调用:
    from dy_pure import DouyinPure
    with DouyinPure() as c:
        items = c.search("篮球", pages=2)
"""
import json
import os
import subprocess
import sys
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RUN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run")
SIGNER_JS = os.path.join(RUN_DIR, "dy_signer.js")
COOKIE_FILE = os.path.join(RUN_DIR, "cookie.txt")

try:
    from curl_cffi import requests as creq
except ImportError:
    creq = None


class DouyinPure:
    """Node 签名守护 + curl_cffi 请求的纯算客户端."""

    def __init__(self, cookie_file=COOKIE_FILE, impersonate="chrome131",
                 node="node", timeout=30):
        if creq is None:
            raise RuntimeError("需要 curl_cffi: pip install curl_cffi")
        self.cookie_file = cookie_file
        self.impersonate = impersonate
        self.node = node
        self.timeout = timeout
        self._proc = None
        self._id = 0
        self.session = None

    # ---------- 守护进程协议 ----------
    def _rpc(self, msg, timeout=None):
        self._id += 1
        msg["id"] = self._id
        proc = self._proc
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        deadline = time.time() + (timeout or self.timeout)
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("signer exited")
            try:
                out = json.loads(line)
            except Exception:
                continue
            if out.get("id") == self._id:
                if not out.get("ok"):
                    raise RuntimeError(out.get("error", "signer error"))
                return out
        raise RuntimeError("signer timeout")

    def __enter__(self):
        self._proc = subprocess.Popen(
            [self.node, SIGNER_JS],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        init = self._rpc({"cmd": "init", "cookieFile": self.cookie_file},
                         timeout=60)
        cookie = ""
        self._cookie_map = None
        if os.path.exists(self.cookie_file):
            cookie = open(self.cookie_file, encoding="utf-8").read().strip()
            self._cookie_map = {}
            for part in cookie.split(";"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    self._cookie_map[k.strip()] = v.strip()
        self.session = creq.Session(impersonate=self.impersonate)
        if self._cookie_map:
            for k, v in self._cookie_map.items():
                self.session.cookies.set(k, v)
        self.session.headers.update({
            "user-agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "referer": "https://www.douyin.com/",
        })
        return self

    def __exit__(self, *exc):
        try:
            if self._proc:
                self._rpc({"cmd": "quit"}, timeout=5)
        except Exception:
            pass
        try:
            if self._proc:
                self._proc.kill()
        except Exception:
            pass
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass

    # ---------- 业务 ----------
    def _sync_ms_token(self, rpc_out):
        tok = rpc_out.get("msToken")
        if tok:
            self.session.cookies.set("msToken", tok)

    def sign(self, unsigned_url):
        out = self._rpc({"cmd": "sign", "url": unsigned_url})
        self._sync_ms_token(out)
        return out["url"]

    def search_url(self, keyword, offset=0, count=10, search_id=""):
        out = self._rpc({
            "cmd": "search", "keyword": keyword, "offset": offset,
            "count": count, "search_id": search_id,
        })
        self._sync_ms_token(out)
        return out["url"]

    def request(self, url):
        r = self.session.get(url, timeout=self.timeout)
        ct = r.headers.get("content-type", "")
        if "json" not in ct:
            bdt = r.headers.get("x-vc-bdturing-parameters")
            raise RuntimeError(
                f"非JSON响应 status={r.status_code} ct={ct} "
                f"风控={bool(bdt)}")
        return r.json()

    def search(self, keyword, pages=1, count=10, delay=1.5):
        """综合搜索, 返回 (items, raw_pages). 自动链 search_id 翻页."""
        all_items, raws = [], []
        offset, search_id = 0, ""
        for _ in range(pages):
            data = None
            for attempt in range(2):
                url = self.search_url(keyword, offset=offset, count=count,
                                      search_id=search_id)
                data = self.request(url)
                if (data.get("data") or data.get("status_code") != 0
                        or data.get("has_more") not in (0, None)):
                    break
                # status=0 但空数据 —— 设备风控软拦截, 重签重试一次
                if attempt == 0:
                    time.sleep(3)
            if data is None:
                break
            raws.append(data)
            items = data.get("data") or []
            all_items.extend(items)
            # search_id 在响应顶层 log_pb.impr_id
            search_id = (data.get("log_pb") or {}).get("impr_id") or search_id
            if not items or data.get("has_more") in (0, None):
                break
            offset += len(items) or count
            time.sleep(delay)
        return all_items, raws


def _fmt_item(it):
    info = it.get("aweme_info") or {}
    if not info:
        return {"type": it.get("type"), "raw": it}
    v = info.get("video") or {}
    play = v.get("play_addr") or {}
    downloads = {}
    if play.get("url_list"):
        downloads["sd"] = play["url_list"]
    # bit_rate: 按码率降序排好取最高清
    brs = v.get("bit_rate") or []
    if brs and isinstance(brs[0], dict):
        best = brs[0].get("play_addr") or {}
        if best.get("url_list"):
            downloads["hd"] = best["url_list"]
    da = v.get("download_addr") or {}
    if da.get("url_list"):
        downloads["dl"] = da["url_list"]
    return {
        "id": info.get("aweme_id"),
        "desc": info.get("desc"),
        "author": (info.get("author") or {}).get("nickname"),
        "uid": (info.get("author") or {}).get("uid"),
        "digg": (info.get("statistics") or {}).get("digg_count"),
        "comment": (info.get("statistics") or {}).get("comment_count"),
        "duration_ms": info.get("duration"),
        "page_url": "https://www.douyin.com/video/" + str(info.get("aweme_id")),
        "download": downloads,
        "cover": (v.get("cover") or {}).get("url_list"),
    }


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "search":
        kw = rest[0] if rest else "测试"
        pages, count = 1, 10
        if "-n" in rest:
            i = rest.index("-n")
            count = int(rest[i + 1])
            pages = (count + 9) // 10
        if "-o" in rest:
            i = rest.index("-o")
            outfile = rest[i + 1]
        else:
            outfile = None
        with DouyinPure() as c:
            items, raws = c.search(kw, pages=pages)
        flat = [_fmt_item(x) for x in items]
        print(f"total={len(flat)} pages={len(raws)}")
        for x in flat:
            print("-", x.get("desc") or x.get("type"), "|",
                  x.get("author"), "| digg:", x.get("digg"))
            if x.get("page_url"):
                print("   page:", x["page_url"])
            dl = x.get("download") or {}
            if dl.get("hd") or dl.get("sd"):
                print("   dl:", (dl.get("hd") or dl.get("sd"))[0][:160])
        if outfile:
            json.dump({"items": flat, "raw": raws},
                      open(outfile, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            print("saved:", outfile)
    elif cmd == "sign":
        with DouyinPure() as c:
            print(c.sign(rest[0] if rest else "https://www.douyin.com/"))
    elif cmd == "download":
        # python dy_pure.py download out.json ./videos
        src = rest[0] if rest else "out.json"
        outdir = rest[1] if len(rest) > 1 else "./videos"
        os.makedirs(outdir, exist_ok=True)
        payload = json.load(open(src, encoding="utf-8"))
        items = payload.get("items") or []
        n_ok = 0
        sess = creq.Session(impersonate="chrome131")
        sess.headers["referer"] = "https://www.douyin.com/"
        for i, it in enumerate(items):
            dl = (it.get("download") or {})
            urls = dl.get("hd") or dl.get("sd") or dl.get("dl") or []
            if not urls:
                continue
            name = f"{i:03d}_{it.get('id') or 'x'}.mp4"
            path = os.path.join(outdir, name)
            ok = False
            for u in urls:
                try:
                    r = sess.get(u, timeout=60)
                    if r.status_code == 200 and len(r.content) > 10000:
                        open(path, "wb").write(r.content)
                        ok = True
                        break
                except Exception:
                    continue
            print(("OK " if ok else "FAIL ") + name,
                  "|", (it.get("desc") or "")[:40])
            n_ok += ok
            time.sleep(0.3)
        print(f"downloaded {n_ok}/{len(items)} -> {outdir}")


if __name__ == "__main__":
    main()
