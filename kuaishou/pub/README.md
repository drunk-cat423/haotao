# 快手账号工具 (ruyipage 指纹浏览器驱动)

扫码登录 + 用户信息登记 + 视频发布。基于定制 Firefox 内核 + ruyipage
(`E:\parttime-job\douyin\ruyipage-with-browser`), 登录态存于每账号
独立 firefox profile, cookie 可导出给纯算签名器 (`../pure/ks_pure.py`) 共用。

## 用法

```bash
cd E:\parttime-job\kuaishou\pub

# 1. 扫码登录 (弹出指纹浏览器 → 存二维码 → 手机快手App扫)
python ks.py login acc1
# 终端提示 ">>> qrcode_acc1.png <<<", 用快手App侧边栏扫一扫

# 2. 看登记账号
python ks.py accounts

# 3. 发视频
python ks.py publish acc1 D:\videos\x.mp4 "标题" "描述 #话题"
python ks.py publish acc1 D:\videos\x.mp4 "标题" --dry-run   # 跑到发布前停, 截图确认
# 未登录会自动弹二维码, 扫后继续

# 4. 把账号 cookie 导给纯算搜索
python ks.py cookie acc1
# -> ../pure/run/cookie.txt, ks_pure.py 直接用
```

## 文件

| 文件 | 作用 |
|---|---|
| `ks.py` | 统一 CLI 入口 |
| `ks_common.py` | 浏览器启动 / cookie读写 / 登录判定 / tab切换 |
| `ks_login.py` | 扫码登录 + 用户信息抓取 + accounts.json 登记 |
| `ks_publish.py` | 视频发布 (上传作品 → setFiles → 填信息 → 发布) |
| `ks_userinfo.py` | 单独重抓用户信息 |
| `profiles/<acc>/` | 每账号 firefox profile (登录态持久化) |
| `profiles/<acc>.cookie.txt` | 导出 cookie |
| `accounts.json` | 账号登记表 |
| `qrcode_<acc>.png` | 最近二维码 (自动刷新) |
| `pub_debug_<acc>.png` | 发布失败调试截图 |

## 设计要点

- **登录判定以 UI 为准** (`page_logged_in`): sqlite 里的 cookie 可能服务端已
  过期, 页面有无头像/登录按钮才是真相
- **轮询用 `page.get_cookies()`** 实时读内存 cookie —— Firefox 运行期不落
  cookies.sqlite, 读文件永远慢一拍
- **发布全程可信输入**: `ele.click()`/`ele.input()` 走 BiDi 真事件
  (isTrusted=true), JS `.click()` 快手不认
- **上传直达 URL**: `cp.kuaishou.com/article/publish/video?origin=www.kuaishou.com`
  (主页'上传作品'是 isNewPage 跨域链接, 直接 `page.get()` 比点击稳)
- **文件上传**: `ele('css:input[type=file]').input(path)` → BiDi
  `input.setFiles`, 无文件对话框
- **编辑器是 ant-design**: 描述框 `contenteditable._description_*`,
  `ele.input()` 走 BiDi 真键盘逐字输入, 实测填入成功
- **发布按钮精确匹配**: `xpath://button[text()='发布']` —— 页上还有
  '发布作品'(侧栏)/'发布取消'(合并节点), `text:` 模糊定位会误点

## 依赖

- 定制 Firefox: `E:\parttime-job\douyin\ruyipage-with-browser\firefox-*\firefox\firefox.exe`
- ruyipage: `E:\parttime-job\douyin\ruyipage-with-browser\ruyipage`
- 指纹文件: `ruyipage/profile1.txt` (UA/canvas/WebGL/时区整套画像)

## 注意

- `profiles/`, `accounts.json`, `qrcode_*.png` 是运行时产物, 别进 git
- 多账号: 每个账号一个 profile + 可选 `--proxy`(launch 支持 set_proxy)
- 发布风控: 单账号日发有上限, 连续发会被要求验证 — 间隔几分钟
