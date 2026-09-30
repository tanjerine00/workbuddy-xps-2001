# -*- coding: utf-8 -*-
"""把 HTML 可见文本里的 ASCII 双引号成对替换为中文引号 “”。
   - 严格跳过 <script>/<style> 内容（js 字符串与字体名里的引号必须保留 ASCII）
   - 跳过标签属性（属性在 <...> 内，本就不在文本段里）
   - 用全局状态机保证跨标签（如 " <b> </b> "）也能正确配对
   用法: python fix_quotes.py <file> [--apply]
"""
import io, re, sys

def collect_text_segments(s):
    """返回 [(start, end)] 指向标签之外的文本区间（跳过 script/style）。"""
    protected = []
    def stash(m):
        protected.append(m.span())
        return m.group(0)
    re.sub(r'<(script|style)\b[^>]*>[\s\S]*?</\1\s*>', stash, s, flags=re.I)
    # 还要挡掉自闭合不了的 <script ... /> 不发生；忽略
    segs = []
    pos = 0
    for m in re.finditer(r'<[^>]+>', s):
        segs.append((pos, m.start()))
        pos = m.end()
    segs.append((pos, len(s)))
    def inside(p):
        return any(a <= p < b for a, b in protected)
    return segs, inside

def run(path, apply_):
    s = io.open(path, encoding='utf-8').read()
    segs, inside = collect_text_segments(s)
    opened = False
    changes = []
    out = list(s)
    for (a, b) in segs:
        if inside(a):
            continue
        t = s[a:b]
        for k, ch in enumerate(t):
            if ch == '"':
                p = a + k
                rep = '”' if opened else '“'
                changes.append((p, rep, s[max(0, p - 16):p], s[p + 1:p + 17]))
                out[p] = rep
                opened = not opened
    print('=== %s ===' % path.split('\\')[-1])
    print('文本段 %d 个；将替换 %d 处引号' % (len(segs), len(changes)))
    for p, rep, before, after in changes:
        print('   %s  %s  <<"  %s | %s' % (rep, rep == '“' and 'OPEN ' or 'CLOSE', before, after))
    if opened:
        print('  !! 警告：引号总数为奇数，最后一个引号配对可疑')
    if apply_:
        io.open(path, 'w', encoding='utf-8', newline='\n').write(''.join(out))
        print('  已写入')
    return s

if __name__ == '__main__':
    f = sys.argv[1]
    run(f, '--apply' in sys.argv)
