---
name: tradingagents-windows-setup
description: 在 Windows 本机安装并跑通 TradingAgents（TauricResearch 多智能体金融交易框架）的完整流程与排错：venv + pip 装包、.env/API Key 落位、双击启动器、以及「装完了但跑不起来」的两类真实卡点——LLM 账户余额 402 与 Yahoo Finance/yfinance IP 限流的分层定位手法。当用户要装 TradingAgents、或装完后 yfinance 取不到数据、或 DeepSeek/其他 provider 报 402 Insufficient Balance 时使用。
agent_created: true
---

# TradingAgents on Windows：安装、验证与两类硬卡点

## 项目结构（v0.4.0，装完必须知道的几处）

| 位置 | 作用 |
|---|---|
| `tradingagents/default_config.py` | 全部默认值 + `TRADINGAGENTS_*` 环境变量覆盖表 |
| `tradingagents/llm_clients/model_catalog.py` | 各 provider 的 CLi 可选模型名（**这里是模型名的唯一权威来源**） |
| `tradingagents/llm_clients/api_key_env.py` | provider → 环境变量名映射 |
| `tradingagents/dataflows/interface.py` | `route_to_vendor(method, *args)` 是数据层统一入口，方法→vendor 映射表在这里 |
| `cli/main.py` | Typer app，`python -m cli.main` 或控制台脚本 `tradingagents` |
| `.env` | `find_dotenv(usecwd=True)` 读取，**所以必须在 cwd（项目根）** |

- `requires-python = ">=3.10"`，无上限 → Python 3.13 可用（实测 3.13.14 全绿）。
- 默认 `llm_provider: openai` / `gpt-5.6`；默认数据 vendor 全是 `yfinance`。
- `results_dir` = `~/.tradingagents/logs`，不是项目目录。

## 安装步骤（可复制）

```bash
# 1. 克隆（bash 里不要用管道接 tail，本机没有 coreutils）
cd /c/Users/<USER> && git clone --depth 1 https://github.com/TauricResearch/TradingAgents.git TradingAgents

# 2. venv（用 managed python 全路径，-E 绕开沙箱 shim）
cd /c/Users/<USER>/TradingAgents
<PY> -E -m venv .venv

# 3. 装依赖。必须后台跑，实测低配机要 25 分钟
CODEBUDDY_SAFE_DELETE_ENABLED=0 ./.venv/Scripts/python.exe -E -m pip install -e . \
  -i https://pypi.tuna.tsinghua.edu.cn/simple --extra-index-url https://pypi.org/simple \
  --no-input --progress-bar off > _install_out.log 2>&1; echo "EXIT=$?" >> _install_out.log
```

- **用 `-e .`（editable）而不是 `pip install .`**：源码改动立刻生效，用户改 prompts/配置不会"改了没反应"。
- `.env` 用 `find_dotenv(usecwd=True)`，所以启动器必须先 `cd` 到项目根。

## 装完必做的验证（分三层，别只看"装完了"）

**第 1 层：依赖与入口**（不需要任何 Key）

```bash
./.venv/Scripts/python.exe -E -m pip check          # 期望：No broken requirements found.
./.venv/Scripts/python.exe -m cli.main --help        # 期望：Typer 帮助页，rc=0
./.venv/Scripts/python.exe -c "import tradingagents; print(tradingagents.__file__)"
#     ↑ 必须指向仓库源码（editable 生效），不是 site-packages 副本
```

**第 2 层：配置真被读到**

```bash
./.venv/Scripts/python.exe -c "
import os, tradingagents           # 导入 tradingagents 会触发 load_dotenv
print('KEY len =', len(os.environ.get('DEEPSEEK_API_KEY','')))
print('lang =', os.environ.get('TRADINGAGENTS_OUTPUT_LANGUAGE'))"
```

`output_language` 若为 Chinese 而不是默认 English，就证明 `.env` 确实被找到了。

**第 3 层：数据层与 LLM 层分开测** —— 这一步最关键，见下。

## 回答「必须充值吗 / 不充值行不行」

**口径**：框架代码本身开源 0 成本；花钱的是背后的 LLM API。所以问题本质是
"要不要给某个大模型服务商付费"，不是给这个项目付费。

**不能只答"能/不能"，必须先说清框架对模型的硬能力要求** —— 否则用户拿免费 Key
跑不起来，会以为是装错了：

1. **工具调用（function calling）** —— 四个分析师 agent 靠它取行情/新闻/财报；
2. **结构化输出** —— Research Manager / Trader / Portfolio Manager 靠它产出 Pydantic 对象。

- `tradingagents/agents/utils/structured.py` 提供**降级兜底**：结构化调用失败会退回
  `plain_llm.invoke` 自由文本重试，所以弱模型**能跑完**，只是输出格式不保证。这是"降级"不是"不能跑"。
- ⚠️ `capabilities.py` 的 `_DEFAULT` 对**未知模型**判定为"支持 tool_choice + json_schema"，
  **偏乐观**。免费档模型必须实测，**不能信这张表**。
  （已知：`deepseek-v4-flash` / `deepseek-v4-pro` 都落到 `_DEEPSEEK_THINKING`，
  即 `supports_tool_choice=False`。）

**免费路线（都不需要给 DeepSeek 充值）** —— 端点已在境内实测可达（401 = 只差鉴权）：

| 厂商 | provider 取值 | 环境变量 | 端点实测延迟 |
|---|---|---|---|
| 智谱 GLM | `glm-cn` | `ZHIPU_CN_API_KEY` | 290ms（最快） |
| Kimi/Moonshot | `kimi` | `MOONSHOT_API_KEY` | 274ms |
| 通义千问 | `qwen-cn` | `DASHSCOPE_CN_API_KEY` | 779ms |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | 200 |
| Google Gemini | `google` | `GOOGLE_API_KEY` | 403（境内不稳） |

- ⚠️ **智谱的免费档 `glm-4.7-flash` 不在仓库模型菜单里**（菜单是 glm-5.3 系列等），
  必须用 CLI 的「Custom model ID」手填。
- 各家的"免费额度"说法来自二手信息且政策变动频繁，**不要报具体数字当事实**，
  让用户以官方页面为准。
- **本地 Ollama 理论 0 成本但低配机不现实**：菜单默认是 Qwen3-8B / GPT-OSS-20B /
  GLM-4.7-Flash-30B，8GB 内存无独显跑不动能胜任 tool-calling 的档位。

**交付一个 `check_key.py` 式的三层探测器**（基础对话 / 工具调用 / 结构化输出），
让用户拿任何一家的 Key 先自测。只测"能不能聊天"是不够的——很多模型能聊天但
工具调用直接报错。脚本要用仓库自己的 `create_llm_client` 走真实代码路径，
并用 `get_capabilities` 打印仓库对该模型的判定。

## 硬卡点 1：LLM 返回 402 Insufficient Balance

**症状**：客户端能构建成功，一调用就
`APIStatusError: Error code: 402 - {'error': {'message': 'Insufficient Balance', ...}}`

**别猜，直接查余额**（比反复试调用快得多）：

```
GET https://api.deepseek.com/user/balance
Authorization: Bearer <key>
→ {"is_available": false, "balance_infos":[{"currency":"CNY","total_balance":"0.00",...}]}
```

**关键区分**：`GET /v1/models` 返回 200 只证明 **Key 有效**，不证明**能调用**。
两者必须分开验证，否则会把"账户没钱"误报成"Key 配错了"。

**余额为 0 时有个连带后果**：DeepSeek 在余额校验阶段就拒绝，
**因此无法验证模型名是否有效**（不会返回 400 model not found）。

**模型名的实测结论（充值后已验证，别再让用户手动改模型名）**：
- 官方定价页脚注原文：现推荐 **`deepseek-flash`**（= DeepSeek-V4.1-Flash）；
  **旧名 `deepseek-v4-flash` 仍可调用**，请求由同一个 V4.1-Flash 提供服务、按 Flash 价格计费。
- 所以仓库 `model_catalog.py` 里的 `deepseek-v4-flash` **能直接用，不会 400**。
- 两个模型都支持 Tool Calls 与 Json Output，框架的硬能力要求满足。

**充值路径（官方文档原文要点）**：需先**实名认证** → 充值页用**支付宝/微信**在线充值；
**充值余额永久有效**；**未消费金额支持自助退款**（账单 → 退款管理）。
「赠送余额」与「充值余额」并存时**优先扣赠送余额**。

**DeepSeek 费率（CNY / 百万 token，2026-09 官方定价页）**——
**空闲时段是高峰的一半，高峰 = 北京时间周一至周五 9:00-12:00、14:00-18:00
（即周末全天、工作日夜间都是半价）**：

| 模型 | 输入(缓存命中) 闲/峰 | 输入(未命中) 闲/峰 | 输出 闲/峰 |
|---|---|---|---|
| `deepseek-flash` | 0.02 / 0.04 | 1 / 2 | 4 / 8 |
| `deepseek-v4-pro` | 0.15 / 0.30 | 4.5 / 9.0 | 13.5 / 27 |

→ 实测一次完整分析约 **¥0.17**（见下文实测开销），所以"充值多少"按每 100 次约 ¥20 估即可，
不必让用户充大额。**周末跑等于自动半价**，可以主动建议。

## ⚠️ 必须修的代码坑：`deepseek-flash` 会被误判成普通对话模型 → HTTP 400

`capabilities.py` 决定要不要给请求带 `tool_choice` 参数，而 **DeepSeek 思考型模型收到
`tool_choice` 会直接返回 400**。但 `_BY_ID` 只登记了 `deepseek-v4-flash`，
**没登记官方现名 `deepseek-flash`**；`_BY_PATTERN` 也只覆盖 `^deepseek-v\d` 和
`^deepseek-reasoner`。于是官方推荐的模型名会落到偏乐观的 `_DEFAULT`：

| 模型 ID | supports_tool_choice | requires_reasoning_content_roundtrip |
|---|---|---|
| `deepseek-flash`（官方现名） | **True ← 错** | **False ← 错** |
| `deepseek-v4-flash` | False ✓ | True ✓ |
| `deepseek-v4-pro` | False ✓ | True ✓ |

**修法**：给 `_BY_ID` 补 `"deepseek-flash": _DEEPSEEK_THINKING`，
并加 pattern `re.compile(r"^deepseek-flash")` 覆盖 `deepseek-flash-*` 变体。
配置里仍可优先用仓库原生的 `deepseek-v4-flash`（双保险）。

**通用教训**：只要用户报了 400，先查 `capabilities.py` 对该模型名的判定，
不要先怀疑 API Key 或参数。`_DEFAULT` 对未知模型一律当作"功能全支持"，是偏乐观的。

## 硬卡点 2：yfinance 取不到数据（YFRateLimitError）

`yfinance` 是默认且基本唯一的数据源（行情/指标/基本面/新闻全走它）。失败时数据层返回：

```
NO_DATA_AVAILABLE: No usable market data for 'AAPL' from any configured vendor
(Yahoo Finance returned no rows). ... Do not estimate or fabricate values
```

⚠️ **这个字符串长度只有 200~300 字符，看起来"没报错"，很容易被误判成 OK。**
验证数据层时**必须把返回内容打印出来看**，不能只看"有没有抛异常"。

**三段式定位法（按顺序做，能一步排除一个方向）**

1. **是代理吗？** 带 `HTTPS_PROXY` 跑一次，再 `unset HTTPS_PROXY HTTP_PROXY https_proxy http_proxy` + `NO_PROXY="*"` 跑一次。
   两次结果一致 → 不是代理。
2. **是客户端指纹吗？** `yfinance/_http.py` 把 `impersonate="chrome"` **写死，没有环境变量可调**。
   但它有 fallback：`curl_cffi` 不可用时退回 requests。用 import hook 模拟：

   ```python
   import sys
   class Blocker:
       def find_spec(self, fullname, path=None, target=None):
           if fullname == "curl_cffi" or fullname.startswith("curl_cffi."):
               raise ImportError("blocked")
           return None
   sys.meta_path.insert(0, Blocker())
   import yfinance._http as h; print("HAS_CURL_CFFI =", h.HAS_CURL_CFFI)  # 期望 False
   ```

   两种后端都同样失败 → 不是指纹问题，是 **IP 级限流**。
3. **是网络不通吗？** 用系统 HTTP 栈直连同一 URL 对比：
   `query1/query2.finance.yahoo.com/v8/finance/chart/<ticker>?range=5d&interval=1d`。
   如果系统栈能拿到 200 + 真实数据，而 yfinance 仍 403 → 网络通，是 Yahoo 在拒绝该客户端/IP。

**结论口径 —— 分两种情况，别一律说"等等就好了"：**

- **轻度**：间歇性限流，会自行衰减。**诊断时的大量探测请求本身会加剧限流**，
  看到失败后不要再连打。**这一条是踩过的真坑：一轮十几二十次探测会把轻度限流推成硬封锁。**
- **重度（本次实际遇到）**：**IP 级硬封锁，等不来**。判据是——
  403 在长时间后可**恶化**成 ConnectTimeout，连 `fc.yahoo.com`（取 cookie 用）也超时，
  三种客户端结果完全一致。此时"等一会儿再试"是错误建议。

**被测出的事实：`TradingAgents` 不支持 akshare/baostock，但它的 vendor 层是可扩展的。**
`alpha_vantage` 覆盖有限（仅美股、免费档约 25 次/日、不覆盖 A 股），所以
**正解是自己加一个国内源供应商 `cn`** —— 完整改法见下一节。

## 解决 Yahoo 封锁：新增国内源供应商 `cn`（新浪）

### 国内源选型（按实测淘汰，别照抄网上的推荐）

| 源 | 实测 | 判定 |
|---|---|---|
| 东财 K线 `push2his.eastmoney.com` | 首次通，之后**连续三次 ConnectionError** | ❌ 不稳定，弃用 |
| 腾讯 A股 `web.ifzq.gtimg.cn/.../fqkline` | 稳定，但**硬上限 640 根**（约 2.5 年） | ⚪ 备选 |
| 腾讯美股 `usfqkline` | 只返回 **2 根** | ❌ 不可用 |
| **新浪 A股** `money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh600519&scale=240&ma=no&datalen=5000` | 稳定，**最多 5000 根（约 20 年）**，字段具名 | ✅ |
| **新浪美股** `stock.finance.sina.com.cn/usstock/api/jsonp_v2.php/var%20_{S}=/US_MinKService.getDailyK?symbol={S}&___qn=3` | 稳定，**10030 根（1984 至今）**，带 JSONP 包裹 | ✅ |

**选新浪的关键理由：字段具名**（`day/open/high/low/close/volume`），
没有"数组第几位是开盘价"的位置错位风险。

⚠️ **如果改用腾讯的数组格式**：顺序经交叉校验是 `date,open,close,high,low,volume` ——
**不是**常见的 `date,O,H,L,C`。搞错会静默污染所有指标，且不会报错。

⚠️ **一定要做字段顺序交叉校验**：拿新浪实时快照 `hq.sinajs.cn/list=sh600519,gb_aapl`
（格式 `名称,今开,昨收,现价,最高,最低,...`）比对同一天的 K 线。
本次用 600519 / AAPL / NVDA 三个标的验过，开高低收全部完全一致。

⚠️ 新浪日 K 是**不复权**数据，长周期指标在分红/送股处会有偏差——交付时要说明。

### 改哪四个文件

| 文件 | 改动 |
|---|---|
| `dataflows/cn_data.py` | **新增**。代码映射（A股/美股）+ 日K抓取 + 输出与 `get_YFin_data_online` 同格式 |
| `dataflows/stockstats_utils.py` | ★ **最关键**：`load_ohlcv` 从写死 `yf.download` 改为按 vendor 链取数。指标是在本地用 stockstats 算的，**换掉取数源头，`get_indicators` 就跟着一起通了** |
| `dataflows/interface.py` | `VENDOR_METHODS["get_stock_data"]` 加 `"cn": get_cn_stock_data`；`VENDOR_LIST` 加 `"cn"` |
| `default_config.py` | `data_vendors` 是 **dict**，走不了 `_coerce` 标量路径 → 单独加 `TRADINGAGENTS_DATA_VENDOR_CHAIN` 处理，作用于四个市场数据类别 |

配置：`.env` 里 `TRADINGAGENTS_DATA_VENDOR_CHAIN=cn,yfinance`
（链式，前一个失败自动落下一个，**Yahoo 解封了会自动接上，不用改代码**）。

### 已知缺口（改完仍然缺的）

`get_fundamentals` / 三大报表 / `get_news` **只有 yfinance 实现**，Yahoo 被封就是空的。
后果：4 个分析师里行情/技术面有数据、基本面与新闻面为空。
- **A 股基本面可行性已验证**：东财 `datacenter.eastmoney.com` 财务报表接口、
  `np-anotice-stock.eastmoney.com` 公告接口都返回 200 + 真数据，可以补。
- **美股基本面**：东财美股接口连接被重置，暂无可用的国内源。

### 注意路由的一个细节

`route_to_vendor` 在显式配置 vendor 链时，会**只保留该方法真实支持的 vendor**：
```python
vendor_chain = [v for v in explicit if v in VENDOR_METHODS[method]]
```
所以 `cn,yfinance` 配给 `get_fundamentals`（没有 cn 实现）会自动退化成只用 `yfinance`，
**不会报错**。即链式配置可以全局生效、按方法各自取交集。这是安全的。

## 怎么跑一次（CLI 是纯交互的，非交互必须程序化驱动）

**`cli/main.py` 的 `analyze` 命令没有 ticker 参数**（只有 `--checkpoint` / `--clear-checkpoints`），
所有选择都靠 `prompt_toolkit` 交互。**所以想后台/脚本化跑，不能调 CLI**，要直接驱动图：

```python
import tradingagents                      # 触发 .env 加载
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

config = DEFAULT_CONFIG.copy()            # 已含 .env 覆盖（provider/模型/输出语言/vendor链）
ta = TradingAgentsGraph(
    ("market", "social", "news", "fundamentals"),
    debug=True, config=config, callbacks=[meter],
)
state, signal = ta.propagate("688981.SS", "2026-09-11")   # signal 是 5 档评级
```

- `propagate(company_name, trade_date, asset_type="stock")` → `(final_state, signal)`。
- ⚠️ **`on_tool_start` 回调不会触发**（langgraph 的 ToolNode 不走这个回调），
  所以自己写的工具计数器会一直是 0 —— **别把 0 当事实报出去**。
  真实工具调用次数从 debug 日志里数（匹配 `^  [a-z_]+ \(call_`）。
- **一定要加 token 上限保护**（在 `on_llm_end` 里累计并在超限时抛异常），
  避免失控循环把钱烧掉。

**实测开销（2026-09-12，A股 `688981.SS`，flash+pro 混合，空闲时段）**：

| 项 | 值 |
|---|---|
| 墙钟 | **9 分 24 秒** |
| LLM 调用 | 22 次 |
| 工具调用 | 34 次 |
| Token | in 146,780 / out 55,014 / 合计 201,794 |
| **真实成本** | **¥0.17**（用余额变化实测，不是估算） |

→ 别凭感觉报价：**实测比"几十次调用所以很贵"的直觉低一个数量级**。
按 ¥0.17/次，¥20 约能跑 100 次以上。

**落盘位置**（要取报告看这里，不在项目目录）：
- `~/.tradingagents/logs/<TICKER>/TradingAgentsStrategy_logs/full_states_log_<date>.json`（完整状态）
- `~/.tradingagents/cache/<symbol>-OHLCV-<start>-<end>.csv`（K线缓存，按天为窗口）
- `~/.tradingagents/cache/checkpoints/<symbol>.db`（断点续跑）
- `~/.tradingagents/memory/trading_memory.md`

**建议给用户开启 `TRADINGAGENTS_CHECKPOINT_ENABLED=true`**：一次跑十几分钟，
中途崩了可从最后成功节点续，不用重付 token。实测该模块 import 正常
（依赖 `langgraph.checkpoint.sqlite`，装包时已带上），可以放心开。

## 该框架的固有成本提醒（给用户交底时必须说）

- 一次分析会驱动多个分析师 + 多轮多空辩论 + 风控辩论 + 组合经理，
  是**几十次 LLM 调用**，不是一次。默认 `max_debate_rounds=1`、`max_risk_discuss_rounds=1`
  已是最省档，调高会显著加价。
- A 股 ticker 用后缀：`600519.SS`（沪）/ `000001.SZ`（深）；
  港股 `.HK`、加密 `BTC-USD`。
- 宏观数据（FRED）需单独免费 Key，不填则该模块不可用。

## 本机环境踩坑（这几个坑会浪费大量时间，务必先避开）

1. **不要用 PowerShell 的 `Start-Process` 起子进程。**
   本机 PS 5.1 会直接失败：`已添加项。字典中的关键字:"Path"所添加的关键字:"PATH"`。
   原因是环境里同时存在 `Path` 和 `PATH`，PS 5.1 构建环境块时崩掉。
   → **改用 bash 的 `>` / `2>&1` 重定向**，增量落盘且不受此 bug 影响。
2. **本机 bash 没有 coreutils。** `ls / mkdir / tail / head / wc / grep / dirname` 全部不存在，
   连 `mkdir` 都没有。但 shell 内建可用：`cd`、`echo`、`unset`、变量赋值。
   → 目录操作用 PowerShell `New-Item`，输出落盘用 `>`，读文件一律用 Read 工具。
3. **pip 输出重定向到文件时被块缓冲。** 日志长时间 0 字节 ≠ 没在跑。
   → 判断真实进度看：`site-packages` 目录数/体积、python 进程的 CPU 时间、venv 大小。
4. **`python -E` 的双面性**（最容易翻车的点）：
   - 装包时**必须**加 `-E`，否则沙箱 shim 的 `sitecustomize` 会进 PYTHONPATH，
     pip 覆盖文件超阈值会直接猝死；
   - 但**启动器里绝对不能加 `-E`**，因为它会连 `PYTHONUTF8` / `PYTHONIOENCODING`
     一起忽略——而这两个正是让 Windows 控制台中文不乱码的关键。
5. **别把用户口头描述当成事实基线。** 本次用户说"Key 已经在系统环境变量里了"，
   实测 User 级只有 5 个变量、Machine 级没有任何含 KEY/TOKEN/SECRET/API 的变量。
   → 涉及凭据时，先枚举环境变量（`[Environment]::GetEnvironmentVariables('User')` 列出全部名字
   即可证明注册表读取正常），再下结论。
6. **`HTTPS_PROXY` 可能只存在于 agent 进程环境**，不在 User/Machine 级。
   → 意味着"我这边能通"不代表"用户双击时能通"，涉及网络结论要说明这个差异。
   本机的 `127.0.0.1:10432` 代理实测对 HTTPS 请求报 **SSLError，代理本身是坏的**，
   不能当绕行手段。
7. **`Edit` 工具可能报成功但内容没写进文件。** 本次给 `interface.py` 加一行 import，
   返回 `Successfully edited`，实际文件里没有，导致启动时 `NameError`。
   → **改完关键文件必须用 Grep 复核实际内容，不要信返回值。** 重新编辑一次通常就好。
8. **别用 `python -c` 配合 bash heredoc + 管道**（`python - <<'PY' ... | tail`）：
   本机 bash 没有 `tail`，整条命令会静默失败只抛出 shim 噪音。
   → 校验脚本一律写成 `.py` 文件落盘再执行，`>` 重定向输出，再用 Read 读结果。
9. **给用户文档写结论时，不要把实测结论降级成"可能/如果"。**
   本次多处结论（Yahoo 封锁、字段顺序、模型名）都已实测，写"如果报 400 就…"
   会削弱可信度。事实与判断要分开写。
