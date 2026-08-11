/**
 * Browser walk-through of the AI upload path (Phase 2).
 *
 *   cd backend && python scripts/fake_llm_server.py &      # or use real keys
 *   LLM_PROVIDER_1_MODEL=fake LLM_PROVIDER_1_API_KEY=fake \
 *     LLM_PROVIDER_1_BASE_URL=http://127.0.0.1:9001/v1 \
 *     uvicorn app.main:app --port 8000 &
 *   cd frontend && npm run dev &
 *   node e2e/upload.mjs path/to/resume.pdf
 *
 * Set CHROMIUM_PATH to reuse a local browser, SHOT_DIR to move the screenshots.
 */
import { mkdirSync } from 'node:fs';
import { chromium } from 'playwright';

const SHOT_DIR = process.env.SHOT_DIR ?? './e2e-screenshots';
const BASE_URL = process.env.BASE_URL ?? 'http://localhost:5173';
const RESUME = process.argv[2] ?? '/tmp/test-resume.pdf';
mkdirSync(SHOT_DIR, { recursive: true });

const shot = async (page, name) =>
  page.screenshot({ path: `${SHOT_DIR}/${name}.png`, fullPage: true });

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
page.on('pageerror', (e) => console.log('PAGE ERROR:', e.message));
page.on('console', (m) => m.type() === 'error' && console.log('CONSOLE ERROR:', m.text()));

await page.goto(BASE_URL);
await page.evaluate(() => localStorage.clear());
await page.reload();

await page.getByRole('button', { name: 'Build my resume' }).click();
await page.waitForTimeout(2000);
await page.getByRole('button', { name: 'Use this format' }).click();
await shot(page, 'u1-choose-path');

await page.getByRole('heading', { name: 'I already have a resume' }).click();
await shot(page, 'u2-upload');

await page.locator('input[type=file]').setInputFiles(RESUME);
await page.waitForSelector('text=Contact', { timeout: 60000 });
await shot(page, 'u3-prefilled-form');

const name = await page.getByLabel('Full name').inputValue();
const email = await page.getByLabel('Email').inputValue();
const badges = await page.locator('.ai-badge').count();
console.log('extracted name:', JSON.stringify(name));
console.log('extracted email:', JSON.stringify(email));
console.log('AI-filled badges on this step:', badges);

// Editing a field makes it the user's, so its badge must disappear.
await page.getByLabel('Full name').fill('Sam Doe Edited');
await page.waitForTimeout(200);
const afterEdit = await page.locator('.ai-badge').count();
console.log('badges after editing one field:', afterEdit);
if (afterEdit !== badges - 1) throw new Error('editing a field should clear exactly its badge');

// Straight through to a compiled PDF from the extracted data.
for (const step of ['Summary', 'Experience', 'Education', 'Skills', 'Projects', 'Publications']) {
  await page.getByRole('button', { name: step, exact: true }).click();
  await page.waitForTimeout(120);
}
await shot(page, 'u4-experience-badges');
await page.getByRole('button', { name: /Review and generate/ }).click();
await page.getByRole('button', { name: 'Generate PDF' }).click();
await page.waitForSelector('text=Your resume is ready', { timeout: 60000 });
await shot(page, 'u5-done');

console.log('download:', await page.getByRole('link', { name: 'Download PDF' }).getAttribute('href'));
await browser.close();
console.log('UPLOAD E2E OK');
