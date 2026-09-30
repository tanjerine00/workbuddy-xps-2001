---
name: selfcontained-html-lesson-verify
description: 在本机（Windows + WorkBuddy）产出「自包含交互式 HTML 教学页 / 演示页」并做交付前自检的完整流程：标签平衡追踪、内嵌 JS 语法与数值断言、无头 Chrome 截图验收、用 dispatchEvent 注入状态做交互自动验收（SVG 元素没有 .click()，会误导成"交付物有 bug"）、多章合成单册并导出 A4 PDF（Chrome 不支持 orphans/widows、图号必须按文档顺序、用 pymupdf 复核页填充率）、数学符号的**字符层 + 排字层**双门禁（裸根号 / Unicode 上下标 / 斜体范围与正体常数 π、e / 行尾悬算符 / 分数斜线 U+2044 会挤成"√107"），以及本机三个已知卡点（Bash 工具 PATH 损坏、PowerShell 不回显 stdout、file:// URL 带百分号编码被安全守卫拦下）。当你交付单文件 HTML（含 canvas/SVG 交互）、做多章成册/PDF、要求"数学符号达到出版水平"、或页面"看起来写对了但打开是空白"、或"截图看着正常但点了没反应"时使用。
agent_created: true
---

# 自包含交互式 HTML：产出与交付前自检

## 一句话结论

单文件 HTML 交付后**必须跑三步自检**，缺一步都可能交付一个"打开是空白"的页面：
① 标签深度追踪 → ② 内嵌 JS 用 `node --check` 查语法 + 抽出函数跑数值断言 → ③ 无头 Chrome 截图肉眼看。
**最关键的是第 ② 步**：内嵌 JS 一旦有语法错误，整个 `<script>` 静默不执行，
页面上文字全在、canvas 全空——看起来像"渲染问题"，其实是语法问题。

## 本机三个卡点（先记住，否则白折腾）

1. **Bash 工具 PATH 会反复坏 —— 2026-09-14 二次诊断后结论已更正**：
   旧结论"把 usr\bin 追加到用户 PATH 就永久修好"**是错的**。真正的根因是
   **子 bash 拿到的是 WorkBuddy 启动时刻的 PATH 快照**，注册表改了也到不了子进程
   （用探针实测过）；之前以为修好了，其实那段时间是沙箱的 `brokered-bin` 在顶班。
   正确修法是在 `BASH_ENV` 指向的 shim **顶部**插一段纯 bash 自愈补丁，**不需要重启**；
   本机已有双击守护脚本 `C:\Users\zyx32\bin\fix-bash-path.cmd`。
   → 完整根因、决定性诊断手法、以及"这个 bug 会静默关掉删除守卫（rm 变真删）"
   这条重要副作用，见技能 **`workbuddy-bash-path-fix`**。
   **实用结论**：不管修没修好，**都不要依赖 bash 的核心工具**——
   一律用绝对路径调 node/python（本机路径见本文末），列目录/读文件/搜内容用
   Read / Glob / Grep 专用工具。这样 PATH 坏不坏都不挡活。
   （历史上那条"用 `> out.txt` 代替 `| head`"的绕法**不要再用了**；
   现在管道是好的，写文件只是为了避免 Read 到 UTF-16。）
2. **PowerShell 工具不回显 stdout**：命令 `Exit Code: 0` 但**没有任何输出**，即使 `Write-Output`。
   → 把结果 `[System.IO.File]::WriteAllLines($path, $lines)` 写到临时文件，再用 Read 读。
   这是唯一可靠的回读方式，别在控制台上浪费时间。
3. **`file://` URL 里不能有百分号编码**：中文文件名转成 `%E9%9A%90...` 后，
   安全守卫会把 `%XX%` 误判成 cmd 的 `%VAR%` 语法并**拦掉整条命令**，
   报 `cmd.exe %VAR% environment variable syntax is not PowerShell syntax`。
   → 先 `Copy-Item` 到一个 **ASCII 临时文件名**（如 `$env:TEMP\hidtest.html`）再截图。
4. **反引号是转义符，别拿它当分隔符**：PowerShell 里 `` `f `` 是换页符（form feed），
   所以 `"$env:TEMP\$tag`fig.png"` 会生成一个混入不可见字符的文件名，
   截图"执行成功"但文件找不到。→ 一律用 `"${tag}fig.png"` 或 `Join-Path`。
5. **PowerShell 5.1 不支持 `(if …)` 当表达式**：`$o += "x=" + (if ($c) {1} else {0})`
   直接语法错，而且**stdout 是空的**，看起来像"脚本没输出/没执行"。
   → 先赋值再拼串：`$sz = 0; if (Test-Path $p) { $sz = (Get-Item $p).Length }`。

## 三步自检

### ① 标签深度追踪（找多余/缺失的闭合标签）

```powershell
$L = [System.IO.File]::ReadAllLines($f)
$d = 0
for ($i=0; $i -lt $L.Count; $i++) {
  if ($L[$i] -match 'class="card"' ) { "CARD-OPEN line {0} depth_before={1}" -f ($i+1), $d }
  $d += ([regex]::Matches($L[$i],'<div')).Count
  $d -= ([regex]::Matches($L[$i],'</div>')).Count
  if ($d -lt 0) { "NEGATIVE at line {0}" -f ($i+1) }
}
"final depth : $d"
```

用两个信号定位：
- **final depth ≠ 0** → 有净失衡。
- **每个顶层容器的 `depth_before` 应恒等于同一个数**（例如全是 1）。
  若某个 card 出现在 `depth_before=2`，说明**上一个 card 内部少了一个闭合标签**，
  多出的那个 `</div>` 会一路漏到文件末尾。

常见成因：分段用 Edit 追加内容时，`old_string` 与 `new_string` 的收尾 `</div>` 数量不一致，
结果在 `</html>` 之后多出一个孤立 `</div>`（HTML 容错所以浏览器不报错，但 DOM 结构是坏的）。

**分段追加的根治写法**：在文件里留占位注释推进（`<!--SEC2-->` → `<!--SEC3-->` …），
**且只有第一块自带 `</div></body></html>` 收尾，后续每块的 `new_string` 末尾绝不要再带一套闭合**。
我踩过这个：某一块的新内容末尾顺手写上了 `</div></body></html>`，而原文那里本来就已经有一份，
结果文件尾部出现两份闭合、`div` 深度 −1。症状只在"深度追踪"里可见，浏览器完全不报错。

**同一文件的多个 Edit 不能并行（本轮新踩，很隐蔽）**：
并行发出的多个 Edit 各自基于**同一份原始快照**，后写盘的会把先写盘的改动静默覆盖掉。
本轮在一条消息里同时改 `font-size="13"` 和 `stroke="#c6ccd1"`，
前者被后者冲掉——**两次工具返回都是 "Successfully edited"**，只有事后 Grep 复核才发现漏改。
→ **同一文件的多次修改必须串行**；改完用 Grep 回读关键值确认。

**改动嵌套结构后必须重跑深度追踪**：删掉一个开标签时，配对的闭标签也要删；
本轮把"图 + 读数"的左右并排改成上下布局，删了外层 `<div class="panelrow">` 的开标签
却漏了它的 `</div>`，于是 `open=55 / close=56`、最终深度 −1。
这类错误浏览器一律容错不报，**只有深度追踪能抓到**。

**SVG 元素会让朴素标签平衡检查误报**：`<rect ... />` / `<circle ... />` / `<line ... />` /
`<path ... />` 是自闭合，只数 `<rect` 会得到 `open=11 close=0` 的假阳性。
→ 平衡检查**只对容器类标签**做（`div` / `table` / `tr` / `svg` / `g` / `script` / `button` /
`ol` / `ul` / `li` / `h2`–`h4` / `footer` / `span` / `b` / `code`），
或统计开标签时同时排除紧跟 `/>` 的形式：`<rect(?=[\s>])(?![^>]*/>)`。
（HTML5 解析器在 SVG 外来内容里**支持**自闭合标签，所以 `<rect ... />` 本身是安全的。）

### ② 内嵌 JS：语法 + 数值（最容易被跳过、也最值钱）

裁 script 时**必须按整行锚定**，否则会静默截断：

```powershell
$jsStart = ($L | Select-String -Pattern '^<script>$' | Select-Object -First 1).LineNumber - 1
$jsEnd   = ($L | Select-String -Pattern '^</script>$' | Select-Object -Last 1).LineNumber - 1
$script  = ($L[$jsStart..$jsEnd] -join "`n")   # 含 <script> 与 </script>
```

> 坑：用 `$L.Count-4` 这类偏移量收尾，会把 `</script>` 吃掉。
> 缺 `</script>` 时后面的 `</body></html>` 会被当成脚本内容 → 语法错误 → **整页 JS 静默不执行**。
> 症状就是"文字正常、canvas 全空"。这个错我踩过。

语法检查：

```powershell
& "<node>\node.exe" --check "$env:TEMP\_chk.js"   # 把 <script> 内容单独存成 .js
```

**数值断言（真正的验收）**：不要只查语法。把页面里**真实的函数文本抽出来 eval**，
用已知答案断言，避免"代码能跑但算错"：

```js
const html = fs.readFileSync(p,'utf8');
const js = html.slice(html.indexOf('<script>')+8, html.lastIndexOf('</script>'));
eval(js.slice(js.indexOf('function mapto(q){'), js.indexOf('function naive(q){')));
// 然后用已知输入断言输出，例如：映射函数必须在四角精确复现目标顶点
```

断言清单（做几何/教学可视化时）：
- 映射类函数：**四个角点必须精确复现**（浮点用四舍五入后比较）。
- 反向映射：**往返误差应达机器精度**（正解 → 反解 → 比较，`1e-15` 量级）。
  这一条能一次抓出公式抄错、变量写反、分母漏项。
- 面积/坐标类函数：**子区域之和 == 总面积**；已知例题的解析答案。
- **对照型演示必须断言"两边真的不一样"**：并排画"正确 vs 朴素"时，
  取同一个采样点分别跑两套映射，断言差值足够大（例如某处 `v` 差 0.19）。
  **否则你可能交付一个两边看起来一模一样的"对比图"**——这种错光靠看截图未必发现。
- 若手搓伪透视（用梯形假装正方形的透视像），必须断言**一致性恒等式**
  `x_TL·w_TL + x_BR·w_BR == x_TR·w_TR + x_BL·w_BL`（Y 同理）。
  不满足说明这四个角点压根不是同一个投影变换的像，"正确"那一边**也是错的**。
- 只做「能跑」的检查会漏掉符号错、权重错、角点错。

### ③ 无头 Chrome 截图验收

```powershell
$chrome = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
Copy-Item $src "$env:TEMP\page.html" -Force          # ASCII 名，规避百分号守卫
& $chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars `
  --force-device-scale-factor=1 --window-size=1120,1500 `
  --screenshot="$env:TEMP\_shot.png" "file:///$env:TEMP/page.html"
```

- **长页面不要整页截**：`--window-size=1120,11000` 出来的图会大到 Read 工具只能看到缩略图，
  等于没看。**正确做法是只截要验收的那一段**——把该段的 HTML 片段 + 同一份 `<style>` +
  完整 `<script>` 拼成一个临时测试页再截，宽度 1120、高度按内容给 1200~1700。
- Edge 也在 `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`，参数相同。
- 看截图时确认三件事：canvas **有内容**（不是空白）、读数区**不是初始占位符**（如 `—`）、
  布局没有塌陷/溢出。读数区若还是占位符，说明脚本没跑，回到第 ② 步。

### ④ 交互行为的自动验收（DOM + SVG）——截图只能看初始态

截图证明不了"点了会不会变"。做法：一个测试页 + `location.hash` 注状态 + 批量截图，
每张图上叠一条**自检日志条**，看日志条比放大截图可靠得多。

```js
// 追加在页面末尾（主 <script> 之后，此时事件已绑定完）
function tap(sel){
  var el = document.querySelector(sel);
  if(!el){ log.push('!! 找不到 ' + sel); return; }
  el.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window}));
}
```

**两个必踩的坑：**

1. **SVG 元素没有 `.click()`。** `Element.prototype.click` 只定义在 `HTMLElement` 上，
   `<g>` / `<rect>` / `<circle>` 调 `.click()` 抛 `TypeError: el.click is not a function`。
   症状极具误导性：测试脚本先点 HTML 按钮（成功）、再点 SVG 开关（抛错），
   你会看到"模式切换生效了、但开关没反应"——**很容易误判成交付物有 bug，跑去改本来正确的代码**。
   → 一律用 `dispatchEvent(new MouseEvent('click', {bubbles:true}))`。
   真实鼠标点击不受影响：SVG 元素的 `addEventListener('click')` 正常工作；
   `<g>` 的子元素有 `fill` 时默认 `pointer-events:visiblePainted`，点图形会冒泡到 `<g>`。

2. **同一状态绑定了多个元素时，别用 `querySelectorAll` 全点。**
   若"串联组的开关 A"和"并联组的开关 A"绑的是同一个 toggle（或同一继电器的多组触点），
   奇偶次点击互相抵消，看起来像"点击无效"。
   → 用 `document.querySelector(sel)` **只点第一个**。

**日志条**（把受检状态显式写出来）：

```js
var d = document.createElement('div');
d.style.cssText = 'position:fixed;left:0;top:0;right:0;background:#111;color:#3f6;'+
                  'font:13px/1.6 monospace;padding:10px;z-index:99999';
d.textContent = log.join('\n');   // 灯色 / 文案 / 高亮行 / 计数 / 错误信息
document.body.appendChild(d);
```

把 `try{…}catch(e){ log.push('!! ' + e.message); }` 包住注入逻辑——
否则抛错后日志条根本不会出现，你会误以为"注入没生效"。

**一次生成、四次截图**：

```powershell
foreach ($h in @('s1','s2','s3','s4')) {
  & $chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars `
    --force-device-scale-factor=1 --window-size=1000,760 `
    --screenshot="$env:TEMP\t_$h.png" "file:///$env:TEMP\test.html#$h"
}
```

窗口高度给 700~800 就够（日志条固定在左上角，正文截没截到无所谓）。
判定标准要写成**可证伪的断言**，例如开关电路页：同一个开关组合 `10`，
串联时灯色应为 `#d5dade`（灭）、并联时应为 `#f5b301`（亮），
且真值表高亮行**两边都是** `10` —— 这才证明"换接法、结果不同"这个教学点真的渲染出来了。

### ⑤ 交互图示优先用 SVG，而不是 canvas

同一个需求，SVG 版能绕开一整类 canvas 陷阱：

- 没有 `devicePixelRatio` / `putImageData` / 变换矩阵的问题（见本文末节）；
- 元素可加 `addEventListener`，天然可点击、可键盘聚焦（`tabindex` + `role="button"`）；
- 可写 `fill="var(--line)"` 跟随主题，canvas 里取不到 CSS 变量；
- 用 `viewBox` 自适应，配合 CSS `svg{width:100%;height:auto}` 就行；
- 打印/缩放不糊。

代价：几何要用坐标手算（用 `viewBox="0 0 680 140"` 这类固定画布更好排）。
**需要在图元内部切换状态时，用"同一组元素 + JS 改属性"**（改 `fill`/`stroke`/`textContent`），
不要生成两套 DOM 再 toggle `display`——后者会让"同一次点击"要更新多个副本，
测试时容易踩上面第 2 条的坑。

### ⑥ 图要清晰：字号会随缩放缩水（用户一眼能看出来）

**最容易忽略、也最直观砸口碑的一处。**

SVG / canvas 里的字号是按 `viewBox` 或 `width/height` 属性写的，
**实际视觉字号 = 设定字号 ×（显示宽度 ÷ 固有宽度）**。

实例：电路图 `viewBox="0 0 680 150"` 被塞进 364px 宽的"图 + 读数"左右并排栏位 →
缩放比 0.53 → `font-size="15"` 的字实际只有 **8px**，糊成一片。
更坑的是：截图时若加了 `--force-device-scale-factor=2`，PNG 分辨率很高，
**光看截图未必察觉问题**——必须自己算缩放比。

→ **两条硬规矩**：

1. **图要占满版心宽度。** 左右并排（图 + 读数面板）必然让图缩水；
   把读数面板移到图的**下方**（默认单列，宽屏时可两列但图仍在最上方占满整行）。
   目标：**显示宽度 ÷ 固有宽度 ≥ 0.9**。
2. **canvas 做 2 倍超采样**——屏幕与打印都锐利，且逻辑坐标完全不用改：

```js
function fit(cv){
  if (cv.dataset.logical === '1') return;              // 防重复初始化
  var r = Math.max(2, window.devicePixelRatio || 1);   // 下限 2；别写成 if (r===1) return
  var w = cv.width, h = cv.height;
  cv.width = w * r; cv.height = h * r;
  cv.getContext('2d').setTransform(r,0,0,r,0,0);        // 逻辑坐标仍是 w×h
  cv.dataset.w = w; cv.dataset.h = h; cv.dataset.logical = '1';
}
```

**这一条只适用于矢量绘制的 canvas**（`arc`/`lineTo` 那类）。
逐像素 `putImageData` 的 canvas 绝不能这样做（见本文末节）。

**经验值**（`viewBox="0 0 680"` 的图，占满 612px 版心时）：
文字 `font-size` 16~17、元件边框 1.8、导线 3、数据点半径 7、虚线 1.4。
**宁可大一号**——打印到 A4 时还会再缩一轮。

### ⑦ 用 puppeteer-core 做真正的 DOM 级验收（比截图硬，也能自动跑交互）

本机已装 `puppeteer-core` + Chrome，比"截图肉眼看"强得多：能读**计算后的**尺寸、
像素统计、以及真实鼠标事件后的状态。四条**会静默骗过你**的坑：

```js
// 正确的起手式
const page = await browser.newPage();
const errs = [];
page.on('pageerror', e => errs.push('PAGEERROR ' + e.message));
page.on('console', m => { if (m.type()==='error') errs.push('CONSOLE ' + m.text()); });
await page.setViewport({width:880, height:1000, deviceScaleFactor:1});
await page.goto(url, {waitUntil:'networkidle0'});          // file:// 用 encodeURI 包中文名
```

1. **`boundingBox()` 不会自动滚入视口 → 鼠标事件静默落空（最坑）**。
   元素在首屏以下时返回的 `y` 可能大于视口高度，`page.mouse.move/down/up` 打出去的事件
   **一个都到不了元素上**。断言会"通过"（因为读数没变恰好等于断言没检查），
   或者"失败得莫名其妙"（我本轮 4 条拖拽断言全挂，就是这一个原因）。
   → **交互前必须先滚进来**：

```js
async function boxOf(page, sel){
  await page.evaluate(s => document.querySelector(s).scrollIntoView({block:'center'}), sel);
  await sleep(180);
  return await (await page.$(sel)).boundingBox();
}
```
2. **"非白像素占比"判据在浅色底图上会误报空白**。
   图自己用 `#f7f9fa` 之类的浅灰填充球面/曲面时，这些像素全部 >245，被当成"白"。
   我的球面图只测出 4.5% 非白，看起来像"canvas 没画"，其实画得好好的。
   → 判据改成**"既不是白底、也不是自己的填充色"**，并且**额外查主色像素占比**
   （如 `#8f3129` 占比 >0.15%）来证明关键笔画真的画出来了。阈值别卡在边界上
   （我写过 `>3` 而实际正好 `3.0`，白挂一条）。
3. **`setPointerCapture` / 拖拽要用真实 `page.mouse`，不要只 `dispatchEvent`**。
   本轮图 3-1、图 3-2 用的是 `pointerdown`+`pointermove`+`pointerup` + `setPointerCapture`，
   `dispatchEvent` 造不出捕获语义。真实鼠标能同时验证事件绑定与坐标换算。
   拖拽断言要**算准目标点的屏幕坐标**再断言读出值（如把 A 从 `(-1.40,0.75)` 拖到 `(0,2.0)`，
   断言欧氏距离变成 `1.552`）——这样连"映射有没有错"一起验了。
4. **`node` 在 Windows 上把 Git Bash 的 `/tmp/x.js` 解释成 `C:\tmp\x.js`** →
   `Error: Cannot find module 'c:\tmp\book_math.js'`。
   → 用 `$(cygpath -w /tmp/x.js)` 转成 Windows 路径再传。
   （历史上本环境 Bash 的 PATH 是坏的、管道得换成 `> out.txt` ——
   **那条已于 2026-09-14 永久修好**，见技能 `workbuddy-bash-path-fix`，现在管道可以正常用。）

**额外必做：正文数字 ↔ 图读数的一致性断言。**
教学页最容易出的错是"正文写 3.022、图里算出来 2.952"，改稿时只改了一处。
把两者都读成文本再比对：

```js
const txt = await page.evaluate(() => document.body.innerText);
ok('正文出现 3.022（与图读数一致）', txt.includes('3.022'));
ok('附录与图一致：180.5° / 276.2°', txt.includes('180.5°') && txt.includes('276.2°'));
```

**第 5 条（2026-09-14 第四章新踩）：交付物上的数字必须由交付物自己算出来。**
两种情况我都撞上了，性质完全不同：

- **图上标了"别的物体"的数字。** 图 4-3 的读数是"离亮点 0.25 处的残留 10.0% / 0.3%"，
  这两个值来自我事前跑的数值验证脚本，用的是**单点源**；而图上画的是**两个亮点**。
  数字本身没错，但它不属于这张图。
  → **凡是要画在 canvas 上的数字，都要在绘制函数里现场算**，不要从外部脚本搬。
- **正文数字与页面读数不一致。** 正文引用了相关系数序列，写的是预验证脚本（N=96 网格）
  的结果 0.68/0.83/0.93；而页面里的演示程序用 N=64 网格，实际显示 0.70/0.82/0.91。
  差异 0.007–0.023，**全部来自网格粗细，不是算法不同**。
  → **正文一律采用读者能在页面上看到的那一组**，并在附录里注明两套口径的差异来源。
  "两处独立实现互校"是用来**发现 bug** 的，不是让正文去迁就验证脚本的数值。

**成本权衡**：让页面实现和验证脚本用同一套参数（同网格、同采样）能消除差异，
但页面要实时响应拖动，网格必须小（N=64，不是 96）。
**这里选体验优先，用附录把口径写清楚**——不要为了数值对齐把交互卡住。

**手算的期望值要先跑一遍再写进断言。** 本轮我把球面最小三角形的内角和手算成 180.44°，
断言容差 0.06，结果程序给 180.51° —— 不是程序错，是我手算的精度不够。
凡是"手算 → 写进断言/写进正文"的数字，**先让脚本算一遍再落笔**，否则会把错的数写进正文
（本轮附录 A 就真的被我写成了 180.4°，已改回 180.5°）。


### ⑧ 多章合成单册 → A4 PDF（含两类"只有印出来/数了页"才暴露的错）

合册 = 封面 + 前言 + 总目录 + N 章 + 书末说明。合册脚本的三个要点：

1. **共享 CSS 以"定版那一章"为准**，其余章独有的选择器再追加。
   做法：把每章 `<style>` 解析成 `[(selector, body)]`，拿第 1 章的 selector 集合当基准，
   其余章只保留"基准里没有的"。注意 **`@media print` 整块当一条规则**，
   否则后面各章的 print 规则会覆盖第 1 章。
2. **跨章 id 必然撞车**：每章都有 `id="n1"`（章末注）与 `id="fn1"`（正文角标）。
   合册时按章加前缀 `c{i}-n{n}` / `c{i}-fn{n}`，**`href` 必须同步改**，否则角标点了不跳。
   切片脚本时尤其小心：要用"正文那段字符串"去 `rfind('<script')`，
   **别用整文件的下标**（下标错位会把 HTML 混进 `<script>`，结果是 8 个 JS 块全部语法错）。
3. **给章内每个 `<h2>` 生成 `id="c{i}-h{j}"`**，总目录才有锚点可跳。

**错误 A：图号必须按"文档顺序"排，不是按写作顺序。**
我有一章把 图 4-2 的 `<figure>` 块排在了 图 4-1 前面，印出来先出现 4-2。
检查法：把全文 `图 X-Y` 按**首次出现顺序**抽出来，断言每章递增（这个检查一并跑在导出的 PDF 上）。
**改法**：只换"给读者看的编号"（`<span class="fno">` + 所有正文/附录引用），
**不要动代码里的 id**（`c41` / `draw41` 是内部标识符，本就与显示号解耦）。
用占位符做交换，避免自我覆盖：

```python
s = re.sub(r'图\s*4-1', '§A§', s)
s = re.sub(r'图\s*4-2', '§B§', s)
s = s.replace('§A§', '图 4-2').replace('§B§', '图 4-1')
```

这个"全局换号"连 JS 注释里的 `/* 图 4-2 正弦图 */` 一起换掉，正好与新的显示号自洽。
**换完要把预览图也重出**——文件名带旧图号的会和新标签对不上。

**错误 B：Chrome 不支持 `orphans` / `widows`（写了等于没写）。**
为修一个"孤行页"，我往 `@media print` 加了 `p{orphans:2;widows:2}`，重建后**那一页还是只有一个孤行**。
真因是 `.notes{break-before:page}` 把章末注强制推到新页，正文最后一行被单独留在一页上。
→ **`break-before:page` 只加在"必须另起页"的开头类块**（章首页 `.ch-open`、章容器 `.chap`、
附录 `.appendix`、前言/书末），**不要加在章末注上**；让注顺排，孤行页自然消失
（本例页数还从 178 降到 175，多出来的空白页一并消掉）。
**另注意**：`.chap{break-before:page}` 才是章与章之间的分隔，删注释的强制分页不会让两章粘连。

**导出与独立复核（不要信渲染脚本的自我汇报）：**

```js
await page.pdf({ path: PDF, preferCSSPageSize: true, printBackground: true,
  outline: true, tagged: true, displayHeaderFooter: true, headerTemplate: '<div></div>',
  footerTemplate: '<div style="width:100%;font-size:8pt;text-align:center;'
    + 'font-family:Microsoft YaHei,sans-serif"><span class="pageNumber"></span> / '
    + '<span class="totalPages"></span></div>' });
```

- **footerTemplate 里必须显式写 `font-family:Microsoft YaHei`**，否则页码会渲成方框。
- `outline:true` 才会生成书签；导出前先轮询等所有 canvas 画完（各章计算量差别很大，
  别写死等 2 秒）。

```python
import pymupdf
d = pymupdf.open(pdf)
print(d.page_count, len(d.get_toc()))
thin = [(i+1, len(p.get_text().strip())) for i, p in enumerate(d)
        if len(p.get_text().strip()) < 200]
```

判读：**<200 字符的页**要么是章节/附录起始页（正常，70~160 字符），
要么是孤行页（要修）；正文页应 700~1100 字符。再抽几个**关键数字/术语**确认真的印进去了
（注意 `GF(2^8)` 在 PDF 文本提取里会变成 `GF(28)`——**上下标会丢，别当成缺失**）。
断言 `h1` 条数时要算上封面（封面 1 + N 章 = N+1），否则会误报"章标题不全"。


**可直接复用的三个脚本**（在本技能 `scripts/` 目录，均已支持用第一个参数指定书稿目录）：
- `book_check.py <书稿目录>` —— 逐章结构自检：div 深度、容器标签配对、**图号顺序**、
  注释编号与引用顺序、角标回跳、被引图表是否存在、各 `<script>` 用 `node --check` 验语法。
- `build_volume.py <书稿目录>` —— 多章合单册：共享 CSS 去重、跨章 id 加前缀、`h2` 加锚点、生成总目录。
- `volume_pdf.js <书稿目录>` —— 无头 Chrome 渲染 + 断点交互抽查 + 导出 A4 PDF（书签 + 页脚页码）。
  跑法：`NODE_PATH=<node workspace>/node_modules node volume_pdf.js <书稿目录>`。

Chrome 路径：**`C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`**
（子进程/子 agent 常只查默认 x64 路径而找不到它，然后"截不了图"）


### ⑨ canvas 的 DPR 适配函数必须幂等（否则滑块一拖就白屏）

**症状**：首屏正常，**一拖滑块画布就空白**（或内容缩到左上角一小块）。
**根因**：DPR 适配写成这样 ——

```js
function setup(cv){
  var W = cv.width, H = cv.height;          // ← 第二次调用时这里已经是物理像素
  cv.width = Math.round(W*dpr);             // ← 于是再乘一次 dpr
  ...
}
```

第一次调用 `cv.width` 是 HTML 属性里的逻辑值（如 648），函数把它改成 `648*dpr`。
**第二次调用时读到的 `cv.width` 已经是 1296**，于是画布变成 2592……
滑几次后超过浏览器 canvas 尺寸上限，Chrome 直接分配失败 → 画布空白，
控制台报 `Failed to execute 'getImageData': Out of memory at ImageData creation`。

**修法**：逻辑尺寸只记一次，存在 `dataset` 上，并且只在需要时才改属性。

```js
function setup(cv){
  var W = +(cv.dataset.logW || cv.getAttribute('width'));
  var H = +(cv.dataset.logH || cv.getAttribute('height'));
  cv.dataset.logW = W; cv.dataset.logH = H;
  var dpr = Math.min(window.devicePixelRatio || 1, 2);
  var pw = Math.round(W*dpr), ph = Math.round(H*dpr);
  if (cv.width  !== pw) cv.width  = pw;      // 只在真的不同时才写，避免无谓清空
  if (cv.height !== ph) cv.height = ph;
  cv.style.width = '100%'; cv.style.height = 'auto';
  var ctx = cv.getContext('2d');
  ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,W,H);
  return {ctx:ctx, W:W, H:H};
}
```

**必须写成回归断言**（截图看不出来，首屏永远是好的）：

```js
// 拖过 N 次滑块之后
const bad = ids.filter(id => {
  const cv = document.getElementById(id);
  return cv.width !== +cv.dataset.logW * dpr || cv.height !== +cv.dataset.logH * dpr;
});
ok('多次重绘后画布尺寸不膨胀', bad.length === 0, bad.join(','));
```

配套的一条：**别用 `ctx.getImageData(0,0,cv.width,cv.height)` 给大画布做"指纹"**——
在高 DPR 下 1296×640 反复读取会直接 OOM。改成先 `drawImage` 到一个 80×40 的离屏画布再读。

### ⑩ 参数化图示必须扫极值（首屏和默认值最容易骗过你）

带 `input[type=range]` 的图，**默认值下的版面几乎不能说明任何问题**。至少要扫：

| 类型 | 要扫的值 | 典型塌版 |
|---|---|---|
| 步数 / 项数类 | `min`、`max` | 行数变多互相压住；行数变 0 时标题还在说"下面这张图" |
| 比例类（速度比、概率） | `min`、`max` | 纵轴自适应后曲线贴顶/贴底，标注压轴 |
| 对数间隔类 | 最大、最小 | 最小端数字打印成 `0.00000000`，把"永远不到 0"讲成"等于 0" |

三个必须真正去查的点：

1. **打印精度要跟数量级走**。`(9.3e-10).toFixed(8)` → `"0.00000000"`，
   恰好把这一页要讲的"它不为 0"讲反了。写个小工具按量级选格式：
   ```js
   function num2(x){ if(x===0) return '0';
     var a=Math.abs(x); return a<1e-4 ? sci(x,3) : x.toFixed(6); }
   function num(x){  if(x===0) return '0';
     var a=Math.abs(x); if(a<1e-4) return sci(x,4);
     if(a>=1) return x.toFixed(12);
     return x.toFixed(Math.min(15, -Math.floor(Math.log10(a))+6)); }
   ```
   图上用 `num2`（短），读数区用 `num`（准）。
   别忘了 `0.999999999069` 也不能写成 `1.000000` —— 那正好是"趋近但不等于"的反面。
2. **画布上的每一行文字都要量宽度**。中文按 `≈ 字号` 估、数字按 `≈ 字号×0.55` 估，
   起点 + 长度必须落在 `[0, 逻辑宽]` 内。极值下数字会变长（`0.5` → `9.3132e-10`），
   默认值下不溢出不代表极值下不溢出。
3. **退化状态要有专稿**。例如"区间还没形成"、"只有 1 个样本"这类 `k === 0` 的分支，
   标题和旁注要跟着改口，不能还印着"把最后一个区间放大"。

做法：写一个 `ch_extreme.js`，对每组参数 `dispatchEvent(new Event('input'))` 后
逐图 `screenshot`，输出到 `预览图/极端参数/`，再逐张看。**这一步不能省**——
本项目里"滑块一拖就白屏"和"n=30 时 Sₙ 显示成 1.000000"两个错，
在默认参数下都是完全正常的。

### ⑪ 中文正文的引号必须是 “ ” ，不是 ASCII `"`（印刷前看不出来）

**症状**：正文里写 `"显然"`，屏幕上、PDF 里都长成一对**直杆**。中文出版物该用 `“ ”`。
本项目《很久以后》九份文件（174–343 处/章）与《直觉的边界》两份（246、36 处）
**全部**是 ASCII 直引号——一次性起草时批量打进去的，逐字校对发现不了。

**唯一可靠的检查**：HTML 去标签后正则找 `[\u4e00-\u9fff]["']|["'][\u4e00-\u9fff]`，
命中即错。（只数全文引号总数没用，`data-tex="p^2"` 这类属性引号是合法的。）

**替换必须用状态机，不能全局 replace**：
- 跳过 `<script>` / `<style>` 内容——JS 字符串与 CSS 字体名（`"PingFang SC"`）里的引号要
  保持 ASCII；
- 跳过标签属性（本就不在文本段里）；
- 用**全局开/关状态跨标签配对**，否则 `"<b>显然</b>"` 会把两个都变成左引号；
- 引号总数为奇数要报警（文本流里落单了）；
- **先 dry-run 打印每处的前后 16 字人工扫一遍**，再 `--apply`。
- 脚本：`scripts/cn-punct-fix.py`。

**暗坑**：canvas / DOM 里由 JS 拼出来的中文也会含直引号（本项目是
`'芝诺的"追不上"'` 画到图上）。**改产物不够，源脚本要一起改**，否则重新注入会覆盖回 ASCII。

**何时做**：写完一章立刻做，别攒到合册——PDF 已导之后再改要重导整本。

### ⑫ 数学符号要逐字形验：字体只给你半截（根号只是钩、上标在宋体里是全身宽）

**钩子 / 横线（vinculum）**：U+221A `√` 在常用字体里**只是一个钩**，横线得排版系统补。
LaTeX 的 `\sqrt{}` 是钩＋横线拼出来的；HTML 里直接写 `√2`，读者看到的就是缺半截的符号。
两种补法：

- 正文 HTML：`√<span class="rad">2</span>`，横线用 `.rad::before` 画
  （`.rad{display:inline-block;position:relative;line-height:1}` +
  `::before{content:"";position:absolute;left:-.14em;right:-.02em;top:.115em;height:1px;background:currentColor}`）。
  **只能作用于被开方数本身**，不要靠"给整串加 border-top"——换行时会断。
- canvas：塞不进标记，必须自绘。**先量字形再画线**：量出 `√` 的墨迹顶端
  （`top`＝离基线几像素）与顶端那一撮墨迹的右边界（`right`），
  横线高度取 `baseline − min(top, max(0.717em, top×0.62))`，
  起点 `cx + right − lw`、终点 `cx + 该字形步进宽 + 被开方数宽 + .02em`。
  三个数都得**量出来**，写死换个字体就错位。
- **本项目实际踩的坑**：第一版 `txtR` 用 `s.split(/√\{(.*?)\}/)` 解析，`√` 被当分隔符
  **吃掉**了，画面上只剩"2 顶一条横线"，比原状更糟。**凡用 split 解析标记，先确认被当
  分隔符的那个字符还需不需要画出来。**
- 别用 `lab()` / `fillText('√2')` 了事——那正是缺陷本身。

**上标 / 下标**：

- **正文 HTML 一律 `<sup>` / `<sub>`，不用 Unicode 上下标**（`⁰¹²³⁻ⁿ₀₁₂ₙ`）。
  实测 SimSun 里 `U+2076 ⁶` 的**步进宽度等于全尺寸数字**（30px 字号 adv=15px，与 `6` 同），
  排出来松得离谱；换雅黑又变窄——同一本书两种观感。混着 `<sup>` 用最难看。
- 补一条 CSS 让它不撑行距：
  `sup,sub{font-size:.72em;line-height:0;position:relative;vertical-align:baseline}`
  ＋ `sup{top:-.44em}` / `sub{top:.16em}`。
- **canvas 反过来：继续用 Unicode 上下标**。实测 `ⁿ ⁻ ⁿ ₙ ⁰ ₁ ₂ ⁺ × ′ ″ ° ∶ ⁄`
  在 SimSun / 雅黑 / Times 三套字体栈里**都有真字形**（无豆腐块），
  且尺寸就是字体设计好的小号上下标，比自己缩放更稳。
- 折中点——读数框是 JS 拼字符串、同时喂 `innerHTML` 与 canvas：**在写进 `innerHTML`
  之前转一道**（`supHtml()`），画布那条路保持原样。
  **坑**：别写"元素里已有 `<sup>` 就整块跳过"——一个读数框常同时含 `<sup>n</sup>` 与
  拼进来的 `10⁻⁴`，跳过就漏掉后者。转换函数只动 Unicode 字符本身，本就幂等，不必跳过。

**标点与连接号**：

- 数值区间统一 **en dash `–`**（同一本书别一半 `–` 一半 `—`）；中文破折号 `——` 才用 em dash。
- 半角 `, ; : ! ? ( )` 不要紧贴汉字（本项目抓到一处 `历史上,人们`）。

**关键：这些必须扫渲染后的 DOM，不能只扫源码。** 读数框与滑杆数值都是运行时填的，
源码里根本不出现（本项目第一章静态 3 处、动态 6 处）。

**一键门禁**：`node scripts/math-symbol-gate.js <章节.html>`
→ 五项：裸根号 / Unicode 上下标 / 数值区间 / 半角标点 / 页面脚本报错。

### ⑬ 出版级排字：斜体范围、正体常数、行尾悬算符

上面 ⑫ 管的是"符号有没有缺胳膊少腿"，这一节管**排字规范**——要让数学符号达到
论文／出版水平，只有 ⑫ 不够。判据逐字查过 **GB/T 3102.11-1993**（＝ISO 80000-2）原文：

| 该正体 | 该斜体 |
|---|---|
| 其值不变的数学常数（e、π、i²=−1） | 变量、变动附标（∑ᵢxᵢ 的 i） |
| 有定义的已知函数（sin、exp、ln、Γ） | 函数符号本身（f、g） |
| 已定义的算子（div、δx 的 δ、df/dx 的 d） | 点 A、线段 AB、弧 CD |
| 数字表中的数（351204、1.32、7/8） | **在特定场合视为常数的参数（a、b）** |

**实现**：`.m{font-style:italic}` 是"变量默认斜体"的语境，**凡非变量部分都要包
`.up{font-style:normal}` 扳回来**；整块该正体的（π、e）用 `.m.r{font-style:normal}`。

最常漏的是：混在斜体块里的**数字、`=`、`<`、括号**。一本书两章 23 处 `.m`，几乎每处都中。

**易错：`δ` 有两种身份。** 作**变量／角量**时斜体；作**变分算子**（δx）时正体。
别一刀切把它整个扳正体——那是两种东西。同理 `d`（微分算子）正体，但字母 d 作变量时斜体。

**⚠️ 正体小写希腊字母本机到底有没有？必须实测，不能假定。**
ISO 文件反复警告"标准字体没有正体小写希腊字母，π 常被迫斜体"。若字体栈缺真字形，
`font-style:normal` 得到的是 Chrome 的**合成倾斜**——这个"正体"是假的。
验法：同一字符 `italic` / `normal` 并排放大 54px 截图。实测 **Times New Roman 有真正体 π**
（腿一斜一垂直，肉眼可分），所以这条规范在本机是真能做到的。

**⚠️ 字形缺失测不出来——这是踩过两次的坑。**
`getBoundingClientRect` 对非 ASCII 符号一律返回**整字宽度**（`√ × · ≈ ≤` 全测成 16px，
与汉字同宽；`U+2044 ⁄` 测成 0 宽，可它明明画得出来）。
→ 据此判"缺字形"必然误报。**门禁里字形项只 warn 不 FAIL，真验收只能靠放大截图。**

**分数斜线**：用 ASCII `/`（U+002F），**不要** `U+2044 ⁄`。
放大样张实测 U+2044 会跟前后数字挤成「√107」，读成一百零七。

**行尾不许悬算符**。`→`、`=`、`+` 落在行末是排字忌讳；链条／公式这类要**强制断行**
（`<br>` 或分块），别指望自动折行。10 格的链条在 700px 宽的版心里必然折成两行，
不强制的话第一行就以 `→` 收尾。

**省略号分两种，别混**：中文省略号 `……`（六点）；数学省略号 `…`（三点 U+2026，
如 `0.999…`）。把 `0.999…` 写成 `0.999……` 是排字错误。

**数值与单位之间用不换行空格** `U+00A0`，否则窗口一窄"米"就掉到下一行。

**`data-tex` 必须是纯 LaTeX 源**，不许混 HTML 实体（`&gt;` `&lt;` `&amp;`）——
页脚若承诺"公式一律以 LaTeX 源格式保存"，混实体就自相矛盾。

**⚠️ `text-indent` 会被 inline-block 继承，把行内公式盒撑宽。**
中文书体例几乎必有 `p{text-indent:2em}`（首行缩进）。`text-indent` 是**可继承属性**，
而它只对"块容器"起作用——`display:inline-block` 的 `.rad` / `.frac` **正好是块容器**，
缩进就落在它内部的第一行上，shrink-to-fit 宽度因此凭空多出 **2em**。
根号横线是按盒子宽度画的 → 横线横向长出 2em，`√⎯⎯⎯2` 里那个 2 被甩到最右端。
（2026-09-15 实测：同一个 `√2`，段落里的盒宽 42.2px，`.trap` 里的 9.2px，差别就是 2em。）
**解法：给 `.rad`、`.frac` 显式写 `text-indent:0`。**

**⚠️ 门禁不能拿"元素自己的宽度"当基准——那是自证。**
根号那条像素检查原本是比「实测横线宽 ≈ `元素宽 + 0.16em`」，元素宽本身被撑大了 2em，
于是横线跟着错、检查照样全过。**基准必须独立于被测对象**：改成"被开方数用同一字体
量出来的宽度"。`typeset-gate.js` 的第 ⑤ 项即为此设，并配了一份回归件验证它真能报出来。

**一键门禁**：`node scripts/typeset-gate.js <章节.html>`
→ 五项：`.m` 内非变量是否都扳成正体 / `data-tex` 纯度 / 正文流里的裸希腊字母 /
行内公式盒有没有被继承的 `text-indent` 撑宽 / 脚本报错。

## 交付前检查单

- [ ] **数学符号过 `math-symbol-gate.js`**（裸 `√`、Unicode 上下标、区间连接号、半角标点）；
      **必须对渲染后的 DOM 跑**——读数框里的符号源码里看不到
- [ ] **有 `√` 时**：正文用 `.rad::before` 补横线、canvas 用自绘 `txtR()`（先量字形再画线），
      并放大裁图**肉眼确认钩子与横线都在**（只看结构检查会漏掉整条符号）
- [ ] **中文正文无 ASCII 直引号**（`[\u4e00-\u9fff]["']` 零命中）；JS 拼给 canvas 的中文同样要查
- [ ] div 深度最终为 0，且每个顶层 card 的 depth_before 一致
- [ ] **要出版级时再过一遍 `typeset-gate.js`**（见 ⑬）：`.m` 里非变量都扳正体、
      `data-tex` 没混 HTML 实体、正文无裸希腊字母、行内公式盒没被 `text-indent` 撑宽
- [ ] **行内公式用 `inline-block` 时，必须显式 `text-indent:0`**——中文书体例的
      `p{text-indent:2em}` 会继承进来，把根号横线／分式盒横向撑长 2em
- [ ] 涉及宽度／位置的门禁，**基准要独立于被测元素**（别拿 `el.getBoundingClientRect().width`
      当参照再去量 `el` 的装饰），并在改完后跑一遍"把修复摘掉"的回归件确认门禁真会 FAIL
- [ ] **正体小写希腊字母（π、e）先验字体栈是否真有字形**——没有真字形的话
      `font-style:normal` 只会得到合成倾斜，得并排放大 54px 肉眼确认
- [ ] **行尾不悬算符**（`→` `=` `+`），链条／公式强制断行；数学省略号用三点 `…`
- [ ] **每张图算一遍 显示宽度 ÷ 固有宽度**，低于 0.9 就改布局（让图占满整宽）
- [ ] 标签平衡检查**只对容器类标签**做（`rect`/`circle`/`line`/`path` 自闭合，会假阳性）
- [ ] `node --check` 通过
- [ ] 关键函数有数值断言，且断言覆盖四角/边界/已知例题
- [ ] 无头 Chrome 截图里 canvas 有内容、无占位符残留
- [ ] **用 puppeteer 做 DOM 级验收**：`page.on('pageerror')` 无报错；
      交互前先 `scrollIntoView`（否则鼠标事件静默落空）
- [ ] **正文数字与图读数一致**（同一个量只算一次，正文/图/附录共用一个来源）
- [ ] **手算的期望值先跑脚本核一遍**再写进正文或断言
- [ ] **多章成册时**：共享 CSS 以定版章为准、跨章 id 加章前缀且 `href` 同步改、
      每个 `h2` 有锚点；合册后重新跑一次结构自检与交互抽查
- [ ] **全文 `图 X-Y` 按首次出现顺序递增**（每章独立检查，导出 PDF 后再查一遍）
- [ ] **`break-before:page` 只给"开头类"块**（章首页/章容器/附录/前言），
      章末注一律顺排——`orphans`/`widows` 在 Chrome 里无效，别指望它
- [ ] **PDF 导出后用 pymupdf 独立复核**：页数、书签数、<200 字符的页是否有非起始页的孤行页、
      关键数字/术语确实在文本里（`GF(2^8)` 会抽成 `GF(28)`，属正常）
- [ ] **有交互控件时**：用 `dispatchEvent(MouseEvent)` 注入 ≥3 个状态各截一张，
      日志条里的灯色/文案/高亮行都符合预期（只截初始态等于没验）
- [ ] **有 `input[type=range]` 时**：把每个滑块推到 `min` 与 `max` 各截一张（见 ⑩）；
      并断言"拖 N 次后 canvas 尺寸不膨胀"（见 ⑨）
- [ ] 图上数字的**打印精度跟着数量级走**，别把 `9.3e-10` 印成 `0.00000000`、
      也别把 `0.999999999069` 印成 `1.000000`
- [ ] 页面**不依赖任何外部资源**（教学页常要在无网教室用）；唯一可接受的例外是
      `cdnjs.cloudflare.com` / `esm.sh` / `cdn.jsdelivr.net` / `unpkg.com`
- [ ] canvas 里不要用 CSS 变量取色（解析不了），硬编码 hex；但 SVG 里
      `fill="var(--color-text-secondary)"` **可以**用，且是跟随亮/暗主题的推荐做法
- [ ] **搬迁/复制整个项目目录后**：脚本里的 Windows 绝对路径有**两种形态**——
      单反斜杠（`C:\Users\...`）与 JS 字符串里转义过的双反斜杠（`C:\\Users\\...`）。
      只按单反斜杠做批量替换会**漏掉后者**（本次实测：30 个文件里漏了 1 个，
      而那个"搬过去"的脚本一跑就找不到文件）。复查残留时**搜不含转义的短子串**
      （比如只搜那段时间戳），不要搜完整路径——完整路径会因为反斜杠数量不同而漏检。
      搬迁后**必须在新位置真跑一遍全套验收**，跑通才算搬完。

## 交互控件的两个硬细节

- **指针坐标换算**：canvas 的 `width` 属性（缓冲区）常与 CSS 显示尺寸不同，
  必须按 `getBoundingClientRect()` 缩放，否则拖拽位置偏移：
  `x = (e.clientX - r.left) * (cv.width / r.width)`
- **拖拽必加 `touch-action:none`**（内联样式），否则触屏/触控板会与页面滚动抢事件；
  并在 `pointerdown` 里 `setPointerCapture`，否则快速拖动会丢事件。

## 逐像素绘制的 canvas（画纹理/热力图/图像变换）单独注意

这类 canvas 用 `createImageData` + `putImageData` 逐像素写，规则和普通 canvas 不同：

1. **`putImageData` 完全无视 canvas 的变换矩阵**。所以**绝不能**对这类 canvas 施加
   devicePixelRatio 缩放（`ctx.setTransform(r,0,0,r,0,0)`）后再用逻辑尺寸建 ImageData——
   在高 DPI 屏上图像会缩成四分之一并卡在左上角。
   → 做法：这类 canvas **不要做 DPR 适配**，直接用 `canvas.width/height` 属性值当逻辑尺寸
   （HTML 里写死 `width="300" height="200"`），交给 CSS `width:100%` 缩放。
   略有软化，但几何正确。DPR 适配只用于矢量绘制（`arc`/`lineTo` 那种）的 canvas。
   → 另一处细节：这类 canvas 起始时显式 `setTransform(1,0,0,1,0,0)` 清干净，避免上一个
     绘制流程残留的变换。
2. **别在像素循环里拼字符串**。`'rgb('+r+','+g+','+b+')'` 再 `.match(/\d+/g)` 解析，
   300×200 两个 canvas 就是 12 万次正则，肉眼可见卡顿。
   → 直接返回/查表拿颜色数组：`d[i]=c[0]; d[i+1]=c[1]; d[i+2]=c[2]; d[i+3]=255;`
3. **循环范围先夹到画布内**（`Math.max(0, …)` / `Math.min(w, …)`），
   否则边界像素写到 ImageData 外面会污染相邻行，出现斜条纹。
4. `putImageData` 会**覆盖**该区域已有的描边，所以外框描边要放在 `putImageData` **之后**。
