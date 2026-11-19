// Présentation de l'outil méthode SURYA (charte neutre provisoire)
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const { applyTheme } = require("/root/.claude/skills/synced/a72cde76-44a8-49b2-bd44-e3e1bceffde4_d551501c-8a93-4307-a1d6-eb47503105c6/pptx/scripts/apply_theme.js");

const DIR = __dirname;
const IMG = (n) => path.join(DIR, "img", n + ".jpg");
const DATA = JSON.parse(fs.readFileSync(path.join(DIR, "data.json"), "utf-8"));
const OUT = path.join(DIR, "Outil_methode_SURYA_presentation.pptx");

const THEME = {
  name: "SURYA neutre",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1F2A30", lt1: "FFFFFF", dk2: "263238", lt2: "F1F4F5",
    accent1: "D9661F", accent2: "2A7F8E", accent3: "6B7C85", accent4: "0F5A26",
    accent5: "8C1D18", accent6: "B7C4CA", hlink: "2A7F8E", folHlink: "6B7C85",
  },
};
const HEX = THEME.colors;
// couleurs des statuts (identiques à l'application et aux PDF)
const ST = {
  "Recommandé": ["D3F0DB", "0F5A26"], "À optimiser": ["FFE2C2", "8A4300"], "En place": ["D6E6FB", "0E4A8A"],
  "Sous réserve": ["FFF2B3", "6B5300"], "Non recommandé ou non adapté": ["F9D2D0", "8C1D18"], "Non concerné": ["E6E6E6", "4D4D4D"],
};
const COURT = { "Non recommandé ou non adapté": "Non recommandé" };

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13,333 × 7,5 in
pres.title = "Outil méthode SURYA — fonctionnement";
pres.author = "ACTEE";
pres.company = "ACTEE";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333, H = 7.5, M = 0.6;

// ------------------------------------------------------------------ dispositions
pres.defineSlideMaster({
  title: "TITRE", background: { color: HEX.dk2 },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: M, y: 2.3, w: 9.5, h: 1.6, fontSize: 44, bold: true, color: C.background1, valign: "bottom", margin: 0 }, text: "" } },
            { placeholder: { options: { name: "body", type: "body", x: M, y: 4.1, w: 9.5, h: 1.2, fontSize: 20, color: C.accent6, valign: "top", margin: 0 }, text: "" } }],
});
pres.defineSlideMaster({
  title: "SECTION", background: { color: HEX.dk2 },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: M, y: 2.9, w: 11, h: 1.0, fontSize: 40, bold: true, color: C.background1, margin: 0 }, text: "" } },
            { placeholder: { options: { name: "body", type: "body", x: M, y: 4.0, w: 11, h: 0.8, fontSize: 18, color: C.accent6, margin: 0 }, text: "" } }],
  slideNumber: { x: W - 1.0, y: H - 0.5, w: 0.5, h: 0.3, fontSize: 10, color: C.accent6, fontFace: "Calibri" },
});
pres.defineSlideMaster({
  title: "CONTENU", background: { color: HEX.lt1 },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: M, y: 0.35, w: W - 2 * M, h: 0.85, fontSize: 30, bold: true, color: C.text2, valign: "middle", margin: 0 }, text: "" } },
            { text: { text: "Outil méthode SURYA — présentation interne ACTEE", options: { x: M, y: H - 0.45, w: 7, h: 0.3, fontSize: 10, color: C.accent3, margin: 0 } } }],
  slideNumber: { x: W - 1.0, y: H - 0.45, w: 0.5, h: 0.3, fontSize: 10, color: C.accent3, fontFace: "Calibri" },
});

// ------------------------------------------------------------------ outils
const TOP = 1.45; // haut de la zone de contenu
function slide(titre, section) {
  const s = pres.addSlide({ masterName: "CONTENU", sectionTitle: section });
  s.addText(titre, { placeholder: "title" });
  return s;
}
function capture(s, img, x, y, w, ratio, nom) {
  const h = w * ratio;
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: C.background1 }, line: { color: HEX.accent6, width: 0.75 },
    shadow: { type: "outer", color: "000000", opacity: 0.18, blur: 8, offset: 3, angle: 90 }, objectName: nom + " cadre" });
  s.addImage({ path: IMG(img), x, y, w, h, objectName: nom, altText: nom });
  return h;
}
const R_ECRAN = 1042 / 2000, R_PAGE = 1287 / 910;
function puces(s, items, x, y, w, h, taille = 15) {
  s.addText(items.map((t, i) => {
    const runs = Array.isArray(t) ? t : [{ text: t }];
    return runs.map((r, j) => ({ text: r.text, options: { ...(r.options || {}), bullet: j === 0 ? { indent: 16 } : undefined,
      breakLine: j === runs.length - 1 && i < items.length - 1, paraSpaceAfter: 8 } }));
  }).flat(), { x, y, w, h, fontSize: taille, color: C.text1, valign: "top", margin: 0, isTextBox: true });
}
function pastille(s, statut, x, y, w = 1.6, h = 0.32, taille = 11) {
  const [f, t] = ST[statut];
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: f }, line: { color: f }, objectName: "pastille " + statut });
  s.addText(COURT[statut] || statut, { x, y, w, h, fontSize: taille, bold: true, color: t, align: "center", valign: "middle", margin: 0, isTextBox: true });
}
function carte(s, x, y, w, h, titre, texte, opts = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: opts.fond || C.background2 }, line: { color: opts.fond || HEX.lt2 }, objectName: "carte " + titre });
  if (opts.numero) {
    s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: y + 0.25, w: 0.5, h: 0.5, fill: { color: opts.pastille || C.accent1 }, line: { color: opts.pastille || HEX.accent1 } });
    s.addText(String(opts.numero), { x: x + 0.25, y: y + 0.25, w: 0.5, h: 0.5, fontSize: 16, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
  }
  const dx = opts.numero ? 0.95 : 0.3;
  s.addText(titre, { x: x + dx, y: y + 0.22, w: w - dx - 0.25, h: 0.55, fontSize: 17, bold: true, color: opts.couleurTitre || C.text2, valign: "middle", margin: 0, isTextBox: true });
  s.addText(texte, { x: x + 0.3, y: y + 0.9, w: w - 0.55, h: h - 1.05, fontSize: opts.taille || 14, color: C.text1, valign: "top", margin: 0, isTextBox: true, paraSpaceAfter: 6 });
}
function note(s, t) { s.addNotes(t); }

// ================================================================== 1. Titre
pres.addSection({ title: "Introduction" });
let s = pres.addSlide({ masterName: "TITRE", sectionTitle: "Introduction" });
s.addText("L'outil d'audit de faisabilité SURYA", { placeholder: "title" });
s.addText("Comment il fonctionne : parcours, entrées, sorties et exemples\nMaquette — présentation interne ACTEE", { placeholder: "body" });
s.addShape(pres.shapes.OVAL, { x: 10.6, y: 1.6, w: 2.1, h: 2.1, fill: { color: C.accent1 }, line: { color: HEX.accent1 }, objectName: "motif soleil" });
s.addShape(pres.shapes.OVAL, { x: 11.3, y: 3.2, w: 1.1, h: 1.1, fill: { color: C.accent2 }, line: { color: HEX.accent2 }, objectName: "motif" });
note(s, "Présentation de la maquette développée à partir de l'Excel « Outil d'aide au test de la méthode d'audit de faisabilité d'actions d'adaptation » de SURYA Ingénierie, notre prestataire. Objectif : montrer comment l'outil s'utilise, ce qu'il produit, et sur quelles règles il s'appuie.");

// ================================================================== 2. En bref
s = slide("De l'Excel à une application guidée", "Introduction");
const cw = (W - 2 * M - 2 * 0.35) / 3;
carte(s, M, TOP + 0.2, cw, 3.7, "Même logique que l'Excel",
  "Les 134 règles et alertes de l'Excel SURYA sont reprises à l'identique dans un moteur de calcul.\n\nVérifié sur des milliers de cas tirés au hasard : 0 écart avec l'Excel (aux erreurs de l'Excel près).", { numero: 1 });
carte(s, M + cw + 0.35, TOP + 0.2, cw, 3.7, "Une saisie guidée",
  "Un parcours étape par étape remplace les onglets de l'Excel : seules les questions utiles s'affichent, les manques sont signalés sans bloquer.", { numero: 2, pastille: C.accent2 });
carte(s, M + 2 * (cw + 0.35), TOP + 0.2, cw, 3.7, "Des documents prêts à diffuser",
  "Tableau des résultats, PDF des résultats, compte rendu complet (plan d'action, alertes, fiches) et export CSV.", { numero: 3, pastille: C.accent3 });
s.addText([{ text: "Statut actuel : ", options: { bold: true } }, { text: "maquette en ligne, sans base de données — la saisie s'exporte et se réimporte en fichier. Le passage à une base (Supabase) est préparé." }],
  { x: M, y: 5.75, w: W - 2 * M, h: 0.6, fontSize: 14, color: C.text2, margin: 0, isTextBox: true });
note(s, "Trois idées : on n'a pas réinventé la méthode, on l'a rendue utilisable. L'outil est en ligne sur Streamlit (outilplancanicule.streamlit.app). Aucune donnée n'est stockée sur un serveur pour l'instant.");

// ================================================================== 3. Comment l'outil décide
s = slide("Comment l'outil décide d'un statut", "Introduction");
const etapes = [["Réponses", "Relevés de visite : bâtiment, locaux, façades, espaces extérieurs"],
                ["État de chaque réponse", "Valeur saisie, « inconnue » (vide ou Non évalué) ou « sans objet »"],
                ["Règles dans l'ordre", "Pour chaque solution, la première règle vérifiée donne le statut"],
                ["Statut + alertes", "Une donnée manquante sur la règle retenue → « Sous réserve »"]];
const ew = 2.75, eg = 0.32;
etapes.forEach(([t, d], i) => {
  const x = M + i * (ew + eg);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: TOP + 0.2, w: ew, h: 1.9, rectRadius: 0.1, fill: { color: i === 3 ? C.accent1 : C.background2 }, line: { color: i === 3 ? HEX.accent1 : HEX.lt2 }, objectName: "étape " + t });
  s.addText(t, { x: x + 0.2, y: TOP + 0.35, w: ew - 0.4, h: 0.45, fontSize: 16, bold: true, color: i === 3 ? C.background1 : C.text2, margin: 0, isTextBox: true });
  s.addText(d, { x: x + 0.2, y: TOP + 0.85, w: ew - 0.4, h: 1.15, fontSize: 13, color: i === 3 ? C.background1 : C.text1, margin: 0, valign: "top", isTextBox: true });
  if (i < 3) s.addShape(pres.shapes.CHEVRON, { x: x + ew + 0.08, y: TOP + 1.0, w: 0.16, h: 0.3, fill: { color: C.accent3 }, line: { color: HEX.accent3 }, objectName: "flèche" });
});
s.addText("Les six statuts", { x: M, y: 4.0, w: 5, h: 0.4, fontSize: 18, bold: true, color: C.text2, margin: 0, isTextBox: true });
const defs = [["Recommandé", "Solution absente, sans obstacle identifié"], ["À optimiser", "Présente mais défaillante ou mal réglée"],
              ["En place", "Présente et satisfaisante"], ["Sous réserve", "Possible sous réserve de vérifications"],
              ["Non recommandé ou non adapté", "Impossible ou très peu pertinente"], ["Non concerné", "Le local ne comporte pas l'élément"]];
defs.forEach(([st, d], i) => {
  const col = i % 2, row = Math.floor(i / 2), x = M + col * 6.1, y = 4.55 + row * 0.6;
  pastille(s, st, x, y, 2.0, 0.38, 12);
  s.addText(d, { x: x + 2.15, y, w: 3.8, h: 0.38, fontSize: 13, color: C.text1, valign: "middle", margin: 0, isTextBox: true });
});
note(s, "Logique à trois valeurs reprise de l'Excel : chaque condition vaut vrai, faux ou indéterminé. Les règles d'un bloc sont lues dans l'ordre de la méthode ; la première non fausse l'emporte. Si elle est indéterminée faute de donnée, la solution passe « Sous réserve ». Les alertes (AL : maîtrise d'œuvre, VA : validation ponctuelle) s'ajoutent au statut.");

// ================================================================== 4. Deux parcours
pres.addSection({ title: "Les parcours" });
s = pres.addSlide({ masterName: "SECTION", sectionTitle: "Les parcours" });
s.addText("Les parcours", { placeholder: "title" });
s.addText("Du choix de départ jusqu'aux documents", { placeholder: "body" });
note(s, "Partie 2 : comment un auditeur utilise l'outil, écran par écran.");

s = slide("Au départ : deux usages, deux parcours", "Les parcours");
capture(s, "s01_depart", M, TOP + 0.1, 6.6, R_ECRAN, "Écran de départ");
const px = M + 7.0, pw = W - M - px;
carte(s, px, TOP + 0.1, pw, 2.25, "Résultats de faisabilité",
  "L'équivalent de l'Excel. 6 étapes : Bâtiment → Locaux → Espaces extérieurs → Façades → Vérification → Résultats.", { couleurTitre: C.accent2 });
carte(s, px, TOP + 2.55, pw, 2.35, "Diagnostic complet",
  "Même saisie, plus l'identification de l'audit, les observations, les questionnaires usagers. 8 étapes, jusqu'au compte rendu complet.", { couleurTitre: C.accent1 });
s.addText("On passe de l'un à l'autre sans perdre la saisie.", { x: px, y: 6.15, w: pw, h: 0.45, fontSize: 13, italic: true, color: C.accent3, margin: 0, isTextBox: true });
note(s, "Premier choix : ce que l'on veut produire. Le parcours Résultats sert à tester la méthode comme avec l'Excel ; le Diagnostic complet produit le livrable pour la collectivité. Deuxième choix sur le même écran : le mode de saisie (slide suivante).");

// ================================================================== 6. Modes de saisie
s = slide("Deux façons de remplir : pas à pas ou par onglets", "Les parcours");
capture(s, "s03_batiment", M, TOP + 0.1, 6.0, R_ECRAN, "Bâtiment, pas à pas");
capture(s, "s05_local_theme1", M + 6.3, TOP + 0.1, 6.0, R_ECRAN, "Local, premier thème");
s.addText([{ text: "Pas à pas : ", options: { bold: true, color: C.accent1 } }, { text: "un bloc par écran (bâtiment en 5 blocs, local en 7 thèmes), avec « Suivant ». Idéal pendant la visite." }],
  { x: M, y: 4.85, w: 6.0, h: 0.9, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true });
s.addText([{ text: "Fiches à onglets : ", options: { bold: true, color: C.accent2 } }, { text: "tous les thèmes accessibles librement. Idéal pour reprendre ou corriger une saisie." }],
  { x: M + 6.3, y: 4.85, w: 6.0, h: 0.9, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true });
s.addText("Les questions conditionnelles (« si B-09 = Oui… ») n'apparaissent que lorsqu'elles ont un objet.", { x: M, y: 5.9, w: W - 2 * M, h: 0.4, fontSize: 13, italic: true, color: C.accent3, margin: 0, isTextBox: true });
note(s, "Le mode se change à tout moment. Dans les deux cas, chaque question garde son code de la méthode (B-01, L-03, MEX-04…) pour faire le lien avec le carnet de visite.");

// ================================================================== 7. Saisie d'un local
s = slide("Saisir un local : les statuts se calculent en direct", "Les parcours");
capture(s, "s06_local_murs", M, TOP + 0.1, 8.2, R_ECRAN, "Murs et baies");
puces(s, [
  [{ text: "Murs extérieurs : ", options: { bold: true } }, { text: "orientation, position des baies, retrait du vitrage, débord, types et nombre de baies (4 murs au plus)." }],
  [{ text: "À droite : ", options: { bold: true } }, { text: "les 12 statuts du local, recalculés à chaque réponse." }],
  [{ text: "En bas : ", options: { bold: true } }, { text: "ce qui reste sans réponse, sans bloquer." }],
], M + 8.55, TOP + 0.2, W - M - (M + 8.55), 4.2, 14);
note(s, "Exemple : la Classe CP de l'école type. Le thème « Murs et baies » est le plus riche : il alimente la ventilation naturelle et les protections solaires. Les statuts à droite permettent à l'auditeur de voir immédiatement l'effet d'une réponse.");

// ================================================================== 8. Liste des locaux
s = slide("Une fiche par local, un coup d'œil sur l'avancement", "Les parcours");
capture(s, "s04_locaux_liste", M, TOP + 0.1, 7.6, R_ECRAN, "Liste des locaux");
carte(s, M + 7.95, TOP + 0.1, W - M - (M + 7.95), 4.0, "Sur chaque carte",
  "Le type de local, l'état de la saisie (complet ou nombre de réponses manquantes) et le nombre de solutions par statut.\n\nBoutons : modifier, dupliquer (locaux semblables), supprimer. Les noms en double sont signalés.");
note(s, "Après chaque local, on revient à cette liste pour en ajouter un autre ou passer à l'étape suivante. La duplication fait gagner du temps sur des classes identiques.");

// ================================================================== 9. Façades
s = slide("Les façades, décrites une fois pour tous les locaux", "Les parcours");
capture(s, "s08_facades", M, TOP + 0.1, 7.6, R_ECRAN, "Façades");
puces(s, [
  "L'étape vient après les locaux et les espaces : l'outil coche d'office les façades qu'ils citent.",
  "Quatre questions par façade : alignement sur la rue, accès nacelle, obstacle, désordres.",
  "Elles alimentent les protections solaires des locaux et l'ombrage adossé de la cour.",
], M + 7.95, TOP + 0.2, W - M - (M + 7.95), 4.4, 14);
note(s, "Ordre décidé avec vous : bâtiment, locaux, espaces extérieurs, puis façades. Une façade citée mais non décrite laisse les règles qui en dépendent « Sous réserve » ; la vérification le signale.");

// ================================================================== 10. Questionnaires
s = slide("Diagnostic complet : le ressenti des usagers", "Les parcours");
capture(s, "s13_usager", M, TOP + 0.1, 6.0, R_ECRAN, "Questionnaire usager");
capture(s, "s09b_synthese", M + 6.3, TOP + 0.1, 6.0, 917 / 2000, "Synthèse et matrice");
s.addText("Le questionnaire en ligne (24 questions, 5 minutes) tel que le voit un enseignant.", { x: M, y: 4.85, w: 6.0, h: 0.7, fontSize: 13, color: C.text1, margin: 0, valign: "top", isTextBox: true });
s.addText("Synthèse pour l'établissement et croisement avec les préconisations de l'audit.", { x: M + 6.3, y: 4.85, w: 6.0, h: 0.7, fontSize: 13, color: C.text1, margin: 0, valign: "top", isTextBox: true });
s.addText("Collecte : lien en ligne, import d'un fichier CSV au même format, ou saisie d'un questionnaire papier. En maquette, aucune réponse n'est stockée.", { x: M, y: 5.85, w: W - 2 * M, h: 0.7, fontSize: 13, italic: true, color: C.accent3, margin: 0, isTextBox: true });
note(s, "Le questionnaire SURYA du 11/11/2026, avec une question ouverte ajoutée (Q24). La matrice de correspondance est une proposition à valider (points à trancher, § E1). La collecte en ligne réelle demandera la base de données.");

// ================================================================== 11. Vérification
s = slide("Avant les documents : une vérification, sans blocage", "Les parcours");
capture(s, "s10_verification", M, TOP + 0.1, 7.6, R_ECRAN, "Vérification");
carte(s, M + 7.95, TOP + 0.1, W - M - (M + 7.95), 4.0, "Ce qui est vérifié",
  "Identification, bâtiment, façades citées, chaque local et chaque espace : nombre de réponses manquantes et solutions « Sous réserve » faute de données.\n\nUn bouton « Compléter » ramène au bon bloc.");
note(s, "Principe retenu : avertir sans bloquer. Une donnée manquante n'empêche pas de produire les documents ; elle se traduit par « Sous réserve » et apparaît dans la liste des données à compléter du compte rendu.");

// ================================================================== 12. Sorties
s = slide("Quatre sorties, à la fin du parcours", "Les parcours");
const sw = 2.55, sg = (W - 2 * M - 4 * sw) / 3;
[["s11_documents", R_ECRAN, "À l'écran", "Tableau des statuts et détail des règles pour chaque local."],
 ["res_p1", R_PAGE, "PDF Résultats", "2 à 3 pages : statuts, alertes, données manquantes."],
 ["cr_p5", R_PAGE, "Compte rendu complet", "≈ 30 pages : synthèse, plan d'action, alertes AL / VA, fiches."],
 ["cr_p1", R_PAGE, "CSV", "Une ligne par solution et par local, pour Excel."]].forEach(([img, r, t, d], i) => {
  const x = M + i * (sw + sg);
  const hImg = Math.min(sw * r, 3.0), wImg = hImg / r;
  if (t === "CSV") {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: TOP + 0.1, w: sw, h: 3.0, rectRadius: 0.1, fill: { color: C.background2 }, line: { color: HEX.lt2 }, objectName: "CSV" });
    s.addText("Type ; Nom ; Groupe ; Solution ; Statut ; Règle retenue ; Donnée manquante ; Alertes", { x: x + 0.2, y: TOP + 0.4, w: sw - 0.4, h: 2.4, fontSize: 12, fontFace: "Courier New", color: C.text2, margin: 0, valign: "top", isTextBox: true });
  } else {
    capture(s, img, x + (sw - wImg) / 2, TOP + 0.1, wImg, r, t);
  }
  s.addText(t, { x, y: TOP + 3.3, w: sw, h: 0.4, fontSize: 16, bold: true, color: C.text2, margin: 0, isTextBox: true });
  s.addText(d, { x, y: TOP + 3.75, w: sw, h: 0.9, fontSize: 13, color: C.text1, margin: 0, valign: "top", isTextBox: true });
});
note(s, "Le parcours Résultats propose l'écran, le PDF Résultats et le CSV ; le Diagnostic complet ajoute le compte rendu. Le compte rendu suit le cadre de la méthode : ce qui est engageable rapidement, ce qui doit d'abord être validé, avec les quantités relevées.");

// ================================================================== 13. Exemple
pres.addSection({ title: "Exemple" });
s = pres.addSlide({ masterName: "SECTION", sectionTitle: "Exemple" });
s.addText("Un exemple : une école type du Sud", { placeholder: "title" });
s.addText("Entrées, sorties, et ce qui fait changer un statut", { placeholder: "body" });
note(s, "Partie 3 : un jeu de données fictif mais réaliste, chargeable dans l'application (Réglages → Charger l'école type du Sud).");

s = slide("Groupe scolaire Les Pins (fictif) : les entrées", "Exemple");
const chiffres = [["≈ 1 000 m²", "R+1, maçonnerie, 1972"], ["8 cm", "d'isolant en toiture-terrasse"], ["6 locaux", "audités + la cour"], ["14", "questionnaires usagers"]];
chiffres.forEach(([v, l], i) => {
  const x = M + i * 3.05;
  s.addText(v, { x, y: TOP + 0.1, w: 2.9, h: 0.8, fontSize: 36, bold: true, color: C.accent1, margin: 0, isTextBox: true });
  s.addText(l, { x, y: TOP + 0.9, w: 2.9, h: 0.4, fontSize: 13, color: C.accent3, margin: 0, isTextBox: true });
});
const locs = [["Classe CP", "RDC, traversante sud / nord, volets ajourés, dalle béton 3,00 m, éclairage non LED"],
              ["Classe CM2", "Étage, sud seul, baies au nu extérieur, oscillo-battants, stores pleins, faux plafond 2,50 m"],
              ["Salle de motricité", "Plain-pied, ouest, vitrages fixes, brasseurs hors service, toiture"],
              ["Dortoir maternelle", "RDC, est, alarme volumétrique, retrait du vitrage 14 cm"],
              ["Bureau de direction", "14 m² pour 3 personnes, copieur, postes allumés la nuit"],
              ["Bibliothèque BCD", "Étage, est / ouest, fenêtres de toit motorisées avec volets"]];
const tbl = [[{ text: "Local", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } }, { text: "Ce qui a été relevé", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } }]]
  .concat(locs.map(([a, b], i) => [{ text: a, options: { bold: true, fill: { color: i % 2 ? HEX.lt1 : HEX.lt2 } } }, { text: b, options: { fill: { color: i % 2 ? HEX.lt1 : HEX.lt2 } } }]));
s.addTable(tbl, { x: M, y: TOP + 1.55, w: W - 2 * M, colW: [2.6, W - 2 * M - 2.6], fontSize: 13, color: HEX.dk1, border: { type: "solid", pt: 0.5, color: HEX.accent6 }, rowH: 0.42, valign: "middle", objectName: "locaux de l'exemple" });
s.addText("Cour : 150 élèves, 80 m² d'ombrage hors arbres, préau métallique foncé de 2,80 m, deux platanes.", { x: M, y: 6.55, w: W - 2 * M, h: 0.35, fontSize: 13, italic: true, color: C.accent3, margin: 0, isTextBox: true });
note(s, "Un groupe scolaire de 1972 comme il en existe beaucoup dans le Sud. Les locaux ont été choisis pour couvrir des situations contrastées : traversant ou mono-orienté, RDC ou dernier niveau, plafond haut ou faux plafond bas.");

// ================================================================== 15. Résultats
s = slide("Les sorties : statuts de l'école", "Exemple");
const solIdx = [0, 1, 3, 4, 5, 8, 10];
const nomsSol = ["Brasseurs d'air", "Ventilation naturelle nocturne", "Protections verticales", "Protections horizontales", "Films solaires", "Toiture", "Éclairage"];
const courtsLoc = ["Classe CP", "Classe CM2", "Motricité", "Dortoir", "Bureau", "BCD"];
const head = [{ text: "", options: { fill: { color: HEX.lt1 } } }].concat(courtsLoc.map((n) => ({ text: n, options: { bold: true, align: "center", color: HEX.lt1, fill: { color: HEX.dk2 } } })));
const rows = solIdx.map((si, k) => [{ text: nomsSol[k], options: { bold: true, fill: { color: HEX.lt2 } } }].concat(DATA.statuts.map((st) => {
  const v = st[si], [f, t] = ST[v];
  return { text: COURT[v] || v, options: { align: "center", color: t, bold: true, fill: { color: f } } };
})));
s.addTable([head].concat(rows), { x: M, y: TOP + 0.1, w: W - 2 * M, colW: [3.0].concat(Array(6).fill((W - 2 * M - 3.0) / 6)), fontSize: 12, rowH: 0.5, valign: "middle", border: { type: "solid", pt: 1, color: HEX.lt1 }, objectName: "statuts de l'école" });
s.addText("Ventilation mécanique : « Non recommandé » partout (pas de ventilation mécanique). Cour : ombrage adossé « Recommandé », préau et ombrage de la cour « À optimiser ».",
  { x: M, y: 5.75, w: W - 2 * M, h: 0.6, fontSize: 13, italic: true, color: C.accent3, margin: 0, isTextBox: true });
note(s, "Extrait du tableau des résultats (7 des 12 solutions). Les mêmes statuts figurent dans le PDF Résultats et dans le CSV. Sur l'école : 20 Recommandé, 14 En place, 12 Sous réserve, 11 Non recommandé, 4 À optimiser, 14 Non concerné.");

// ================================================================== 16. Pourquoi
s = slide("Pourquoi deux classes au sud n'ont pas les mêmes statuts", "Exemple");
const cmp = [
  ["Classe CP (RDC)", [["Brasseurs", "Recommandé", "dalle béton à 3,00 m (BS-7)"], ["Ventilation naturelle", "Recommandé", "baies ouvrantes au sud et au nord (VN-7)"], ["Protections verticales", "Recommandé", "retrait du vitrage 20 cm ≥ 16 cm (PV-8)"], ["Toiture", "Non concerné", "local au RDC (TO-0)"]]],
  ["Classe CM2 (étage)", [["Brasseurs", "Sous réserve", "faux plafond à 2,50 m, entre 2,40 et 2,60 m (BS-3)"], ["Ventilation naturelle", "Sous réserve", "stores extérieurs pleins (VN-3)"], ["Protections verticales", "Non recommandé ou non adapté", "baies au nu extérieur sans débord (PV-1)"], ["Toiture", "Sous réserve", "terrasse isolée à 8 cm, < 30 cm (TT-3)"]]],
];
cmp.forEach(([titre, lignes], c) => {
  const x = M + c * 6.15, w = 5.95;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: TOP + 0.1, w, h: 4.6, rectRadius: 0.1, fill: { color: C.background2 }, line: { color: HEX.lt2 }, objectName: titre });
  s.addText(titre, { x: x + 0.3, y: TOP + 0.25, w: w - 0.6, h: 0.5, fontSize: 18, bold: true, color: C.text2, margin: 0, isTextBox: true });
  lignes.forEach(([sol, st, why], i) => {
    const y = TOP + 0.95 + i * 0.92;
    s.addText(sol, { x: x + 0.3, y, w: 2.6, h: 0.36, fontSize: 14, bold: true, color: C.text1, margin: 0, valign: "middle", isTextBox: true });
    pastille(s, st, x + 3.0, y, 2.6, 0.36, 11);
    s.addText(why, { x: x + 0.3, y: y + 0.4, w: w - 0.6, h: 0.4, fontSize: 13, color: C.accent3, margin: 0, valign: "top", isTextBox: true });
  });
});
note(s, "Chaque statut est justifié par la règle qui l'a produit (code entre parenthèses) : c'est le principe de traçabilité de la méthode. Le détail est consultable à l'écran et figure dans les fiches du compte rendu.");

// ================================================================== 17. Plan d'action
s = slide("Ce que le compte rendu en tire : le plan d'action", "Exemple");
const engag = [["Films solaires", "6 locaux"], ["Brasseurs d'air", "CP, motricité (à remettre en service), dortoir, bureau, BCD"], ["Protections verticales", "CP, motricité, bureau"], ["Éclairage LED", "CP, motricité, bureau"], ["Ventilation naturelle", "CP, BCD"], ["Ombrage de la cour", "à compléter (arbres, voiles)"]];
const valid = [["Toiture-terrasse", "8 cm d'isolant : CM2, motricité, BCD"], ["Ventilation naturelle", "CM2, motricité, dortoir, bureau"], ["Ombrage adossé (cour)", "recommandé, mais alertes AL vent et incendie"], ["Préau", "à optimiser, charpente à vérifier (AL)"], ["Bureau", "densité et équipements à revoir"]];
[["Engageable rapidement", engag, C.accent4, "D3F0DB"], ["À valider avant de consulter", valid, C.accent1, "FFE2C2"]].forEach(([t, l, col, fond], c) => {
  const x = M + c * 6.15, w = 5.95;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: TOP + 0.1, w, h: 0.6, rectRadius: 0.1, fill: { color: fond }, line: { color: fond }, objectName: t });
  s.addText(t, { x: x + 0.3, y: TOP + 0.1, w: w - 0.6, h: 0.6, fontSize: 18, bold: true, color: col, margin: 0, valign: "middle", isTextBox: true });
  s.addText(l.map(([a, b], i) => [{ text: a + " : ", options: { bold: true, bullet: { indent: 16 } } }, { text: b, options: { breakLine: i < l.length - 1 } }]).flat(),
    { x: x + 0.1, y: TOP + 0.95, w: w - 0.2, h: 3.9, fontSize: 14, color: C.text1, margin: 0, valign: "top", paraSpaceAfter: 9, isTextBox: true });
});
note(s, "Le plan d'action du compte rendu classe chaque couple solution × local : engageable (Recommandé ou À optimiser sans alerte maîtrise d'œuvre), à valider (Sous réserve ou alerte AL), en place, exclu. Pour chaque ligne : les quantités relevées (baies par orientation, surfaces) et le motif.");

// ================================================================== 18. Cas pédagogiques
s = slide("Une réponse change, le statut change", "Exemple");
const cas = [
  ["Hauteur sous plafond (Classe CP)", [["3,00 m", "Recommandé"], ["2,50 m", "Sous réserve"], ["2,30 m", "Non recommandé ou non adapté"]], "Brasseurs d'air : seuils 2,40 et 2,60 m"],
  ["Ouvrants de la Classe CP", [["Sud + nord", "Recommandé"], ["Sud seul", "Sous réserve"], ["Vitrages fixes", "Non recommandé ou non adapté"]], "Ventilation naturelle nocturne"],
  ["Retrait du vitrage", [["20 cm", "Recommandé"], ["12 cm", "Sous réserve"], ["Nu extérieur", "Non recommandé ou non adapté"]], "Protections verticales : seuil 16 cm"],
  ["Isolant de la toiture-terrasse", [["32 cm", "En place"], ["8 cm", "Sous réserve"], ["Non isolée", "Sous réserve"]], "Toiture (locaux du dernier niveau)"],
];
cas.forEach(([t, vals, sous], i) => {
  const col = i % 2, row = Math.floor(i / 2), x = M + col * 6.15, y = TOP + 0.1 + row * 2.45, w = 5.95;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 2.25, rectRadius: 0.1, fill: { color: C.background2 }, line: { color: HEX.lt2 }, objectName: t });
  s.addText(t, { x: x + 0.3, y: y + 0.15, w: w - 0.6, h: 0.4, fontSize: 16, bold: true, color: C.text2, margin: 0, isTextBox: true });
  s.addText(sous, { x: x + 0.3, y: y + 0.55, w: w - 0.6, h: 0.3, fontSize: 12, color: C.accent3, margin: 0, isTextBox: true });
  vals.forEach(([v, st], j) => {
    const yy = y + 0.95 + j * 0.42;
    s.addText(v, { x: x + 0.3, y: yy, w: 2.4, h: 0.34, fontSize: 14, color: C.text1, margin: 0, valign: "middle", isTextBox: true });
    pastille(s, st, x + 2.9, yy, 2.7, 0.34, 11);
  });
});
note(s, "Résultats calculés par l'outil en ne changeant qu'une réponse de l'école type. Ce sont les seuils de la méthode (onglet Paramètres de l'Excel), modifiables dans les Réglages pour tester des variantes.");

// ================================================================== 19. Données manquantes et priorités
s = slide("Donnée manquante, priorité des règles, alertes", "Exemple");
carte(s, M, TOP + 0.1, 3.9, 4.3, "Une donnée manque",
  "Hauteur sous plafond non renseignée dans la Classe CP.\n\n→ Brasseurs « Sous réserve ».\n\nLe compte rendu indique : « compléter PL-03 ».", { numero: 1 });
carte(s, M + 4.12, TOP + 0.1, 3.9, 4.3, "La première règle l'emporte",
  "Bâtiment en abords de monument historique (B-06 = Oui).\n\n→ Protections verticales de la Classe CP : « Sous réserve » (PV-3), même si tout le reste est favorable.", { numero: 2, pastille: C.accent2 });
carte(s, M + 8.24, TOP + 0.1, 3.9, 4.3, "Les alertes s'ajoutent",
  "Ombrage adossé « Recommandé » dans la cour, avec deux alertes maîtrise d'œuvre : prise au vent des voiles, sécurité incendie.\n\n→ Classé « À valider avant de consulter ».", { numero: 3, pastille: C.accent3 });
note(s, "Trois mécanismes à connaître pour lire les résultats. 1) Le principe de prudence de la méthode : une inconnue donne « Sous réserve ». 2) L'ordre des règles : la plus restrictive passe d'abord. 3) Les alertes AL / VA, dont le typage est une proposition à valider.");

// ================================================================== 20. Usagers
s = slide("Le ressenti des usagers croisé avec l'audit", "Exemple");
[["64 %", "ont trop chaud souvent ou très souvent"], ["79 %", "souffrent de la chaleur l'après-midi"], ["71 %", "ne peuvent pas laisser les fenêtres ouvertes la nuit"]].forEach(([v, l], i) => {
  s.addText(v, { x: M, y: TOP + 0.05 + i * 1.35, w: 3.6, h: 0.75, fontSize: 40, bold: true, color: C.accent1, margin: 0, isTextBox: true });
  s.addText(l, { x: M, y: TOP + 0.8 + i * 1.35, w: 3.6, h: 0.45, fontSize: 13, color: C.accent3, margin: 0, isTextBox: true });
});
const mat = [["M1", "Gêne due au soleil", "Cohérent"], ["M2", "Air lourd", "Cohérent"], ["M3", "Chaleur dès le matin", "Cohérent"], ["M4", "Chaleur l'après-midi", "Cohérent"],
             ["M5", "Inconfort global", "Cohérent"], ["M6", "Protections en place peu utilisées", "À vérifier"], ["M7", "Fenêtres fermées la nuit", "À vérifier"], ["M8", "Équipements déclarés", "À vérifier"]];
const mh = [[{ text: "Croisement", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } }, { text: "Ressenti des usagers", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } }, { text: "Résultat", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } }]]
  .concat(mat.map(([a, b, r]) => [{ text: a, options: { bold: true } }, { text: b }, { text: r, options: { bold: true, color: r === "Cohérent" ? "0F5A26" : "8A4300", fill: { color: r === "Cohérent" ? "D3F0DB" : "FFE2C2" } } }]));
s.addTable(mh, { x: 4.6, y: TOP + 0.1, w: W - M - 4.6, colW: [1.4, 4.4, W - M - 4.6 - 5.8], fontSize: 13, rowH: 0.45, valign: "middle", border: { type: "solid", pt: 0.5, color: HEX.accent6 }, objectName: "matrice" });
s.addText("Indicateur de cohérence : 62 % (5 croisements sans incohérence sur 8). Exemple M7 : la ventilation naturelle est recommandée dans 2 locaux, mais les usagers disent ne pas pouvoir ouvrir la nuit.",
  { x: 4.6, y: 5.75, w: W - M - 4.6, h: 0.7, fontSize: 13, italic: true, color: C.accent3, margin: 0, isTextBox: true });
note(s, "14 réponses fictives. La matrice et l'indicateur sont une proposition de notre part (le questionnaire SURYA les annonce sans les définir) : à valider avec SURYA (points à trancher, § E1 et F7-F8).");

// ================================================================== 21. Fiabilité et suite
pres.addSection({ title: "Suite" });
s = slide("Fiabilité, points ouverts et prochaines étapes", "Suite");
[["≈ 900", "tests automatiques"], ["0 écart", "avec l'Excel corrigé, sur 3 000 cas"], ["37", "anomalies trouvées par la campagne, 36 corrigées"]].forEach(([v, l], i) => {
  const x = M + i * 4.1;
  s.addText(v, { x, y: TOP + 0.05, w: 3.9, h: 0.8, fontSize: 38, bold: true, color: C.accent2, margin: 0, isTextBox: true });
  s.addText(l, { x, y: TOP + 0.85, w: 3.9, h: 0.4, fontSize: 13, color: C.accent3, margin: 0, isTextBox: true });
});
carte(s, M, TOP + 1.6, 5.95, 3.1, "À trancher avec SURYA",
  "Erreurs de l'Excel corrigées dans l'outil (4 statuts changent sur l'exemple de l'Excel), questions de méthode (ventilation mécanique, toiture, « Aucun »), type des alertes AL / VA, matrice usagers.\n→ document « Points à trancher » (8 pages).");
carte(s, M + 6.15, TOP + 1.6, 5.95, 3.1, "Prochaines étapes",
  "Charte graphique ACTEE (outil et documents).\nBase de données (Supabase) : comptes, audits enregistrés, questionnaire en ligne réel.\nPhotos normées dans les fiches.\nRattachement au diagnostic confort d'été global.", { couleurTitre: C.accent1 });
note(s, "La maquette est fiable sur la logique de calcul ; les décisions qui restent sont des choix de méthode, à prendre avec SURYA. Ensuite : charte ACTEE, base de données, puis montée en charge.");

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("écrit", OUT);
})();
