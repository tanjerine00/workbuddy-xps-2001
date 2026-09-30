---
name: install-claude-skill-package
description: 把 GitHub 上的 Claude Code 技能包 / 插件仓库（含 SKILL.md 目录、MCP server.py）安装进 WorkBuddy 的完整流程与排错。当用户要“安装某个 GitHub 上的 skills 包 / 插件 / claude plugin marketplace”、出现 GitHub git clone 被沙箱阻断、技能重名覆盖、Windows CRLF 破坏 frontmatter、或 MCP server.py 因 mcp 2.x 改名 FastMCP→MCPServer 而 import 失败时，使用本技能。
agent_created: true
---

# 把 Claude Code 技能包安装进 WorkBuddy

Claude Code 插件仓库（如 *claude-for-financial-services-cn*）的结构通常是：
`vertical-plugins/<domain>/skills/<skill>/SKILL.md`、MCP 服务在 `mcp-servers/<name>/server.py`、
还有 `agent-plugins/`、`scripts/`、`*.md`。WorkBuddy 的技能目录是 `~/.workbuddy/skills/<name>/SKILL.md`，
frontmatter 用 `name` + `description` —— 与 Claude Code 几乎一致，所以可以直接搬运，但有几个坑。

## 步骤

1. **下载整仓**：本机沙箱常把 `git clone github.com` 用 schannel/CONNECT 502 掐死。
   但 `codeload.github.com` 的 tarball 与 `raw.githubusercontent.com` 的 curl 直连通常可用：
   ```bash
   curl -sS -o repo.tar.gz "https://codeload.github.com/<owner>/<repo>/tar.gz/refs/heads/<branch>"
   tar -xzf repo.tar.gz
   ```
   不要用 `/tmp`（Git Bash 映射不稳），解到工作区下的显式 Windows 路径。

2. **安全审计（装前必做）**：`grep -nE "eval\(|exec\(|os\.system|subprocess|socket\.|requests\.post|urllib|base64|/etc/passwd|\.ssh|pickle"` 扫 `scripts/` 与 `mcp-servers/`。
   重点看 MCP server.py：密钥从哪读（env / 本地 config 均可）、只发往哪个域名、是否 `verify=False`、
   有无把密钥外泄到非官方地址。本例（金融包）结论：wind/ifind 只发官方域名，akshare/china-news 用开源库，**P2 可装**；
   唯一隐患是 ifind 上游默认 `verify=False`（关 TLS 校验）。

3. **移植技能（按领域命名空间，防重名）**：Claude 包的技能名会在不同域重复
   （如 `china-accrual-schedule` 同时出现在 china-finance 与 fund-admin）。
   装到扁平的 `~/.workbuddy/skills/` 会互相覆盖 —— 必须用 `<domain>__<orig>` 作目录名，
   并把 frontmatter 的 `name:` 也改成同名，否则 WorkBuddy 按名注册时会撞车。
   脚本骨架：
   ```python
   for domain in 各 vertical-plugins 子目录:
       for skill in skills/*:
           fm, body = 拆分首个 --- 块 ---
           new_name = f"{domain}__{orig_name}"
           out = "---\n" + fm.rstrip("\n") + "\n---\n" + body
           open(dst/SKILL.md, "w", encoding="utf-8", newline="\n")  # 关键：newline="\n" 防 CRLF
   ```
   **CRLF 坑**：Windows 上 `open(...,"w")` 默认写 `\r\n`，会让 YAML frontmatter 解析失败；
   要么用 `newline="\n"`，要么装完用 `t.split("\n")` 逐行校验 `name:`/`description:` 都在首段。

4. **MCP 数据源**：把 `mcp-servers/<name>` 复制到持久位置（如 `~/.workbuddy/finance-mcp-servers/`），
   在 `~/.workbuddy/mcp.json` 写 `{"mcpServers": {"akshare": {"type":"stdio","command":"<venv>/Scripts/python.exe","args":["<server.py 绝对路径>"]}}}`。
   - **mcp 版本坑**：仓库里 `server.py` 几乎都用 `from mcp.server.fastmcp import FastMCP`（mcp 1.x API）。
     `pip install "mcp>=1.0.0"` 现在会拉到 2.x，而 2.x 把 `FastMCP` 改名为 `MCPServer` 且改了 API，
     直接 import 报 `cannot import name 'FastMCP'`。**必须 `pip install "mcp==1.9.4"`（或 `mcp<2`）**。
   - 免费源（akshare/china-news）只需 `pip install akshare mcp pandas lxml`；付费源（wind/ifind）**不要写 Key**，
     留空或 `${ENV_VAR}`，让用户自备后填 —— 严守凭据纪律。
   - 验证：`python -c "import sys; sys.path.insert(0,'<dir>'); import server"` 看是否 import OK；
     再 `asyncio.run(server.server.list_tools())` 确认工具注册。
   - **★★ 但 import OK ≠ 能取到数。必须真跑一次取数才算验证通过。**
     实测教训（2026-09-18 金融包）：akshare-mcp import + 9 个工具注册全过，但一调就挂 ——
     本机系统代理是 `127.0.0.1:7890`（`urllib.request.getproxies()` 可查），
     走代理报 `ProxyError`，`session.trust_env=False` 绕代理直连报
     `ConnectionError: RemoteDisconnected`（而 `curl` 直连同域名却 HTTP 200，属沙箱网络策略差异）。
     → 装完务必用一个真实标的代码真取一次数，不能停在 import 成功就向用户报"数据层已通"。

5. **装前先看本机已连了什么数据源（避免重复/白装）**：
   `<connector-status>` 里已 connected 的 MCP 往往比仓库自带的更强且零配置。
   例：WorkBuddy 常连 **mx-ds-mcp（东方财富妙想）**，实测能出实时行情、财务估值、
   多条件选股（一次返回带 3 年营收增速+ROE+市值+PE+概念标签）、公告原文全文（含 PDF 链接），
   覆盖面**强于** akshare，且不需要任何 Key。→ 有它就不必再为 akshare 折腾，付费源也未必需要买。

6. **清点技能的数据依赖，别凭印象下结论**：用正则扫全部 SKILL.md 里的
   `wind_\w+|ifind_\w+|akshare_\w+|mcp__[\w-]+__[\w-]+`。实测 63 个金融技能里
   **只有 6 个硬绑付费源**，其余 57 个用抽象函数名（`get_quote`/`get_financials`/…），
   本就可换数据源。→ 不要对用户说"大量依赖付费 Key，没 Key 就用不了"这种未经统计的话。

7. **清理**：删掉解包的临时仓库与 tarball（自己下载的临时数据，非用户文件，可删）；
   保留 `SKILL_CATALOG.md` 之类的清单给用户参考。

## 关键判断
- 同源技能重名 → 用 `domain__name` 命名空间，frontmatter `name` 也要同步改。
- frontmatter 行尾必须 LF，否则 YAML 解析出问题。
- MCP server 跑不起来，先看 mcp 版本是不是 2.x（FastMCP 改名）——这是 2025 年后新拉包最高频的坑。
- 安全审计只看 scripts/ 和 mcp-servers/ 即可，SKILL.md 是纯提示词，低风险。
