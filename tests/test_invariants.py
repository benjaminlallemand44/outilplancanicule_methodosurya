"""Partie C — invariants du moteur, vérifiés sur des milliers de saisies aléatoires
(générateur ``fuzz_excel.tirage``) et partie B « seuils modifiés »."""
from __future__ import annotations

import copy
import random
import re

import pytest

import fuzz_excel
from cas_base import donnees, moteur
from matrice_dependances import comparer, observer

STATUTS = {moteur.RECOMMANDE, moteur.A_OPTIMISER, moteur.EN_PLACE, moteur.SOUS_RESERVE, moteur.NON_RECOMMANDE,
           moteur.NON_CONCERNE}
SOLUTIONS_LOCAL = ["Mise en place de brasseurs d'air plafonniers", "Par ventilation naturelle nocturne",
                   "Par ventilation mécanique nocturne", "Protections verticales", "Protections horizontales",
                   "Films solaires", "Sur fenêtres de toiture", "Sur vérandas et/ou verrières", "Toiture", "Occupation",
                   "Éclairage", "Équipements"]
SOLUTIONS_ESPACE = ["Ombrage rapporté adossé au bâtiment", "Adaptation d'un préau existant",
                    "Ombrage autoportant ou végétal de la cour"]
# Solutions pour lesquelles la méthode prévoit « Non concerné »
NC_METHODE = {"Sur fenêtres de toiture", "Sur vérandas et/ou verrières", "Toiture", "Adaptation d'un préau existant",
              "Ombrage autoportant ou végétal de la cour"}
# Ajoutées par l'Excel (règles PV-0, PH-0, FS-0, absentes de la méthode) quand « Aucune baie » est coché : QM-02
NC_AUCUNE_BAIE = {"Protections verticales", "Protections horizontales", "Films solaires"}
N = 1500


def tirages(n=N, graine=2026):
    rnd = random.Random(graine)
    for _ in range(n):
        yield fuzz_excel.tirage(rnd)


def test_un_statut_parmi_six_et_non_concerne_prevu():
    for d in tirages():
        res = moteur.calculer(d)
        for l, x in zip(d["locaux"], res["locaux"]):
            assert [s["solution"] for s in x["solutions"]] == SOLUTIONS_LOCAL
            for s in x["solutions"]:
                assert s["statut"] in STATUTS
                if s["statut"] == moteur.NON_CONCERNE:
                    assert s["solution"] in NC_METHODE or (s["solution"] in NC_AUCUNE_BAIE and l.get("aucune_baie")), s
        for x in res["espaces"]:
            assert [s["solution"] for s in x["solutions"]] == SOLUTIONS_ESPACE
            for s in x["solutions"]:
                assert s["statut"] in STATUTS
                assert s["statut"] != moteur.NON_CONCERNE or s["solution"] in NC_METHODE
            assert x["EX-AL"] in (0, 0.5, 1)


def _par_nom(res):
    return {x["nom"]: [(s["statut"], tuple(s["alertes"])) for s in x["solutions"]] + [x.get("EX-AL")]
            for x in res["locaux"] + res["espaces"]}


def test_deterministe_et_independant_de_l_ordre_et_des_noms():
    rnd = random.Random(5)
    for d in tirages(300, 9):
        for k, x in enumerate(d["locaux"]):
            x["L-01"] = f"L{k}"
        for k, x in enumerate(d["espaces"]):
            x["E-01"] = f"E{k}"
        ref = _par_nom(moteur.calculer(d))
        assert ref == _par_nom(moteur.calculer(copy.deepcopy(d)))
        d2 = copy.deepcopy(d)
        rnd.shuffle(d2["locaux"])
        rnd.shuffle(d2["espaces"])
        assert _par_nom(moteur.calculer(d2)) == ref
        # renommer (accents, apostrophes, emoji) ne change aucun statut
        d3 = copy.deepcopy(d)
        for k, x in enumerate(d3["locaux"]):
            x["L-01"] = f"L{k} — salle d'arts & « co » <b> 🌡️"
        res3 = moteur.calculer(d3)
        assert [[s["statut"] for s in x["solutions"]] for x in res3["locaux"]] == \
               [[s["statut"] for s in x["solutions"]] for x in moteur.calculer(d)["locaux"]]


def test_un_local_ne_change_pas_les_autres():
    """Ajouter ou retirer un local ne change rien aux autres locaux ; pour les espaces, seule l'alerte
    OA-AL1 peut changer."""
    for d in tirages(300, 13):
        ref = moteur.calculer(d)
        for i in range(len(d["locaux"])):
            d2 = copy.deepcopy(d)
            del d2["locaux"][i]
            res = moteur.calculer(d2)
            autres = ref["locaux"][:i] + ref["locaux"][i + 1:]
            assert [[(s["statut"], s["alertes"]) for s in x["solutions"]] for x in res["locaux"]] == \
                   [[(s["statut"], s["alertes"]) for s in x["solutions"]] for x in autres]
            for x0, x1 in zip(ref["espaces"], res["espaces"]):
                for s0, s1 in zip(x0["solutions"], x1["solutions"]):
                    assert s0["statut"] == s1["statut"]
                    assert set(s0["alertes"]) - {"OA-AL1"} == set(s1["alertes"]) - {"OA-AL1"}


def test_matrice_de_dependances_sans_dependance_inattendue():
    """Toute solution touchée par une question doit être prévue par la colonne « Questions » des règles
    (ou par la sélection du cas). Les questions [info] n'ont aucun effet."""
    lignes = comparer(observer(25, 3))
    inattendues = {q: inat for q, info, o, inat, _ in lignes if inat}
    assert not inattendues
    assert not [q for q, info, o, _, _ in lignes if info and o]


@pytest.mark.xfail(strict=True, reason="C1 (documenté) : B-07 n'a aucun effet et n'est pas marquée [info]")
def test_toute_question_non_info_a_un_effet():
    lignes = comparer(observer(25, 3))
    sans_effet = [q for q, info, o, _, _ in lignes if not info and not o]
    assert "B-07" not in sans_effet


# ------------------------------------------------------------------ marqueur « donnée manquante »
SIMPLES = re.compile(r"^(B|L|PL|BA|ECL|E|MEX)-\d+$")
MUR = {"MEX-01", "MEX-04", "MEX-05", "MEX-06", "MEX-07", "MEX-08"}


def _remplir(ent: dict, code: str, sections):
    q = next((q for s in sections for q in s["questions"] if q["code"] == code), None)
    inconnus = (None, "", [], ["Non évalué"], *moteur._INCONNUS)
    if q is None or ent.get(code) not in inconnus and \
            not (q["type"] == "nombre" and not isinstance(ent.get(code), (int, float))):
        return
    t = q["type"]
    opts = [o for o in q.get("options", []) if o not in ("Non évalué", "Pas d'information", "Non renseigné")]
    ent[code] = {"choix": opts[0] if opts else None, "multi": [opts[0]] if opts else None,
                 "nombre": 10, "texte": "x"}.get(t)


def test_repondre_leve_le_marqueur_donnee_manquante():
    """Si une règle est retenue faute de donnée, répondre à toutes les questions qu'elle cite (colonne
    « Questions ») doit la trancher. Vérifie que la colonne « Questions » est complète."""
    from surya.questions import SECTIONS_BATIMENT, SECTIONS_ESPACE, SECTIONS_LOCAL
    vus, defauts = 0, []
    for d in tirages(400, 21):
        res = moteur.calculer(d)
        for cle, sections in (("locaux", SECTIONS_LOCAL), ("espaces", SECTIONS_ESPACE)):
            for i, x in enumerate(res[cle]):
                retenus = {b for sol in x["solutions"] for b in sol["blocs"]}
                for nom_bloc, bl in x["blocs"].items():
                    r = bl["regle"]
                    if nom_bloc not in retenus:
                        continue
                    if not (r and bl["manquante"]):
                        continue
                    qs = re.findall(r"[A-Z]{1,3}-\d+", moteur.REGLES[r]["questions"])
                    if any(q in MUR or q.startswith("F-") for q in qs):
                        continue
                    d2 = copy.deepcopy(d)
                    ent = d2[cle][i]
                    for _ in range(3):  # les questions conditionnelles se révèlent en cascade
                        for q in qs:
                            if q.startswith("B-"):
                                _remplir(d2["batiment"], q, SECTIONS_BATIMENT)
                            else:
                                _remplir(ent, q, sections)
                    x2 = moteur.calculer(d2)[cle][i]
                    v = x2["blocs"][nom_bloc]["valeurs"][r]
                    vus += 1
                    if v == 0.5:
                        defauts.append((r, {q: ent.get(q, d2["batiment"].get(q)) for q in qs}))
    assert vus > 200
    assert not defauts, defauts[:5]


# ------------------------------------------------------------------ seuils modifiés (partie B)
PARAMS = {p["nom"]: p for p in moteur.REFERENTIEL["parametres"]}


def _valeurs_regles(d):
    res = moteur.calculer(d)
    out = {}
    for cle in ("locaux", "espaces"):
        for i, x in enumerate(res[cle]):
            for b in x["blocs"].values():
                for c, v in b["valeurs"].items():
                    out[(cle, i, c)] = v
            if cle == "espaces":
                out[(cle, i, "EX-AL")] = x["EX-AL"]
    return out


@pytest.mark.parametrize("nom", list(PARAMS))
def test_seuil_modifie_ne_touche_que_ses_regles(nom):
    p = PARAMS[nom]
    prevues = set(re.findall(r"[A-Z]{2}-[A-Z0-9]+", p["regles"]))
    if "EX-AL" in prevues:
        prevues.add("PR-AL4")
    touchees = set()
    for d in tirages(150, 31):
        ref = _valeurs_regles(d)
        for facteur in (0.5, 1.5, 3):
            d2 = dict(d, parametres={nom: p["valeur"] * facteur})
            new = _valeurs_regles(d2)
            touchees |= {k[2] for k in ref if ref[k] != new[k]}
    assert touchees, f"{nom} n'a aucun effet"
    assert touchees <= prevues, touchees - prevues


SEUILS_CAS = [
    # (paramètre, nouvelle valeur, données, bloc, (règle avant, règle après))
    ("P_HSP_MIN", 2.5, {"local": {"PL-03": 2.45}}, "BS", ("BS-3", "BS-1")),
    ("P_HSP_CONF", 2.5, {"local": {"PL-03": 2.55}}, "BS", ("BS-3", "BS-7")),
    ("P_PLENUM", 1.0, {"local": {"PL-01": "Faux plafond démontable (dalles sur ossature)", "PL-02": 0.8}}, "BS", ("BS-4", "BS-7")),
    ("P_TABLEAU", 10, {"local": {"murs": [{"orientation": "S", "MEX-04": "Nu intérieur", "MEX-05": 12, "MEX-06": "Bon état",
                                           "MEX-07": "Aucun", "baies": {"Fenêtre à la française": 1}}]}}, "PV", ("PV-2", "PV-8")),
    ("P_ISOL_TOIT", 40, {"bat": {"B-18": "Toiture-terrasse", "B-19": "Isolée", "B-20": 35}, "local": {"L-09": "Dernier niveau"}}, "TT", ("TT-2", "TT-3")),
    ("P_ISOL_COMBLE", 20, {"bat": {"B-24": 25}, "local": {"L-09": "Dernier niveau"}}, "CP", ("CP-7", "CP-3")),
    ("P_ISOL_RAMPANT", 30, {"bat": {"B-22": "Sous pente", "B-24": 25}, "local": {"L-09": "Dernier niveau"}}, "CA", ("CA-3", "CA-2")),
    ("P_BUREAU_M2", 4, {"local": {"L-02": "Bureau, salle des maîtres, salle de réunion", "L-03": 20, "L-04": 4}}, "CO", ("CO-1", "CO-3")),
    ("P_CLASSE_M2", 3, {}, "CO", ("CO-3", "CO-2")),
    ("P_VOL_H", 3, {}, "VM", ("VM-7", "VM-10")),
    ("P_PREAU_H", 5, {"espace": {"E-26": "Bac acier ou tôle, non isolé"}}, "PR", ("PR-6", "PR-5")),
    ("P_PREAU_FERME", 3, {"espace": {"E-30": 2, "E-26": "Bac acier ou tôle, isolé", "E-28": "Moyenne"}}, "PR", ("PR-3", "PR-4")),
    ("P_PREAU_OUVERT", 0, {}, "PR", ("PR-6", "PR-7")),
    ("P_PALE_PLAFOND", 0.3, {"local": {"BA-05": "Présent et fonctionnel", "BA-06": 1, "BA-09": 200, "BA-11": "Oui",
                                        "BA-12": 250, "BA-13": 250}}, "BP", ("BP-5", "BP-3")),
    ("P_ENTRAXE", 1.5, {"local": {"BA-05": "Présent et fonctionnel", "BA-06": 2, "BA-09": 200, "BA-11": "Oui", "BA-12": 250,
                                   "BA-13": 250, "L-03": 240, "BA-14": 450}}, "BP", ("BP-4", "BP-5")),
    ("P_DIAM_MIN", 0.3, {"local": {"BA-05": "Présent et fonctionnel", "BA-06": 1, "BA-09": 200, "BA-11": "Oui",
                                    "BA-12": 250, "BA-13": 250}}, "BP", ("BP-5", "BP-4")),
    ("P_DIAM_MAX", 0.25, {"local": {"BA-05": "Présent et fonctionnel", "BA-06": 1, "BA-09": 200, "BA-11": "Oui",
                                     "BA-12": 250, "BA-13": 250}}, "BP", ("BP-5", "BP-4")),
]


@pytest.mark.parametrize("nom,val,kw,bloc,regles", SEUILS_CAS, ids=[s[0] for s in SEUILS_CAS])
def test_seuil_modifie_deplace_la_limite(nom, val, kw, bloc, regles):
    from cas_base import evaluer
    if nom == "P_PREAU_OUVERT":  # PR-6 « au plus 1 côté fermé » ; à 0, un préau à 1 côté n'est plus ouvert
        assert evaluer(donnees(**kw), bloc)[0] == regles[0]
        assert evaluer(donnees(**kw, param={nom: val}), bloc)[0] == regles[1]
        return
    assert evaluer(donnees(**kw), bloc)[0] == regles[0]
    assert evaluer(donnees(**kw, param={nom: val}), bloc)[0] == regles[1]


@pytest.mark.parametrize("nom,val,attendu", [("P_OMBRE_ELEM", 1.0, 1), ("P_OMBRE_MAT_CL", 4, 1), ("P_OMBRE_MAT_1", 80, 0),
                                             ("P_OMBRE_MAT_2", 100, 0)])
def test_seuils_ex_al(nom, val, attendu):
    e = {"E-14": 90, "E-06": 100} if nom == "P_OMBRE_ELEM" else {"E-04": ["Maternelle"], "E-07": 5, "E-14": 90}
    if nom == "P_OMBRE_MAT_CL":
        e["E-14"] = 120
    if nom == "P_OMBRE_MAT_2":
        e = {"E-04": ["Maternelle"], "E-07": 6, "E-14": 120}
    avant = moteur.calculer(donnees(espace=e))["espaces"][0]["EX-AL"]
    apres = moteur.calculer(donnees(espace=e, param={nom: val}))["espaces"][0]["EX-AL"]
    assert avant != apres and apres == attendu


@pytest.mark.xfail(strict=True, reason="ANO-07 : un seuil importé en texte (JSON) est accepté ; toutes les comparaisons "
                                       "qui l'utilisent deviennent silencieusement « fausses »")
def test_seuil_texte_refuse_ou_converti():
    d = donnees(local={"PL-03": 2.2}, param={"P_HSP_MIN": "2,4"})
    from cas_base import evaluer
    assert evaluer(d, "BS")[:2] == ("BS-1", moteur.NON_RECOMMANDE)
