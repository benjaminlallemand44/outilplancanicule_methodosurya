"""Partie F — questionnaire usagers : import CSV, aller-retour, questions conditionnelles, synthèse,
matrice de correspondance (docs/points_a_trancher.md § E1) et partie « Ressenti des usagers » du PDF."""
from __future__ import annotations

import copy
import csv
import re
import io
import json

import pytest

import sorties
from cas_base import RACINE, moteur
from surya import questionnaire as QU
from surya.rapport import generer_pdf

MODELE = (RACINE / "surya" / "exemple_questionnaires.csv").read_bytes()
EXEMPLE = json.loads((RACINE / "surya" / "exemple.json").read_text(encoding="utf-8"))
OPT = {q["code"]: q.get("options") for q in QU.QUESTIONS}


# ------------------------------------------------------------------ import CSV
def test_modele_vide_et_exemple():
    assert QU.lire_csv(QU.modele_csv()) == ([], [])
    reps, av = QU.lire_csv(MODELE)
    assert len(reps) == 14 and av == []


def _csv(lignes, sep=";", entetes=None):
    out = io.StringIO()
    w = csv.writer(out, delimiter=sep)
    w.writerow(entetes or list(lignes[0]))
    for l in lignes:
        w.writerow([l.get(h, "") for h in (entetes or list(lignes[0]))])
    return out.getvalue()


R1 = {"Q1": "Classe 2", "Q4": "Chaude", "Q5": "Inconfortable", "Q11": "Stores intérieurs ; Rideaux", "Q12": "Rarement",
      "Q13": "Elles gênent la ventilation ou l'aération (claquent, bloquent l'ouverture des fenêtres) ; Je n'y pense pas",
      "Q24": "Trop chaud l'après-midi ; « vraiment »"}
ATTENDU_R1 = {"Q1": "Classe 2", "Q4": "Chaude", "Q5": "Inconfortable", "Q11": ["Stores intérieurs", "Rideaux"],
              "Q12": "Rarement",
              "Q13": ["Elles gênent la ventilation ou l'aération (claquent, bloquent l'ouverture des fenêtres)",
                      "Je n'y pense pas"], "Q24": "Trop chaud l'après-midi ; « vraiment »"}


@pytest.mark.parametrize("sep", [";", ","])
@pytest.mark.parametrize("bom", [False, True])
def test_separateurs_et_bom(sep, bom):
    texte = _csv([R1], sep)
    contenu = ("﻿" + texte).encode("utf-8") if bom else texte.encode("utf-8")
    assert QU.lire_csv(contenu) == ([ATTENDU_R1], [])


@pytest.mark.parametrize("forme", ["{c} - {lib}", "{c}. {lib}", "{c}", "{c} {lib}", "{cl}"])
def test_entetes_avec_libelle_separateur_virgule(forme):
    """En-têtes « Q4 - libellé » (export de formulaire en ligne) avec le séparateur « , »."""
    ent = [forme.format(c=q["code"], lib=q["libelle"], cl=q["code"].lower()) for q in QU.QUESTIONS]
    lignes = [{e: R1.get(q["code"], "") for e, q in zip(ent, QU.QUESTIONS)}]
    assert QU.lire_csv(_csv(lignes, ",", ent)) == ([ATTENDU_R1], [])


@pytest.mark.xfail(strict=True, reason="ANO-17 : en-têtes « Q4 - libellé » + séparateur « ; » : le séparateur est "
                                       "déduit à tort de la première ligne (« , » des libellés) ; tout part dans Q1, "
                                       "sans avertissement")
@pytest.mark.parametrize("forme", ["{c} - {lib}", "{c}. {lib}"])
def test_entetes_avec_libelle_separateur_point_virgule(forme):
    ent = [forme.format(c=q["code"], lib=q["libelle"]) for q in QU.QUESTIONS]
    lignes = [{e: R1.get(q["code"], "") for e, q in zip(ent, QU.QUESTIONS)}]
    assert QU.lire_csv(_csv(lignes, ";", ent)) == ([ATTENDU_R1], [])


def test_colonnes_desordre_manquantes():
    ent = ["Q24", "Q13", "horodatage", "Q4", "Q11", "Q12", "Q1", "Q5"]
    r, av = QU.lire_csv(_csv([dict(R1, horodatage="2026-06-01 10:00")], ";", ent))
    assert r == [dict(ATTENDU_R1, horodatage="2026-06-01 10:00")] and av == []


@pytest.mark.xfail(strict=True, reason="ANO-18 : une colonne inconnue (« Commentaire », « Q99 ») est ignorée sans être "
                                       "signalée")
def test_colonne_inconnue_signalee():
    r, av = QU.lire_csv("Q4;Commentaire;Q99\nChaude;rien;x\n")
    assert r == [{"Q4": "Chaude"}] and av


def test_accents_apostrophes_casse():
    texte = ("Q4;Q13;Q18\nTRÈS CHAUDE;Elles gênent la ventilation ou l’aération (claquent, bloquent l’ouverture des "
             "fenêtres);Non, pour des raisons de sécurité (intrusion, nuisibles, pluie…)\n")
    r, av = QU.lire_csv(texte)
    # Q13 est masquée (Q11 absente) mais conservée : voir ANO-19
    assert r[0]["Q4"] == "Très chaude" and r[0]["Q18"] == OPT["Q18"][1] and not av


def test_reponses_hors_liste_signalees():
    r, av = QU.lire_csv("Q4;Q11;Q20\nBrûlante;\"Rideaux ; Parasol\";Oui, un ventilateur d'appoint mobile\n")
    assert r == [{"Q11": ["Rideaux"], "Q20": "Oui, un ventilateur d'appoint mobile"}]
    assert len(av) == 2 and "Brûlante" in av[0] and "Parasol" in av[1]


def test_lignes_vides_fichier_vide_mauvais_fichier():
    assert QU.lire_csv("Q4;Q5\n\n;\nChaude;\n\n") == ([{"Q4": "Chaude"}], [])
    assert QU.lire_csv(b"") == ([], ["Fichier vide."])
    assert QU.lire_csv(b"   \n") == ([], ["Fichier vide."])
    for mauvais in (b"nom,age\nPaul,3\n", "\x00\x01\x02".encode(), b"<html><body>Q4</body></html>"):
        r, av = QU.lire_csv(mauvais)
        assert r == [] and av


@pytest.mark.xfail(strict=True, reason="ANO-26 : plantage (csv.Error non rattrapée) sur un CSV à fins de ligne CR "
                                       "(« CSV Macintosh » d'Excel) ou un fichier binaire renommé en .csv")
@pytest.mark.parametrize("contenu", [b"Q4;Q5\rChaude;Confortable\r", "xlsx", "pdf"])
def test_import_sans_plantage(contenu):
    if contenu == "xlsx":
        contenu = (RACINE / "reference" / "outil_aide_test_methode.xlsx").read_bytes()
    elif contenu == "pdf":
        contenu = (RACINE / "reference" / "questionnaire_confort_v01_2026-11-11.pdf").read_bytes()
    r, av = QU.lire_csv(contenu)
    assert r or av


def test_points_de_suspension_non_reconnus():
    """Observé (mineur, ANO-25) : « ... » au lieu de « … » à l'intérieur d'une option la rend « hors liste »."""
    r, av = QU.lire_csv("Q18\nNon, pour des raisons de sécurité (intrusion, nuisibles, pluie...)\n")
    assert r == [] and av


@pytest.mark.xfail(strict=True, reason="ANO-20 : un CSV enregistré par Excel (« CSV séparateur point-virgule », "
                                       "encodage Windows-1252) perd toutes les réponses accentuées")
def test_csv_excel_windows_1252():
    contenu = QU.vers_csv([{"Q4": "Très chaude", "Q5": "Légèrement inconfortable", "Q8": "Très souvent"}]).encode("cp1252")
    r, av = QU.lire_csv(contenu)
    assert r == [{"Q4": "Très chaude", "Q5": "Légèrement inconfortable", "Q8": "Très souvent"}]


def test_multi_option_avec_virgule_dans_un_csv_virgule():
    """Réponses multiples séparées par « ; » dont une option contient une virgule, dans un CSV « , »."""
    texte = ('Q11,Q13\n"Stores intérieurs","Elles gênent la ventilation ou l\'aération (claquent, bloquent '
             'l\'ouverture des fenêtres) ; Autre"\n')
    r, av = QU.lire_csv(texte)
    assert r[0]["Q13"] == [OPT["Q13"][3], "Autre"] and not av


# ------------------------------------------------------------------ aller-retour
def _reponse_complete(i=0):
    r = {}
    for q in QU.QUESTIONS:
        o = q.get("options")
        if q["type"] == "texte":
            r[q["code"]] = f"Texte {i} ; « guillemets », virgule\net retour"
        elif q["type"] == "choix":
            r[q["code"]] = o[i % len(o)]
        else:
            r[q["code"]] = [o[i % len(o)], o[(i + 2) % len(o)]] if len(o) > 2 else [o[0]]
    return {k: v for k, v in r.items() if QU.visible(k, r)}


def test_aller_retour_usager_csv_import():
    for i in range(7):
        r = dict(_reponse_complete(i), horodatage="2026-06-0%d 10:00" % (i + 1))
        lu, av = QU.lire_csv(QU.vers_csv([r]).encode("utf-8-sig"))
        attendu = {k: (v.strip() if isinstance(v, str) else [o for o in OPT[k] if o in v]) for k, v in r.items()}
        assert lu == [attendu] and av == []


def test_export_reimport_synthese_identique():
    reps = QU.lire_csv(MODELE)[0]
    reps2 = QU.lire_csv(QU.vers_csv(reps).encode("utf-8-sig"))[0]
    assert QU.synthese(reps2) == QU.synthese(reps)
    res = moteur.calculer(EXEMPLE)
    assert QU.matrice(reps2, res) == QU.matrice(reps, res)


# ------------------------------------------------------------------ questions conditionnelles
@pytest.mark.parametrize("r,visibles", [
    ({}, {"Q12": False, "Q13": False, "Q14": False, "Q15": False, "Q17": True}),
    ({"Q11": ["Aucune"]}, {"Q12": False, "Q14": False, "Q15": False}),
    ({"Q11": ["Je ne sais pas"]}, {"Q12": False}),
    ({"Q11": ["Aucune", "Je ne sais pas"]}, {"Q12": False}),
    ({"Q11": ["Rideaux"]}, {"Q12": True, "Q13": False, "Q14": True, "Q15": True}),
    ({"Q11": ["Rideaux"], "Q12": "Rarement"}, {"Q13": True}),
    ({"Q11": ["Rideaux"], "Q12": "Jamais"}, {"Q13": True}),
    ({"Q11": ["Rideaux"], "Q12": "Parfois"}, {"Q13": False}),
    ({"Q16": ["Jamais"]}, {"Q17": True}),
    ({"Q16": ["Avant les cours"]}, {"Q17": True}),
    ({"Q16": ["Avant les cours", "Pendant les cours"]}, {"Q17": False}),
])
def test_visibilite(r, visibles):
    for code, v in visibles.items():
        assert QU.visible(code, r) == v, code


@pytest.mark.xfail(strict=True, reason="ANO-19 : une réponse à une question masquée (Q12 alors que Q11 = Aucune) est "
                                       "conservée à l'import CSV et comptée dans la synthèse et la matrice")
def test_reponse_masquee_ni_conservee_ni_comptee():
    r, _ = QU.lire_csv("Q11;Q12;Q15\nAucune;Jamais;Pas du tout efficaces\n")
    assert "Q12" not in r[0] and "Q15" not in r[0]


def test_reponse_masquee_comptee_dans_la_synthese():
    """Observé : la synthèse compte les réponses masquées présentes dans les données (via l'import)."""
    reps = [{"Q11": ["Aucune"], "Q12": "Jamais"}] * 3
    assert QU.synthese(reps)["indicateurs"]["protections_peu_utilisees"]["sur"] == 3


# ------------------------------------------------------------------ synthèse (jeu construit à la main)
JEU = [
    {"Q4": "Très chaude", "Q5": "Inconfortable", "Q6": "Plus froide", "Q7": "Peu tolérable", "Q8": "Souvent",
     "Q9": "Assez gênant", "Q10": "Souvent", "Q18": "Oui", "Q21": "Très souvent", "Q22": ["Toute la journée"],
     "Q23": "Très gênant", "Q11": ["Stores intérieurs"], "Q12": "Jamais", "Q15": "Peu efficaces", "Q20": "Non"},
    {"Q4": "Chaude", "Q5": "Légèrement inconfortable", "Q6": "Légèrement plus froide", "Q8": "Très souvent",
     "Q9": "Légèrement gênant", "Q10": "Parfois", "Q18": "Non, les fenêtres ne le permettent pas", "Q21": "Souvent",
     "Q22": ["En début d'après-midi"], "Q11": ["Stores intérieurs"], "Q12": "Souvent", "Q15": "Très efficaces"},
    {"Q4": "Ni chaude ni froide", "Q5": "Confortable", "Q6": "Inchangée", "Q8": "Jamais", "Q10": "Jamais",
     "Q18": "Je ne sais pas", "Q21": "Rarement", "Q22": ["Dès l'arrivée le matin"], "Q11": ["Aucune"]},
    {"Q4": "Légèrement chaude", "Q5": "Très inconfortable", "Q8": "Parfois", "Q9": "Extrêmement gênant",
     "Q10": "Très souvent", "Q18": "Non, pour des raisons de sécurité (intrusion, nuisibles, pluie…)", "Q21": "Parfois",
     "Q22": ["En fin de matinée", "En fin d'après-midi"], "Q11": ["Rideaux"], "Q12": "Rarement",
     "Q15": "Je ne sais pas / je ne les utilise pas", "Q20": "Oui, un climatiseur mobile"},
    {"Q4": "Très froide", "Q6": "Beaucoup plus chaude", "Q8": "Très souvent", "Q9": "Très gênant", "Q21": "Jamais",
     "Q24": "RAS"},
    {"Q1": "Bureau"},
]


def test_synthese_recalculee_a_la_main():
    s = QU.synthese(JEU)
    i = s["indicateurs"]
    assert s["repondants"] == 6
    assert i["sensation_moyenne"] == pytest.approx((3 + 2 + 0 + 1 - 3) / 5)          # 0,6
    assert i["preference_moyenne"] == pytest.approx((-2 - 1 + 0 + 3) / 4)           # 0
    assert (i["inconfort"]["nb"], i["inconfort"]["sur"]) == (2, 4)                  # Inconfortable, Très inconf.
    assert (i["peu_tolerable"]["nb"], i["peu_tolerable"]["sur"]) == (1, 1)
    assert (i["trop_chaud_souvent"]["nb"], i["trop_chaud_souvent"]["sur"]) == (2, 5)
    assert (i["soleil_gene"]["nb"], i["soleil_gene"]["sur"]) == (2, 5)              # R1 et R5 (R2 : légèrement)
    assert (i["air_lourd"]["nb"], i["air_lourd"]["sur"]) == (2, 4)
    assert (i["protections_peu_utilisees"]["nb"], i["protections_peu_utilisees"]["sur"]) == (2, 3)
    assert (i["protections_peu_efficaces"]["nb"], i["protections_peu_efficaces"]["sur"]) == (1, 2)  # « je ne sais pas » exclu
    assert (i["fenetres_fermees_nuit"]["nb"], i["fenetres_fermees_nuit"]["sur"]) == (2, 4)
    assert (i["chaleur_matin"]["nb"], i["chaleur_matin"]["sur"]) == (2, 4)
    assert (i["chaleur_apres_midi"]["nb"], i["chaleur_apres_midi"]["sur"]) == (3, 4)
    assert (i["gene_travail"]["nb"], i["gene_travail"]["sur"]) == (1, 1)
    assert s["repartition"]["Q22"]["repondants"] == 4 and s["repartition"]["Q22"]["comptes"]["Toute la journée"] == 1
    assert s["remarques"] == ["RAS"]


def test_synthese_dans_le_pdf_identique():
    d = dict(copy.deepcopy(EXEMPLE), questionnaires=JEU)
    t = " ".join(sorties.texte(generer_pdf(d)).split())
    s = QU.synthese(JEU)["indicateurs"]
    assert "+0.6" in t or "+0,6" in t
    for cle, lib in QU.LIBELLES_INDICATEURS.items():
        v = s[cle]
        if v["part"] is not None:
            assert f"{v['part']:.0%}" in t and re.search(rf"\b{v['nb']} ?/ ?{v['sur']}\b", t), cle
    assert "6 répondant(s)" in t


# ------------------------------------------------------------------ matrice de correspondance (§ E1)
def _res(locaux_statuts, etats=None):
    """Résultat d'audit construit : une liste de {solution: statut} par local."""
    noms = [s["solution"] for s in moteur.calculer({"locaux": [{}]})["locaux"][0]["solutions"]]
    loc = []
    for st in locaux_statuts:
        loc.append({"solutions": [{"solution": n, "statut": st.get(n, moteur.NON_CONCERNE)} for n in noms],
                    "etats": etats or {}})
    return {"locaux": loc, "espaces": []}


PROTEGE_R = {"Protections verticales": moteur.RECOMMANDE}
PROTEGE_NR = {"Protections verticales": moteur.NON_RECOMMANDE, "Films solaires": moteur.EN_PLACE}


def _reps(n_oui, n_non, oui, non):
    return [dict(oui) for _ in range(n_oui)] + [dict(non) for _ in range(n_non)]


def _ligne(m, ident):
    return next(l for l in m["lignes"] if l["id"] == ident)


SOLEIL = ({"Q8": "Souvent", "Q9": "Assez gênant"}, {"Q8": "Jamais"})
AIR = ({"Q10": "Souvent"}, {"Q10": "Rarement"})
MATIN = ({"Q22": ["Dès l'arrivée le matin"]}, {"Q22": ["En fin de matinée"]})
APM = ({"Q22": ["En fin d'après-midi"]}, {"Q22": ["En fin de matinée"]})
INCONF = ({"Q5": "Inconfortable"}, {"Q5": "Confortable"})
NOCT_R = {"Par ventilation naturelle nocturne": moteur.RECOMMANDE}
NOCT_NR = {"Par ventilation naturelle nocturne": moteur.NON_RECOMMANDE,
           "Par ventilation mécanique nocturne": moteur.EN_PLACE,
           "Mise en place de brasseurs d'air plafonniers": moteur.NON_RECOMMANDE}
TOUT_EP = {n: moteur.EN_PLACE for n in ("Protections verticales", "Occupation", "Éclairage")}

MATRICE = [
    # (croisement, réponses (oui, non), nb oui/non, audit, résultat attendu)
    ("M1", SOLEIL, (3, 7), [PROTEGE_R], QU.COHERENT),
    ("M1", SOLEIL, (3, 7), [PROTEGE_NR], QU.A_VERIFIER),
    ("M1", SOLEIL, (2, 8), [PROTEGE_R], QU.NON_CORROBORE),
    ("M1", SOLEIL, (2, 8), [PROTEGE_NR], QU.COHERENT),
    ("M1", SOLEIL, (3, 0), [PROTEGE_R], QU.COHERENT),          # exactement 3 réponses
    ("M1", SOLEIL, (2, 0), [PROTEGE_R], QU.NON_EVALUABLE),     # 2 réponses
    ("M1", SOLEIL, (3, 7), [{}], QU.NON_EVALUABLE),            # aucun local concerné (tout « Non concerné »)
    ("M1", SOLEIL, (3, 7), [], QU.NON_EVALUABLE),              # aucun local
    ("M2", AIR, (3, 7), [NOCT_R], QU.COHERENT),
    ("M2", AIR, (3, 7), [NOCT_NR], QU.A_VERIFIER),
    ("M2", AIR, (1, 9), [NOCT_R], QU.NON_CORROBORE),
    ("M2", AIR, (1, 9), [NOCT_NR], QU.COHERENT),
    ("M3", MATIN, (5, 5), [NOCT_R], QU.COHERENT),
    ("M3", MATIN, (5, 5), [NOCT_NR], QU.A_VERIFIER),
    ("M3", MATIN, (0, 5), [NOCT_R], QU.NON_CORROBORE),
    ("M3", MATIN, (0, 5), [NOCT_NR], QU.COHERENT),
    ("M4", APM, (4, 6), [{"Toiture": moteur.SOUS_RESERVE}], QU.COHERENT),
    ("M4", APM, (4, 6), [PROTEGE_NR], QU.A_VERIFIER),
    ("M4", APM, (2, 8), [PROTEGE_R], QU.NON_CORROBORE),
    ("M4", APM, (2, 8), [PROTEGE_NR], QU.COHERENT),
    ("M5", INCONF, (3, 7), [PROTEGE_R], QU.COHERENT),
    ("M5", INCONF, (3, 7), [TOUT_EP], QU.A_VERIFIER),
    ("M5", INCONF, (2, 8), [PROTEGE_R], QU.NON_CORROBORE),
    ("M5", INCONF, (2, 8), [TOUT_EP], QU.COHERENT),
]


@pytest.mark.parametrize("ident,reps,n,audit,attendu", MATRICE,
                         ids=[f"{m[0]}-{m[2][0]}sur{sum(m[2])}-{m[4]}-{k}" for k, m in enumerate(MATRICE)])
def test_matrice_m1_m5(ident, reps, n, audit, attendu):
    m = QU.matrice(_reps(n[0], n[1], *reps), _res(audit))
    assert _ligne(m, ident)["resultat"] == attendu


def test_seuil_30_pourcent_pile():
    m = QU.matrice(_reps(3, 7, *SOLEIL), _res([PROTEGE_NR]))
    assert _ligne(m, "M1")["usagers"].startswith("30%") and _ligne(m, "M1")["resultat"] == QU.A_VERIFIER
    m = QU.matrice(_reps(29, 71, *SOLEIL), _res([PROTEGE_NR]))
    assert _ligne(m, "M1")["resultat"] == QU.COHERENT


PEU_UTIL = {"Q11": ["Stores intérieurs"], "Q12": "Rarement", "Q13": ["Je n'y pense pas"]}
BIEN_UTIL = {"Q11": ["Stores intérieurs"], "Q12": "Souvent", "Q15": "Très efficaces"}
EN_PLACE_P = {"Films solaires": moteur.EN_PLACE}


@pytest.mark.parametrize("reps,audit,attendu", [
    (_reps(3, 7, PEU_UTIL, BIEN_UTIL), [EN_PLACE_P], QU.A_VERIFIER),
    (_reps(2, 8, PEU_UTIL, BIEN_UTIL), [EN_PLACE_P], QU.COHERENT),
    (_reps(3, 7, PEU_UTIL, BIEN_UTIL), [PROTEGE_R], QU.NON_EVALUABLE),     # aucune protection « En place »
    (_reps(2, 0, PEU_UTIL, BIEN_UTIL), [EN_PLACE_P], QU.NON_EVALUABLE),
], ids=["30% rares", "20% rares", "pas en place", "2 réponses"])
def test_matrice_m6(reps, audit, attendu):
    assert _ligne(QU.matrice(reps, _res(audit)), "M6")["resultat"] == attendu


@pytest.mark.xfail(strict=True, reason="ANO-21 : M6 conclut « À vérifier » sur un indicateur calculé avec moins de 3 "
                                       "réponses (1 seule réponse à Q15), le minimum n'étant vérifié que sur Q12")
def test_matrice_m6_minimum_par_indicateur():
    reps = [dict(BIEN_UTIL) for _ in range(9)]
    for r in reps:
        r.pop("Q15")
    reps.append({"Q11": ["Stores intérieurs"], "Q12": "Souvent", "Q15": "Peu efficaces"})
    assert _ligne(QU.matrice(reps, _res([EN_PLACE_P])), "M6")["resultat"] != QU.A_VERIFIER


FERMEES = ({"Q18": "Non, pour des raisons de sécurité (intrusion, nuisibles, pluie…)"}, {"Q18": "Oui"})


@pytest.mark.parametrize("n,audit,attendu", [
    ((3, 7), [NOCT_R], QU.A_VERIFIER), ((2, 8), [NOCT_R], QU.COHERENT), ((3, 7), [NOCT_NR], QU.COHERENT),
    ((2, 0), [NOCT_R], QU.NON_EVALUABLE), ((3, 0), [], QU.NON_EVALUABLE)])
def test_matrice_m7(n, audit, attendu):
    assert _ligne(QU.matrice(_reps(*n, *FERMEES), _res(audit)), "M7")["resultat"] == attendu


CLIM = ({"Q20": "Oui, un climatiseur mobile"}, {"Q20": "Non"})


@pytest.mark.parametrize("n,etats,attendu", [
    ((3, 7), {"BA-02": "Présent et fonctionnel"}, QU.COHERENT),
    ((3, 7), {"BA-02": "Aucun"}, QU.A_VERIFIER),
    ((0, 5), {}, QU.COHERENT),
    ((0, 2), {}, QU.NON_EVALUABLE),
])
def test_matrice_m8(n, etats, attendu):
    assert _ligne(QU.matrice(_reps(*n, *CLIM), _res([PROTEGE_R], etats)), "M8")["resultat"] == attendu


@pytest.mark.xfail(strict=True, reason="ANO-22 : M8 est évalué (« À vérifier ») avec une seule réponse, alors que § E1 "
                                       "prévoit « Non évaluable » en dessous de 3 réponses")
def test_matrice_m8_minimum_trois_reponses():
    assert _ligne(QU.matrice(_reps(1, 0, *CLIM), _res([PROTEGE_R])), "M8")["resultat"] == QU.NON_EVALUABLE


@pytest.mark.xfail(strict=True, reason="ANO-23 : M8 sans aucun local dans l'audit conclut « À vérifier » au lieu de "
                                       "« Non évaluable » (aucun local concerné)")
def test_matrice_m8_sans_local():
    assert _ligne(QU.matrice(_reps(5, 5, *CLIM), _res([])), "M8")["resultat"] == QU.NON_EVALUABLE


def test_matrice_m8_ignore_le_seuil_de_30_pourcent():
    """QM-08 : un seul usager sur 20 déclarant un équipement non relevé suffit à « À vérifier »."""
    reps = _reps(1, 19, *CLIM)
    assert _ligne(QU.matrice(reps, _res([PROTEGE_R])), "M8")["resultat"] == QU.A_VERIFIER


def test_indicateur_de_coherence():
    reps = _reps(3, 7, {**SOLEIL[0], **AIR[0]}, {**SOLEIL[1], **AIR[1]})
    m = QU.matrice(reps, _res([dict(PROTEGE_NR, **NOCT_R)]))
    ev = [l for l in m["lignes"] if l["resultat"] != QU.NON_EVALUABLE]
    av = [l for l in ev if l["resultat"] == QU.A_VERIFIER]
    assert m["evalues"] == len(ev) and m["a_verifier"] == len(av)
    assert m["indicateur"] == pytest.approx((len(ev) - len(av)) / len(ev))
    assert QU.matrice([], _res([PROTEGE_R]))["indicateur"] is None


def test_exemple_documente_e1():
    """§ E1 : sur l'exemple (14 réponses), 7 croisements évalués, 1 « À vérifier » (M7), indicateur 86 %."""
    m = QU.matrice(QU.lire_csv(MODELE)[0], moteur.calculer(EXEMPLE))
    assert (m["evalues"], m["a_verifier"], round(m["indicateur"] * 100)) == (7, 1, 86)
    assert [l["id"] for l in m["lignes"] if l["resultat"] == QU.A_VERIFIER] == ["M7"]


def test_audit_vide_tout_sous_reserve_juge_coherent():
    """QM-07 : un audit sans aucune donnée (tout « Sous réserve ») rend M1 à M5 « Cohérent » dès que le
    ressenti est signalé — « Sous réserve » compte comme une préconisation."""
    res = moteur.calculer({"locaux": [{}]})
    reps = _reps(10, 0, {**SOLEIL[0], **AIR[0], **INCONF[0], "Q22": ["Toute la journée"]}, {})
    m = QU.matrice(reps, res)
    assert {l["id"]: l["resultat"] for l in m["lignes"]}["M1"] == QU.COHERENT
    assert m["indicateur"] == 1


def test_libelle_seuil_coherent_avec_le_calcul():
    """Le PDF annonce « signalé au-delà de 30 % » ; le calcul retient « au moins 30 % » (≥), comme § E1."""
    t = " ".join(sorties.texte(generer_pdf(dict(copy.deepcopy(EXEMPLE), questionnaires=JEU))).split())
    assert "au-delà de 30%" in t  # libellé ambigu (ANO-24, mineur) : « au-delà » se lit « strictement plus de »
