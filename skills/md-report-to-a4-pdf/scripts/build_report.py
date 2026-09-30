# -*- coding: utf-8 -*-
r"""把中芯国际分析报告 Markdown 渲染成中文 A4 PDF。

架构（详见 skill md-report-to-a4-pdf 的 SKILL.md）：
  build_report.py   md → cover.html + body.html
  render_pdf.js     puppeteer-core + 本机 Chrome，displayHeaderFooter:false
  finalize.py       pymupdf：拼封面 + 盖页眉页脚 + 书签 + 子集化字体

入口：.venv\Scripts\python.exe build_report.py
产物：分析结果_688981.SS_2026-09-12.pdf（封面 + 21 页正文）
"""
from __future__ import annotations

import html as htmllib
import re
import sys
from pathlib import Path

# Windows 控制台默认 GBK，中文 print 会乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ============================ 配置区（换报告只改这里） ============================
# 源 Markdown：默认取本目录下最新修改的「分析结果_*.md」，也可写死文件名
_MD_CANDIDATES = sorted(
    Path(__file__).parent.glob("分析结果_*.md"),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)
MD_PATH = _MD_CANDIDATES[0] if _MD_CANDIDATES else Path(__file__).parent / "报告.md"

# 封面封面文案（主标题默认取 md 的第一个 H1，这里只覆盖副标题与 ticker 行）
COVER_TICKER = "688981.SS · SSE STAR Market"
COVER_RATING = "Hold"
COVER_AUTHOR = "安宁"
COVER_DATE = "2026-09-12"
COVER_FOOTER = "本报告由 TradingAgents 多智能体框架自动生成 · 仅供研究参考"

# 产物（不带扩展名的基名，三个脚本共用）
STEM = MD_PATH.stem
# ==================================================================================

COVER_HTML = Path(__file__).parent / "cover.html"
BODY_HTML = Path(__file__).parent / "body.html"


# ---------- 行级 Markdown 渲染 ----------
def render_inline(s: str) -> str:
    """行内的 **bold** / `code` 转 HTML，HTML 转义必须先做。"""
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # **bold**
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    # `code`
    s = re.sub(r"`([^`]+?)`", r'<code class="ic">\1</code>', s)
    return s


def md_to_blocks(md: str) -> list[str]:
    """把 md 切成块级结构：headings / paragraphs / table rows / hr / lists。"""
    blocks: list[str] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # --- 水平线 ---
        if stripped == "---":
            blocks.append("<hr>")
            i += 1
            continue

        # --- 标题 # / ## / ### ---
        m = re.match(r"^(#{1,4})\s+(.+?)\s*$", stripped)
        if m:
            level = len(m.group(1))
            text = render_inline(m.group(2))
            blocks.append(f"<h{level}>{text}</h{level}>")
            i += 1
            continue

        # --- 表格（|---| 起始）---
        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|\s*$", lines[i + 1].strip()):
            header_cells = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2  # 跳过分隔行
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            blocks.append(("TABLE", header_cells, rows))
            continue

        # --- 无序列表 ---
        if re.match(r"^[-*]\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append(render_inline(re.sub(r"^[-*]\s+", "", lines[i].strip())))
                i += 1
            blocks.append("<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>")
            continue

        # --- 有序列表 ---
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                items.append(render_inline(re.sub(r"^\d+\.\s+", "", lines[i].strip())))
                i += 1
            blocks.append("<ol>" + "".join(f"<li>{x}</li>" for x in items) + "</ol>")
            continue

        # --- 空行 ---
        if not stripped:
            i += 1
            continue

        # --- 段落（合并连续非空行；"**xxx**：" 开头的行单独成段）---
        _BOLD_LABEL = re.compile(r"^\*\*[^*]+\*\*\s*[:：]")
        if _BOLD_LABEL.match(stripped):
            blocks.append(f"<p>{render_inline(stripped)}</p>")
            i += 1
            continue
        para = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt or nxt.startswith("#") or nxt == "---" \
                    or nxt.startswith("|") or re.match(r"^[-*]\s+", nxt) \
                    or re.match(r"^\d+\.\s+", nxt) \
                    or _BOLD_LABEL.match(nxt):
                break
            para.append(nxt)
            i += 1
        blocks.append(f"<p>{render_inline(' '.join(para))}</p>")

    return blocks


def blocks_to_html_body(blocks: list[str]) -> str:
    """把块级结构渲染成 HTML body。摘要 / 决策路径 / 落盘 不强制分页。"""
    out: list[str] = []
    no_break_titles = {"摘要", "决策路径", "八、落盘位置"}
    for blk in blocks:
        if isinstance(blk, str):
            # 给不需要分页的 h2 加 class
            for t in no_break_titles:
                if blk.startswith("<h2>") and t in blk:
                    blk = blk.replace("<h2>", '<h2 class="no-break">')
                    break
            out.append(blk)
            continue
        # TABLE 元组
        if isinstance(blk, tuple) and blk[0] == "TABLE":
            _, header, rows = blk
            th = "".join(f"<th>{render_inline(c)}</th>" for c in header)
            trs = "".join(
                "<tr>" + "".join(f"<td>{render_inline(c)}</td>" for c in r) + "</tr>"
                for r in rows
            )
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>")
    return "\n".join(out)


# ---------- 章节分类（封面/目录/正文） ----------
def split_sections(blocks: list[str]):
    """把 blocks 切成：cover_meta（用于封面）、toc_entries（目录）、body_blocks（正文）。

    约定：
      · 第一个 H1（标题）→ 封面元数据（已重写为更大的 cover title）
      · 第二个 H1 之后所有 H2/H3 → 正文章节
      · 自动生成目录：从正文 H2 中提取
    """
    cover_title = None
    cover_meta: list[str] = []
    body: list[str] = []
    toc: list[tuple[str, str]] = []  # (level, text)
    seen_first_h1 = False

    i = 0
    while i < len(blocks):
        blk = blocks[i]
        if isinstance(blk, str) and blk.startswith("<h1>"):
            if not seen_first_h1:
                seen_first_h1 = True
                cover_title = re.sub(r"<.+?>", "", blk[4:-5]).strip()
                # 接下来到第一个 H2 之前的非 H1 块作为封面副信息
                j = i + 1
                while j < len(blocks):
                    nxt = blocks[j]
                    if isinstance(nxt, str) and nxt.startswith("<h2"):
                        break
                    if isinstance(nxt, str):
                        # 收集封面副信息：剥离 <p> 标签但保留内容
                        cover_meta.append(re.sub(r"</?p>|</?hr>", "", nxt).strip())
                    j += 1
                i = j
                continue
            else:
                # 不应该有第二个 H1，转成 H2
                body.append(blk.replace("<h1>", "<h2>").replace("</h1>", "</h2>"))
                toc.append(("2", re.sub(r"<.+?>", "", blk[4:-5]).strip()))
                i += 1
                continue

        if isinstance(blk, str) and blk.startswith("<h2"):
            toc.append(("2", re.sub(r"<.+?>", "", blk[4:-5]).strip()))
        elif isinstance(blk, str) and blk.startswith("<h3"):
            toc.append(("3", re.sub(r"<.+?>", "", blk[5:-6]).strip()))

        body.append(blk)
        i += 1

    return cover_title, cover_meta, body, toc


# ---------- HTML 模板 ----------
BODY_CSS = """
@page{size:A4;margin:16mm 15mm 18mm 15mm;}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
body{font-family:"Microsoft YaHei","DengXian","SimHei",sans-serif;
     font-size:10.5pt;line-height:1.62;color:#1c2024;
     -webkit-font-smoothing:antialiased;}
h1{font-size:22pt;line-height:1.25;margin:0 0 8mm 0;color:#0b1c33;
    font-weight:700;letter-spacing:0.5pt;border-bottom:2.5pt solid #b3261e;
    padding-bottom:3mm;}
h2{font-size:14.5pt;line-height:1.3;margin:7mm 0 3mm 0;color:#0b1c33;
    font-weight:700;page-break-after:avoid;break-before:page;
    border-left:3.5pt solid #b3261e;padding-left:3mm;}
h2.no-break{break-before:auto;} /* 摘要、决策路径不强制分页 */
h3{font-size:11.5pt;line-height:1.3;margin:4mm 0 2mm 0;color:#1c3d6e;
    font-weight:700;page-break-after:avoid;}
h4{font-size:10.5pt;line-height:1.3;margin:3mm 0 1.5mm 0;color:#444;font-weight:700;}
p{margin:0 0 2.5mm 0;text-align:justify;}
p strong,b{color:#0b1c33;}
hr{border:0;border-top:0.6pt solid #dde5ec;margin:5mm 0;}
ul,ol{margin:0 0 3mm 0;padding-left:6mm;}
li{margin:0 0 1mm 0;}
table{border-collapse:collapse;width:100%;margin:2mm 0 4.5mm 0;
      font-size:9.5pt;page-break-inside:auto;}
thead{display:table-header-group;}
tbody tr{page-break-inside:avoid;}
th,td{border:0.5pt solid #c8d2dc;padding:1.6mm 2.2mm;text-align:left;
      vertical-align:top;}
th{background:#f3f6fa;color:#0b1c33;font-weight:700;white-space:nowrap;}
tbody tr:nth-child(even){background:#fafbfc;}
code.ic{font-family:"Consolas","Courier New",monospace;font-size:9pt;
        background:#f3f6fa;color:#0b1c33;padding:0.3mm 1mm;border-radius:1mm;}
/* 第一屏用作 TOC 后空白（让目录进自己一页）*/
.toc-card{margin:0 0 5mm 0;padding:3mm 4mm;border:0.5pt solid #dde5ec;
          border-left:3pt solid #0b1c33;background:#fafbfc;}
.toc-card h2{margin-top:0;border-left:none;padding-left:0;break-before:auto;}
.toc-list{margin:0;padding:0;list-style:none;}
.toc-list li{font-size:10pt;margin:0.6mm 0;}
.toc-list li.lvl2{padding-left:0;}
.toc-list li.lvl3{padding-left:6mm;color:#555;font-size:9.5pt;}
/* 摘要卡 */
.exec-card{margin:0 0 4mm 0;padding:3mm 4mm;border:0.5pt solid #dde5ec;
           border-left:3pt solid #b3261e;background:#fff8f6;}
.exec-card h3{margin-top:0;color:#b3261e;}
/* 摘要表 */
.exec-card table{margin:0;font-size:10pt;}
.exec-card th{width:24mm;}
/* 决策路径多空对冲 */
.decision-row{display:flex;gap:3mm;margin:3mm 0;}
.decision-row > div{flex:1;padding:2.5mm 3mm;border:0.5pt solid #dde5ec;
                   background:#fafbfc;font-size:9.8pt;line-height:1.55;}
.decision-row .bull{border-left:3pt solid #b3261e;}
.decision-row .bear{border-left:3pt solid #0f7b4f;}
.decision-row .mid{border-left:3pt solid #0b1c33;}
.decision-row h4{margin:0 0 1.5mm 0;font-size:10pt;}
/* 标记 */
.rating-hold{display:inline-block;background:#0b1c33;color:#fff;
             padding:0.8mm 3mm;border-radius:1mm;font-weight:700;}
.note{font-size:9pt;color:#666;font-style:italic;margin:0 0 3mm 0;}
"""


def make_body_html(title: str, body_html: str, toc: list[tuple[str, str]]) -> str:
    toc_items = "".join(
        f'<li class="lvl{lvl}">{htmllib.escape(text)}</li>'
        for lvl, text in toc
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{htmllib.escape(title)}</title>
<style>{BODY_CSS}</style></head>
<body>
<h1>{htmllib.escape(title)}</h1>
<div class="toc-card"><h2>目录</h2>
<ul class="toc-list">{toc_items}</ul></div>
{body_html}
</body></html>
"""


COVER_CSS = """
@page{size:A4;margin:0;}
*{box-sizing:border-box;}
html,body{width:210mm;height:297mm;margin:0;padding:0;overflow:hidden;}
body{font-family:"Microsoft YaHei","DengXian","SimHei",sans-serif;
     background:linear-gradient(135deg,#0b1c33 0%,#1c3d6e 60%,#2a528a 100%);
     color:#fff;position:relative;padding:0;}
.cover-deco{position:absolute;top:0;right:0;width:90mm;height:90mm;
            background:radial-gradient(circle at top right,rgba(179,38,30,.45),transparent 60%);}
.cover-deco2{position:absolute;bottom:0;left:0;width:130mm;height:130mm;
             background:radial-gradient(circle at bottom left,rgba(255,255,255,.08),transparent 65%);}
.cover-inner{position:relative;z-index:2;padding:38mm 22mm 30mm 22mm;height:100%;
             display:flex;flex-direction:column;justify-content:space-between;}
.cover-eyebrow{font-size:11pt;letter-spacing:6pt;color:rgba(255,255,255,.7);
               font-weight:400;text-transform:uppercase;}
.cover-title{font-size:32pt;line-height:1.22;font-weight:700;
             margin:8mm 0 4mm 0;letter-spacing:0.8pt;}
.cover-ticker{font-size:13pt;letter-spacing:3pt;color:#f6c9a0;
              font-family:"Consolas",monospace;margin-bottom:14mm;}
.cover-meta{display:grid;grid-template-columns:1fr 1fr;gap:5mm 12mm;
            font-size:10.5pt;line-height:1.6;}
.cover-meta .k{color:rgba(255,255,255,.6);font-size:9.5pt;
              letter-spacing:1pt;text-transform:uppercase;margin-bottom:1mm;}
.cover-meta .v{font-weight:600;color:#fff;}
.cover-rating{margin-top:8mm;display:inline-block;
              background:rgba(255,255,255,.12);border:1pt solid rgba(255,255,255,.3);
              padding:2mm 5mm;border-radius:1.5mm;font-size:11pt;}
.cover-footer{font-size:9pt;color:rgba(255,255,255,.5);
              border-top:0.5pt solid rgba(255,255,255,.2);padding-top:3mm;}
.cover-footer .right{float:right;}
.legend{display:flex;gap:5mm;font-size:9pt;color:rgba(255,255,255,.85);
        margin-top:4mm;align-items:center;}
.legend .sw{display:inline-block;width:5mm;height:2mm;
            vertical-align:middle;margin-right:1.5mm;}
"""


def make_cover_html(title: str, ticker: str, meta: list[str]) -> str:
    # 简单把 meta 里的 <p>/<hr> 都剥掉，然后按中/英文冒号切成 key-value
    meta_clean: list[tuple[str, str]] = []
    for m in meta:
        m = re.sub(r"<[^>]+>", "", m).strip()
        if not m:
            continue
        m_colon = re.search(r"[:：]", m)
        if m_colon:
            k = m[: m_colon.start()].strip()
            v = m[m_colon.end():].strip()
            meta_clean.append((k, v))
        else:
            meta_clean.append(("备注", m))
    meta_items = "".join(
        f'<div><div class="k">{htmllib.escape(k)}</div>'
        f'<div class="v">{htmllib.escape(v)}</div></div>'
        for k, v in meta_clean
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>封面 - {htmllib.escape(title)}</title>
<style>{COVER_CSS}</style></head>
<body>
<div class="cover-deco"></div>
<div class="cover-deco2"></div>
<div class="cover-inner">
  <div>
    <div class="cover-eyebrow">TradingAgents Research Report</div>
    <div class="cover-title">{htmllib.escape(title)}</div>
    <div class="cover-ticker">{htmllib.escape(ticker)}</div>
    <div class="cover-rating">最终评级：<b>{htmllib.escape(COVER_RATING)}</b> &nbsp;|&nbsp; 决策路径见正文</div>
  </div>
  <div>
    <div class="cover-meta">{meta_items}</div>
    <div class="legend">
      <span><span class="sw" style="background:#b3261e"></span>涨 / 多头</span>
      <span><span class="sw" style="background:#0f7b4f"></span>跌 / 空头</span>
      <span><span class="sw" style="background:#0b1c33"></span>中性 / 元数据</span>
      <span><span class="sw" style="background:#d08a12"></span>警示 / 待确认</span>
    </div>
  </div>
  <div class="cover-footer">
    <span>{htmllib.escape(COVER_FOOTER)}</span>
    <span class="right">{htmllib.escape(COVER_AUTHOR)} · {htmllib.escape(COVER_DATE)}</span>
  </div>
</div>
</body></html>
"""


# ---------- main ----------
def main() -> None:
    print(f"源 Markdown: {MD_PATH.name}")
    md = MD_PATH.read_text(encoding="utf-8")
    blocks = md_to_blocks(md)
    cover_title, cover_meta, body_blocks, toc = split_sections(blocks)
    if not cover_title:
        cover_title = "分析报告"
    body_html = blocks_to_html_body(body_blocks)
    body_doc = make_body_html(cover_title, body_html, toc)
    cover_doc = make_cover_html(cover_title, COVER_TICKER, cover_meta)

    BODY_HTML.write_text(body_doc, encoding="utf-8")
    COVER_HTML.write_text(cover_doc, encoding="utf-8")
    print(f"wrote: {BODY_HTML.name}  ({BODY_HTML.stat().st_size} bytes)")
    print(f"wrote: {COVER_HTML.name}  ({COVER_HTML.stat().st_size} bytes)")
    print(f"（产物基名 STEM = {STEM!r}，render_pdf.js / finalize.py 会用）")


if __name__ == "__main__":
    main()