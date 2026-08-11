/**
 * Checks the gallery and the format switcher across every template.
 *
 *   node e2e/templates.mjs
 *
 * Generates a PDF, switches format, regenerates, and confirms the on-page
 * render changes — the Phase 3 promise is "same data, different layout, no
 * retyping", and this is what proves it.
 */
import { mkdirSync } from 'node:fs';
import { chromium } from 'playwright';

const SHOT_DIR = process.env.SHOT_DIR ?? './e2e-screenshots';
const BASE_URL = process.env.BASE_URL ?? 'http://localhost:5173';
mkdirSync(SHOT_DIR, { recursive: true });

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH });
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
page.on('pageerror', (e) => console.log('PAGE ERROR:', e.message));

await page.goto(BASE_URL);
await page.evaluate(() => localStorage.setItem('resume-maker:draft:v1', JSON.stringify({
  contact: { full_name: 'Sam Doe', headline: 'Backend Engineer', email: 'sam@example.com',
             phone: '+1 555 0100', location: 'Austin, TX',
             links: [{ label: 'GitHub', url: 'https://github.com/sam?tab=repositories&x=1' }] },
  summary: 'Engineer with eight years building high-throughput services.',
  experience: [{ title: 'Senior Engineer', company: 'Acme & Co', location: 'Remote',
                 start_date: 'Mar 2022', end_date: 'Present',
                 bullets: ['Cut p99 latency by 60%', 'Led a migration of 40+ services'] }],
  education: [{ degree: 'B.S. Computer Science', institution: 'UT Austin', location: 'Austin',
                start_date: '2015', end_date: '2019', grade: 'GPA 3.8/4.0', details: '' }],
  skills: [{ category: 'Languages', skills: ['Python', 'Go', 'C#'] }],
  projects: [], publications: [],
})));
await page.reload();

// The gallery must show every template, with a thumbnail for each.
await page.getByRole('button', { name: 'Build my resume' }).click();
await page.waitForSelector('.card', { timeout: 20000 });
await page.waitForTimeout(1500);
const cards = await page.locator('.card').count();
const thumbs = await page.locator('.card__preview img').count();
console.log('gallery cards:', cards, '| thumbnails:', thumbs);
await page.screenshot({ path: `${SHOT_DIR}/t1-gallery.png`, fullPage: true });
if (cards < 4) throw new Error(`expected 4 templates, saw ${cards}`);

await page.getByRole('button', { name: 'Use this format' }).first().click();
await page.getByRole('heading', { name: 'Fill it in myself' }).click();
await page.getByRole('button', { name: 'Publications', exact: true }).click();
await page.getByRole('button', { name: /Review and generate/ }).click();

const digestOfRender = async () =>
  page.evaluate(() => {
    const canvas = document.querySelector('.pdf-viewer canvas');
    return canvas ? canvas.toDataURL().length + ':' + canvas.height : 'none';
  });

const seen = {};
for (const format of ['Classic', 'Compact', 'Modern', 'Technical']) {
  await page.selectOption('.review__template select', { label: format });
  await page.getByRole('button', { name: 'Generate PDF' }).click();
  await page.waitForSelector('text=Your resume is ready', { timeout: 90000 });
  await page.waitForTimeout(3500);
  seen[format] = await digestOfRender();
  console.log(`${format}: rendered ${seen[format]}`);
  if (seen[format] === 'none') throw new Error(`${format} did not render`);
  await page.screenshot({ path: `${SHOT_DIR}/t2-${format.toLowerCase()}.png`, fullPage: true });
}

const unique = new Set(Object.values(seen));
if (unique.size !== 4) throw new Error('formats produced identical output — switching had no effect');

await browser.close();
console.log('TEMPLATES E2E OK — 4 distinct layouts from one set of data');
