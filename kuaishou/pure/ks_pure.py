# -*- coding: utf-8 -*-
"""快手搜索纯算客户端 —— __NS_hxfalcon 由 Node 本地算法函数生成, 无浏览器.

用法:
  python ks_pure.py search 篮球              # 一页 (type=VIDEO)
  python ks_pure.py search 篮球 -n 40        # 翻页
  python ks_pure.py search 篮球 -o out.json  # 存文件
  python ks_pure.py download out.json ./videos
  python ks_pure.py sign /rest/v/search/feed '{"keyword":"篮球"}'

库:
  from ks_pure import KuaishouPure
  with KuaishouPure() as c:
      items, raws = c.search("篮球", pages=2)
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse

from curl_cffi import requests as creq

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE, "run", "cookie.txt")
NODE_SCRIPT = os.path.join(BASE, "ks_sign.js")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")


class KuaishouPure:
    def __init__(self, cookie_file=COOKIE_FILE, impersonate="chrome131",
                 timeout=30):
        self.cookie_file = cookie_file
        self.impersonate = impersonate
        self.timeout = timeout
        self.session = None

    def __enter__(self):
        cookie = ""
        if os.path.exists(self.cookie_file):
            cookie = open(self.cookie_file, encoding="utf-8").read().strip()
        self.session = creq.Session(impersonate=self.impersonate)
        self.session.headers.update({
            "user-agent": UA,
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9",
            "origin": "https://www.kuaishou.com",
            "referer": "https://www.kuaishou.com/",
            "cookie": cookie,
        })
        return self

    def __exit__(self, *a):
        if self.session:
            self.session.close()

    # ---------- 签名 ----------
    def _node_sign(self, path_name, form, body=None, caver="2"):
        env = dict(os.environ)
        env["MSYS_NO_PATHCONV"] = "1"
        r = subprocess.run(
            ["node", NODE_SCRIPT, path_name,
             json.dumps(form, ensure_ascii=False, separators=(",", ":")),
             json.dumps(body or {}, ensure_ascii=False,
                        separators=(",", ":")),
             caver],
            capture_output=True, cwd=BASE, env=env)
        if r.returncode != 0:
            raise RuntimeError("signer rc=%d: %s" % (
                r.returncode, r.stderr.decode("utf-8", "replace")[:300]))
        return json.loads(r.stdout.decode("utf-8"))

    def signed_url(self, path_name, form, body=None, caver="2"):
        out = self._node_sign(path_name, form, body, caver)
        sig = urllib.parse.quote(out["signRes"], safe="")
        return ("https://www.kuaishou.com" + path_name
                + "?__NS_hxfalcon=" + sig + "&caver=" + caver, out)

    # ---------- 请求 ----------
    def request(self, path_name, form, body=None):
        url, siginfo = self.signed_url(path_name, form, body)
        r = self.session.post(url, json=form if body is None else body,
                              headers={"content-type": "application/json"},
                              timeout=self.timeout)
        return r.json(), siginfo

    # ---------- 搜索 ----------
    def search(self, keyword, pages=1, stype="VIDEO", delay=1.5):
        """返回 (feeds, raw_pages). pcursor 链翻页."""
        all_feeds, raws = [], []
        pcursor, page = "", 1
        for _ in range(pages):
            form = {"keyword": keyword, "page": page, "pcursor": pcursor,
                    "search_channel": "", "type": stype}
            try:
                j, _ = self.request("/rest/v/search/feed", form)
            except Exception as e:
                print("[req err]", str(e)[:150])
                break
            raws.append(j)
            if j.get("result") != 1:
                print("[api err]", j.get("result"), j.get("error_msg"))
                break
            feeds = j.get("feeds") or []
            all_feeds.extend(feeds)
            pcursor = j.get("pcursor") or ""
            if not feeds or not pcursor or pcursor == "no_more":
                break
            page += 1
            time.sleep(delay)
        return all_feeds, raws


def _video_urls(photo):
    """manifest -> [(quality, url)] 按码率降序."""
    out = []
    man = photo.get("manifest")
    if isinstance(man, str):
        try:
            man = json.loads(man)
        except Exception:
            man = None
    for ads in (man or {}).get("adaptationSet") or []:
        for rep in ads.get("representation") or []:
            u = rep.get("url")
            if u:
                out.append((rep.get("qualityLabel") or
                            rep.get("qualityType") or "?", u))
    return out


def _fmt_item(f):
    ph = f.get("photo") or {}
    au = f.get("author") or {}
    if not ph:
        return {"type": f.get("type"), "raw": f}
    vids = _video_urls(ph)
    return {
        "id": ph.get("id"),
        "caption": ph.get("caption"),
        "author": (au.get("name") or
                   (ph.get("userName")) or (au.get("id"))),
        "like": ph.get("likeCount"),
        "view": ph.get("viewCount"),
        "duration_ms": ph.get("duration"),
        "ts": ph.get("timestamp"),
        "page_url": ("https://www.kuaishou.com/short-video/"
                     + str(ph.get("id")) if ph.get("id") else None),
        "videos": vids,
        "cover": ph.get("coverUrl"),
    }


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "search":
        kw = rest[0] if rest else "篮球"
        pages, out = 1, None
        if "-n" in rest:
            i = rest.index("-n")
            pages = (int(rest[i + 1]) + 19) // 20 or 1
        if "-o" in rest:
            out = rest[rest.index("-o") + 1]
        with KuaishouPure() as c:
            feeds, raws = c.search(kw, pages=pages)
        flat = [_fmt_item(f) for f in feeds]
        print("total=%d pages=%d" % (len(flat), len(raws)))
        for x in flat:
            print("-", (x.get("caption") or str(x.get("type")))[:70],
                  "|", x.get("author"), "| like:", x.get("like"))
            if x.get("page_url"):
                print("   page:", x["page_url"])
            if x.get("videos"):
                print("   dl:", x["videos"][0][1][:150])
        if out:
            json.dump({"items": flat, "raw": raws},
                      open(out, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            print("saved:", out)
    elif cmd == "sign":
        path_name = rest[0] if rest else "/rest/v/search/feed"
        form = json.loads(rest[1]) if len(rest) > 1 else {}
        with KuaishouPure() as c:
            url, info = c.signed_url(path_name, form)
        print("signInput:", info["signInput"][:200])
        print("url:", url)
    elif cmd == "download":
        src = rest[0] if rest else "out.json"
        outdir = rest[1] if len(rest) > 1 else "./videos"
        os.makedirs(outdir, exist_ok=True)
        payload = json.load(open(src, encoding="utf-8"))
        sess = creq.Session(impersonate="chrome131")
        sess.headers["referer"] = "https://www.kuaishou.com/"
        n_ok = 0
        for i, it in enumerate(payload.get("items") or []):
            vids = it.get("videos") or []
            if not vids:
                continue
            name = "%03d_%s.mp4" % (i, it.get("id") or "x")
            path = os.path.join(outdir, name)
            ok = False
            for _, u in vids:
                try:
                    r = sess.get(u, timeout=60)
                    if r.status_code == 200 and len(r.content) > 10000:
                        open(path, "wb").write(r.content)
                        ok = True
                        break
                except Exception:
                    continue
            print(("OK " if ok else "FAIL ") + name,
                  "|", (it.get("caption") or "")[:40])
            n_ok += ok
            time.sleep(0.3)
        print("downloaded %d/%d -> %s" % (n_ok,
              len(payload.get("items") or []), outdir))


if __name__ == "__main__":
    main()
