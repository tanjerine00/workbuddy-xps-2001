---
name: baostock-ashare-setup
description: 在 Windows 本机安装并跑通「baostock/akshare 数据源的 A 股量化项目」（如 Sequoia-X 这类选股系统）时必须知道的坑与验证流程：baostock 全市场股票列表需要长 socket 超时、回填速度估算、pip 分批安装避开代理 502、以及一套可复用的小样本链路验证脚本。当用户要求安装/跑通一个用 baostock 取 A 股日K的项目、出现 "timed out / 接收数据异常"、或需要估算全市场回填耗时的时候使用。
agent_created: true
---

# baostock / akshare A 股数据项目：安装与跑通

## 头号坑：`socket.setdefaulttimeout` 会把 baostock 掐死

**症状**：`login success!` 之后紧跟 `timed out` + `接收数据异常，请稍后再试。`，
然后 `get_all_symbols()` 返回 0 只 / `list index out of range`，回填根本启动不了。

**根因**：baostock 是流式 socket 接收。`query_stock_basic(code_name="", code="")`
一次返回**全市场约 9000 行**，在慢网络（~150 kB/s）下实测需要 **40s+** 才传完。
很多项目模板会写 `socket.setdefaulttimeout(10.0)` —— 10 秒必挂。

**诊断方法**（先量化，别猜）：

```python
import time, baostock as bs
bs.login()
t = time.time()
rs = bs.query_stock_basic(code_name="", code="")
n = sum(1 for _ in iter(lambda: rs.next(), False) if rs.get_row_data())
print(f"{n} 行，耗时 {time.time()-t:.1f}s")
bs.logout()
```

**修复**：永远不要用 10s。改成可配置，默认 120：

```python
import os, socket
socket.setdefaulttimeout(float(os.environ.get("SOCKET_TIMEOUT", "120")))
```

排查任何 baostock 项目时，**第一件事就是 grep `setdefaulttimeout`**。

## 回填耗时估算（先估再决定跑不跑）

实测在 i7-8550U / 8G / 慢网络上：**约 2.6 秒/只**（200 只用 526 秒）。
全市场 5200 只 → **约 3.8 小时**。

> README 里写的「12 分钟」是快网络 + 服务器的数字，本机不要采信。
> 单线程 `backfill` 和前向窗口（如 `START_DATE=2024-01-01` → 每只约 650 根K线）决定耗时。

**做法**：先跑 200 只小样本验证全链路，再决定要不要挂全量。
不要一上来就 `--backfill` 全市场然后干等 4 小时。

## pip 安装：必须分批，否则前功尽弃

pip **全有或全无** —— 依赖树大时（akshare 会拖进 mini-racer 15MB、lxml 4MB、
curl_cffi 2MB…），最后一步某个大 wheel 被代理 502 掐断，前面 8 分钟的下载全废。

按这个顺序装（清华镜像 + 加大重试）：

```bash
PIP="./.venv/Scripts/python.exe -m pip"
M="-i https://pypi.tuna.tsinghua.edu.cn/simple --retries 10 --timeout 120"
$PIP install $M "pandas==3.0.5"                    # 1) 最大最易失败的先装
$PIP install $M baostock pydantic-settings rich requests akshare   # 2) 其余
$PIP install $M --no-deps .                        # 3) 项目本体，不再触发解析
```

顺带：`pip` 声称 "looking at multiple versions of X" 开始回溯时，直接把那个包
`== 具体版本` 钉死（用 `uv.lock` 里的版本），能跳过回溯、也能命中已下载的缓存。
pandas 3.x 对这类项目一般没问题 —— 先看 `uv.lock` 里锁的是不是 3.x。

## 小样本验证脚本（可复用模板）

写一个**不改动项目原始代码**的验证脚本，跑完四步并打印汇总表：

1. `engine.get_all_symbols()` 取全市场列表 —— **打印总数**（正常应在 5000+，
   若为 0 就是上面那个超时坑）
2. 等间隔抽样 `symbols[::len//N][:N]`，覆盖沪深两市且可复现
3. `engine.backfill(sample)` → 直接查 SQLite 校验
   `SELECT COUNT(*), MIN(date), MAX(date)`，**必须断言行数 > 0**
4. 逐个跑策略，`try/except` 包住每个策略（单个策略炸掉不该中断整轮），
   最后打印「策略 / 命中数 / 示例代码」表格

关键细节：
- 脚本顶部同样要设 `SOCKET_TIMEOUT`，否则复现不了真实条件
- 提供 `--no-backfill`（复用已有库只跑策略）和 `--no-notify`（跳过推送），
  否则每次调参数都要重跑几十分钟
- 若项目用 `multiprocessing.Pool`（Windows 是 spawn），**必须实跑一次 `main.py`**
  验证多进程路径，这是最容易在 Windows 上崩的地方

## 验证「能工作」的判定标准

别只看「没报错」。逐项确认：

| 环节 | 判定依据 |
|---|---|
| 依赖 | 逐个 `importlib.import_module` 全部模块，不能只看 pip 说 Successfully |
| 取数 | 打印行数 + 最新一条真实数值（如茅台后复权收盘价），确认不是空壳 |
| 落库 | 直接查 SQLite 的 COUNT / MIN / MAX，别信日志 |
| 策略 | 至少有一个策略命中数 > 0，全为 0 要怀疑数据或筛选条件 |
| 推送 | 用**占位符 URL** 跑一次，期望看到飞书返回 `code 19001 token invalid` 并被
  `except` 优雅降级 —— 这恰好证明 HTTP 链路通、只差真实 token。**这不算失败** |

## 交付形态

给用户做入口时按「双击即用」来：`.cmd` 纯 ASCII + CRLF 只负责找解释器，
中文菜单全放在 Python 里（详见 `windows-cmd-doubleclick-launcher` 技能）。
本类项目还额外要求：**`.cmd` 和启动器都必须 `cd` 到项目根目录**，
因为 `.env` 与 `data/*.db` 都按相对路径解析，双击时 cwd 是 system32。
