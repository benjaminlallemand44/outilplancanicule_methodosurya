"""CCTP types du kit « passage en travaux », remplis à partir du diagnostic.

Les gabarits (``surya/kit/cctp/cctp_N.md``) sont en Markdown simple, avec :

* des variables ``{{nom}}`` (une variable absente devient « [À COMPLÉTER] ») ;
* des tableaux ``{{tableau:locaux}}``, ``{{tableau:baies}}``, ``{{tableau:espaces}}`` (seuls sur leur ligne) ;
* des blocs conditionnels ``[SI condition]`` … ``[FIN SI]`` (sur des lignes seules, imbricables). Une
  condition est un indicateur (``amiante``, ``abf``, ``lot1``…), ``alerte CODE`` ou ``regle CODE`` ; plusieurs
  conditions se combinent avec `` ou ``. Elle est vraie si elle l'est pour au moins un local ou espace
  concerné par le CCTP.

``remplir(n, donnees)`` renvoie le CCTP en Markdown ; ``docx(markdown)`` le convertit en Word (modifiable
par la collectivité) ; ``dossier(donnees)`` renvoie une archive ZIP avec un .docx par CCTP utile. Aucune
dépendance à Streamlit.
"""
from __future__ import annotations

import datetime as dt
import io
import re
import zipfile
from pathlib import Path

from . import travaux
from .moteur import A_OPTIMISER

GABARITS = Path(__file__).parent / "kit" / "cctp"
A_COMPLETER = "[À COMPLÉTER]"


def _fr(v) -> str:
    if v is None:
        return A_COMPLETER
    if isinstance(v, float):
        v = round(v, 1)
        v = int(v) if v == int(v) else v
    return str(v).replace(".", ",")


def _liste(noms) -> str:
    noms = list(dict.fromkeys(noms))
    return ", ".join(noms) if noms else A_COMPLETER


# ------------------------------------------------------------------ contexte d'un CCTP
def _operations(n, etat: dict) -> list[dict]:
    return (etat["pieces"].get(n) or {}).get("operations") or [o for o in etat["retenues"] if n in o["cctp"]]


def _entites(ops) -> list[dict]:
    """Locaux et espaces concernés, une fois chacun, avec le constat de chaque opération du CCTP."""
    par_nom = {}
    for o in ops:
        for e in o["a_engager"] + o["a_valider"]:
            x = par_nom.setdefault(e["nom"], {**e, "constats": []})
            c = e["statut"] + (f" (règle {e['regle']})" if e["regle"] else "")
            if e["alertes"]:
                c += ", alertes " + ", ".join(e["alertes"])
            x["constats"].append((c if len(ops) == 1 else f"{_court(o)} : {c}"))
    return list(par_nom.values())


def _court(o: dict) -> str:
    return {"Mise en place de brasseurs d'air plafonniers": "Brasseurs", "Éclairage": "Éclairage",
            "Protections verticales": "Protections", "Sur fenêtres de toiture": "Fenêtres de toit",
            "Ombrage rapporté adossé au bâtiment": "Voile adossée",
            "Ombrage autoportant ou végétal de la cour": "Ombrage de la cour"}.get(o["solution"], o["libelle"])


def contexte(n: int, donnees: dict, etat: dict | None = None) -> tuple[dict, set, dict]:
    """(variables, indicateurs, tableaux) du CCTP ``n``."""
    etat = etat or travaux.etat(donnees)
    ctx, audit, b = etat["contexte"], donnees.get("audit") or {}, donnees.get("batiment") or {}
    ops = _operations(n, etat)
    par_sol = {o["solution"]: o for o in ops}
    ents = _entites(ops)
    flags = {k for k in ("amiante", "plomb", "ite", "double_flux", "simple_flux", "combles_perdus") if ctx[k]}
    if ctx["patrimoine"]:
        flags.add("abf")
    for o in ops:
        for e in o["a_engager"] + o["a_valider"]:
            flags.update(f"alerte {a}" for a in e["alertes"])
            if e["regle"]:
                flags.add(f"regle {e['regle']}")
    brasseurs = par_sol.get("Mise en place de brasseurs d'air plafonniers")
    eclairage = par_sol.get("Éclairage")
    if brasseurs:
        flags.add("lot1")
        types = {e["entree"].get("L-02") for e in brasseurs["a_engager"] + brasseurs["a_valider"]}
        if "Dortoir ou salle de repos" in types:
            flags.add("dortoir")
        if "Salle de motricité, de sport ou d'activité physique" in types:
            flags.add("motricite")
        if any(e["statut"] == A_OPTIMISER for e in brasseurs["a_engager"] + brasseurs["a_valider"]):
            flags.add("option_bp")
    if eclairage:
        flags.add("lot2")
    if "Sur fenêtres de toiture" in par_sol:
        flags.add("fenetres_toit")
    if "Ombrage rapporté adossé au bâtiment" in par_sol:
        flags.add("adosse")
    sols = set(par_sol)
    zones = {
        "z_facade": {"Protections verticales", "Protections horizontales", "Films solaires", "Sur fenêtres de toiture",
                     "Ombrage rapporté adossé au bâtiment", "Sur vérandas et/ou verrières"},
        "z_menuiseries": {"Par ventilation naturelle nocturne"},
        "z_plafond": {"Mise en place de brasseurs d'air plafonniers", "Éclairage"},
        "z_toiture": {"Toiture"},
        "z_preau": {"Adaptation d'un préau existant"},
        "s_horizontales": {"Protections horizontales", "Sur vérandas et/ou verrières"},
        "s_preau": {"Adaptation d'un préau existant"},
        "s_toiture": {"Toiture"},
    }
    flags.update(k for k, v in zones.items() if sols & v)

    def noms_si(test):
        return _liste(e["nom"] for e in ents if test(e))

    principale = ops[0] if ops else {}
    quantite = sum(o["quantite"] or 0 for o in ops if o["solution"] not in ("Éclairage",
                                                                           "Mise en place de brasseurs d'air plafonniers"))
    horizon = min((o["horizon"] for o in ops), default=3)
    v = {
        "etablissement": audit.get("etablissement"), "adresse": audit.get("adresse"), "commune": audit.get("commune"),
        "moa": audit.get("moa"), "auditeur": audit.get("auditeur"), "date_visite": audit.get("date_visite"),
        "periode_construction": ctx["periode"].lower() if ctx["periode"] else None,
        "quantite": _fr(quantite) if quantite else None,
        "nb_locaux": len([e for e in ents if "L-01" in e["entree"] or "L-03" in e["entree"]]) or None,
        "quantite_brasseurs": _fr(brasseurs["quantite"]) if brasseurs and brasseurs["quantite"] else None,
        "nb_locaux_lot1": len(brasseurs["a_engager"] + brasseurs["a_valider"]) if brasseurs else None,
        "surface_eclairage": _fr(eclairage["quantite"]) if eclairage and eclairage["quantite"] else None,
        "nb_locaux_lot2": len(eclairage["a_engager"] + eclairage["a_valider"]) if eclairage else None,
        "locaux_eclairage": _liste(e["nom"] for e in (eclairage["a_engager"] + eclairage["a_valider"])) if eclairage else None,
        "locaux_bp": _liste(e["nom"] for e in (brasseurs["a_engager"] + brasseurs["a_valider"])
                            if e["statut"] == A_OPTIMISER) if brasseurs else None,
        "locaux_bs3": noms_si(lambda e: e["regle"] == "BS-3"),
        "locaux_pv2": noms_si(lambda e: e["regle"] == "PV-2"),
        "locaux_pv5": noms_si(lambda e: e["regle"] == "PV-5"),
        "locaux_vn7": noms_si(lambda e: e["regle"] == "VN-7"),
        "locaux_vn4": noms_si(lambda e: e["regle"] == "VN-4"),
        "locaux_vn3": noms_si(lambda e: e["regle"] == "VN-3"),
        "locaux_ftal": noms_si(lambda e: "FT-AL" in e["alertes"]),
        "locaux_ft": _liste(e["nom"] for e in (par_sol["Sur fenêtres de toiture"]["a_engager"]
                                               + par_sol["Sur fenêtres de toiture"]["a_valider"])) if "Sur fenêtres de toiture" in par_sol else None,
        "locaux_vm": _liste(e["nom"] for e in ents) if ents else None,
        "locaux_concernes": _liste(e["nom"] for e in ents) if ents else None,
        "ventilation": ("ventilation mécanique " + ctx["ventilation"].lower()) if ctx["ventilation"] else None,
        "toiture": (ctx["toiture"] or "").lower() or None,
        "isolant_combles": ", ".join(filter(None, [
            (b.get("B-23") if isinstance(b.get("B-23"), str) else ", ".join(b.get("B-23") or [])) or None,
            f"{_fr(b['B-24'])} cm" if isinstance(b.get("B-24"), (int, float)) else None])) or None,
        "acces_combles": {"Oui": "trappe d'accès", "Non": "pas d'accès relevé"}.get(b.get("B-26")),
        "elements_combles": ", ".join(b.get("B-28") or []) or None,
        "periode_travaux": ("les vacances scolaires [À COMPLÉTER : printemps ou été]" if horizon < 3 else None),
        "principale": principale.get("libelle"),
        "plomb_objet": " et la recherche de plomb dans les revêtements" if ctx["plomb"] else " ",
        "locaux_bral": noms_si(lambda e: "BR-AL" in e["alertes"]),
    }
    tableaux = {"locaux": _tab_locaux(ents), "baies": _tab_baies(ents), "espaces": _tab_espaces(ents),
                "operations": _tab_operations(ops)}
    return v, flags, tableaux


def _tab_operations(ops) -> list[list[str]]:
    lignes = [["Opération", "Locaux ou espaces", "Intervenant prévu", "Alertes du diagnostic"]]
    for o in ops:
        ents = o["a_engager"] + o["a_valider"]
        lignes.append([_cell(o["action"]), _cell(", ".join(e["nom"] for e in ents)), _cell(o["prestataire"]),
                       _cell(", ".join(sorted(travaux._alertes(o))) or None)])
    return lignes if len(lignes) > 1 else []


def _cell(x) -> str:
    return str(x).replace("|", "/").replace("\n", " ") if x not in (None, "", []) else "n.r."


def _tab_locaux(ents) -> list[list[str]]:
    lignes = [["Local", "Niveau", "Surface (m²)", "Hauteur libre (m)", "Plafond", "Constat du diagnostic"]]
    for e in ents:
        x = e["entree"]
        if "E-01" in x:
            continue
        constat = " ; ".join(e["constats"])
        lignes.append([_cell(e["nom"]), _cell(x.get("L-09")), _cell(_fr(x.get("L-03")) if x.get("L-03") else None),
                       _cell(_fr(x.get("PL-03")) if x.get("PL-03") else None), _cell(x.get("PL-01")), constat])
    return lignes if len(lignes) > 1 else []


def _tab_baies(ents) -> list[list[str]]:
    lignes = [["Local", "Orientation", "Nombre de baies", "Types de baies", "Position de la menuiserie",
               "Profondeur de tableau (cm)"]]
    for e in ents:
        x = e["entree"]
        for m in x.get("murs") or []:
            baies = {k: n for k, n in (m.get("baies") or {}).items() if isinstance(n, (int, float)) and n}
            if not baies:
                continue
            lignes.append([_cell(e["nom"]), _cell(m.get("orientation")), _fr(sum(baies.values())),
                           _cell(", ".join(baies)), _cell(m.get("MEX-04")),
                           _cell(_fr(m.get("MEX-05")) if m.get("MEX-05") is not None else None)])
    return lignes if len(lignes) > 1 else []


def _tab_espaces(ents) -> list[list[str]]:
    lignes = [["Espace", "Effectif simultané", "Ombre existante hors végétaux (m²)", "Sol", "Contraintes d'accès"]]
    for e in ents:
        x = e["entree"]
        if "E-01" not in x and "E-06" not in x:
            continue
        lignes.append([_cell(e["nom"]), _cell(_fr(x.get("E-06")) if x.get("E-06") else None),
                       _cell(_fr(x.get("E-14")) if x.get("E-14") is not None else None), _cell(x.get("E-32")),
                       _cell(x.get("E-31"))])
    return lignes if len(lignes) > 1 else []


# ------------------------------------------------------------------ remplissage
_SI = re.compile(r"^\[SI (.+)\]$")
_VAR = re.compile(r"\{\{([a-z0-9_:]+)\}\}")


def _vrai(condition: str, flags: set) -> bool:
    return any(c.strip() in flags for c in condition.split(" ou "))


def appliquer(gabarit: str, variables: dict, flags: set, tableaux: dict | None = None) -> str:
    """Applique variables, tableaux et blocs conditionnels à un gabarit."""
    tableaux = tableaux or {}
    out, pile = [], []
    for ligne in gabarit.splitlines():
        s = ligne.strip()
        m = _SI.match(s)
        if m:
            pile.append(_vrai(m.group(1), flags))
            continue
        if s == "[FIN SI]":
            if pile:
                pile.pop()
            continue
        if not all(pile):
            continue
        if s.startswith("{{tableau:") and s.endswith("}}"):
            t = tableaux.get(s[10:-2]) or []
            if t:
                out.append("| " + " | ".join(t[0]) + " |")
                out.append("| " + " | ".join("---" for _ in t[0]) + " |")
                out += ["| " + " | ".join(r) + " |" for r in t[1:]]
            else:
                out.append(f"{A_COMPLETER} (tableau à compléter : aucune donnée relevée)")
            continue
        out.append(_VAR.sub(lambda mm: str(variables.get(mm.group(1)) or A_COMPLETER), ligne))
    texte = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", texte).strip() + "\n"


def _cout_txt(c) -> str:
    if not c:
        return "à chiffrer"
    if c["haut"] == 0:
        return "sans coût"
    f = lambda x: f"{x:,.0f} €".replace(",", " ")
    return f"env. {f(c['bas'])} HT" if c["bas"] == c["haut"] else f"{f(c['bas'])} à {f(c['haut'])} HT"


VOLETS = {"façade": "volet façade (protections solaires)", "toiture": "volet toiture",
          "paysage": "volet espaces extérieurs", "fluides": "volet ventilation et rafraîchissement",
          "intérieur": "volet équipements intérieurs (brasseurs, éclairage)"}
CLES_VOLET = {"façade": "facade", "toiture": "toiture", "paysage": "paysage", "fluides": "fluides",
              "intérieur": "interieur"}


def contexte_moe(donnees: dict, etat: dict | None = None) -> tuple[dict, set, dict]:
    """Variables, indicateurs et tableaux du cahier des charges de maîtrise d'œuvre (gabarit cctp_moe.md).
    Toutes les opérations de travaux retenues sont confiées à la maîtrise d'œuvre, quel que soit leur niveau ;
    elles activent les volets."""
    etat = etat or travaux.etat(donnees)
    ctx, audit = etat["contexte"], donnees.get("audit") or {}
    ops_c = [o for o in etat["retenues"] if travaux.est_travaux(o)]
    ops_moa = [o for o in etat["retenues"] if not travaux.est_travaux(o)]
    par_volet = {}
    for o in ops_c:
        par_volet.setdefault(travaux._volet(o), []).append(o)
    flags = {f"volet_{CLES_VOLET[v]}" for v in par_volet}
    for k in ("amiante", "plomb"):
        if ctx[k]:
            flags.add(k)
    if ctx["patrimoine"]:
        flags.add("abf")
    structure = sorted({a for o in ops_c for e in o["a_engager"] + o["a_valider"] for a in e["alertes"]
                        if a in ("VV-AL", "OA-AL2", "PR-AL2")})
    if structure:
        flags.add("structure")
    if "façade" in par_volet or "abf" in flags or any(
            o["solution"] in ("Ombrage rapporté adossé au bâtiment", "Ombrage autoportant ou végétal de la cour")
            for o in ops_c):
        flags.add("autorisations")
    if {"façade", "toiture"} & set(par_volet):
        flags.add("std")
    if len(par_volet) >= 2:
        flags.add("opc")
    flags.update(f"alerte {a}" for o in ops_c for e in o["a_engager"] + o["a_valider"] for a in e["alertes"])
    if ops_moa:
        flags.add("ops_moa")
    rapides = [o for o in ops_c if o["horizon"] < 3]
    if rapides:
        flags.add("ops_rapides")
    p = travaux.pieces(etat["retenues"], True, ctx)
    if 10 in p:
        flags.add("amiante")
    if 12 in p:
        flags.add("ct")
    if 13 in p:
        flags.add("csps")
    if etat["completer"]:
        flags.add("donnees_manquantes")

    def liste(ops):
        return "; ".join(f"{o['action']} ({', '.join(e['nom'] for e in o['a_engager'] + o['a_valider'])})"
                         for o in ops) or A_COMPLETER

    v = {
        "etablissement": audit.get("etablissement"), "adresse": audit.get("adresse"), "commune": audit.get("commune"),
        "moa": audit.get("moa"), "date_visite": audit.get("date_visite"),
        "volets": ", ".join(VOLETS[k] for k in ("façade", "toiture", "paysage", "fluides", "intérieur") if k in par_volet) or A_COMPLETER,
        "ops_facade": liste(par_volet.get("façade", [])), "ops_toiture": liste(par_volet.get("toiture", [])),
        "ops_paysage": liste(par_volet.get("paysage", [])), "ops_fluides": liste(par_volet.get("fluides", [])),
        "ops_interieur": liste(par_volet.get("intérieur", [])),
        "ops_moa": "; ".join(o["action"] for o in ops_moa) or None,
        "ops_rapides": "; ".join(o["action"] for o in rapides) or None,
        "alertes_structure": ", ".join(structure) or None,
        "donnees_manquantes": "; ".join(f"{n} ({', '.join(x)})" for n, x in etat["completer"].items()) or None,
        "tranche_ferme_auto": " ", "tranche_opc": " et OPC (option)" if "opc" in flags else " ",
        "options_supp": " ",
    }
    t_ops = [["Opération", "Volet", "Locaux ou espaces", "Constat du diagnostic"]]
    libelle_volet = {"façade": "Façade", "toiture": "Toiture", "paysage": "Espaces extérieurs", "fluides": "Ventilation",
                     "intérieur": "Équipements intérieurs"}
    ordre_volet = list(libelle_volet)
    for o in sorted(ops_c, key=lambda o: ordre_volet.index(travaux._volet(o))):
        ents = o["a_engager"] + o["a_valider"]
        constat = "; ".join(sorted({f"{e['statut']}" + (f" ({e['regle']})" if e["regle"] else "")
                                    + (f", alertes {', '.join(e['alertes'])}" if e["alertes"] else "") for e in ents}))
        t_ops.append([_cell(o["action"]), libelle_volet[travaux._volet(o)], _cell(", ".join(e["nom"] for e in ents)),
                      _cell(constat)])
    t_all = [["Opération", "Niveau", "Horizon", "Locaux ou espaces"]]
    for o in etat["retenues"]:
        t_all.append([_cell(o["action"]), o["niveau"], str(o["horizon"]),
                      _cell(", ".join(e["nom"] for e in o["a_engager"] + o["a_valider"]))])
    tableaux = {"operations_moe": t_ops if len(t_ops) > 1 else [], "locaux_moe": t_all if len(t_all) > 1 else []}
    return v, flags, tableaux


def remplir(n, donnees: dict, etat: dict | None = None) -> str:
    if n == "MOE":
        v, f, t = contexte_moe(donnees, etat)
        return appliquer((GABARITS / "cctp_moe.md").read_text(encoding="utf-8"), v, f, t)
    v, f, t = contexte(n, donnees, etat)
    return appliquer((GABARITS / f"cctp_{n}.md").read_text(encoding="utf-8"), v, f, t)


# ------------------------------------------------------------------ Word
def _runs(par, texte: str):
    for morceau in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", texte):
        if not morceau:
            continue
        if morceau.startswith("**") and morceau.endswith("**"):
            par.add_run(morceau[2:-2]).bold = True
        elif morceau.startswith("*") and morceau.endswith("*") and len(morceau) > 2:
            par.add_run(morceau[1:-1]).italic = True
        else:
            r = par.add_run(morceau)
            if A_COMPLETER[1:-1] in morceau:
                from docx.enum.text import WD_COLOR_INDEX
                r.font.highlight_color = WD_COLOR_INDEX.YELLOW


def docx(markdown: str, mention: str = "") -> bytes:
    """Convertit le Markdown d'un CCTP en document Word modifiable."""
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    doc.styles["Normal"].font.name = "Arial"
    doc.styles["Normal"].font.size = Pt(10)
    if mention:
        p = doc.sections[0].footer.paragraphs[0]
        p.text = mention
        for r in p.runs:
            r.font.size = Pt(7.5)
    lignes = markdown.splitlines()
    i = 0
    while i < len(lignes):
        s = lignes[i].rstrip()
        if s.startswith("|"):
            bloc = []
            while i < len(lignes) and lignes[i].startswith("|"):
                cells = [c.strip() for c in lignes[i].strip().strip("|").split("|")]
                if not all(set(c) <= {"-", ":", " "} for c in cells):
                    bloc.append(cells)
                i += 1
            if bloc:
                t = doc.add_table(rows=len(bloc), cols=len(bloc[0]))
                t.style = "Table Grid"
                for r, row in enumerate(bloc):
                    for c, val in enumerate(row[:len(bloc[0])]):
                        cell = t.cell(r, c)
                        cell.text = ""
                        _runs(cell.paragraphs[0], val)
                        if r == 0:
                            for run in cell.paragraphs[0].runs:
                                run.bold = True
                doc.add_paragraph()
            continue
        if s.startswith("### "):
            doc.add_heading(s[4:], level=3)
        elif s.startswith("## "):
            doc.add_heading(s[3:], level=2)
        elif s.startswith("# "):
            doc.add_heading(s[2:], level=1)
        elif s.startswith("- [ ] "):
            _runs(doc.add_paragraph(), "☐ " + s[6:])
        elif s.startswith("- "):
            _runs(doc.add_paragraph(style="List Bullet"), s[2:])
        elif s:
            _runs(doc.add_paragraph(), s)
        i += 1
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def nom_fichier(n) -> str:
    return "CCTP_MOE_adaptation" if n == "MOE" else travaux.CCTP[n].split(" — ")[0].replace(" ", "_")


DOSSIERS = {"moe": "1_Maitrise_d_oeuvre", "prealable": "2_Prestations_prealables",
            "travaux": "3_Travaux_et_commandes", "reference": "3_Travaux_base_pour_la_MOE"}


def dossier(donnees: dict, etat: dict | None = None) -> bytes:
    """Archive ZIP : un CCTP .docx par pièce utile, rangé par catégorie (maîtrise d'œuvre, prestations
    préalables, travaux), et un fichier LISEZMOI."""
    etat = etat or travaux.etat(donnees)
    statut = "version validée" if etat["valide"] else "PROJET non validé"
    mention = (f"Généré le {dt.date.today().strftime('%d/%m/%Y')} par l'outil ACTEE à partir du diagnostic ({statut}). "
               "Modèle à adapter et à relire avant envoi ; les champs surlignés en jaune sont à compléter.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        lisez = ["Dossier de consultation — kit passage en travaux ACTEE", "",
                 f"Statut : {statut}.",
                 "Maîtrise d'œuvre : " + ("recommandée ; toutes les opérations de travaux lui sont confiées."
                                         if etat["moe"] else "non retenue.")]
        cat = None
        for n, x in etat["pieces"].items():
            if x["categorie"] != cat:
                cat = x["categorie"]
                lisez += ["", travaux.CATEGORIES[cat] + " :"]
            z.writestr(f"{DOSSIERS[cat]}/{nom_fichier(n)}.docx", docx(remplir(n, donnees, etat), mention))
            lisez.append(f"- {travaux.CCTP[n]}")
        lisez += ["", "Les champs [À COMPLÉTER] sont surlignés en jaune dans chaque document.",
                  "Les quantités sont des estimations issues du diagnostic : à confirmer par un métré."]
        z.writestr("LISEZMOI.txt", "\n".join(lisez))
    return buf.getvalue()
