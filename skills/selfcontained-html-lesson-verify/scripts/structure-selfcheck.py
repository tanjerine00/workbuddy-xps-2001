# -*- coding: utf-8 -*-
"""《直觉的边界》第一章 结构自检"""
import io, os, re, collections, sys

BOOK = r'C:\Users\zyx32\WorkBuddy\2026-09-14-09-35-29'
F = os.path.join(BOOK, '直觉的边界_第一章_连续的世界真的像我们想象的那样吗.html')
s = io.open(F, encoding='utf-8').read()

out = []
def chk(name, cond, extra=''):
    out.append(('OK  ' if cond else '**FAIL**') + '  ' + name + (('   ' + str(extra)) if extra else ''))

# ---------- 1. 章节骨架 ----------
h2s = re.findall(r'<h2><span class="no">([\d.]+)</span>([^<]*)</h2>', s)
nums = [h[0] for h in h2s]
want = ['1.1','1.2','1.3','1.4','1.5','1.6','1.7','1.8','1.9']
chk('小节编号 1.1–1.9 齐全且有序', nums == want, nums)

# ---------- 2. 栏目 ----------
for cls, exp, label in [('ask', 1, '本章只问一个问题'),
                        ('trap', 1, '直觉陷阱'),
                        ('strict', 3, '严格地说'),
                        ('world', 1, '数学走出纸面'),
                        ('newint', 1, '本章获得的新直觉'),
                        ('sum', 1, '本章辩证小结'),
                        ('ex', 1, '思考题')]:
    n = len(re.findall(r'class="' + cls + '"', s))
    chk('栏目 %s ×%d' % (label, exp), n == exp, n)
# 思考题 4 题
nli = len(re.findall(r'<li>', s))
chk('思考题 4 题', nli == 4, nli)

# ---------- 3. 图 ----------
capno = re.findall(r'<span class="fno">图\s*([\d\-]+)</span>', s)
chk('图号 1-1…1-4 按文档顺序', capno == ['1-1','1-2','1-3','1-4'], capno)
chk('canvas 4 个', len(re.findall(r'<canvas ', s)) == 4)
chk('滑块 5 个', len(re.findall(r'type="range"', s)) == 5)
chk('读数块 4 个', len(re.findall(r'class="readout"', s)) == 4)
# 每个图都必须有「它让什么结构变得可见」
chk('四张图都有"它让什么结构变得可见"', len(re.findall(r'它让什么结构变得可见', s)) == 4)
# 每个图题都必须带问题
chk('四张图都配了"一图一问题"式图题', len(re.findall(r'<figcaption>', s)) == 4)

# ---------- 4. 注与出处 ----------
fnr = re.findall(r'<span class="fnr" id="(fn\d+)">', s)
notes = re.findall(r'<p class="note" id="(n\d+)">', s)
chk('正文角标 fn1–fn6', fnr == ['fn1','fn2','fn3','fn4','fn5','fn6'], fnr)
chk('章末注 n1–n6', notes == ['n1','n2','n3','n4','n5','n6'], notes)
backs = re.findall(r'<a class="back" href="#(fn\d+)">', s)
chk('每条注都有回链且一一对应', backs == fnr, backs)

# ---------- 5. LaTeX 源 ----------
# 页脚那句以 <span class="m">data-tex</span> 是"讲属性的散文"，不算公式，单独排除
prose = s.count('<span class="m">data-tex</span>')
s2 = s.replace('<span class="m">data-tex</span>', '<span class="m">@@PROSE@@</span>')
tex = re.findall(r'data-tex="([^"]*)"', s2)
mspans = len(re.findall(r'class="m"', s2)) - prose      # 排除散文那一个
chk('data-tex 公式源 ≥ 12 处', len(tex) >= 12, len(tex))
chk('每个公式元素都带 data-tex', mspans == len(tex), '%d 个 .m / %d 个 data-tex（排除 %d 处散文）' % (mspans, len(tex), prose))
# 不依赖外部资源
chk('无外部 script src', 'src="http' not in s and '<script src' not in s)
chk('无 MathJax / KaTeX', ('MathJax' not in s) and ('katex' not in s.lower()))
chk('无外链字体/CDN', 'cdn.' not in s.lower() and 'fonts.googleapis' not in s)

# ---------- 6. id 唯一性 ----------
ids = re.findall(r'\sid="([^"]+)"', s)
dup = [k for k, v in collections.Counter(ids).items() if v > 1]
chk('id 无重复', not dup, dup)

# ---------- 7. 脚本 ----------
chk('内联 script 已注入', '<!-- CH1-FIGS-SCRIPT -->' in s)
chk('四个绘制函数都在', all(k in s for k in ['__draw11','__draw12','__draw13','__draw14']))
chk('没有残留的 </script> 破坏', s.count('<script') == s.count('</script>'), s.count('<script'))

# ---------- 8. 篇幅 ----------
body = s[s.index('<div class="page">'):s.index('<script>')]
han = len(re.findall(r'[\u4e00-\u9fff]', body))
out.append('---- 正文汉字数（不含脚本）：%d ----' % han)
out.append('---- 文件大小：%d 字节 ----' % len(s.encode('utf-8')))

print('\n'.join(out))
bad = [x for x in out if x.startswith('**')]
print('\n===== %s =====' % ('全部通过' if not bad else '%d 项未通过' % len(bad)))
sys.exit(1 if bad else 0)
