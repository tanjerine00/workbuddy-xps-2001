'use strict';
/* 排版门禁（DOM 版）：查「数学符号排得对不对」，与 math-symbol-gate.js 互补。
   math-symbol-gate 查的是字符层面（裸根号 / Unicode 上下标 / en dash / 半角标点）；
   本门禁查的是**排字规范**层面：

     ① 斜体范围 —— .m 是「变量默认斜体」的语境，里面的数字、算符、函数名、单位
        必须包在 .up（或 .m.r）里扳回正体。这是 ISO 80000-2 / GB/T 3102.11 的硬要求：
        "g = 9.8" 里的 9.8 和 = 不能是斜的。
     ② LaTeX 源纯度 —— data-tex 里不许出现 HTML 实体（&gt; &lt; &amp;）。
        页脚承诺"公式一律以 LaTeX 源格式保存"，混进实体就自相矛盾了。
     ③ 正文流里的裸数学变量 —— 希腊字母必须落在 .m 里，否则会以正文宋体的字形
        混进来，与同章其他位置的同一个符号两副面孔。
     ④ 字形覆盖 —— 书里用到的数学符号在本机字体栈下必须真有字形，
        而不是渲染成缺字方框（.notdef）。
     ⑤ 行内公式盒的宽度 —— .rad / .frac 是 inline-block，会**继承**中文书体例里的
        p{text-indent:2em}，使盒宽凭空多出 2em；根号横线按盒宽画，于是横线横向长出 2em、
        被开方数被甩到最右端（2026-09-15 编辑大纲里那个「√———2」缺陷就是这个成因）。
        这一条是那次漏检后补的：原来的根号像素检查拿「元素自己的宽度」当基准，等于自证。

   用法：node typeset-gate.js <章节 HTML 的绝对路径>
   退出码：有 FAIL 则为 1。
*/
const puppeteer = require('puppeteer-core');

const CHROME = 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe';
const FILE = process.argv[2];

let pass = 0, fail = 0, warn = 0;
function ok(n, c, extra) {
  if (c) { pass++; console.log('OK    ' + n + (extra ? '   ' + extra : '')); }
  else { fail++; console.log('**FAIL**  ' + n + (extra ? '   ' + extra : '')); }
}
function wn(n, c, extra) { if (!c) { warn++; console.log('warn  ' + n + (extra ? '   ' + extra : '')); } }

/* 必须正体的字符：数字 + 算符 + 括号 + 比/除号 + 常用关系符 */
const UPRIGHT = /[0-9=<>+\-\u2212/\u00B7\u22C5\u2248\u2260\u2264\u2265()\[\]{}\u00D7\u00F7\u00B1\u2236,.]/;
/* 希腊字母：正文里出现即应是数学变量 */
const GREEK = /[\u0391-\u03C9]/;

(async () => {
  const b = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--allow-file-access-from-files', '--hide-scrollbars']
  });
  const p = await b.newPage();
  await p.setViewport({ width: 900, height: 1400, deviceScaleFactor: 1 });
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto('file:///' + FILE.replace(/\\/g, '/'), { waitUntil: 'load', timeout: 120000 });
  await new Promise(r => setTimeout(r, 1800));

  const r = await p.evaluate(() => {
    const UPRIGHT_SRC = '[0-9=<>+\\-\\u2212/\\u00B7\\u22C5\\u2248\\u2260\\u2264\\u2265()\\[\\]{}\\u00D7\\u00F7\\u00B1\\u2236,.]';
    const UPRE = new RegExp(UPRIGHT_SRC);
    const GREEK_SRC = '[\\u0391-\\u03C9]';
    const GRK = new RegExp(GREEK_SRC);

    const badItalic = [];   // ① 斜体语境里的正体字符
    const badTex = [];      // ② data-tex 里的 HTML 实体
    const badVar = [];      // ③ 正文流里的裸数学变量
    const CHARS = '\u221A\u2236\u2013\u2014\u2212\u00D7\u00B7\u22C5\u2248\u2264\u2265' +
                  '\u00B0\u2032\u2033\u03C0\u03B4\u03B8\u03B5\u0394\u211D\u211A\u21A9' +
                  '\u2192\u2208\u221E\u2261\u00BD\u00BC\u2044';

    /* ---- ① .m 内部：找「到最近的 .m 为止，祖先链上没有 .up」的文本节点 ---- */
    document.querySelectorAll('.m').forEach(m => {
      if (m.classList.contains('r')) return;              // .m.r 整块即正体
      const w = document.createTreeWalker(m, NodeFilter.SHOW_TEXT);
      while (w.nextNode()) {
        const n = w.currentNode;
        let e = n.parentElement, upright = false;
        while (e && e !== m) {
          if (e.classList.contains('up')) { upright = true; break; }
          e = e.parentElement;
        }
        if (upright) continue;
        const t = n.nodeValue || '';
        const hit = t.match(UPRE);
        if (hit) {
          badItalic.push('[tex="' + (m.getAttribute('data-tex') || '?') + '"] ' +
            JSON.stringify(t.slice(0, 40)));
        }
      }
    });

    /* ---- ② data-tex 纯度 ---- */
    document.querySelectorAll('[data-tex]').forEach(el => {
      const v = el.getAttribute('data-tex');
      if (/&(gt|lt|amp|quot|nbsp);/.test(v)) badTex.push(v);
    });

    /* ---- ③ 正文流里的裸希腊字母（图内控件 UI 另有体例，排除） ---- */
    const w2 = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (w2.nextNode()) {
      const n = w2.currentNode, pe = n.parentElement;
      if (!pe || /^(SCRIPT|STYLE)$/.test(pe.tagName)) continue;
      if (pe.closest('.m')) continue;                     // 已在数学语境里
      if (pe.closest('figure.fig')) continue;             // 图内的滑杆／读数框 UI
      const t = n.nodeValue || '';
      const g = t.match(GRK);
      if (g) badVar.push(t.slice(Math.max(0, g.index - 16), g.index + 12));
    }

    /* ---- ④ 字形覆盖：不做硬断言，只采集信号 ----
       本机实测：getBoundingClientRect 对非 ASCII 符号会退回一个统一的"整字宽度"
       （√ × · ≈ ≤ 都测成 16px，与汉字"永"及 .notdef 的宽度相同），据此判定缺字形
       必然误报；U+2044 测成 0 宽，但放大截图里它明明画得出来。
       所以这一项只报「document.fonts.check 认为字体栈覆盖不了的字符」与「宽度为 0 的异常」，
       真正的字形验收走 工具\验收\typeset_sample.js 的 4× 放大截图
       —— 字形类改动必须肉眼过，这是本项目在根号那次踩坑后立下的规矩。 */
    const fontsMissing = [];
    const zeroWidth = [];
    const host = document.createElement('div');
    host.style.cssText = 'position:absolute;left:-9999px;top:0;white-space:pre;' +
      'font-family:"Songti SC","SimSun","Source Han Serif SC",Georgia,serif;font-size:16.5px';
    document.body.appendChild(host);
    for (const ch of CHARS.split('')) {
      if (document.fonts && document.fonts.check &&
          !document.fonts.check('16.5px "SimSun"', ch)) fontsMissing.push(ch);
      const s = document.createElement('span');
      s.style.cssText = 'display:inline-block;white-space:pre';
      s.textContent = ch;
      host.appendChild(s);
      if (s.getBoundingClientRect().width === 0) zeroWidth.push(ch);
    }
    host.remove();

    /* ---- ⑤ 行内公式盒不得被「继承的首行缩进」撑宽 ----
       .rad / .frac 是 display:inline-block。中文书体例里 p{text-indent:2em} 会**被继承**进来，
       而首行缩进作用在 inline-block 内部的第一行上，shrink-to-fit 宽度因此凭空多出 2em。
       根号的横线是按「盒子宽度」画的，于是横线横向长出 2em、被开方数被甩到最右端
       —— 这正是 2026-09-15 编辑大纲里那个「√———2」缺陷的成因。
       ① 直接查 computed text-indent（根因，零误报）；
       ② 再查 .rad 盒宽是否只由被开方数决定（防别的撑宽方式）。 */
    const indentLeak = [];
    document.querySelectorAll('.rad,.frac,.m,.up').forEach(el => {
      const cs = getComputedStyle(el);
      /* text-indent 只对「块容器」起作用；.m/.up 是 inline，继承到也没有效果，不算问题。
         真正会中招的是 inline-block（.rad/.frac）—— 缩进落在它内部第一行上，
         而 shrink-to-fit 宽度会把这段缩进算进去。 */
      if (!/inline-block|inline-flex|inline-grid|table|flow-root/.test(cs.display)) return;
      const ti = cs.textIndent;
      if (ti && ti !== '0px' && ti !== '0em')
        indentLeak.push({ sel: el.className, ti: ti, html: el.outerHTML.slice(0, 60) });
    });
    const bloated = [];
    const cvs = document.createElement('canvas'), g2 = cvs.getContext('2d');
    document.querySelectorAll('.rad').forEach(el => {
      const cs = getComputedStyle(el), box = el.getBoundingClientRect();
      g2.font = cs.font;
      const tw = g2.measureText(el.textContent || '').width;
      /* 允许：被开方数宽 + padding + 0.35em 余量 */
      const budget = tw + parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight) +
                     0.35 * parseFloat(cs.fontSize);
      if (box.width > budget)
        bloated.push('"' + el.textContent + '" 盒宽 ' + box.width.toFixed(1) +
                     ' > 被开方数宽 ' + tw.toFixed(1) + '（多出 ' +
                     (box.width - tw).toFixed(1) + 'px）');
    });

    return { badItalic, badTex, badVar, fontsMissing, zeroWidth, indentLeak, bloated };
  });

  ok('① .m 里的数字/算符都是正体（变量才斜体）', r.badItalic.length === 0,
     (r.badItalic.length ? r.badItalic.length + ' 处：' : '') + r.badItalic.slice(0, 5).join(' | '));
  ok('② data-tex 是纯 LaTeX 源（没混进 HTML 实体）', r.badTex.length === 0,
     r.badTex.slice(0, 5).join(' | '));
  ok('③ 正文里的希腊字母都在 .m 数学语境内', r.badVar.length === 0,
     (r.badVar.length ? r.badVar.length + ' 处：' : '') + r.badVar.slice(0, 5).join(' | '));
  wn('字形覆盖：document.fonts 认为字体栈覆盖不了 ' + r.fontsMissing.length + ' 个符号',
     r.fontsMissing.length === 0, r.fontsMissing.join(' '));
  wn('字形覆盖：有 ' + r.zeroWidth.length + ' 个符号测出 0 宽（异常）',
     r.zeroWidth.length === 0, r.zeroWidth.join(' '));
  console.log('      注：本机 getBoundingClientRect 判不了字形（√ × · ≈ 都测成整字宽），');
  console.log('          字形验收以 工具\\验收\\typeset_sample.js 的放大截图为准。');
  ok('④ 页面无脚本报错', errs.length === 0, errs.slice(0, 3).join(' | '));
  ok('⑤ 行内公式盒没被继承的首行缩进撑宽',
     r.indentLeak.length === 0 && r.bloated.length === 0,
     (r.indentLeak.length ? r.indentLeak.map(o => o.sel + ' text-indent=' + o.ti).join(' | ') : '') +
     (r.bloated.length ? '  ' + r.bloated.slice(0, 3).join(' | ') : ''));

  console.log('\n===== ' + pass + ' 通过 / ' + fail + ' 失败 / ' + warn + ' 警告 =====');
  await b.close();
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('CRASH', e); process.exit(2); });
