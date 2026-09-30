---
name: xelatex-chinese-math-publication
description: 在 Windows 本机用 XeLaTeX 把「中文正文 + 专业数学公式 + 参考文献」排成论文出版级 PDF 的完整可跑流程：MiKTeX 的 OpenType 数学字体缺失怎么办（tex-gyre / Cambria Math 兜底）、ctexart + unicode-math + TeX Gyre Termes 字体配对、GB/T 3102.11 正斜体纪律在 LaTeX 里的写法、xelatex→biber→xelatex 链、中文本地化必须改的那五个名字、黑白印刷下"颜色不能是唯一语义通道"（等效灰阶怎么算、线型/标记二通道怎么加、怎么机检）、以及"编译成功≠排对了"的四道验收与门禁负样本回归件的写法。当用户说"数学符号要论文出版水平 / 用 LaTeX 排版 / 转成 PDF 出版物 / 排书 / 黑白印刷要能分辨"或 HTML 手搓公式已经不够用时使用。
agent_created: true
---

# 中文数学内容 → XeLaTeX 出版级 PDF

## 一句话架构

**ctexart 管中文，unicode-math + OpenType Math 字体管公式，biber 管文献，XeLaTeX 链负责收敛。**
不要用 `pdflatex`（中文和 OpenType 数学字体都不行），不要用 pdfLaTeX 时代的 `newtxmath` 老路子。

## 什么时候该上 LaTeX（判断，不是偏好）

| 场景 | 用什么 | 理由 |
|---|---|---|
| 有滑杆／画布交互、要在浏览器里看 | 自包含 HTML | LaTeX 做不了交互 |
| 纯阅读／印刷／存档，公式密度高 | **XeLaTeX** | 根号横线、分式、上下标、间距由 TeX 排版算法保证 |
| 公式多但必须留 HTML | HTML + KaTeX/MathJax | 别再手搓 `::before` 画根号横线 |

**手搓 CSS 数学有天花板。** 用 `.rad::before` 画根号横线这类做法，一旦盒子宽度、
继承属性、字体度量任何一个变量动了，横线就会错位——而且错了还不一定被检查发现。
**公式密度一上来，就换 TeX，不要死磕 CSS。**

## 一、本机环境（2026-09-15 实测）

```
MiKTeX  26.5        C:\Users\zyx32\AppData\Local\Programs\MiKTeX\miktex\bin\x64\
  可执行：pdflatex xelatex lualatex latexmk bibtex biber miktex initexmf
Python  C:\Users\zyx32\.workbuddy\binaries\python\envs\default\Scripts\python.exe（有 pymupdf）
Chrome  C:\Program Files (x86)\Google\Chrome\Application\chrome.exe
```

**⚠️ MiKTeX 默认 `AutoInstall=2`（询问）**，非交互调用时缺宏包会直接失败。改成 1：

```bash
initexmf --set-config-value="[MPM]AutoInstall=1"     # 原值 2，还原就用 2
```

**⚠️ 首次装 tex-gyre 字体后，`fc-list` 可能一时看不见**，重开一次 shell 或跑 `fc-cache -f`。

## 二、字体：这一步最容易卡死

`\setmathfont{TeX Gyre Termes Math}` 报 **"The font ... cannot be found"**，不是名字写错，
是 MiKTeX 里根本还没装这套 OpenType 字体。先装：

```bash
miktex packages install tex-gyre tex-gyre-math
```

装完在 `MiKTeX\fonts\opentype\public\tex-gyre{,-math}\` 下应有
`texgyretermes-{regular,italic,bold,bolditalic}.otf` 与 `texgyretermes-math.otf`。
XeLaTeX 靠 fontconfig 找字体，用 `fc-list | grep -i termes` 确认它看得见。

**兜底方案（不装任何包）**：Windows 自带真正的 OpenType MATH 字体 **Cambria Math**
（`C:\Windows\Fonts\cambria.ttc`），正文配 Cambria，是 Word 公式编辑器的同款组合。
质量可靠，只是和 Times 不是一套。

## 三、最小可编译模板

见 `scripts/template.tex`。核心就这几行：

```latex
\documentclass[11pt,a4paper]{ctexart}
\usepackage{unicode-math}
\setmainfont{TeX Gyre Termes}
\setmathfont{TeX Gyre Termes Math}
\usepackage{amsmath,booktabs,amsthm}
\usepackage[backend=biber,style=numeric]{biblatex}
\addbibresource{refs.bib}
```

**中文本地化必须逐个改**（默认全是英文，漏一个就露出来）：

```latex
\renewcommand{\contentsname}{目录}
\renewcommand{\figurename}{图}
\renewcommand{\tablename}{表}
\renewcommand{\proofname}{证明}
```

**⚠️ 参考文献标题是个例外，前两种常见写法都无效（2026-09-15 实测）：**
`\renewcommand{\refname}{参考文献}` ✗ 和
`\DefineBibliographyStrings{english}{bibliography={参考文献}}` ✗
**唯一可靠的是显式定义 heading：**

```latex
\defbibheading{bibliography}[\refname]{\section*{参考文献}}
```

（用 `\usepackage[backend=biber]{biblatex}` 时。若改用传统 `bibtex` + `\bibliographystyle`，
那就回到 `\renewcommand{\refname}`。）

**题注分隔符**：默认是半角冒号 `表 1:`，中文体例不用。加
`\usepackage{caption}\captionsetup{labelsep=quad}` 改成空格。

## 四、GB/T 3102.11-1993（=ISO 80000-2）的正斜体，在 LaTeX 里的写法

LaTeX 的 `\symup` / `\symit` 让这条规范**逐字符可控**——这是 CSS 做不到的。

| 该正体 | 写法 |
|---|---|
| 其值不变的数学常数（π、e、i²=−1） | `\symup{\pi}`、`\symup{e}`、`\symup{i}^2=-1` |
| 已知函数名（sin、exp、ln、cot、Γ） | `\sin` `\exp` `\ln` `\cot` `\Gamma`（amsmath 已内建正体） |
| 微分算子 | `\mathrm{d}f/\mathrm{d}x` 或 `\operatorname{d}` |
| 数字 | 天然正体 |

变量 `x`、参数 `a`、角量 `A`、`δ`、`ε`、`R` 保持数学斜体。
**注意 `δ` 有两种身份**：作变分算子（δx）正体，作变量／角量斜体。

实测：`\symup{\pi}`（正体）与 `\pi`（斜体）在 TeX Gyre Termes Math 下**字形真的不同**，
不是合成倾斜——放大截图里两腿一斜一垂直。

## 五、编译链

```bash
xelatex -interaction=nonstopmode 文件.tex
biber 文件
xelatex -interaction=nonstopmode 文件.tex
xelatex -interaction=nonstopmode 文件.tex
```

四步都要。少跑一遍 biber，参考文献就是 `[?]`；少跑最后一遍，目录页码与交叉引用不收敛。
一键跑法见 `scripts/build.py`。

## 六、验收：编译成功 ≠ 排对了

1. **零 `!` 错误**：`grep -n "^!" 文件.log`
2. **零缺字**：`grep -c "Missing character" 文件.log` 必须是 0。
   **中文缺字不报错、只是那个字不印出来**——只看"编译成功"会漏掉整段中文。
3. **零未定义引用**：`grep -c -i undefined 文件.log`
4. **肉眼**：`pymupdf` 渲 2.6–3× PNG 看版式。字形类问题（正体 π 是不是真正体、
   根号钩与横线接上没有）**只能靠眼睛**，断言测不出来。
5. **门禁必须配"负样本回归件"**：任何会自动 FAIL 的机检判据，都要有一份"故意把语料
   做坏 → 门禁必须 FAIL；好语料必须 PASS"的回归脚本，且**挂进一键验收**。
   不挂 = 平时没人喂坏样本 = 长期退化成"永远 PASS"。
   ⚠ 多条判据要**各自单独**造坏样本：两条错若落在同一处会互相抵消，报出假阴性。
   ⚠ 造负样本后要**校验改动确实发生**（替换数 > 0），否则静默失配会得出
   "门禁不报警"的错误结论——那比不测更糟。
6. ★ **图"够不够大"要量，不能只看有没有报错**。图排小了不会报任何错，门禁也全绿：
   实测一张"逐行向右生长"的图，最宽只到 60.5mm，**墨迹仅占版心 41%**
   （同书其余图 72–100%）——编译 0 错、图注满行而图只半页宽，读者只会觉得"排坏了"。
   量法：`get_drawings()` 并集宽 ÷ 版心宽；顺手也在人眼终检时对每张图跑一遍。

```python
import pymupdf
d = pymupdf.open('文件.pdf')
for pg in d:
    r = None
    for dr in pg.get_drawings():
        b = pymupdf.Rect(dr['rect']); r = b if r is None else (r | b)
    if r: print(pg.number + 1, '墨迹宽 %.1fpt = 版心的 %.0f%%' % (r.width, 100 * r.width / 412.3))
```

   ⚠ 这个并集**会被非图矢量吃掉**：页眉横线、正文里的框式 div（整版心宽、几十上百 pt 高）
   都在 `get_drawings()` 里 ⇒ 要**先与版心求交并剔掉退化矩形**（宽或高 < 0.5pt），
   更稳的做法是**以图题为基准开窗口**取（见第七节）。

```python
import pymupdf
d = pymupdf.open('文件.pdf')
for i, p in enumerate(d):
    p.get_pixmap(matrix=pymupdf.Matrix(2.6, 2.6)).save('第%d页.png' % (i+1))
```

## 七、踩过的坑

- **`We must be careful` 类迷惑**：日志里 `Running miktex-makemf.exe...` / `hbf2gf` /
  `Couldn't open 'TeX Gyre Term.cfg'` 这些是**干扰项**，真错误在更下面的
  `! Package fontspec Error:`。查错永远从最后一条 `!` 往上读。
- **不要把 `\setmathfont` 放在 `\setmainfont` 之前**——unicode-math 要先生成数学表。
- **参考文献标题改不动**：见第三节，`\renewcommand{\refname}` 与
  `\DefineBibliographyStrings` 都不行，只有 `\defbibheading` 有效。
- **刚 `cp` 覆盖过 .tex 就立刻编译，可能报空错误**（文件锁），重跑一次即可。
- **控制台是 GBK 时**，Python 往 stdout 打中文文件名会乱码（`绗�1椤�`），
  不影响生成的文件，但别拿这个乱码当文件名去引用。
- **Latin Modern Math / STIX Two Math 也在 MiKTeX 里**（`fonts/opentype/public/` 下），
  想要 LaTeX 原味就用 `\setmathfont{Latin Modern Math}`。
- **行尾悬算符**：TeX 允许在关系符后断行，`≈` 可能出现在行末。要禁就在导言区设
  `\binoppenalty=10000 \relpenalty=10000`（代价是可能溢出）。
- **中文与行内公式之间的间距**由 xeCJK 自动处理，不要手写空格；
  但 `$...$` 前后若紧跟标点，检查一下 `.` `,` 用的是全角还是半角。
- **用 `\NewDocumentCommand` 包装 TikZ 片段时，宏体里不要写路径终止符 `;`**——
  由调用点的 `;` 收尾。宏体自带 `;` 而调用点又写一个，多出来的那个 `;` 会被当**正文**
  排，于是每调一次报一条 `Missing character: There is no ; in font nullfont!`。
  **编译"成功"、页数正常、只有日志脏**，最容易漏（实测全书 18 个标记 × 3 遍 = 58 条）。
  隔离手法：写个只含该宏的最小 .tex，`--fast` 单遍编，`grep -c nullfont *.log`。
- **pymupdf 判线型别用 `if not d["dashes"]`**：实线给的是 `"[] 0"`（**非空串**），
  这么写会把实线全归成虚线、白查一轮。可靠判据取 dash 数组的首个数：TikZ 的
  `densely dotted` 实测 `[.29889 .99628]`、`dashed` 实测 `[2.9888 2.9888]`，
  以 **1.0** 为界分点线/虚线。
- **语义色反查要建 `{hex: 名字}` 表**：调色板字典是「名字→hex」，而 PDF 抽出来的是 hex，
  写成 `if hex in 调色板` 恒为假（拿值查键），会误报"这个颜色一处都没用到"。
- ★ **判"线型"时要排除小面积实心填充体**：箭头头、方形/圆形标记都是**填充几何体**，
  光看 `fill` 颜色会把它们当成"这条语义色也有实线"。实测一个 1.7×2.2pt 的箭头头
  就让"两色必须虚实分明"的判据**误报**。判据：面积 < 100pt² 的填充体**不参与线型统计**
  （它们本来就承载不了线型信息）。⚠ 改这类判据必须配**判别性正样本**：
  造一支"含箭头的好语料"，用**修改前**的门禁跑它，必须 FAIL —— 这才是"判据原来错了"的证据。
- ★ **从 PDF 裁图做预览时，`get_drawings()` 要按图题开窗口**，不能对整页取并集：
  页眉横线（宽=版心、高 0）与正文里的框式元素都在里面。实测整页并集会产出
  1184×1512 的"整页切图"而不是一张图。另外 **图注要取整个 block**：
  `\fno`／`\label` 常让图号**单独占一行**，只匹配那一行会得到"图 6-1"四个字的窄框，
  图注正文被切在半句上（实测裁到 378.9pt）。

- ★★ **整页高的表用 float 包的 `[H]` 会把正文页"劈开"**：`[H]` 是"就地非浮动盒子"，
  装不下时**既不推迟也不警告、直接强制换页**。症状特别隐蔽 —— 日志干净、连 Underfull 告警都没有
  （`\flushbottom` 把橡皮长度吃掉了），但**段间距被拉到 25–30mm**（正常 3–6mm），下一页空一大片。
  **诊断法**：别读图，量相邻文字块的包围盒间距（pymupdf `get_text("blocks")` 排序后取
  `b.y0 - a.y1`），>25mm 就是被拉伸。**修法**：独立表题表用 `[htbp]`（大表自动成**浮动页**、
  垂直居中 —— 整页表独占一页本就是常规排法）；**框内表只能 `[H]`**（`\begin{table}[htbp]`
  放进 `tcolorbox` 会报 `Not in outer par mode` —— 浮动体进不了盒子）。对照实验值得先做：
  `[H]` / `[H]+raggedbottom` / `[htbp]` / `[t]` 各编一遍量间距，别凭推断选。
- ★★ **`\topfraction` 是 dimen，且按"类默认版心高"算，不跟 `geometry` 走**：`latex.ltx` 在
  format 期取 `.7\textheight`，那会儿 `book`/`ctexbook` 11pt 的 `\textheight` 还是 550pt
  （≈193.7mm）⇒ 阈值 ≈135.6mm；`geometry` 之后把版心改成 220mm 也**不重算**。所以
  "表 155mm／版心 220mm／比例 0.70 ≤ `\topfraction` 0.7 所以能上页顶"这条推算是**错的** ——
  大 float 永远上不了页顶，只会掉进浮动页。表现为 `[t]`/`[tb]` 时"表漂到章末那一页"，
  就是这个阈值在拒收。要放开得在 document 内显式写 `\topfraction=.85\textheight`
  （**赋值点必须在 `\begin{document}` 之后，`\textheight` 才是新值**；写成 `\topfraction=.85`
  是赋 0.85pt，会把排版搞崩 —— 实测直接编出 117 页乱页）。而它是**全局量**，
  改了会挪动已有各章分页，单章试制阶段别动。

```python
cap = None
for blk in pg.get_text('dict')['blocks']:
    if any(''.join(sp['text'] for sp in ln['spans']).strip().startswith('图')
           for ln in blk.get('lines', [])):
        bb = pymupdf.Rect(blk['bbox']); cap = bb if cap is None else (cap | bb)
box = pymupdf.Rect(48, cap.y0 - 260, 475, cap.y0 + 2)     # 只取图题上方这一段
```

## 八、从已有 HTML 迁移

若已有自包含 HTML 版（`.m` 元素带 `data-tex="\sqrt{2}"` 这类纯 LaTeX 源），
**公式不用重录**——直接抽 `data-tex` 就是现成的 LaTeX。要转的是散文骨架：
`.ch-open` / `.keys` / `.trap` / `.strict` / `p.note` 这些类对应哪个 LaTeX 环境，
映射表定下来以后就能半自动批量转。

- ⚠ **`<table>` 最容易被"块切分"整块漏掉**：若分块正则只列 `div/p/h2/figure` 之类而**没有 `table`**，
  表内第一个 `<p>` 会被当成"下一个块"，**整张表从它头上跨过去，连一条"未处理的块"警告都不留**。
  症状："HTML 里有表、编译 0 错、所有门禁全绿、纸书上就是没有这张表"。**迁移前先数**：
  HTML 里 `<table>` 的个数 ↔ `grep -c tabular 正文/*.tex`（本机实测：12 章 `tabular` 全为 0，
  三张表没进纸书，而没有任何门禁在看这件事）。
- 表格落地：booktabs 三线表 + `p{}` 列 + `\RaggedRight\arraybackslash`；列宽优先吃 HTML 自带的
  `style="width:N%"`，否则按各列**最长内容**比例分，下限留 4.5 个汉字宽（`\small`=10pt／
  `\footnotesize`=9pt 分别算）。**列宽预算 = 目标宽 − 2(n−1)·tabcolsep** —— `@{}` 只去掉
  **两端**的 tabcolsep，所以是 `2(n−1)` 而非 `2n`；按 `2n` 扣会把表排窄（进 `tcolorbox` 则
  反过来探出内边距，且小于编译告警阈值、日志与门禁都看不见）。表题要**全文搜**
  （`<caption>` 可以写在 `</tbody>` 之后），并剥掉网页自带编号，否则印成「表 12-1　表 12-1」。

## 九、黑白印刷：颜色不能是唯一语义通道

书里若用一对颜色承载论证结构（如"旧直觉→危机"用赭红、"修正→新理论"用深青），
**先算它们在黑白下的等效灰阶**——两个颜色的相对亮度可能几乎相同：

```python
def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def rel_lum(h):                       # h = "7a2e22"
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    return 0.2126*_lin(r) + 0.7152*_lin(g) + 0.0722*_lin(b)
def gray255(h):
    return (rel_lum(h) ** (1/2.4) * 1.055 - 0.055) * 255
```

实测踩过的例子：`#7a2e22`(赭红) = 70.5、`#0f4c5c`(深青) = 69.5 —— **只差 0.9/255，
黑白下同灰**。阈值取 **20/255**（低于这个数，一次复印就不可分）。只有 Δ < 20 的色对
才**必须**加二通道；Δ ≥ 20 的（如赭黄 99.9）颜色自己就分得开，不必强求。

**二通道就地叠加，不替换颜色**（彩色版不能变差）：线型（实/虚/点）、标记形状（●/▲/■）、
填充图案、字族（黑体 vs 宋体，中文可用；斜体对中文无效）。

> **⚠ 最大的坑：线型这个通道往往已经被"主线 vs 辅助线"占用。**
> 实测改前 accent/accent2/warn 三色的线型集合**完全相同**（都在用 `dashed` 表示投影线/
> 参考线），也就是说线型当时**不携带任何语义信息**。不先把虚线腾出来，
> 把 semB 设成虚线只会跟"辅助线"打架。做法：辅助线一律改走**点线**
> （`guide`/`guidem`/`guidem2`/`guidew` 四个样式），「虚线」从此专指 semB。

**机检怎么落地**（查规则，别查死配色——凡 Δ<阈值的色对都要成立，换配色自动跟着变）：

1. **源层**：不可分色**不得裸写**。二通道锁在 `semA`/`semB`/`sem?mark` 的定义里，
   裸写 `\draw[accent, …]` 等于绕过二通道，而且**绕过时不留痕迹**。用
   `re.compile(r"\[(" + "|".join(须二通道的色) + r")[,\]]")` 扫图源码。
   ⚠ 图若由脚本生成，**生成器本身也要扫**——只扫 `.tex` 会漏"改了生成器没重跑"。
2. **渲染层·线型**：从 PDF 抽描边，按颜色分组，扣掉共用的辅助点线后，
   每色的**专属线型集合必须非空且两色互斥**。
3. **渲染层·标记**：小标记（面积 < 100 pt² 排除底纹色块）形状必须不同——
   圆的 `get_drawings()` items 含 `'c'`（贝塞尔弧），方的全是 `'l'`（直线段）。

**语义色文字通常不用加二通道，但理由必须是"文字自指"**（文字内容本身指明它指谁，
如「底边（两个底角都是直角）」）。**别把豁免理由写成"语义由旁边的标记承担"**——
若标签附近根本没有标记，那句话就是假的。这一层无法机检，列目检并留清单。
