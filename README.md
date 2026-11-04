# ai-reverse

抖音 / 快手 / 知乎 Web 接口签名纯算逆向。

三个平台的请求签名都已脱离浏览器独立实现：**无浏览器、无自动化、无握手、纯本地计算**。

## 目录

```
douyin/
  abogus/          真·纯算签名器 (bdms.js 独立 JSVM, 推荐)
    bdms.js            官方 bdms SDK (含 JSVM 解释器 + ~796 个程序 + SM3)
    dy_abogus_signer.js Node 签名器 (常驻守护, stdin/stdout)
    dy_abogus.py        Python 客户端 (search/download/sign)
  pure/            旧版 env-shim 方案 (webmssdk+secsdk 全套, 已被 abogus 取代)
    dy_pure.py          Python 客户端 (需要完整 SDK 链, 仅供对照)
kuaishou/
  pure/            真·纯算签名器 (源码级算法函数直提)
    ks_sig_core.js      从 kuaishou bundle 切出的真实算法函数
    ks_sign.js          Node 签名器
    ks_pure.py          Python 客户端 (search/download/pcursor 翻页)
    test_replay.py      重放验证
zhihu/
  zh_sign.js       x-zse-96 纯算签名器 (heifetz m1514 JSVMP + m10261 MD5)
  zh_pure.py       Python 客户端 (login 扫码/search/sign)
```

## 抖音 `a_bogus`

签名主体不在 webmssdk，在 **`bdms.js`** 的自研 JSVM 里（程序 105/107 是 XHR open/send 钩子）：

- `bdms.init({aid, pageId, paths, boe, ddrt, ic})` — `paths` 白名单控制哪些 URL 被签名
- 单次签名 ~50ms，纯本地；之前的 `/web/common`+`/web/r/token` 握手是 webmssdk 层的需求，bdms 不需要
- 文件内含明文 SM3（`gr` 类）—— a_bogus 摘要是 SM3 系

```bash
cd douyin/abogus
pip install curl_cffi   # Node>=18 也要
python dy_abogus.py search 篮球 -n 24 -o out.json
python dy_abogus.py download out.json ./videos
```

## 快手 `__NS_hxfalcon`

格式 `HUDR_<设备指纹>$HE_<请求载荷>`：

- HUDR 段：`ChaCha20(固定key/iv)( TLV设备数据 XOR 0x23 )` → base64url
- HE 段：`hex( XOR链( 版本 + 时间戳 + 随机 + 计数 + tmsFn(BLAKE2s'(signInput)) ))`
- 算法函数是 bundle 明文 JS，直接切出来跑；确定性输出，无需预热

```bash
cd kuaishou/pure
python ks_pure.py search 篮球 -n 40 -o out.json
python ks_pure.py download out.json ./videos
```

## 快手账号工具 `kuaishou/pub`

指纹浏览器 + ruyipage 驱动的扫码登录 / 账号登记 / 视频发布（不是纯算——走定制内核真实浏览器）：

```bash
cd kuaishou/pub
python ks.py login acc1                       # 扫码登录 → accounts.json + cookie.txt
python ks.py accounts                          # 已登记账号
python ks.py publish acc1 D:\v.mp4 "标题" "描述 #话题"   # 发布 (--dry-run 先跑到发布前)
python ks.py cookie acc1                       # 导出 cookie 给 ../pure 纯算用
```

- 登录判定以页面 UI 为准（cookie 服务端可能过期）；轮询走 BiDi 实时 cookie（Firefox 运行期不落 sqlite）
- 上传直达 `cp.kuaishou.com/article/publish/video`，`input.setFiles` 传文件；描述框 contenteditable 用 BiDi 真键盘输入
- 需要 `browser/` 分片先重组出 ruyipage + 定制 Firefox；`ks_common.py` 里的路径按本地目录调整

## 知乎 `x-zse-96`

签名 = `"2.0_" + ZP(md5hex(source))`，`source=[zse93,path+search,d_c0,body≤4K,xZst81]` 用 `+` 拼接：

- `ZP` 是 heifetz `2878.app` 模块 1514 的自研 JSVMP（加载时装配 SM4 风格 S 盒/轮密钥表），扣出后在 Node 直跑
- `x-zst-81` 由 zswsdid SDK 产出（会话内恒定），服务端接受不带它的请求 —— 可省
- `search_v3` 需登录 `z_c0`（401 ZERR_NOT_LOGIN），扫码一次落 cookie.txt

```bash
cd zhihu
python zh_pure.py login            # 指纹浏览器扫码
python zh_pure.py search 篮球 -n 2
```

## 浏览器（分片存储）

`browser/` 下是指纹浏览器运行时的分片 zip（ruyipage + 定制 Firefox, 149MB 拆成 3×50MB）：

```bash
python browser/assemble_browser.py   # 拼回 ruyipage-with-browser.zip 并校验
# 解压后即是完整指纹浏览器, 用于登录/养号
```

**仅用于登录取凭证** — 签名本身不需要浏览器。

## 会话输入（不随仓库分发）

签名本身零网络，但 URL 里要携带会话字段，放在仓库外：

- `douyin/pure/run/cookie.txt` — 抖音完整 Cookie 行（模板见 `.example`）
- `douyin/pure/local/session.secrets.json` — 设备指纹（模板见 `.example`）
- `kuaishou/pure/run/cookie.txt` — 快手 Cookie（模板见 `.example`）

## 风险提示

- 设备指纹 + IP 一致性：换机器/IP 段可能触发风控（2483 或空 data），住宅 IP 最稳
- cookie 里的 `sessionid`/`msToken` 服务端会轮转，长期使用需定期刷新
- SDK 字节码版本轮换后需重新下载对应 JS 文件
