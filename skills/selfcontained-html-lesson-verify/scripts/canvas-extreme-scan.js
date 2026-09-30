'use strict';
/* 极端参数下的版面检查 */
const puppeteer = require('puppeteer-core');
const path = require('path'), fs = require('fs');

const CHROME = 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe';
const BOOK = 'C:/Users/zyx32/WorkBuddy/2026-09-14-09-35-29';
const OUT = path.join(BOOK, '预览图', '极端参数');
const HTML = path.join(BOOK, '直觉的边界_第一章_连续的世界真的像我们想象的那样吗.html');

const STATES = [
  { tag: '图1-1_n1',   set: { s11: 1 } },
  { tag: '图1-1_n26',  set: { s11: 26 } },
  { tag: '图1-2_n1_r05',  set: { s12: 1,  s12b: 5 } },
  { tag: '图1-2_n30_r95', set: { s12: 30, s12b: 95 } },
  { tag: '图1-3_n1',   set: { s13: 1 } },
  { tag: '图1-3_n14',  set: { s13: 14 } },
  { tag: '图1-4_dt最大', set: { s14: 0 } },
  { tag: '图1-4_dt最小', set: { s14: 26 } }
];

(async () => {
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--allow-file-access-from-files']
  });
  const page = await browser.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(e.message));
  await page.setViewport({ width: 900, height: 1200, deviceScaleFactor: 2 });
  await page.goto('file:///' + HTML.replace(/\\/g, '/'), { waitUntil: 'load', timeout: 120000 });
  await new Promise(r => setTimeout(r, 2000));

  const figMap = {};
  const figs = await page.$$('figure.fig');
  for (let i = 0; i < figs.length; i++) {
    const no = await figs[i].evaluate((el, idx) => {
      const s = el.querySelector('.fno');
      return s ? s.textContent.replace(/\s+/g, '') : 'fig' + idx;
    }, i);
    figMap[no] = figs[i];
  }

  for (const st of STATES) {
    await page.evaluate((set) => {
      Object.keys(set).forEach(id => {
        const el = document.getElementById(id);
        el.value = String(set[id]);
        el.dispatchEvent(new Event('input', { bubbles: true }));
      });
    }, st.set);
    await new Promise(r => setTimeout(r, 180));
    const key = st.tag.split('_')[0];
    const h = figMap[key];
    if (!h) { console.log('跳过 ' + st.tag); continue; }
    await h.screenshot({ path: path.join(OUT, st.tag + '.png') });
    console.log('写出 ' + st.tag + '.png');
  }
  console.log(errs.length ? '页面错误：' + errs.join(' | ') : '页面无 JS 错误');
  await browser.close();
})().catch(e => { console.error('CRASH', e); process.exit(2); });
