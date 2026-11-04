# -*- coding: utf-8 -*-
"""
快手扫码登录 —— 指纹浏览器打开 kuaishou.com → 点登录 → 提取二维码 PNG
→ 等用户扫码 → 落凭证 + 抓用户信息 + 登记账号.

用法:
    python ks_login.py <账号名>              # python ks_login.py acc1
    python ks_login.py acc1 --timeout=300
    python ks_login.py acc1 --headless
产物:
    profiles/<账号>/                        firefox profile (持久登录态)
    profiles/<账号>.cookie.txt              cookie 行 (纯算 ks_pure.py 直接用)
    qrcode_<账号>.png                       二维码 (用快手App扫)
    accounts.json                          账号登记表
"""
import base64
import json
import os
import sys
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ks_common import (launch, live_cookies, is_logged_in, page_logged_in,
                       register_account, BASE)

LOGIN_URL = "https://www.kuaishou.com/"
QR_IMG_SEL = ".qrcode-img img, .qrcode img, [class*=qrcode] img"
LOGIN_BTN_SEL = ".sidebar-login-button"


def _click_login(page):
    """可信输入点登录按钮出二维码弹窗."""
    try:
        e = page.ele(LOGIN_BTN_SEL, timeout=5)
        if e:
            e.click()
            return "sidebar-login-button"
    except Exception:
        pass
    for loc in ("text:立即登录", "xpath://*[contains(@class,'login')][contains(text(),'登录')]"):
        try:
            e = page.ele(loc, timeout=3)
            if e:
                e.click()
                return loc
        except Exception:
            continue
    # 兜底 JS click (弹窗不要求 trusted)
    return page.run_js(r"""
    (() => {
      const c = document.querySelector('.sidebar-login-button');
      if (c) { c.click(); return 'js:' + c.className; }
      return null;
    })()
    """, as_expr=True)


def _wait_qr(page, timeout=15):
    """等 .qrcode-img img 出现, 返回 base64 data url."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        src = page.run_js(r"""
        (() => {
          const img = document.querySelector('.qrcode-img img, .qrcode img');
          if (img && img.src && img.src.startsWith('data:image')) return img.src;
          for (const m of document.querySelectorAll('[class*=modal],[role=dialog],[class*=login-modal]')) {
            for (const i of m.querySelectorAll('img')) {
              if ((i.src||'').startsWith('data:image') && i.width > 60) return i.src;
            }
          }
          return null;
        })()
        """, as_expr=True)
        if src:
            return src
        time.sleep(0.8)
    return None


def _save_qr(data_url, account):
    png = os.path.join(BASE, f"qrcode_{account}.png")
    b64 = data_url.split(",", 1)[1]
    open(png, "wb").write(base64.b64decode(b64))
    return png


def _fetch_user_info(page):
    """登录后抓用户信息: 头像/昵称/uid/localStorage/接口兜底."""
    out = {}
    try:
        r = page.run_js(r"""
        (() => {
          const o = {};
          const av = document.querySelector('img[class*=avatar], .avatar img, [class*=Avatar] img');
          if (av) o.avatar = av.src;
          for (const sel of ['[class*=nickname]','[class*=user-name]','.sidebar-user [class*=name]']) {
            const e = document.querySelector(sel);
            const t = e && (e.textContent||'').trim();
            if (t && t.length < 30) { o.nickname = t; break; }
          }
          for (let i=0;i<localStorage.length;i++){
            const k=localStorage.key(i), v=localStorage.getItem(k);
            if (/^(uid|userId|mid|user_id)$/i.test(k)) o['ls_'+k]=v;
            else if (/userInfo|my_user|self/i.test(k)) { try{o['ls_'+k]=JSON.parse(v)}catch(e){o['ls_'+k]=v.slice(0,400)} }
          }
          return o;
        })()
        """, as_expr=True) or {}
        out.update(r)
    except Exception:
        pass
    try:
        r = page.run_js(
            "fetch('https://www.kuaishou.com/rest/v/uc/web/user/info',"
            "{credentials:'include'}).then(r=>r.json())",
            as_expr=True)
        if isinstance(r, dict) and (r.get("userInfo") or r.get("data")):
            out["api"] = r.get("userInfo") or r.get("data")
    except Exception:
        pass
    return out


def login_qr(account="default", timeout=240, headless=False, keep_open=False):
    """扫码登录主流程. 返回 (user_info, cookie_path, page_or_None)."""
    page, user_dir = launch(account, headless=headless)
    print(f"[login] profile: {user_dir}")
    page.get(LOGIN_URL)
    time.sleep(4)

    # UI 判定: 已登录就跳过扫码 (cookie 可能服务端过期, 信UI)
    if page_logged_in(page):
        print("[login] UI 已登录, 直接登记")
        info = _fetch_user_info(page)
        cookies = live_cookies(page)
        register_account(account, info, cookies)
        cp = os.path.join(user_dir, "..", account + ".cookie.txt")
        if not keep_open:
            try:
                page.quit()
            except Exception:
                pass
            page = None
        return info, cp, page

    hit = _click_login(page)
    print(f"[login] 登录按钮: {hit or '未找到'}")
    time.sleep(3)

    src = _wait_qr(page)
    if not src:
        print("[login] 未提取到二维码 — 截图存 debug")
        page.screenshot(path=os.path.join(BASE, f"debug_{account}.png"))
        return None, None, page if keep_open else None
    png = _save_qr(src, account)
    print(f"[login] >>> 二维码: {os.path.basename(png)} <<<")
    print("[login] 用快手App / 快手极速版 → 侧边栏 → 扫一扫")

    last_b64 = ""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            # QR 过期刷新: 重存最新
            cur = _wait_qr(page, timeout=1)
            if cur and cur != last_b64:
                last_b64 = cur
                _save_qr(cur, account)
            # 实时 cookie (内存) + UI 双判定
            cookies = live_cookies(page)
            logged = is_logged_in(cookies) and page_logged_in(page)
        except Exception as e:
            # WS 瞬断/页面重载 — 不崩, 继续轮询
            cookies, logged = [], False
        if logged:
            el = int(time.time() - t0)
            print(f"[login] OK 登录成功 ({el}s)")
            time.sleep(2)
            info = _fetch_user_info(page)
            register_account(account, info, cookies)
            cp = os.path.join(os.path.dirname(user_dir), account + ".cookie.txt")
            print(f"[login] cookie -> {cp}")
            if not keep_open:
                try:
                    page.quit()
                except Exception:
                    pass
                page = None
            return info, cp, page
        time.sleep(1.5)

    print("[login] 超时未登录")
    if not keep_open:
        try:
            page.quit()
        except Exception:
            pass
        page = None
    return None, None, page


def main():
    acc = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "default"
    headless = "--headless" in sys.argv
    timeout = 240
    for a in sys.argv:
        if a.startswith("--timeout="):
            timeout = int(a.split("=")[1])
    info, cp, _ = login_qr(acc, timeout=timeout, headless=headless)
    if info:
        print(json.dumps(info, ensure_ascii=False, indent=2)[:2500])
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
