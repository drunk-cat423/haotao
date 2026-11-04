# -*- coding: utf-8 -*-
"""共用工具: ruyipage 指纹浏览器启动 / cookie 导出导入 / profile 管理"""
import json
import os
import sys
import time
import sqlite3
import shutil
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
KS_ROOT = os.path.dirname(BASE)                      # E:\parttime-job\kuaishou
PJ_ROOT = os.path.dirname(KS_ROOT)                   # E:\parttime-job
RUYI = os.path.join(PJ_ROOT, "douyin", "ruyipage-with-browser", "ruyipage")
sys.path.insert(0, RUYI)

DEFAULT_FIREFOX = os.path.join(
    PJ_ROOT, "douyin", "ruyipage-with-browser",
    "firefox-155.0a1.en-US.win64-20260803", "firefox", "firefox.exe")
DEFAULT_FPFILE = os.path.join(RUYI, "profile1.txt")

PROFILES_DIR = os.path.join(BASE, "profiles")        # 每账号一个 firefox profile
ACCOUNTS_FILE = os.path.join(BASE, "accounts.json")
CONFIG_DIR = os.path.join(BASE, "..", "pure", "run")  # 现有纯算读取位置

os.makedirs(PROFILES_DIR, exist_ok=True)


def launch(profile_name="default", headless=False, proxy=None):
    """起一个指纹浏览器实例. 返回 (FirefoxPage, user_dir)."""
    from ruyipage import FirefoxOptions, FirefoxPage

    user_dir = os.path.join(PROFILES_DIR, profile_name)
    os.makedirs(user_dir, exist_ok=True)

    # 上次没干净退出会留 parent.lock -> 连接失败; 无 firefox 进程时清掉
    lock = os.path.join(user_dir, "parent.lock")
    if os.path.exists(lock):
        try:
            os.remove(lock)
        except OSError:
            pass

    opts = FirefoxOptions()
    opts.set_browser_path(DEFAULT_FIREFOX)
    opts.set_fpfile(DEFAULT_FPFILE)
    opts.set_user_dir(user_dir)
    opts.set_auto_port(True)
    opts.allow_system_access(True)
    opts.headless(headless)
    if proxy:
        opts.set_proxy(proxy)

    return FirefoxPage(opts), user_dir


# ---------- cookie 导入导出 ----------

def dump_cookies_sqlite(user_dir, domain="kuaishou.com"):
    """从 firefox profile 读 cookies.sqlite -> [{name,value,domain,path,secure,expiry}]"""
    src = os.path.join(user_dir, "cookies.sqlite")
    if not os.path.exists(src):
        return []
    tmp = tempfile.mktemp(suffix=".sqlite")
    shutil.copy(src, tmp)
    try:
        con = sqlite3.connect(tmp)
        rows = con.execute(
            "SELECT name, value, host, path, isSecure, expiry FROM moz_cookies WHERE host LIKE ?",
            (f"%{domain}%",)).fetchall()
        con.close()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return [{"name": n, "value": v, "domain": h, "path": p,
             "secure": bool(s), "expiry": e} for n, v, h, p, s, e in rows]


def cookie_header(cookies):
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


def save_cookie_txt(cookies, path):
    open(path, "w", encoding="utf-8").write(cookie_header(cookies))


def load_cookie_txt(path):
    c = open(path, encoding="utf-8").read().strip()
    out = []
    for part in c.split(";"):
        if "=" in part:
            n, v = part.strip().split("=", 1)
            out.append({"name": n, "value": v})
    return out


def is_logged_in(cookies):
    """快手登录态判定: kuaishou.server.webday7_st 存在即登录.
    注意: 只代表本地有该 cookie, 服务端可能已过期 — 权威判定用 page_logged_in."""
    names = {c["name"] for c in cookies}
    return any(n.startswith("kuaishou.server.webday7_st") or n == "webday7_st"
               or n.startswith("kuaishou.server.web") and n.endswith("_st")
               for n in names)


def live_cookies(page, domain="kuaishou.com"):
    """BiDi 实时读 cookie (Firefox 运行期不落 sqlite, 必须走这个).
    get_cookies 返回 CookieInfo 对象, 兼容 dict/属性两种取法."""
    try:
        raw = page.get_cookies(all_info=True) or []
    except Exception:
        return []
    out = []
    for c in raw:
        if isinstance(c, dict):
            d = c
        else:
            d = {"name": getattr(c, "name", ""),
                 "value": getattr(c, "value", ""),
                 "domain": getattr(c, "domain", "") or "",
                 "path": getattr(c, "path", "/"),
                 "expiry": getattr(c, "expiry", 0) or getattr(c, "expires", 0) or 0}
            v = d["value"]
            if isinstance(v, dict):
                d["value"] = v.get("value", "")
        if domain in (d.get("domain") or ""):
            out.append(d)
    return out


JS_LOGGED_IN = r"""
(() => {
  // 已登录: 头像/用户菜单存在 且 无'立即登录'按钮
  const hasAvatar = !!document.querySelector(
    '[class*=avatar] img, img[class*=avatar], [class*=user-info] img, '
    + '[class*=Avatar] img');
  let hasLoginBtn = false;
  for (const e of document.querySelectorAll('.sidebar-login-button, [class*=login-btn], span, button')) {
    const t = (e.textContent || '').trim();
    const r = e.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && (t === '立即登录' || t === '登录')) {
      hasLoginBtn = true; break;
    }
  }
  return {avatar: hasAvatar, loginBtn: hasLoginBtn};
})()
"""


def page_logged_in(page):
    """页面UI权威判定登录态 (cookie 可能服务端过期, 以UI为准)."""
    try:
        r = page.run_js(JS_LOGGED_IN, as_expr=True) or {}
        return bool(r.get("avatar")) and not r.get("loginBtn")
    except Exception:
        return False


def bind_context(page, context_id):
    """把 page 重绑到另一个 browsingContext (新tab)."""
    page._context_id = context_id
    return page


def list_contexts(page):
    """[{context, url}] 顶层 tab 列表."""
    try:
        tree = page.contexts.get_tree(max_depth=0)
        return [{"context": c.context, "url": c.url} for c in tree.contexts]
    except Exception:
        return []


UPLOAD_URL = "https://cp.kuaishou.com/article/publish/video?origin=www.kuaishou.com"


def goto_upload(page):
    """直达上传页 (比点按钮稳 — '上传作品'是 isNewPage 跨域链接, 直接get同域跳)."""
    page.get(UPLOAD_URL)
    return True


def click_upload(page):
    """可信输入点'上传作品' (备用路径, 会开新tab)."""
    for loc in ("text:上传作品",
                "xpath://div[contains(@class,'button')]//div[text()='上传作品']",
                "xpath://*[contains(text(),'上传作品')]"):
        try:
            e = page.ele(loc, timeout=3)
            if e and getattr(e, "click", None):
                e.click()
                return True
        except Exception:
            continue
    return False


def switch_to_new_tab(page, before_ids, timeout=10):
    """等新 tab 出现并重绑过去. 返回新 context_id 或 None."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        for c in list_contexts(page):
            if c["context"] not in before_ids:
                bind_context(page, c["context"])
                return c["context"]
        time.sleep(0.6)
    return None


# ---------- 账号登记 ----------

def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        return json.load(open(ACCOUNTS_FILE, encoding="utf-8"))
    return []


def save_accounts(accs):
    json.dump(accs, open(ACCOUNTS_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


def register_account(profile_name, user_info, cookies):
    """把一个登录完成的账号写进 accounts.json."""
    accs = load_accounts()
    accs = [a for a in accs if a.get("profile") != profile_name]
    accs.append({
        "profile": profile_name,
        "user_info": user_info,
        "login_at": int(time.time()),
        "cookie_file": os.path.join(PROFILES_DIR, profile_name + ".cookie.txt"),
    })
    save_accounts(accs)
    save_cookie_txt(cookies, os.path.join(PROFILES_DIR, profile_name + ".cookie.txt"))
    return accs


def ua_from_fpfile(path=None):
    fp = path or DEFAULT_FPFILE
    if not os.path.exists(fp):
        return ""
    for line in open(fp, encoding="utf-8", errors="replace"):
        if line.strip().lower().startswith("useragent"):
            return line.split("=", 1)[1].strip()
    return ""
