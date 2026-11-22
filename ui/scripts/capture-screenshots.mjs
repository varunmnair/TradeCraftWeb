// Captures screenshots of every TradeCraftX UI page and builds a PDF gallery.
//
// Usage (from ui/):
//   npm install --no-save --package-lock=false playwright
//   node scripts/capture-screenshots.mjs --pass empty
//   node scripts/capture-screenshots.mjs --pass live --connection-id 1
//
// Requires a running server (default http://localhost:8000) and the system Chrome.

import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright';

function parseArgs(argv) {
  const result = {};
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith('--')) continue;
    const eq = token.indexOf('=');
    if (eq !== -1) {
      result[token.slice(2, eq)] = token.slice(eq + 1);
    } else {
      result[token.slice(2)] = argv[i + 1]?.startsWith('--') ? true : argv[++i];
    }
  }
  return result;
}

const args = parseArgs(process.argv.slice(2));
const baseUrl = (args['base-url'] || 'http://localhost:8000').replace(/\/$/, '');
const outRoot = path.resolve(args.out || '../screenshots');
const pass = args.pass || 'both';
const email = args.email || 'admin@tradecraft.com';
const password = args.password || 'password123';
const connectionId = args['connection-id'] ? Number(args['connection-id']) : null;
const settleMs = Number(args.settle || 1200);

const PAGES = [
  { route: '/dashboard', name: 'dashboard', title: 'Dashboard' },
  { route: '/broker-connections', name: 'broker-connections', title: 'Broker Connections' },
  { route: '/sessions', name: 'sessions', title: 'Sessions' },
  { route: '/holdings', name: 'holdings', title: 'Holdings' },
  { route: '/entries', name: 'entries', title: 'Entry Plans / Buy Entries' },
  { route: '/entry-strategies', name: 'entry-strategies', title: 'Entry Strategies' },
  { route: '/entry-candidates', name: 'entry-candidates', title: 'Entry Candidates' },
  { route: '/plan', name: 'plan', title: 'Plan' },
  { route: '/gtt', name: 'gtt', title: 'Buy Orders / GTT' },
  { route: '/jobs', name: 'jobs', title: 'Jobs' },
  { route: '/admin', name: 'admin', title: 'Administration' },
];

// In the built app, a few SPA paths collide with API router prefixes, so a hard
// navigation returns JSON. Reach those pages through the sidebar like a user.
const NAV_LABELS = {
  '/dashboard': 'Dashboard',
  '/broker-connections': 'Brokers',
  '/sessions': 'Sessions',
  '/holdings': 'Holdings',
  '/entries': 'Entry Plans',
  '/entry-strategies': 'Entry Strategies',
  '/entry-candidates': 'Entry Candidates',
  '/gtt': 'Buy Orders',
  '/jobs': 'Jobs',
  '/admin': 'Administration',
};

async function navigateTo(page, route) {
  if (route === '/plan') {
    // No sidebar item; use the Dashboard quick link to stay in the SPA.
    await navigateTo(page, '/dashboard');
    await page.getByText('Plan', { exact: true }).first().click();
    await page.waitForURL('**/plan', { timeout: 10000 });
    return;
  }
  const label = NAV_LABELS[route];
  if (!label) {
    await page.goto(`${baseUrl}${route}`);
    return;
  }
  await page.locator('nav').getByText(label, { exact: true }).first().click();
  await page.waitForURL(`**${route}`, { timeout: 10000 });
}

const PUBLIC_PAGES = [
  { route: '/login', name: 'login', title: 'Login' },
  { route: '/register', name: 'register', title: 'Register' },
];

const manifest = [];
const indexJsonPath = path.join(outRoot, 'index.json');

// Reuse earlier captures when adding a second pass or rebuilding the PDF.
if ((pass === 'live' || pass === 'pdf') && fs.existsSync(indexJsonPath)) {
  const prior = JSON.parse(fs.readFileSync(indexJsonPath, 'utf8'));
  manifest.push(...(pass === 'live' ? prior.filter((item) => item.group !== 'live') : prior));
}

async function settle(page) {
  try {
    await page.waitForLoadState('networkidle', { timeout: 8000 });
  } catch {
    // Job polling can keep the network busy; a fixed wait is enough.
  }
  await page.waitForTimeout(settleMs);
}

async function snap(page, group, index, name, title) {
  await settle(page);
  const dir = path.join(outRoot, group);
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `${String(index).padStart(2, '0')}-${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  const relative = path.relative(outRoot, file).replaceAll('\\', '/');
  const info = await page.evaluate(() => ({
    url: location.pathname,
    text: document.body.innerText.replace(/\s+/g, ' ').slice(0, 1200),
  }));
  manifest.push({ group, title, file: relative, ...info });
  console.log(`  captured ${relative} (${info.url})`);
}

async function login(page) {
  await page.goto(`${baseUrl}/login`);
  await settle(page);
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Login', exact: true }).click();
  await page.waitForURL('**/dashboard', { timeout: 20000 });
  await settle(page);
  console.log(`logged in as ${email}`);
}

async function startSession(page) {
  if (!connectionId) {
    console.log('  no --connection-id supplied; capturing live pass without a new session');
    return;
  }
  const token = await page.evaluate(() => sessionStorage.getItem('access_token'));
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const response = await page.request.post(`${baseUrl}/session/start`, {
    data: { broker_connection_id: connectionId },
    headers,
  });
  if (!response.ok()) {
    throw new Error(`session/start failed: ${response.status()} ${await response.text()}`);
  }
  const session = await response.json();
  await page.request.post(`${baseUrl}/session/active-connection`, {
    data: { broker_connection_id: connectionId },
    headers,
  });
  // The UI reads these keys on mount; without them pages show "no active session".
  await page.evaluate(
    ({ sessionId, connection }) => {
      localStorage.setItem('tradecraftx_session_id', sessionId);
      localStorage.setItem('tradecraftx_upstox_connection_id', String(connection));
    },
    { sessionId: session.session_id, connection: connectionId },
  );
  console.log(`  session started: ${session.session_id} (connection ${connectionId})`);
}

async function capturePublicPages(page, group) {
  for (const [i, item] of PUBLIC_PAGES.entries()) {
    await page.goto(`${baseUrl}${item.route}`);
    await snap(page, group, i + 1, item.name, item.title);
  }
}

async function captureAuthenticatedPages(page, group, startIndex = 1) {
  if (new URL(page.url()).pathname !== '/dashboard') {
    await navigateTo(page, '/dashboard');
  }
  for (const [i, item] of PAGES.entries()) {
    try {
      await navigateTo(page, item.route);
      await snap(page, group, startIndex + i, item.name, item.title);
    } catch (error) {
      console.warn(`  skipped ${item.route}: ${error.message}`);
    }
  }
}

async function captureOverlays(page, group, startIndex) {
  await page.goto(`${baseUrl}/dashboard`);
  await settle(page);
  try {
    await page.locator('[data-testid="HelpIcon"]').first().click();
    await page.locator('[role="dialog"]').first().waitFor({ timeout: 5000 });
    await snap(page, group, startIndex, 'help-panel', 'Help Panel');
    await page.keyboard.press('Escape');
    await page.locator('[role="dialog"]').first().waitFor({ state: 'hidden', timeout: 5000 });
  } catch (error) {
    console.warn(`  skipped Help overlay: ${error.message}`);
  }
  try {
    await page.locator('[data-testid="SmartToyIcon"]').last().click();
    await page.getByText('AI Analyst', { exact: true }).first().waitFor({ timeout: 5000 });
    await snap(page, group, startIndex + 1, 'ai-chat-panel', 'AI Chat Panel');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);
  } catch (error) {
    console.warn(`  skipped AI overlay: ${error.message}`);
  }
}

function escapeHtml(value) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}

function buildGalleryHtml() {
  const groups = [...new Set(manifest.map((item) => item.group))];
  const sections = groups
    .map((group) => {
      const label = group === 'empty' ? 'Logged in, no broker session' : 'Broker session active';
      const figures = manifest
        .filter((item) => item.group === group)
        .map(
          (item) => `      <figure>
        <img src="${escapeHtml(item.file)}" alt="${escapeHtml(item.title)}" />
        <figcaption>${escapeHtml(item.title)}</figcaption>
      </figure>`,
        )
        .join('\n');
      return `    <section>
      <h2>${escapeHtml(label)}</h2>
${figures}
    </section>`;
    })
    .join('\n');

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>TradeCraftX UI Screenshots</title>
<style>
  @page { size: A4; margin: 12mm; }
  body { font-family: Arial, Helvetica, sans-serif; color: #222; margin: 0; }
  .cover { text-align: center; page-break-after: always; break-after: page; padding-top: 60mm; }
  .cover h1 { font-size: 32px; margin-bottom: 8px; }
  .cover p { color: #666; font-size: 14px; }
  section { page-break-before: always; break-before: page; }
  h2 { font-size: 20px; margin: 0 0 10mm; }
  figure { margin: 0 0 10mm; break-inside: avoid; page-break-inside: avoid; }
  figure img {
    display: block; width: 100%; max-height: 225mm; object-fit: contain;
    border: 1px solid #ddd; box-shadow: 0 1px 4px rgba(0,0,0,.12);
  }
  figcaption { margin-top: 4px; font-size: 12px; color: #555; }
</style>
</head>
<body>
  <div class="cover">
    <h1>TradeCraftX</h1>
    <p>UI screenshots &mdash; ${new Date().toISOString().slice(0, 10)}</p>
    <p>${manifest.length} pages captured</p>
  </div>
${sections}
</body>
</html>
`;
}

async function buildPdf(browser) {
  fs.mkdirSync(outRoot, { recursive: true });
  const htmlPath = path.join(outRoot, 'index.html');
  fs.writeFileSync(htmlPath, buildGalleryHtml(), 'utf8');

  const page = await browser.newPage();
  await page.goto(pathToFileURL(htmlPath).href);
  await page.waitForFunction(() => Array.from(document.images).every((img) => img.complete));
  const pdfPath = path.join(outRoot, 'TradeCraftX-Screenshots.pdf');
  await page.pdf({
    path: pdfPath,
    format: 'A4',
    printBackground: true,
    margin: { top: '12mm', right: '10mm', bottom: '12mm', left: '10mm' },
  });
  await page.close();
  console.log(`PDF written to ${pdfPath}`);
}

async function main() {
  fs.mkdirSync(outRoot, { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();

    if (pass === 'empty' || pass === 'both') {
      console.log('== empty pass ==');
      await capturePublicPages(page, 'empty');
      await login(page);
      await captureAuthenticatedPages(page, 'empty', PUBLIC_PAGES.length + 1);
      await captureOverlays(page, 'empty', PUBLIC_PAGES.length + PAGES.length + 1);
    }

    if (pass === 'live' || pass === 'both') {
      console.log('== live pass ==');
      if (pass === 'live') {
        await login(page);
      }
      await startSession(page);
      if (connectionId) {
        // SessionsPage hydrates SessionContext from localStorage on mount.
        await navigateTo(page, '/sessions');
        await settle(page);
      }
      await captureAuthenticatedPages(page, 'live');
      await captureOverlays(page, 'live', PAGES.length + 1);
    }

    fs.writeFileSync(indexJsonPath, JSON.stringify(manifest, null, 2), 'utf8');

    if (pass === 'both' || pass === 'live' || pass === 'pdf') {
      await buildPdf(browser);
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
