# -*- coding: utf-8 -*-
r"""把 cover.pdf + body.pdf 合成最终 PDF：拼封面 + 盖中文页眉页脚 + 写书签 + 子集化字体。

关键决策（见 SKILL.md）：
  1. 不让 Chrome 加页眉页脚（displayHeaderFooter:false 已经做了）—— 改用 pymupdf
     逐页盖印，**顺带算准真实页码**（封面 = 第 0 页不算入正文页码）。
  2. pymupdf 每次 insert_text 都嵌一份字体 → 调 doc.subset_fonts() 把 21 页各自的字体
     合并去重。实测 13MB → 1.3MB。
  3. 书签用 Chrome outline + 后处理折叠重复标题（如果 outline 出问题，回退到手动书签）。

入口：.venv\Scripts\python.exe finalize.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pymupdf as fitz

# Windows 控制台默认 GBK，中文 print 会乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ============================ 配置区（换报告只改这里） ============================
# 输出文件名：默认取本目录下最新修改的「分析结果_*.md」同名 PDF
_MD_CANDIDATES = sorted(
    Path(__file__).parent.glob("分析结果_*.md"),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)
STEM = _MD_CANDIDATES[0].stem if _MD_CANDIDATES else "报告"

# 页眉/页脚文案
DOC_TITLE = "中芯国际 00981.HK · 分析报告"
DOC_SUBTITLE = "TradingAgents · 2026-09-11"
RATING_TAG = "Hold"          # 页脚左侧标签，如 Hold / Buy / Underweight

# 兜底书签（仅当 body.pdf 没有 outline 时使用）
CHAPTER_TITLES = [
    "摘要与决策路径", "一、市场行情", "二、基本面", "三、新闻与资讯",
    "四、市场情绪", "五、交易员决策", "六、风控与投资计划",
    "七、与上次跑对照", "八、落盘位置",
]
# ==================================================================================

ROOT = Path(__file__).parent
COVER_PDF = ROOT / "cover.pdf"
BODY_PDF = ROOT / "body.pdf"
FINAL_PDF = ROOT / f"{STEM}.pdf"

ZH_FONT = r"C:\Windows\Fonts\msyh.ttc"
ZH_FONT_INDEX = 0  # msyh.ttc 第一个字面 = 微软雅黑 Regular

# A4 (pt)
W, H = 595.276, 841.89
LEFT = 42.52      # 15mm
RIGHT = W - 42.52

# 页眉/页脚位置
HEAD_RULE_Y = 40.0
HEAD_BASE_Y = 32.5
FOOT_RULE_Y = 793.5
FOOT_BASE_Y = 808.5

FS = 7.2
GRAY = (0.45, 0.50, 0.55)
RULE_GRAY = (0.84, 0.86, 0.90)
ACCENT = (0.70, 0.15, 0.12)  # 与封面装饰色对齐


def draw_headfoot(page: fitz.Page, page_num: int, total: int, font: fitz.Font):
    """在一页上盖页眉横线+文档标题 与 页脚横线+页码+评级标签。"""
    # 页眉横线
    page.draw_line((LEFT, HEAD_RULE_Y), (RIGHT, HEAD_RULE_Y), color=RULE_GRAY, width=0.5)
    # 页眉文字（左：DOC_TITLE，右：DOC_SUBTITLE）
    page.insert_text((LEFT, HEAD_BASE_Y), DOC_TITLE,
                     fontname="zh", fontfile=ZH_FONT, fontsize=FS,
                     color=GRAY)
    sub_w = font.text_length(DOC_SUBTITLE, fontsize=FS)
    page.insert_text((RIGHT - sub_w, HEAD_BASE_Y), DOC_SUBTITLE,
                     fontname="zh", fontfile=ZH_FONT, fontsize=FS,
                     color=GRAY)

    # 页脚横线
    page.draw_line((LEFT, FOOT_RULE_Y), (RIGHT, FOOT_RULE_Y), color=RULE_GRAY, width=0.5)
    # 页脚左：评级标签
    tag_text = f"评级：{RATING_TAG}"
    page.insert_text((LEFT, FOOT_BASE_Y), tag_text,
                     fontname="zh", fontfile=ZH_FONT, fontsize=FS,
                     color=ACCENT)
    # 页脚右：第 N / TOTAL 页（仅正文页有页码；封面不编号）
    page_text = f"第 {page_num} / {total} 页"
    pw = font.text_length(page_text, fontsize=FS)
    page.insert_text((RIGHT - pw, FOOT_BASE_Y), page_text,
                     fontname="zh", fontfile=ZH_FONT, fontsize=FS,
                     color=GRAY)


def add_outline(doc: fitz.Document):
    """手工写书签。从 body 的标题锚点找。

    body.pdf 是由 puppeteer 渲染的，puppeteer 默认会把 <h2>/<h3> 写入 outline。
    我们直接读 doc.get_toc()，再折叠重复标题。
    """
    toc = doc.get_toc()  # [[level, title, page_no], ...]
    cleaned: list[tuple[int, str, int]] = []
    for level, title, page in toc:
        # 折叠 "X X" 重复
        if cleaned:
            prev = cleaned[-1]
            m = re.match(r"^(.+?)\1$", title)
            if m and m.group(1) == prev[1]:
                continue
            if title == prev[1]:
                continue
        # 砍掉过深（> 3）的条目
        if level > 3:
            continue
        cleaned.append((level, title.strip(), page))

    # 写回 outline
    if cleaned:
        doc.set_toc(cleaned)


def find_chapter_pages(doc: fitz.Document, titles: list[str]) -> list[tuple[int, str, int]]:
    """按标题关键词在每页文本里定位章节页码。

    匹配要求：关键词出现在该页**前 1/3 文本**内（章节标题在页首），
    且跳过目录页（目录页会同时列出所有标题，会污染匹配）。

    1-based 页码（含封面）。
    """
    # 先找出哪一页是「目录」页（含"目录"两字且有多个标题）
    toc_page = None
    for pno in range(1, doc.page_count):
        head = doc.load_page(pno).get_text()[:400]
        if "目录" in head and head.count("、") >= 4:
            toc_page = pno
            break

    result: list[tuple[int, str, int]] = []
    for title in titles:
        key = title.split("、")[-1][:12]
        found = None
        for pno in range(1, doc.page_count):
            if pno == toc_page:
                continue
            text = doc.load_page(pno).get_text()
            # 章节标题应出现在页面靠前位置
            head = text[: max(300, len(text) // 3)]
            if key in head:
                found = pno + 1  # 1-based（含封面）
                break
        result.append((1, title, found if found else 2))
    return result


def main() -> None:
    # 1. 直接打开两个 PDF（不修改）
    body = fitz.open(str(BODY_PDF))
    cover = fitz.open(str(COVER_PDF))

    # 2. 给 body 每页盖页眉/页脚（在拼装前盖，避免最终文档顺序乱）
    font = fitz.Font(fontfile=ZH_FONT)
    body_total = body.page_count
    print(f"body.pdf: {body_total} 页")

    for i in range(body_total):
        page = body.load_page(i)
        draw_headfoot(page, i + 1, body_total, font)

    # 3. 拼封面 + 正文：封面在前，正文在后
    final = fitz.open()
    final.insert_pdf(cover, from_page=0, to_page=0)
    final.insert_pdf(body, from_page=0, to_page=body_total - 1)

    page_total = final.page_count
    print(f"final pdf: {page_total} 页（封面 1 + 正文 {page_total - 1}）")

    # 4. 书签：优先用 body 自己的 outline（puppeteer outline:true 生成），
    #    拿不到就用「标题关键词定位页码」兜底。
    try:
        raw_toc = body.get_toc()
        cleaned: list[tuple[int, str, int]] = []
        if raw_toc:
            for level, title, page in raw_toc:
                if level > 3:
                    continue
                # Chrome outline 会把标题文本自我重复拼接（"情景推演情景推演"）。
                # 只要自重复就折叠成一半——不需要和前一项比较，否则前一项不同
                # 时就会漏网（2026-09-12 实测踩到）。
                m = re.match(r"^(.+?)\1$", title)
                if m:
                    title = m.group(1)
                if cleaned and title.strip() == cleaned[-1][1]:
                    continue
                is_doc_title = (level == 1 and not cleaned)
                cleaned.append((
                    level,
                    "封面" if is_doc_title else title.strip(),
                    1 if is_doc_title else page + 1,  # 文档标题书签指回封面
                ))
            print(f"outline（来自 body.pdf）: {len(cleaned)} 个条目")
        if not cleaned:
            cleaned = find_chapter_pages(final, CHAPTER_TITLES)
            print(f"outline（关键词定位兜底）: {len(cleaned)} 个条目")
        final.set_toc(cleaned)
        for lvl, t, p in cleaned:
            print(f"    {t}  ->  p{p}")
    except Exception as e:
        print(f"outline 处理失败：{e}")

    # 5. 子集化字体
    print("subset_fonts ...")
    final.subset_fonts()

    # 6. 保存
    final.save(str(FINAL_PDF), deflate=True, garbage=4)
    final.close()
    body.close()
    cover.close()

    # 7. 验证
    sz = FINAL_PDF.stat().st_size
    print(f"\nFINAL: {FINAL_PDF}")
    print(f"  size: {sz} bytes ({sz / 1024 / 1024:.2f} MB)")
    print(f"  pages: {page_total}")
    if sz > 5 * 1024 * 1024:
        print("  ⚠️  >5MB, subset_fonts 可能没生效")


if __name__ == "__main__":
    main()