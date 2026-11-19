"""Profils de référence écrits à la main pour la campagne de tests (parties B, C, D).

Chaque profil est « sans contrainte » : toutes les règles restrictives y sont fausses, et chaque
bloc tombe sur sa règle par défaut (ou sur une règle connue, indiquée en commentaire). Un cas de
test part d'un profil et ne modifie que les réponses nécessaires pour déclencher la règle visée.

Ce module ne dépend que de ``surya.moteur`` (pas de l'Excel ni de l'interface).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from surya import moteur  # noqa: E402

# Statuts attendus avec les profils de base :
#   brasseurs BS-7 Recommandé · VN-10 Sous réserve · VM-7 En place · PV-8 Recommandé ·
#   PH-11 Recommandé · FS-3 Recommandé · FT-1 / VV-1 / TO-0 Non concerné · CO-3, CE-2, CQ-3 En place
#   espace : OA-10 Recommandé · PR-6 En place · OC-6 Recommandé · EX-AL = 0
BATIMENT = {
    "B-01": "De 1948 à 1974", "B-03": "Maçonnerie", "B-04": "ITI (isolation par l'intérieur)", "B-05": "Non",
    "B-06": "Non", "B-07": "Non", "B-08": "Non", "B-09": "Oui", "B-10": "Simple flux",
    "B-13": "En fonctionnement", "B-14": "Oui", "B-15": "Oui", "B-16": "Oui",
    "B-18": "Toiture à pentes (tuiles, ardoises, zinc)", "B-21": "Oui", "B-22": "En comble perdu",
    "B-23": ["Bon état (épaisseur régulière et continue)"], "B-24": 20, "B-25": "Oui", "B-26": "Oui",
    "B-27": "Non", "B-28": ["Aucun"],
}
FACADE = {"F-01": True, "F-02": "Non", "F-03": "Oui", "F-04": "Non", "F-05": "Non"}
FACADES = {o: dict(FACADE) for o in moteur.ORIENTATIONS}
MUR = {"orientation": "S", "MEX-04": "Nu intérieur", "MEX-05": 20, "MEX-06": "Bon état", "MEX-07": "Aucun",
       "baies": {"Fenêtre à la française": 2}}
LOCAL = {
    "L-01": "Classe A", "L-02": "Classe", "L-03": 60, "L-04": 25, "L-09": "Étage intermédiaire", "L-10": ["Aucun"],
    "L-11": "Oui", "MEX-14": "Non", "MEX-25": "Non", "MEX-26": "Maçonnerie", "MEX-29": ["Aucune"],
    "MEX-32": "Aucun", "MEX-34": "Non", "MEX-36": ["Grilles"], "MEX-37": "Non",
    "PL-01": "Sous-face de dalle ou de plancher béton apparente", "PL-03": 3, "PL-05": "Béton",
    "BA-01": "Aucun", "BA-02": "Aucun", "BA-04": "Aucun", "BA-05": "Aucun", "BA-15": "Oui", "BA-18": 500,
    "BA-19": ["Aucun"], "ECL-01": "LED", "ECL-02": ["Encastré dans le faux plafond (dalle, spot)"],
    "murs": [dict(MUR)],
}
ESPACE = {
    "E-01": "Cour", "E-02": ["Cour de récréation", "Préau"], "E-04": ["Élémentaire"], "E-06": 100, "E-09": "0 %",
    "E-10": ["Aucune"], "E-14": 200, "E-15": "Aucune structure", "E-16": "Oui", "E-17": "Non", "E-19": "Non",
    "E-20": ["S"], "E-21": "Aucune", "E-22": "Béton ou maçonnerie pleine", "E-23": "Non",
    "E-24": "Mâts, poteaux ou élément solide existants (mur, préau, bâtiment voisin)", "E-25": "Oui",
    "E-26": "Tuiles", "E-28": "Claire", "E-29": 4, "E-30": 1, "E-31": "Non", "E-32": "Pleine terre ou sol fondable",
}
# Variantes utiles
BRASSEURS_EN_PLACE = {"BA-05": "Présent et fonctionnel", "BA-06": 1, "BA-09": 200, "BA-11": "Oui", "BA-12": 250,
                      "BA-13": 250}  # (300 - 250) / 200 = 0,25 > 0,15 ; 2,0 / √60 = 0,258 ; 250 > 200
FENETRE_DE_TOIT = {"MEX-14": "Oui", "MEX-15": ["Fenêtre de toit (type Velux)"], "MEX-16": "Non",
                   "MEX-18": ["Aucune"], "MEX-20": "Marque et modèle identifiables", "MEX-21": "Oui"}
VERANDA = {"MEX-14": "Oui", "MEX-15": ["Véranda"], "MEX-16": "Oui", "MEX-18": ["Aucune"], "MEX-22": "Oui",
           "MEX-24": "Oui"}
DERNIER = {"L-09": "Dernier niveau"}

SUPPR = object()  # valeur de patch : supprimer la réponse


def fusion(base: dict, patch: dict | None) -> dict:
    d = copy.deepcopy(base)
    for k, v in (patch or {}).items():
        if v is SUPPR:
            d.pop(k, None)
        else:
            d[k] = copy.deepcopy(v)
    return d


def mur(**k) -> dict:
    return fusion(MUR, {kk.replace("_", "-"): v for kk, v in k.items()})


def donnees(bat=None, fac=None, local=None, espace=None, param=None, locaux=None, espaces=None) -> dict:
    """Jeu de données complet : profils de base modifiés par les patchs.

    ``fac`` : {orientation: patch} ; ``locaux`` / ``espaces`` : listes complètes (remplacent le local
    ou l'espace unique)."""
    facades = copy.deepcopy(FACADES)
    for o, p in (fac or {}).items():
        facades[o] = fusion(facades.get(o, {}), p)
    return {"batiment": fusion(BATIMENT, bat), "facades": facades,
            "locaux": locaux if locaux is not None else [fusion(LOCAL, local)],
            "espaces": espaces if espaces is not None else [fusion(ESPACE, espace)],
            "parametres": param or {}}


def solution(x: dict, nom: str) -> dict:
    return next(s for s in x["solutions"] if s["solution"] == nom)


def statuts(x: dict) -> dict:
    return {s["solution"]: s["statut"] for s in x["solutions"]}


# bloc -> solution
SOLUTION_DU_BLOC = {
    "BP": "Mise en place de brasseurs d'air plafonniers", "BS": "Mise en place de brasseurs d'air plafonniers",
    "VN": "Par ventilation naturelle nocturne", "VM": "Par ventilation mécanique nocturne",
    "PV": "Protections verticales", "PH": "Protections horizontales", "FS": "Films solaires",
    "FT": "Sur fenêtres de toiture", "VV": "Sur vérandas et/ou verrières",
    "TO": "Toiture", "TT": "Toiture", "CP": "Toiture", "CA": "Toiture",
    "CO": "Occupation", "CE": "Éclairage", "CQ": "Équipements",
    "OA": "Ombrage rapporté adossé au bâtiment", "PR": "Adaptation d'un préau existant",
    "OC": "Ombrage autoportant ou végétal de la cour",
}
BLOCS_ESPACE = ("OA", "PR", "OC")


def evaluer(d: dict, bloc: str, indice: int = 0) -> tuple[str | None, str, bool, dict]:
    """(règle retenue du bloc, statut de la solution, donnée manquante ?, solution)."""
    res = moteur.calculer(d)
    x = res["espaces" if bloc in BLOCS_ESPACE else "locaux"][indice]
    s = solution(x, SOLUTION_DU_BLOC[bloc])
    b = x["blocs"][bloc]
    return b["regle"], s["statut"], b["manquante"], s
