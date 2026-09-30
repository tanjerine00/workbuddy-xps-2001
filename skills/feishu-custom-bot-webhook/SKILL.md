---
name: feishu-custom-bot-webhook
description: 用飞书（Lark）自定义机器人 Webhook 推送消息时的排错与签名实现。覆盖 19001/19021/19024/9499 错误码的区分与定位、机器人开启「签名校验」后必须补的 timestamp+sign 字段、飞书签名算法那个反直觉的写法、以及不靠猜的决定性验证手法。当推送消息到飞书失败、返回 code 19021 sign match fail、或需要给一个没实现签名的项目补上飞书推送能力时使用。
agent_created: true
---

# 飞书自定义机器人 Webhook：排错与签名

## 先用错误码区分问题在哪一层

飞书 Webhook **HTTP 状态码永远是 200**，真正的结果在响应体的 `code` 字段。
所以「`resp.status_code == 200` 就以为成功」是经典误判 —— 必须解析 body：

```python
r = requests.post(url, data=json.dumps(payload), headers={"Content-Type": "application/json"})
body = r.json()
ok = (r.status_code == 200 and body.get("code") == 0)
```

| code | 含义 | 怎么办 |
|---|---|---|
| 0 | 成功 | — |
| **19001** | access token invalid | URL 里的 token 不对/已失效，重新完整复制 |
| **19021** | sign match fail or timestamp is not within one hour | **签名问题**，见下 |
| 19002 | 机器人被移出群 / 群解散 | 重新拉机器人进群 |
| 19024 | 机器人被停用 | 群里重新启用 |
| 9499 | 报文格式错误 | 卡片 JSON 结构问题 |

**关键区分**：19001 → URL 错；**19021 → URL 是对的、token 有效，只是缺签名**。
看到 19021 就等于确认「这个机器人开了签名校验」。

## 决定性验证：别猜，发两个最小 payload

怀疑是签名问题还是 URL 问题时，发这两个请求对照（都不需要密钥）：

```python
for body in [
    {"msg_type": "text", "content": {"text": "ping"}},                       # 完全不带 sign
    {"msg_type": "text", "content": {"text": "ping"},
     "timestamp": "0", "sign": ""},                                          # 带空 sign
]:
    print(requests.post(URL, data=json.dumps(body),
                        headers={"Content-Type": "application/json"}).text)
```

两个都返回 19021 → 签名被强制要求（和 URL 无关）。
如果其中一个能成功 → 说明签名没开，问题在别处。

## 签名算法（写法反直觉，最容易写错）

飞书官方算法是：把 `"{timestamp}\n{secret}"` 整个字符串当作 **HMAC 的 key**，
**消息体为空**，再 base64。很多人会想当然写成「secret 当 key、timestamp 当消息」——
那是错的，会得到 19021。

```python
import base64, hashlib, hmac, time

def gen_sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")
```

签名放在**请求体顶层**，与 `msg_type` 平级：

```python
ts = str(int(time.time()))
payload["timestamp"] = ts
payload["sign"] = gen_sign(ts, secret)
```

要点：
- `timestamp` 是**秒级**字符串，有效窗口 **1 小时** → 客户端时钟偏差超 1 小时也会报 19021。
  排查时顺手打印一次本机时间。
- 签名是**每次请求现算**，不能缓存复用。
- 密钥位置：飞书群 → 设置 → 群机器人 → 点机器人 → 「签名校验」右侧的密钥。

## 给已有项目补签名支持（最小侵入写法）

不要一上来就重写推送模块。按这个顺序做，**保证不破坏未开签名的机器人**：

1. 配置层加一个**可空**字段（默认空串），并加一个「取密钥」的方法，
   找不到就回退到默认密钥：
   ```python
   def get_secret(self, key: str) -> str:
       return self.strategy_secrets.get(key.lower(), self.default_secret)
   ```
2. 推送时**只在密钥非空时才附加** timestamp/sign：
   ```python
   if secret:
       ts = str(int(time.time())); payload["timestamp"] = ts; payload["sign"] = gen_sign(ts, secret)
   ```
   这样密钥留空 = 完全不签名 = 原行为，零回归风险。
3. **配置项默认值一定留空，不要写占位符**（如 `REPLACE_WITH_SECRET`）。
   留占位符会让「没开签名校验」的机器人收到一个错误的 sign，反而把原本能用的推送搞坏。
4. 若项目已用 `前缀 + 环境变量` 扫描机制收集配置（比如 `STRATEGY_WEBHOOK_*`），
   新密钥的**前缀不要复用同一个**，否则会被旧逻辑误当成一条 URL 收进去。换个前缀
   （如 `FEISHU_SECRET_*`）。

## 排错工具该有的样子

把「只记一条 ERROR 日志」升级成一个能直接跑的诊断脚本，比事后翻日志高效得多：
打印 **URL（打码）+ 是否配了密钥 + 本机时间 + 将要发送的报文 + 飞书原始响应 + 错误码的人话解释**，
并支持 `--dry-run` 只看报文不发送。微信/飞书这类推送排查 90% 的时间花在
「不确定到底是 URL、密钥、时钟还是报文格式」，把这些一次性摊开就省下了。
