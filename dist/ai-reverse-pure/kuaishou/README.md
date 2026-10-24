# 快手搜索纯算（真·纯算，无浏览器）

`__NS_hxfalcon` (sig4) 由**从站点 bundle 直接切出的真实算法函数**在 Node
本地运行生成 —— 不是补环境跑 JSVM，不需要预热握手，签名本身完全离线确定。

## 算法结构（已完整还原）

```
__NS_hxfalcon = "HUDR_" + deviceInfo + "$HE_" + payload
```

**输入打包** `we(t)`:
```
signInput = urlPath + sortedK=V拼接(去__NS前缀key) + JSON.stringify(requestBody)
           = "/rest/v/search/feed" + "caver=2keyword=篮球page=1..." 
```

**HUDR 段** (设备指纹, 基本恒定):
```
deviceInfo = base64url( ChaCha20_custom(key固定,iv固定) ( TLV设备数据 XOR 0x23 ) )
TLV = [45,61,0,2] + infoCache(脚本数等) + [112,0]+count(4B) 
      + [114,1]+SECS.s.len(2B)+SECS.s + [115,0]+SECS.c(4B)
SECS.s = 调用栈尾100字符 (反hook), SECS.c = 请求计数
```

**$HE_ 段** (请求载荷, 96 hex):
```
i  = "4B54" + He(43469,2B) + "ab" + He(startupRandom,6B) + He(rand48,6B)
   + "0100000000" + He(3131873467^cnt, 4B) + l + He(Date.now()^3360347992,6B)
   + f + Ke(f)
l  = hex(XOR( substr(hex(tmsFn(hex32(blake2s'(signInput+deviceInfo)))),0,8), [45,211,69,192] ))
f  = hex(XOR("e0000000000000", [123,86,62,218]))
blake2s' = 魔改BLAKE2s (自定义IV, 无key, 10轮σ)
tmsFn    = 自研LFSR流密码 (48字节状态种子 + "X{t:hMFv`?MA"混入)
Ke       = 校验字节 (sum, 补码)
最终      = hex( 每字节 XOR 链: out[j]=n[j]^n[last], out[last]=n[last] )
```

## 文件

| 文件 | 作用 |
|---|---|
| `ks_pure.py` | Python 客户端 (CLI + 库) |
| `ks_sign.js` | Node 签名器 (加载 core + env stubs) |
| `ks_sig_core.js` | **从 kuaishou bundle 切出的真实算法函数** (17.5KB) |
| `run/cookie.txt` | kuaishou.com Cookie (必需) |
| `captures/` | 抓包原始数据 |
| `../captures/ks_js/` | 站点 JS 落盘 (分析源) |

## 用法

```bash
python ks_pure.py search 篮球             # 一页 ~20条
python ks_pure.py search 篮球 -n 40       # 翻页 (pcursor链)
python ks_pure.py search 篮球 -n 40 -o out.json
python ks_pure.py download out.json ./videos   # 批量下载MP4
python ks_pure.py sign /rest/v/search/feed '{"keyword":"篮球","page":1}'
```

```python
from ks_pure import KuaishouPure
with KuaishouPure() as c:
    feeds, raws = c.search("篮球", pages=2)
    url, info = c.signed_url("/rest/v/search/feed",
                           {"keyword":"篮球","page":1})
```

## Cookie 获取

浏览器登录 https://www.kuaishou.com → DevTools Network → 任意
`www.kuaishou.com` 请求的 `Cookie` 头 → 整行存 `run/cookie.txt`。

## 与抖音方案的区别

| | 抖音 a_bogus | 快手 __NS_hxfalcon |
|---|---|---|
| 实现 | 补环境跑官方 JSVM | **切出的真实算法函数** |
| 网络依赖 | /web/common + /web/r/token 预热 | **零网络** |
| 状态 | msToken 服务端轮换 | 纯本地 (cnt 计数器) |
| 版本 | 字节码轮换易碎 | 源码级函数, 稳定 |

唯一外部输入: `run/cookie.txt` (登录态 cookie) + 请求本身。

## 已验证

- `result:1` + 19~20 feeds/页 + `pcursor` 翻页链
- `photo.manifest` 多档清晰度直链 (djvod.ndcimgs.com) 可直接下载 MP4
- 同一 cookie 连续签名多次均通过签名验证
