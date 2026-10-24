# ai-reverse-pure — 快速上手

抖音 + 快手 Web 接口签名**纯算**实现。无浏览器、无自动化、无握手、纯本地计算。

## 一键验证

```bash
pip install -r requirements.txt    # curl_cffi
python check_env.py                # 环境自检
```

## 配置凭证（只需一次）

**方式 A — 自动提取（推荐）**：浏览器已登录的情况下，一条命令搞定全部配置

```bash
# Firefox/指纹浏览器: cookie 在 profile/cookies.sqlite 明文, 直接读
python extract_creds.py --douyin-profile <抖音profile目录> \
                        --kuaishou-profile <快手profile目录> \
                        --fp-file <指纹文件(可选, 提取UA)>

# 自动探测模式: profile 放本目录或上级目录 (名字含 douyin/kuaishou/ks) 即可
python extract_creds.py
```

自动解出: cookie 全量 / uifid / webid(从 web_sign_token JWT) / verifyFp / fp / msToken / ua

**方式 B — 手动**：`config/` 下 `.example` 复制成无后缀版填真实值

| 文件 | 填什么 |
|---|---|
| `config/douyin.cookie.txt` | 浏览器登 douyin.com → F12 → 任一 douyin 请求 → `Cookie:` 整行（单行） |
| `config/session.secrets.json` | 设备指纹：`ua/uifid/webid/verify_fp/fp`（example 里有占位符结构；uifid/verifyFp/fp/webid 从请求 URL 参数里抠） |
| `config/kuaishou.cookie.txt` | 同上，kuaishou.com 的 Cookie 行 |

## 跑 demo

```bash
python demo.py 篮球          # 抖音3条 + 快手3条
python demo.py 足球
```

## 直接调用

```bash
# 抖音
cd douyin
python dy_abogus.py search 篮球 -n 24 -o out.json   # 搜2页存JSON (含视频直链/封面)
python dy_abogus.py download out.json ./videos      # 批量下MP4
python dy_abogus.py sign '<URL>'                    # 只签名
node dy_abogus_signer.js search 篮球 0 12           # Node 签名器直出URL
node dy_abogus_signer.js                            # 守护模式 stdin/stdout

# 快手
cd kuaishou
python ks_pure.py search 篮球 -n 40 -o out.json     # 搜索40条 (pcursor翻页)
python ks_pure.py download out.json ./videos
python test_replay.py                               # 重放验证
```

## Python 库调用

```python
sys.path.insert(0, "douyin");  from dy_abogus import DouyinPure
sys.path.insert(0, "kuaishou"); from ks_pure import KuaishouPure

with DouyinPure() as c:
    items, raws = c.search("篮球", pages=2)

c = KuaishouPure()
feeds, raws = c.search("篮球", pages=2)
```

## 技术要点

| | 抖音 a_bogus | 快手 __NS_hxfalcon |
|---|---|---|
| 签名实体 | bdms.js 内置 JSVM（程序105/107 hook XHR） | bundle 明文算法函数 |
| 算法核心 | SM3 + 自定义编码 | ChaCha20 + 魔改BLAKE2s + 自研LFSR |
| 预热/握手 | **无** | **无** |
| 启动延迟 | ~2s init | ~1s |
| 单次签名 | ~50ms | ~1ms |

## 风险

- cookie 里的 `sessionid`/`msToken` 服务端轮转，长期使用定期刷新
- 换 IP 段可能触发风控（2483/空 data）——住宅 IP 最稳
- SDK 版本轮换 → 重下对应 JS 文件即可
