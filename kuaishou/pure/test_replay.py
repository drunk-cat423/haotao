# -*- coding: utf-8 -*-
"""快手签名服务器验收: Node 纯算签名 -> curl_cffi 回放 /rest/v/search/feed."""
import json
import os
import subprocess
import sys
import urllib.parse

from curl_cffi import requests as cr

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = os.path.dirname(os.path.abspath(__file__))


def node_sign(path_name, form, body=None, caver="2"):
    env = dict(os.environ)
    env["MSYS_NO_PATHCONV"] = "1"
    r = subprocess.run(
        ["node", "ks_sign.js", path_name,
         json.dumps(form, ensure_ascii=False),
         json.dumps(body or {}, ensure_ascii=False), caver],
        capture_output=True, cwd=BASE, env=env)
    out = r.stdout.decode("utf-8", "replace")
    if r.returncode != 0:
        raise RuntimeError("node rc=%d err=%s" % (r.returncode, r.stderr.decode("utf-8", "replace")[:400]))
    return json.loads(out)


def load_cookie():
    caps = json.load(open(
        r"E:\parttime-job\douyin\captures\ks_search_requests.json",
        encoding="utf-8"))
    for c in caps:
        ck = (c.get("headers") or {}).get("Cookie") or \
             (c.get("headers") or {}).get("cookie")
        if ck:
            return ck
    return ""


def main():
    cookie = load_cookie()
    print("cookie len:", len(cookie))
    form = {"keyword": "篮球", "page": 1, "pcursor": "",
            "search_channel": "", "type": "VIDEO"}
    sig = node_sign("/rest/v/search/feed", form)
    print("signInput:", sig["signInput"][:140])
    print("sig:", sig["signRes"][:70] + "...")

    url = ("https://www.kuaishou.com/rest/v/search/feed?__NS_hxfalcon="
           + urllib.parse.quote(sig["signRes"], safe="") + "&caver=2")
    resp = cr.post(url, impersonate="chrome131", json=form, headers={
        "user-agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "cookie": cookie,
        "referer": "https://www.kuaishou.com/search/video?searchKey="
            + urllib.parse.quote("篮球"),
        "origin": "https://www.kuaishou.com",
        "content-type": "application/json",
    }, timeout=30)
    print("HTTP", resp.status_code)
    try:
        j = resp.json()
        print("result:", j.get("result"), "| err:", j.get("error_msg"),
              "| feeds:", len(j.get("feeds") or j.get("photos") or []),
              "| keys:", list(j.keys())[:15])
        if j.get("feeds"):
            f = j["feeds"][0]
            ph = f.get("photo") or {}
            print("first:", (ph.get("caption") or "")[:60],
                  "| id:", ph.get("id"))
    except Exception:
        print("body:", resp.text[:400])


if __name__ == "__main__":
    main()
