// Renders the pages written by build.py: PNG screenshots of one element, or PDFs at an exact mm page size.
// Usage: node build/render.js jobs.json
const fs = require('fs');
const { chromium } = require('playwright');

(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await chromium.launch();
  for (const job of jobs) {
    const page = await browser.newPage({ deviceScaleFactor: job.scale || 2, viewport: { width: 1800, height: 1400 } });
    await page.goto('file://' + job.html, { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    if (job.type === 'png') {
      await page.locator(job.selector).screenshot({ path: job.out });
    } else {
      await page.pdf({ path: job.out, width: job.width_mm + 'mm', height: job.height_mm + 'mm', printBackground: true, pageRanges: '1' });
    }
    await page.close();
  }
  await browser.close();
})();
