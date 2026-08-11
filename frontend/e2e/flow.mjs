/**
 * End-to-end walk-through of the whole Phase 1 flow, against real servers.
 *
 *   cd backend && uvicorn app.main:app --port 8000
 *   cd frontend && npm run dev
 *   node e2e/flow.mjs
 *
 * Screenshots land in SHOT_DIR. Set CHROMIUM_PATH to reuse a local browser.
 * The form is filled with LaTeX-hostile text on
 * purpose, so a regression in escaping fails here as well as in pytest.
 */
import { mkdirSync } from 'node:fs';
import { chromium } from 'playwright';

const SHOT_DIR = process.env.SHOT_DIR ?? './e2e-screenshots';
const BASE_URL = process.env.BASE_URL ?? 'http://localhost:5173';
mkdirSync(SHOT_DIR, { recursive: true });

const shot = async (page, name) =>
  page.screenshot({ path: `${SHOT_DIR}/${name}.png`, fullPage: true });

// CHROMIUM_PATH lets you point at an already-installed browser instead of
// Playwright's own download.
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
page.on('console', (m) => m.type() === 'error' && console.log('CONSOLE ERROR:', m.text()));
page.on('pageerror', (e) => console.log('PAGE ERROR:', e.message));

await page.goto(BASE_URL);
await shot(page, '01-landing');

await page.getByRole('button', { name: 'Build my resume' }).click();
await page.waitForTimeout(2500);
await shot(page, '02-templates');

await page.getByRole('button', { name: 'Use this format' }).click();
await shot(page, '03-path');

await page.getByRole('heading', { name: 'Fill it in myself' }).click();
await page.waitForTimeout(300);

// Step 1 — contact, including LaTeX-hostile characters.
await page.getByLabel('Full name').fill('Alex Rivera & Co. 100%');
await page.getByLabel('Headline').fill('Backend Engineer — C# & Python');
await page.getByLabel('Email').fill('alex@example.com');
await page.getByLabel('Phone').fill('+1 (555) 014-2288');
await page.getByLabel('Location').fill('Austin, TX');
await page.getByRole('button', { name: '+ Add a link' }).click();
await page.getByLabel('Label').fill('GitHub');
await page.getByLabel('Address').fill('github.com/alexrivera');
await shot(page, '04-contact');

await page.getByRole('button', { name: /Next: Summary/ }).click();
await page.getByLabel('Professional summary').fill('Backend engineer with 6 years of experience. Cut costs by 30% & shipped $1M of value.');
await page.getByRole('button', { name: /Next: Experience/ }).click();

// Step 3 — experience with two entries.
await page.getByLabel('Job title').fill('Senior Software Engineer');
await page.getByLabel('Company').fill('Northwind Data');
await page.getByLabel('Location').fill('Austin, TX');
await page.getByLabel('Start').fill('Mar 2022');
await page.getByLabel('End').fill('Present');
await page.getByLabel('What you did — point 1').fill('Raised throughput from 4k to 26k events/second (a 550% gain).');
await page.getByRole('button', { name: '+ Add a point' }).click();
await page.getByLabel('What you did — point 2').fill('Cut p99 latency 63% using a materialised read model.');
await page.getByRole('button', { name: '+ Add another job' }).click();
await page.getByLabel('Job title').nth(1).fill('Software Engineer');
await page.getByLabel('Company').nth(1).fill('Cobalt Systems');
await page.getByLabel('Start').nth(1).fill('Jul 2019');
await page.getByLabel('End').nth(1).fill('Feb 2022');
await shot(page, '05-experience');

// Blank out a required field to prove inline validation blocks the step.
await page.getByLabel('Company').nth(1).fill('');
await page.getByRole('button', { name: /Next: Education/ }).click();
await shot(page, '06-validation-blocked');
await page.getByLabel('Company').nth(1).fill('Cobalt Systems');
await page.getByRole('button', { name: /Next: Education/ }).click();

await page.getByLabel('Degree or qualification').fill('B.S. Computer Science');
await page.getByLabel('Institution').fill('University of Texas at Austin');
await page.getByLabel('Grade').fill('GPA 3.8/4.0');
await page.getByLabel('Start').fill('2015');
await page.getByLabel('End').fill('2019');
await page.getByRole('button', { name: /Next: Skills/ }).click();

await page.getByLabel('Category').fill('Languages');
await page.getByLabel('Skills').fill('Python, Go, C#, TypeScript');
await shot(page, '07-skills');
await page.getByRole('button', { name: /Next: Projects/ }).click();
await page.getByRole('button', { name: '+ Add a project' }).click();
await page.getByLabel('Project name').fill('queuelite');
await page.getByLabel('Link').fill('github.com/alexrivera/queuelite');
await page.getByLabel('Description').fill('A dependency-free job queue for Postgres.');
await page.getByRole('button', { name: /Next: Publications/ }).click();
await shot(page, '08-publications');

await page.getByRole('button', { name: /Review and generate/ }).click();
await page.waitForTimeout(300);
await shot(page, '09-review');

await page.getByRole('button', { name: 'Generate PDF' }).click();
await page.waitForSelector('text=Your resume is ready', { timeout: 60000 });
await shot(page, '10-done');

const href = await page.getByRole('link', { name: 'Download PDF' }).getAttribute('href');
console.log('download:', href);

// Reload mid-flow to prove autosave survives a refresh.
await page.reload();
await page.waitForTimeout(1000);
await shot(page, '12-after-reload');
await page.getByRole('button', { name: 'Continue where I left off' }).click();
await page.waitForTimeout(500);
const name = await page.getByLabel('Full name').inputValue();
console.log('after reload, name restored as:', JSON.stringify(name));

// Mobile layout.
// A new page means a new context, so carry the draft across by hand.
const draft = await page.evaluate(() => localStorage.getItem('resume-maker:draft:v1'));
const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
await mobile.goto(BASE_URL);
await mobile.evaluate((d) => localStorage.setItem('resume-maker:draft:v1', d), draft);
await mobile.reload();
await mobile.getByRole('button', { name: 'Continue where I left off' }).click();
await mobile.waitForTimeout(400);
await mobile.screenshot({ path: `${SHOT_DIR}/11-mobile.png` });

await browser.close();
console.log('E2E OK');
