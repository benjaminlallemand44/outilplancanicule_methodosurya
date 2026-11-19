"""Compte rendu PDF de l'audit de faisabilité d'actions d'adaptation.

Le compte rendu suit le cadre de la méthode SURYA (document « Méthode de l'audit de faisabilité
d'actions d'adaptation », version 01 du 27/10/2026) :

* il indique ce qui peut être engagé rapidement (consultation d'entreprises, régie) et ce qui exige
  d'abord une validation par un tiers ou un approfondissement ;
* il donne assez de matière pour consulter : quantités, localisation, contraintes ;
* il signale les alertes maîtrise d'œuvre (AL) et les points de validation ponctuelle (VA) ;
* il est traçable : chaque statut est justifié par la règle qui l'a produit.

``generer_pdf(donnees)`` renvoie le PDF (bytes). Aucune dépendance à Streamlit.
"""
from __future__ import annotations

import datetime as dt
import html
import io
from collections import Counter, defaultdict

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (CondPageBreak, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from . import moteur
from .moteur import (A_OPTIMISER, EN_PLACE, NON_CONCERNE, NON_RECOMMANDE, PARAMETRES_DEFAUT, RECOMMANDE, REFERENTIEL,
                     REGLES, SOUS_RESERVE)

# ------------------------------------------------------------------ référentiel du compte rendu
STATUTS = [RECOMMANDE, A_OPTIMISER, EN_PLACE, SOUS_RESERVE, NON_RECOMMANDE, NON_CONCERNE]
DEFINITIONS_STATUTS = {  # méthode, § II.ii
    NON_CONCERNE: "Le local ne comporte pas l'élément évalué",
    NON_RECOMMANDE: "Solution impossible ou très peu pertinente dans ce contexte",
    SOUS_RESERVE: "Solution possible sous réserve de vérifications techniques ou réglementaires",
    A_OPTIMISER: "Solution déjà présente mais défaillante, incomplète ou mal réglée",
    EN_PLACE: "Solution déjà présente et satisfaisante",
    RECOMMANDE: "Solution absente, sans obstacle identifié : à recommander",
}
COULEURS = {  # fond, texte (identiques à l'interface)
    RECOMMANDE: ("#d3f0db", "#0f5a26"),
    EN_PLACE: ("#d6e6fb", "#0e4a8a"),
    A_OPTIMISER: ("#ffe2c2", "#8a4300"),
    SOUS_RESERVE: ("#fff2b3", "#6b5300"),
    NON_RECOMMANDE: ("#f9d2d0", "#8c1d18"),
    NON_CONCERNE: ("#e6e6e6", "#4d4d4d"),
}
VERT = colors.HexColor("#1f5e3b")

# Type de chaque alerte de l'Excel, selon le tableau « Limites déclenchant une alerte maîtrise
# d'œuvre » de la méthode (§ I.e). AL : étude par une maîtrise d'œuvre avant de consulter ;
# VA : validation ponctuelle par un professionnel ; INFO : point d'attention sans validation.
# L'Excel ne type pas les alertes : ce classement est une PROPOSITION (voir docs/points_a_trancher.md).
TYPES_ALERTE = {
    "BR-AL": "VA",    # électricité + fixation simple
    "VN-AL1": "VA",   # sûreté
    "VN-AL2": "INFO",
    "FT-AL": "INFO",
    "VV-AL": "AL",    # structure
    "EX-AL": "INFO",
    "OA-AL1": "INFO",
    "OA-AL2": "AL",   # structure : fixation en façade, prise au vent
    "OA-AL3": "AL",   # sécurité incendie
    "PR-AL1": "AL",   # patrimoine
    "PR-AL2": "AL",   # structure : surcharge sur couverture
    "PR-AL3": "AL",   # matériaux dangereux
    "PR-AL4": "INFO",
}
LIBELLES_TYPE = {"AL": "Alerte maîtrise d'œuvre", "VA": "Validation ponctuelle", "INFO": "Point d'attention"}

# Solutions dont le statut dépend d'abord d'un « cas » : questions à renseigner si le cas est indéterminé
QUESTIONS_DU_CAS = {
    "Mise en place de brasseurs d'air plafonniers": "BA-05",
    "Toiture": "L-09, puis B-18, B-21 et B-22 (bâtiment)",
    "Ombrage autoportant ou végétal de la cour": "E-02",
}

# Rubriques d'identification de l'audit (hors Excel), saisies dans l'outil pour la page de garde
CHAMPS_AUDIT = [
    ("etablissement", "Établissement"),
    ("adresse", "Adresse"),
    ("commune", "Commune"),
    ("moa", "Maître d'ouvrage"),
    ("auditeur", "Auditeur"),
    ("date_visite", "Date de visite"),
]


def donnee_manquante(x: dict, s: dict) -> bool:
    """Le statut « Sous réserve » de la solution ``s`` vient-il d'une donnée manquante ?"""
    if s["statut"] != SOUS_RESERVE:
        return False
    return not s["blocs"] or any(x["blocs"][b]["manquante"] for b in s["blocs"])


def justification(x: dict, s: dict) -> tuple[str, str]:
    """(code de la règle retenue, texte expliquant le statut)."""
    if not s["blocs"]:
        if s["statut"] == NON_CONCERNE:
            return "", "L'espace ne comporte pas de cour de récréation."
        return "", f"Cas non déterminé : renseigner {QUESTIONS_DU_CAS.get(s['solution'], '—')}."
    codes, textes = [], []
    for b in s["blocs"]:
        bl = x["blocs"][b]
        if bl["regle"] is None:
            textes.append("Aucune règle vérifiable avec les données disponibles.")
            continue
        r = REGLES[bl["regle"]]
        codes.append(bl["regle"])
        if bl["manquante"]:
            textes.append(f"Donnée manquante pour la règle « {r['regle']} » : compléter {r['questions'] or '—'}.")
        else:
            textes.append(r["regle"])
    return ", ".join(codes), " ".join(textes)


def nom(x: dict, i: int, defaut: str) -> str:
    return x["nom"] or f"{defaut} {i + 1}"


# ------------------------------------------------------------------ quantités (débouché opérationnel)
def _baies_par_orientation(l: dict) -> str:
    if l.get("aucune_baie"):
        return "aucune baie en façade"
    total, non_comptes = Counter(), set()
    for m in (l.get("murs") or [])[:moteur.NB_MURS_MAX]:
        o = m.get("orientation")
        if not o:
            continue
        for n in (m.get("baies") or {}).values():
            if isinstance(n, (int, float)) and not isinstance(n, bool):
                total[o] += int(n)
            else:
                non_comptes.add(o)
    orientations = [o for o in moteur.ORIENTATIONS if o in total or o in non_comptes]
    if not orientations:
        return "baies non décrites"
    morceaux = []
    for o in orientations:
        n = f"{total[o]} baie{'s' if total[o] > 1 else ''}" if total[o] else ""
        nc = "nombre non relevé" if o in non_comptes else ""
        morceaux.append(f"{o} : " + (" + ".join(t for t in (n, nc) if t)))
    return " ; ".join(morceaux)


def _nb(v, unite=""):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{v:g}{unite}"
    return "n.r."


def quantites(solution: str, entree: dict) -> str:
    """Éléments quantitatifs utiles à la consultation, selon la solution."""
    if solution.startswith("Protections") or solution == "Films solaires":
        return _baies_par_orientation(entree)
    if solution.startswith("Mise en place de brasseurs"):
        return f"{_nb(entree.get('L-03'), ' m²')}, hauteur libre {_nb(entree.get('PL-03'), ' m')}"
    if solution in ("Éclairage", "Occupation", "Équipements"):
        return f"{_nb(entree.get('L-03'), ' m²')}, {_nb(entree.get('L-04'), ' pers.')}"
    if solution in ("Par ventilation naturelle nocturne", "Par ventilation mécanique nocturne"):
        return f"{_nb(entree.get('L-03'), ' m²')} × {_nb(entree.get('PL-03'), ' m')}"
    if solution == "Toiture":
        return f"{_nb(entree.get('L-03'), ' m²')} sous toiture"
    if solution.startswith("Ombrage") or solution.startswith("Adaptation d'un préau"):
        return (f"effectif {_nb(entree.get('E-06'), ' pers.')}, ombrage hors végétaux "
                f"{_nb(entree.get('E-14'), ' m²')}")
    return ""


# ------------------------------------------------------------------ mise en page
def _t(texte) -> str:
    """Texte -> XML de Paragraph, avec les seuls caractères des polices standard."""
    s = html.escape(str(texte if texte is not None else ""), quote=False)
    for a, b in (("≤", "&lt;="), ("≥", "&gt;="), ("√", "racine "), ("▶", ""), ("\n", "<br/>")):
        s = s.replace(a, b)
    return s


def _styles():
    ss = getSampleStyleSheet()
    base = ParagraphStyle("base", parent=ss["Normal"], fontName="Helvetica", fontSize=9, leading=12)
    return {
        "base": base,
        "petit": ParagraphStyle("petit", parent=base, fontSize=7.5, leading=9.5),
        "cellule": ParagraphStyle("cellule", parent=base, fontSize=7.5, leading=9),
        "statut": ParagraphStyle("statut", parent=base, fontSize=7, leading=8.5, alignment=TA_CENTER,
                                 fontName="Helvetica-Bold"),
        "entete": ParagraphStyle("entete", parent=base, fontSize=7.5, leading=9, alignment=TA_CENTER,
                                 fontName="Helvetica-Bold"),
        "h1": ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=VERT,
                             spaceBefore=4, spaceAfter=8),
        "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=VERT,
                             spaceBefore=10, spaceAfter=5),
        "h3": ParagraphStyle("h3", parent=base, fontName="Helvetica-Bold", fontSize=9.5, leading=13, spaceBefore=7,
                             spaceAfter=3),
        "titre": ParagraphStyle("titre", parent=base, fontName="Helvetica-Bold", fontSize=22, leading=28,
                                textColor=VERT, alignment=TA_CENTER),
        "sous_titre": ParagraphStyle("sous_titre", parent=base, fontSize=13, leading=17, alignment=TA_CENTER),
        "puce": ParagraphStyle("puce", parent=base, leftIndent=10, bulletIndent=2),
    }


def _tableau(data, largeurs, style=(), entete=True):
    t = Table(data, colWidths=largeurs, repeatRows=1 if entete else 0)
    cmds = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8b8b8")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if entete:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9f1ec")))
    t.setStyle(TableStyle(cmds + list(style)))
    return t


def _fond(statut):
    return colors.HexColor(COULEURS.get(statut, ("#ffffff", "#000"))[0])


def _p_statut(statut, S):
    texte = COULEURS.get(statut, ("", "#000000"))[1]
    return Paragraph(f"<font color='{texte}'>{_t(statut or '—')}</font>", S["statut"])


# ------------------------------------------------------------------ sections
def _page_de_garde(audit, res, S):
    el = [Spacer(1, 45 * mm), Paragraph("Audit de faisabilité d'actions d'adaptation", S["titre"]),
          Spacer(1, 4 * mm), Paragraph("Plan rafraîchissement des écoles — compte rendu de visite", S["sous_titre"]),
          Spacer(1, 18 * mm)]
    lignes = [[Paragraph(f"<b>{_t(lib)}</b>", S["base"]), Paragraph(_t(audit.get(k) or "—"), S["base"])]
              for k, lib in CHAMPS_AUDIT]
    lignes.append([Paragraph("<b>Périmètre visité</b>", S["base"]),
                   Paragraph(f"{len(res['locaux'])} local(aux), {len(res['espaces'])} espace(s) extérieur(s)", S["base"])])
    lignes.append([Paragraph("<b>Édité le</b>", S["base"]), Paragraph(dt.date.today().strftime("%d/%m/%Y"), S["base"])])
    el.append(_tableau(lignes, [55 * mm, 110 * mm], entete=False))
    el += [Spacer(1, 18 * mm),
           Paragraph(_t(f"Méthode SURYA Ingénierie / ACTEE — {REFERENTIEL['version']}."), S["petit"]),
           Paragraph("Document établi à partir d'observations factuelles relevées lors de la visite. Il s'agit d'une "
                     "faisabilité de principe, qui ne vaut pas validation technique : l'audit n'est pas une mission "
                     "de maîtrise d'œuvre.", S["petit"]),
           PageBreak()]
    return el


def _cadre(S):
    el = [Paragraph("1. Cadre de l'audit", S["h1"]),
          Paragraph("L'audit est un <b>audit de faisabilité d'actions d'adaptation</b> à l'aléa « vagues de chaleur », "
                    "et non un diagnostic thermique. Il établit, pour chaque local et espace extérieur visité, quelles "
                    "solutions sont réalistes ou exclues compte tenu des usages et des contraintes constatées, ce qui "
                    "peut être engagé rapidement (consultation d'entreprises, travaux en régie) et ce qui exige "
                    "d'abord une validation par un tiers ou un approfondissement technique. Il ne classe pas les "
                    "bâtiments et ne sert pas à établir des priorités.", S["base"]),
          Spacer(1, 3 * mm),
          Paragraph("Chaque statut résulte de règles écrites, lues dans l'ordre : la première règle vérifiée donne le "
                    "statut. Si une donnée nécessaire est inconnue (« non évaluée » ou non renseignée), la solution "
                    "passe « Sous réserve ».", S["base"]),
          Paragraph("Statuts", S["h2"])]
    data = [[Paragraph("Statut", S["entete"]), Paragraph("Définition", S["entete"])]]
    style = []
    for i, st in enumerate(STATUTS, start=1):
        data.append([_p_statut(st, S), Paragraph(_t(DEFINITIONS_STATUTS[st]), S["cellule"])])
        style.append(("BACKGROUND", (0, i), (0, i), _fond(st)))
    el.append(_tableau(data, [50 * mm, 130 * mm], style))
    el.append(Paragraph("Alertes", S["h2"]))
    data = [[Paragraph("Type", S["entete"]), Paragraph("Signification", S["entete"])],
            [Paragraph("<b>AL</b> — alerte maîtrise d'œuvre", S["cellule"]),
             Paragraph("Une étude complémentaire par une maîtrise d'œuvre (ou une expertise équivalente) est "
                       "nécessaire avant de consulter.", S["cellule"])],
            [Paragraph("<b>VA</b> — validation ponctuelle", S["cellule"]),
             Paragraph("Un professionnel identifié (installateur, électricien, bureau de contrôle…) peut lever le "
                       "point sans étude de maîtrise d'œuvre.", S["cellule"])],
            [Paragraph("<b>Point d'attention</b>", S["cellule"]),
             Paragraph("Information utile à la conception ou à l'exploitation, sans validation requise.", S["cellule"])]]
    el.append(_tableau(data, [50 * mm, 130 * mm]))
    return el


def _synthese(res, S, titre="2. Synthèse des statuts", saut=True):
    el = ([PageBreak()] if saut else []) + [Paragraph(titre, S["h1"])]
    compte = Counter(s["statut"] for x in res["locaux"] + res["espaces"] for s in x["solutions"])
    data = [[_p_statut(st, S) for st in STATUTS], [Paragraph(f"<b>{compte.get(st, 0)}</b>", S["entete"]) for st in STATUTS]]
    el.append(_tableau(data, [30 * mm] * 6, [("BACKGROUND", (i, 0), (i, 0), _fond(st)) for i, st in enumerate(STATUTS)],
                       entete=False))
    el.append(Paragraph("Nombre de couples solution × local ou espace par statut.", S["petit"]))
    for titre, cle, defaut in (("Locaux", "locaux", "Local"), ("Espaces extérieurs", "espaces", "Espace")):
        entites = res[cle]
        if not entites:
            continue
        el.append(Paragraph(titre, S["h2"]))
        for debut in range(0, len(entites), 5):
            el.append(_tableau_statuts(entites[debut:debut + 5], debut, defaut, S))
            el.append(Spacer(1, 3 * mm))
    el.append(Paragraph("(?) statut « Sous réserve » dû à une donnée manquante · (!) alerte associée, voir la partie Alertes.", S["petit"]))
    return el


def _tableau_statuts(entites, debut, defaut, S):
    n = len(entites)
    largeur_col = min(30 * mm, 125 * mm / n)
    data = [[Paragraph("Solution", S["entete"])] + [Paragraph(_t(nom(x, debut + i, defaut)), S["entete"])
                                                    for i, x in enumerate(entites)]]
    style, groupe = [], None
    for j, s in enumerate(entites[0]["solutions"]):
        if s["groupe"] != groupe:
            groupe = s["groupe"]
            data.append([Paragraph(f"<b>{_t(groupe)}</b>", S["cellule"])] + [""] * n)
            r = len(data) - 1
            style += [("SPAN", (0, r), (-1, r)), ("BACKGROUND", (0, r), (-1, r), colors.HexColor("#f4f4f4"))]
        ligne = [Paragraph(_t(s["solution"]), S["cellule"])]
        r = len(data)
        for i, x in enumerate(entites):
            sx = x["solutions"][j]
            marques = (" (?)" if donnee_manquante(x, sx) else "") + (" (!)" if sx["alertes"] else "")
            ligne.append(_p_statut(sx["statut"] + marques, S))
            style.append(("BACKGROUND", (1 + i, r), (1 + i, r), _fond(sx["statut"])))
        data.append(ligne)
    return _tableau(data, [55 * mm] + [largeur_col] * n, style)


def _plan_action(res, d, S):
    """§ 3 : par solution, ce qui est engageable, à valider, en place, exclu."""
    el = [PageBreak(), Paragraph("3. Plan d'action par solution", S["h1"]),
          Paragraph("Pour chaque solution, les locaux et espaces sont classés selon la suite à donner. "
                    "« Engageable » : statut Recommandé ou À optimiser sans alerte maîtrise d'œuvre — la solution peut "
                    "faire l'objet d'une consultation d'entreprises ou de travaux en régie, après levée des éventuels "
                    "points de validation ponctuelle. « À valider » : alerte maîtrise d'œuvre ou statut Sous réserve. "
                    "Les quantités indiquées sont celles relevées lors de la visite.", S["base"])]
    rubriques = [("Engageable", "engageable"), ("À valider avant de consulter", "valider"),
                 ("Déjà en place", "en_place"), ("Exclue (non recommandée ou non adaptée)", "exclue")]
    for cle, defaut, entrees in (("locaux", "Local", d.get("locaux") or []), ("espaces", "Espace", d.get("espaces") or [])):
        entites = res[cle]
        if not entites:
            continue
        for j, s0 in enumerate(entites[0]["solutions"]):
            classes = defaultdict(list)
            for i, x in enumerate(entites):
                s = x["solutions"][j]
                types = {TYPES_ALERTE.get(a, "INFO") for a in s["alertes"]}
                code, texte = justification(x, s)
                if s["statut"] in (RECOMMANDE, A_OPTIMISER):
                    classe = "valider" if "AL" in types else "engageable"
                elif s["statut"] == SOUS_RESERVE:
                    classe = "valider"
                elif s["statut"] == EN_PLACE:
                    classe = "en_place"
                elif s["statut"] == NON_RECOMMANDE:
                    classe = "exclue"
                else:
                    continue
                points = [f"{a} ({TYPES_ALERTE.get(a, 'INFO')})" for a in s["alertes"]
                          if TYPES_ALERTE.get(a, "INFO") != "INFO"]
                classes[classe].append((nom(x, i, defaut), s["statut"], quantites(s0["solution"], entrees[i]),
                                        texte, code, points))
            if not classes:
                continue
            bloc = [Paragraph(f"{_t(s0['groupe'])} — {_t(s0['solution'])}", S["h3"])]
            data = [[Paragraph(h, S["entete"]) for h in ("Suite", "Local / espace", "Statut", "Quantités relevées",
                                                          "Motif (règle retenue)")]]
            style = []
            for lib, k in rubriques:
                for n_, st, q, texte, code, points in classes.get(k, []):
                    motif = texte + (f" [{code}]" if code else "")
                    if points:
                        motif += " — Points à lever : " + ", ".join(points) + "."
                    data.append([Paragraph(_t(lib), S["cellule"]), Paragraph(_t(n_), S["cellule"]), _p_statut(st, S),
                                 Paragraph(_t(q), S["cellule"]), Paragraph(_t(motif), S["cellule"])])
                    style.append(("BACKGROUND", (2, len(data) - 1), (2, len(data) - 1), _fond(st)))
            bloc.append(_tableau(data, [24 * mm, 30 * mm, 24 * mm, 36 * mm, 66 * mm], style))
            el.append(KeepTogether(bloc) if len(data) < 12 else bloc[0])
            if len(data) >= 12:
                el.append(bloc[1])
    return el


def _alertes(res, S, titre="4. Alertes et points de vigilance", saut=True):
    el = ([PageBreak()] if saut else []) + [Paragraph(titre, S["h1"]),
          Paragraph("Le type d'alerte (AL / VA) est proposé par l'outil d'après le tableau « Limites déclenchant une "
                    "alerte maîtrise d'œuvre » de la méthode.", S["petit"])]
    concernes = defaultdict(list)
    for cle, defaut in (("locaux", "Local"), ("espaces", "Espace")):
        for i, x in enumerate(res[cle]):
            codes = [a for s in x["solutions"] for a in s["alertes"]]
            if x.get("EX-AL") == 1:
                codes.insert(0, "EX-AL")
            for a in dict.fromkeys(codes):
                concernes[a].append(nom(x, i, defaut))
    if not concernes:
        el.append(Paragraph("Aucune alerte.", S["base"]))
        return el
    ordre = {"AL": 0, "VA": 1, "INFO": 2}
    data = [[Paragraph(h, S["entete"]) for h in ("Type", "Code", "Alerte", "Concerne")]]
    for a in sorted(concernes, key=lambda c: (ordre[TYPES_ALERTE.get(c, "INFO")], c)):
        typ = TYPES_ALERTE.get(a, "INFO")
        data.append([Paragraph(f"<b>{_t(LIBELLES_TYPE[typ])}</b>", S["cellule"]), Paragraph(a, S["cellule"]),
                     Paragraph(_t(REGLES[a]["regle"]), S["cellule"]), Paragraph(_t(", ".join(concernes[a])), S["cellule"])])
    el.append(_tableau(data, [30 * mm, 17 * mm, 88 * mm, 45 * mm]))
    return el


def _donnees_manquantes(res, S, titre="5. Données manquantes"):
    lignes = []
    for cle, defaut in (("locaux", "Local"), ("espaces", "Espace")):
        for i, x in enumerate(res[cle]):
            for s in x["solutions"]:
                if donnee_manquante(x, s):
                    lignes.append((nom(x, i, defaut), s["solution"], justification(x, s)[1]))
    el = [Paragraph(titre, S["h1"])]
    if not lignes:
        return el + [Paragraph("Aucune : tous les statuts sont établis sur des données renseignées.", S["base"])]
    el.append(Paragraph("Ces statuts « Sous réserve » ne traduisent pas un obstacle constaté mais une information "
                        "manquante. Les compléter permet de lever la réserve.", S["base"]))
    data = [[Paragraph(h, S["entete"]) for h in ("Local / espace", "Solution", "À compléter")]]
    data += [[Paragraph(_t(a), S["cellule"]), Paragraph(_t(b), S["cellule"]), Paragraph(_t(c), S["cellule"])]
             for a, b, c in lignes]
    el.append(_tableau(data, [40 * mm, 50 * mm, 90 * mm]))
    return el


def _reponse(v):
    if v is None or v == "" or v == []:
        return "—"
    if isinstance(v, list):
        return ", ".join(v)
    if isinstance(v, bool):
        return "oui" if v else "non"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def _questions_renseignees(sections, d, c, cb):
    from .questions import visible  # import tardif : questions.py dépend du moteur

    data = []
    for s in sections:
        lignes = [(q["code"], q["libelle"] + (f" ({q['unite']})" if q.get("unite") else ""), d.get(q["code"]))
                  for q in s["questions"] if visible(q["code"], c, d, cb) and q["type"] != "case"]
        if lignes:
            data.append(("section", s["titre"], None))
            data += lignes
    return data


def _table_reponses(lignes, S):
    data, style = [], []
    for code, lib, v in lignes:
        if code == "section":
            data.append([Paragraph(f"<b>{_t(lib)}</b>", S["cellule"]), ""])
            style += [("SPAN", (0, len(data) - 1), (1, len(data) - 1)),
                      ("BACKGROUND", (0, len(data) - 1), (1, len(data) - 1), colors.HexColor("#f4f4f4"))]
        else:
            data.append([Paragraph(f"{_t(lib)} <font color='#888888'>· {_t(code.removesuffix('b'))}</font>", S["cellule"]),
                         Paragraph(_t(_reponse(v)), S["cellule"])])
    return _tableau(data, [110 * mm, 70 * mm], style, entete=False) if data else Spacer(1, 1)


def _usagers(d, res, S, num):
    """Ressenti des usagers (questionnaire confort estival) et matrice de cohérence."""
    from . import questionnaire as QU

    reponses = d.get("questionnaires") or []
    m = QU.matrice(reponses, res)
    syn, ind = m["synthese"], m["synthese"]["indicateurs"]
    el = [PageBreak(), Paragraph(f"{num}. Ressenti des usagers", S["h1"]),
          Paragraph(f"Questionnaire confort estival : <b>{syn['repondants']} répondant(s)</b>, synthèse pour l'ensemble "
                    "de l'établissement. Enquête déclarative ponctuelle : elle ne remplace pas une campagne de mesures ; "
                    "ses résultats sont indicatifs et servent à orienter et vérifier les préconisations.", S["base"])]
    if syn["repondants"] < QU.MIN_REPONDANTS:
        el.append(Paragraph(f"Moins de {QU.MIN_REPONDANTS} réponses : synthèse non interprétable.", S["base"]))
    el.append(Paragraph("Indicateurs clés", S["h2"]))
    data = [[Paragraph(h, S["entete"]) for h in ("Indicateur", "Valeur", "Répondants")]]
    for cle_i, (lib, unite) in (("sensation_moyenne", ("Sensation thermique moyenne (Q4), de −3 très froide à +3 très chaude", "")),
                                ("preference_moyenne", ("Préférence moyenne (Q6), de −3 beaucoup plus froide à +3 beaucoup plus chaude", ""))):
        v = ind[cle_i]
        data.append([Paragraph(_t(lib), S["cellule"]), Paragraph("—" if v is None else f"{v:+.1f}", S["cellule"]), ""])
    for cle_i, lib in QU.LIBELLES_INDICATEURS.items():
        v = ind[cle_i]
        data.append([Paragraph(_t(lib), S["cellule"]),
                     Paragraph("—" if v["part"] is None else f"<b>{v['part']:.0%}</b>", S["cellule"]),
                     Paragraph(f"{v['nb']} / {v['sur']}", S["cellule"])])
    el.append(_tableau(data, [120 * mm, 25 * mm, 35 * mm]))

    el.append(Paragraph("Répartition des réponses", S["h2"]))
    for code in ("Q4", "Q5", "Q21", "Q8", "Q10", "Q22", "Q11", "Q12", "Q15", "Q13", "Q16", "Q18", "Q19", "Q20"):
        q = QU.PAR_CODE[code]
        rep_q = syn["repartition"][code]
        if not rep_q["repondants"]:
            continue
        lignes = [[Paragraph(_t(o), S["cellule"]), Paragraph(str(n), S["cellule"]),
                   Paragraph(f"{n / rep_q['repondants']:.0%}", S["cellule"])] for o, n in rep_q["comptes"].items()]
        bloc = [Paragraph(f"{code}. {_t(q['libelle'])} <font color='#888888'>({rep_q['repondants']} répondant(s)"
                          f"{', plusieurs réponses possibles' if q['type'] == 'multi' else ''})</font>", S["h3"]),
                _tableau(lignes, [110 * mm, 20 * mm, 20 * mm], entete=False)]
        el.append(KeepTogether(bloc))

    el.append(Paragraph("Correspondance ressenti / préconisations", S["h2"]))
    el.append(Paragraph(f"Proposition de matrice (à valider) : chaque ressenti est jugé « signalé » au-delà de "
                        f"{m['seuil']:.0%} des répondants, et rapproché des statuts de l'audit pour l'ensemble des "
                        f"locaux. Cohérent : ressenti et préconisation concordent. À vérifier : contradiction entre "
                        f"le ressenti et l'audit. Non corroboré : préconisation sans ressenti signalé (elle reste "
                        f"valable). Indicateur de cohérence : part des croisements évalués sans incohérence.", S["petit"]))
    couleurs = {QU.COHERENT: "#d3f0db", QU.A_VERIFIER: "#ffe2c2", QU.NON_CORROBORE: "#e6e6e6", QU.NON_EVALUABLE: "#ffffff"}
    data = [[Paragraph(h, S["entete"]) for h in ("Croisement", "Usagers", "Audit", "Résultat", "Commentaire")]]
    style = []
    for l in m["lignes"]:
        data.append([Paragraph(f"<b>{l['id']}</b> {_t(l['ressenti'])}", S["cellule"]), Paragraph(_t(l["usagers"]), S["cellule"]),
                     Paragraph(_t(l["audit"]), S["cellule"]), Paragraph(f"<b>{_t(l['resultat'])}</b>", S["cellule"]),
                     Paragraph(_t(l["commentaire"]), S["cellule"])])
        style.append(("BACKGROUND", (3, len(data) - 1), (3, len(data) - 1), colors.HexColor(couleurs[l["resultat"]])))
    el.append(_tableau(data, [34 * mm, 30 * mm, 28 * mm, 22 * mm, 66 * mm], style))
    if m["indicateur"] is not None:
        el.append(Paragraph(f"<b>Indicateur de cohérence : {m['indicateur']:.0%}</b> "
                            f"({m['evalues'] - m['a_verifier']} croisement(s) sans incohérence sur {m['evalues']} évalué(s)).",
                            S["base"]))
    if syn["remarques"]:
        el.append(Paragraph("Remarques libres", S["h2"]))
        el += [Paragraph(f"« {_t(t)} »", S["puce"], bulletText="•") for t in syn["remarques"][:30]]
    return el


def _fiches(res, d, S, num=6):
    from .questions import QUESTIONS_MUR, SECTIONS_BATIMENT, SECTIONS_ESPACE, SECTIONS_LOCAL

    cb = res["batiment"]
    el = [PageBreak(), Paragraph(f"{num}. Fiches détaillées", S["h1"]), Paragraph(f"{num}.1 Bâtiment", S["h2"])]
    el.append(_table_reponses(_questions_renseignees(SECTIONS_BATIMENT, d.get("batiment") or {}, cb, cb), S))
    facades = [(o, f) for o, f in (d.get("facades") or {}).items() if f.get("F-01")]
    if facades:
        el.append(Paragraph("Façades décrites", S["h3"]))
        qs = REFERENTIEL["facades"][1:]
        data = [[Paragraph("Orientation", S["entete"])] + [Paragraph(_t(q["libelle"]), S["entete"]) for q in qs]]
        data += [[Paragraph(f"<b>{o}</b>", S["cellule"])] + [Paragraph(_t(_reponse(f.get(q["code"]))), S["cellule"])
                                                            for q in qs] for o, f in facades]
        el.append(_tableau(data, [20 * mm] + [40 * mm] * len(qs)))

    for titre, cle, defaut, sections in ((f"{num}.2 Locaux", "locaux", "Local", SECTIONS_LOCAL),
                                         (f"{num}.3 Espaces extérieurs", "espaces", "Espace", SECTIONS_ESPACE)):
        entites = res[cle]
        if not entites:
            continue
        for i, x in enumerate(entites):
            entree = (d.get(cle) or [])[i]
            el.append(PageBreak())
            if i == 0:
                el.append(Paragraph(titre, S["h2"]))
            el.append(Paragraph(_t(nom(x, i, defaut)), S["h1"]))
            data = [[Paragraph(h, S["entete"]) for h in ("Solution", "Statut", "Justification (règle retenue)")]]
            style = []
            for s in x["solutions"]:
                code, texte = justification(x, s)
                alertes = "".join(f"<br/><b>{a} ({TYPES_ALERTE.get(a, 'INFO')})</b> : {_t(REGLES[a]['regle'])}"
                                  for a in s["alertes"])
                data.append([Paragraph(_t(s["solution"]), S["cellule"]), _p_statut(s["statut"], S),
                             Paragraph(_t(texte) + (f" <font color='#888888'>[{code}]</font>" if code else "") + alertes,
                                       S["cellule"])])
                style.append(("BACKGROUND", (1, len(data) - 1), (1, len(data) - 1), _fond(s["statut"])))
            el.append(_tableau(data, [45 * mm, 27 * mm, 108 * mm], style))
            if x.get("EX-AL") == 1:
                el.append(Paragraph(f"<b>EX-AL</b> : {_t(REGLES['EX-AL']['regle'])}", S["petit"]))
            if entree.get("observations"):
                el += [Paragraph("Observations de l'auditeur", S["h3"]), Paragraph(_t(entree["observations"]), S["base"])]
            el.append(CondPageBreak(40 * mm))
            el.append(Paragraph("Relevé de visite", S["h3"]))
            el.append(_table_reponses(_questions_renseignees(sections, entree, x["etats"], cb), S))
            if cle == "locaux":
                el.append(_table_murs(entree, QUESTIONS_MUR, S))
    return el


def _table_murs(l, questions_mur, S):
    if l.get("aucune_baie"):
        return Paragraph("Baies en façade : aucune.", S["cellule"])
    murs = [m for m in (l.get("murs") or [])[:moteur.NB_MURS_MAX] if m]
    if not murs:
        return Paragraph("Baies en façade : non décrites.", S["cellule"])
    qs = [q for q in questions_mur if q["type"] != "baies"]
    courts = {"orientation": "Orientation", "MEX-04": "Position des baies", "MEX-05": "Retrait vitrage (cm)",
              "MEX-06": "État des menuiseries", "MEX-07": "Débord"}
    data = [[Paragraph("Mur", S["entete"])] + [Paragraph(_t(courts.get(q["code"], q["libelle"])), S["entete"]) for q in qs]
            + [Paragraph("Baies (nombre)", S["entete"])]]
    for i, m in enumerate(murs, start=1):
        baies = ", ".join(f"{t} : {n if isinstance(n, (int, float)) else 'n.r.'}" for t, n in (m.get("baies") or {}).items())
        data.append([Paragraph(str(i), S["cellule"])] + [Paragraph(_t(_reponse(m.get(q["code"]))), S["cellule"]) for q in qs]
                    + [Paragraph(_t(baies or "—"), S["cellule"])])
    largeurs = [10 * mm, 18 * mm, 24 * mm, 20 * mm, 30 * mm, 22 * mm, 56 * mm]
    return KeepTogether([Paragraph("Baies en façade", S["h3"]), _tableau(data, largeurs[:len(data[0])])])


def _annexe(d, S):
    p = {**PARAMETRES_DEFAUT, **(d.get("parametres") or {})}
    el = [PageBreak(), Paragraph("Annexe — seuils utilisés", S["h1"])]
    data = [[Paragraph(h, S["entete"]) for h in ("Seuil", "Valeur", "Signification", "Règles")]]
    for q in REFERENTIEL["parametres"]:
        v = p[q["nom"]]
        modifie = v != q["valeur"]
        data.append([Paragraph(_t(q["nom"]), S["cellule"]),
                     Paragraph(f"{'<b>' if modifie else ''}{v:g} {_t(q['unite'])}{' (modifié)</b>' if modifie else ''}",
                               S["cellule"]),
                     Paragraph(_t(q["signification"]), S["cellule"]), Paragraph(_t(q["regles"]), S["cellule"])])
    el.append(_tableau(data, [32 * mm, 30 * mm, 93 * mm, 25 * mm]))
    el += [Spacer(1, 6 * mm),
           Paragraph("Méthode : © 2026 ACTEE et SURYA Ingénierie, diffusée sous licence CC BY-SA 4.0 "
                     "(https://creativecommons.org/licenses/by-sa/4.0/deed.fr).", S["petit"])]
    return el


def _entete_resultats(audit, res, S):
    """En-tête du PDF « résultats seuls » : titre, identification, légende des statuts."""
    el = [Paragraph("Résultats de l'audit de faisabilité d'actions d'adaptation", S["h1"])]
    ident = [f"<b>{_t(lib)}</b> : {_t(audit[k])}" for k, lib in CHAMPS_AUDIT if audit.get(k)]
    ident.append(f"<b>Périmètre</b> : {len(res['locaux'])} local(aux), {len(res['espaces'])} espace(s) extérieur(s)")
    ident.append(f"<b>Édité le</b> : {dt.date.today().strftime('%d/%m/%Y')}")
    el.append(Paragraph(" · ".join(ident), S["base"]))
    el.append(Spacer(1, 3 * mm))
    data = [[_p_statut(st, S) for st in STATUTS],
            [Paragraph(_t(DEFINITIONS_STATUTS[st]), S["petit"]) for st in STATUTS]]
    el.append(_tableau(data, [30 * mm] * 6, [("BACKGROUND", (i, 0), (i, 0), _fond(st)) for i, st in enumerate(STATUTS)],
                       entete=False))
    return el


# ------------------------------------------------------------------ point d'entrée
def generer_pdf(donnees: dict, complet: bool = True) -> bytes:
    """PDF de l'audit.

    ``complet=True`` : compte rendu complet (page de garde, cadre, synthèse, plan d'action, alertes,
    données manquantes, fiches détaillées, annexe).
    ``complet=False`` : résultats seuls (tableaux de statuts, alertes, données manquantes).
    """
    S = _styles()
    res = moteur.calculer(donnees)
    audit = donnees.get("audit") or {}
    titre_pied = " — ".join(t for t in (audit.get("etablissement"), audit.get("commune")) if t) or "Audit de faisabilité"

    def pied(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(15 * mm, 9 * mm, f"Audit de faisabilité d'actions d'adaptation — {titre_pied}"
                          .encode("cp1252", "replace").decode("cp1252"))
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"p. {doc.page}")
        canvas.setStrokeColor(VERT)
        canvas.line(15 * mm, 12 * mm, A4[0] - 15 * mm, 12 * mm)
        canvas.restoreState()

    if not complet:
        el = _entete_resultats(audit, res, S)
        if res["locaux"] or res["espaces"]:
            el += _synthese(res, S, "Statuts par solution", saut=False)
            el += [CondPageBreak(60 * mm)] + _alertes(res, S, "Alertes", saut=False) + [Spacer(1, 4 * mm)]
            el += _donnees_manquantes(res, S, "Données manquantes")
        else:
            el.append(Paragraph("Aucun local ni espace extérieur n'a été saisi.", S["base"]))
        return _construire(el, audit, titre_pied, "Résultats — audit de faisabilité d'actions d'adaptation", pied)

    el = _page_de_garde(audit, res, S) + _cadre(S)
    if res["locaux"] or res["espaces"]:
        el += _synthese(res, S) + _plan_action(res, donnees, S) + _alertes(res, S) + [Spacer(1, 6 * mm)]
        el += _donnees_manquantes(res, S)
    else:
        el += [PageBreak(), Paragraph("Aucun local ni espace extérieur n'a été saisi.", S["base"])]
    if audit.get("synthese"):
        el += [Paragraph("Commentaire général de l'auditeur", S["h2"]), Paragraph(_t(audit["synthese"]), S["base"])]
    num = 6
    if donnees.get("questionnaires"):
        el += _usagers(donnees, res, S, num)
        num += 1
    el += _fiches(res, donnees, S, num) + _annexe(donnees, S)
    return _construire(el, audit, titre_pied, "Compte rendu — audit de faisabilité d'actions d'adaptation", pied)


def _construire(el, audit, titre_pied, titre, pied) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm,
                            bottomMargin=17 * mm, title=titre, author=audit.get("auditeur") or "", subject=titre_pied)
    doc.build(el, onFirstPage=pied, onLaterPages=pied)
    return buf.getvalue()
