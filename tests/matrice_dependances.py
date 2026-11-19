"""Matrice de dépendances questions → solutions (partie C de la campagne de tests).

Pour chaque question, on fait varier sa réponse (toutes les options, vide, quelques nombres) sur des
saisies aléatoires et on note les solutions dont le statut ou les alertes changent. On compare à la
colonne « Questions » des règles de l'Excel (``referentiel.json``), complétée des questions qui
sélectionnent un cas (BA-05, L-09, B-18, B-21, B-22, E-02).

Usage : python tests/matrice_dependances.py [nb_tirages]   → tableau Markdown sur la sortie standard.
"""
from __future__ import annotations

import copy
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import fuzz_excel  # noqa: E402
from surya import moteur  # noqa: E402
from surya.questions import SECTIONS_BATIMENT, SECTIONS_ESPACE, SECTIONS_LOCAL  # noqa: E402

BLOC_SOLUTION = {
    "BP": "Brasseurs", "BS": "Brasseurs", "BR": "Brasseurs", "VN": "VN nocturne", "VM": "VM nocturne",
    "PV": "Prot. verticales", "PH": "Prot. horizontales", "FS": "Films", "FT": "Fenêtres de toit",
    "VV": "Vérandas", "TO": "Toiture", "TT": "Toiture", "CP": "Toiture", "CA": "Toiture", "CO": "Occupation",
    "CE": "Éclairage", "CQ": "Équipements", "OA": "Ombrage adossé", "PR": "Préau", "EX": "Préau",
    "OC": "Ombrage cour",
}
COURT = {
    "Mise en place de brasseurs d'air plafonniers": "Brasseurs", "Par ventilation naturelle nocturne": "VN nocturne",
    "Par ventilation mécanique nocturne": "VM nocturne", "Protections verticales": "Prot. verticales",
    "Protections horizontales": "Prot. horizontales", "Films solaires": "Films",
    "Sur fenêtres de toiture": "Fenêtres de toit", "Sur vérandas et/ou verrières": "Vérandas", "Toiture": "Toiture",
    "Occupation": "Occupation", "Éclairage": "Éclairage", "Équipements": "Équipements",
    "Ombrage rapporté adossé au bâtiment": "Ombrage adossé", "Adaptation d'un préau existant": "Préau",
    "Ombrage autoportant ou végétal de la cour": "Ombrage cour",
}
# Questions qui choisissent le cas (bloc) d'une solution : elles n'apparaissent pas toujours dans la
# colonne « Questions » des règles, mais ont naturellement un effet.
CAS = {"BA-05": {"Brasseurs"}, "L-09": {"Toiture"}, "B-18": {"Toiture"}, "B-21": {"Toiture"}, "B-22": {"Toiture"},
       "E-02": {"Ombrage cour", "Préau"}}
# Questions conditionnelles : leur question « mère » agit via elles (porte « #SO »).
MERES = {"MEX-14": ["MEX-15", "MEX-16", "MEX-18"], "MEX-15": ["MEX-20", "MEX-21", "MEX-22", "MEX-24"],
         "MEX-16": ["MEX-17"], "MEX-18": ["MEX-19"], "BA-06": ["BA-14"], "B-09": ["B-10", "B-13", "B-14", "B-15", "BA-15"],
         "B-10": ["B-11"], "B-11": ["B-12"], "B-15": ["B-16"], "B-19": ["B-20"], "BA-15": ["BA-18"], "PL-01": ["PL-02"],
         "E-04": ["E-07"], "E-10": ["E-12"], "E-20": ["E-21", "E-22", "E-23", "E-24", "E-25"], "E-26": ["E-27"],
         "B-08": ["MEX-37"], "MEX-29": ["MEX-30"], "MEX-32": ["MEX-33"], "MEX-34": ["MEX-35"]}


def attendues() -> dict[str, set[str]]:
    """question -> solutions attendues d'après la colonne « Questions » des règles et alertes."""
    att = defaultdict(set)
    for code, r in moteur.REGLES.items():
        sol = BLOC_SOLUTION[code.split("-")[0]]
        for q in re.findall(r"[A-Z]{1,3}-\d+", r["questions"] or ""):
            att[q].add(sol)
    for q, s in CAS.items():
        att[q] |= s
    for mere, filles in MERES.items():
        for f in filles:
            att[mere] |= att.get(f, set())
    # OA-AL1 (alerte de l'ombrage adossé) dépend du statut PH des locaux du RDC : toute question de PH
    # touche donc indirectement l'ombrage adossé.
    for q in list(att):
        if "Prot. horizontales" in att[q]:
            att[q].add("Ombrage adossé")
    att["F-01"] = att["F-02"] | att["F-03"] | att["F-04"] | att["F-05"]  # « façade décrite »
    att["EX-AL"] = set()
    return att


def _signature(res):
    out = {}
    for cle in ("locaux", "espaces"):
        for i, x in enumerate(res[cle]):
            for s in x["solutions"]:
                out[(cle, i, COURT[s["solution"]])] = (s["statut"], tuple(s["alertes"]))
            if cle == "espaces":
                out[(cle, i, "Préau")] = out[(cle, i, "Préau")] + (x["EX-AL"],)
    return out


def _valeurs(q):
    t = q["type"]
    if t == "choix":
        return [None, *q["options"]]
    if t == "multi":
        return [None, *[[o] for o in q["options"]]]
    if t == "nombre":
        return [None, 0, 1, 2, 2.5, 5, 16, 20, 30, 100, 1000]
    return [None, "texte"]


def observer(n=60, graine=7):
    """question -> solutions dont le statut ou les alertes changent quand la réponse varie."""
    rnd = random.Random(graine)
    obs = defaultdict(set)
    plans = (("batiment", SECTIONS_BATIMENT), ("locaux", SECTIONS_LOCAL), ("espaces", SECTIONS_ESPACE))
    for _ in range(n):
        d = fuzz_excel.tirage(rnd)
        d["locaux"], d["espaces"] = d["locaux"][:2], d["espaces"][:2]
        ref = _signature(moteur.calculer(d))
        for cle, sections in plans:
            cibles = [d["batiment"]] if cle == "batiment" else d[cle]
            for ent in cibles:
                for s in sections:
                    for q in s["questions"]:
                        avant = ent.get(q["code"], None)
                        for v in _valeurs(q):
                            if v is None:
                                ent.pop(q["code"], None)
                            else:
                                ent[q["code"]] = copy.deepcopy(v)
                            sig = _signature(moteur.calculer(d))
                            for k in ref:
                                if sig[k] != ref[k]:
                                    obs[q["code"]].add(k[2])
                        if avant is None:
                            ent.pop(q["code"], None)
                        else:
                            ent[q["code"]] = avant
        # façades et murs
        for o in moteur.ORIENTATIONS:
            f = d["facades"].setdefault(o, {})
            for k in ("F-01", "F-02", "F-03", "F-04", "F-05"):
                avant = f.get(k)
                for v in ([None, True] if k == "F-01" else [None, "Oui", "Non"]):
                    if v is None:
                        f.pop(k, None)
                    else:
                        f[k] = v
                    sig = _signature(moteur.calculer(d))
                    obs[k] |= {x[2] for x in ref if sig[x] != ref[x]}
                if avant is None:
                    f.pop(k, None)
                else:
                    f[k] = avant
        for l in d["locaux"]:
            for m in l.get("murs") or []:
                for q in moteur.REFERENTIEL["mur"]:
                    if q["type"] == "baies":
                        continue
                    avant = m.get(q["code"])
                    for v in _valeurs(q):
                        if v is None:
                            m.pop(q["code"], None)
                        else:
                            m[q["code"]] = v
                        sig = _signature(moteur.calculer(d))
                        code = "MEX-01" if q["code"] == "orientation" else q["code"]
                        obs[code] |= {x[2] for x in ref if sig[x] != ref[x]}
                    if avant is None:
                        m.pop(q["code"], None)
                    else:
                        m[q["code"]] = avant
                avant = m.get("baies")
                for v in (None, {"Vitrage fixe": 1}, {"Fenêtre oscillo-battante": 2}, {"Fenêtre à la française": 1}):
                    if v is None:
                        m.pop("baies", None)
                    else:
                        m["baies"] = v
                    sig = _signature(moteur.calculer(d))
                    obs["MEX-08"] |= {x[2] for x in ref if sig[x] != ref[x]}
                if avant is None:
                    m.pop("baies", None)
                else:
                    m["baies"] = avant
    return obs


def comparer(obs):
    att = attendues()
    info = {q["code"] for s in SECTIONS_BATIMENT + SECTIONS_LOCAL + SECTIONS_ESPACE for q in s["questions"] if q.get("info")}
    codes = [q["code"] for s in SECTIONS_BATIMENT + SECTIONS_LOCAL + SECTIONS_ESPACE for q in s["questions"]]
    codes += ["F-01", "F-02", "F-03", "F-04", "F-05", "MEX-01", "MEX-04", "MEX-05", "MEX-06", "MEX-07", "MEX-08"]
    lignes = []
    for q in codes:
        o, a = obs.get(q, set()), att.get(q, set())
        lignes.append((q, q in info, sorted(o), sorted(o - a), sorted(a - o)))
    return lignes


def markdown(lignes) -> str:
    out = ["| Question | info | Solutions touchées (observé) | **Inattendues** | Attendues mais sans effet |",
           "|---|---|---|---|---|"]
    for q, info, o, inat, absentes in lignes:
        out.append(f"| {q} | {'oui' if info else ''} | {', '.join(o) or '—'} | "
                   f"{('**' + ', '.join(inat) + '**') if inat else ''} | {', '.join(absentes)} |")
    return "\n".join(out)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    print(markdown(comparer(observer(n))))
