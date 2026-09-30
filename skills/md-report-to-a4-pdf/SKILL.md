---
name: md-report-to-a4-pdf
description: 把 Markdown（或网页/长文）排成一份「能直接给人看」的中文 A4 PDF 报告：封面出血、目录、章节卡片、表格、页眉页脚真实页码、PDF 书签。基于本机 Chrome + puppeteer-core + pymupdf，不装 wkhtmltopdf/weasyprint。当用户说「排版好转换成 PDF / 做成报告 PDF / 供下载的 PDF / 把 md 导出 pdf」时使用。
agent_created: true
---

# Markdown → 中文 A4 报告 PDF（Chrome + pymupdf）

## 一句话架构

**HTML 负责版式，Chrome 负责渲染，pymupdf 负责盖章与拼装。**

```
build_report.py   手写 md→HTML（自己写渲染器，别上 markdown 库，层级/样式才可控）
   ├─ cover.html  @page{margin:0}，单独渲染成 1 页，用来做满版出血封面
   └─ body.html   @page{margin:16/15/18/15mm}，正常分页
render_pdf.js     puppeteer-core + 本机 Chrome，displayHeaderFooter:false
finalize.py       pymupdf：拼封面 + 盖页眉页脚（中文页码）+ 写书签 + 子集化字体
```

## 八个必须知道的坑（都是实测踩出来的）

### 1. 负边距做不出出血；puppeteer `margin` 会压掉 CSS `@page{margin}`

给 `.cover` 写 `margin:-16mm -15mm -18mm -15mm` **没用**，Chrome 会把它裁回页面内容框。

**实测确认（2026-09-12 做 688981 报告时）**：`page.pdf({margin:{top:'0',right:'0',bottom:'0',left:'0'}})`
**会覆盖** CSS 里的 `@page{margin:16mm 15mm 18mm 15mm}` —— 症状是正文从预期 9 页缩成 4 页
（页面可写满整页，内容重新流动）。**正文 PDF 调用 `page.pdf()` 时不要传 `margin` 参数**，
让 CSS 的 `@page` 独占控制权。

→ 正解：**封面单独一个 HTML**，在自己 `<style>` 的最后追加
`@page{size:A4;margin:0;} html,body{width:210mm;height:297mm;margin:0;padding:0;overflow:hidden;}`，
再渲染成独立 PDF，最后只取它的第 1 页拼进去。
封面即使多出一页空白也无所谓——`insert_pdf(cover, from_page=0, to_page=0)` 只取第 1 页。

### 2. Chrome 的页眉页脚没法「首页不要」

`displayHeaderFooter:true` 会盖在每一页上，封面页会被毁掉。
→ 正解：**别用 Chrome 的页眉页脚**，改用 pymupdf 逐页盖印，顺带还能算准真实页码。

### 3. 用 pymupdf 盖中文页眉 → 文件从 1.3MB 涨到 13MB

`page.insert_text(..., fontfile=r"C:\Windows\Fonts\msyh.ttc")` 会**每页各嵌一份字体**，
21 页就 11MB+。
→ 正解：保存前调 `doc.subset_fonts()`。实测 **13.14MB → 1.29MB**。
（返回 `None` 是正常的，不是失败。）

### 4. Chrome `outline:true` 生成的书签标题会重复拼接

形如 `最终决策（组合经理）最终决策（组合经理）`（`<h2>` 里套了 `span` 时尤其明显）。
→ 正解：`re.match(r"^(.+?)\1$", title)` 折叠；再用 `min(level)` 归一化层级、
`lvl > base+2` 砍掉过深的条目（79 条 → 55 条，刚好是「章 + 分报告标题 + 小节」）。

**补充（实测）**：`outline` **默认是 `false`**，必须显式写 `page.pdf({..., outline: true})`。
不写的话 body.pdf 里**一条 outline 都没有**（症状：finalize 报 "no outline found"），
只能靠关键词定位兜底。

**⚠️ 折叠逻辑的陷阱（2026-09-12 修 bug）**：
```python
# ❌ 错：多加了一个"折叠结果要等于前一项"的约束
m = re.match(r"^(.+?)\1$", title)
if m and m.group(1) == cleaned[-1][1]:   # ← 这个约束是多余的
    continue
# ✅ 对：只要自重复就折叠，再单独判断是否与前一项重复
m = re.match(r"^(.+?)\1$", title)
if m:
    title = m.group(1)
if cleaned and title.strip() == cleaned[-1][1]:
    continue
```
加了那个约束后，"情景推演情景推演" 的前一项若是别的标题（如"关键点位汇总"），
`m.group(1) != cleaned[-1][1]` → **不跳过 → 重复标题漏网**。
自重复是标题**自身属性**，跟前一项无关，不该混在一起判断。

### 5. 预览图有白边 ≠ PDF 有白边

图片查看器会给 PNG 加 letterbox，看起来像出血失败。
→ 正解：**采样四角像素**，别用眼睛判断。

**API 变化（pymupdf 1.28+）**：`Page.pixel(x, y)` **已不存在**（会报 AttributeError）。
替代写法 —— `get_pixmap()` 后手动索引 `samples` 字节数组：

```python
pix = doc.load_page(0).get_pixmap(dpi=72)
def px(pix, x, y):
    i = (y * pix.width + x) * pix.n
    return tuple(pix.samples[i:i+3])
print(px(pix, 3, 3))    # 封面左上角，应为深色 → 出血成功
print(px(pix, 10, 10) if False else '')  # 正文页同理应为 (255,255,255)
```

### 6. `insert_pdf` 不复制 outline

拼完 `final = cover + body` 后，`final.get_toc()` 是**空的** —— pymupdf 的 `insert_pdf`
只搬页面对象，不搬书签。
→ 正解：从**源文档**读 `body.get_toc()`，手写 `final.set_toc(...)`，
页码整体 `+1`（封面插在了最前面）。源文档也没 outline 时，用「关键词定位页码」兜底：
逐页取文本，要求关键词出现在**页面前 1/3** 内（章节标题在页首），
并**跳过目录页**（目录页列了所有章节名，会污染匹配）。判断目录页：
`"目录" in head and head.count("、") >= 4`。

### 7. Markdown 里连续几行 `**字段**：值` 会被合并成一段

手写 md→HTML 渲染器时，「段落 = 合并连续非空行」这条规则会把
```markdown
**生成日期**：2026-09-12
**框架**：TradingAgents v0.4.2
```
合并成**一个** `<p>`。两个后果：
- 封面元信息只剩第一项（按第一个冒号切分后，后面全挤进 value），其余被显示成"备注"
- 正文「交易员决策」的 Action / Entry / Stop / Position 四个字段挤成一行，可读性下降

→ 正解：段落合并逻辑里加一条中断规则 ——
`re.compile(r"^\*\*[^*]+\*\*\s*[:：]")` 匹配到的行**单独成段**，且它也是内层循环的 break 条件。

**附带坑**：中文全角冒号 `：`(U+FF1A) ≠ 半角 `:`(U+003A)。
解析 `key：value` 用 `re.search(r"[:：]", s)`，不要用 `s.index(":")` 或 `":" in s`，
否则带中文冒号的字段**全部静默解析失败**。

### 8. （环境）puppeteer-core 的 require 路径

Git Bash 里 `NODE_PATH=... node script.js` 对 `require('puppeteer-core')` **不生效**
（实测 MODULE_NOT_FOUND）。→ 直接写绝对路径：

```javascript
const puppeteer = require('C:\\Users\\zyx32\\.workbuddy\\binaries\\node\\workspace\\node_modules\\puppeteer-core');
```

### 9. SVG 图表的 viewBox 高度必须由内容**推算**，不能写死

往报告里嵌 SVG 图表时，`viewBox="0 0 660 214"` 这种写死的高度，在**行数变化时会静默裁掉内容** ——
不报错、不警告，肉眼看只是「少了两个数」。

**实测（2026-09-21 做中芯国际目标价对照报告）**：一张 4 行的分组条形图高度写死 214，
实际需要 `14 + 2×(21 + 2×34) + 26 = 216` → 最后两行（H 股那组）连同数据一起被裁到画布外，
底部说明文字还压在条形上。改成按「分组数 × (组标题高 + 2×行高) + 页脚」算出来即正常。

配套两条：
- 数据缺失要有**显式分支**（画一行「查不到」），否则缺数据的条目会**静默消失**，读者以为没这家机构。
- 横向条形图的「标签 → 条 → 数值」三段要算好 x 余量：给数值预留固定宽度（本例 78px），
  否则最长的条形会把数值顶出画布。

---

## 关键参数（A4，pt）

```python
W, H = 595.276, 841.89
LEFT, RIGHT = 42.52, W - 42.52        # 15mm
TOP_RULE_Y,  HEAD_BASE_Y = 40.0, 32.5 # 页眉横线 / 基线（上边距 16mm 内）
BOT_RULE_Y,  FOOT_BASE_Y = 793.5, 808.5
FS, GRAY, RULE = 7.2, (0.58,0.62,0.67), (0.886,0.906,0.925)
```

`insert_text` 的 y 是**基线**，PyMuPDF 原点在左上。右对齐用
`fitz.Font(fontfile=...).text_length(s, fontsize=FS)` 自己算宽度。

中文字体（本机实际可用）：`msyh.ttc`（微软雅黑，首选）、`Deng.ttf`（等线）、
`simhei.ttf`（黑体）。**没有** Noto / 思源。

## 分页策略

- 长报告：每个大章节 `break-before:page`。
- **短章节连续排**（本例决策层 2–5 章各半页，强行分页会浪费 3 页）：
  `.chapter.flow{break-before:auto;margin-top:12mm}`，并配 `.flow .ch-head{border-top:1px solid #dde5ec;padding-top:6mm}`。
- 表格 `break-inside:auto` + 行 `avoid` + `thead{display:table-header-group}`（跨页自动重复表头）。
- 表头加 `white-space:nowrap`，否则「尝试次数」这种 4 字表头会被压成两行。
- 相邻两张表要留间距：`table{margin:2mm 0 4.5mm}`，否则会贴在一起。
- ★ **别对全部大章节强制分页（2026-09-21 实测）**：一份 8 节的报告若每个 `h2` 都 `break-before:page`，
  短节之间会留下**几乎全空的残页**（实测 p3 只有 273 字、其余整页空白）。
  改法：只给「有长表格的节」和「末节免责」强制分页，其余用 `.flow{break-before:auto}`；
  并给 `blockquote` 加 `page-break-inside:avoid`、给图表标题 `.chart-cap` 加 `page-break-after:avoid`
  （否则会出现「图标题在页尾、图在下一页」的孤行）。
  本例修完 **10 页 → 9 页**，每页字符量从 273~1031 收敛到 354~1031。
- 正文里**不要重复封面的大标题**：md 的 H1 与封面/hero 重复，会白占半页 —— 渲染时直接剔除。

## 配色约定（A 股）

- **涨 = 红 `#b3261e`，跌 / 看空 / 减持 = 绿 `#0f7b4f`**（与欧美相反，别搞错）。
- 「数据可信 / 数据缺失」这类**非方向性**语义**不要用红绿**，改用蓝（`#12395f`）与琥珀（`#d08a12`），
  否则会和涨跌语义打架。封面/目录要附一行配色图例。

## 环境事实（本机）

- Chrome：`C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`（Edge 也在）
- puppeteer-core 装在 `C:\Users\zyx32\.workbuddy\binaries\node\workspace\node_modules`。
  `executablePath` 指向本机 Chrome，**不要**下 Playwright/Chromium（省 150MB）。
  **require 用绝对路径**（见坑 8），`NODE_PATH` 在 Git Bash 里不可靠。
- pymupdf 装法：`<managed-python> -E -m pip install pymupdf`
  （`-E` 挡沙箱 shim，见全局记忆）。本机两个可用解释器：
  - 托管 Python：`C:\Users\zyx32\.workbuddy\binaries\python\versions\3.13.12\python.exe`
  - 目标项目 venv：`<项目>\.venv\Scripts\python.exe`
  两个都装了 pymupdf 1.28.2。渲染脚本用托管 Python，`outline` 等 puppeteer 参数不依赖它。
- `import fitz` 已废弃，现在写 `import pymupdf as fitz`。
- Windows 控制台默认 GBK，Python 打印中文会乱码且被 `grep` 判定为 binary。
  → 脚本开头写 `sys.stdout.reconfigure(encoding="utf-8")`；
  验证输出时用 `| iconv -f utf-8 -t utf-8 -c`，**不要**用 `grep` 过滤（会把整段吞掉）。
- PowerShell 工具 stdout 不回显：命令输出一律 `| Out-File -Encoding UTF8 文件` 再用 Read 读；
  **不要**用 `>`（PS 5.1 写 UTF-16LE，Read 工具读不了）。

## 三个脚本模板

`scripts/` 目录下有三个可直接复制的模板（2026-09-12 用它们产出过 10 页报告）：

| 文件 | 作用 | 改哪里 |
|---|---|---|
| `scripts/build_report.py` | md → cover.html + body.html | `MD_PATH`（源 md）、`BODY_CSS` 配色、`make_cover_html` 里的封面文案 |
| `scripts/render_pdf.js` | 两个 html → 两个 pdf | `CHROME` 路径、`puppeteer-core` 的 require 绝对路径 |
| `scripts/finalize.py` | 拼封面 + 页眉页脚 + 书签 + 子集化 | `DOC_TITLE`/`DOC_SUBTITLE`/`HOLD_TAG`、`chapter_titles`（兜底书签用）、`FINAL_PDF` 文件名 |

依赖顺序：`build_report.py` → `render_pdf.js` → `finalize.py`。
中间产物（cover/body 的 html+pdf）**保留**，用户改文案后可只重跑后半段。

## 验证清单（每次交付前）

1. `pymupdf` 打开成品，报 `page_count`。
2. 封面第 1 页四角像素采样，确认是深色（出血成功）。
3. 正文某页四角是白色（说明页边距生效）。
4. 抽看 3–4 页：表格间距、表头不折行、章节标题不孤行、末页无重复注释。
5. 文件体积：正常应在 1–3MB；>5MB 基本就是字体没子集化。
6. ★ **逐页统计文字字符数**，`<350` 即疑似残页 —— 比肉眼看快且不漏：
   ```python
   for i in range(doc.page_count):
       n = len(doc.load_page(i).get_text().replace(chr(10), "").replace(" ", ""))
       print("p%-3d %d%s" % (i + 1, n, "  ← 偏空" if n < 350 else ""))
   ```
7. 有内嵌 SVG 图表时，**数一数图上的数据条数是否等于源数据条数** ——
   少一条就是 viewBox 裁掉了（见坑 9），PDF 不会报任何错。
