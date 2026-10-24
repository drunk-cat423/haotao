# 抖音搜索纯算（无浏览器）

`a_bogus` / `msToken` / `uifid` / `webid` / `verifyFp` 全部在 **Node 本地 JSVM**
里算出，请求由 Python `curl_cffi` 模拟浏览器 TLS 指纹发出。
**运行时零浏览器参与。**

## 架构

```
Python dy_pure.py
   │  stdin/stdout JSON-lines
   ▼
Node dy_signer.js (常驻守护)
   │  createSigner() 补浏览器环境 (navigator/document/canvas/storage...)
   │  加载 run/ 下全套 SDK 本地文件:
   │    sdk-glue.js → webmssdk.es5.js (JSVM HNOJ@?RC 字节码)
   │    → secsdk-lastest.umd.js → runtime.js/runtime-stable.js
   │    → config_90/project_90/strategy_90 → bdms.js (路径策略 VM)
   │  预热: /web/common + /web/r/token (真网络, 换动态 msToken)
   │  签名: XHR.send 注入 → 字节码程序在 URL 追加 a_bogus+msToken+uifid
   ▼
curl_cffi (chrome131 TLS 指纹) → douyin.com
```

## 文件

| 文件 | 作用 |
|---|---|
| `dy_pure.py` | Python 客户端入口 (CLI + 库) |
| `run/dy_signer.js` | Node 签名守护进程 |
| `run/douyin_search_node.js` | 补环境+SDK加载+预热+签名 核心 (4354行) |
| `run/*.js` | 抖音官方 SDK 本地副本 (1.0.0.53 webmssdk 等) |
| `run/cookie.txt` | douyin.com 完整 Cookie 行 (**必需, 定期更换**) |
| `local/session.secrets.json` | 设备/浏览器画像参数 |

## 用法

```bash
pip install curl_cffi          # Python 依赖
node --version                  # 需要 >=18

python dy_pure.py search 篮球            # 一页10条 (显示标题+页面链接+下载直链)
python dy_pure.py search 篮球 -n 20      # 翻页 (search_id 自动链)
python dy_pure.py search 篮球 -n 20 -o out.json
python dy_pure.py download out.json ./videos   # 批量下载 MP4 (优先HD码率)
python dy_pure.py sign "<未签名URL>"      # 只签名
```

```python
from dy_pure import DouyinPure
with DouyinPure() as c:
    items, raws = c.search("篮球", pages=2)
    url = c.sign("https://www.douyin.com/aweme/v1/web/xx/?a=1")
```

## Cookie 获取 (唯一外部输入)

1. 任意浏览器登录 https://www.douyin.com/
2. DevTools → Network → 任一发往 www.douyin.com 的请求 → 复制完整 `Cookie` 头
3. 整行粘贴到 `run/cookie.txt`

Cookie 失效表现: 搜索返回 `status_code:0` 但 `data:[]`、`has_more:0`,
或 `status_code:2483`, 或 `x-vc-bdturing-parameters` 头 → 换新 Cookie.

## 反爬注意事项

- **请求频率**: 连续高频搜索会被软封 (`data:[]` 空结果). 脚本内置 1.5s
  页间隔 + 空结果重试一次. 批量跑建议间隔 5s+.
- **TLS 指纹**: 默认 `chrome131`, 在 `DouyinPure(impersonate=...)` 可换
  (支持 chrome120/131/136/146, firefox133/144).
- **UA 与 Cookie 设备一致性**: cookie.txt 若来自 Chrome, secrets 画像应保
  持 Chrome; 不要混用 Firefox cookie + Chrome 画像 (会触发 bdturing 验证).
- **msToken 轮换**: 每次签名后 daemon 返回最新 msToken, 客户端自动写入
  cookie jar, 无需手工同步.

## 环境参数 (`local/session.secrets.json`)

| 字段 | 说明 |
|---|---|
| `ua` / `sec_ch_ua` | 必须与 cookie 来源浏览器一致 (Chrome 138 默认) |
| `uifid` | UIFID cookie 值 (cookie.txt 里有, init 会自动覆盖) |
| `webid` | 设备 web id (ttwid 派生) |
| `verify_fp`/`fp` | `s_v_web_id` cookie 值 (init 自动覆盖) |
| `endpoint` | `general`(综合/视频) 或 `discover`(用户) |
| `screen_*`/`cpu_core_num`/`device_memory` | 设备画像, 与 UA 匹配即可 |

## 已验证

- `a_bogus` 长度 184~196, `msToken` 172 —— 与浏览器同型
- `general/search/single`: `status_code:0` + 真实视频条目
- `discover/search` (用户搜索): 签名可生成但该端点风控更严, 易出
  `x-vc-bdturing-parameters` 滑块挑战 —— 建议用 general.

## 限制

- 仍是"补环境跑官方 JSVM"的纯算, 不是把 a_bogus 算法翻译成 Python.
  SDK 版本更新 (字节码轮换) 时, 重新下载对应 JS 文件即可, 补环境层大概率
  仍兼容 (文件头部有版本号, 见 `run/webmssdk.es5.js` 第一行 `1.0.0.53`).
- 预热走真网络: `/web/common` + `/web/r/token` 每次启动守护进程各一次,
  签名本身完全离线.
