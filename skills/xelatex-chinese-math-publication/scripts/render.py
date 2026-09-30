#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 PDF 逐页渲成 PNG，供肉眼验收版式与字形。
用法：python render.py 文件.pdf [缩放倍数，默认 2.6]
输出：与 PDF 同目录的「文件名_第N页.png」。
"""
import os
import sys

import pymupdf


def main():
    if len(sys.argv) < 2:
        print('用法：python render.py 文件.pdf [scale]')
        return 2
    pdf = os.path.abspath(sys.argv[1])
    if not os.path.isfile(pdf):
        print('找不到 %s' % pdf)
        return 2
    scale = float(sys.argv[2]) if len(sys.argv) > 2 else 2.6
    stem = pdf[:-4]

    doc = pymupdf.open(pdf)
    for i, page in enumerate(doc):
        out = '%s_第%d页.png' % (stem, i + 1)
        page.get_pixmap(matrix=pymupdf.Matrix(scale, scale)).save(out)
        print('  %s  %dx%d' % (os.path.basename(out),
                               page.rect.width * scale, page.rect.height * scale))
    print('共 %d 页' % doc.page_count)
    return 0


if __name__ == '__main__':
    sys.exit(main())
