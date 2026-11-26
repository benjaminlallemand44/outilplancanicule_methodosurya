"""Présentation de l'outil (charte ACTEE), avec les captures d'écran de l'application.

    python docs/presentation/generer_presentation_outil.py <présentation ACTEE servant de gabarit> <sortie.pptx>

Mêmes mises en page et mêmes fonctions que ``generer_points_a_trancher.py``. Les captures sont dans
``docs/presentation/captures`` : application lancée en local avec l'école type du Sud (exemple fictif) et,
pour la liste des audits, un faux serveur Supabase (``tests/faux_supabase.py``) avec des établissements fictifs.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generer_points_a_trancher import (BLANC, NOIR, bandeau_methode, boite, ecrire, mise_en_page, notes,  # noqa: E402
                                       vider, zone)

CAPTURES = Path(__file__).resolve().parent / "captures"
GRIS = RGBColor(0x9A, 0xA3, 0x9A)
HAUT, BAS = 1.85, 6.55  # zone de contenu sous le titre, au-dessus du pied de page du gabarit


def retirer(slide, idx):
    for ph in list(slide.placeholders):
        if ph.placeholder_format.idx == idx:
            ph._element.getparent().remove(ph._element)


def image(slide, nom, x, y, w=None, h=None):
    """Capture posée avec un filet gris ; on donne la largeur ou la hauteur (proportions conservées)."""
    chemin = CAPTURES / f"{nom}.jpg"
    lx, ly = Image.open(chemin).size
    if w is None:
        w = h * lx / ly
    h = w * ly / lx
    pic = slide.shapes.add_picture(str(chemin), Inches(x), Inches(y), Inches(w), Inches(h))
    pic.line.color.rgb = GRIS
    pic.line.width = Pt(0.75)
    return w, h


def texte(slide, x, y, w, h, paras, taille=13):
    """Bloc de texte : paras = liste de (texte, gras) ou de textes ; « ■ » pour les puces de niveau 1."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for k, p in enumerate(paras):
        t, gras = p if isinstance(p, tuple) else (p, False)
        para = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
        para.space_after = Pt(7)
        r = para.add_run()
        r.text = t
        r.font.size = Pt(taille)
        r.font.bold = gras
        r.font.color.rgb = NOIR
        r.font.name = "Schibsted Grotesk Bold" if gras else "Schibsted Grotesk Medium"
    return tb


def legende(slide, x, y, w, t):
    texte(slide, x, y, w, 0.3, [(t, True)], taille=11)


def diapo(prs, titre):
    s = prs.slides.add_slide(mise_en_page(prs, "Tableau Seul"))
    ecrire(zone(s, 20).text_frame, [titre])
    retirer(s, 11)
    return s


# ------------------------------------------------------------------ gabarits de diapositives
def une_capture(prs, titre, nom, paras, note=None, larg=8.0):
    s = diapo(prs, titre)
    _, h = image(s, nom, 0.56, HAUT, w=larg)
    texte(s, 0.56 + larg + 0.35, HAUT, 12.77 - (0.56 + larg + 0.35), BAS - HAUT, paras)
    notes(s, note)
    return s


def deux_captures(prs, titre, gauche, droite, paras, note=None):
    s = diapo(prs, titre)
    w = 5.95
    hs = []
    for (nom, leg), x in ((gauche, 0.56), (droite, 0.56 + w + 0.3)):
        _, h = image(s, nom, x, HAUT + 0.35, w=w)
        legende(s, x, HAUT, w, leg)
        hs.append(h)
    texte(s, 0.56, HAUT + 0.35 + max(hs) + 0.2, 12.2, 1.2, paras, taille=12)
    notes(s, note)
    return s


def pages(prs, titre, noms, paras, note=None):
    s = diapo(prs, titre)
    x = 0.56
    for nom, leg in noms:
        w, _ = image(s, nom, x, HAUT + 0.35, h=BAS - HAUT - 0.35)
        legende(s, x, HAUT, w + 0.2, leg)
        x += w + 0.25
    texte(s, x + 0.15, HAUT + 0.35, 12.77 - x - 0.15, BAS - HAUT, paras)
    notes(s, note)
    return s


def partie(prs, layout, num, titre, desc):
    s = prs.slides.add_slide(mise_en_page(prs, layout))
    ecrire(zone(s, 1).text_frame, [titre])
    couleur = BLANC if layout == "Partie 1" else NOIR  # texte blanc seulement sur le bleu
    boite(s, 0.55, 0.39, 2.76, num, 96, "Bitter Black", couleur)
    boite(s, 3.58, 3.7, 8.6, desc, 20, "Schibsted Grotesk Medium", couleur)


def chiffres(prs, titre, sous, paras, trois, note=None):
    s = prs.slides.add_slide(mise_en_page(prs, "Texte + 3 Chiffres"))
    ecrire(zone(s, 14).text_frame, [titre])
    ecrire(zone(s, 15).text_frame, [sous])
    ecrire(zone(s, 27).text_frame, paras)
    for (n, lib), (i_n, i_l) in zip(trois, ((21, 22), (25, 26), (23, 24))):
        ecrire(zone(s, i_n).text_frame, [n])
        ecrire(zone(s, i_l).text_frame, [lib])
    notes(s, note)


def colonne(prs, titre, sous, paras, note=None):
    s = prs.slides.add_slide(mise_en_page(prs, "Texte 1 colonne"))
    ecrire(zone(s, 14).text_frame, [titre])
    ecrire(zone(s, 15).text_frame, [sous])
    ecrire(zone(s, 16).text_frame, paras)
    notes(s, note)


# ------------------------------------------------------------------ contenu
def construire(gabarit, sortie):
    prs = Presentation(gabarit)
    vider(prs)

    s = prs.slides.add_slide(mise_en_page(prs, "Titre"))
    ecrire(zone(s, 11).text_frame, ["L’outil d’audit de faisabilité — méthode SURYA"])
    ecrire(zone(s, 1).text_frame, ["Parcours, documents, passage à l’action et données"])
    ecrire(zone(s, 15).text_frame, ["Maquette de test · novembre 2026", "ACTEE"])
    bandeau_methode(s)
    notes(s, "Outil en ligne : https://outilplancanicule.streamlit.app/ — les captures montrent l’école type du Sud, "
             "un exemple fictif livré avec l’outil.")

    chiffres(prs, "De l’Excel à une application guidée", "Même logique de calcul, saisie et documents plus simples", [
        "Les règles et alertes de l’Excel de la méthode SURYA sont reprises dans un moteur de calcul : mêmes statuts, "
        "vérifiés sur des milliers de cas tirés au hasard.",
        "Un parcours guidé remplace les onglets : seules les questions utiles s’affichent, les manques sont signalés "
        "sans bloquer.",
        "À la fin : des documents prêts à diffuser, et désormais un passage en travaux."],
        [("134", "règles et alertes reprises de l’Excel"), ("0", "écart avec l’Excel corrigé (3 000 cas)"),
         ("3", "parcours")],
        "0 écart : l’Excel recalculé avec ses références réparées (catégorie A des points à trancher) donne exactement "
        "les statuts de l’outil.")

    s = prs.slides.add_slide(mise_en_page(prs, "Sommaire"))
    ecrire(zone(s, 1).text_frame, ["Sommaire"])
    ecrire(zone(s, 16).text_frame, ["1. Les parcours et la saisie", "2. Les documents", "3. Passer à l’action",
                                    "4. Comptes et données", "Fiabilité et suites"], sans_puce=True)

    # 1. parcours et saisie
    partie(prs, "Partie 1", "1.", "Les parcours et la saisie",
           "Trois parcours selon ce que l’on veut produire, une saisie guidée, des statuts calculés en direct.")
    une_capture(prs, "Au départ : trois parcours", "s01b_parcours", [
        ("Résultats de faisabilité", True), "L’équivalent de l’Excel : 6 étapes, jusqu’au tableau des statuts et au PDF "
        "des résultats.",
        ("Diagnostic complet", True), "Même saisie, plus l’identification, les observations et les questionnaires "
        "usagers : 8 étapes, jusqu’au compte rendu.",
        ("Passage en travaux", True), "Depuis l’audit en cours ou un diagnostic réalisé hors méthode SURYA.",
        "On passe d’un parcours à l’autre sans perdre la saisie."])
    deux_captures(prs, "Deux façons de remplir : pas à pas ou par onglets",
                  ("s04_batiment", "Bâtiment, pas à pas"), ("s06_local_theme1", "Local, premier thème"), [
                      "Pas à pas : un bloc par écran, avec « Suivant » — idéal pendant la visite. Fiches à onglets : tous les "
                      "thèmes accessibles librement — idéal pour reprendre une saisie. Les questions conditionnelles "
                      "n’apparaissent que lorsqu’elles ont un objet."])
    une_capture(prs, "Saisir un local : les statuts se calculent en direct", "s07_local_murs", [
        "Murs extérieurs : orientation, position des baies, retrait du vitrage, débord, menuiseries (4 murs au plus).",
        "À droite, les statuts du local se mettent à jour à chaque réponse.",
        "Une donnée manquante sur la règle retenue donne « Sous réserve », et le compte rendu dit quoi compléter."])
    une_capture(prs, "Une fiche par local, un coup d’œil sur l’avancement", "s05_locaux_liste", [
        "Sur chaque carte : le type de local, l’état de la saisie (complet ou nombre de réponses manquantes) et le "
        "nombre de solutions par statut.",
        "Modifier, dupliquer un local semblable, supprimer.",
        "Photos par local, par espace et pour le bâtiment : prises au téléphone ou chargées, visages floutés "
        "automatiquement."])
    une_capture(prs, "Les façades, décrites une fois pour tous les locaux", "s08_facades", [
        "L’étape vient après les locaux et les espaces : l’outil coche d’office les façades qu’ils citent.",
        "Quatre questions par façade : alignement sur la rue, accès, obstacles, support des protections.",
        "Les règles des protections solaires et de l’ombrage adossé les lisent pour chaque local."])
    deux_captures(prs, "Diagnostic complet : le ressenti des usagers",
                  ("s17_usager", "Le questionnaire en ligne, côté enseignant"),
                  ("s09b_synthese", "Synthèse et croisement avec l’audit"), [
                      "Questionnaire confort estival (24 questions, 5 minutes), anonyme, par lien en ligne ; ou import d’un "
                      "fichier, ou saisie d’un questionnaire papier. Synthèse pour l’établissement et matrice qui croise "
                      "le ressenti avec les préconisations (proposition à valider, catégorie E des points à trancher)."])
    une_capture(prs, "Avant les documents : une vérification, sans blocage", "s10_verification", [
        "Identification, bâtiment, façades citées, chaque local et chaque espace : réponses manquantes et solutions "
        "« Sous réserve » faute de données.",
        "On peut générer les documents à tout moment : les manques y sont signalés."])

    # 2. documents
    partie(prs, "Partie 2", "2.", "Les documents",
           "Un compte rendu orienté décision, le PDF des résultats et un export pour Excel.")
    une_capture(prs, "Les documents, en un clic", "s11_documents", [
        ("Compte rendu complet (PDF)", True), "Synthèse en une page, bâtiment, ressenti des usagers, pistes d’action ; "
        "le détail passe en annexes.",
        ("Résultats (PDF)", True), "2 à 3 pages : statuts, alertes, données manquantes.",
        ("Tableau (CSV)", True), "Une ligne par solution et par local, pour Excel.",
        "En bas de l’écran : « Passer à l’action » ouvre le passage en travaux."])
    pages(prs, "Le compte rendu, orienté décision",
          [("cr-01", "Couverture"), ("cr-02", "Synthèse en une page"), ("cr-03", "Plan simplifié")], [
              "La synthèse classe les solutions en trois étapes : dès maintenant, petits travaux, travaux sur le "
              "bâtiment.",
              "Le plan simplifié situe chaque local par niveau, avec ses solutions et ses côtés exposés.",
              "Ces choix sont des propositions de l’outil (catégorie G des points à trancher)."])

    # 3. passer à l'action
    partie(prs, "Partie 3", "3.", "Passer à l’action",
           "Du diagnostic aux consultations : pré-programme, accompagnement, cahiers des charges.")
    deux_captures(prs, "Pré-programme et accompagnement",
                  ("s13_travaux_1", "1. Pré-programme"), ("s14_travaux_2", "2. Accompagnement"), [
                      "Le pré-programme traduit le diagnostic en opérations, avec un motif pour chacune : l’auditeur retient "
                      "ou retire, puis présente le PDF aux élus. L’accompagnement indique quand une maîtrise d’œuvre est "
                      "recommandée et aide à trouver une ingénierie du territoire."])
    deux_captures(prs, "Mise en œuvre et consultations",
                  ("s15_travaux_3", "3. Mise en œuvre"), ("s16_travaux_4", "4. Consultations"), [
                      "Cahier des charges de maîtrise d’œuvre, ou fiches travaux si l’on s’en passe. Les CCTP des "
                      "prestataires et des travaux sont pré-remplis avec les données du diagnostic (Word, à relire). Un "
                      "diagnostic existant peut aussi être reporté ; sa lecture par IA est prévue pour février 2027."])

    # 4. comptes et données
    partie(prs, "Partie 4", "4.", "Comptes et données",
           "Sans compte, rien n’est enregistré. Avec un compte, les audits sont conservés et retrouvés.")
    deux_captures(prs, "Plusieurs audits par auditeur",
                  ("s02_audits", "Vos audits enregistrés"), ("s02b_recherche", "Recherche par nom ou par code"), [
                      "Inscription ouverte à tous. Chaque auditeur ne voit que ses audits. Enregistrement à chaque étape ; "
                      "« Nouvel audit » garde l’audit en cours dans la liste. Date de suppression affichée, rappel un mois "
                      "avant."],
                  "Captures faites avec des établissements fictifs.")
    colonne(prs, "Où sont les données, et combien de temps", "Maquette de test", [
        ("Base Supabase hébergée à Paris ; application sur Streamlit Community Cloud.", 0),
        ("Sans compte : rien n’est enregistré, export de la saisie (JSON ou ZIP avec photos).", 0),
        ("Audits et photos : 3 ans après la dernière modification ; ouvrir un audit le conserve 3 ans de plus.", 0),
        ("Questionnaire en ligne ouvert 90 jours ; réponses brutes conservées 12 mois.", 0),
        ("Comptes inactifs supprimés après 3 ans. Purge automatique chaque semaine, des seules données échues.", 0),
        ("Avant une diffusion institutionnelle : hébergement maîtrisé et notice RGPD.", 0)])

    chiffres(prs, "Fiabilité et suites", "Où en est la maquette", [
        "Deux campagnes de tests : la n° 1 a corrigé 36 anomalies sur 37 ; la n° 2 (26/11) confirme le moteur et "
        "relève des défauts dans les fonctions récentes (photos, imports, passage en travaux), en cours de correction.",
        "À venir : décisions de méthode (réunions points à trancher), test sur une école réelle, base de coûts du "
        "passage en travaux, lecture des diagnostics par IA (février 2027)."],
        [("976", "tests automatiques"), ("0", "écart avec l’Excel corrigé"), ("2", "campagnes de tests")])

    s = prs.slides.add_slide(mise_en_page(prs, "Fin"))
    ecrire(zone(s, 1).text_frame, ["Merci pour votre attention !"])
    prs.save(sortie)
    return len(prs.slides)


if __name__ == "__main__":
    print(construire(sys.argv[1], sys.argv[2]), "slides")
