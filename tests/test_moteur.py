"""Tests du moteur (pytest). La comparaison exhaustive avec l'Excel est dans fuzz_excel.py."""
import json
import random
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from surya import moteur  # noqa: E402
from surya.import_excel import lire_classeur  # noqa: E402

EXEMPLE = json.loads((RACINE / "surya" / "exemple.json").read_text(encoding="utf-8"))


def statuts(x):
    return {s["solution"]: s["statut"] for s in x["solutions"]}


def test_exemple_de_l_excel():
    res = moteur.calculer(EXEMPLE)
    motricite = statuts(res["locaux"][1])
    assert motricite["Mise en place de brasseurs d'air plafonniers"] == "À optimiser"
    assert motricite["Par ventilation naturelle nocturne"] == "Sous réserve"
    assert motricite["Par ventilation mécanique nocturne"] == "Non recommandé ou non adapté"
    assert motricite["Toiture"] == "Non concerné"
    assert statuts(res["locaux"][0])["Toiture"] == "À optimiser"
    cour = res["espaces"][0]
    assert statuts(cour) == {"Ombrage rapporté adossé au bâtiment": "Recommandé",
                             "Adaptation d'un préau existant": "À optimiser",
                             "Ombrage autoportant ou végétal de la cour": "À optimiser"}
    assert cour["EX-AL"] == 1


def test_import_excel_identique_a_l_exemple():
    assert lire_classeur(RACINE / "reference" / "outil_aide_test_methode.xlsx") == EXEMPLE


def test_local_vide_sous_reserve():
    res = moteur.calculer({"locaux": [{}], "espaces": [{}]})
    assert set(statuts(res["locaux"][0]).values()) == {"Sous réserve"}


def test_seuils_modifiables():
    local = {"BA-05": "Aucun", "PL-01": "Sous-face de dalle ou de plancher béton apparente", "PL-03": 2.5,
             "BA-19": ["Aucun"], "ECL-02": ["Encastré dans le faux plafond (dalle, spot)"]}
    cle = "Mise en place de brasseurs d'air plafonniers"
    assert statuts(moteur.calculer({"locaux": [local]})["locaux"][0])[cle] == "Sous réserve"  # BS-3
    res = moteur.calculer({"locaux": [local], "parametres": {"P_HSP_CONF": 2.5}})
    assert statuts(res["locaux"][0])[cle] == "Recommandé"


def test_tirages_aleatoires_sans_erreur_et_regles_atteintes():
    """Le moteur ne plante sur aucune combinaison et les tirages atteignent presque toutes les règles."""
    import fuzz_excel

    rnd, vues = random.Random(3), set()
    for _ in range(300):
        res = moteur.calculer(fuzz_excel.tirage(rnd))
        for x in res["locaux"] + res["espaces"]:
            vues.update(b["regle"] for b in x["blocs"].values() if b["regle"])
            vues.update(c for s in x["solutions"] for c in s["alertes"])
    assert len(vues) >= 0.93 * len(moteur.REGLES), sorted(set(moteur.REGLES) - vues)
