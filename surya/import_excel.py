"""Lecture d'un classeur Excel de la méthode (onglets Saisie_*) vers le format de données de l'outil.

Les lignes sont repérées par leur code (colonne A) et leur libellé (colonne B), pas par
leur numéro : l'import reste valable si des lignes sont ajoutées ou supprimées dans l'Excel.
"""
from __future__ import annotations

import warnings

from .moteur import ORIENTATIONS

DEBUT = 5  # première ligne de saisie


def plan_feuille(ws, fin=None) -> dict:
    """Repère les lignes d'un onglet de saisie.

    Renvoie {"questions": {code: (ligne, type)}, "options": {(code, libellé): ligne},
    "murs": [{"questions": {code: ligne}, "baies": {libellé: ligne}}], "aucune_baie": ligne}.
    """
    plan = {"questions": {}, "options": {}, "murs": [], "aucune_baie": None}
    mur, courant = None, None
    for r in range(DEBUT, (fin or ws.max_row) + 1):
        a, b, c = (ws.cell(r, i).value for i in (1, 2, 3))
        c = (c or "").strip() if isinstance(c, str) or c is None else c
        if a and not b:
            mur = None
            if str(a).startswith("Mur extérieur"):
                mur = {"questions": {}, "baies": {}}
                plan["murs"].append(mur)
            courant = None
        elif a and b:
            code = str(a).strip()
            if c == "x":
                plan["aucune_baie"] = r
                courant = None
            elif mur is not None:
                if c == "":
                    courant = ("baies", None)
                else:
                    mur["questions"]["orientation" if code == "MEX-01" else code] = r
                    courant = None
            else:
                if code in plan["questions"]:
                    code += "b"
                multi = isinstance(c, str) and c.startswith("Plusieurs réponses")
                plan["questions"][code] = (r, "multi" if multi else "simple")
                courant = ("multi", code) if multi else None
        elif b and courant:
            if courant[0] == "baies":
                mur["baies"][str(b).strip()] = r
            else:
                plan["options"][(courant[1], str(b).strip())] = r
    return plan


def _valeur(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def lire_colonne(ws, plan, col) -> dict:
    d = {}
    for code, (r, typ) in plan["questions"].items():
        if typ == "multi":
            sel = [lab for (c, lab), ro in plan["options"].items() if c == code and _valeur(ws.cell(ro, col).value) is not None]
            if sel:
                d[code] = sel
        else:
            v = _valeur(ws.cell(r, col).value)
            if v is not None:
                d[code] = v
    if plan["murs"]:
        if plan["aucune_baie"] and _valeur(ws.cell(plan["aucune_baie"], col).value) is not None:
            d["aucune_baie"] = True
        murs = []
        for m in plan["murs"]:
            mur = {k: _valeur(ws.cell(r, col).value) for k, r in m["questions"].items()}
            mur = {k: v for k, v in mur.items() if v is not None}
            baies = {lab: _valeur(ws.cell(r, col).value) for lab, r in m["baies"].items()}
            baies = {k: v for k, v in baies.items() if v is not None}
            if baies:
                mur["baies"] = baies
            murs.append(mur)
        while murs and not murs[-1]:
            murs.pop()
        if murs:
            d["murs"] = murs
    return d


def lire_classeur(source) -> dict:
    """``source`` : chemin ou fichier binaire d'un .xlsx de la méthode."""
    import openpyxl

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(source, data_only=True)

    ws = wb["Saisie_Bâtiment"]
    ligne_facades = next(r for r in range(DEBUT, ws.max_row + 1) if ws.cell(r, 1).value == "F-01") - 1
    batiment = lire_colonne(ws, plan_feuille(ws, fin=ligne_facades - 2), 4)
    facades = {}
    for col in range(4, 4 + len(ORIENTATIONS)):
        o = ws.cell(ligne_facades, col).value
        f = {}
        for r in range(ligne_facades + 1, ligne_facades + 6):
            v = _valeur(ws.cell(r, col).value)
            if v is not None:
                code = ws.cell(r, 1).value
                f[code] = True if code == "F-01" else v
        if o in ORIENTATIONS and f:
            facades[o] = f

    def colonnes(nom):
        ws = wb[nom]
        plan = plan_feuille(ws)
        out = []
        for col in range(4, ws.max_column + 1):
            d = lire_colonne(ws, plan, col)
            if d:
                out.append(d)
        return out

    return {"batiment": batiment, "facades": facades,
            "locaux": colonnes("Saisie_Locaux"), "espaces": colonnes("Saisie_Extérieurs")}
