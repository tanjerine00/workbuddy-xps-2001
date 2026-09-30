'use strict';
/* 第一章 DOM 级验证：画布是否真的画上了内容 + 滑块是否真的会重绘 */
const puppeteer = require('puppeteer-core');
const path = require('path');

const CHROME = 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe';
const HTML = 'C:/Users/zyx32/WorkBuddy/2026-09-14-09-35-29/直觉的边界_第一章_连续的世界真的像我们想象的那样吗.html';

let pass = 0, fail = 0;
function ok(n, c, extra) { if (c) { pass++; console.log('OK    ' + n + (extra ? '   ' + extra : '')); } else { fail++; console.log('**FAIL**  ' + n + (extra ? '   ' + extra : '')); } }

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--allow-file-access-from-files']
  });
  const page = await browser.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push('PAGEERROR ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE ' + m.text()); });
  await page.setViewport({ width: 900, height: 1200, deviceScaleFactor: 2 });
  await page.goto('file:///' + HTML.replace(/\\/g, '/'), { waitUntil: 'load', timeout: 120000 });
  await new Promise(r => setTimeout(r, 2500));

  ok('页面无 JS 错误', errs.length === 0, errs.join(' | '));

  /* 画布着色比例 */
  const ink = await page.evaluate(() => {
    const out = {};
    ['c11', 'c12', 'c13', 'c14'].forEach(id => {
      const cv = document.getElementById(id);
      if (!cv) { out[id] = { err: 'no canvas' }; return; }
      const ctx = cv.getContext('2d');
      const d = ctx.getImageData(0, 0, cv.width, cv.height).data;
      let n = 0, tot = 0;
      for (let i = 0; i < d.length; i += 4) {
        tot++;
        if (d[i + 3] > 8 && !(d[i] > 248 && d[i + 1] > 248 && d[i + 2] > 248)) n++;
      }
      out[id] = { w: cv.width, h: cv.height, ink: n, tot: tot, pct: +(100 * n / tot).toFixed(2) };
    });
    return out;
  });
  for (const k of ['c11', 'c12', 'c13', 'c14']) {
    const v = ink[k];
    ok(k + ' 已绘制（有色像素占比 > 1%）', v.pct > 1, v.w + '×' + v.h + '  ' + v.pct + '%');
  }

  /* 读数块都有内容 */
  const reads = await page.evaluate(() => {
    const o = {};
    ['r11', 'r12', 'r13', 'r14'].forEach(id => {
      const el = document.getElementById(id);
      o[id] = el ? el.textContent.replace(/\s+/g, '').length : -1;
    });
    return o;
  });
  for (const k of ['r11', 'r12', 'r13', 'r14']) {
    ok(k + ' 读数已填充（> 40 字）', reads[k] > 40, reads[k] + ' 字');
  }

  /* 滑块真的会重绘 */
  const before = await page.evaluate(() => {
    const cv = document.getElementById('c11').getContext('2d');
    return cv.getImageData(0, 0, document.getElementById('c11').width, document.getElementById('c11').height).data.join('').length;
  });
  const sig = async () => page.evaluate(() => {
    const ids = ['c11', 'c12', 'c13', 'c14'];
    const tmp = document.createElement('canvas');
    tmp.width = 80; tmp.height = 40;
    const tc = tmp.getContext('2d');
    return ids.map(id => {
      const cv = document.getElementById(id);
      tc.clearRect(0, 0, 80, 40);
      tc.drawImage(cv, 0, 0, 80, 40);
      const d = tc.getImageData(0, 0, 80, 40).data;
      let h = 2166136261;
      for (let i = 0; i < d.length; i += 4) h = ((h ^ d[i]) * 16777619) >>> 0;
      return h;
    }).join(',');
  });
  const s0 = await sig();
  for (const [id, val] of [['s11', 20], ['s12', 18], ['s12b', 80], ['s13', 12], ['s14', 22]]) {
    await page.evaluate((id, v) => {
      const el = document.getElementById(id);
      el.value = String(v);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }, id, val);
    await new Promise(r => setTimeout(r, 120));
  }
  const s1 = await sig();
  ok('五个滑块都能触发重绘（画面指纹改变）', s0 !== s1);

  /* 回归测试：setup() 反复调用不得让画布物理尺寸增长 */
  const dims = await page.evaluate(() => {
    const o = {};
    ['c11', 'c12', 'c13', 'c14'].forEach(id => {
      const cv = document.getElementById(id);
      o[id] = { w: cv.width, h: cv.height, lw: +(cv.dataset.logW || 0), lh: +(cv.dataset.logH || 0) };
    });
    return o;
  });
  const dpr = Math.min(2, 2);
  let grow = [];
  for (const id of ['c11', 'c12', 'c13', 'c14']) {
    const v = dims[id];
    if (v.w !== v.lw * dpr || v.h !== v.lh * dpr) grow.push(id + ' ' + v.w + '×' + v.h + ' ≠ ' + (v.lw * dpr) + '×' + (v.lh * dpr));
  }
  ok('多次重绘后画布尺寸不膨胀（setup 幂等）', grow.length === 0, grow.join(' | '));
  // 极值不报错
  await page.evaluate(() => {
    ['s11', 's12', 's12b', 's13', 's14'].forEach(id => {
      const el = document.getElementById(id);
      el.value = el.min; el.dispatchEvent(new Event('input', { bubbles: true }));
    });
  });
  await new Promise(r => setTimeout(r, 150));
  await page.evaluate(() => {
    ['s11', 's12', 's12b', 's13', 's14'].forEach(id => {
      const el = document.getElementById(id);
      el.value = el.max; el.dispatchEvent(new Event('input', { bubbles: true }));
    });
  });
  await new Promise(r => setTimeout(r, 150));
  ok('滑块推到 min / max 极值不报错', errs.length === 0, errs.join(' | '));

  console.log('\n===== ' + pass + ' 通过 / ' + fail + ' 失败 =====');
  await browser.close();
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('CRASH', e); process.exit(2); });
