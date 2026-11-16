"""Moteur de calcul de la méthode SURYA (audit de faisabilité d'actions d'adaptation).

Reprise en Python de la logique de l'Excel « outil d'aide au test de la méthode » :

* onglets ``Calc_*``   -> fonctions ``etats_*``  (état de chaque réponse) ;
* onglets ``Règles_*`` -> fonctions ``regles_*`` (règles ordonnées par priorité) ;
* onglet ``Résultats`` -> fonction ``calculer``.

Logique à trois valeurs, comme dans l'Excel :

* une réponse vaut ``SO`` (« #SO », question sans objet), ``INC`` (« #INC », donnée
  inconnue) ou la valeur saisie ;
* une condition de règle vaut 1 (vraie), 0 (fausse) ou 0.5 (indéterminée, donnée
  manquante). « ET » = ``min``, « OU » = ``max``.

Dans chaque bloc, la première règle (par ordre de priorité) dont la condition est > 0
est retenue ; si sa condition vaut 0.5, le statut devient « Sous réserve ».

Ce module ne dépend d'aucune interface : il prend des dictionnaires et en renvoie.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

SO = "#SO"
INC = "#INC"

RECOMMANDE = "Recommandé"
A_OPTIMISER = "À optimiser"
SOUS_RESERVE = "Sous réserve"
EN_PLACE = "En place"
NON_RECOMMANDE = "Non recommandé ou non adapté"
NON_CONCERNE = "Non concerné"

ORIENTATIONS = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
NB_MURS_MAX = 4

REFERENTIEL = json.loads((Path(__file__).parent / "referentiel.json").read_text(encoding="utf-8"))
REGLES = REFERENTIEL["regles"]
PARAMETRES_DEFAUT = {p["nom"]: p["valeur"] for p in REFERENTIEL["parametres"]}

_INCONNUS = ("", "Non évalué", "Pas d'information", "Non renseigné")

# Libellés d'options utilisés par les règles
FAUX_PLAFONDS = ("Faux plafond démontable (dalles sur ossature)", "Faux plafond fixe (plaques de plâtre, enduit)")
PRESENT = ("Présent et fonctionnel", "Présent, hors service")
RDC = ("RDC", "RDC et dernier niveau (plain-pied)")
DERNIER_NIVEAU = ("Dernier niveau", "RDC et dernier niveau (plain-pied)")
DEGRADE = ("Dégradé (manœuvre difficile, pièces cassées, pourriture ou corrosion)", "Très dégradé, remplacement à envisager")
BAIES_FIXES = ("Vitrage fixe", "Façade vitrée continue (mur-rideau)")
BAIES_OSC = ("Fenêtre oscillo-battante", "Imposte en soufflet")
ITE_MEX26 = ("Ossature légère avec bardage ou vêture", "Isolation par l'extérieur (enduit sur isolant, bardage ventilé)")
ITE_B04 = "ITE (isolation par l'extérieur)"


# ------------------------------------------------------------------ primitives
def val(x):
    """Réponse à choix unique ou texte : ``INC`` si vide ou « Non évalué »."""
    return INC if x is None or x in _INCONNUS else x


def num(x):
    """Réponse numérique : ``INC`` si ce n'est pas un nombre."""
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else INC


def multi(selection, options_comptees=None):
    """Réponse à choix multiples : « ok » si au moins une case comptée est cochée."""
    sel = selection or []
    if options_comptees is not None:
        sel = [o for o in sel if o in options_comptees]
    return "ok" if sel else INC


def a(selection, *options) -> bool:
    """Au moins une des options est cochée."""
    return any(o in (selection or []) for o in options)


def t3(etat, test, si_so=0):
    """Test à trois valeurs sur l'état d'une réponse."""
    if etat == SO:
        return si_so
    if etat == INC:
        return 0.5
    return 1 if test else 0


def porte(condition, valeur):
    """État d'une question conditionnelle : ``SO`` si la condition est fausse."""
    if condition == 0:
        return SO
    if condition == 0.5:
        return INC
    return valeur


def calcul(test, *etats):
    """Test numérique sur plusieurs réponses : 0 si l'une est sans objet, 0.5 si inconnue."""
    if SO in etats:
        return 0
    if INC in etats:
        return 0.5
    try:
        return 1 if test(*etats) else 0
    except (ZeroDivisionError, TypeError, ValueError):
        return 0


def bloc(regles):
    """Évalue un bloc de règles ordonnées ``[(code, valeur), ...]``."""
    for code, v in regles:
        if v > 0:
            manquante = v == 0.5
            return {"regle": code, "manquante": manquante,
                    "statut": SOUS_RESERVE if manquante else REGLES[code]["statut"],
                    "valeurs": dict(regles)}
    return {"regle": None, "manquante": True, "statut": SOUS_RESERVE, "valeurs": dict(regles)}


def _solution(groupe, nom, statut, blocs, alertes=()):
    """Ligne de résultat. ``blocs`` : blocs de règles évalués (dans l'ordre de lecture)."""
    return {"groupe": groupe, "solution": nom, "statut": statut, "blocs": blocs,
            "alertes": [c for c, v in alertes if v == 1],
            "alertes_a_verifier": [c for c, v in alertes if v == 0.5]}


# ------------------------------------------------------------------ bâtiment
def etats_batiment(b: dict, facades: dict) -> dict:
    """Onglet Calc_Bâtiment. ``facades`` : {orientation: {"F-01": bool, "F-02": ..., ...}}."""
    c = {}
    for k in ("B-01", "B-03", "B-04", "B-05", "B-06", "B-07", "B-08", "B-09", "B-18", "B-21"):
        c[k] = val(b.get(k))
    vm = t3(c["B-09"], c["B-09"] == "Oui")
    c["B-10"] = porte(vm, val(b.get("B-10")))
    c["B-11"] = porte(t3(c["B-10"], c["B-10"] == "Double flux"), val(b.get("B-11")))
    c["B-12"] = porte(t3(c["B-11"], c["B-11"] == "Oui"), val(b.get("B-12")))
    for k in ("B-13", "B-14", "B-15"):
        c[k] = porte(vm, val(b.get(k)))
    c["B-16"] = porte(t3(c["B-15"], c["B-15"] == "Oui"), val(b.get("B-16")))
    c["B-19"] = porte(t3(c["B-18"], c["B-18"] in ("Toiture-terrasse", "Bac acier ou fibro-ciment")), val(b.get("B-19")))
    c["B-20"] = porte(t3(c["B-19"], c["B-19"] == "Isolée"), num(b.get("B-20")))
    combles = t3(c["B-21"], c["B-21"] == "Oui")
    c["B-22"] = porte(combles, val(b.get("B-22")))
    c["B-23"] = porte(combles, multi(b.get("B-23"), (
        "Bon état (épaisseur régulière et continue)", "Tassée",
        "Discontinue ou partiellement déplacée", "Dégradée (humidité, nuisibles, souillures)")))
    c["B-24"] = porte(combles, num(b.get("B-24")))
    c["B-25"] = porte(combles, val(b.get("B-25")))
    perdus = t3(c["B-22"], c["B-22"] == "En comble perdu")
    c["B-26"] = porte(perdus, val(b.get("B-26")))
    c["B-27"] = porte(combles, val(b.get("B-27")))
    c["B-28"] = porte(perdus, multi(b.get("B-28"), (
        "Spots encastrés", "Conduits de fumée", "Gaines électriques non protégées",
        "Matériaux suspects d'amiante", "Aucun")))
    # Façades : une façade non décrite (F-01 non cochée) est inconnue.
    c["facades"] = {}
    for o in ORIENTATIONS:
        f = (facades or {}).get(o) or {}
        c["facades"][o] = {k: (val(f.get(k)) if f.get("F-01") else INC) for k in ("F-02", "F-03", "F-04", "F-05")}
    return c


def _patrimoine(cb):
    return max(t3(cb["B-05"], cb["B-05"] == "Oui"), t3(cb["B-06"], cb["B-06"] == "Oui"))


# ------------------------------------------------------------------ locaux
def etats_local(l: dict, cb: dict) -> dict:
    """Onglet Calc_Locaux pour un local."""
    c = {}
    for k in ("L-01", "L-02", "L-09", "L-11", "MEX-14", "MEX-25", "MEX-26", "MEX-32", "MEX-34",
              "PL-01", "PL-05", "BA-01", "BA-02", "BA-04", "BA-05", "ECL-01"):
        c[k] = val(l.get(k))
    for k in ("L-03", "L-04", "PL-03"):
        c[k] = num(l.get(k))
    for k in ("L-10", "MEX-29", "MEX-36", "BA-19", "ECL-02"):
        c[k] = multi(l.get(k))

    plafond = t3(c["MEX-14"], c["MEX-14"] == "Oui")
    c["MEX-15"] = porte(plafond, multi(l.get("MEX-15")))
    c["MEX-16"] = porte(plafond, val(l.get("MEX-16")))
    c["MEX-17"] = porte(t3(c["MEX-16"], c["MEX-16"] == "Oui"), val(l.get("MEX-17")))
    c["MEX-18"] = porte(plafond, multi(l.get("MEX-18")))
    c["MEX-19"] = porte(t3(c["MEX-18"], a(l.get("MEX-18"), "Volet extérieur", "Store extérieur", "Store intérieur")),
                        val(l.get("MEX-19")))
    velux = t3(c["MEX-15"], a(l.get("MEX-15"), "Fenêtre de toit (type Velux)"))
    c["MEX-20"] = porte(velux, val(l.get("MEX-20")))
    c["MEX-21"] = porte(velux, val(l.get("MEX-21")))
    c["MEX-22"] = porte(t3(c["MEX-15"], a(l.get("MEX-15"), "Verrière", "Véranda")), val(l.get("MEX-22")))
    c["MEX-24"] = porte(t3(c["MEX-15"], a(l.get("MEX-15"), "Véranda")), val(l.get("MEX-24")))

    c["MEX-25b"] = porte(t3(c["MEX-25"], c["MEX-25"] == "Oui"), multi(l.get("MEX-25b")))
    c["MEX-30"] = porte(t3(c["MEX-29"], a(l.get("MEX-29"), "Volets roulants", "Stores")), val(l.get("MEX-30")))
    c["MEX-33"] = porte(t3(c["MEX-32"], c["MEX-32"] in ("Sur toutes les baies", "Sur une partie des baies")),
                        val(l.get("MEX-33")))
    c["MEX-35"] = porte(t3(c["MEX-34"], c["MEX-34"] == "Oui"), val(l.get("MEX-35")))
    c["MEX-37"] = porte(t3(cb["B-08"], cb["B-08"] == "Oui"), val(l.get("MEX-37")))
    c["PL-02"] = porte(t3(c["PL-01"], c["PL-01"] in FAUX_PLAFONDS), num(l.get("PL-02")))
    c["BA-03"] = porte(t3(c["BA-02"], c["BA-02"] in PRESENT), val(l.get("BA-03")))
    brasseurs = t3(c["BA-05"], c["BA-05"] in PRESENT)
    for k in ("BA-06", "BA-09", "BA-12", "BA-13"):
        c[k] = porte(brasseurs, num(l.get(k)))
    c["BA-11"] = porte(brasseurs, val(l.get("BA-11")))
    c["BA-14"] = porte(calcul(lambda n: n >= 2, c["BA-06"]), num(l.get("BA-14")))
    c["BA-15"] = porte(t3(cb["B-09"], cb["B-09"] == "Oui"), val(l.get("BA-15")))
    c["BA-18"] = porte(t3(c["BA-15"], c["BA-15"] == "Oui"), num(l.get("BA-18")))

    # --- murs extérieurs (4 au maximum) ---
    aucune = bool(l.get("aucune_baie"))
    murs_saisis = [m for m in (l.get("murs") or [])[:NB_MURS_MAX]]
    c["aucune_baie"] = aucune
    c["MURS_INC"] = (not aucune) and not any(m.get("orientation") for m in murs_saisis)
    c["murs"] = []
    for m in murs_saisis:
        actif = 1 if (not aucune and m.get("orientation")) else 0
        ori = m.get("orientation")
        baies = [t for t, n in (m.get("baies") or {}).items() if n not in (None, "", False)]
        ntypes = len(baies)
        nonfixe = len([t for t in baies if t not in BAIES_FIXES])
        e = {"actif": actif, "orientation": ori}
        e["MEX-04"] = porte(actif, val(m.get("MEX-04")))
        e["MEX-05"] = porte(min(actif, t3(e["MEX-04"], e["MEX-04"] in ("Nu intérieur", "En tunnel"))), num(m.get("MEX-05")))
        e["MEX-06"] = porte(actif, val(m.get("MEX-06")))
        e["MEX-07"] = porte(actif, val(m.get("MEX-07")))
        e["NTYPES"] = ntypes
        e["OSC"] = len([t for t in baies if t in BAIES_OSC])
        e["AUTRES"] = len([t for t in baies if t not in BAIES_FIXES and t not in BAIES_OSC])
        e["OUVRANT"] = 0 if not actif else (0.5 if ntypes == 0 else (1 if nonfixe > 0 else 0))
        e["SEULFIXE"] = 1 if not actif else (0.5 if ntypes == 0 else (1 if nonfixe == 0 else 0))
        e["SUD"] = 1 if ori in ("S", "SE", "SO") else 0
        for k in ("F-02", "F-03", "F-04", "F-05"):
            e[k] = SO if not actif else cb["facades"].get(ori, {}).get(k, INC)
        c["murs"].append(e)
    return c


def regles_local(l: dict, c: dict, cb: dict, b: dict, p: dict) -> dict:
    """Onglet Règles_Locaux pour un local. Renvoie les blocs, les solutions et la variable MUT."""
    murs = c["murs"]
    actifs = [m for m in murs if m["actif"]]

    def un_mur(f):  # « au moins un mur tel que… »
        return 0.5 if c["MURS_INC"] else max([f(m) for m in actifs], default=0)

    sans_baie = 1 if c["aucune_baie"] else (0.5 if c["MURS_INC"] else 0)
    ouvrant_facade = 0.5 if c["MURS_INC"] else max([m["OUVRANT"] for m in murs], default=0)
    hors_rdc = t3(c["L-09"], c["L-09"] not in RDC, si_so=1)
    au_rdc = t3(c["L-09"], c["L-09"] in RDC)
    patrimoine = _patrimoine(cb)
    R = {}

    # --- Brasseurs d'air : en place -------------------------------------------------
    cas_bp = t3(c["BA-05"], c["BA-05"] in PRESENT)
    R["BP"] = bloc([
        ("BP-1", t3(c["BA-05"], c["BA-05"] == "Présent, hors service")),
        ("BP-2", t3(c["BA-11"], c["BA-11"] == "Non")),
        ("BP-3", calcul(lambda h, pale, d: (h * 100 - pale) / d <= p["P_PALE_PLAFOND"], c["PL-03"], c["BA-12"], c["BA-09"])),
        ("BP-4", max(
            calcul(lambda d, s, n: not (p["P_DIAM_MIN"] < (d / 100) / (math.sqrt(s) / n) < p["P_DIAM_MAX"]),
                   c["BA-09"], c["L-03"], c["BA-06"]),
            calcul(lambda mur, d: mur <= d, c["BA-13"], c["BA-09"]),
            calcul(lambda e, d: e <= p["P_ENTRAXE"] * d, c["BA-14"], c["BA-09"]))),
        ("BP-5", 1),
    ])
    # --- Brasseurs d'air : pas en place ---------------------------------------------
    cas_bs = t3(c["BA-05"], c["BA-05"] == "Aucun")
    faux_plafond = t3(c["PL-01"], c["PL-01"] in FAUX_PLAFONDS)
    R["BS"] = bloc([
        ("BS-1", calcul(lambda h: h < p["P_HSP_MIN"], c["PL-03"])),
        ("BS-2", max(t3(c["BA-19"], a(l.get("BA-19"), "Baffles acoustiques", "Gaines de ventilation", "Décoration")),
                     t3(c["ECL-02"], a(l.get("ECL-02"), "Suspendu")))),
        ("BS-3", calcul(lambda h: p["P_HSP_MIN"] <= h < p["P_HSP_CONF"], c["PL-03"])),
        ("BS-4", min(faux_plafond, calcul(lambda h: h > p["P_PLENUM"], c["PL-02"]), t3(c["PL-05"], c["PL-05"] == "Béton"))),
        ("BS-5", min(faux_plafond, t3(c["PL-05"], c["PL-05"] != "Béton", si_so=1))),
        ("BS-6", t3(c["PL-01"], c["PL-01"] in ("Plafond bois, lambris, rampants ou charpente apparente", "Autre"))),
        ("BS-7", 1),
    ])
    if cas_bp == 1:
        statut, blocs = R["BP"]["statut"], ["BP"]
    elif cas_bs == 1:
        statut, blocs = R["BS"]["statut"], ["BS"]
    else:
        statut, blocs = SOUS_RESERVE, []
    S = [_solution("Brasseurs d'air plafonniers", "Mise en place de brasseurs d'air plafonniers", statut, blocs,
                   [("BR-AL", 1)])]

    # --- Ventilation naturelle nocturne ---------------------------------------------
    R["VN"] = bloc([
        ("VN-1", min(sans_baie, t3(c["MEX-14"], c["MEX-14"] == "Non"))),
        ("VN-2", min(0.5 if c["MURS_INC"] else min([m["SEULFIXE"] for m in murs], default=1),
                     t3(c["MEX-16"], c["MEX-16"] != "Oui", si_so=1))),
        ("VN-3", t3(c["MEX-30"], c["MEX-30"] == "Non (pleins)")),
        ("VN-4", min(t3(cb["B-08"], cb["B-08"] == "Oui"), t3(c["MEX-37"], c["MEX-37"] == "Oui"))),
        ("VN-5", un_mur(lambda m: t3(m["MEX-06"], m["MEX-06"] in DEGRADE))),
        ("VN-6", 0.5 if (c["MURS_INC"] or any(m["NTYPES"] == 0 for m in actifs)) else
            (1 if sum(m["OSC"] for m in actifs) > 0 and sum(m["AUTRES"] for m in actifs) == 0 else 0)),
        ("VN-7", 0.5 if c["MURS_INC"] else
            (1 if sum(m["OUVRANT"] == 1 for m in murs) >= 2 else
             (0.5 if sum(m["OUVRANT"] > 0 for m in murs) >= 2 else 0))),
        ("VN-8", min(ouvrant_facade, t3(c["MEX-16"], c["MEX-16"] == "Oui"))),
        ("VN-9", min(ouvrant_facade, t3(c["MEX-34"], c["MEX-34"] == "Oui"),
                     t3(c["MEX-35"], c["MEX-35"] in ("Oui, porte standard",
                                                     "Oui, porte coupe-feu avec ventouse asservie à la détection incendie")))),
        ("VN-10", 1),
    ])
    vn = R["VN"]["statut"]
    S.append(_solution("Décharge thermique nocturne", "Par ventilation naturelle nocturne", vn, ["VN"], [
        ("VN-AL1", 0 if vn == NON_RECOMMANDE else
            (1 if t3(c["MEX-36"], not a(l.get("MEX-36"), "Grilles", "Ventelles"), si_so=1) == 1 else 0)),
        ("VN-AL2", 1 if vn == RECOMMANDE else 0),
    ]))

    # --- Ventilation mécanique nocturne ---------------------------------------------
    double_flux = t3(cb["B-10"], cb["B-10"] == "Double flux")
    debit = lambda test: calcul(lambda q, s, h: test(q / (s * h)), c["BA-18"], c["L-03"], c["PL-03"])  # noqa: E731
    R["VM"] = bloc([
        ("VM-1", max(t3(cb["B-09"], cb["B-09"] == "Non"), t3(c["BA-15"], c["BA-15"] == "Non"))),
        ("VM-2", min(t3(cb["B-10"], cb["B-10"] == "Simple flux"), t3(cb["B-14"], cb["B-14"] == "Non"))),
        ("VM-3", t3(cb["B-13"], cb["B-13"] in ("À l'arrêt ou hors service", "Filtres encrassés"))),
        ("VM-4", min(double_flux, t3(cb["B-11"], cb["B-11"] == "Oui"), t3(cb["B-12"], cb["B-12"] == "Non"))),
        ("VM-5", t3(cb["B-15"], cb["B-15"] == "Non")),
        ("VM-6", min(t3(cb["B-15"], cb["B-15"] == "Oui"), t3(cb["B-16"], cb["B-16"] == "Non"))),
        ("VM-7", min(t3(cb["B-16"], cb["B-16"] == "Oui"),
                     max(t3(cb["B-10"], cb["B-10"] != "Double flux", si_so=1), t3(cb["B-12"], cb["B-12"] == "Oui")),
                     debit(lambda v: v >= p["P_VOL_H"]))),
        ("VM-8", min(double_flux, t3(cb["B-11"], cb["B-11"] == "Non"))),
        ("VM-9", 1 if c["BA-18"] == INC else 0),
        ("VM-10", debit(lambda v: v < p["P_VOL_H"])),
        ("VM-11", 1),
    ])
    S.append(_solution("Décharge thermique nocturne", "Par ventilation mécanique nocturne", R["VM"]["statut"], ["VM"]))

    # --- Protections solaires verticales --------------------------------------------
    if c["MEX-26"] not in (INC, SO, "Non identifiable"):
        ite = 1 if c["MEX-26"] in ITE_MEX26 else 0
    else:
        ite = max(t3(cb["B-03"], cb["B-03"] == "Ossature légère"), t3(cb["B-04"], cb["B-04"] == ITE_B04))
    sans_acces = min(hors_rdc, un_mur(lambda m: t3(m["F-03"], m["F-03"] == "Non")))
    obstacle = un_mur(lambda m: t3(m["F-04"], m["F-04"] == "Oui"))
    desordre = un_mur(lambda m: t3(m["F-05"], m["F-05"] == "Oui"))
    alignement = un_mur(lambda m: t3(m["F-02"], m["F-02"] == "Oui"))
    R["PV"] = bloc([
        ("PV-0", sans_baie),
        ("PV-1", un_mur(lambda m: min(t3(m["MEX-04"], m["MEX-04"] == "Nu extérieur"), t3(m["MEX-07"], m["MEX-07"] == "Aucun")))),
        ("PV-2", un_mur(lambda m: min(t3(m["MEX-04"], m["MEX-04"] in ("Nu intérieur", "En tunnel")),
                                      calcul(lambda d: d < p["P_TABLEAU"], m["MEX-05"])))),
        ("PV-3", patrimoine),
        ("PV-4", ite),
        ("PV-5", sans_acces),
        ("PV-6", obstacle),
        ("PV-7", desordre),
        ("PV-8", 1),
    ])
    S.append(_solution("Protections solaires extérieures", "Protections verticales", R["PV"]["statut"], ["PV"]))

    # --- Protections solaires horizontales ------------------------------------------
    debord = lambda niveau: un_mur(lambda m: t3(m["MEX-07"], m["MEX-07"] == niveau) if m["SUD"] else 0)  # noqa: E731
    R["PH"] = bloc([
        ("PH-0", sans_baie),
        ("PH-1", debord("Important")),
        ("PH-2", debord("Faible")),
        ("PH-3", 0.5 if c["MURS_INC"] else (1 if not any(m["SUD"] for m in actifs) else 0)),
        ("PH-4", min(au_rdc, alignement)),
        ("PH-5", patrimoine),
        ("PH-6", min(hors_rdc, alignement)),
        ("PH-7", ite),
        ("PH-8", sans_acces),
        ("PH-9", obstacle),
        ("PH-10", desordre),
        ("PH-11", 1),
    ])
    S.append(_solution("Protections solaires extérieures", "Protections horizontales", R["PH"]["statut"], ["PH"]))

    # --- Films solaires -----------------------------------------------------------------
    R["FS"] = bloc([
        ("FS-0", min(sans_baie, t3(c["MEX-14"], c["MEX-14"] == "Non"))),
        ("FS-1", t3(c["MEX-33"], c["MEX-33"] == "État détérioré")),
        ("FS-2", min(t3(c["MEX-32"], c["MEX-32"] == "Sur toutes les baies"), t3(c["MEX-33"], c["MEX-33"] == "Bon état"))),
        ("FS-3", 1),
    ])
    S.append(_solution("Protections solaires extérieures", "Films solaires", R["FS"]["statut"], ["FS"]))

    # --- Fenêtres de toiture ----------------------------------------------------------
    pas_de_plafond = t3(c["MEX-14"], c["MEX-14"] == "Non")
    prot_ext = t3(c["MEX-18"], a(l.get("MEX-18"), "Volet extérieur", "Store extérieur"))
    prot_int_seule = t3(c["MEX-18"], not a(l.get("MEX-18"), "Volet extérieur", "Store extérieur", "Aucune", "Autre"))
    R["FT"] = bloc([
        ("FT-1", max(pas_de_plafond, t3(c["MEX-15"], not a(l.get("MEX-15"), "Fenêtre de toit (type Velux)", "Lanterneau", "Voûte", "Autre")))),
        ("FT-2", min(prot_ext, t3(c["MEX-19"], c["MEX-19"] == "Hors service ou dégradée"))),
        ("FT-3", prot_int_seule),
        ("FT-4", min(prot_ext, t3(c["MEX-19"], c["MEX-19"] == "Bon état"))),
        ("FT-5", patrimoine),
        ("FT-6", t3(c["MEX-20"], c["MEX-20"] in ("Non identifiables", "Fenêtre très ancienne"))),
        ("FT-7", min(t3(c["MEX-21"], c["MEX-21"] == "Non"),
                     t3(c["MEX-17"], c["MEX-17"] not in ("Électrique", "Automatique (sans action humaine)"), si_so=1))),
        ("FT-8", 1),
    ])
    ft = R["FT"]["statut"]
    S.append(_solution("Protections solaires extérieures", "Sur fenêtres de toiture", ft, ["FT"], [
        ("FT-AL", 0 if ft == NON_CONCERNE else (1 if t3(c["MEX-16"], c["MEX-16"] == "Oui") == 1 else 0)),
    ]))

    # --- Vérandas et verrières -----------------------------------------------------------
    R["VV"] = bloc([
        ("VV-1", max(pas_de_plafond, t3(c["MEX-15"], not a(l.get("MEX-15"), "Verrière", "Véranda", "Puits de lumière, atrium")))),
        ("VV-2", min(prot_ext, t3(c["MEX-19"], c["MEX-19"] == "Hors service ou dégradée"))),
        ("VV-3", prot_int_seule),
        ("VV-4", t3(c["MEX-16"], c["MEX-16"] == "Non")),
        ("VV-5", min(prot_ext, t3(c["MEX-19"], c["MEX-19"] == "Bon état"), t3(c["MEX-16"], c["MEX-16"] == "Oui"))),
        ("VV-6", patrimoine),
        ("VV-7", t3(c["MEX-22"], c["MEX-22"] == "Non")),
        ("VV-8", t3(c["MEX-24"], c["MEX-24"] == "Non")),
        ("VV-9", 1),
    ])
    S.append(_solution("Protections solaires extérieures", "Sur vérandas et/ou verrières", R["VV"]["statut"], ["VV"], [
        ("VV-AL", 1 if t3(c["MEX-15"], a(l.get("MEX-15"), "Véranda", "Verrière")) == 1 else 0),
    ]))

    # --- Toiture -------------------------------------------------------------------------
    to0 = t3(c["L-09"], c["L-09"] not in DERNIER_NIVEAU, si_so=1)
    R["TO"] = bloc([("TO-0", to0)])
    isolee = t3(cb["B-19"], cb["B-19"] == "Isolée")
    cas_tt = t3(cb["B-18"], cb["B-18"] in ("Toiture-terrasse", "Bac acier ou fibro-ciment"))
    R["TT"] = bloc([
        ("TT-1", t3(cb["B-19"], cb["B-19"] == "Non isolée")),
        ("TT-2", min(isolee, calcul(lambda e: e >= p["P_ISOL_TOIT"], cb["B-20"]))),
        ("TT-3", min(isolee, calcul(lambda e: e < p["P_ISOL_TOIT"], cb["B-20"]))),
    ])
    combles = t3(cb["B-21"], cb["B-21"] == "Oui")
    cas_cp = min(combles, t3(cb["B-22"], cb["B-22"] == "En comble perdu"))
    isolant_abime = a(b.get("B-23"), "Tassée", "Discontinue ou partiellement déplacée", "Dégradée (humidité, nuisibles, souillures)")
    R["CP"] = bloc([
        ("CP-1", t3(cb["B-23"], isolant_abime)),
        ("CP-2", t3(cb["B-25"], cb["B-25"] == "Non")),
        ("CP-3", min(calcul(lambda e: e >= p["P_ISOL_COMBLE"], cb["B-24"]), t3(cb["B-23"], not isolant_abime))),
        ("CP-4", t3(cb["B-26"], cb["B-26"] == "Non")),
        ("CP-5", t3(cb["B-27"], cb["B-27"] == "Oui")),
        ("CP-6", t3(cb["B-28"], a(b.get("B-28"), "Spots encastrés", "Conduits de fumée",
                                  "Gaines électriques non protégées", "Matériaux suspects d'amiante"))),
        ("CP-7", 1),
    ])
    cas_ca = min(combles, t3(cb["B-22"], cb["B-22"] == "Sous pente"))
    R["CA"] = bloc([
        ("CA-1", 1 if str(b.get("B-24") or "").strip().lower() == "inconnu" else 0),
        ("CA-2", calcul(lambda e: e < p["P_ISOL_RAMPANT"], cb["B-24"])),
        ("CA-3", calcul(lambda e: e >= p["P_ISOL_RAMPANT"], cb["B-24"])),
    ])
    if to0 == 1:
        statut, blocs = NON_CONCERNE, ["TO"]
    elif to0 == 0.5:
        statut, blocs = SOUS_RESERVE, ["TO"]
    elif cas_tt == 1:
        statut, blocs = R["TT"]["statut"], ["TT"]
    elif cas_cp == 1:
        statut, blocs = R["CP"]["statut"], ["CP"]
    elif cas_ca == 1:
        statut, blocs = R["CA"]["statut"], ["CA"]
    else:
        statut, blocs = SOUS_RESERVE, []
    S.append(_solution("Réduction de la surchauffe par la toiture", "Toiture", statut, blocs))

    # --- Charges internes ------------------------------------------------------------------
    R["CO"] = bloc([
        ("CO-1", min(t3(c["L-02"], c["L-02"] == "Bureau, salle des maîtres, salle de réunion"),
                     calcul(lambda s, n: n > 0 and s / n < p["P_BUREAU_M2"], c["L-03"], c["L-04"]))),
        ("CO-2", min(t3(c["L-02"], c["L-02"] == "Classe"),
                     calcul(lambda s, n: n > 0 and s / n < p["P_CLASSE_M2"], c["L-03"], c["L-04"]))),
        ("CO-3", 1),
    ])
    S.append(_solution("Réduction des charges internes", "Occupation", R["CO"]["statut"], ["CO"]))
    R["CE"] = bloc([
        ("CE-1", t3(c["ECL-01"], c["ECL-01"] in ("Non LED (tubes fluorescents, halogène, incandescence)", "Mixte (LED et non LED)"))),
        ("CE-2", 1),
    ])
    S.append(_solution("Réduction des charges internes", "Éclairage", R["CE"]["statut"], ["CE"]))
    R["CQ"] = bloc([
        ("CQ-1", min(t3(c["L-10"], a(l.get("L-10"), "Copieurs, imprimantes", "Baies informatiques, serveurs", "Appareils de cuisson", "Autre")),
                     calcul(lambda n: n > 0, c["L-04"]))),
        ("CQ-2", t3(c["L-11"], c["L-11"] == "Non")),
        ("CQ-3", 1),
    ])
    S.append(_solution("Réduction des charges internes", "Équipements", R["CQ"]["statut"], ["CQ"]))

    # Variable pour OA-AL1 : local au RDC dont la protection horizontale est Recommandée ou Sous réserve
    mut = au_rdc == 1 and R["PH"]["statut"] in (RECOMMANDE, SOUS_RESERVE) and not R["PH"]["manquante"]
    return {"blocs": R, "solutions": S,
            "orientations_mutualisables": [m["orientation"] for m in actifs] if mut else []}


# ------------------------------------------------------------------ espaces extérieurs
def etats_espace(e: dict) -> dict:
    """Onglet Calc_Extérieurs pour un espace."""
    c = {}
    for k in ("E-01", "E-09", "E-15", "E-16", "E-17", "E-19", "E-31"):
        c[k] = val(e.get(k))
    for k in ("E-06", "E-11", "E-14"):
        c[k] = num(e.get(k))
    for k in ("E-02", "E-04", "E-10", "E-20"):
        c[k] = multi(e.get(k))
    c["E-07"] = porte(t3(c["E-04"], a(e.get("E-04"), "Maternelle")), num(e.get("E-07")))
    c["E-12"] = porte(t3(c["E-10"], a(e.get("E-10"), "Arbres")), val(e.get("E-12")))
    adosse = t3(c["E-20"], not a(e.get("E-20"), "Aucune"), si_so=1)
    for k in ("E-21", "E-22", "E-23", "E-24", "E-25"):
        c[k] = porte(adosse, val(e.get(k)))
    preau = t3(c["E-02"], a(e.get("E-02"), "Préau"))
    c["E-26"] = porte(preau, val(e.get("E-26")))
    c["E-27"] = porte(t3(c["E-26"], c["E-26"] == "Polycarbonate ou verrière"), val(e.get("E-27")))
    c["E-28"] = porte(preau, val(e.get("E-28")))
    c["E-29"] = porte(preau, num(e.get("E-29")))
    c["E-30"] = porte(preau, num(e.get("E-30")))
    c["E-32"] = porte(t3(c["E-02"], a(e.get("E-02"), "Cour de récréation")), val(e.get("E-32")))
    return c


def regles_espace(e: dict, c: dict, cb: dict, orientations_mut: set, p: dict) -> dict:
    """Onglet Règles_Extérieurs pour un espace."""
    patrimoine = _patrimoine(cb)
    R = {}
    ex_al = max(
        min(t3(c["E-04"], a(e.get("E-04"), "Élémentaire")),
            calcul(lambda s, n: n > 0 and s / n < p["P_OMBRE_ELEM"], c["E-14"], c["E-06"])),
        min(t3(c["E-04"], a(e.get("E-04"), "Maternelle")),
            max(calcul(lambda n, s: n <= p["P_OMBRE_MAT_CL"] and s < p["P_OMBRE_MAT_1"], c["E-07"], c["E-14"]),
                calcul(lambda n, s: n > p["P_OMBRE_MAT_CL"] and s < p["P_OMBRE_MAT_2"], c["E-07"], c["E-14"]))))

    # --- Ombrage adossé au bâtiment ---
    facades_bordees = [o for o in ORIENTATIONS if a(e.get("E-20"), o)]
    R["OA"] = bloc([
        ("OA-1", t3(c["E-20"], not a(e.get("E-20"), "S", "SE", "SO", "E", "O"), si_so=1)),
        ("OA-2", t3(c["E-21"], c["E-21"] == "En bon état, couvre l'essentiel de la zone d'usage")),
        ("OA-3", t3(c["E-21"], c["E-21"] in ("En bon état, couvre une partie de la zone d'usage", "Hors service ou dégradée"))),
        ("OA-4", 0.5 if c["E-20"] == INC else
            max([t3(cb["facades"][o]["F-02"], cb["facades"][o]["F-02"] == "Oui") for o in facades_bordees], default=0)),
        ("OA-5", patrimoine),
        ("OA-6", t3(c["E-22"], c["E-22"] in ("Maçonnerie ancienne ou dégradée", "Bardage", "Isolation par l'extérieur",
                                             "Ossature légère", "Non identifiable"))),
        ("OA-7", max(t3(c["E-31"], c["E-31"] == "Oui"), t3(c["E-23"], c["E-23"] == "Oui"))),
        ("OA-8", t3(c["E-24"], c["E-24"] == "Aucun existant, mâts ou poteaux à créer")),
        ("OA-9", t3(c["E-24"], c["E-24"] == "Aucun possible")),
        ("OA-10", min(t3(c["E-25"], c["E-25"] == "Oui"), t3(c["E-22"], c["E-22"] == "Béton ou maçonnerie pleine"),
                      t3(c["E-24"], c["E-24"] == "Mâts, poteaux ou élément solide existants (mur, préau, bâtiment voisin)"))),
        ("OA-11", 1),
    ])
    oa_ok = 1 if (not R["OA"]["manquante"] and R["OA"]["statut"] in (RECOMMANDE, SOUS_RESERVE)) else 0
    S = [_solution("Adaptation des espaces extérieurs", "Ombrage rapporté adossé au bâtiment", R["OA"]["statut"], ["OA"], [
        ("OA-AL1", 1 if oa_ok and any(o in orientations_mut for o in facades_bordees) else 0),
        ("OA-AL2", oa_ok),
        ("OA-AL3", oa_ok),
    ])]

    # --- Adaptation d'un préau existant ---
    opaque = t3(c["E-26"], c["E-26"] != "Polycarbonate ou verrière", si_so=1)
    R["PR"] = bloc([
        ("PR-1", t3(c["E-02"], not a(e.get("E-02"), "Préau"), si_so=1)),
        ("PR-2", min(t3(c["E-26"], c["E-26"] == "Polycarbonate ou verrière"), t3(c["E-27"], c["E-27"] == "Non"))),
        ("PR-3", calcul(lambda n: n >= p["P_PREAU_FERME"], c["E-30"])),
        ("PR-4", min(opaque, t3(c["E-28"], c["E-28"] in ("Foncée", "Moyenne")))),
        ("PR-5", min(t3(c["E-26"], c["E-26"] == "Bac acier ou tôle, non isolé"), calcul(lambda h: h < p["P_PREAU_H"], c["E-29"]))),
        ("PR-6", min(calcul(lambda n: n <= p["P_PREAU_OUVERT"], c["E-30"]),
                     max(t3(c["E-26"], c["E-26"] == "Tuiles"), t3(c["E-28"], c["E-28"] == "Claire")))),
        ("PR-7", 1),
    ])
    pr = R["PR"]["statut"]
    concerne = pr != NON_CONCERNE
    S.append(_solution("Adaptation des espaces extérieurs", "Adaptation d'un préau existant", pr, ["PR"], [
        ("PR-AL1", 1 if concerne and patrimoine == 1 else 0),
        ("PR-AL2", 1 if pr == A_OPTIMISER and not R["PR"]["manquante"] else 0),
        ("PR-AL3", 1 if concerne and t3(c["E-26"], c["E-26"] == "Fibrociment") == 1
            and t3(cb["B-01"], cb["B-01"] != "Après 1997", si_so=1) > 0 else 0),
        ("PR-AL4", 1 if concerne and ex_al == 1 else 0),
    ]))

    # --- Ombrage autoportant ou végétal de la cour ---
    cas_oc = t3(c["E-02"], a(e.get("E-02"), "Cour de récréation"))
    R["OC"] = bloc([
        ("OC-1", min(t3(c["E-09"], c["E-09"] in ("Entre 25 et 50 %", "Entre 50 et 75 %", "Entre 75 et 100 %")),
                     t3(c["E-12"], c["E-12"] != "Dégradé", si_so=1),
                     t3(c["E-15"], c["E-15"] != "Hors service ou dégradé", si_so=1))),
        ("OC-2", min(t3(c["E-10"], a(e.get("E-10"), "Arbres", "Voiles d'ombrage", "Pergola ou treille végétalisée")),
                     max(t3(c["E-12"], c["E-12"] == "Dégradé"), t3(c["E-15"], c["E-15"] == "Hors service ou dégradé"),
                         t3(c["E-09"], c["E-09"] in ("0 %", "Entre 0 et 25 %"))))),
        ("OC-3", patrimoine),
        ("OC-4", t3(c["E-32"], c["E-32"] in ("Dalle sur ouvrage ou parking souterrain", "Faible épaisseur de terre"))),
        ("OC-5", t3(c["E-31"], c["E-31"] == "Oui")),
        ("OC-6", 1),
    ])
    if cas_oc == 0:
        statut, blocs = NON_CONCERNE, []
    elif cas_oc == 0.5:
        statut, blocs = SOUS_RESERVE, []
    else:
        statut, blocs = R["OC"]["statut"], ["OC"]
    S.append(_solution("Adaptation des espaces extérieurs", "Ombrage autoportant ou végétal de la cour", statut, blocs))
    return {"blocs": R, "solutions": S, "EX-AL": ex_al}


# ------------------------------------------------------------------ point d'entrée
def calculer(donnees: dict) -> dict:
    """Calcule tous les résultats.

    ``donnees`` = {"batiment": {...}, "facades": {...}, "locaux": [...], "espaces": [...],
    "parametres": {...}} (voir ``exemple.py`` pour un jeu complet).
    """
    p = {**PARAMETRES_DEFAUT, **(donnees.get("parametres") or {})}
    b = donnees.get("batiment") or {}
    cb = etats_batiment(b, donnees.get("facades") or {})

    locaux, orientations_mut = [], set()
    for l in donnees.get("locaux") or []:
        c = etats_local(l, cb)
        r = regles_local(l, c, cb, b, p)
        orientations_mut.update(r.pop("orientations_mutualisables"))
        locaux.append({"nom": l.get("L-01") or "", "etats": c, **r})

    espaces = []
    for e in donnees.get("espaces") or []:
        c = etats_espace(e)
        espaces.append({"nom": e.get("E-01") or "", "etats": c, **regles_espace(e, c, cb, orientations_mut, p)})
    return {"batiment": cb, "locaux": locaux, "espaces": espaces}
