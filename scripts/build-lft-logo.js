#!/usr/bin/env node
// Рендерит логотип LFT Foro Teatro из assets/lft/lft-logo-animation.html:
//   lft-logo.svg, lft-logo-512.png, lft-logo-1024.png  — статичная аватарка
//   lft-animation.mp4 (800×800, H.264, 9.6 с)          — видео-аватарка Telegram
//   lft-animation.gif (480×480)                          — превью
// Требует: playwright (с Chromium) и ffmpeg в PATH.
//   node scripts/build-lft-logo.js
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const DIR = path.join(__dirname, '..', 'assets', 'lft');
const PAGE = 'file://' + path.join(DIR, 'lft-logo-animation.html');
const FPS = 30;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1024, height: 1024 } });
  await page.goto(PAGE + '?static');
  await page.evaluate(() => document.fonts.ready);

  // статичный логотип
  const svg = await page.evaluate(() => {
    const s = document.getElementById('logo').cloneNode(true);
    s.setAttribute('width', '1000');
    s.setAttribute('height', '1000');
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + s.outerHTML + '\n';
  });
  fs.writeFileSync(path.join(DIR, 'lft-logo.svg'), svg);
  await page.locator('#logo').screenshot({ path: path.join(DIR, 'lft-logo-1024.png') });
  await page.setViewportSize({ width: 512, height: 512 });
  await page.locator('#logo').screenshot({ path: path.join(DIR, 'lft-logo-512.png') });

  // кадры анимации
  await page.setViewportSize({ width: 800, height: 800 });
  const total = await page.evaluate(() => window.LFT.TOTAL);
  const frames = Math.round(total * FPS);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'lft-'));
  for (let i = 0; i < frames; i++) {
    await page.evaluate((t) => window.LFT.renderAt(t), i / FPS);
    await page.locator('#logo').screenshot({ path: path.join(tmp, `f${String(i).padStart(4, '0')}.png`) });
  }
  await browser.close();

  const input = ['-framerate', String(FPS), '-i', path.join(tmp, 'f%04d.png')];
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', ...input,
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'slow',
    '-movflags', '+faststart', '-an', path.join(DIR, 'lft-animation.mp4')]);
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', ...input,
    '-vf', 'fps=20,scale=480:480:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4',
    '-loop', '0', path.join(DIR, 'lft-animation.gif')]);
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(`done: ${frames} frames, ${total}s`);
})();
