// render_pdf.js — 用本机 Chrome 把 cover.html / body.html 渲染成 PDF
//
// 用法（在 PowerShell 里）：
//   $env:NODE_PATH="C:\Users\zyx32\.workbuddy\binaries\node\workspace\node_modules"
//   node render_pdf.js
//
// 不下 Playwright/Chromium；puppeteer-core 走 executablePath 复用本机 Chrome。
// 关键参数：A4，displayHeaderFooter:false（避免 Chrome 把封面页毁掉）。

const path = require('path');
const puppeteer = require('C:\\Users\\zyx32\\.workbuddy\\binaries\\node\\workspace\\node_modules\\puppeteer-core');

const ROOT = __dirname;
const CHROME = 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe';

const jobs = [
  {
    html: path.join(ROOT, 'cover.html'),
    pdf: path.join(ROOT, 'cover.pdf'),
    pageCSS: 'cover',  // 标志，build_report.py 已经在 @page 里把 margin 设成 0
  },
  {
    html: path.join(ROOT, 'body.html'),
    pdf: path.join(ROOT, 'body.pdf'),
    pageCSS: 'body',
  },
];

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });
  for (const job of jobs) {
    const page = await browser.newPage();
    const url = 'file:///' + job.html.replace(/\\/g, '/');
    console.log('rendering', url);
    await page.goto(url, { waitUntil: 'networkidle0', timeout: 60000 });
    // 给中文字体一点排版时间
    await new Promise(r => setTimeout(r, 400));
    await page.pdf({
      path: job.pdf,
      format: 'A4',
      printBackground: true,
      preferCSSPageSize: true,  // 关键：让 @page{margin:...} 生效
      displayHeaderFooter: false,
      outline: true,            // 让 Chrome 根据 h1-h6 生成书签
      tagged: false,
      // 不要传 margin：会让 Chrome 覆盖 CSS @page 的 margin。
      // 真正控制正文边距靠 build_report.py 的 BODY_CSS 里的 @page{margin:16mm 15mm 18mm 15mm;}
    });
    await page.close();
    console.log('  wrote', job.pdf);
  }
  await browser.close();
})().catch(e => {
  console.error(e);
  process.exit(1);
});