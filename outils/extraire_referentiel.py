"""Extrait de l'Excel de référence les libellés (questions, options, règles, seuils)
et les écrit dans surya/referentiel.json.

Seuls les TEXTES viennent de l'Excel ; la logique (conditions d'affichage, règles)
est écrite en Python dans surya/moteur.py et surya/questions.py.

Usage : python outils/extraire_referentiel.py reference/outil_aide_test_methode.xlsx
"""
import json
import re
import sys
import warnings
from pathlib import Path

import openpyxl

warnings.filterwarnings("ignore")
src = sys.argv[1] if len(sys.argv) > 1 else "reference/outil_aide_test_methode.xlsx"
wb = openpyxl.load_workbook(src)

# --- listes déroulantes -------------------------------------------------------
listes = {}
ws = wb["Listes"]
for col in ws.iter_cols(min_row=1, max_row=ws.max_row):
    if col[0].value:
        listes[str(col[0].value)] = [c.value for c in col[1:] if c.value is not None]


def nettoyer(label: str) -> str:
    label = label.replace("[info]", "").replace("[ajout]", "")
    label = re.sub(r"^Mur \d - ", "", label.strip())
    label = re.sub(r"^-?\s*si .*? : ", "", label)
    label = label.replace("((0 à 4))", "(0 à 4)")
    label = re.sub(r"\s+\?", " ?", label)
    label = re.sub(r"(?<=\w)\?", " ?", label)
    return re.sub(r"\s{2,}", " ", label).strip()


def lire_saisie(nom, fin=None, debut=5):
    ws = wb[nom]
    sections, courante, q = [], None, None
    for r in range(debut, (fin or ws.max_row) + 1):
        a, b, c = (ws.cell(r, i).value for i in (1, 2, 3))
        if a and not b:  # titre de section
            courante = {"titre": str(a).strip(), "questions": []}
            sections.append(courante)
            q = None
            continue
        if a and b:
            code = str(a).strip()
            if any(x["code"] == code for s in sections for x in s["questions"]):
                code += "b"
            c = (c or "").strip()
            q = {"code": code, "libelle": nettoyer(b), "info": "[info]" in b}
            if c.startswith("Plusieurs réponses"):
                q.update(type="multi", options=[])
            elif c.startswith("Nombre"):
                m = re.match(r"Nombre en (.+?)(?: ou .*)?$", c)
                q.update(type="nombre", unite=(m.group(1) if m else "").strip("()"))
                u = re.search(r"\(([^()]+)\)$", q["libelle"])
                if u and (u.group(1) == q["unite"] or not q["unite"]):
                    q["unite"] = q["unite"] or u.group(1)
                    q["libelle"] = q["libelle"][: u.start()].strip()
            elif c == "Texte":
                q.update(type="texte")
            elif c == "x":
                q.update(type="case")
            elif c == "":
                q.update(type="baies", options=[])
            else:
                q.update(type="choix", options=listes.get(code.rstrip("b")) or [o.strip() for o in c.split(" / ")])
            courante["questions"].append(q)
        elif b and q is not None and q["type"] in ("multi", "baies"):
            q["options"].append(str(b).strip())
    return sections


ref = {"version": wb["Règles_Locaux"]["A1"].value}
ref["batiment"] = lire_saisie("Saisie_Bâtiment", fin=46)
ws = wb["Saisie_Bâtiment"]
ref["facades"] = [
    {"code": ws.cell(r, 1).value, "libelle": nettoyer(ws.cell(r, 2).value.split(" : mettre x")[0]),
     "options": listes.get(ws.cell(r, 1).value, [])}
    for r in range(50, 55)
]
ref["orientations"] = listes["Orientations"]
locaux = lire_saisie("Saisie_Locaux")
# Les 4 blocs « Mur extérieur n » sont identiques : on ne garde que le premier comme modèle.
ref["mur"] = next(s for s in locaux if s["titre"] == "Mur extérieur 1")["questions"]
ref["mur"][0].update(code="orientation", libelle="Orientation du mur", options=listes["Orientations"])
ref["locaux"] = [s for s in locaux if not s["titre"].startswith("Mur extérieur")]
ref["espaces"] = lire_saisie("Saisie_Extérieurs")

# --- seuils -------------------------------------------------------------------
ws = wb["Paramètres"]
ref["parametres"] = [
    {"nom": ws.cell(r, 1).value, "valeur": ws.cell(r, 2).value, "unite": ws.cell(r, 3).value or "",
     "signification": ws.cell(r, 4).value, "regles": ws.cell(r, 5).value}
    for r in range(5, ws.max_row + 1) if ws.cell(r, 1).value
]

# --- textes des règles ----------------------------------------------------------
regles = {}
for nom in ("Règles_Locaux", "Règles_Extérieurs"):
    ws = wb[nom]
    for r in range(4, ws.max_row + 1):
        a, b, c, d, e, f = (ws.cell(r, i).value for i in range(1, 7))
        if a and re.match(r"^[A-Z]{2,3}-[A-Z0-9]+$", str(a)) and d:
            regles[a] = {"statut": c, "alerte": b == "Alerte", "regle": nettoyer(d),
                         "condition": e, "questions": "" if f in (None, "-") else f}
ref["regles"] = regles

out = Path(__file__).resolve().parent.parent / "surya" / "referentiel.json"
out.write_text(json.dumps(ref, ensure_ascii=False, indent=1), encoding="utf-8")
print("écrit", out, "-", len(regles), "règles")
