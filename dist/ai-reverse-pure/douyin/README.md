# 抖音 a_bogus —— 真·纯算实现

**已验证**: `status_code: 0` + 真实搜索数据, 翻页正常, 无浏览器/无握手/无网络签名依赖.

## 架构

```
Python dy_abogus.py
   └── node dy_abogus_signer.js   (常驻守护, stdin/stdout)
          └── vm.runInContext(bdms.js, 环境桩沙箱)
                 └── JSVM 解释器 d + ~796 个程序
                        └── 程序 105/107 (XHR open/send hook)
                               └── a_bogus 计算 + append
```

## 关键事实

- `a_bogus` 由 **`bdms.js` 的 JSVM 程序**计算, 不是 webmssdk/secsdk.
  链路: `XHR.open/send → bdms hook(程序107) → 内部 append a_bogus`.
- `bdms.init({aid, pageId, paths, boe, ddrt, ic})` — `paths` 白名单
  决定哪些 URL 会被签名 (`^/aweme/v1/` 覆盖搜索端点).
- 计算是纯本地的 — 之前的 `/web/common` + `/web/r/token` 握手
  是 **webmssdk 层**的需求(msToken/状态机), bdms 不需要.
- bdms 内含明文 SM3 实现(`gr` 类) — a_bogus 摘要用 SM3 系.
- 单次签名 ~50ms, 常驻进程可反复签.

## 文件

| 文件 | 用途 |
|---|---|
| `bdms.js` | 官方 bdms SDK (147KB, 含 VM+程序包) — 从 `pure/run/bdms.js` 拷来 |
| `dy_abogus_signer.js` | Node 签名器 — 加载 bdms + 假 XHR + init |
| `dy_abogus.py` | Python 客户端 — 搜索/翻页/下载 |
| `bdms_dbg.js` | 带插桩的 bdms (程序调用日志) — 调试用 |

## 用法

```bash
pip install curl_cffi
node dy_abogus_signer.js search 篮球 0 12        # 签一条搜索URL
node dy_abogus_signer.js                         # 守护模式 (stdin一行一个URL)
python dy_abogus.py search 篮球 -n 24 -o out.json
python dy_abogus.py download out.json ./videos
python dy_abogus.py sign '<URL>'
```

## 需要的输入 (静态会话值)

- `../pure/local/session.secrets.json` — `ua/webid/uifid/verifyFp/fp`
- `../pure/run/cookie.txt` — 完整 cookie (从中取 `msToken`)

签名本身零网络; 只有 `curl_cffi` 请求时才出网.

## 与旧版对比

| | 旧 (env-shim) | 新 (bdms 独立) |
|---|---|---|
| 签名实体 | webmssdk+secsdk+project_90+strategy+runtime 全套 | **只 bdms.js** |
| 握手 | 每次启动 2 次 (`/web/common`, `/web/r/token`) | **零** |
| 启动延迟 | ~12s 预热 | ~2s init |
| 环境桩 | 完整 DOM/事件/存储 | 最小桩 (~60行) |
| 稳定性 | 字节码版本轮换敏感 | 同样敏感, 但单文件好维护 |

## 待办

- [ ] `discover/search` 端点签名验证 (当前 `paths` 已含 `^/aweme/v1/` 应该通吃)
- [ ] a_bogus 程序 (107/689) 字节码级提取 — 去掉整文件依赖 (可选)
- [ ] Python 原生移植 (SM3+编码器直译, 彻底去 Node) — 工作量大
