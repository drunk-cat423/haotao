# -*- coding: utf-8 -*-
"""
快手视频发布 —— 已登录 profile + ruyipage 指纹浏览器驱动上传.

用法:
    python ks_publish.py <账号名> <视频路径> [标题] [描述]
    python ks_publish.py acc1 D:\\v.mp4 "标题" "描述 #话题"

流程: 主页 → UI判登录(未登录自动出二维码) → 可信点'上传作品' →
      处理新tab/同页跳 → 文件input.setFiles → 填标题/描述 → 可信点发布 → 验证
"""
import os
import sys
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ks_common import (launch, page_logged_in, live_cookies, is_logged_in,
                       click_upload, list_contexts, bind_context,
                       switch_to_new_tab, BASE)


def _fill_field(page, locators, text):
    """可信输入填字段. locators 为候选定位列表."""
    for loc in locators:
        try:
            e = page.ele(loc, timeout=3)
            if e:
                e.input(text)
                return loc
        except Exception:
            continue
    return None


def _click_text(page, texts):
    """可信点击指定文本的按钮 (精确文本匹配, 避免'发布'命中'发布作品/发布取消')."""
    for t in texts:
        for loc in (
            f"xpath://button[normalize-space(text())='{t}']",
            f"xpath://*[@role='button'][normalize-space(text())='{t}']",
            f"xpath://div[contains(@class,'btn')][normalize-space(text())='{t}']",
            f"xpath://span[normalize-space(text())='{t}']",
            f"xpath://*[normalize-space(text())='{t}' and not(*)]",
        ):
            try:
                e = page.ele(loc, timeout=3)
                if e:
                    e.click()
                    return t
            except Exception:
                continue
    return None


def publish(account, video_path, title="", desc="", qr_timeout=240,
            dry_run=False):
    """发布视频主流程. dry_run=True 全流程跑到发布前停下(截图确认). 返回 True/False."""
    video_path = os.path.abspath(video_path)
    if not os.path.exists(video_path):
        print("[pub] 视频不存在:", video_path)
        return False

    page, user_dir = launch(account, headless=False)
    print(f"[pub] profile: {user_dir}")
    page.get("https://www.kuaishou.com/")
    time.sleep(4)

    # UI 权威判登录; 未登录 → 内联扫码
    if not page_logged_in(page):
        print("[pub] 未登录 — 出二维码 (快手App扫)")
        from ks_login import _click_login, _wait_qr, _save_qr, _fetch_user_info
        from ks_common import register_account
        _click_login(page)
        time.sleep(3)
        src = _wait_qr(page)
        if not src:
            print("[pub] 未拿到二维码")
            page.screenshot(path=os.path.join(BASE, f"pub_debug_{account}.png"))
            return False
        png = _save_qr(src, account)
        print(f"[pub] >>> 二维码: {os.path.basename(png)} <<< 扫后自动继续")
        t0 = time.time()
        ok = False
        while time.time() - t0 < qr_timeout:
            cur = _wait_qr(page, timeout=1)
            if cur:
                _save_qr(cur, account)
            if is_logged_in(live_cookies(page)) and page_logged_in(page):
                ok = True
                break
            time.sleep(1.5)
        if not ok:
            print("[pub] 扫码超时")
            return False
        info = _fetch_user_info(page)
        register_account(account, info, live_cookies(page))
        print("[pub] 登录完成, 继续发布")
        time.sleep(2)

    # 直达上传页 (isNewPage跨域链接, get比点击稳)
    from ks_common import goto_upload
    goto_upload(page)
    print("[pub] 打开上传页...")
    time.sleep(6)
    print("[pub] url:", page.url)

    # 等 file input
    t0 = time.time()
    found = False
    while time.time() - t0 < 25:
        found = page.run_js(
            "!!document.querySelector('input[type=file]')", as_expr=True)
        if found:
            break
        time.sleep(1)
    if not found:
        print("[pub] 没等到文件输入框 — 截图存 debug")
        page.screenshot(path=os.path.join(BASE, f"pub_debug_{account}.png"))
        return False

    # 上传文件 (BiDi input.setFiles)
    fe = page.ele("css:input[type=file]", timeout=8)
    fe.input(video_path)
    print("[pub] 文件已设置, 等解析上传...")

    # 等编辑器出现 (描述框 class _description_*)
    t0 = time.time()
    desc_ready = False
    while time.time() - t0 < 60:
        desc_ready = page.run_js(
            "!!document.querySelector('[contenteditable=true][class*=_description],"
            "[contenteditable=true][data-placeholder]')",
            as_expr=True)
        if desc_ready:
            break
        time.sleep(1.5)
    if not desc_ready:
        print("[pub] 编辑器没出来 — 截图存 debug")
        page.screenshot(path=os.path.join(BASE, f"pub_debug_{account}.png"))
        return False
    print("[pub] 编辑器就绪")

    # 快手主字段是"作品描述" (contenteditable, 标题走描述第一行)
    caption = desc or title or os.path.splitext(os.path.basename(video_path))[0]
    d_loc = _fill_field(page, (
        "css:[contenteditable=true][class*=_description]",
        "css:[contenteditable=true][data-placeholder]",
        "css:[contenteditable=true]",
    ), caption)
    print("[pub] 描述框:", d_loc)
    if not d_loc:
        print("[pub] 描述框填写失败")
        page.screenshot(path=os.path.join(BASE, f"pub_debug_{account}.png"))
        return False
    time.sleep(2)

    # 若有'下一步'(分步向导)先点; 发布按钮精确匹配文本'发布'
    nxt = _click_text(page, ("下一步",))
    if nxt:
        print("[pub] 点了'下一步'")
        time.sleep(3)
    if dry_run:
        print("[pub] dry-run: 停在发布前, 截图确认")
        page.screenshot(path=os.path.join(BASE, f"pub_ready_{account}.png"))
        _dump_state(page, account, "ready")
        return True
    # 主发布按钮: <div class="_button_*_1 _button-primary_*_60">发布</div>
    # 视频处理完才渲染 + 在视口外 — 等出现→滚动进视口→点 (最多90s)
    hit = None
    t0 = time.time()
    while time.time() - t0 < 90 and not hit:
        for loc in ("css:div[class*=_button-primary]",
                    "xpath://div[contains(@class,'_button-primary')]"):
            try:
                e = page.ele(loc, timeout=2)
                if not (e and getattr(e, "click", None)):
                    continue
                # 按钮在 fixed/内滚容器 — window滚不动, 拉高窗口让它进视口
                try:
                    page.set_window_size(1400, 1700)
                    time.sleep(1)
                except Exception:
                    pass
                in_view = page.run_js(r"""
                (() => {
                  const el = document.querySelector('div[class*=_button-primary]');
                  if (!el) return false;
                  const r = el.getBoundingClientRect();
                  return r.top >= 0 && r.bottom <= innerHeight;
                })()
                """, as_expr=True)
                print(f"[pub] 按钮在视口内: {in_view}")
                if in_view:
                    e.click()
                else:
                    # 兜底: JS合成点击 (React div onClick 不要求 trusted)
                    e._run_safe("(el)=>el.click()")
                hit = loc
                break
            except Exception as ex:
                print(f"[pub] 点击异常: {str(ex)[:80]}")
        if not hit:
            time.sleep(2)
    print("[pub] 发布按钮:", hit)
    if not hit:
        page.screenshot(path=os.path.join(BASE, f"pub_debug_{account}.png"))
        return False

    # 等结果: 成功提示 / URL 跳转 / 作品链接出现
    t0 = time.time()
    result_url, ok, link = None, False, None
    while time.time() - t0 < 45:
        try:
            st = page.run_js(r"""
            (() => {
              const t = document.body.innerText || '';
              const ok = /发布成功|已发布|上传成功|审核中|发布完成/.test(t);
              // 作品链接: a[href*=short-video] / a[href*=photo] / 成功页上的链接
              let link = null;
              for (const a of document.querySelectorAll('a[href]')) {
                const h = a.href || '';
                if (/short-video|\/photo\/|workId|photoId/.test(h)) { link = h; break; }
              }
              return {ok, link, url: location.href};
            })()
            """, as_expr=True) or {}
            ok = bool(st.get("ok"))
            link = st.get("link")
            result_url = st.get("url")
            if ok or link:
                break
        except Exception:
            pass
        time.sleep(1.5)
    print(f"[pub] 成功提示: {ok} | url: {result_url} | link: {link}")
    # 兜底: 成功但没拿到链接 → 去内容管理页抓最新作品
    if ok and not link:
        link = _get_latest_work_link(page)
        print(f"[pub] 内容管理兜底: {link}")
    _dump_state(page, account, "done",
                extra={"ok": ok, "link": link, "url": result_url})
    page.screenshot(path=os.path.join(BASE, f"pub_done_{account}.png"))
    try:
        page.quit()
    except Exception:
        pass
    return bool(ok or link)


def _get_latest_work_link(page):
    """内容管理页抓最新作品链接."""
    try:
        page.get("https://cp.kuaishou.com/article/manage/video")
        time.sleep(6)
        return page.run_js(r"""
        (() => {
          for (const a of document.querySelectorAll('a[href]')) {
            const h = a.href || '';
            if (/short-video|\/photo\/|workId|photoId|article\/detail/.test(h))
              return h;
          }
          return null;
        })()
        """, as_expr=True)
    except Exception:
        return None


def _dump_state(page, account, stage, extra=None):
    """留存调试中间参数 -> pub_state_<acc>.json (追加阶段记录)."""
    import json
    path = os.path.join(BASE, f"pub_state_{account}.json")
    rec = {"stage": stage, "ts": int(time.time())}
    try:
        rec["url"] = page.url
    except Exception:
        pass
    try:
        rec["buttons"] = page.run_js(r"""
        (() => [...document.querySelectorAll('button,[class*=btn],[role=button]')]
          .map(e => (e.textContent||'').trim()).filter(t => t && t.length < 20)
          .slice(0, 40))()
        """, as_expr=True) or []
    except Exception:
        rec["buttons"] = []
    try:
        rec["fields"] = page.run_js(r"""
        (() => ({
          inputs: [...document.querySelectorAll('input')].map(
            e => ({type: e.type, ph: e.placeholder||''})),
          ce: [...document.querySelectorAll('[contenteditable=true]')].map(
            e => String(e.className).slice(0, 60)),
          textarea: [...document.querySelectorAll('textarea')].map(
            e => e.placeholder || ''),
        }))()
        """, as_expr=True) or {}
    except Exception:
        rec["fields"] = {}
    if extra:
        rec.update(extra)
    old = []
    if os.path.exists(path):
        try:
            old = json.load(open(path, encoding="utf-8"))
        except Exception:
            old = []
    old.append(rec)
    json.dump(old, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"[dbg] state -> {path}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    acc = args[0] if len(args) > 0 else "default"
    video = args[1] if len(args) > 1 else ""
    title = args[2] if len(args) > 2 else ""
    desc = args[3] if len(args) > 3 else title
    if not video:
        print("用法: python ks_publish.py <账号> <视频.mp4> [标题] [描述] [--dry-run]")
        return
    ok = publish(acc, video, title, desc, dry_run="--dry-run" in sys.argv)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
