# ai-reverse

抖音 / 快手 Web 接口签名纯算逆向。

两个平台的请求签名都已脱离浏览器独立实现：**无浏览器、无自动化、无握手、纯本地计算**。

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

## 会话输入（不随仓库分发）

签名本身零网络，但 URL 里要携带会话字段，放在仓库外：

- `douyin/pure/run/cookie.txt` — 抖音完整 Cookie 行（模板见 `.example`）
- `douyin/pure/local/session.secrets.json` — 设备指纹（模板见 `.example`）
- `kuaishou/pure/run/cookie.txt` — 快手 Cookie（模板见 `.example`）

## 风险提示

- 设备指纹 + IP 一致性：换机器/IP 段可能触发风控（2483 或空 data），住宅 IP 最稳
- cookie 里的 `sessionid`/`msToken` 服务端会轮转，长期使用需定期刷新
- SDK 字节码版本轮换后需重新下载对应 JS 文件
