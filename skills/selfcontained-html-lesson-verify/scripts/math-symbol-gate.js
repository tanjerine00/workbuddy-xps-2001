'use strict';
/* 数学符号门禁（DOM 版）：查渲染后的可见文字，而不是静态 HTML。
   为什么要 DOM：读数框里的文字是脚本运行时填进去的，静态扫源码看不到。
   用法：node ch_sym_dom.js <章节 HTML 的绝对路径> */
const puppeteer = require('puppeteer-core');
const path = require('path');

const CHROME = 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe';
const FILE = process.argv[2];

let pass = 0, fail = 0, warn = 0;
function ok(n, c, extra) { if (c) { pass++; console.log('OK    ' + n + (extra ? '   ' + extra : '')); } else { fail++; console.log('**FAIL**  ' + n + (extra ? '   ' + extra : '')); } }
function wn(n, c, extra) { if (!c) { warn++; console.log('warn  ' + n + (extra ? '   ' + extra : '')); } }

(async () => {
  const b = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--allow-file-access-from-files', '--hide-scrollbars'] });
  const p = await b.newPage();
  await p.setViewport({ width: 900, height: 1400, deviceScaleFactor: 1 });
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto('file:///' + FILE.replace(/\\/g, '/'), { waitUntil: 'load', timeout: 120000 });
  await new Promise(r => setTimeout(r, 1800));

  const r = await p.evaluate(() => {
    const SUP = /[\u00B2\u00B3\u00B9\u2070-\u207F\u2080-\u209F\u02B0-\u02FF]/;
    const badRad = [], badSup = [], badDash = [], badMinus = [], badPunc = [];
    let textNodes = 0;
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) {
      const n = w.currentNode, pe = n.parentElement;
      if (!pe || /^(SCRIPT|STYLE)$/.test(pe.tagName)) continue;
      const t = n.nodeValue || '';
      if (!t.trim()) continue;
      textNodes++;
      /* ① 裸根号：√ 后面没有紧邻的 .rad 元素 */
      for (let i = 0; i < t.length; i++) {
        if (t[i] !== '\u221A') continue;
        const nx = n.nextSibling;
        const isRad = nx && nx.nodeType === 1 && nx.classList && nx.classList.contains('rad');
        const sameNodeOk = /^\u221A<span class="rad">/.test('');   /* 静态写法由静态检查覆盖 */
        if (!isRad) badRad.push(t.slice(Math.max(0, i - 14), i + 10));
      }
      /* ② Unicode 上下标：一律改用 <sup>/<sub> */
      const m = t.match(SUP);
      if (m) badSup.push(t.slice(Math.max(0, m.index - 16), m.index + 10));
      /* ③ 数值区间应统一用 en dash */
      const d = t.match(/\d\s*\u2014\s*\d|\u524d\d+\u2014\u7ea6?\u524d?\d+|\d\u2014\u7ea6?\d/);
      if (d) badDash.push(t.slice(Math.max(0, d.index - 14), d.index + 14));
      /* ④ 数字之间用 ASCII 连字符（应改成 −） */
      const h = t.match(/\d\s+-\s+\d/);
      if (h) badMinus.push(t.slice(Math.max(0, h.index - 14), h.index + 14));
      /* ⑤ 半角标点混进中文：ASCII , ; : ! ? ( ) . 紧贴汉字 */
      if (!pe.closest('.m')) {
        const CJK = /[\u4e00-\u9fff]/;
        for (let i = 0; i < t.length; i++) {
          const c = t[i];
          if (',;:!?()'.indexOf(c) < 0) continue;
          if (CJK.test(t[i - 1] || '') || CJK.test(t[i + 1] || ''))
            badPunc.push(t.slice(Math.max(0, i - 12), i + 12));
        }
      }
    }
    return { badRad, badSup, badDash, badMinus, badPunc, textNodes };
  });

  console.log('扫描可见文字节点 ' + r.textNodes + ' 个\n');
  ok('渲染后没有裸的「√」（横线都补上了）', r.badRad.length === 0, r.badRad.slice(0, 6).join(' | '));
  ok('可见文字里没有 Unicode 上下标（一律用 <sup>/<sub>）', r.badSup.length === 0, r.badSup.slice(0, 6).join(' | '));
  ok('数值区间统一用 en dash（–）', r.badDash.length === 0, r.badDash.slice(0, 6).join(' | '));
  wn('数字之间没有 ASCII 连字符冒充减号', r.badMinus.length === 0, r.badMinus.slice(0, 4).join(' | '));
  ok('半角标点没有混进中文（, ; : ! ? ( ) ）', r.badPunc.length === 0, (r.badPunc.length ? r.badPunc.length + ' 处：' : '') + r.badPunc.slice(0, 6).join(' | '));
  ok('页面无脚本报错', errs.length === 0, errs.slice(0, 3).join(' | '));

  console.log('\n===== ' + pass + ' 通过 / ' + fail + ' 失败 / ' + warn + ' 警告 =====');
  await b.close();
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('CRASH', e); process.exit(2); });
