#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键跑通 XeLaTeX 中文数学出版链：xelatex -> biber -> xelatex -> xelatex。
用法：
    python build.py 你的文件.tex
不带参数则编译同目录下的 template.tex。

跑完会打印三道验收读数（错误数 / 缺字数 / 未定义引用数），
任一项非零就返回非零退出码 —— 让 CI 或批处理能看见失败。
"""
import os
import re
import subprocess
import sys

MIKTEX_BIN = r'C:\Users\zyx32\AppData\Local\Programs\MiKTeX\miktex\bin\x64'
PYMUPDF_PY = r'C:\Users\zyx32\.workbuddy\binaries\python\envs\default\Scripts\python.exe'


def run(cmd, cwd):
    env = dict(os.environ)
    env['PATH'] = MIKTEX_BIN + os.pathsep + env.get('PATH', '')
    p = subprocess.run(cmd, cwd=cwd, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p.returncode


def main():
    tex = sys.argv[1] if len(sys.argv) > 1 else 'template.tex'
    tex = os.path.abspath(tex)
    if not os.path.isfile(tex):
        print('找不到 %s' % tex)
        return 2
    d, base = os.path.dirname(tex), os.path.splitext(os.path.basename(tex))[0]

    print('[1/4] xelatex ...')
    run(['xelatex', '-interaction=nonstopmode', base + '.tex'], d)
    print('[2/4] biber ...')
    run(['biber', base], d)
    print('[3/4] xelatex ...')
    run(['xelatex', '-interaction=nonstopmode', base + '.tex'], d)
    print('[4/4] xelatex ...')
    run(['xelatex', '-interaction=nonstopmode', base + '.tex'], d)

    log_path = os.path.join(d, base + '.log')
    pdf_path = os.path.join(d, base + '.pdf')
    if not os.path.isfile(pdf_path):
        print('!! 没有产出 PDF，去看 %s' % log_path)
        return 1

    log = open(log_path, encoding='utf-8', errors='replace').read()
    errs = re.findall(r'^!.*$', log, re.M)
    missing = log.count('Missing character')
    undef = len(re.findall(r'undefined', log, re.I))

    print('')
    print('PDF      : %s  (%d 字节)' % (pdf_path, os.path.getsize(pdf_path)))
    print('错误     : %d' % len(errs))
    for e in errs[:5]:
        print('           ' + e.strip())
    print('缺字     : %d   ← 中文缺字不报错、只是不印出来，必须是 0' % missing)
    print('未定义引用: %d   ← 非 0 说明 biber 或多跑一遍 xelatex 少了' % undef)

    # 顺手出图，供肉眼验收（字形类问题只能靠眼睛）
    render = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'render.py')
    if os.path.isfile(render) and os.path.isfile(PYMUPDF_PY):
        subprocess.run([PYMUPDF_PY, render, pdf_path])

    return 1 if (errs or missing or undef) else 0


if __name__ == '__main__':
    sys.exit(main())
