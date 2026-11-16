"""Test de non-régression : compare le moteur Python à l'Excel de référence recalculé.

Pour chaque tirage : des réponses aléatoires (10 locaux, 5 espaces, 1 bâtiment) sont écrites
dans une copie de l'Excel, LibreOffice recalcule toutes les formules, puis la valeur de CHAQUE
règle, le statut de chaque bloc, les alertes et l'onglet Résultats sont comparés au moteur.

L'Excel de référence contient quelques erreurs de références (voir README, « Écarts avec
l'Excel »). ``corriger_classeur`` les répare dans la copie de test, pour comparer le moteur à la
logique voulue par la méthode.

Usage : python tests/fuzz_excel.py [nb_tirages] [graine]      (nécessite LibreOffice)
"""
from __future__ import annotations

import random
import re
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from surya import moteur  # noqa: E402
from surya.import_excel import plan_feuille  # noqa: E402

REF = RACINE / "reference" / "outil_aide_test_methode.xlsx"
R = moteur.REFERENTIEL
LIGNE_BA18 = 166  # ligne libre de Saisie_Locaux utilisée pour la question BA-18 (absente de l'Excel)
warnings.filterwarnings("ignore")


# ------------------------------------------------------------------ correction de l'Excel
def _decaler(formule: str, feuille: str, delta: int) -> str:
    """Décale de ``delta`` lignes les références (cellules ou plages) vers ``feuille``."""
    def ref(m):
        fin = f":{m.group(4)}{int(m.group(5)) + delta}" if m.group(3) else ""
        return f"{m.group(1)}{int(m.group(2)) + delta}{fin}"
    return re.sub(rf"({feuille}!\$?[A-Z]+\$?)(\d+)(:(\$?[A-Z]+\$?)(\d+))?", ref, formule)


def corriger_classeur(wb):
    cl, rl = wb["Calc_Locaux"], wb["Règles_Locaux"]
    for col in range(4, 14):
        L = get_column_letter(col)
        # 1. Murs 2 à 4 : les formules pointent une ligne trop bas dans Saisie_Locaux
        #    (et un type de baie est en #REF!). On les régénère à partir de celles du mur 1.
        for k in (1, 2, 3):
            for base in (22, 23, 24, 25):  # MEX-04, 05, 06, 07
                f = _decaler(cl[f"{L}{base}"].value, "Saisie_Locaux", 15 * k)
                f = f.replace(f"Calc_Locaux!{L}$71", f"Calc_Locaux!{L}${71 + k}")
                f = f.replace(f"Calc_Locaux!{L}$22", f"Calc_Locaux!{L}${22 + 4 * k}")
                cl[f"{L}{base + 4 * k}"] = f
            for base in (75, 79, 83, 87):  # NTYPES, NONFIXE, OSC, AUTRES
                cl[f"{L}{base + k}"] = _decaler(cl[f"{L}{base}"].value, "Saisie_Locaux", 15 * k)
        # 2. MEX-17 (type de commande) : #REF! -> choix unique saisi ligne 29
        cl[f"{L}15"] = (cl[f"{L}14"].value.replace(f"Calc_Locaux!{L}$12", f"Calc_Locaux!{L}$14")
                        .replace(f"Saisie_Locaux!{L}$28", f"Saisie_Locaux!{L}$29"))
        # 3. BA-18 (débit maximal de ventilation) : #REF! -> question ajoutée
        cl[f"{L}65"] = re.sub(r"IF\(ISNUMBER\(Saisie_Locaux!#REF!\),Saisie_Locaux!#REF!,\"#INC\"\)",
                              f'IF(ISNUMBER(Saisie_Locaux!{L}${LIGNE_BA18}),Saisie_Locaux!{L}${LIGNE_BA18},"#INC")',
                              cl[f"{L}65"].value)
        # 4. FT-7 : « MEX-17 ne contient ni Électrique ni Automatique »
        G = get_column_letter(col + 3)
        c15 = f"Calc_Locaux!{L}$15"
        rl[f"{G}109"] = re.sub(
            r'IF\(OR\(Saisie_Locaux!#REF!<>"",Saisie_Locaux!#REF!<>""\),0,1\)',
            f'IF(OR({c15}="Électrique",{c15}="Automatique (sans action humaine)"),0,1)', rl[f"{G}109"].value)
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                assert not (isinstance(c.value, str) and c.value.startswith("=") and "#REF!" in c.value), (ws.title, c.coordinate)


# ------------------------------------------------------------------ tirage aléatoire
SEUILS = [0, 1, 1.4, 1.5, 2, 2.39, 2.4, 2.5, 2.6, 3, 5, 6, 15, 16, 19, 20, 29, 30, 31, 54, 99, 100, 149, 150, 200, 500]


def _reponse(q, rnd, p_vide, pref=None):
    """``pref`` : rang d'option privilégié (réponses corrélées, pour atteindre les règles de
    faible priorité qui supposent que toutes les précédentes sont fausses)."""
    if rnd.random() < p_vide:
        return None
    t = q["type"]
    if t in ("choix", "multi") and pref is not None and rnd.random() < 0.75:
        o = q["options"][pref if -len(q["options"]) <= pref < len(q["options"]) else -1]
        return o if t == "choix" else [o]
    if t == "choix":
        return rnd.choice(q["options"])
    if t == "multi":
        return rnd.sample(q["options"], rnd.choice([1, 1, 1, 2, 3])) or None
    if t == "nombre":
        return rnd.choice(SEUILS) if rnd.random() < 0.7 else round(rnd.uniform(0, 300), 2)
    if t == "texte":
        return "Nom %d" % rnd.randint(1, 99)
    return None


def _pref(rnd):
    return rnd.choice([None, None, 0, 0, 1, 1, 2, -1])


def _entite(sections, rnd, p_vide):
    d, pref = {}, _pref(rnd)
    if pref is not None:
        p_vide = min(p_vide, 0.1)
    for s in sections:
        for q in s["questions"]:
            v = _reponse(q, rnd, p_vide, pref)
            if v is not None:
                d[q["code"]] = v
    return d


# Profils « sans contrainte » : presque toutes les règles restrictives y sont fausses. En modifiant
# quelques réponses au hasard, on atteint les règles de faible priorité et les règles par défaut.
BASE_BATIMENT = {
    "B-01": "De 1948 à 1974", "B-03": "Maçonnerie", "B-04": "ITI (isolation par l'intérieur)", "B-05": "Non",
    "B-06": "Non", "B-08": "Non", "B-09": "Oui", "B-10": "Simple flux", "B-13": "En fonctionnement", "B-14": "Oui",
    "B-15": "Oui", "B-16": "Oui", "B-18": "Toiture à pentes (tuiles, ardoises, zinc)", "B-21": "Oui",
    "B-22": "En comble perdu", "B-23": ["Bon état (épaisseur régulière et continue)"], "B-24": 20, "B-25": "Oui",
    "B-26": "Oui", "B-27": "Non", "B-28": ["Aucun"]}
BASE_FACADE = {"F-01": True, "F-02": "Non", "F-03": "Oui", "F-04": "Non", "F-05": "Non"}
BASE_MUR = {"orientation": "S", "MEX-04": "Nu intérieur", "MEX-05": 20, "MEX-06": "Bon état", "MEX-07": "Aucun",
            "baies": {"Fenêtre à la française": 2}}
BASE_LOCAL = {
    "L-02": "Classe", "L-03": 60, "L-04": 25, "L-09": "Étage intermédiaire", "L-10": ["Aucun"], "L-11": "Oui",
    "MEX-14": "Non", "MEX-25": "Non", "MEX-26": "Maçonnerie", "MEX-29": ["Aucune"], "MEX-32": "Aucun",
    "MEX-34": "Non", "MEX-36": ["Grilles"], "MEX-37": "Non",
    "PL-01": "Sous-face de dalle ou de plancher béton apparente", "PL-03": 3, "PL-05": "Béton", "BA-05": "Aucun",
    "BA-15": "Oui", "BA-18": 500, "BA-19": ["Aucun"], "ECL-01": "LED",
    "ECL-02": ["Encastré dans le faux plafond (dalle, spot)"]}
BASE_ESPACE = {
    "E-02": ["Cour de récréation", "Préau"], "E-04": ["Élémentaire"], "E-06": 100, "E-09": "0 %", "E-10": ["Aucune"],
    "E-14": 200, "E-15": "Aucune structure", "E-20": ["S"], "E-21": "Aucune", "E-22": "Béton ou maçonnerie pleine",
    "E-23": "Non", "E-24": "Mâts, poteaux ou élément solide existants (mur, préau, bâtiment voisin)", "E-25": "Oui",
    "E-26": "Tuiles", "E-28": "Claire", "E-29": 4, "E-30": 3, "E-31": "Non", "E-32": "Pleine terre ou sol fondable"}


def _muter(base, sections, rnd):
    d = dict(base)
    questions = [q for s in sections for q in s["questions"] if q["type"] != "case"]
    for q in rnd.sample(questions, rnd.choice([0, 1, 1, 2, 3, 5])):
        v = _reponse(q, rnd, 0.15)
        if v is None:
            d.pop(q["code"], None)
        else:
            d[q["code"]] = v
    return d


def tirage(rnd) -> dict:
    d = _tirage_libre(rnd)
    if rnd.random() < 0.5:
        d["batiment"] = _muter(BASE_BATIMENT, R["batiment"], rnd)
    if rnd.random() < 0.5:
        d["facades"] = {o: dict(BASE_FACADE, **({"F-0%d" % rnd.randint(2, 5): rnd.choice(["Oui", "Non"])}
                                                 if rnd.random() < 0.3 else {})) for o in moteur.ORIENTATIONS}
    for i in range(len(d["locaux"])):
        if rnd.random() < 0.5:
            l = _muter(BASE_LOCAL, R["locaux"], rnd)
            murs = [dict(BASE_MUR, orientation=rnd.choice(moteur.ORIENTATIONS)) for _ in range(rnd.choice([1, 1, 2]))]
            if rnd.random() < 0.5:
                murs[0] = (d["locaux"][i].get("murs") or murs)[0]
            l["murs"] = murs
            d["locaux"][i] = l
    for i in range(len(d["espaces"])):
        if rnd.random() < 0.5:
            d["espaces"][i] = _muter(BASE_ESPACE, R["espaces"], rnd)
    return d


def _tirage_libre(rnd) -> dict:
    p_vide = rnd.choice([0.05, 0.15, 0.4])
    bat = _entite(R["batiment"], rnd, p_vide)
    if rnd.random() < 0.15:
        bat["B-24"] = "inconnu"
    facades = {}
    for o in moteur.ORIENTATIONS:
        pref = _pref(rnd)
        f = {q["code"]: _reponse({**q, "type": "choix"}, rnd, 0.1, pref) for q in R["facades"][1:]}
        f = {k: v for k, v in f.items() if v is not None}
        if rnd.random() < 0.8:
            f["F-01"] = True
        facades[o] = f
    locaux = []
    for _ in range(10):
        pv = rnd.choice([0.05, 0.2, 0.5])
        l = _entite(R["locaux"], rnd, pv)
        l.pop("MEX-01", None)
        if rnd.random() > pv:
            l["BA-18"] = rnd.choice([0, 50, 200, 500, 1000, 5000])
        if l.get("BA-06") is not None and rnd.random() < 0.8:
            l["BA-06"] = rnd.choice([1, 2, 3, 4])
        if rnd.random() < 0.12:
            l["aucune_baie"] = True
        murs = []
        for _ in range(rnd.choice([0, 1, 1, 2, 2, 3, 4])):
            m = {}
            for q in R["mur"]:
                if q["type"] == "baies":
                    b = {t: rnd.choice([1, 2, 5, "x"]) for t in rnd.sample(q["options"], rnd.choice([0, 1, 1, 2, 3]))}
                    if b:
                        m["baies"] = b
                else:
                    v = _reponse(q, rnd, 0.1, rnd.choice([None, 0, 1, 2]))
                    if v is not None:
                        m[q["code"]] = v
            murs.append(m)
        while murs and not murs[-1]:
            murs.pop()
        if murs:
            l["murs"] = murs
        locaux.append(l)
    espaces = [_entite(R["espaces"], rnd, rnd.choice([0.05, 0.2, 0.5])) for _ in range(5)]
    return {"batiment": bat, "facades": facades, "locaux": locaux, "espaces": espaces}


# ------------------------------------------------------------------ écriture dans l'Excel
def _ecrire_colonne(ws, plan, col, d):
    for code, (r, typ) in plan["questions"].items():
        if typ == "multi":
            for (c, lab), ro in plan["options"].items():
                if c == code:
                    ws.cell(ro, col).value = "x" if lab in (d.get(code) or []) else None
        else:
            ws.cell(r, col).value = d.get(code)
    if plan["murs"]:
        ws.cell(plan["aucune_baie"], col).value = "x" if d.get("aucune_baie") else None
        murs = d.get("murs") or []
        for i, pm in enumerate(plan["murs"]):
            m = murs[i] if i < len(murs) else {}
            for k, r in pm["questions"].items():
                ws.cell(r, col).value = m.get(k)
            for lab, r in pm["baies"].items():
                ws.cell(r, col).value = (m.get("baies") or {}).get(lab)


def ecrire(wb, d):
    ws = wb["Saisie_Bâtiment"]
    _ecrire_colonne(ws, plan_feuille(ws, fin=47), 4, d["batiment"])
    for i, o in enumerate(moteur.ORIENTATIONS):
        f = d["facades"].get(o, {})
        ws.cell(50, 4 + i).value = "x" if f.get("F-01") else None
        for j, code in enumerate(("F-02", "F-03", "F-04", "F-05")):
            ws.cell(51 + j, 4 + i).value = f.get(code)
    ws = wb["Saisie_Locaux"]
    plan = plan_feuille(ws)
    for i, l in enumerate(d["locaux"]):
        _ecrire_colonne(ws, plan, 4 + i, l)
        ws.cell(LIGNE_BA18, 4 + i).value = l.get("BA-18")
    ws = wb["Saisie_Extérieurs"]
    plan = plan_feuille(ws)
    for i, e in enumerate(d["espaces"]):
        _ecrire_colonne(ws, plan, 4 + i, e)


def recalculer(chemin: Path) -> Path:
    sortie = chemin.parent / "recalc"
    subprocess.run(["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(sortie), str(chemin)],
                   check=True, capture_output=True, timeout=300)
    return sortie / chemin.name


# ------------------------------------------------------------------ comparaison
def _codes(ws):
    return {ws.cell(r, 1).value: r for r in range(4, ws.max_row + 1)
            if ws.cell(r, 1).value in moteur.REGLES}


def _statuts_blocs(ws):
    """{préfixe du bloc: (ligne règle retenue, ligne statut)}"""
    out = {}
    for r in range(4, ws.max_row + 1):
        if ws.cell(r, 4).value == "▶ Règle retenue":
            prefixe = str(ws.cell(r - 1, 1).value).split("-")[0]
            out[prefixe] = (r, r + 2)
    return out


def comparer(wb, d) -> list[str]:
    res = moteur.calculer(d)
    ecarts = []

    def verif(ou, attendu, obtenu):
        if isinstance(attendu, (int, float)) and isinstance(obtenu, (int, float)):
            ok = abs(attendu - obtenu) < 1e-9
        else:
            ok = (attendu or "") == (obtenu or "")
        if not ok:
            ecarts.append(f"{ou}: Excel={attendu!r} Python={obtenu!r}")

    for feuille, cle, saisie, lignes_res in (("Règles_Locaux", "locaux", "Saisie_Locaux", range(6, 18)),
                                             ("Règles_Extérieurs", "espaces", "Saisie_Extérieurs", range(22, 25))):
        ws, wr = wb[feuille], wb["Résultats"]
        codes, blocs = _codes(ws), _statuts_blocs(ws)
        for i, x in enumerate(res[cle]):
            col, nom = 7 + i, f"{cle}[{i}]"
            if not d[cle][i]:
                continue  # colonne vide : l'Excel n'affiche rien
            alertes = {c for s in x["solutions"] for c in s["alertes"]}
            a_verifier = {c for s in x["solutions"] for c in s["alertes_a_verifier"]}
            valeurs = {c: v for b in x["blocs"].values() for c, v in b["valeurs"].items()}
            for code, r in codes.items():
                xl = ws.cell(r, col).value
                if moteur.REGLES[code]["alerte"]:
                    py = x["EX-AL"] if code == "EX-AL" else (1 if code in alertes else 0.5 if code in a_verifier else 0)
                else:
                    py = valeurs[code]
                verif(f"{nom} {code}", xl, py)
            for prefixe, (r_regle, r_statut) in blocs.items():
                b = x["blocs"][prefixe]
                verif(f"{nom} bloc {prefixe} règle", ws.cell(r_regle, col).value, b["regle"] or "(aucune)")
                verif(f"{nom} bloc {prefixe} statut", ws.cell(r_statut, col).value, b["statut"])
            for s, r in zip(x["solutions"], lignes_res):
                assert wr.cell(r, 2).value == s["solution"], (wr.cell(r, 2).value, s["solution"])
                verif(f"{nom} Résultats « {s['solution']} »", wr.cell(r, 4 + i).value, s["statut"])
    return ecarts


def main(n=20, graine=1):
    rnd = random.Random(graine)
    total = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        jeux = []
        for i in range(n):
            wb = openpyxl.load_workbook(REF)
            corriger_classeur(wb)
            d = tirage(rnd)
            ecrire(wb, d)
            wb.save(tmp / f"t{i}.xlsx")
            jeux.append(d)
        subprocess.run(["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(tmp / "recalc"),
                        *[str(tmp / f"t{i}.xlsx") for i in range(n)]], check=True, capture_output=True, timeout=1800)
        for i, d in enumerate(jeux):
            wb = openpyxl.load_workbook(tmp / "recalc" / f"t{i}.xlsx", data_only=True)
            ecarts = comparer(wb, d)
            total += len(ecarts)
            for e in ecarts[:15]:
                print(f"[tirage {i}] {e}")
    print(f"{n} tirages ({n * 10} locaux, {n * 5} espaces) : {total} écart(s)")
    return total


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:]]
    sys.exit(1 if main(*args) else 0)
