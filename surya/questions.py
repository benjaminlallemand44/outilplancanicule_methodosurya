"""Questionnaire : sections et questions (textes issus de l'Excel) et conditions d'affichage.

Une question masquée correspond à l'état « #SO » (sans objet) du moteur : les conditions
ci-dessous reprennent les « - si … : » de la colonne Question des onglets de saisie.
"""
from __future__ import annotations

import copy

from .moteur import FAUX_PLAFONDS, PRESENT, REFERENTIEL, a

SECTIONS_BATIMENT = REFERENTIEL["batiment"]
SECTIONS_ESPACE = REFERENTIEL["espaces"]
QUESTIONS_FACADE = REFERENTIEL["facades"]  # F-01 (façade décrite) puis F-02 à F-05
QUESTIONS_MUR = REFERENTIEL["mur"]

# BA-18 est utilisée par les règles VM-7, VM-9 et VM-10 mais n'a pas de ligne de saisie
# dans l'Excel (référence #REF!) : la question est ajoutée ici.
SECTIONS_LOCAL = copy.deepcopy([s for s in REFERENTIEL["locaux"] if s["titre"] != "Baies en façade"])
for _s in SECTIONS_LOCAL:
    for _i, _q in enumerate(_s["questions"]):
        if _q["code"] == "BA-15":
            _s["questions"].insert(_i + 1, {
                "code": "BA-18", "type": "nombre", "unite": "m³/h", "info": False,
                "libelle": "Débit maximal de ventilation mécanique du local"})
            break

# code -> fonction(c, d, cb) : c = états calculés de l'entité, d = réponses saisies,
# cb = états du bâtiment. Une question absente du dictionnaire est toujours affichée.
VISIBLE = {
    # Bâtiment
    "B-10": lambda c, d, cb: c["B-09"] == "Oui",
    "B-11": lambda c, d, cb: c["B-10"] == "Double flux",
    "B-12": lambda c, d, cb: c["B-11"] == "Oui",
    "B-13": lambda c, d, cb: c["B-09"] == "Oui",
    "B-14": lambda c, d, cb: c["B-09"] == "Oui",
    "B-15": lambda c, d, cb: c["B-09"] == "Oui",
    "B-16": lambda c, d, cb: c["B-15"] == "Oui",
    "B-19": lambda c, d, cb: c["B-18"] in ("Toiture-terrasse", "Bac acier ou fibro-ciment"),
    "B-20": lambda c, d, cb: c["B-19"] == "Isolée",
    "B-22": lambda c, d, cb: c["B-21"] == "Oui",
    "B-23": lambda c, d, cb: c["B-21"] == "Oui",
    "B-24": lambda c, d, cb: c["B-21"] == "Oui",
    "B-25": lambda c, d, cb: c["B-21"] == "Oui",
    "B-26": lambda c, d, cb: c["B-22"] == "En comble perdu",
    "B-27": lambda c, d, cb: c["B-21"] == "Oui",
    "B-28": lambda c, d, cb: c["B-22"] == "En comble perdu",
    # Locaux
    "MEX-15": lambda c, d, cb: c["MEX-14"] == "Oui",
    "MEX-16": lambda c, d, cb: c["MEX-14"] == "Oui",
    "MEX-17": lambda c, d, cb: c["MEX-16"] == "Oui",
    "MEX-18": lambda c, d, cb: c["MEX-14"] == "Oui",
    "MEX-19": lambda c, d, cb: c["MEX-18"] == "ok" and a(d.get("MEX-18"), "Volet extérieur", "Store extérieur", "Store intérieur"),
    "MEX-20": lambda c, d, cb: c["MEX-15"] == "ok" and a(d.get("MEX-15"), "Fenêtre de toit (type Velux)"),
    "MEX-21": lambda c, d, cb: c["MEX-15"] == "ok" and a(d.get("MEX-15"), "Fenêtre de toit (type Velux)"),
    "MEX-22": lambda c, d, cb: c["MEX-15"] == "ok" and a(d.get("MEX-15"), "Verrière", "Véranda"),
    "MEX-24": lambda c, d, cb: c["MEX-15"] == "ok" and a(d.get("MEX-15"), "Véranda"),
    "MEX-25b": lambda c, d, cb: c["MEX-25"] == "Oui",
    "MEX-30": lambda c, d, cb: a(d.get("MEX-29"), "Volets roulants", "Stores"),
    "MEX-33": lambda c, d, cb: c["MEX-32"] in ("Sur toutes les baies", "Sur une partie des baies"),
    "MEX-35": lambda c, d, cb: c["MEX-34"] == "Oui",
    "MEX-37": lambda c, d, cb: cb["B-08"] == "Oui",
    "PL-02": lambda c, d, cb: c["PL-01"] in FAUX_PLAFONDS,
    "BA-03": lambda c, d, cb: c["BA-02"] in PRESENT,
    "BA-06": lambda c, d, cb: c["BA-05"] in PRESENT,
    "BA-09": lambda c, d, cb: c["BA-05"] in PRESENT,
    "BA-11": lambda c, d, cb: c["BA-05"] in PRESENT,
    "BA-12": lambda c, d, cb: c["BA-05"] in PRESENT,
    "BA-13": lambda c, d, cb: c["BA-05"] in PRESENT,
    "BA-14": lambda c, d, cb: isinstance(c["BA-06"], (int, float)) and c["BA-06"] >= 2,
    "BA-15": lambda c, d, cb: cb["B-09"] == "Oui",
    "BA-18": lambda c, d, cb: c["BA-15"] == "Oui",
    # Espaces extérieurs
    "E-07": lambda c, d, cb: a(d.get("E-04"), "Maternelle"),
    "E-12": lambda c, d, cb: a(d.get("E-10"), "Arbres"),
    "E-21": lambda c, d, cb: bool(d.get("E-20")) and not a(d.get("E-20"), "Aucune"),
    "E-22": lambda c, d, cb: bool(d.get("E-20")) and not a(d.get("E-20"), "Aucune"),
    "E-23": lambda c, d, cb: bool(d.get("E-20")) and not a(d.get("E-20"), "Aucune"),
    "E-24": lambda c, d, cb: bool(d.get("E-20")) and not a(d.get("E-20"), "Aucune"),
    "E-25": lambda c, d, cb: bool(d.get("E-20")) and not a(d.get("E-20"), "Aucune"),
    "E-26": lambda c, d, cb: a(d.get("E-02"), "Préau"),
    "E-27": lambda c, d, cb: c["E-26"] == "Polycarbonate ou verrière",
    "E-28": lambda c, d, cb: a(d.get("E-02"), "Préau"),
    "E-29": lambda c, d, cb: a(d.get("E-02"), "Préau"),
    "E-30": lambda c, d, cb: a(d.get("E-02"), "Préau"),
    "E-32": lambda c, d, cb: a(d.get("E-02"), "Cour de récréation"),
}


def visible(code: str, c: dict, d: dict, cb: dict) -> bool:
    f = VISIBLE.get(code)
    return True if f is None else bool(f(c, d, cb))


def avancement(sections, c, d, cb) -> tuple[int, int]:
    """(questions renseignées, questions affichées) pour une entité."""
    fait = total = 0
    for s in sections:
        for q in s["questions"]:
            if visible(q["code"], c, d, cb):
                total += 1
                fait += d.get(q["code"]) not in (None, "", [])
    return fait, total
