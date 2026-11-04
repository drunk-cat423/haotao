# -*- coding: utf-8 -*-
"""
快手用户信息获取 —— 登录态下抓取账号昵称/快手号/头像/UID,
写入 accounts.json 供发布账号登记.

用法:
    python ks_userinfo.py <账号名>          # 用已登录 profile 抓
"""
import json
import os
import sys
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ks_common import (launch, dump_cookies_sqlite, is_logged_in,
                       load_accounts, save_accounts, BASE)

# 页面内多源抓用户信息
JS_PROFILE = r"""
(async () => {
  const out = {};
  // 1) 顶部头像区
  const av = document.querySelector(
    'img[class*=avatar], .avatar img, [class*=Avatar] img, ' +
    '[class*=user-avatar] img, .user-info img');
  if (av) o = av.src && (out.avatar = av.src);
  // 2) 昵称
  for (const sel of ['[class*=nickname]','[class*=nick]','.user-name',
                      '[class*=user-info] [class*=name]','.sidebar-user [class*=name]']) {
    const e = document.querySelector(sel);
    const t = e && (e.textContent||'').trim();
    if (t && t.length < 30 && t.length > 0) { out.nickname = t; break; }
  }
  // 3) 快手号 — 页面常显示 "快手号: xxx"
  const all = [...document.querySelectorAll('*')]
    .map(e => (e.textContent||'').trim())
    .filter(t => /快手号|kwai|id[:：]/i.test(t) && t.length < 40);
  if (all.length) out.ksid_hint = all.slice(0, 3);
  // 4) localStorage uid
  for (let i=0;i<localStorage.length;i++){
    const k=localStorage.key(i), v=localStorage.getItem(k);
    if (/^(uid|userId|mid|user_id|viewer)$/i.test(k)) out['ls_'+k]=v;
    else if (/^(my_user|userInfo|self)$/i.test(k)) { try{out['ls_'+k]=JSON.parse(v)}catch(e){out['ls_'+k]=v} }
  }
  // 5) 接口兜底
  try {
    const r = await fetch('https://www.kuaishou.com/rest/v/uc/web/user/info',
                          {credentials:'include'}).then(r=>r.json());
    if (r && (r.userInfo || r.data)) out.api = r.userInfo || r.data;
  } catch(e){}
  return out;
})()
"""


def fetch_user_info(account):
    """用已登录 profile 抓用户信息."""
    page, user_dir = launch(account, headless=False)
    page.get("https://www.kuaishou.com/")
    time.sleep(5)

    cookies = dump_cookies_sqlite(user_dir)
    if not is_logged_in(cookies):
        print("[info] 未登录 — 先跑 ks_login.py")
        return None

    info = page.run_js(JS_PROFILE, as_expr=True) or {}

    # 补充: 点开头像/我的页面拿更多
    try:
        page.run_js(r"""
          (() => {
            const a = document.querySelector('[class*=avatar],[class*=Avatar],[class*=user]');
            if (a) a.click();
            return true;
          })()
        """, as_expr=True)
        time.sleep(2)
        # 再看 URL 是否带到 user/id
        u = page.url or ""
        import re
        m = re.search(r"/profile/([^/?]+)|/user/([^/?]+)|mid=(\d+)", u)
        if m:
            info["profile_url"] = u
            info["uid_from_url"] = next(g for g in m.groups() if g)
    except Exception:
        pass

    # 写回 accounts.json
    accs = load_accounts()
    for a in accs:
        if a.get("profile") == account:
            a["user_info"] = {**a.get("user_info", {}), **info}
            a["fetched_at"] = int(time.time())
    save_accounts(accs)
    try:
        page.quit()
    except Exception:
        pass
    return info


def main():
    acc = sys.argv[1] if len(sys.argv) > 1 else "default"
    info = fetch_user_info(acc)
    print(json.dumps(info or {}, ensure_ascii=False, indent=2)[:3000])


if __name__ == "__main__":
    main()
