// Partie E — interface dans un vrai navigateur (Chromium + Playwright préinstallés, Node).
//
// Usage : node tests/interface_playwright.js <url de l'application> <dossier de sortie>
// (lancé par tests/test_interface_playwright.py, qui démarre Streamlit). Écrit <sortie>/resultats.json :
// { scenario: { ok, erreurs_console, exceptions, duree_ms, details } } et des captures d'écran.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const URL = process.argv[2] || 'http://localhost:8501';
const OUT = process.argv[3] || '/tmp/surya_playwright';
const RACINE = path.resolve(__dirname, '..');
fs.mkdirSync(OUT, { recursive: true });
const resultats = {};

async function attendre(page, ms = 400) {
  // Streamlit : attendre la fin du recalcul (le widget d'état « Running » disparaît)
  await page.waitForTimeout(ms);
  for (let i = 0; i < 300; i++) {
    const enCours = await page.locator('[data-testid="stStatusWidget"]').count();
    if (!enCours) break;
    await page.waitForTimeout(100);
  }
  await page.waitForTimeout(150);
}

async function cliquer(page, nom, opts = {}) {
  const b = page.getByRole('button', { name: nom, exact: !!opts.exact }).first();
  await b.scrollIntoViewIfNeeded();
  await b.click();
  await attendre(page);
}

async function nouvellePage(browser, vp = { width: 1440, height: 900 }) {
  const ctx = await browser.newContext({ viewport: vp, acceptDownloads: true, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const journal = { console: [], pageerror: [] };
  page.on('console', (m) => { if (m.type() === 'error') journal.console.push(m.text()); });
  page.on('pageerror', (e) => journal.pageerror.push(String(e)));
  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.getByText('Audit de faisabilité', { exact: false }).first().waitFor({ timeout: 60000 });
  await attendre(page);
  return { ctx, page, journal };
}

async function exceptions(page) {
  return await page.locator('[data-testid="stException"]').allInnerTexts();
}

async function telecharger(page, nom, dest) {
  const t0 = Date.now();
  const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 120000 }),
                                  page.getByRole('button', { name: nom }).first().click()]);
  await dl.saveAs(dest);
  return { fichier: dest, taille: fs.statSync(dest).size, ms: Date.now() - t0 };
}

async function scenario(nom, browser, f, vp) {
  const t0 = Date.now();
  const { ctx, page, journal } = await nouvellePage(browser, vp);
  const r = { ok: false, details: {} };
  try {
    await f(page, r.details);
    r.ok = true;
  } catch (e) {
    r.erreur = String(e).slice(0, 600);
    await page.screenshot({ path: path.join(OUT, `${nom}_erreur.png`), fullPage: true }).catch(() => {});
  }
  r.exceptions = await exceptions(page).catch(() => []);
  r.erreurs_console = journal.console;
  r.erreurs_page = journal.pageerror;
  r.duree_ms = Date.now() - t0;
  resultats[nom] = r;
  await ctx.close();
}

async function chargerExemple(page) {
  await page.getByText('Reprendre une saisie existante ou essayer avec un exemple').click();
  await attendre(page);
  await cliquer(page, "Charger l'exemple de l'Excel");
}

async function importerJSON(page, fichier) {
  await page.getByText('Reprendre une saisie existante ou essayer avec un exemple').click();
  await attendre(page);
  await page.locator('input[type=file]').first().setInputFiles(fichier);
  await attendre(page, 800);
  await cliquer(page, 'Importer ce fichier');
}

async function aller(page, numero, nomEtape) {
  await cliquer(page, new RegExp(`^(✓ )?${numero}\\. ${nomEtape}$`));
}

(async () => {
  const browser = await chromium.launch();

  // 1. Diagnostic complet, pas à pas, avec l'exemple : parcours et téléchargement des 3 documents
  await scenario('complet_pas_a_pas', browser, async (page, d) => {
    await chargerExemple(page);
    await cliquer(page, 'Commencer — diagnostic complet');
    const etapes = [];
    for (let i = 0; i < 20; i++) {
      etapes.push((await page.locator('h2').first().innerText().catch(() => '')).trim());
      const suivant = page.getByRole('button', { name: /^(Suivant :|Générer les documents|Bloc suivant)/ });
      if (!(await suivant.count())) break;
      // un recalcul en cours peut remplacer le bouton (« element was detached ») : on réessaie
      let fini = false;
      for (let essai = 0; ; essai++) {
        try { await suivant.first().click({ timeout: 5000 }); break; } catch (e) {
          if (essai >= 3) throw e;
          await attendre(page);
          if (!(await suivant.count())) { fini = true; break; }  // le recalcul a changé d'étape
        }
      }
      if (fini) break;
      await attendre(page);
    }
    d.etapes = [...new Set(etapes)];
    // libellés d'étapes tronqués (points de suspension CSS) et infobulles dont le nom contient du balisage
    d.etapes_tronquees = await page.evaluate(() => [...document.querySelectorAll('button')]
      .filter((b) => /^(✓ )?\d\. /.test(b.innerText.trim()))
      .filter((b) => [b, ...b.querySelectorAll('*')].some((e) => e.scrollWidth > e.clientWidth + 1
        || getComputedStyle(e).textOverflow === 'ellipsis' && e.scrollWidth > e.getBoundingClientRect().width + 1))
      .map((b) => b.innerText.trim()));
    await aller(page, 3, 'Locaux');
    await page.getByRole('button', { name: '✏️ Modifier' }).first().click();
    await attendre(page);
    d.aria_balisage = await page.evaluate(() => [...document.querySelectorAll('[aria-label]')]
      .map((e) => e.getAttribute('aria-label')).filter((a) => a.includes(':gray[')).slice(0, 5));
    await aller(page, 8, 'Documents');
    d.pdf_cr = await telecharger(page, 'Compte rendu complet (PDF)', path.join(OUT, 'cr.pdf'));
    d.pdf_res = await telecharger(page, 'Résultats (PDF)', path.join(OUT, 'resultats.pdf'));
    d.csv = await telecharger(page, 'Tableau (CSV)', path.join(OUT, 'resultats.csv'));
    await page.screenshot({ path: path.join(OUT, 'documents.png'), fullPage: true });
  });

  // 2. Résultats, fiches à onglets ; retour arrière ; étapes verrouillées au départ
  await scenario('resultats_onglets', browser, async (page, d) => {
    await page.getByText('Fiches à onglets').click();
    await attendre(page);
    await cliquer(page, 'Commencer — résultats');
    d.etape6_desactivee = await page.getByRole('button', { name: /6\. Résultats/ }).isDisabled();
    await cliquer(page, 'Suivant : Locaux →');
    await cliquer(page, '➕ Ajouter un local');
    await page.getByRole('textbox', { name: /Nom de la pièce/ }).fill('Classe « test » & <b>');
    await page.keyboard.press('Tab');
    await attendre(page);
    await cliquer(page, '✓ Terminer le local');
    d.nom_affiche = await page.getByText('Classe « test » & <b>').count();
    await cliquer(page, '← Étape précédente');
    await cliquer(page, 'Suivant : Locaux →');
    d.nom_conserve = await page.getByText('Classe « test » & <b>').count();
    for (const e of ['Espaces extérieurs', 'Façades', 'Vérification', 'Résultats']) {
      await cliquer(page, new RegExp(`^Suivant : ${e}|^Voir les résultats`));
    }
    d.csv = await telecharger(page, 'Tableau (CSV)', path.join(OUT, 'resultats_onglets.csv'));
    d.pdf = await telecharger(page, 'Résultats (PDF)', path.join(OUT, 'resultats_onglets.pdf'));
  });

  // 3. Téléphone (375 px) : page de départ, étape Locaux et résultats de l'exemple
  await scenario('telephone', browser, async (page, d) => {
    d.debordement_depart = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    await page.screenshot({ path: path.join(OUT, 'tel_depart.png'), fullPage: true });
    await chargerExemple(page);
    await cliquer(page, 'Commencer — résultats');
    await aller(page, 6, 'Résultats');
    d.debordement_resultats = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    d.titre_y = (await page.locator('h2').first().boundingBox()).y;
    await page.screenshot({ path: path.join(OUT, 'tel_resultats.png'), fullPage: true });
    await aller(page, 2, 'Locaux');
    d.debordement_locaux = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    await page.screenshot({ path: path.join(OUT, 'tel_locaux.png'), fullPage: true });
  }, { width: 375, height: 812 });

  // 4. Grand écran
  await scenario('grand_ecran', browser, async (page, d) => {
    await chargerExemple(page);
    await cliquer(page, 'Commencer — diagnostic complet');
    await aller(page, 8, 'Documents');
    await page.screenshot({ path: path.join(OUT, 'grand_ecran_documents.png'), fullPage: false });
  }, { width: 2560, height: 1440 });

  // 5. Performances : 30 locaux et 5 espaces importés en JSON
  await scenario('trente_locaux', browser, async (page, d) => {
    const f = path.join(OUT, 'trente.json');
    if (!fs.existsSync(f)) throw new Error('trente.json absent');
    let t = Date.now();
    await importerJSON(page, f);
    d.import_ms = Date.now() - t;
    await cliquer(page, 'Commencer — diagnostic complet');
    t = Date.now();
    await aller(page, 3, 'Locaux');
    d.liste_locaux_ms = Date.now() - t;
    t = Date.now();
    await page.getByRole('button', { name: '✏️ Modifier' }).first().click();
    await attendre(page);
    d.ouvrir_local_ms = Date.now() - t;
    t = Date.now();
    await page.getByRole('spinbutton', { name: /Surface au sol/ }).first().fill('77');
    await page.keyboard.press('Tab');
    await attendre(page);
    d.saisie_ms = Date.now() - t;
    t = Date.now();
    await aller(page, 8, 'Documents');
    d.documents_ms = Date.now() - t;
    d.pdf_cr = await telecharger(page, 'Compte rendu complet (PDF)', path.join(OUT, 'cr_trente.pdf'));
    d.pdf_res = await telecharger(page, 'Résultats (PDF)', path.join(OUT, 'res_trente.pdf'));
  });

  // 6. Questionnaire en ligne : réponse → CSV téléchargé (réimporté par le test Python)
  await scenario('questionnaire_usager', browser, async (page, d) => {
    await page.goto(URL + '/?questionnaire=test123', { waitUntil: 'networkidle' });
    await page.getByText('Questionnaire confort estival').first().waitFor();
    await attendre(page);
    d.q12_visible_avant = await page.getByText(/12\. Si vous en avez/).count();
    await page.getByText('Rideaux', { exact: true }).click();
    await attendre(page);
    d.q12_visible_apres = await page.getByText(/12\. Si vous en avez/).count();
    await page.getByRole('radiogroup').filter({ hasText: 'Très chaude' }).getByText('Chaude', { exact: true }).click();
    await attendre(page);
    await page.getByRole('textbox', { name: /Remarques libres/ }).fill("Trop chaud l’après-midi ; « vraiment », merci");
    await page.keyboard.press('Tab');
    await attendre(page);
    await cliquer(page, 'Envoyer mes réponses');
    d.csv = await telecharger(page, 'Télécharger ma réponse (CSV)', path.join(OUT, 'reponse_usager.csv'));
  });

  // 7. Imports invalides dans le navigateur
  await scenario('imports_invalides', browser, async (page, d) => {
    const mauvais = path.join(OUT, 'mauvais.json');
    fs.writeFileSync(mauvais, '{pas du json');
    await importerJSON(page, mauvais);
    d.message = await page.locator('[data-testid="stAlertContentError"]').allInnerTexts();
  });

  await browser.close();
  fs.writeFileSync(path.join(OUT, 'resultats.json'), JSON.stringify(resultats, null, 1));
  console.log(JSON.stringify(Object.fromEntries(Object.entries(resultats).map(([k, v]) => [k, v.ok]))));
})();
