'use strict';
/* 单册渲染验收 + 导出 A4 PDF */
const puppeteer = require('puppeteer-core');
const path = require('path'), fs = require('fs');

const CHROME = 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe';
// 用法：node volume_pdf.js [书稿目录]
const BOOK = (process.argv[2] || 'C:/Users/zyx32/WorkBuddy/2026-09-14-09-35-29').replace(/\\/g, '/');
const HTML = path.join(BOOK, '很久以后_全一卷.html');
const PDF = path.join(BOOK, '很久以后（全一卷）.pdf');

let pass = 0, fail = 0; const fails = [];
function ok(n, c, i) { if (c) pass++; else { fail++; fails.push(n + '  [' + i + ']'); console.log('FAIL  ' + n + '  ' + i); } }

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--allow-file-access-from-files']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 900, height: 1200, deviceScaleFactor: 2 });
  const errs = [];
  page.on('pageerror', e => errs.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });

  await page.goto('file:///' + HTML.replace(/\\/g, '/'), { waitUntil: 'load', timeout: 120000 });

  /* 等全部画布画完（逐块轮询，各章计算量差别很大） */
  let ready = false;
  for (let t = 0; t < 60; t++) {
    await new Promise(r => setTimeout(r, 1000));
    const st = await page.evaluate(() => {
      let blank = 0;
      document.querySelectorAll('canvas').forEach(cv => {
        const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
        let ink = 0;
        for (let i = 0; i < d.length; i += 4 * 37) {
          if (d[i + 3] && (d[i] < 245 || d[i + 1] < 245 || d[i + 2] < 245)) ink++;
        }
        if (ink < 20) blank++;
      });
      return { blank, total: document.querySelectorAll('canvas').length };
    });
    if (st.blank === 0) { ready = true; console.log('  全部 ' + st.total + ' 块画布已绘制（等待 ' + (t + 1) + 's）'); break; }
    if (t === 59) console.log('  超时：仍有 ' + st.blank + '/' + st.total + ' 块空白');
  }
  ok('全部画布绘制完成', ready);

  ok('单册加载无 JS 报错', errs.length === 0, errs.join(' | ').slice(0, 300));

  const info = await page.evaluate(() => ({
    chaps: document.querySelectorAll('section.chap').length,
    canvases: document.querySelectorAll('canvas').length,
    figures: document.querySelectorAll('figure.fig').length,
    notes: document.querySelectorAll('p.note').length,
    toc: document.querySelectorAll('ul.toc a').length,
    tables: document.querySelectorAll('table').length,
    h1: [...document.querySelectorAll('h1')].map(h => h.textContent.trim()),
    sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth
  }));
  console.log('  ' + JSON.stringify({ chaps: info.chaps, canvases: info.canvases, figures: info.figures, notes: info.notes, toc: info.toc, tables: info.tables }));
  console.log('  章标题: ' + JSON.stringify(info.h1));
  ok('章标题齐全（封面 1 + 八章 8 = 9 个 h1）', info.h1.length === 9, info.h1.join(' / '));
  ok('画布 20 块', info.canvases === 20, String(info.canvases));
  ok('图 22 张', info.figures === 22, String(info.figures));
  ok('目录 126 条链接', info.toc === 126, String(info.toc));
  ok('无横向溢出', info.sw <= info.cw + 1, info.sw + ' vs ' + info.cw);

  /* 抽查一个跨章交互仍然工作（第五讲的纠错演示） */
  const d1 = await page.evaluate(() => {
    const el = document.getElementById('nerr');
    el.value = '4'; el.dispatchEvent(new Event('input', { bubbles: true }));
    return document.getElementById('r51e').textContent;
  });
  ok('合册后第五章交互仍正常（4 个错 → 恢复成功）', d1 === '一致（恢复成功）', d1);
  const d2 = await page.evaluate(() => {
    const el = document.getElementById('sqM');
    el.value = '101'; el.dispatchEvent(new Event('input', { bubbles: true }));
    return document.getElementById('rsqPct').textContent;
  });
  ok('合册后第七章交互仍正常（101 项 → 过冲 8.95%）', String(d2).indexOf('8.9') === 0, String(d2));

  /* 打印媒体下的分页 */
  await page.emulateMediaType('print');
  const pr = await page.evaluate(() => {
    const g = (s, p) => getComputedStyle(document.querySelector(s))[p];
    return { cover: g('.cover', 'breakAfter'), chap1: document.querySelectorAll('section.chap')[0] ? g('section.chap', 'breakBefore') : null,
             chOpen: g('.ch-open', 'breakAfter'), notes: g('.notes', 'breakBefore'), appx: g('.appendix', 'breakBefore'),
             fig: g('figure.fig', 'breakInside'), body: getComputedStyle(document.body).fontSize };
  });
  console.log('  打印样式: ' + JSON.stringify(pr));
  ok('打印：章首页另起页', pr.chOpen === 'page', pr.chOpen);
  ok('打印：附录另起页', pr.appx === 'page', pr.appx);
  ok('打印：章末注顺排、不强制另起页（避免孤行页）', pr.notes === 'auto', pr.notes);
  ok('打印：图不跨页断开', pr.fig === 'avoid', pr.fig);
  ok('打印：字号 10.5pt', pr.body === '14px', pr.body);
  await page.emulateMediaType(null);

  /* ---------- 导出 A4 PDF ---------- */
  console.log('\n  正在导出 A4 PDF …');
  await page.pdf({
    path: PDF,
    preferCSSPageSize: true,
    printBackground: true,
    displayHeaderFooter: true,
    headerTemplate: '<div></div>',
    footerTemplate: '<div style="width:100%;font-size:8pt;color:#868e95;' +
      'font-family:Microsoft YaHei,sans-serif;text-align:center;padding:0 0 4mm;">' +
      '<span class="pageNumber"></span> / <span class="totalPages"></span></div>',
    outline: true,
    tagged: true,
    margin: { top: '0mm', bottom: '0mm', left: '0mm', right: '0mm' }
  });
  const sz = fs.statSync(PDF).size;
  console.log('  PDF: ' + path.basename(PDF) + '  ' + (sz / 1024 / 1024).toFixed(2) + ' MB');
  ok('PDF 已生成且非空', sz > 500 * 1024, (sz / 1024).toFixed(0) + ' KB');

  await browser.close();
  console.log('\n================  ' + pass + ' 通过 / ' + fail + ' 失败  ================');
  if (fails.length) console.log(fails.map(f => '  - ' + f).join('\n'));
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('CRASH', e); process.exit(2); });
