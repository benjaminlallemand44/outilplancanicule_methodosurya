"""Partie D — cohérence des sorties : moteur (= tableau à l'écran), CSV, PDF « Résultats » et PDF
« Compte rendu complet », sur une dizaine de saisies variées."""
from __future__ import annotations

import copy
import json
import random
import re
from collections import Counter, defaultdict

import pytest

import fuzz_excel
import sorties
from cas_base import ESPACE, LOCAL, RACINE, SUPPR, donnees, fusion, moteur, mur
from surya import questionnaire as QU
from surya.questions import QUESTIONS_MUR, SECTIONS_BATIMENT, SECTIONS_ESPACE, SECTIONS_LOCAL, visible
from surya.rapport import TYPES_ALERTE, donnee_manquante, generer_pdf

pytest.importorskip("pdfplumber")

EXEMPLE = json.loads((RACINE / "surya" / "exemple.json").read_text(encoding="utf-8"))
REPONSES = QU.lire_csv((RACINE / "surya" / "exemple_questionnaires.csv").read_bytes())[0]
TECHNIQUE = re.compile(r"\bNone\b|\bnan\b|#SO|#INC|\bTrue\b|\bFalse\b|\['|\{'|\[\]|\{\}|&lt;|&amp;|&gt;")


def _complet():
    """Un cas « complet » : plusieurs locaux qui déclenchent des règles variées, deux espaces."""
    locaux = [
        fusion(LOCAL, {"L-01": "CP Soleil", "L-09": "RDC", "murs": [mur(), mur(orientation="N", baies={"Vitrage fixe": 3})],
                       "observations": "Stores cassés côté cour."}),
        fusion(LOCAL, {"L-01": "Bureau direction", "L-02": "Bureau, salle des maîtres, salle de réunion", "L-03": 18,
                       "L-04": 4, "L-10": ["Copieurs, imprimantes"], "L-09": "Dernier niveau",
                       "murs": [mur(orientation="O", MEX_04="Nu extérieur", MEX_05=SUPPR, MEX_07="Faible",
                                    baies={"Fenêtre oscillo-battante": "x", "Vitrage fixe": 2})]}),
        fusion(LOCAL, {"L-01": "Motricité", "L-02": "Salle de motricité, de sport ou d'activité physique",
                       "BA-05": "Présent, hors service", "BA-06": 2, "BA-09": 120, "BA-11": "Non", "MEX-14": "Oui",
                       "MEX-15": ["Fenêtre de toit (type Velux)", "Verrière"], "MEX-16": "Oui", "MEX-17": "Manuelle",
                       "MEX-18": ["Store intérieur"], "MEX-19": "Bon état", "MEX-20": "Fenêtre très ancienne",
                       "MEX-21": "Non", "MEX-22": "Non", "murs": [mur(orientation="SE", MEX_07="Important"),
                                                                   mur(orientation="SO", baies={"Fenêtre à la française": 3})]}),
        fusion(LOCAL, {"L-01": "Classe vide", "aucune_baie": True, "murs": []}),
    ]
    espaces = [fusion(ESPACE, {"E-01": "Cour haute", "E-14": 60}),
               fusion(ESPACE, {"E-01": "Jardin", "E-02": ["Jardin, espace vert"], "E-20": ["N"]})]
    d = donnees(locaux=locaux, espaces=espaces)
    d["audit"] = {"etablissement": "École des Tilleuls", "commune": "Tours", "auditeur": "A. Martin",
                  "date_visite": "12/06/2026", "moa": "Ville de Tours", "adresse": "1 rue des Écoles",
                  "synthese": "Visite réalisée par temps chaud."}
    return d


def _trente_locaux():
    rnd = random.Random(30)
    d = fuzz_excel.tirage(rnd)
    locaux = []
    for i in range(30):
        l = fuzz_excel._muter(fuzz_excel.BASE_LOCAL, moteur.REFERENTIEL["locaux"], rnd)
        l["L-01"] = f"Salle {i + 1:02d}"
        l["murs"] = [dict(fuzz_excel.BASE_MUR, orientation=rnd.choice(moteur.ORIENTATIONS)) for _ in range(rnd.randint(1, 4))]
        locaux.append(l)
    d["locaux"] = locaux
    for i, e in enumerate(d["espaces"]):
        e["E-01"] = f"Espace {i + 1}"
    return d


def _noms_speciaux():
    noms = ["Salle d’arts plastiques « Les Petits » & Cie", "Classe <CM2> \"B\"", "Dortoir 😴 🌡️ maternelle",
            "Réfectoire " + "très long nom de local avec beaucoup de mots " * 4,
            "Saint-Éloi/Œuvre ; çà — n°1"]
    locaux = [fusion(LOCAL, {"L-01": n, "observations": "Ligne 1\nLigne 2 avec <balise> & « guillemets » " + "x" * 300})
              for n in noms]
    d = donnees(locaux=locaux, espaces=[fusion(ESPACE, {"E-01": "Cour « A » & <B> 🌳"})])
    d["audit"] = {"etablissement": "École « L'Envol » & <test> 🎒", "synthese": "Texte\navec retour & <b>gras</b>"}
    return d


def _exemple_usagers():
    d = copy.deepcopy(EXEMPLE)
    d["questionnaires"] = copy.deepcopy(REPONSES)
    d["audit"] = {"etablissement": "École exemple"}
    return d


def _seuils():
    d = donnees(param={"P_HSP_MIN": 2.5, "P_VOL_H": 2.5, "P_PALE_PLAFOND": 0.2})
    return d


JEUX = {
    "exemple Excel": lambda: copy.deepcopy(EXEMPLE),
    "exemple + usagers": _exemple_usagers,
    "complet": _complet,
    "presque vide": lambda: {"locaux": [{}], "espaces": [{}]},
    "30 locaux, 5 espaces": _trente_locaux,
    "noms spéciaux": _noms_speciaux,
    "seuils modifiés": _seuils,
    "locaux seuls": lambda: donnees(espaces=[]),
    "espaces seuls": lambda: donnees(locaux=[]),
    "tirage 1": lambda: fuzz_excel.tirage(random.Random(101)),
    "tirage 2": lambda: fuzz_excel.tirage(random.Random(202)),
}


@pytest.fixture(scope="module")
def sortie(request):
    cache = {}

    def f(nom):
        if nom not in cache:
            d = JEUX[nom]()
            res = moteur.calculer(d)
            cache[nom] = (d, res, generer_pdf(d, complet=False), generer_pdf(d))
        return cache[nom]
    return f


def _noms(res, cle, defaut):
    return [x["nom"] or f"{defaut} {i + 1}" for i, x in enumerate(res[cle])]


def _cp1252(c):
    try:
        c.encode("cp1252")
        return c
    except UnicodeEncodeError:
        return ""  # caractère que les polices standard ne savent pas afficher : retiré des PDF (correctif ANO-16)


def _norm(s):
    return "".join(_cp1252(c) for c in re.sub(r"\s+", "", s or ""))


def _attendu_cellules(res):
    """{(nom, solution): texte attendu dans le tableau de synthèse}"""
    out = {}
    for cle, defaut in (("locaux", "Local"), ("espaces", "Espace")):
        for nom, x in zip(_noms(res, cle, defaut), res[cle]):
            for s in x["solutions"]:
                t = s["statut"] + (" (?)" if donnee_manquante(x, s) else "") + (" (!)" if s["alertes"] else "")
                out[(_norm(nom), s["solution"])] = _norm(t)
    return out


@pytest.mark.parametrize("jeu", list(JEUX))
@pytest.mark.parametrize("complet", [False, True], ids=["PDF résultats", "PDF compte rendu"])
def test_pdf_statuts_identiques_au_moteur(sortie, jeu, complet):
    d, res, pdf_res, pdf_cr = sortie(jeu)
    pdf = pdf_cr if complet else pdf_res
    assert "Pages:" in sorties.info(pdf)
    tabs = sorties.tableaux(pdf)
    noms = _noms(res, "locaux", "Local") + _noms(res, "espaces", "Espace")
    lus = {}
    for _, t in tabs:
        if t and t[0] and t[0][0] == "Solution" and len(t[0]) >= 2 and t[0][1] != "Statut":
            for ligne in t[1:]:
                if len(ligne) > 1 and ligne[1] is not None:
                    for nom, cellule in zip(t[0][1:], ligne[1:]):
                        lus[(_norm(nom), ligne[0])] = _norm(cellule)
    assert lus == _attendu_cellules(res)
    # totaux de la synthèse
    compte = Counter(s["statut"] for x in res["locaux"] + res["espaces"] for s in x["solutions"])
    tot = next(t for _, t in tabs if t and t[0] and t[0][0] == "Recommandé" and len(t) == 2 and t[1][0].isdigit())
    assert dict(zip([_norm(c) for c in tot[0]], [int(n) for n in tot[1]])) == \
           {_norm(st): compte.get(st, 0) for st in (moteur.RECOMMANDE, moteur.A_OPTIMISER, moteur.EN_PLACE,
                                                     moteur.SOUS_RESERVE, moteur.NON_RECOMMANDE, moteur.NON_CONCERNE)}


@pytest.mark.parametrize("jeu", list(JEUX))
def test_csv_identique_au_moteur(sortie, jeu):
    d, res, _, _ = sortie(jeu)
    lignes = sorties.export_csv(res)
    attendu = []
    for cle, typ, defaut in (("locaux", "Local", "Local"), ("espaces", "Espace extérieur", "Espace")):
        for nom, x in zip(_noms(res, cle, defaut), res[cle]):
            for s in x["solutions"]:
                attendu.append({"Type": typ, "Nom": nom, "Groupe": s["groupe"], "Solution": s["solution"],
                                "Statut": s["statut"],
                                "Règle retenue": ", ".join(x["blocs"][b]["regle"] or "(aucune)" for b in s["blocs"]),
                                "Donnée manquante": "oui" if donnee_manquante(x, s) else "non",
                                "Alertes": ", ".join(s["alertes"])})
    assert lignes == attendu
    assert not any(TECHNIQUE.search(v or "") for l in lignes for k, v in l.items() if k != "Nom")


def test_ex_al_dans_toutes_les_sorties():
    d = donnees(espace={"E-02": ["Cour de récréation"], "E-14": 20})
    res = moteur.calculer(d)
    assert res["espaces"][0]["EX-AL"] == 1
    csv_alertes = {l["Alertes"] for l in sorties.export_csv(res) if l["Type"] == "Espace extérieur"}
    assert any("EX-AL" in a for a in csv_alertes)


@pytest.mark.parametrize("jeu", ["exemple Excel", "complet", "30 locaux, 5 espaces", "tirage 1", "noms spéciaux"])
def test_plan_d_action(sortie, jeu):
    d, res, _, pdf = sortie(jeu)
    tabs = [t for _, t in sorties.tableaux(pdf) if t and t[0] and t[0][0] == "Suite"]
    lignes = [l for t in tabs for l in t[1:]]
    attendu = []
    for cle, defaut in (("locaux", "Local"), ("espaces", "Espace")):
        for j in range(len(res[cle][0]["solutions"]) if res[cle] else 0):
            par_classe = defaultdict(list)
            for nom, x in zip(_noms(res, cle, defaut), res[cle]):
                s = x["solutions"][j]
                types = {TYPES_ALERTE.get(a, "INFO") for a in s["alertes"]}
                if s["statut"] in (moteur.RECOMMANDE, moteur.A_OPTIMISER):
                    k = "À valider avant de consulter" if "AL" in types else "Engageable"
                elif s["statut"] == moteur.SOUS_RESERVE:
                    k = "À valider avant de consulter"
                elif s["statut"] == moteur.EN_PLACE:
                    k = "Déjà en place"
                elif s["statut"] == moteur.NON_RECOMMANDE:
                    k = "Exclue (non recommandée ou non adaptée)"
                else:
                    continue
                par_classe[k].append((_norm(k), _norm(nom), _norm(s["statut"])))
            for k in ("Engageable", "À valider avant de consulter", "Déjà en place", "Exclue (non recommandée ou non adaptée)"):
                attendu += par_classe[k]
    obtenu = [(_norm(l[0]), _norm(l[1]), _norm(l[2])) for l in lignes]
    assert obtenu == attendu
    assert not any(_norm(moteur.NON_CONCERNE) == o[2] for o in obtenu)
    for suite, _, statut in obtenu:
        if suite == _norm("Engageable"):
            assert statut in (_norm(moteur.RECOMMANDE), _norm(moteur.A_OPTIMISER))


def _baies_attendues(l):
    if l.get("aucune_baie"):
        return "aucune baie en façade"
    tot, nc, ordre = Counter(), set(), []
    for m in (l.get("murs") or [])[:4]:
        o = m.get("orientation")
        if not o:
            continue
        for n in (m.get("baies") or {}).values():
            if isinstance(n, int) and n > 0:
                tot[o] += n
            else:
                nc.add(o)
    parts = []
    for o in moteur.ORIENTATIONS:
        if o in tot or o in nc:
            p = []
            if tot[o]:
                p.append(f"{tot[o]} baie{'s' if tot[o] > 1 else ''}")
            if o in nc:
                p.append("nombre non relevé")
            parts.append(f"{o} : " + " + ".join(p))
    return " ; ".join(parts) or "baies non décrites"


@pytest.mark.parametrize("jeu", ["exemple Excel", "complet", "30 locaux, 5 espaces"])
def test_quantites_baies_par_orientation(sortie, jeu):
    d, res, _, pdf = sortie(jeu)
    tabs = [t for _, t in sorties.tableaux(pdf) if t and t[0] and t[0][0] == "Suite"]
    noms = dict(zip(map(_norm, _noms(res, "locaux", "Local")), d["locaux"]))
    vus = 0
    for t in tabs:
        for l in t[1:]:
            if _norm(l[1]) in noms and ("baie" in (l[3] or "")):
                assert _norm(l[3]) == _norm(_baies_attendues(noms[_norm(l[1])])), (l[1], l[3])
                vus += 1
    assert vus


def test_quantites_somme_des_baies_a_la_main():
    """Vérification à la main : S 2 + S 3 (deux murs S) = 5 ; E « x » = non relevé ; NO 0 baie."""
    l = fusion(LOCAL, {"murs": [mur(baies={"Fenêtre à la française": 2}), mur(baies={"Vitrage fixe": 3}),
                                mur(orientation="E", baies={"Baie coulissante": "x", "Porte extérieure": 1})]})
    from surya.rapport import quantites
    assert quantites("Protections verticales", l) == "E : 1 baie + nombre non relevé ; S : 5 baies"


def test_quantites_zero_baie():
    from surya.rapport import quantites
    l = fusion(LOCAL, {"murs": [mur(orientation="NO", baies={"Vitrage fixe": 0})]})
    assert not quantites("Protections verticales", l).rstrip().endswith(":")


@pytest.mark.parametrize("jeu", list(JEUX))
def test_donnees_manquantes_et_alertes(sortie, jeu):
    d, res, pdf_res, pdf_cr = sortie(jeu)
    for pdf in (pdf_res, pdf_cr):
        tabs = [t for _, t in sorties.tableaux(pdf)]
        dm = [l for t in tabs if t and t[0] == ["Local / espace", "Solution", "À compléter"] for l in t[1:]]
        attendu = []
        for cle, defaut in (("locaux", "Local"), ("espaces", "Espace")):
            for nom, x in zip(_noms(res, cle, defaut), res[cle]):
                for s in x["solutions"]:
                    if donnee_manquante(x, s):
                        attendu.append((_norm(nom), s["solution"]))
                        b = [x["blocs"][k] for k in s["blocs"]]
                        regles = [bl["regle"] for bl in b if bl["regle"]]
                        ligne = next(l for l in dm if (_norm(l[0]), l[1]) == (_norm(nom), s["solution"]))
                        # « À compléter » ne cite que des questions de la règle, et au moins une (ANO-35)
                        for r in regles:
                            prevues = re.findall(r"[A-Z]{1,3}-\d+", moteur.REGLES[r]["questions"])
                            citees = re.findall(r"[A-Z]{1,3}-\d+", ligne[2].split("compléter")[-1])
                            if prevues:
                                assert citees and set(citees) <= set(prevues), (nom, s["solution"], citees, ligne[2])
        assert [(_norm(l[0]), l[1]) for l in dm] == attendu
        # alertes : code -> entités concernées
        al = [l for t in tabs if t and t[0] == ["Type", "Code", "Alerte", "Concerne"] for l in t[1:]]
        lues = {l[1]: _norm(l[3]) for l in al}
        att = defaultdict(list)
        for cle, defaut in (("locaux", "Local"), ("espaces", "Espace")):
            for nom, x in zip(_noms(res, cle, defaut), res[cle]):
                codes = ([] if x.get("EX-AL") != 1 else ["EX-AL"]) + [a for s in x["solutions"] for a in s["alertes"]]
                for a in dict.fromkeys(codes):
                    att[a].append(nom)
        assert lues == {a: _norm(", ".join(n)) for a, n in att.items()}
        for l in al:
            assert l[2] and len(l[2]) > 15, l  # chaque code a son libellé
            assert TYPES_ALERTE[l[1]] in ("AL", "VA", "INFO")


@pytest.mark.parametrize("jeu", list(JEUX))
def test_aucune_fuite_technique(sortie, jeu):
    d, res, pdf_res, pdf_cr = sortie(jeu)
    for pdf in (pdf_res, pdf_cr):
        t = sorties.texte(pdf)
        fuites = sorted({m.group(0) for m in TECHNIQUE.finditer(t)})
        assert not fuites, fuites


def _fiches(pdf, res):
    """{nom: [(code, valeur)]} lus dans les tableaux « Relevé de visite » des fiches."""
    import io
    import pdfplumber
    noms = [n for n in _noms(res, "locaux", "Local") + _noms(res, "espaces", "Espace")]
    out, courant = defaultdict(list), "Bâtiment"
    with pdfplumber.open(io.BytesIO(pdf)) as p:
        commence = False
        for page in p.pages:
            txt = page.extract_text() or ""
            if "Annexe G — Fiches détaillées" in txt:
                commence = True
            if not commence:
                continue
            if "Annexe H — Seuils utilisés" in txt:
                break
            lignes = [l.strip() for l in txt.splitlines() if l.strip()]
            for l in lignes[:3]:
                if l in noms:
                    courant = l
            for t in page.extract_tables():
                for ligne in t:
                    if len(ligne) == 2 and ligne[0] and "·" in ligne[0]:
                        code = ligne[0].rsplit("·", 1)[1].strip()
                        out[courant].append((code, " ".join((ligne[1] or "").split())))
    return out


@pytest.mark.parametrize("jeu", ["exemple Excel", "complet", "tirage 1", "tirage 2"])
def test_fiches_reprennent_les_reponses_sans_question_masquee(sortie, jeu):
    from surya.rapport import _reponse
    d, res, _, pdf = sortie(jeu)
    fiches = _fiches(pdf, res)
    cb = res["batiment"]

    def attendu(sections, ent, c):
        out = []
        for s in sections:
            for q in s["questions"]:
                if q["type"] == "case":
                    continue
                if visible(q["code"], c, ent, cb):
                    out.append((q["code"].removesuffix("b"), _reponse(ent.get(q["code"]))))
        return out
    assert [(c, v) for c, v in fiches["Bâtiment"]] == [(c, " ".join(v.split())) for c, v in
                                                        attendu(SECTIONS_BATIMENT, d.get("batiment") or {}, cb)]
    for cle, sections, defaut in (("locaux", SECTIONS_LOCAL, "Local"), ("espaces", SECTIONS_ESPACE, "Espace")):
        for nom, ent, x in zip(_noms(res, cle, defaut), d[cle], res[cle]):
            if nom in ("Bâtiment",):
                continue
            att = [(c, " ".join(v.split())) for c, v in attendu(sections, ent, x["etats"])]
            assert fiches[nom] == att, nom


def test_tableau_des_murs_sans_question_masquee():
    d = donnees(local={"murs": [mur(MEX_04="Nu extérieur", MEX_05=7)]})
    t = sorties.texte(generer_pdf(d))
    bloc = t[t.index("Baies en façade"):]
    assert not re.search(r"Nu extérieur\s+7\b", bloc)


def test_page_de_garde_et_annexe(sortie):
    d, res, _, pdf = sortie("complet")
    p1 = sorties.pages(pdf)[0]
    for k in ("etablissement", "commune", "auditeur", "date_visite", "moa", "adresse"):
        assert d["audit"][k] in p1, k
    assert "4 local(aux), 2 espace(s)" in p1
    annexe = sorties.texte(pdf).split("Annexe H — Seuils utilisés")[1]
    assert "(modifié)" not in annexe
    d2, _, _, pdf2 = sortie("seuils modifiés")
    annexe2 = sorties.texte(pdf2).split("Annexe H — Seuils utilisés")[1]
    assert annexe2.count("(modifié)") == 3
    for nom in ("P_HSP_MIN", "P_VOL_H", "P_PALE_PLAFOND"):
        ligne = next(l for l in annexe2.splitlines() if nom in l)
        assert "(modifié)" in ligne, ligne


def test_decimales_a_la_francaise(sortie):
    d, res, _, pdf = sortie("seuils modifiés")
    annexe = sorties.texte(pdf).split("Annexe H — Seuils utilisés")[1].split("Méthode SURYA : ©")[0]  # hors « CC BY-SA 4.0 »
    assert not re.search(r"\d\.\d", annexe)


@pytest.mark.parametrize("jeu", list(JEUX))
def test_pas_de_debordement(sortie, jeu):
    d, res, pdf_res, pdf_cr = sortie(jeu)
    for pdf in (pdf_res, pdf_cr):
        assert not sorties.debordements(pdf)


def test_partie_usagers_et_numerotation(sortie):
    _, _, _, avec = sortie("exemple + usagers")
    _, _, _, sans = sortie("exemple Excel")
    ta, ts = sorties.texte(avec), sorties.texte(sans)
    assert "3. Ressenti des usagers et résultats de la visite" in ta and "4. Pistes d'action, dans l'ordre de mise en œuvre" in ta
    assert "5. Avant de consulter" in ta and "Annexe F — Questionnaire usagers" in ta
    assert "Ressenti des usagers" not in ts and "3. Pistes d'action, dans l'ordre de mise en œuvre" in ts
    assert "4. Avant de consulter" in ts and "Annexe F" not in ts
    # ordre : synthèse et bâtiment d'abord, détail en annexe
    for t in (ta, ts):
        pos = [t.index(x) for x in ("1. Synthèse", "2. Le bâtiment et le périmètre visité", "Pistes d'action",
                                     "Annexe A —", "Annexe B —", "Annexe C —", "Annexe G —", "Annexe H —")]
        assert pos == sorted(pos)


def test_numerotation_sans_entite():
    t = sorties.texte(generer_pdf({"batiment": {"B-01": "Avant 1948"}}))
    assert "Pistes d'action" not in t and "1. Synthèse" in t and "Annexe G — Fiches détaillées" in t


def test_synthese_tient_sur_une_page(sortie):
    """La synthèse (partie 1) tient sur la page qui suit la page de garde."""
    for jeu in ("exemple Excel", "complet", "30 locaux, 5 espaces", "exemple + usagers"):
        _, _, _, pdf = sortie(jeu)
        p = sorties.pages(pdf)
        assert "1. Synthèse" in p[1] and "Points de vigilance" in p[1], jeu
        assert "2. Le bâtiment et le périmètre visité" in p[2], jeu


def test_pdf_cas_degeneres():
    for d in ({}, {"locaux": [], "espaces": []}, {"locaux": [{}]}, {"espaces": [{}]},
              {"questionnaires": REPONSES[:1]}, {"locaux": [{}], "questionnaires": REPONSES}):
        for complet in (True, False):
            assert generer_pdf(d, complet=complet).startswith(b"%PDF")


def test_emojis_lisibles_dans_les_pdf(sortie):
    import io
    import pdfplumber
    _, _, pdf_res, _ = sortie("noms spéciaux")
    with pdfplumber.open(io.BytesIO(pdf_res)) as p:
        carres = [c for page in p.pages for c in page.chars if "Zapf" in c["fontname"]]
    assert not carres


# ------------------------------------------------------------------ ergonomie des « données manquantes »
def test_toiture_sans_bloc_n_est_pas_une_donnee_manquante():
    from cas_base import DERNIER, solution
    x = moteur.calculer(donnees(bat={"B-21": "Non"}, local=DERNIER))["locaux"][0]
    assert not donnee_manquante(x, solution(x, "Toiture"))


def test_a_completer_ne_cite_que_les_questions_vides():
    from cas_base import SUPPR as S_, solution
    from surya.rapport import justification
    x = moteur.calculer(donnees(local={"BA-18": S_}))["locaux"][0]
    texte = justification(x, solution(x, "Par ventilation mécanique nocturne"))[1]
    assert "BA-18" in texte and "L-03" not in texte


# ------------------------------------------------------------------ ordre de mise en œuvre et plan simplifié
def test_phases_de_mise_en_oeuvre():
    from surya.rapport import phase
    R, O = moteur.RECOMMANDE, moteur.A_OPTIMISER
    assert phase("Occupation", R) == phase("Équipements", R) == 1
    assert phase("Par ventilation naturelle nocturne", R) == 1
    assert phase("Par ventilation naturelle nocturne", R, ["VN-AL1"]) == 2  # grilles ou ventelles à poser
    assert phase("Mise en place de brasseurs d'air plafonniers", O) == 1  # remise en service
    assert phase("Mise en place de brasseurs d'air plafonniers", R) == 2
    assert phase("Films solaires", R) == phase("Éclairage", R) == 2
    assert phase("Protections verticales", O) == 1 and phase("Protections verticales", R) == 3
    for sol in ("Toiture", "Ombrage rapporté adossé au bâtiment", "Adaptation d'un préau existant"):
        assert phase(sol, R) == 3


def test_toute_solution_a_une_phase():
    from surya.rapport import phase
    res = moteur.calculer({"locaux": [{}], "espaces": [{}]})
    for x in res["locaux"] + res["espaces"]:
        for s in x["solutions"]:
            for st in (moteur.RECOMMANDE, moteur.A_OPTIMISER, moteur.SOUS_RESERVE):
                assert phase(s["solution"], st) in (1, 2, 3)


@pytest.mark.parametrize("jeu", list(JEUX))
def test_pistes_par_etape_reprennent_toutes_les_solutions_a_engager(sortie, jeu):
    """Chaque couple « à engager » de l'annexe C apparaît dans les pistes (partie 3 ou 4)."""
    d, res, _, pdf = sortie(jeu)
    if not (res["locaux"] or res["espaces"]):
        return
    t = " ".join(sorties.texte(pdf).split())
    pistes = t[t.index("Pistes d'action, dans l'ordre"):t.index("Avant de consulter")]
    for cle, defaut in (("locaux", "Local"), ("espaces", "Espace")):
        for nom_, x in zip(_noms(res, cle, defaut), res[cle]):
            if any(s["statut"] in (moteur.RECOMMANDE, moteur.A_OPTIMISER) for s in x["solutions"]):
                assert _norm(nom_) in _norm(pistes), nom_
    etapes = [e for e in ("Étape 1 — Dès maintenant", "Étape 2 — Petits travaux", "Étape 3 — Travaux sur le bâtiment")
              if e in pistes]
    assert [pistes.index(e) for e in etapes] == sorted(pistes.index(e) for e in etapes)


def test_plan_simplifie():
    from surya import plan
    d = json.loads((RACINE / "surya" / "exemple_ecole_sud.json").read_text(encoding="utf-8"))
    res = moteur.calculer(d)
    lignes = plan._boites(d, res)
    assert [l for l, _ in lignes] == ["Dernier niveau", "RDC", "Extérieur"]
    assert sum(len(b) for _, b in lignes) == len(res["locaux"]) + len(res["espaces"])
    cp = next(b for _, bs in lignes for b in bs if b["nom"].startswith("Classe CP"))
    assert set(cp["orient"]) == {"S", "N"} and cp["n"] == plan.a_engager(res["locaux"][0])
    assert plan.dessin({}, moteur.calculer({})) is None
    s = plan.svg(d, res)
    assert s.startswith("<svg") and 'width="100%"' in s and "Classe CP" in s
    t = sorties.texte(generer_pdf(d))
    assert "Plan simplifié" in t


def test_plan_simplifie_cas_degeneres():
    from surya import plan
    for d in ({"locaux": [{}]}, {"espaces": [{}]}, {"locaux": [{"L-09": "Sous-sol", "L-03": 0}] * 25}):
        res = moteur.calculer(d)
        assert plan.dessin(d, res) is not None and plan.svg(d, res)
