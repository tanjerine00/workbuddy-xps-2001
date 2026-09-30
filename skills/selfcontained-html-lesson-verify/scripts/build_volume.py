# -*- coding: utf-8 -*-
"""把《很久以后》八讲合成单册：封面 + 出版说明 + 总目录 + 八章 + 全书文献说明。
   - 共享 CSS 以第一章（定版）为准，各章独有规则追加
   - 跨章冲突的 id（n# / fn#）按章加前缀
   - 给章内 h2 生成可跳转锚点，据此生成总目录
"""
import re, os, sys, glob, html

# 用法：python build_volume.py [书稿目录]   目录里应有 很久以后_第{一..八}章*.html
BOOK = (sys.argv[1] if len(sys.argv) > 1
        else r"C:/Users/zyx32/WorkBuddy/2026-09-14-09-35-29").replace("\\", "/")
ORDER = "一二三四五六七八"
chs = []
for i, ch in enumerate(ORDER, 1):
    g = glob.glob(os.path.join(BOOK, "很久以后_第%s章*.html" % ch))
    assert len(g) == 1, (ch, g)
    chs.append((i, g[0]))
print("合册：%d 章" % len(chs))

def load(p):
    return open(p, encoding="utf-8").read()


def parse_rules(css):
    """返回 [(selector, body)]，@media 整块算一条。"""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    out, i = [], 0
    while i < len(css):
        j = css.find('{', i)
        if j < 0: break
        sel = css[i:j].strip()
        depth, k = 1, j + 1
        while k < len(css) and depth:
            if css[k] == '{': depth += 1
            elif css[k] == '}': depth -= 1
            k += 1
        body = css[j + 1:k - 1].strip()
        if sel: out.append((sel, body))
        i = k
    return out


# ---------- 1. 收集内容 ----------
parts = []
base_css = None
base_sels = set()
extra_css = []
for i, p in chs:
    s = load(p)
    css = s.split('<style>')[1].split('</style>')[0]
    rules = parse_rules(css)
    if i == 1:
        base_css = css.strip()
        base_sels = set(sel for sel, _ in rules)
    else:
        for sel, body in rules:
            if sel.startswith('@media print'):
                continue
            if sel in base_sels:
                continue  # 以第一章为准
            extra_css.append((sel, body))

    # 正文（.page 的内层）+ 脚本
    body_html = s.split('<div class="page">', 1)[1]
    sp = body_html.rfind('<script')
    inner = body_html[:sp]
    inner = inner[:inner.rfind('</div>')]          # 去掉 .page 的收尾 </div>
    # 注意：必须从 body_html 切，不能用 s（下标会错位，把 HTML 混进脚本里）
    script = body_html[sp:].split('>', 1)[1].rsplit('</script>', 1)[0]
    assert '<p ' not in script[:400] and '<div' not in script[:400], \
        '第 %d 章脚本切片可疑: %s' % (i, script[:120])

    # n# / fn# 加章前缀（这两个 id 每章都有，全书会撞）
    inner = re.sub(r'id="fn(\d+)"', lambda m: 'id="c%d-fn%s"' % (i, m.group(1)), inner)
    inner = re.sub(r'id="n(\d+)"', lambda m: 'id="c%d-n%s"' % (i, m.group(1)), inner)
    inner = re.sub(r'href="#fn(\d+)"', lambda m: 'href="#c%d-fn%s"' % (i, m.group(1)), inner)
    inner = re.sub(r'href="#n(\d+)"', lambda m: 'href="#c%d-n%s"' % (i, m.group(1)), inner)

    # 给每个 h2 加锚点，供总目录跳转
    counter = [0]
    def add_anchor(m):
        counter[0] += 1
        return '<h2 id="c%d-h%d">' % (i, counter[0])
    inner = re.sub(r'<h2>', add_anchor, inner)

    # 章标题
    h1 = re.search(r'<h1>(.*?)</h1>', inner, re.S).group(1).strip()
    sub = re.search(r'<p class="ch-sub">(.*?)</p>', inner, re.S)
    parts.append({'i': i, 'file': os.path.basename(p), 'inner': inner,
                  'script': script, 'h1': h1,
                  'sub': sub.group(1).strip() if sub else '',
                  'chars': len(s.encode('utf-8'))})

# ---------- 2. 总目录 ----------
def plain(t):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', t)).strip()

def toc_entries(inner, i):
    """从章内 h2 提取目录项：编号节 / 章末注 / 附录。"""
    out = []
    for m in re.finditer(r'<h2 id="c%d-h(\d+)">(.*?)</h2>' % i, inner, re.S):
        hid, txt = m.group(1), m.group(2)
        t = plain(txt)
        no = re.match(r'^(\d+\.\d+)', t)
        if no:
            out.append(('sec', 'c%d-h%s' % (i, hid), t))
        elif t == '注':
            out.append(('sub', 'c%d-h%s' % (i, hid), '章末注'))
        elif t.startswith('附录'):
            out.append(('sub', 'c%d-h%s' % (i, hid), t))
    return out

toc_html = []
for pt in parts:
    i = pt['i']
    toc_html.append('  <li class="lv1"><a href="#ch%d"><span class="n">%s</span>%s</a></li>'
                    % (i, ['一','二','三','四','五','六','七','八'][i-1] + '·', pt['h1']))
    for kind, anc, t in toc_entries(pt['inner'], i):
        cls = 'lv2' if kind == 'sec' else 'lv3'
        toc_html.append('    <li class="%s"><a href="#%s">%s</a></li>' % (cls, anc, t))
TOC = "\n".join(toc_html)
print("目录条目 %d 条" % (len([1 for l in toc_html if '<li' in l])))

# ---------- 3. 全书文献说明 ----------
REF_TABLE = [
    ("第一讲", "英伟达 NV1 的公司史实与年份；网络流传版本的六处走样", "附录 C"),
    ("第二讲", "布尔、香农与中岛（Nakashima）三条线的文献考订", "附录 C / D"),
    ("第三讲", "黎曼演讲的刊年三说、高斯年龄、汉诺威大地测量、一九一九年日食精度", "附录 C"),
    ("第四讲", "拉东 1917、Oldendorf 的钉子实验与专利、Hounsfield 第一台机的九天", "附录 C"),
    ("第五讲", "有限域的确切年份（1830 而非 1831）；“决斗前夜写完一生数学”的夸大", "附录 C"),
    ("第六讲", "哈代 1940 原话、RSA 1977、Cocks 1973 的机密工作", "附录 C"),
    ("第七讲", "一八〇七提交／一八一一评奖／一八二二出版的年表；拉格朗日反对的具体理由", "附录 C"),
    ("第八讲", "六条等待年数的核算；对总纲“1831／129 年”的修正", "附录 C"),
]

# ---------- 4. 拼装 ----------
head = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>很久以后 · 数学与现实之间，那几十年的时差（全一卷）</title>
<style>
%s

/* ============ 单册增补：封面、目录、页边距 ============ */
@page{ size:A4; margin:22mm 20mm; }
.cover{text-indent:0; padding-top:16vh; text-align:left}
.cover .bk{font-family:var(--sans); font-size:15px; letter-spacing:.5em; color:var(--ink3); margin:0 0 18px}
.cover h1.title{font-family:var(--sans); font-size:52px; font-weight:700; letter-spacing:.06em; margin:0 0 20px; line-height:1.15}
.cover .rule{width:88px; height:3px; background:var(--ink); margin:0 0 24px}
.cover .sub{font-family:var(--serif); font-size:21px; line-height:1.8; color:var(--ink2); margin:0 0 8px}
.cover .sub2{font-family:var(--sans); font-size:14px; color:var(--ink3); line-height:1.9; margin:0}
.cover .meta{font-family:var(--sans); font-size:13px; color:var(--ink3); line-height:2; margin-top:34px;
             border-top:1px solid var(--line); padding-top:14px}
.frontmatter{break-before:page; page-break-before:always; margin-top:0}
.toc{list-style:none; margin:22px 0 0; padding:0; text-indent:0; font-family:var(--sans)}
.toc li{margin:0; line-height:1.85}
.toc a{border:0; color:inherit}
.toc .lv1{font-size:15.5px; font-weight:600; margin-top:16px; padding-top:9px; border-top:1px solid var(--line)}
.toc .lv1 .n{color:var(--accent); margin-right:.5em}
.toc .lv2{font-size:13.5px; color:var(--ink2); padding-left:1.6em}
.toc .lv3{font-size:12.5px; color:var(--ink3); padding-left:2.6em}
.toc-note{font-family:var(--sans); font-size:12.5px; color:var(--ink3); line-height:1.85; margin-top:26px;
          text-indent:0; border-top:1px solid var(--line); padding-top:12px}
.chap{break-before:page; page-break-before:always}
.chap:first-of-type{break-before:auto; page-break-before:auto}
.colophon{break-before:page; page-break-before:always; font-family:var(--sans); font-size:13.5px;
          line-height:1.95; color:var(--ink2); text-indent:0}
.colophon h2{font-size:18px; color:var(--ink)}
.colophon p{text-indent:0; margin:11px 0}
.colophon p b{color:var(--ink)}
@media print{
  .cover{padding-top:0; margin-top:70mm}
  .toc .lv1{break-inside:avoid; page-break-inside:avoid}
  .toc li{break-inside:avoid; page-break-inside:avoid}
}
%s
</style>
</head>
<body>
<div class="page">

<section class="cover">
  <p class="bk">很久以后</p>
  <h1 class="title">很久以后</h1>
  <div class="rule"></div>
  <p class="sub">数学与现实之间，那几十年的时差</p>
  <p class="sub2">八讲读本　·　高中至大学低年级</p>
  <p class="meta">结构决定一个想法能不能便宜，<br>现实决定它用不用得上。<br>数学只负责前一半。</p>
</section>

<section class="frontmatter">
<h2>出版说明</h2>

<p class="noind">这本读本要回答的，是一个很具体的问题：<strong>为什么一个数学想法在它被想出来的那一年常常没用，而在几十年之后突然到处都在用。</strong></p>

<p>八讲各自挑一个案例，每一讲都固定回答两件事。第一件是<strong>结构</strong>：这个想法内部藏着什么，所以它一定能行、而且用起来便宜。第二件是<strong>时间</strong>：现实为什么偏偏要等那么多年才来用它。</p>

<p>八讲里的等待，长短差得很远——最短十五年，最长一百三十年。把这些等待放在一起看，会看到一件不太舒服的事：<strong>绝大多数情况下，没有人做错什么。</strong>不是有人打压，不是有人看不懂，只是那个需要它的世界还没有长出来。只有两讲是例外，而那两讲恰好最能说明"人"在其中的位置。</p>

<div class="box key">
  <p class="h">这本书的立场</p>
  <p>凡属文献记载的，注明出处；凡属推断的，写明是推断；凡各来源冲突、或只有流行说法而查不到一手依据的，单列成"考订"并标注存疑。</p>
  <p><strong>这套书不想讲一个励志故事，它想讲一件可以核查的事。</strong>因此每章都带四个附录：课堂执行建议、作业与评价量规、文献考订与勘误、本卷体例。正文给读者，附录给课堂。</p>
</div>

<p>关于阅读方式，只有一句要提醒：<strong>书里的图都是可以动手的</strong>。用鼠标拖一拖、拉一拉滑块，比读三段解释更快。凡是标了“图 x-y”的地方，图上出现了数字，正文就一定用同一组数字。</p>

<h2>总目录</h2>
<ul class="toc">
%s
</ul>
<p class="toc-note">目录中的每一行都可以点击跳转。<strong>未标注印刷页码</strong>：本卷同时用于屏幕阅读与 A4 打印，纸质版页码随排版引擎浮动，故不印死页码，而在 PDF 里生成书签目录。</p>
</section>

""" % (base_css, "\n".join("%s{%s}" % (s, b) for s, b in extra_css), TOC)

body = []
for pt in parts:
    body.append('<section class="chap" id="ch%d">\n%s\n</section>' % (pt['i'], pt['inner']))

ref_rows = "\n".join(
    '<tr><td class="k">%s</td><td>%s</td><td class="num">%s</td></tr>' % r for r in REF_TABLE)

tail = """
<section class="colophon">
<h2>全书文献与考订说明</h2>

<p>本卷不另设“总参考文献”，而是<strong>把文献考订分散到每一章的附录 C</strong>。这样做的理由很实际：同一个出处常常只跟某一章的某一句话有关，集中在书末会让人来回翻；更重要的是，若在书末另立一份总表，同一处考订就有两个版本，日后修订时几乎必然打架。</p>

<p>各章的考订重点如下：</p>

<div class="tbl">
<div class="tcap"><b>表 全-1</b>　各章文献考订的位置与重点</div>
<table>
<tr><th style="width:14%%">章</th><th>考订重点</th><th style="width:16%%">位置</th></tr>
%s
</table>
</div>

<p><strong>三条通用的处理原则：</strong></p>

<p>一、<strong>一手优先。</strong>凡技术细节（一台机器的实验记录、一份专利、一篇论文的页码），一律回到原始文件；二手综述只用于定位，不作为结论依据。</p>

<p>二、<strong>流行说法单独标出。</strong>本卷至少揭穿了三处广为流传但站不住的说法：第三章的"一九七七年工程师不相信相对论所以故意不打开频率合成器"（原始备忘录只记过程，未记动机）、第五章的"伽罗瓦在决斗前夜写完一生数学"（学界普遍认为是被夸大）、第一讲的"黄仁勋在书店买了三本每本六十美元的书"（把口袋里的现金说成了书的单价）。<strong>把它们留在书里而不是删掉，是因为它们本身就是这项研究的一部分。</strong></p>

<p>三、<strong>数值一律可复现。</strong>正文与图中出现的每一个数字，都能由随章的验证脚本复算出来。演示程序与验证脚本若因分辨率等口径不同而给出略有差异的数字，正文一律采用<strong>读者在页面上实际看到的那一组</strong>，并在附录说明差异来源。</p>

<h2>关于这套书本身的一处坦白</h2>

<p>本卷用一个框架来组织八个案例：<strong>结构决定便宜，现实决定用不用得上，等待可按原因分成三类。</strong>这个框架本身也是从这八个案例上长出来的——八个样本证明不了任何事。第八章会把这一点正面写出来，包括对“幸存者偏差”的反驳：我们讲的全是“等了很久最后终于被用上”的故事，而那些等了很久、最后永远没被用上的，我们看不见，因为它们不在书里。</p>

<p>所以这套书的结论是克制的：<strong>能做的事只有一件——把结构备好。</strong></p>

</section>
""" % ref_rows

scripts = []
for pt in parts:
    scripts.append('<script>\n/* ===== 第 %d 章脚本 ===== */\n%s\n</script>' % (pt['i'], pt['script'].strip()))

out = head + "\n".join(body) + tail + "\n</div>\n" + "\n".join(scripts) + "\n</body>\n</html>\n"

dst = os.path.join(BOOK, "很久以后_全一卷.html")
open(dst, "w", encoding="utf-8").write(out)
print("\n已生成: %s" % dst)
print("大小: %.1f KB" % (len(out.encode('utf-8')) / 1024))
print("各章字节: %s" % ", ".join("第%d章 %dKB" % (p['i'], p['chars'] // 1024) for p in parts))
