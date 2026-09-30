# -*- coding: utf-8 -*-
"""《很久以后》各章结构 + JS 语法自检，可复用到全部章节。"""
import re, os, sys, subprocess, glob

NODE = r"C:/Users/zyx32/.workbuddy/binaries/node/versions/22.22.2-3/node.exe"
TMP  = os.environ.get("TEMP", ".")
# 用法：python book_check.py [书稿目录]
BOOK = (sys.argv[1] if len(sys.argv) > 1
        else r"C:/Users/zyx32/WorkBuddy/2026-09-14-09-35-29").replace("\\", "/")

def check(path):
    raw = open(path, encoding="utf-8").read()
    name = os.path.basename(path)
    # 剥掉 script / style 内容再数标签，否则 i<p.length 这类代码会被当标签
    s = re.sub(r'<script\b.*?</script>', '<script></script>', raw, flags=re.S)
    s = re.sub(r'<style\b.*?</style>', '<style></style>', s, flags=re.S)
    out = []
    out.append("=" * 68)
    out.append("%s\n  bytes=%d  lines=%d" % (name, len(raw.encode("utf-8")), raw.count("\n") + 1))

    # --- div 深度 ---
    d = 0; mn = 0; mx = 0
    for m in re.finditer(r'<div\b[^>]*>|</div>', s):
        d += 1 if m.group(0).startswith("<div") else -1
        mn = min(mn, d); mx = max(mx, d)
    out.append("  div: final=%d  min=%d  max=%d  %s" % (d, mn, mx, "OK" if d == 0 else "**MISMATCH**"))

    # --- 其它标签配对 ---
    bad = []
    for tag in ["section", "table", "figure", "svg", "script", "style", "canvas",
                "header", "footer", "h1", "h2", "h3", "p", "figcaption"]:
        o = len(re.findall(r'<%s\b' % tag, s))
        c = len(re.findall(r'</%s>' % tag, s))
        if o != c:
            bad.append("%s %d/%d" % (tag, o, c))
    out.append("  tag balance: " + ("OK" if not bad else "**" + ", ".join(bad) + "**"))

    # --- 空 div / 未闭合引号粗查 ---
    out.append("  canvas=%d  svg=%d  figure=%d" % (
        len(re.findall(r'<canvas', s)), len(re.findall(r'<svg', s)),
        len(re.findall(r'<figure', s))))

    # --- 章末注 ---
    notes = re.findall(r'<p class="note" id="n(\d+)">', raw)
    refs_in_order = re.findall(r'class="fnr" id="fn(\d+)"', raw)
    out.append("  notes=%s" % (len(notes),))
    seen = []
    for n2 in refs_in_order:
        if n2 not in seen: seen.append(n2)
    ordered = [int(x) for x in notes] == [int(x) for x in seen]
    out.append("  note refs=%s  编号按引用顺序=%s" % (
        len(refs_in_order), "OK" if ordered else "**乱序: 引用 %s / 注 %s**" % (seen, notes)))
    backs = re.findall(r'class="back" href="#fn(\d+)"', raw)
    dangling = [b for b in backs if b not in refs_in_order]
    out.append("  back-links=%d  dangling=%s" % (len(backs), dangling or "none"))

    # --- 附录 ---
    app = re.findall(r'<h2>(附录 [A-D][^<]*)</h2>', s)
    out.append("  appendix: " + (" | ".join(app) if app else "**none**"))

    # --- 图编号 ---
    figs = re.findall(r'<span class="fno">图 ([0-9]+-[0-9]+)</span>', s)
    tabs = re.findall(r'<b>表 ([0-9A-Z]+-[0-9]+)</b>', s)
    out.append("  figures: %s" % (figs,))
    out.append("  tables: %s" % (tabs,))

    # --- 图号必须按"文档顺序"递增（曾出过 4-2 排在 4-1 前面，只有印出来才发现） ---
    seq = [tuple(int(x) for x in f.split("-")) for f in figs]
    jump = [("%d-%d" % a, "%d-%d" % b) for a, b in zip(seq, seq[1:]) if b <= a]
    out.append("  figure order: %s" % ("OK" if not jump else "**OUT OF ORDER** %s" % jump))

    # --- 正文里引称的图表是否都存在 ---
    body = re.sub(r'<figure\b.*?</figure>', '', s, flags=re.S)
    body = re.sub(r'<div class="tbl">.*?</div>', '', body, flags=re.S)
    cited = set(re.findall(r'图\s*([0-9]+-[0-9]+)', body)) | set(re.findall(r'表\s*([0-9A-Z]+-[0-9]+)', body))
    have  = set(figs) | set(tabs)
    out.append("  cited-but-missing: %s" % (sorted(cited - have) or "none"))

    # --- JS 语法（必须从原始文本里抽，不能从剥空的 s 里抽） ---
    scripts = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', raw, re.S)
    js = "\n;\n".join(scripts)
    if js.strip():
        p = os.path.join(TMP, "chk_%s.js" % re.sub(r'\W', '_', name)[:40])
        open(p, "w", encoding="utf-8").write(js)
        r = subprocess.run([NODE, "--check", p], capture_output=True, text=True)
        out.append("  node --check: exit=%d %s" % (r.returncode, r.stderr.strip()[:180]))
    else:
        out.append("  node --check: (no inline script)")

    # --- 未转义的裸 & 和 < 粗查 ---
    stray = re.findall(r'&(?!(amp|lt|gt|quot|apos|nbsp|#\d+|#x[0-9a-fA-F]+);)', s)
    if stray:
        out.append("  **raw '&' x%d**" % len(stray))

    return "\n".join(out), (d == 0 and not bad and ordered and not dangling)

if __name__ == "__main__":
    files = sys.argv[1:] or sorted(glob.glob(os.path.join(BOOK, "很久以后_第*.html")))
    allok = True
    for f in files:
        txt, okv = check(f)
        allok = allok and okv
        print(txt)
    print("=" * 68)
    print("ALL OK" if allok else "**SOME CHECKS FAILED**")
