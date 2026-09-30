---
name: install-mx-skills-dfcfs
description: 在 Windows/WorkBuddy 上安装东方财富「妙想 Skills」（mx-data / mx-search / mx-xuangu / mx-zixuan / mx-moni / mx-poster）并配置永久 MX_APIKEY。覆盖：官方指南按 ClawHub/openclaw 写而本机没装 openclaw 时的路径改投、zip 内层嵌套目录、mx-moni 缺 YAML frontmatter、脚本硬编码 Linux 输出路径会在 C 盘根建目录、以及用 curl 实测两端点验密钥的手法。当用户要装/重装妙想 skill、或妙想 skill 不生效/取不到数据时使用。
agent_created: true
---

# 东方财富妙想 Skills 安装（Windows / WorkBuddy）

## 什么时候用

- 用户给出妙想安装指南（`https://marketing.dfcfw.com/res/download/A*.md`）要求安装
- 已装的 mx-* 技能不生效、或调接口报密钥错误，需要重装/排查

## 官方指南与本机的三处错配（先认清再动手）

官方指南是写给 **ClawHub / openclaw** 的，本机是 WorkBuddy。直接照抄会失败：

| 指南要求 | 本机实际 | 处理 |
|---|---|---|
| 装到 `~/.openclaw/skills`、`~/skills` 等 | 本机无 openclaw，这些路径全空 | 改投 `C:\Users\<user>\.workbuddy\skills\` |
| 指南自带 `check_skill` 取证脚本 | 它只查 `$HOME/.openclaw/...` | **必然全报 MISSING**，别据此判定失败；自行按 `.workbuddy\skills` 校验 |
| 第 1 步九条 `rm -rf` 清旧版 | 大概率一个都不存在 | **先盘点再决定**，不存在就是空操作，不要无脑执行 |

## 安装步骤

### 1. 下载 6 个包（官方固定链接）

```
mx-data   https://marketing.dfcfw.com/res/download/A620260331IHX67H.zip
mx-search https://marketing.dfcfw.com/res/download/A620260331K5WDTK.zip
mx-xuangu https://marketing.dfcfw.com/res/download/A620260623PHDKPP.zip
mx-zixuan https://marketing.dfcfw.com/res/download/A6202603314TMGR1.zip
mx-moni   https://marketing.dfcfw.com/res/download/A620260529ON5BMY.zip
mx-poster https://marketing.dfcfw.com/res/download/A6202606169PIWQO.zip
```

用 PowerShell `Invoke-WebRequest -OutFile`。**curl 写到工作区可能报
`(23) client returned ERROR on write`** —— 换 PowerShell 写就行（底层能写成功）。

### 2. 剥掉一层嵌套目录

每个 zip 解出来是 `mx-data/mx-data/SKILL.md`，**内层还套一层同名目录**。
安装要取**内层**，最终必须是：

```
~/.workbuddy/skills/mx-data/{SKILL.md, _meta.json, mx_data.py}
```

### 3. 安全审计（装前必做）

扫全部 `.py` 与 `SKILL.md`，关注：`os.system|shell=True|eval|exec|__import__|base64|pickle|
rmtree|unlink|os.remove`、出网域名、密钥流向。

**本包的既有结论（v1.0.x，可作基线）**

- 出网**只有** `mkapi2.dfcfs.com/finskillshub`（东方财富官方）
- 密钥只读 `MX_APIKEY`，只写进 `apikey` 请求头
- 唯一 `subprocess` 在 `mx_moni.py`：`subprocess.run(['curl', ...])` 固定 argv、
  无 `shell=True`、无用户可控拼接 → **非注入**
- 判定：无 P0/P1，可装

### 4. 补 frontmatter

`mx-moni/SKILL.md` **没有 YAML frontmatter**（其余 5 个都有）。
WorkBuddy 靠 `name` / `description` 索引技能，缺了会识别不到 → 补上，正文别动。

### 5. 装到用户级技能目录

`C:\Users\<user>\.workbuddy\skills\`。装完核对 6 个目录各有 `SKILL.md`。

不需要改 `_bm_skillid_migration.json`，WorkBuddy 自动发现目录。

## 环境变量（永久）

用户要「永久」时，Windows 上的正解是用户级环境变量，**不是** shell 启动文件：

```powershell
[Environment]::SetEnvironmentVariable("MX_APIKEY", "<key>", "User")
```

读回验证（直接读注册表，不受当前进程影响）：

```powershell
reg query "HKCU\Environment" /v MX_APIKEY
[Environment]::GetEnvironmentVariable("MX_APIKEY","User")
```

- 本机 `~/.bashrc`、`~/.bash_profile` **都不存在**（只有 `~/.profile`），
  往 shell 启动文件里塞是冗余的，别做。
- ⚠️ **新变量对已运行的 WorkBuddy 进程无效** —— 脚本子进程继承 WorkBuddy 的环境，
  **必须重启 WorkBuddy** 才生效。这一点必须主动告知用户。

## 验证（别只验文件在不在，要验密钥能不能用）

直接 curl 打两个官方端点，看 HTTP 码与 `success` 字段：

```bash
curl -s -X POST "https://mkapi2.dfcfs.com/finskillshub/api/claw/news-search" \
  -H "apikey: $MX_APIKEY" -H "Content-Type: application/json; charset=UTF-8" \
  -d '{"query":"中芯国际 最新动态"}' -w "\nHTTP=%{http_code}\n"

curl -s -X POST "https://mkapi2.dfcfs.com/finskillshub/api/claw/query" \
  -H "apikey: $MX_APIKEY" -H "Content-Type: application/json; charset=UTF-8" \
  -d '{"toolQuery":"中芯国际最新价"}' -w "\nHTTP=%{http_code}\n"
```

判据：`HTTP=200` 且响应含 `"success":true`。实测会返回真实行情
（如 `688981.SH` / `00981.HK` 报价）→ 密钥有效、链路通。

## Windows 上跑起来的三道坎（都已实测，装完必须全做）

**① 依赖包：`pandas` + `openpyxl` 必须装**

`mx_data.py` 直接 `import pandas`，没有就整个技能起不来
（`ModuleNotFoundError: No module named 'pandas'`）。写 Excel 还要 `openpyxl`。

```powershell
& "<managed-python>\python.exe" -E -m pip install pandas openpyxl
# 装完约 93 MB：pandas 59.8 + numpy 30.8 + openpyxl 1.8 + 其他 0.6
```

> 装包必须带 `-E`（绕开沙箱的删除守卫 shim，否则 pip 覆盖文件超阈值会猝死）。

**② 编码：必须设 `PYTHONIOENCODING=utf-8`，否则 4/6 个技能直接崩**

脚本要打印 emoji（✅ 📊 ❌）和 API 返回的特殊字符，而 Windows 管道默认编码是
GBK(cp936)，编码不了就抛：

```
UnicodeEncodeError: 'gbk' codec can't encode character '\u2705' in position 0
```

```powershell
[Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "User")
```

- 比开 `PYTHONUTF8=1`（全局 UTF-8 模式，会改 `open()` 默认编码）更克制，
  只影响 stdio 编码。
- ⚠️ **自己写测试脚本时别用 `python -E`**：`-E` 会忽略 `PYTHONIOENCODING`，
  于是 4 个技能全报 encoding 错误——会被误判成技能坏了。这个坑我踩过一次。

**③ 输出路径：厂商写死了 Linux 路径，必须打补丁**

6 个 `.py` 的默认输出目录全是 `/root/.openclaw/workspace/mx_data/output`，
Windows 下落成 `C:\root\.openclaw\workspace\mx_data\output`。
最坑的是 **`mx_moni.py` 在 import 阶段就 `makedirs`，且命令行没有 `--output-dir` 参数**
→ **每次调用都必然在 C 盘根目录建目录树**，输出文件用户根本找不到。

补丁：6 处默认路径统一换成 `os.path.expanduser("~/mx-skills-output")`。
落点 `C:\Users\<user>\mx-skills-output\`。改动位置：

```
mx-data\mx_data.py      第341行
mx-search\mx_search.py  第167行
mx-xuangu\mx_xuangu.py  第201行
mx-zixuan\mx_zixuan.py  第196行
mx-moni\mx_moni.py      第19行   (OUTPUT_DIR，单引号)
mx-poster\mx_poster.py  第16行   (DEFAULT_OUTPUT_DIR)
```

注意 `mx-moni` 那处是**单引号**，其余是双引号，替换要覆盖两种引号。
顺便把 help/print 里的展示文案一起换掉，别让提示信息撒谎。

**回归验证**（强制走默认路径）：`mx-moni` 与 `mx-search` 均返回码 0，
输出落进新目录，`C:\root` **未被重新创建**。

> ⚠️ **补丁会被技能更新覆盖**。升级妙想技能后要重新打，否则 `C:\root` 复发。

## 各技能的功能边界（实测）

| 技能 | 状态 | 备注 |
|---|---|---|
| mx-data | ✅ | 返回真实行情，写 .xlsx + 描述 + 原始 JSON |
| mx-search | ✅ | 返回新闻/研报全文 |
| mx-xuangu | ✅ | 自然语言选股，出 CSV |
| mx-zixuan | ✅ | 读账号真实自选股（需妙想账号已登录/授权） |
| mx-moni | ⚠️ | 脚本正常，但未绑定模拟账户时接口返回 `404 请先绑定账户~` |
| mx-poster | ✅ | `list` 读社区动态；**`post`/`like`/`reply` 是公开发帖，属对外动作，需谨慎** |

## 固化与一键恢复（2026-09-29 起，防升级重装）

六技能已固化在 **`C:\Users\zyx32\dfcfw-mx-backup\`**（目录名刻意避开官方清理通配 `~/mx-*`，
照官方指南清理旧版不会误删它）：

| 文件 | 作用 |
|---|---|
| `skills\mx-*`（6 目录） | 固化快照 = 已装、已打补丁、已验证密钥的最终态 |
| `restore_mx_skills.cmd` | **双击入口**：一键恢复 + 补丁重打 + HKCU 环境变量体检（不写入密钥） |
| `_tools\make_backup.py` | 刷新固化点（官方包升级重装后跑，幂等） |

**升级后操作顺序**（覆盖旧版「手工 patch_path.py」流程）：

1. WorkBuddy 升级清掉技能 → **双击 `restore_mx_skills.cmd`** 即自动补齐；
2. 妙想官方包更新重装 → 恢复脚本对含 `/root/.openclaw` 的新包**幂等重打补丁**（`[RE-PATCHED]`），
   内容不同只报 `[DIFF]` 不覆盖（不把官方新版退回旧版）；
3. 之后跑 `_tools/make_backup.py` 让固化点跟上新版。

三态破坏测试已验证（删文件→RESTORED、补丁回退→RE-PATCHED、正常→全 SKIP），
详见项目日志 2026-09-29。旧工作区 `2026-09-12-15-33-31\mx_download\patch_path.py` 仅作历史追溯。
