// Campagne de tests n° 2 — nouveautés dans un vrai navigateur (Chromium + Playwright préinstallés).
// Usage : node tests/interface_playwright_c2.js <url> <dossier de sortie> <photo.jpg>
// Écrit <sortie>/resultats_c2.json (même format que interface_playwright.js) et des captures.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const URL = process.argv[2] || 'http://localhost:8501';
const OUT = process.argv[3] || '/tmp/surya_c2';
const PHOTO = process.argv[4];
fs.mkdirSync(OUT, { recursive: true });
const resultats = {};

async function attendre(page, ms = 400) {
  await page.waitForTimeout(ms);
  for (let i = 0; i < 400; i++) {
    if (!(await page.locator('[data-testid="stStatusWidget"]').count())) break;
    await page.waitForTimeout(100);
  }
  await page.waitForTimeout(200);
}
async function cliquer(page, nom) {
  const b = page.getByRole('button', { name: nom }).first();
  await b.scrollIntoViewIfNeeded();
  await b.click();
  await attendre(page);
}
async function debord(page) {
  return await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
}
async function scenario(nom, browser, vp, f) {
  const ctx = await browser.newContext({ viewport: vp, acceptDownloads: true });
  const page = await ctx.newPage();
  const r = { ok: false, details: {}, erreurs_console: [], erreurs_page: [] };
  page.on('console', (m) => { if (m.type() === 'error') r.erreurs_console.push(m.text()); });
  page.on('pageerror', (e) => r.erreurs_page.push(String(e)));
  try {
    await page.goto(URL, { waitUntil: 'networkidle' });
    await page.getByText('Audit de faisabilité', { exact: false }).first().waitFor({ timeout: 60000 });
    await attendre(page);
    await f(page, r.details);
    r.ok = true;
  } catch (e) {
    r.erreur = String(e).slice(0, 600);
    await page.screenshot({ path: path.join(OUT, `${nom}_erreur.png`) }).catch(() => {});
  }
  r.exceptions = await page.locator('[data-testid="stException"]').allInnerTexts().catch(() => []);
  resultats[nom] = r;
  await ctx.close();
}
async function exempleSud(page) {
  await page.getByText('Reprendre une saisie existante ou essayer avec un exemple').click();
  await attendre(page);
  await cliquer(page, "Charger l'école type du Sud");
}

(async () => {
  const browser = await chromium.launch();

  // 1. « Passer à l'action » sur téléphone : chaque étape sans débordement horizontal ni exception
  await scenario('travaux_telephone', browser, { width: 375, height: 812 }, async (page, d) => {
    await exempleSud(page);
    await cliquer(page, "À partir de l'audit en cours");
    d.etapes = [];
    for (let i = 0; i < 6; i++) {
      const titre = (await page.locator('h2').first().innerText().catch(() => '')).trim();
      const t0 = Date.now();
      await page.getByRole('button', { name: /^(Suivant|← Étape précédente)/ }).first().waitFor({ timeout: 30000 }).catch(() => {});
      d.etapes.push({ titre, debord: await debord(page), rendu_ms: Date.now() - t0 });
      await page.screenshot({ path: path.join(OUT, `tel_travaux_${i}.png`) });
      const suivant = page.getByRole('button', { name: /^Suivant/ });
      await suivant.first().waitFor({ timeout: 30000 }).catch(() => {});
      if (!(await suivant.count())) break;
      await suivant.first().scrollIntoViewIfNeeded();
      await suivant.first().click();
      await attendre(page, 800);
    }
  });

  // 2. Photos : ajout d'un portrait (visage à flouter), export ZIP, réimport
  await scenario('photos_zip', browser, { width: 1440, height: 900 }, async (page, d) => {
    await exempleSud(page);
    await cliquer(page, 'Commencer — diagnostic complet');
    const t0 = Date.now();
    await page.locator('input[type=file]').first().setInputFiles(PHOTO);
    await attendre(page, 1500);
    d.ajout_ms = Date.now() - t0;
    d.messages = await page.locator('[data-testid="stAlertContentInfo"]').allInnerTexts();
    await page.getByRole('button', { name: /Réglages/ }).first().click();
    await attendre(page);
    await cliquer(page, 'Seuils et données');
    const [dl] = await Promise.all([page.waitForEvent('download'),
      page.getByRole('button', { name: 'Exporter la saisie et les photos (ZIP)' }).first().click()]);
    const zip = path.join(OUT, 'saisie.zip');
    await dl.saveAs(zip);
    d.zip = fs.statSync(zip).size;
    await cliquer(page, /Tout effacer/);
    await page.getByText('Reprendre une saisie existante ou essayer avec un exemple').click();
    await attendre(page);
    await page.locator('input[type=file]').first().setInputFiles(zip);
    await attendre(page, 800);
    await cliquer(page, 'Importer ce fichier');
    d.import = await page.locator('[data-testid="stAlertContentSuccess"]').allInnerTexts();
  });

  await browser.close();
  fs.writeFileSync(path.join(OUT, 'resultats_c2.json'), JSON.stringify(resultats, null, 1));
  console.log(JSON.stringify(Object.fromEntries(Object.entries(resultats).map(([k, v]) => [k, v.ok]))));
})();
