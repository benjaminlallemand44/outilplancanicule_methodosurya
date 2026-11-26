"""PowerPoint de la réunion « Points à trancher », sur le gabarit officiel ACTEE.

    python docs/presentation/generer_points_a_trancher.py <présentation ACTEE servant de gabarit> <sortie.pptx>

Le gabarit est une présentation faite avec le modèle `Modele_Powerpoint-ACTEE.potx` (ses mises en page :
Titre, Sommaire, Partie 1 à 4, Tableau Seul, Texte + 3 Chiffres, Texte 1 colonne, Fin). Ses slides sont
retirées ; on garde le masque, les mises en page, les logos ACTEE + FNCCR et CEE.
"""
from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

BLEU = RGBColor(0x09, 0x15, 0xA6)     # couleurs du modèle PowerPoint ACTEE
BLANC = RGBColor(0xFF, 0xFF, 0xFF)
NOIR = RGBColor(0x00, 0x00, 0x00)
ALT = RGBColor(0xEE, 0xF0, 0xFB)
ORANGE = RGBColor(0xFF, 0x53, 0x00)

ENTETE = ["N°", "Question", "Proposition", "Décision"]
LARGEURS = [0.75, 4.95, 4.95, 1.55]

SLIDES = [
    ("titre", {}),
    ("chiffres", {
        "titre": "Ce que nous devons décider",
        "sous": "Une ligne par point, une décision par ligne",
        "texte": ["Pour chaque point : la question, la proposition (ce que fait l’outil aujourd’hui, ou ce que nous "
                  "recommandons) et une colonne « Décision » à remplir en séance.",
                  "Trois réponses possibles : valider, modifier, ou reporter pour instruction par SURYA.",
                  "Les points mineurs sont validés par écrit après la réunion."],
        "chiffres": [("49", "points relevés (A à G)"), ("4", "statuts changent"), ("3", "réponses possibles")],
        "notes": "49 points relevés en portant l’Excel, la méthode SURYA et le questionnaire dans l’outil. 4 statuts de "
                 "l’exemple de l’Excel changent avec les corrections : l’Excel réparé donne les résultats de l’outil."}),
    ("sommaire", {"lignes": ["Réunion 1 (après un temps de lecture du document)",
                             "A. Corrections de l’Excel · 5 min",
                             "B. Règles de la méthode SURYA et alertes, avec les questions F issues des tests · 35 min",
                             "C. Points mineurs · 5 min",
                             "Réunion 2 (points en suspens et suite)",
                             "D. Écarts entre l’Excel et le document de la méthode SURYA",
                             "E. Questionnaire usagers",
                             "G. Compte rendu orienté décision",
                             "L’outil : décisions et suites"]}),
    ("partie", {"num": "A.", "titre": "Corrections de l’Excel", "layout": "Partie 1",
                "desc": "Des références cassées dans l’Excel, corrigées dans l’outil. Elles ne font pas débat, mais elles "
                        "changent des résultats."}),
    ("tableau", {"titre": "Erreurs de l’Excel corrigées dans l’outil", "entete": ["N°", "Constat", "Proposition", "Décision"],
                 "lignes": [
                     ("A1", "Murs 2 à 4 lus une ligne trop bas : seul le mur 1 compte", "Les 4 murs lus correctement : valider"),
                     ("A2", "MEX-17 (commande des baies en plafond) en #REF! : règle FT-7 cassée", "FT-7 teste « ni électrique ni automatique » : valider"),
                     ("A3", "BA-18 (débit de ventilation) sans ligne de saisie : VM-7, 9 et 10 ignorées", "Question ajoutée en m³/h ; débit inconnu, « Sous réserve » : valider"),
                     ("A4", "Valeur pile sur un seuil ; surface ou hauteur égale à 0", "Arrondi avant comparaison ; valeur nulle, « Sous réserve » : valider")],
                 "notes": "Sur l’exemple de l’Excel, 4 statuts changent (dus à A1 et A2) : Classe CM1, ventilation naturelle "
                          "nocturne et protections horizontales ; salle de motricité, protections horizontales ; salle de classe, "
                          "fenêtres de toit. Recalculé avec ses références réparées, l’Excel donne exactement les résultats de "
                          "l’outil (vérifié sur 3 000 cas tirés au hasard)."}),
    ("partie", {"num": "B.", "titre": "Règles de la méthode SURYA et alertes", "layout": "Partie 2",
                "desc": "Le libellé d’une règle et sa formule divergent, ou un cas n’est pas prévu. Avec les questions F "
                        "issues des tests, rangées par thème. Ce sont les décisions qui changent des statuts."}),
    ("tableau", {"titre": "Ventilation et brasseurs d’air", "lignes": [
        ("B1", "VN-7 « orientations différentes » : la formule compte les murs, pas les orientations (deux murs « S » suffisent)", "Suivre le libellé : compter les orientations distinctes, condition d’un vrai balayage"),
        ("F1", "Ventilation mécanique : VM-9 n’est jamais retenue, VM-11 « Recommandé » n’est jamais atteinte", "Placer VM-9 avant VM-7 ; SURYA précise quand la ventilation mécanique nocturne est « Recommandé »"),
        ("B5", "Fenêtres de toit et verrières partagent les mêmes réponses (MEX-16, 18, 19)", "Garder (cas rare) ; dédoubler les questions si les visites le demandent"),
        ("F10", "Équation des brasseurs : les bornes 0,2 et 0,4 sont-elles incluses ?", "À confirmer par SURYA ; l’Excel les exclut")],
        "notes": "B1 : l’exemple de l’Excel est dans ce cas (Classe CM1, quatre murs saisis au sud)."}),
    ("tableau", {"titre": "Toiture", "lignes": [
        ("B2", "Cas sans statut possible : toiture à pentes sans combles, toiture « Autre », isolation « Autre »", "Traiter les pentes sans combles comme les rampants ; sinon « Sous réserve » assumé"),
        ("B3, F3", "Toiture-terrasse et combles à la fois : seul le bloc terrasse est évalué", "Garder la priorité à la terrasse et signaler les combles dans la fiche"),
        ("B4", "Isolant insuffisant : « Recommandé » en combles perdus, « Sous réserve » en rampants et en terrasse", "Harmoniser à « Recommandé » sans obstacle ; utiliser ou retirer B-23, B-25, B-27"),
        ("F9", "CP-6 cite la période de construction sans l’utiliser (suspicion d’amiante)", "Déduire la suspicion d’une construction d’avant 1997, comme PR-AL3")],
        "notes": "B2 : aujourd’hui l’outil affiche « configuration non prévue par les règles » pour ces cas."}),
    ("tableau", {"titre": "Protections solaires et façades", "lignes": [
        ("B8", "Baies au nu extérieur avec débord : PV-8 donne « Recommandé », mais son libellé parle de tunnel", "À arbitrer par SURYA : règle dédiée, ou libellé corrigé"),
        ("B9", "Sous-sol traité comme un étage (PV-5, PH-6, PH-8)", "Assimiler le sous-sol au rez-de-chaussée pour ces règles"),
        ("B10", "Façade non décrite : les règles PV, PH et OA qui la lisent restent indéterminées", "Garder un avertissement non bloquant, à l’étape Vérification"),
        ("B11", "Alerte de mutualisation OA-AL1 : n’importe quel local du rez-de-chaussée la déclenche", "Suffisant pour l’instant ; rattacher locaux et espaces plus tard")]}),
    ("tableau", {"titre": "Règles générales de calcul et de saisie", "lignes": [
        ("B7", "Une règle indéterminée masque les suivantes (PH-1 inconnue cache PH-2, pourtant certaine)", "Garder ce principe prudent, conforme à la méthode SURYA"),
        ("B6", "« Aucun » peut être coché avec d’autres options (8 questions, dont E-20)", "Rendre « Aucun » exclusif dans la saisie"),
        ("B12", "Occupation : seuls bureaux et classes ; EX-AL divise l’ombre par l’effectif, adultes compris", "Étendre aux autres locaux occupés ; relever l’effectif d’enfants à part")]}),
    ("tableau", {"titre": "Alertes : quand les déclencher", "lignes": [
        ("B13", "BR-AL est « toujours vraie », même quand les brasseurs sont non recommandés", "L’afficher seulement si la solution est envisagée (Recommandé, À optimiser, Sous réserve)"),
        ("F4", "Alertes de l’ombrage adossé muettes quand le « Sous réserve » vient d’une donnée manquante", "Les déclencher aussi, par prudence"),
        ("F5", "EX-AL indéterminée (effectif ou surface d’ombre manquant) : ni affichée ni signalée", "La signaler « à vérifier »"),
        ("F6", "VV-AL ignore les puits de lumière et atriums du bloc VV", "Étendre l’alerte à ces cas")]}),
    ("partie", {"num": "C.", "titre": "Points mineurs", "layout": "Partie 3",
                "desc": "Cohérence des libellés et questions sans effet. Proposition : les valider par écrit avec SURYA."}),
    ("colonne", {"titre": "À valider par écrit après la réunion", "sous": "Points mineurs",
                 "paras": [("C1 · B-07 (local de repli plus frais) n’alimente aucune règle : la marquer « info » ou l’utiliser.", 1),
                           ("C2 · Libellés des réponses de MEX-17 à aligner sur la liste déroulante.", 1),
                           ("C3 · Libellé de CO-1 : un seul des quatre intitulés cités existe dans L-02.", 1),
                           ("C4 · Deux questions portent le code MEX-25 : renuméroter.", 1),
                           ("C5 · Trous de numérotation : confirmer qu’aucune question du carnet de visite ne manque.", 1),
                           ("C6 · 4 murs par local au maximum : confirmer.", 1),
                           ("C7 · « Non évalué » sur F-05 seulement : l’étendre à F-02, F-03 et F-04.", 1)],
                 "notes": "Proposition : envoyer ce tableau à SURYA après la réunion, avec un délai de retour à fixer ensemble."}),
    ("partie", {"num": "D.", "titre": "Écarts entre l’Excel et la méthode SURYA", "layout": "Partie 4",
                "desc": "Ce que le document prévoit et que l’Excel ne fait pas, ou l’inverse."}),
    ("tableau", {"titre": "D1 · Alertes : maîtrise d’œuvre ou validation ponctuelle",
                 "entete": ["Type proposé", "Alertes", "Objet", "Décision"], "largeurs": [2.6, 3.6, 4.4, 1.6],
                 "lignes": [
                     ("AL : étude de maîtrise d’œuvre", "VV-AL, OA-AL2, OA-AL3, PR-AL1, PR-AL2, PR-AL3", "Véranda, prise au vent et feu de la toile, avis de l’ABF, charpente du préau, amiante"),
                     ("VA : validation ponctuelle", "BR-AL, VN-AL1", "Électricité et fixation des brasseurs ; grilles ou ventelles pour ventiler la nuit"),
                     ("Point d’attention", "VN-AL2, FT-AL, EX-AL, OA-AL1, PR-AL4", "Pluie, fenêtres de toit, ombre insuffisante, mutualisation, préau petit"),
                     ("Nouvelle alerte AL ?", "PV-3, PH-5, FT-5, VV-6, OA-5, OC-3", "Patrimoine (monument historique, abords) : ajouter une alerte AL. Proposition : oui")],
                 "notes": "L’Excel ne type pas ses alertes. L’outil les classe d’après le § I.e de la méthode SURYA : une alerte AL "
                          "fait passer la solution en « À valider avant de consulter ». Deux décisions : valider ce classement ; "
                          "ajouter l’alerte patrimoine."}),
    ("tableau", {"titre": "Autres écarts entre l’Excel et le document", "lignes": [
        ("D2", "Photos « normées obligatoires » (§ I.c) : l’outil les recueille, avec une liste non bloquante", "Quelles questions exigent une photo ? Proposition : vue d’ensemble, baies, plafond, façade, ombrages"),
        ("D3", "CO-1 vise un bureau « occupé en continu », ce qui n’est jamais relevé", "Ajouter la question, ou retirer « en continu » du libellé"),
        ("D4", "CQ-1 cite les réfrigérateurs, absents de la question L-10", "Ajouter « Réfrigérateurs » à L-10"),
        ("D5", "23 questions à choix sans option « Non évalué », que demande la règle du doute (§ I.f)", "Ajouter « Non évalué » à ces questions de la grille de visite"),
        ("F2", "Règles « aucune baie » (PV-0, PH-0, FS-0) dans l’Excel seulement", "Les reporter dans le document de la méthode SURYA")]}),
    ("partie", {"num": "E.", "titre": "Questionnaire usagers", "layout": "Partie 1",
                "desc": "La méthode SURYA prévoit une matrice ressenti / préconisations et un indicateur de cohérence, sans les "
                        "définir : l’outil fait une proposition."}),
    ("tableau", {"titre": "Matrice ressenti / préconisations (proposition)",
                 "entete": ["N°", "Proposition de l’outil", "À décider", "Décision"], "lignes": [
        ("E1", "Ressenti « signalé » à partir de 30 % des répondants ; 3 réponses au minimum ; 8 croisements M1 à M8", "Valider le principe, les seuils et les 8 croisements (document joint)"),
        ("E1", "Indicateur de cohérence : part des croisements évalués qui ne sont pas « À vérifier »", "Valider ; « Non corroboré » n’est pas une incohérence"),
        ("F7", "Un « Sous réserve » dû à une donnée manquante compte comme une préconisation", "L’exclure du croisement"),
        ("F8", "M8 (équipements) conclut « À vérifier » dès qu’un seul usager en déclare un", "Appliquer aussi le seuil de 30 %")],
        "notes": "Sur l’exemple fictif (14 réponses) : 7 croisements évalués, 1 « À vérifier » (fenêtres fermées la nuit "
                 "alors que la ventilation naturelle est recommandée) ; indicateur de cohérence 86 %."}),
    ("tableau", {"titre": "Contenu du questionnaire", "lignes": [
        ("E2", "Question ouverte annoncée par la méthode SURYA mais absente", "Q24 « Remarques libres » ajoutée : confirmer"),
        ("E4", "Questions « si vous en avez » (Q12 à Q15, Q17)", "Posées seulement si elles ont un objet : confirmer"),
        ("E5", "Q20 n’admet qu’un seul équipement de rafraîchissement", "Passer en choix multiple"),
        ("E6", "Public : adultes seulement (échelle ISO à 7 points) ?", "Adultes pour l’instant ; version élèves à instruire"),
        ("E3", "Étage et orientation (Q2, Q3) moins détaillés que la grille", "Garder : sans incidence tant que la synthèse est globale")]}),
    ("partie", {"num": "G.", "titre": "Compte rendu orienté décision", "layout": "Partie 2",
                "desc": "Des propositions de l’outil, absentes de la méthode SURYA : ordre de mise en œuvre, synthèse en une page, "
                        "plan simplifié."}),
    ("colonne", {"titre": "Ordre de mise en œuvre en trois étapes", "sous": "De la plus simple à la plus lourde",
                 "paras": [("1. Dès maintenant : usages, réglages, remise en état. Par l’exploitant ou en régie, coût faible, effet dès l’été.", 0),
                           ("2. Petits travaux : brasseurs, films solaires, LED, grilles de ventilation, ombrage de la cour. Pendant les vacances d’été.", 0),
                           ("3. Travaux sur le bâtiment : protections extérieures, toiture, préau, ombrage adossé. Souvent avec une maîtrise d’œuvre.", 0),
                           ("À décider :", 0),
                           ("Valider les trois étapes et le classement des solutions.", 1),
                           ("Plantations (étape 2, effet sur plusieurs années) : à lancer tôt ? Stores extérieurs : étape 2 s’ils se posent sans maîtrise d’œuvre ?", 1),
                           ("Classement dans une étape : l’effectif seul, ou aussi le public sensible, l’exposition et le ressenti des usagers ?", 1)],
                 "notes": "Les coûts ne sont pas encore donnés : ils viendront d’une base de coûts, à brancher dans le module de "
                          "passage en travaux."}),
    ("tableau", {"titre": "Synthèse en une page et plan simplifié", "lignes": [
        ("G2", "Synthèse en une page : 7 solutions principales par étape, 3 à valider, 3 lieux cités pour chacune", "Valider"),
        ("G3", "Plan simplifié : schéma par niveau (surface, solutions à engager, côtés exposés)", "Valider ; plan réel plus tard, par import d’un plan")],
        "notes": "G2 et G3 sont visibles dans le compte rendu complet de l’école type du Sud, pages 2 et 3."}),
    ("partie", {"num": "", "titre": "L’outil : décisions et suites", "layout": "Partie 3",
                "desc": "Ce qui est déjà décidé pour la maquette, et qui fait quoi."}),
    ("colonne", {"titre": "Ce qui est décidé, ce qui reste à décider", "sous": "L’outil",
                 "paras": [("Décidé", 0),
                           ("Maquette de test : Streamlit Cloud et base Supabase hébergée à Paris ; inscriptions ouvertes à tous.", 1),
                           ("Conservation : audits et photos 3 ans après la dernière modification, questionnaire ouvert 90 jours, réponses brutes 12 mois, comptes inactifs 3 ans. Purge automatique chaque semaine.", 1),
                           ("Passage en travaux : un 3ᵉ parcours après le diagnostic. Lecture des rapports par IA : février 2027.", 1),
                           ("Avant toute diffusion institutionnelle", 0),
                           ("Un hébergement maîtrisé (Streamlit Cloud ajoute ses propres traceurs d’audience) et une notice RGPD.", 1)]}),
    ("tableau", {"titre": "Qui fait quoi", "entete": ["Action", "Qui", "Quand"], "largeurs": [7.6, 2.9, 1.7], "lignes": [
        ("Mettre à jour le document de la méthode SURYA (décisions B, D et F2)", "SURYA", "[date]"),
        ("Appliquer les décisions dans l’outil et refaire la campagne de tests", "[ACTEE]", "[date]"),
        ("Valider les points mineurs par écrit", "SURYA, ACTEE", "[date]"),
        ("Base de coûts et relecture des CCTP du passage en travaux", "[équipe passage en travaux]", "[date]"),
        ("Tester l’outil sur une école réelle", "[à définir]", "[date]")],
        "notes": "Responsables et dates à fixer en séance."}),
    ("fin", {}),
]


def vider(prs):
    ids = prs.slides._sldIdLst
    for sld in list(ids):
        prs.part.drop_rel(sld.rId)
        ids.remove(sld)


def mise_en_page(prs, nom):
    return next(l for l in prs.slide_layouts if l.name.strip() == nom)


def ecrire(tf, paras, taille=None, couleur=None, gras=None, sans_puce=False):
    """Remplace le texte d'un cadre ; ``paras`` : liste de (texte, niveau) ou de textes."""
    tf.clear()
    for k, p in enumerate(paras):
        texte, niveau = p if isinstance(p, tuple) else (p, 0)
        para = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
        para.level = niveau
        if sans_puce:  # pas de numérotation automatique du modèle (les lettres A. à E. sont dans le texte)
            from pptx.oxml.ns import qn
            pPr = para._p.get_or_add_pPr()
            pPr.set("marL", "0")
            pPr.set("indent", "0")
            pPr.insert(0, pPr.makeelement(qn("a:buNone"), {}))
        r = para.add_run()
        r.text = texte
        if taille:
            r.font.size = Pt(taille)
        if couleur is not None:
            r.font.color.rgb = couleur
        if gras is not None:
            r.font.bold = gras


def notes(slide, texte):
    if texte:
        slide.notes_slide.notes_text_frame.text = texte


def zone(slide, idx):
    return next(ph for ph in slide.placeholders if ph.placeholder_format.idx == idx)


def boite(slide, x, y, w, texte, taille, police, couleur=BLANC):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(0.5))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    r = tf.paragraphs[0].add_run()
    r.text = texte
    r.font.size = Pt(taille)
    r.font.name = police
    r.font.color.rgb = couleur
    return tb


def tableau(slide, entete, lignes, largeurs):
    ph = zone(slide, 11)
    n_col = len(entete)
    gf = ph.insert_table(rows=len(lignes) + 1, cols=n_col)
    t = gf.table
    for j, w in enumerate(largeurs):
        t.columns[j].width = Inches(w)
    for i, ligne in enumerate([entete] + [tuple(l) + ("",) * (n_col - len(l)) for l in lignes]):
        for j, texte in enumerate(ligne):
            c = t.cell(i, j)
            c.margin_left = c.margin_right = Inches(0.08)
            c.margin_top = c.margin_bottom = Inches(0.05)
            ecrire(c.text_frame, [texte], taille=14, couleur=BLANC if i == 0 else NOIR, gras=(i == 0))
            c.fill.solid()
            c.fill.fore_color.rgb = BLEU if i == 0 else (ALT if i % 2 == 0 else BLANC)


LOGOS = Path(__file__).resolve().parents[2] / "static" / "logos"


def bandeau_methode(slide):
    """Couverture seulement : logo SURYA, badge Creative Commons et financement CEE (fichiers officiels)."""
    y = 6.85  # axe du bandeau blanc en bas du gabarit
    slide.shapes.add_picture(str(LOGOS / "surya.png"), Inches(3.25), Inches(y - 0.23), width=Inches(1.5))
    slide.shapes.add_picture(str(LOGOS / "cc-by-sa.png"), Inches(4.95), Inches(y - 0.085), width=Inches(1.35))
    for x, w, texte in ((6.4, 2.05, "Méthode SURYA — © 2026 ACTEE et SURYA Ingénierie, licence Creative Commons BY-SA 4.0 prévue (dépôt à venir)"),
                        (8.5, 0.85, "Programme financé par")):
        tb = slide.shapes.add_textbox(Inches(x), Inches(y - 0.25), Inches(w), Inches(0.5))
        tb.text_frame.word_wrap = True
        ecrire(tb.text_frame, [texte], taille=8, couleur=NOIR, sans_puce=True)
    slide.shapes.add_picture(str(LOGOS / "cee.png"), Inches(9.35), Inches(y - 0.21), width=Inches(0.95))


def construire(gabarit, sortie):
    prs = Presentation(gabarit)
    vider(prs)
    for genre, d in SLIDES:
        if genre == "titre":
            s = prs.slides.add_slide(mise_en_page(prs, "Titre"))
            ecrire(zone(s, 11).text_frame, ["Points à trancher — outil méthode SURYA"])
            ecrire(zone(s, 1).text_frame, ["Réunion de décision · audit de faisabilité d’actions d’adaptation, plan "
                                           "rafraîchissement des écoles"])
            ecrire(zone(s, 15).text_frame, ["[Date de la réunion]", "ACTEE"])
            bandeau_methode(s)
            notes(s, "Objet : prendre les décisions de la méthode SURYA qui conditionnent la suite de l’outil. Le document complet "
                     "« Points à trancher » (Word) est joint à l’invitation.")
        elif genre == "sommaire":
            s = prs.slides.add_slide(mise_en_page(prs, "Sommaire"))
            ecrire(zone(s, 1).text_frame, ["Sommaire"])
            ecrire(zone(s, 16).text_frame, d["lignes"], sans_puce=True)
        elif genre == "partie":
            s = prs.slides.add_slide(mise_en_page(prs, d["layout"]))
            ecrire(zone(s, 1).text_frame, [d["titre"]])
            # charte : texte blanc seulement sur le bleu (Partie 1) ; noir sur cyan, orange et lila
            couleur = BLANC if d["layout"] == "Partie 1" else NOIR
            boite(s, 0.55, 0.39, 2.76, d["num"], 96, "Bitter Black", couleur)
            boite(s, 3.58, 3.7, 8.6, d["desc"], 20, "Schibsted Grotesk Medium", couleur)
        elif genre == "tableau":
            s = prs.slides.add_slide(mise_en_page(prs, "Tableau Seul"))
            ecrire(zone(s, 20).text_frame, [d["titre"]])
            tableau(s, d.get("entete", ENTETE), d["lignes"], d.get("largeurs", LARGEURS))
            notes(s, d.get("notes"))
        elif genre == "chiffres":
            s = prs.slides.add_slide(mise_en_page(prs, "Texte + 3 Chiffres"))
            ecrire(zone(s, 14).text_frame, [d["titre"]])
            ecrire(zone(s, 15).text_frame, [d["sous"]])
            ecrire(zone(s, 27).text_frame, d["texte"])
            for (n, lib), (i_n, i_l) in zip(d["chiffres"], ((21, 22), (25, 26), (23, 24))):
                ecrire(zone(s, i_n).text_frame, [n])
                ecrire(zone(s, i_l).text_frame, [lib])
            notes(s, d.get("notes"))
        elif genre == "colonne":
            s = prs.slides.add_slide(mise_en_page(prs, "Texte 1 colonne"))
            ecrire(zone(s, 14).text_frame, [d["titre"]])
            ecrire(zone(s, 15).text_frame, [d["sous"]])
            ecrire(zone(s, 16).text_frame, d["paras"])
            notes(s, d.get("notes"))
        elif genre == "fin":
            s = prs.slides.add_slide(mise_en_page(prs, "Fin"))
            ecrire(zone(s, 1).text_frame, ["Merci pour votre attention !"])
    prs.save(sortie)
    return len(prs.slides)


if __name__ == "__main__":
    print(construire(sys.argv[1], sys.argv[2]), "slides")
