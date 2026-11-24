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
import re
from collections import Counter, defaultdict
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from reportlab.platypus import (CondPageBreak, Flowable, Image, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from . import moteur, plan
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
# Charte graphique ACTEE : couleurs de la gamme complémentaire, contrastes de la charte
# (texte blanc uniquement sur bleu, noir, vert foncé ou brun). Identiques à l'interface.
COULEURS = {  # fond, texte
    RECOMMANDE: ("#5bba50", "#000000"),
    A_OPTIMISER: ("#ff5400", "#000000"),
    EN_PLACE: ("#8dc8f8", "#000000"),
    SOUS_RESERVE: ("#ffc300", "#000000"),
    NON_RECOMMANDE: ("#634123", "#ffffff"),
    NON_CONCERNE: ("#e0e6de", "#000000"),
}
BLEU = colors.HexColor("#0a17a6")
NOIR = colors.black
GRIS = colors.HexColor("#e0e6de")
STATIQUE = Path(__file__).resolve().parent.parent / "static"
LOGO = STATIQUE / "logos" / "actee-fnccr-couleur.png"


def _polices():
    """Bitter (titrage) et Schibsted Grotesk (labeur) ; Helvetica en substitut si absentes."""
    polices = {"titre": "Bitter-Black", "titre2": "Bitter-ExtraBold", "texte": "Schibsted-Medium",
               "gras": "Schibsted-Bold", "extra": "Schibsted-ExtraBold"}
    fichiers = {"Bitter-Black": "Bitter-Black.ttf", "Bitter-ExtraBold": "Bitter-ExtraBold.ttf",
                "Schibsted-Medium": "SchibstedGrotesk-Medium.ttf", "Schibsted-Bold": "SchibstedGrotesk-Bold.ttf",
                "Schibsted-ExtraBold": "SchibstedGrotesk-ExtraBold.ttf"}
    try:
        for nom, f in fichiers.items():
            if nom not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(nom, str(STATIQUE / "fonts" / f)))
        pdfmetrics.registerFontFamily("Schibsted-Medium", normal="Schibsted-Medium", bold="Schibsted-Bold",
                           italic="Schibsted-Medium", boldItalic="Schibsted-Bold")
    except Exception:  # polices absentes : substituts
        return {"titre": "Helvetica-Bold", "titre2": "Helvetica-Bold", "texte": "Helvetica",
                "gras": "Helvetica-Bold", "extra": "Helvetica-Bold"}
    return polices

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
SUJETS_ALERTE = {  # libellé court, pour la synthèse
    "BR-AL": "électricité et fixation des brasseurs", "VN-AL1": "grilles ou ventelles pour ventiler la nuit en sécurité",
    "VV-AL": "tenue structurelle de la véranda", "OA-AL2": "prise au vent de la voile", "OA-AL3": "réaction au feu de la toile",
    "PR-AL1": "avis de l'architecte des bâtiments de France", "PR-AL2": "capacité de la charpente du préau",
    "PR-AL3": "repérage amiante",
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
    if not s["blocs"]:  # aucun bloc applicable : faute de donnée, ou cas non prévu par la méthode
        return s.get("cas_inconnu", True)
    return any(x["blocs"][b]["manquante"] for b in s["blocs"])


def questions_vides(x: dict, codes: str) -> str:
    """Parmi les questions citées par une règle (« PL-03, BA-12 »), celles qui restent sans réponse."""
    etats = {**(x.get("etats_batiment") or {}), **(x.get("etats") or {})}
    murs = (x.get("etats") or {}).get("murs") or []
    vides = []
    for c in [c.strip() for c in (codes or "").split(",") if c.strip()]:
        if c in etats:
            if etats[c] == moteur.INC:
                vides.append(c)
        elif c.startswith(("MEX-0", "F-0")) and murs:  # questions des murs et des façades : par mur
            if any(m.get(c) == moteur.INC or (c == "MEX-01" and not m.get("orientation")) for m in murs):
                vides.append(c)
        else:
            vides.append(c)
    return ", ".join(vides) or codes


def justification(x: dict, s: dict) -> tuple[str, str]:
    """(code de la règle retenue, texte expliquant le statut)."""
    if not s["blocs"]:
        if s["statut"] == NON_CONCERNE:
            return "", "L'espace ne comporte pas de cour de récréation."
        if not s.get("cas_inconnu", True):
            return "", ("Configuration non prévue par les règles de la méthode (aucun cas ne s'applique) : "
                        "à examiner au cas par cas.")
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
            textes.append(f"Donnée manquante pour la règle « {r['regle']} » : compléter "
                          f"{questions_vides(x, r['questions']) or '—'}.")
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
                if n > 0:
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
        return f"{_dec(v)}{unite}"
    return "n.r."


def _dec(v, signe=False, decimales=None) -> str:
    """Nombre à la française : virgule décimale."""
    if decimales is not None:
        t = f"{v:+.{decimales}f}" if signe else f"{v:.{decimales}f}"
    else:
        t = f"{v:+g}" if signe else f"{v:g}"
    return t.replace(".", ",")


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
    s = str(texte if texte is not None else "")
    for a, b in (("≤", "<="), ("≥", ">="), ("√", "racine "), ("▶", ""), ("→", "->"), ("−", "-")):
        s = s.replace(a, b)
    s = _imprimable(s)
    return html.escape(s, quote=False).replace("\n", "<br/>")


def _imprimable(s: str) -> str:
    """Retire les caractères que les polices standard des PDF ne savent pas afficher (emojis…)."""
    out = []
    for ch in s:
        try:
            ch.encode("cp1252")
            out.append(ch)
        except UnicodeEncodeError:
            if ch in "\u00a0\u202f":
                out.append(" ")
    return re.sub(r"[ \t]{2,}", " ", "".join(out))


class Titre1(Flowable):
    """Titre 1 de la charte : Bitter Black noir et séparateur noir (≈ 1/6 du corps)."""

    def __init__(self, texte, style):
        super().__init__()
        self.p = Paragraph(texte, style)
        self.style = style
        self.trait = max(2.5, style.fontSize / 6)

    def wrap(self, aw, ah):
        self.aw = aw
        _, self.hp = self.p.wrap(aw, ah)
        return aw, self.hp + self.trait + 4

    def draw(self):
        self.p.drawOn(self.canv, 0, self.trait + 4)
        self.canv.setFillColor(NOIR)
        self.canv.rect(0, 0, min(self.aw, 40 * mm), self.trait, stroke=0, fill=1)

    def getSpaceBefore(self):
        return self.style.spaceBefore

    def getSpaceAfter(self):
        return self.style.spaceAfter


def _styles():
    ss = getSampleStyleSheet()
    P = _polices()
    base = ParagraphStyle("base", parent=ss["Normal"], fontName=P["texte"], fontSize=9, leading=12,
                          textColor=NOIR)
    return {
        "base": base,
        "petit": ParagraphStyle("petit", parent=base, fontSize=7.5, leading=9.5),
        "cellule": ParagraphStyle("cellule", parent=base, fontSize=7.5, leading=9),
        "statut": ParagraphStyle("statut", parent=base, fontSize=7, leading=8.5, alignment=TA_CENTER,
                                 fontName=P["gras"]),
        "entete": ParagraphStyle("entete", parent=base, fontSize=7.5, leading=9, alignment=TA_CENTER,
                                 fontName=P["gras"], textColor=colors.white),
        "h1": ParagraphStyle("h1", parent=base, fontName=P["titre"], fontSize=16, leading=20, spaceBefore=4,
                             spaceAfter=9),
        "h2": ParagraphStyle("h2", parent=base, fontName=P["titre"], fontSize=12, leading=15, spaceBefore=10,
                             spaceAfter=5),
        "h3": ParagraphStyle("h3", parent=base, fontName=P["extra"], fontSize=9.5, leading=13, spaceBefore=7,
                             spaceAfter=3),
        "type_doc": ParagraphStyle("type_doc", parent=base, fontName=P["extra"], fontSize=11, leading=14,
                                   textColor=BLEU),
        "titre": ParagraphStyle("titre", parent=base, fontName=P["titre"], fontSize=26, leading=31),
        "sous_titre": ParagraphStyle("sous_titre", parent=base, fontName=P["extra"], fontSize=12.5, leading=16),
        "puce": ParagraphStyle("puce", parent=base, leftIndent=11, bulletIndent=1, bulletFontName="ZapfDingbats",
                                bulletFontSize=5.5, spaceAfter=1.5),  # puce carrée pleine (charte)
    }


def _tableau(data, largeurs, style=(), entete=True):
    t = Table(data, colWidths=largeurs, repeatRows=1 if entete else 0)
    cmds = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9aa39a")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if entete:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), BLEU))
    t.setStyle(TableStyle(cmds + list(style)))
    return t


def _fond(statut):
    return colors.HexColor(COULEURS.get(statut, ("#ffffff", "#000"))[0])


def _p_statut(statut, S):
    texte = COULEURS.get(statut, ("", "#000000"))[1]
    return Paragraph(f"<font color='{texte}'>{_t(statut or '—')}</font>", S["statut"])


# ------------------------------------------------------------------ sections
class Couverture(Flowable):
    """Illustration de couverture : grille 2×2 de carrés aux couleurs ACTEE, chacun portant une forme."""

    def __init__(self, cote=34 * mm):
        super().__init__()
        self.c = cote

    def wrap(self, aw, ah):
        return 2 * self.c, 2 * self.c

    def draw(self):
        c, k = self.canv, self.c
        bleu, orange, cyan, lila = BLEU, colors.HexColor("#ff5400"), colors.HexColor("#0dcccc"), colors.HexColor("#d1bffc")
        for x, y, fond in ((0, k, bleu), (k, k, orange), (0, 0, cyan), (k, 0, lila)):
            c.setFillColor(fond)
            c.rect(x, y, k, k, stroke=0, fill=1)
        c.setFillColor(orange)  # disque (énergie)
        c.circle(k / 2, 1.5 * k, k * 0.3, stroke=0, fill=1)
        c.setFillColor(bleu)  # quart de cercle (mouvement)
        c.wedge(k, -k, 3 * k, k, 90, 90, stroke=0, fill=1)
        c.setFillColor(colors.white)  # T / maison (bâtiment)
        c.rect(0.2 * k, 0.62 * k, 0.6 * k, 0.16 * k, stroke=0, fill=1)
        c.rect(0.42 * k, 0.15 * k, 0.16 * k, 0.5 * k, stroke=0, fill=1)
        c.setFillColor(lila)
        c.circle(1.5 * k, 1.5 * k, k * 0.22, stroke=0, fill=1)


def _logo(largeur=48 * mm):
    if not LOGO.exists():
        return Spacer(1, 15 * mm)
    img = Image(str(LOGO), width=largeur, height=largeur * 500 / 1600)
    img.hAlign = "LEFT"
    return img


def _page_de_garde(audit, res, S):
    el = [_logo(), Spacer(1, 22 * mm), Paragraph("Compte rendu de visite", S["type_doc"]), Spacer(1, 2 * mm),
          Titre1("Audit de faisabilité d'actions d'adaptation", S["titre"]),
          Spacer(1, 2 * mm), Paragraph("Plan rafraîchissement des écoles", S["sous_titre"]),
          Spacer(1, 10 * mm)]
    couverture = Couverture()
    couverture.hAlign = "LEFT"
    el += [couverture, Spacer(1, 12 * mm)]
    lignes = [[Paragraph(f"<b>{_t(lib)}</b>", S["base"]), Paragraph(_t(audit.get(k) or "—"), S["base"])]
              for k, lib in CHAMPS_AUDIT]
    lignes.append([Paragraph("<b>Périmètre visité</b>", S["base"]),
                   Paragraph(f"{len(res['locaux'])} local(aux), {len(res['espaces'])} espace(s) extérieur(s)", S["base"])])
    lignes.append([Paragraph("<b>Édité le</b>", S["base"]), Paragraph(dt.date.today().strftime("%d/%m/%Y"), S["base"])])
    t = _tableau(lignes, [55 * mm, 125 * mm], entete=False)
    t.hAlign = "LEFT"
    el.append(t)
    el += [Spacer(1, 8 * mm),
           Paragraph(_t(f"Méthode SURYA Ingénierie / ACTEE — {REFERENTIEL['version']}."), S["petit"]),
           Paragraph("Document établi à partir d'observations factuelles relevées lors de la visite. Il s'agit d'une "
                     "faisabilité de principe, qui ne vaut pas validation technique : l'audit n'est pas une mission "
                     "de maîtrise d'œuvre.", S["petit"]),
           PageBreak()]
    return el


def _cadre(S, titre="1. Cadre de l'audit"):
    el = [Titre1(titre, S["h1"]),
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
    el = ([PageBreak()] if saut else []) + [Titre1(titre, S["h1"])]
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
            style += [("SPAN", (0, r), (-1, r)), ("BACKGROUND", (0, r), (-1, r), GRIS)]
        ligne = [Paragraph(_t(s["solution"]), S["cellule"])]
        r = len(data)
        for i, x in enumerate(entites):
            sx = x["solutions"][j]
            marques = (" (?)" if donnee_manquante(x, sx) else "") + (" (!)" if sx["alertes"] else "")
            ligne.append(_p_statut(sx["statut"] + marques, S))
            style.append(("BACKGROUND", (1 + i, r), (1 + i, r), _fond(sx["statut"])))
        data.append(ligne)
    return _tableau(data, [55 * mm] + [largeur_col] * n, style)


def _plan_action(res, d, S, titre="3. Plan d'action par solution"):
    """Par solution, ce qui est engageable, à valider, en place, exclu (tableaux détaillés)."""
    el = [PageBreak(), Titre1(titre, S["h1"]),
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
    el = ([PageBreak()] if saut else []) + [Titre1(titre, S["h1"]),
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
    el = [Titre1(titre, S["h1"])]
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
        return _dec(v)
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
                      ("BACKGROUND", (0, len(data) - 1), (1, len(data) - 1), GRIS)]
        else:
            data.append([Paragraph(f"{_t(lib)} <font color='#888888'>· {_t(code.removesuffix('b'))}</font>", S["cellule"]),
                         Paragraph(_t(_reponse(v)), S["cellule"])])
    return _tableau(data, [110 * mm, 70 * mm], style, entete=False) if data else Spacer(1, 1)


def _indicateurs_usagers(syn, S):
    from . import questionnaire as QU

    ind = syn["indicateurs"]
    data = [[Paragraph(h, S["entete"]) for h in ("Indicateur", "Valeur", "Répondants")]]
    for cle_i, lib in (("sensation_moyenne", "Sensation thermique moyenne (Q4), de −3 très froide à +3 très chaude"),
                       ("preference_moyenne", "Préférence moyenne (Q6), de −3 beaucoup plus froide à +3 beaucoup plus chaude")):
        v = ind[cle_i]
        data.append([Paragraph(_t(lib), S["cellule"]), Paragraph("—" if v is None else _dec(v, signe=True, decimales=1), S["cellule"]), ""])
    for cle_i, lib in QU.LIBELLES_INDICATEURS.items():
        v = ind[cle_i]
        data.append([Paragraph(_t(lib), S["cellule"]),
                     Paragraph("—" if v["part"] is None else f"<b>{v['part']:.0%}</b>", S["cellule"]),
                     Paragraph(f"{v['nb']} / {v['sur']}", S["cellule"])])
    return _tableau(data, [120 * mm, 25 * mm, 35 * mm])


def _usagers(d, res, S, num):
    """Ressenti des usagers rapproché des résultats de la visite (matrice de correspondance)."""
    from . import questionnaire as QU

    reponses = d.get("questionnaires") or []
    m = QU.matrice(reponses, res)
    syn, ind = m["synthese"], m["synthese"]["indicateurs"]
    el = [PageBreak(), Titre1(f"{num}. Ressenti des usagers et résultats de la visite", S["h1"]),
          Paragraph(f"Questionnaire confort estival : <b>{syn['repondants']} répondant(s)</b>, synthèse pour l'ensemble "
                    "de l'établissement. Enquête déclarative ponctuelle : elle ne remplace pas une campagne de mesures ; "
                    "elle sert à confirmer ou à interroger les préconisations de la visite.", S["base"])]
    if syn["repondants"] < QU.MIN_REPONDANTS:
        el.append(Paragraph(f"Moins de {QU.MIN_REPONDANTS} réponses : synthèse non interprétable.", S["base"]))
    cles = [("trop_chaud_souvent", "ont trop chaud souvent ou très souvent"),
            ("inconfort", "jugent l'ambiance inconfortable"),
            ("soleil_gene", "sont gênés par le soleil direct"),
            ("fenetres_fermees_nuit", "ne peuvent pas laisser les fenêtres ouvertes la nuit")]
    chiffres = [(f"{ind[c]['part']:.0%}", lib) for c, lib in cles if ind[c]["part"] is not None]
    if chiffres:
        el += [Spacer(1, 3 * mm), _chiffres_cles(chiffres, S), Spacer(1, 2 * mm)]
    el.append(Paragraph("Ce que le ressenti confirme ou interroge", S["h2"]))
    el.append(Paragraph(f"Chaque ressenti est jugé « signalé » à partir de {m['seuil']:.0%} des répondants et rapproché "
                        "des statuts de la visite pour l'ensemble des locaux (matrice proposée, à valider). "
                        "<b>Cohérent</b> : ressenti et préconisation concordent. <b>À vérifier</b> : contradiction entre "
                        "le ressenti et la visite. <b>Non corroboré</b> : préconisation sans ressenti signalé (elle reste "
                        "valable).", S["petit"]))
    couleurs = {QU.COHERENT: "#5bba50", QU.A_VERIFIER: "#ff5400", QU.NON_CORROBORE: "#e0e6de", QU.NON_EVALUABLE: "#ffffff"}
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
        el.append(Paragraph("Remarques libres (extraits)", S["h2"]))
        freq = Counter(" ".join(t.split()) for t in syn["remarques"])
        el += [Paragraph(f"« {_t(t)} »" + (f" <font color='#555555'>({n_} fois)</font>" if n_ > 1 else ""), S["puce"],
                         bulletText="n") for t, n_ in freq.most_common(5)]
        if len(freq) > 5:
            el.append(Paragraph(f"{len(syn['remarques'])} remarques au total : voir l'annexe.", S["petit"]))
    return el


def _usagers_detail(d, S, titre):
    """Annexe : indicateurs complets et répartition des réponses."""
    from . import questionnaire as QU

    syn = QU.synthese(d.get("questionnaires") or [])
    el = [PageBreak(), Titre1(titre, S["h1"]),
          Paragraph(f"{syn['repondants']} répondant(s), synthèse pour l'ensemble de l'établissement.", S["base"]),
          Paragraph("Indicateurs", S["h2"]), _indicateurs_usagers(syn, S), Paragraph("Répartition des réponses", S["h2"])]
    for code in ("Q4", "Q5", "Q21", "Q8", "Q10", "Q22", "Q11", "Q12", "Q15", "Q13", "Q16", "Q18", "Q19", "Q20"):
        q = QU.PAR_CODE[code]
        rep_q = syn["repartition"][code]
        if not rep_q["repondants"]:
            continue
        lignes = [[Paragraph(_t(o), S["cellule"]), Paragraph(str(n), S["cellule"]),
                   Paragraph(f"{n / rep_q['repondants']:.0%}", S["cellule"])] for o, n in rep_q["comptes"].items()]
        bloc = [Paragraph(f"{code}. {_t(q['libelle'])} <font color='#555555'>({rep_q['repondants']} répondant(s)"
                          f"{', plusieurs réponses possibles' if q['type'] == 'multi' else ''})</font>", S["h3"]),
                _tableau(lignes, [110 * mm, 20 * mm, 20 * mm], entete=False)]
        el.append(KeepTogether(bloc))
    if syn["remarques"]:
        el.append(Paragraph("Remarques libres", S["h2"]))
        el += [Paragraph(f"« {_t(t)} »", S["puce"], bulletText="n") for t in syn["remarques"][:60]]
    return el


def _fiches(res, d, S, num="G", titre=None):
    from .questions import QUESTIONS_MUR, SECTIONS_BATIMENT, SECTIONS_ESPACE, SECTIONS_LOCAL

    cb = res["batiment"]
    el = [PageBreak(), Titre1(titre or f"{num}. Fiches détaillées", S["h1"]), Paragraph(f"{num}.1 Bâtiment", S["h2"])]
    el.append(_table_reponses(_questions_renseignees(SECTIONS_BATIMENT, d.get("batiment") or {}, cb, cb), S))
    if _photos(d, "batiment"):
        el += [Paragraph("Photos", S["h3"]), _planche(d, _photos(d, "batiment"), S, avec_lieu=False)]
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
            el.append(Titre1(_t(nom(x, i, defaut)), S["h1"]))
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
            if entree.get("observations"):
                el += [Paragraph("Observations de l'auditeur", S["h3"]), Paragraph(_t(entree["observations"]), S["base"])]
            ses_photos = _photos(d, f"{cle}:{entree.get('_id')}")
            if ses_photos:
                el += [CondPageBreak(55 * mm), Paragraph("Photos", S["h3"]), _planche(d, ses_photos, S, avec_lieu=False)]
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
        # MEX-05 n'a d'objet que pour des baies au nu intérieur ou en tunnel
        vis = lambda q: q["code"] != "MEX-05" or m.get("MEX-04") in ("Nu intérieur", "En tunnel")  # noqa: E731
        data.append([Paragraph(str(i), S["cellule"])]
                    + [Paragraph(_t(_reponse(m.get(q["code"]) if vis(q) else None)), S["cellule"]) for q in qs]
                    + [Paragraph(_t(baies or "—"), S["cellule"])])
    largeurs = [10 * mm, 18 * mm, 24 * mm, 20 * mm, 30 * mm, 22 * mm, 56 * mm]
    return KeepTogether([Paragraph("Baies en façade", S["h3"]), _tableau(data, largeurs[:len(data[0])])])


def _annexe(d, S, titre="Annexe — seuils utilisés"):
    p = {**PARAMETRES_DEFAUT, **(d.get("parametres") or {})}
    el = [PageBreak(), Titre1(titre, S["h1"])]
    data = [[Paragraph(h, S["entete"]) for h in ("Seuil", "Valeur", "Signification", "Règles")]]
    for q in REFERENTIEL["parametres"]:
        v = p[q["nom"]]
        modifie = v != q["valeur"]
        data.append([Paragraph(_t(q["nom"]), S["cellule"]),
                     Paragraph(f"{'<b>' if modifie else ''}{_dec(v)} {_t(q['unite'])}{' (modifié)</b>' if modifie else ''}",
                               S["cellule"]),
                     Paragraph(_t(q["signification"]), S["cellule"]), Paragraph(_t(q["regles"]), S["cellule"])])
    el.append(_tableau(data, [32 * mm, 30 * mm, 93 * mm, 25 * mm]))
    el += [Spacer(1, 6 * mm),
           Paragraph("Méthode : © 2026 ACTEE et SURYA Ingénierie, diffusée sous licence CC BY-SA 4.0 "
                     "(https://creativecommons.org/licenses/by-sa/4.0/deed.fr).", S["petit"])]
    return el


# ------------------------------------------------------------------ photos
def _photos(d: dict, cible: str | None = None, etiquettes=None) -> list[dict]:
    """Photos disponibles (image fournie), filtrées par cible et étiquette."""
    contenus = d.get("_photos") or {}
    return [ph for ph in d.get("photos") or [] if ph.get("id") in contenus and ph.get("cible")
            and (cible is None or ph["cible"] == cible) and (etiquettes is None or ph.get("etiquette") in etiquettes)]


def _image(d: dict, ph: dict, largeur: float, hauteur: float):
    from PIL import Image as PILImage
    contenu = d["_photos"][ph["id"]]
    try:
        l, h = PILImage.open(io.BytesIO(contenu)).size
    except Exception:
        return Spacer(1, 1)
    k = min(largeur / l, hauteur / h)
    img = Image(io.BytesIO(contenu), width=l * k, height=h * k)
    img.hAlign = "LEFT"
    return img


def _legende_photo(d: dict, ph: dict, avec_lieu: bool = True) -> str:
    from .photos import libelle_cible
    morceaux = [f"<b>{_t(libelle_cible(d, ph['cible']))}</b>"] if avec_lieu else []
    morceaux.append(_t(ph.get("etiquette") or ""))
    if ph.get("legende"):
        morceaux.append(_t(ph["legende"]))
    return " — ".join(m for m in morceaux if m)


def _planche(d: dict, liste: list[dict], S, colonnes: int = 3, hauteur: float = 42 * mm, avec_lieu: bool = True):
    """Planche de photos légendées, sans bordure (charte : angles droits, pas d'ombre)."""
    if not liste:
        return Spacer(1, 1)
    largeur = (180 * mm - 4 * mm * (colonnes - 1)) / colonnes
    cellules = [[_image(d, ph, largeur, hauteur), Paragraph(_legende_photo(d, ph, avec_lieu), S["petit"])] for ph in liste]
    lignes = [cellules[k:k + colonnes] for k in range(0, len(cellules), colonnes)]
    lignes[-1] += [""] * (colonnes - len(lignes[-1]))
    t = Table(lignes, colWidths=[largeur + 4 * mm] * colonnes)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def _photo_facade(d: dict):
    liste = _photos(d, "batiment", ("Façade",)) or _photos(d, "batiment")
    return liste[0] if liste else None


# ------------------------------------------------------------------ compte rendu orienté décision
SUITES = {"engager": "À engager", "valider": "À valider avant de consulter", "completer": "Données à compléter",
          "en_place": "Déjà en place", "exclue": "Écartée"}
COULEURS_SUITE = {"engager": "#5bba50", "valider": "#ffc300", "completer": "#e0e6de"}

# Ordre de mise en œuvre — PROPOSITION (docs/points_a_trancher.md, § G) : trois étapes, de la moins
# coûteuse et la plus rapide à la plus lourde. Une solution « À valider » garde l'étape qu'elle aurait
# une fois la validation obtenue.
PHASES = {
    1: ("Étape 1 — Dès maintenant", "Usages, réglages et remise en état : par l'exploitant ou en régie, coût nul "
        "ou faible, effet dès l'été qui vient."),
    2: ("Étape 2 — Petits travaux", "Équipements légers, sans intervention sur la structure : consultation simple, "
        "réalisables pendant les vacances d'été."),
    3: ("Étape 3 — Travaux sur le bâtiment", "Interventions sur l'enveloppe, la toiture ou les structures : "
        "à programmer, souvent avec une maîtrise d'œuvre."),
}
COULEURS_PHASE = {1: "#5bba50", 2: "#0dcccc", 3: "#8dc8f8"}
REMISE_EN_ETAT = ("Mise en place de brasseurs d'air plafonniers", "Protections verticales", "Protections horizontales",
                  "Sur fenêtres de toiture", "Sur vérandas et/ou verrières")
PETITS_TRAVAUX = ("Mise en place de brasseurs d'air plafonniers", "Films solaires", "Éclairage", "Sur fenêtres de toiture",
                  "Ombrage autoportant ou végétal de la cour")


def phase(solution: str, statut: str, alertes=()) -> int:
    """Étape de mise en œuvre proposée pour une solution dans un local ou un espace."""
    if solution in ("Occupation", "Équipements", "Par ventilation mécanique nocturne"):
        return 1  # organisation, extinction, programmation horaire de la ventilation
    if solution == "Par ventilation naturelle nocturne":
        return 2 if "VN-AL1" in alertes else 1  # consignes d'ouverture ; grilles ou ventelles à poser sinon
    if statut == A_OPTIMISER and solution in REMISE_EN_ETAT:
        return 1  # équipement présent : réparer, régler, remettre en service
    if solution in PETITS_TRAVAUX:
        return 2
    return 3


def _poids(entree: dict, cle: str) -> float:
    """Nombre de personnes concernées (effectif du local ou de l'espace), 1 à défaut."""
    v = entree.get("L-04" if cle == "locaux" else "E-06")
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else 1.0


def _libelle_solution(s0: dict) -> str:
    sol, grp = s0["solution"], s0["groupe"]
    if sol == "Toiture":
        return grp
    if sol in ("Occupation", "Éclairage", "Équipements") or sol.startswith(("Par ", "Sur ")):
        return f"{grp} : {sol[0].lower() + sol[1:]}"
    return sol


def _bilan(res: dict, d: dict) -> list[dict]:
    """Par solution : où l'engager, où la valider, où compléter, où elle est en place ou écartée."""
    out = []
    for cle, defaut in (("locaux", "Local"), ("espaces", "Espace")):
        entites, entrees = res[cle], d.get(cle) or []
        if not entites:
            continue
        for j, s0 in enumerate(entites[0]["solutions"]):
            b = {"solution": s0["solution"], "libelle": _libelle_solution(s0), "groupe": s0["groupe"], "cle": cle,
                 **{k: [] for k in SUITES}}
            for i, x in enumerate(entites):
                s = x["solutions"][j]
                entree = entrees[i] if i < len(entrees) else {}
                types = {TYPES_ALERTE.get(a, "INFO") for a in s["alertes"]}
                if s["statut"] in (RECOMMANDE, A_OPTIMISER):
                    k = "valider" if "AL" in types else "engager"
                elif s["statut"] == SOUS_RESERVE:
                    k = "completer" if donnee_manquante(x, s) else "valider"
                elif s["statut"] == EN_PLACE:
                    k = "en_place"
                elif s["statut"] == NON_RECOMMANDE:
                    k = "exclue"
                else:
                    continue
                b[k].append({"nom": nom(x, i, defaut), "poids": _poids(entree, cle), "statut": s["statut"],
                             "x": x, "s": s, "entree": entree,
                             "phase": phase(s0["solution"], s["statut"], s["alertes"])})
            for k in SUITES:
                b[k].sort(key=lambda e: -e["poids"])
            b["score"] = sum(e["poids"] for e in b["engager"]) + 0.5 * sum(e["poids"] for e in b["valider"])
            out.append(b)
    return sorted(out, key=lambda b: -b["score"])


def _ressentis_par_solution(d: dict) -> dict:
    """{solution: [« soleil direct gênant (64 %) », …]} pour les ressentis signalés par les usagers."""
    from . import questionnaire as QU

    reponses = d.get("questionnaires") or []
    if len(reponses) < QU.MIN_REPONDANTS:
        return {}
    ind = QU.synthese(reponses)["indicateurs"]
    out = defaultdict(list)
    for _, ressenti, cle, solutions, _ in QU.MATRICE:
        i = ind[cle]
        if solutions and i["part"] is not None and i["sur"] >= QU.MIN_REPONDANTS and i["part"] >= QU.SEUIL_SIGNAL:
            for sol in solutions:
                out[sol].append(f"{ressenti[0].lower() + ressenti[1:]} ({i['part']:.0%})")
    return out


def _lieux(entites, n=3) -> str:
    noms = [e["nom"] for e in entites]
    if len(noms) <= n:
        return ", ".join(noms)
    return ", ".join(noms[:n]) + f" et {len(noms) - n} autre(s)"


def _personnes(entites) -> str:
    total = sum(e["poids"] for e in entites if e["poids"] > 1)
    return f"{total:g} pers." if total else ""


def _chiffres_cles(chiffres, S):
    """Bandeau de chiffres clés (charte : Bitter Black dans des blocs de couleur)."""
    fonds = [("#0a17a6", colors.white), ("#ff5400", NOIR), ("#0dcccc", NOIR), ("#d1bffc", NOIR)]
    st_v = ParagraphStyle("cv", parent=S["base"], fontName=S["h1"].fontName, fontSize=19, leading=22)
    st_l = ParagraphStyle("cl", parent=S["base"], fontSize=7.5, leading=9)
    cellules, style = [], []
    for k, (v, lib) in enumerate(chiffres[:4]):
        fond, texte = fonds[k % 4]
        cellules.append([Paragraph(f"<font color='{texte.hexval().replace('0x', '#')}'>{_t(v)}</font>", st_v),
                         Paragraph(f"<font color='{texte.hexval().replace('0x', '#')}'>{_t(lib)}</font>", st_l)])
        style.append(("BACKGROUND", (k, 0), (k, 0), colors.HexColor(fond)))
    n = len(cellules)
    t = Table([cellules], colWidths=[180 * mm / n] * n)
    t.setStyle(TableStyle(style + [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7),
                                   ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    return t


def _phrase_batiment(d: dict, res: dict) -> str:
    b = d.get("batiment") or {}
    morceaux = []
    if b.get("B-01") and b["B-01"] != "Non renseigné":
        periode = b["B-01"]
        morceaux.append(f"bâtiment construit {periode[0].lower() + periode[1:]}" if periode.startswith(("De ", "Avant", "Après"))
                        else f"bâtiment ({periode})")
    if b.get("B-03"):
        morceaux.append(f"structure {b['B-03'].lower()}")
    if b.get("B-04"):
        morceaux.append(f"isolation des murs : {b['B-04']}")
    toit = b.get("B-18")
    if toit:
        t = toit.split(" (")[0].lower()
        if b.get("B-19") == "Isolée":
            t += " isolée" + (f" ({_dec(b['B-20'])} cm d'isolant)" if isinstance(b.get("B-20"), (int, float)) else "")
        elif b.get("B-19") == "Non isolée":
            t += " non isolée"
        if b.get("B-21") == "Oui":
            t += ", avec combles"
        morceaux.append(t)
    if b.get("B-09") == "Non":
        morceaux.append("pas de ventilation mécanique")
    elif b.get("B-09") == "Oui":
        morceaux.append("ventilation mécanique" + (f" {b['B-10'].lower()}" if b.get("B-10") and b["B-10"] != "Non évalué" else ""))
    if b.get("B-05") == "Oui" or b.get("B-06") == "Oui":
        morceaux.append("protection patrimoniale (avis de l'architecte des bâtiments de France)")
    if not morceaux:
        return ""
    txt = " ; ".join(morceaux)
    return txt[0].upper() + txt[1:] + "."


def _perimetre(d: dict, res: dict) -> dict:
    locaux, espaces = d.get("locaux") or [], d.get("espaces") or []
    num = lambda v: v if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else 0  # noqa: E731
    return {"nb_locaux": len(res["locaux"]), "nb_espaces": len(res["espaces"]),
            "surface": sum(num(l.get("L-03")) for l in locaux), "effectif": sum(num(l.get("L-04")) for l in locaux),
            "effectif_ext": max([num(e.get("E-06")) for e in espaces] or [0])}


def _synthese_decision(d, res, S):
    """Page 1 : le bâtiment en bref, les solutions principales et les points de vigilance."""
    audit = d.get("audit") or {}
    bil = _bilan(res, d)
    usagers = _ressentis_par_solution(d)
    per = _perimetre(d, res)
    n_pistes = 4 if d.get("questionnaires") else 3  # numéros des parties citées
    el = [Titre1("1. Synthèse", S["h1"])]

    # le bâtiment en bref
    nom_et = audit.get("etablissement") or "L'établissement"
    perim = (f"{per['nb_locaux']} local(aux) visité(s)" + (f" ({_dec(per['surface'])} m², {per['effectif']:g} personnes "
             "au plus)" if per["surface"] else "") + (f" et {per['nb_espaces']} espace(s) extérieur(s)" if per["nb_espaces"] else ""))
    bref = Paragraph(f"<b>{_t(nom_et)}</b>{' (' + _t(audit['commune']) + ')' if audit.get('commune') else ''} : "
                     f"{_t(perim)}. {_t(_phrase_batiment(d, res))}", S["base"])
    facade = _photo_facade(d)
    if facade:
        t = Table([[bref, _image(d, facade, 58 * mm, 36 * mm)]], colWidths=[120 * mm, 60 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (0, 0), 5 * mm)]))
        el.append(t)
    else:
        el.append(bref)
    engager = [b for b in bil if b["engager"]]
    nb_al = sum(1 for x in res["locaux"] + res["espaces"] for s in x["solutions"] for a in s["alertes"]
                if TYPES_ALERTE.get(a) == "AL")
    chiffres = [(f"{len(engager)}", "solutions à engager sans étude préalable"),
                (f"{sum(1 for b in bil if b['valider'])}", "solutions à valider avant de consulter"),
                (f"{nb_al}", "alertes maîtrise d'œuvre")]
    if d.get("questionnaires"):
        from . import questionnaire as QU
        i = QU.synthese(d["questionnaires"])["indicateurs"]["trop_chaud_souvent"]
        if i["part"] is not None:
            chiffres.append((f"{i['part']:.0%}", "des usagers ont trop chaud souvent ou très souvent"))
    if per["surface"] and len(chiffres) < 4:
        chiffres.append((f"{_dec(per['surface'])} m²", "de locaux visités"))
    el += [Spacer(1, 3 * mm), _chiffres_cles(chiffres, S), Spacer(1, 1 * mm)]
    if audit.get("synthese"):
        el += [Paragraph("L'avis de l'auditeur", S["h2"]), Paragraph(_t(audit["synthese"]), S["base"])]

    # solutions principales, dans l'ordre de mise en œuvre
    el.append(Paragraph("Les solutions principales, dans l'ordre de mise en œuvre", S["h2"]))
    if not engager:
        el.append(Paragraph("Aucune solution n'est engageable en l'état : voir les validations à obtenir.", S["base"]))
    candidats = []
    for b in engager:
        for ph in sorted({e["phase"] for e in b["engager"]}):
            ent = [e for e in b["engager"] if e["phase"] == ph]
            candidats.append((ph, -sum(e["poids"] for e in ent), b, ent))
    candidats.sort(key=lambda c: c[1])
    retenus = sorted(candidats[:7], key=lambda c: (c[0], c[1]))  # les plus utiles, rangés par étape
    lignes = []
    for ph, _, b, ent in retenus:
        quoi = f"<b>{_t(b['libelle'])}</b>"
        if ph == 1 and all(e["statut"] == A_OPTIMISER for e in ent) and b["solution"] in REMISE_EN_ETAT:
            quoi += " <font size='6.5'>(remise en état)</font>"
        detail = _t(_lieux(ent)) + (f" · {_personnes(ent)}" if _personnes(ent) else "")
        if usagers.get(b["solution"]):
            detail += f"<br/><font color='#0a17a6'>Confirmé par les usagers : {_t(usagers[b['solution']][0])}</font>"
        lignes.append((PHASES[ph][0].split(" — ")[0], COULEURS_PHASE[ph], quoi, detail))
    valider = sorted([b for b in bil if b["valider"]], key=lambda b: -sum(e["poids"] for e in b["valider"]))
    for b in valider[:3]:
        lignes.append(("À valider", COULEURS_SUITE["valider"], f"<b>{_t(b['libelle'])}</b>",
                       _t(_lieux(b["valider"])) + " · " + _t(_raison_valider(b))))
    if lignes:
        data, style = [], []
        for tag, coul, quoi, detail in lignes:
            data.append([Paragraph(tag, S["statut"]), Paragraph(quoi, S["cellule"]), Paragraph(detail, S["cellule"])])
            style.append(("BACKGROUND", (0, len(data) - 1), (0, len(data) - 1), colors.HexColor(coul)))
        t = Table(data, colWidths=[22 * mm, 66 * mm, 92 * mm])
        t.setStyle(TableStyle(style + [("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                       ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#9aa39a")),
                                       ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        el.append(t)
        el.append(Paragraph("Étape 1 : usages, réglages, remise en état · Étape 2 : petits travaux · Étape 3 : travaux "
                            f"sur le bâtiment (ordre proposé). Le détail figure à la partie {n_pistes}.", S["petit"]))

    # points de vigilance
    el.append(Paragraph("Points de vigilance", S["h2"]))
    puces = []
    al = _alertes_par_type(res)
    if al["AL"]:
        puces.append("Études de maîtrise d'œuvre à prévoir avant de consulter : "
                     + " ; ".join(f"{_t(SUJETS_ALERTE.get(a, a))} ({_t(_lieux([{'nom': n_} for n_ in lieux], 2))})"
                                  for a, lieux in al["AL"].items()) + ".")
    manquants = sum(len(b["completer"]) for b in bil)
    if manquants:
        puces.append(f"{manquants} statut(s) restent « Sous réserve » faute d'information : compléter le relevé "
                     f"lève la réserve (partie {n_pistes + 1}).")
    if d.get("questionnaires"):
        from . import questionnaire as QU
        m = QU.matrice(d["questionnaires"], res)
        for l in m["lignes"]:
            if l["resultat"] == QU.A_VERIFIER:
                puces.append(f"Ressenti des usagers à rapprocher de la visite : {_t(l['ressenti'][0].lower() + l['ressenti'][1:])} "
                             f"({_t(l['usagers'])}), voir partie 3.")
    if not puces:
        puces.append("Aucune alerte de maîtrise d'œuvre ni donnée manquante.")
    el += [Paragraph(p, S["puce"], bulletText="n") for p in puces[:5]]
    return el


def _motif(texte: str) -> str:
    """Motif lisible d'une règle : « Aucun cas précédent (x) » -> « x »."""
    m = re.match(r"Aucun cas précédent \((.*)\)\s*$", texte.strip())
    return m.group(1) if m else texte


def _fin(texte: str) -> str:
    return texte if texte.endswith((".", "…", "!", "?")) else texte + "."


def _court(texte: str, n: int = 110) -> str:
    texte = " ".join(str(texte).split())
    return texte if len(texte) <= n else texte[:n].rsplit(" ", 1)[0] + "…"


def _alertes_par_type(res) -> dict:
    out = {"AL": defaultdict(list), "VA": defaultdict(list), "INFO": defaultdict(list)}
    for cle, defaut in (("locaux", "Local"), ("espaces", "Espace")):
        for i, x in enumerate(res[cle]):
            codes = [a for s in x["solutions"] for a in s["alertes"]]
            if x.get("EX-AL") == 1:
                codes.insert(0, "EX-AL")
            for a in dict.fromkeys(codes):
                out[TYPES_ALERTE.get(a, "INFO")][a].append(nom(x, i, defaut))
    return out


def _raison_valider(b) -> str:
    raisons = []
    for e in b["valider"]:
        al = [a for a in e["s"]["alertes"] if TYPES_ALERTE.get(a) == "AL"]
        if al:
            raisons.append("étude de maîtrise d'œuvre (" + SUJETS_ALERTE.get(al[0], al[0]) + ")")
        else:
            raisons.append("vérification technique")
    return " et ".join(dict.fromkeys(raisons))


def _presentation(d, res, S):
    """Partie 2 : le bâtiment, les locaux et les espaces visités."""
    per = _perimetre(d, res)
    el = [PageBreak(), Titre1("2. Le bâtiment et le périmètre visité", S["h1"])]
    phrase = _phrase_batiment(d, res)
    el.append(Paragraph(_t(phrase) if phrase else "Caractéristiques du bâtiment non renseignées.", S["base"]))
    facades = [o for o, f in (d.get("facades") or {}).items() if f.get("F-01")]
    if facades:
        el.append(Paragraph(f"Façades décrites : {', '.join(facades)}.", S["base"]))
    schema = plan.dessin(d, res)
    if schema is not None:
        el += [Paragraph("Plan simplifié", S["h2"]), schema]
    locaux = d.get("locaux") or []
    if res["locaux"]:
        el.append(Paragraph(f"Locaux visités ({per['nb_locaux']} local(aux)"
                            + (f", {_dec(per['surface'])} m², {per['effectif']:g} personnes au plus" if per["surface"] else "")
                            + ")", S["h2"]))
        data = [[Paragraph(h, S["entete"]) for h in ("Local", "Usage", "Niveau", "Surface", "Effectif", "Baies par orientation")]]
        for i, x in enumerate(res["locaux"]):
            l = locaux[i] if i < len(locaux) else {}
            data.append([Paragraph(f"<b>{_t(nom(x, i, 'Local'))}</b>", S["cellule"]), Paragraph(_t(l.get("L-02") or "—"), S["cellule"]),
                         Paragraph(_t(l.get("L-09") or "—"), S["cellule"]), Paragraph(_nb(l.get("L-03"), " m²"), S["cellule"]),
                         Paragraph(_nb(l.get("L-04")), S["cellule"]), Paragraph(_t(_baies_par_orientation(l)), S["cellule"])])
        el.append(_tableau(data, [36 * mm, 38 * mm, 24 * mm, 17 * mm, 15 * mm, 50 * mm]))
    espaces = d.get("espaces") or []
    if res["espaces"]:
        el.append(Paragraph(f"Espaces extérieurs ({per['nb_espaces']})", S["h2"]))
        for i, x in enumerate(res["espaces"]):
            e = espaces[i] if i < len(espaces) else {}
            infos = []
            if e.get("E-02"):
                infos.append(", ".join(e["E-02"]) if isinstance(e["E-02"], list) else str(e["E-02"]))
            if isinstance(e.get("E-06"), (int, float)):
                infos.append(f"{e['E-06']:g} personnes au plus")
            if e.get("E-09"):
                infos.append(f"part à l'ombre en milieu de journée : {e['E-09']}")
            if e.get("E-10"):
                infos.append("ombre apportée par : " + (", ".join(e["E-10"]) if isinstance(e["E-10"], list) else str(e["E-10"])).lower())
            el.append(Paragraph(f"<b>{_t(nom(x, i, 'Espace'))}</b> : {_t('; '.join(infos) or 'non décrit')}.", S["puce"], bulletText="n"))
    obs = [(nom(x, i, "Local"), (locaux[i] if i < len(locaux) else {}).get("observations")) for i, x in enumerate(res["locaux"])]
    obs += [(nom(x, i, "Espace"), (espaces[i] if i < len(espaces) else {}).get("observations")) for i, x in enumerate(res["espaces"])]
    obs = [(n_, o) for n_, o in obs if o]
    if obs:
        el.append(Paragraph("Observations de visite", S["h2"]))
        el += [Paragraph(f"<b>{_t(n_)}</b> : {_t(o)}", S["puce"], bulletText="n") for n_, o in obs]
    choix = _photos(d, "batiment")[:2]
    for cle_liste in ("locaux", "espaces"):
        for x in d.get(cle_liste) or []:
            liste = _photos(d, f"{cle_liste}:{x.get('_id')}")
            vue = [ph for ph in liste if ph.get("etiquette") == "Vue d'ensemble"] or liste
            choix += vue[:1]
    if choix:
        el += [CondPageBreak(60 * mm), Paragraph("Photos de la visite", S["h2"]), _planche(d, choix[:9], S),
               Paragraph("Une photo par local ou espace ; toutes les photos figurent dans les fiches (annexe G).", S["petit"])]
    return el


def _pistes(d, res, S, num):
    """Pistes d'action rédigées, rangées par étape de mise en œuvre puis par personnes concernées."""
    bil = [b for b in _bilan(res, d) if b["engager"] or b["valider"] or b["completer"]]
    usagers = _ressentis_par_solution(d)
    el = [PageBreak(), Titre1(f"{num}. Pistes d'action, dans l'ordre de mise en œuvre", S["h1"]),
          Paragraph("Ordre proposé, en trois étapes, de la plus simple à la plus lourde. Dans chaque étape, les "
                    "solutions sont classées par nombre de personnes concernées. <b>À engager</b> : statut Recommandé "
                    "ou À optimiser sans alerte de maîtrise d'œuvre ; consultation d'entreprises ou travaux en régie. "
                    "<b>À valider</b> : une étude ou une vérification technique est nécessaire avant de consulter. "
                    "Les quantités sont celles relevées lors de la visite ; le détail par local figure en annexe C.",
                    S["petit"])]
    if not bil:
        return el + [Paragraph("Aucune solution à engager ni à valider.", S["base"])]
    for ph, (titre, intro) in PHASES.items():
        blocs = []
        for b in bil:
            eng = [e for e in b["engager"] if e["phase"] == ph]
            val = [e for e in b["valider"] if e["phase"] == ph]
            com = [e for e in b["completer"] if e["phase"] == ph]
            if eng or val or com:
                blocs.append((sum(e["poids"] for e in eng) + 0.5 * sum(e["poids"] for e in val), b, eng, val, com))
        if not blocs:
            continue
        el += [Paragraph(_t(titre), S["h2"]), Paragraph(_t(intro), S["petit"])]
        for _, b, eng, val, com in sorted(blocs, key=lambda x: -x[0]):
            el.append(KeepTogether(_bloc_piste(b, eng, val, com, usagers, ph, S)))
    return el


def _bloc_piste(b, eng, val, com, usagers, ph, S):
    titre = b["libelle"]
    if ph == 1 and eng and all(e["statut"] == A_OPTIMISER for e in eng) and b["solution"] in REMISE_EN_ETAT:
        titre += " (remise en état de l'existant)"
    bloc = [Paragraph(_t(titre), S["h3"])]
    if eng:
        lieux = " ; ".join(f"{_t(e['nom'])} ({_t(quantites(b['solution'], e['entree']))})"
                           if quantites(b["solution"], e["entree"]) else _t(e["nom"]) for e in eng)
        optim = [e["nom"] for e in eng if e["statut"] == A_OPTIMISER]
        txt = f"<b>À engager</b>{' (' + _personnes(eng) + ')' if _personnes(eng) else ''} : {lieux}."
        if optim and not titre.endswith("(remise en état de l'existant)"):
            txt += f" Existant à améliorer : {_t(', '.join(optim))}."
        va = {a for e in eng for a in e["s"]["alertes"] if TYPES_ALERTE.get(a) == "VA"}
        if va:
            txt += " Point à faire valider par un professionnel : " + " ; ".join(_t(SUJETS_ALERTE.get(a, a)) for a in sorted(va)) + "."
        bloc.append(Paragraph(txt, S["puce"], bulletText="n"))
    if val:
        par_motif = defaultdict(list)  # un même motif pour plusieurs locaux : cité une fois
        for e in val:
            al = [a for a in e["s"]["alertes"] if TYPES_ALERTE.get(a) == "AL"]
            motif = SUJETS_ALERTE.get(al[0], _court(REGLES[al[0]]["regle"])) if al else _court(_motif(justification(e["x"], e["s"])[1]), 130)
            par_motif[motif].append(e["nom"])
        details = [f"{_t(', '.join(noms))} ({_t(m[0].lower() + m[1:])})" for m, noms in par_motif.items()]
        bloc.append(Paragraph("<b>À valider avant de consulter</b> : " + " ; ".join(details) + ".", S["puce"], bulletText="n"))
    if com:
        bloc.append(Paragraph("<b>Données à compléter</b> : " + _t(", ".join(e["nom"] for e in com))
                              + " (voir annexe E).", S["puce"], bulletText="n"))
    reste = []
    if b["en_place"]:
        reste.append("déjà en place : " + ", ".join(e["nom"] for e in b["en_place"]))
    if b["exclue"]:
        reste.append("écartée : " + ", ".join(e["nom"] for e in b["exclue"]))
    if reste:
        txt = "; ".join(reste)
        bloc.append(Paragraph(_t(txt[0].upper() + txt[1:] + "."), S["petit"]))
    if usagers.get(b["solution"]):
        bloc.append(Paragraph(f"<font color='#0a17a6'>Ressenti des usagers : {_t(', '.join(usagers[b['solution']]))}.</font>",
                              S["petit"]))
    return bloc


def _points_a_lever(d, res, S, num):
    """Avant de consulter : études, validations et informations à obtenir."""
    al = _alertes_par_type(res)
    bil = _bilan(res, d)
    el = [Spacer(1, 4 * mm), CondPageBreak(60 * mm), Titre1(f"{num}. Avant de consulter : ce qu'il reste à lever", S["h1"])]
    for typ, titre, intro in (("AL", "Études de maîtrise d'œuvre", "Une étude par une maîtrise d'œuvre (ou une expertise "
                               "équivalente) est nécessaire avant de consulter des entreprises."),
                              ("VA", "Validations ponctuelles", "Un professionnel identifié (installateur, électricien, "
                               "bureau de contrôle…) peut lever le point sans étude de maîtrise d'œuvre.")):
        if not al[typ]:
            continue
        el.append(KeepTogether([Paragraph(titre, S["h2"]), Paragraph(intro, S["petit"])]
                               + [Paragraph(f"{_t(_court(REGLES[a]['regle'], 200))} — <i>{_t(_lieux([{'nom': n_} for n_ in lieux], 4))}</i>",
                                            S["puce"], bulletText="n") for a, lieux in al[typ].items()]))
    completer = defaultdict(list)
    for b in bil:
        for e in b["completer"]:
            completer[e["nom"]].append(b["solution"])
    if completer:
        el += [Paragraph("Informations à compléter", S["h2"]),
               Paragraph("Ces statuts « Sous réserve » ne traduisent pas un obstacle constaté mais une information "
                         "manquante ; le détail des questions figure en annexe E.", S["petit"])]
        el += [Paragraph(f"<b>{_t(n_)}</b> : {_t(', '.join(sols))}", S["puce"], bulletText="n") for n_, sols in completer.items()]
    points = _photos(d, etiquettes=("Point d'alerte", "Désordre"))
    if points:
        el += [Paragraph("Photos des points à lever", S["h2"]), _planche(d, points[:6], S, hauteur=36 * mm)]
    if not (al["AL"] or al["VA"] or completer):
        el.append(Paragraph("Rien à lever : les solutions à engager peuvent être consultées directement.", S["base"]))
    return el


def _entete_resultats(audit, res, S):
    """En-tête du PDF « résultats seuls » : titre, identification, légende des statuts."""
    el = [Titre1("Résultats de l'audit de faisabilité d'actions d'adaptation", S["h1"])]
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
def generer_pdf(donnees: dict, complet: bool = True, photos: dict | None = None) -> bytes:
    """PDF de l'audit.

    ``complet=True`` : compte rendu orienté décision — synthèse en une page, bâtiment et périmètre,
    ressenti des usagers rapproché de la visite, pistes d'action, points à lever — puis le détail en
    annexes (cadre, statuts, plan d'action détaillé, alertes, données manquantes, questionnaire,
    fiches, seuils).
    ``complet=False`` : résultats seuls (tableaux de statuts, alertes, données manquantes).
    ``photos`` : contenu des photos {id: jpeg} décrites dans ``donnees["photos"]`` (compte rendu complet).
    """
    S = _styles()
    donnees = dict(donnees, _photos=photos or {})
    res = moteur.calculer(donnees)
    audit = donnees.get("audit") or {}
    titre_pied = " — ".join(t for t in (audit.get("etablissement"), audit.get("commune")) if t) or "Audit de faisabilité"

    def pied(canvas, doc):
        canvas.saveState()
        canvas.setFont(_polices()["texte"], 7)
        canvas.setFillColor(NOIR)
        canvas.drawString(15 * mm, 9 * mm, f"Audit de faisabilité d'actions d'adaptation — {titre_pied}"
                          .encode("cp1252", "replace").decode("cp1252"))
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"p. {doc.page}")
        canvas.setStrokeColor(BLEU)
        canvas.setLineWidth(1.2)
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

    el = _page_de_garde(audit, res, S)
    entites = bool(res["locaux"] or res["espaces"])
    usagers = bool(donnees.get("questionnaires"))
    if entites:
        el += _synthese_decision(donnees, res, S) + _presentation(donnees, res, S)
        num = 3
        if usagers:
            el += _usagers(donnees, res, S, num)
            num += 1
        el += _pistes(donnees, res, S, num) + _points_a_lever(donnees, res, S, num + 1)
    else:
        el += [Titre1("1. Synthèse", S["h1"]), Paragraph("Aucun local ni espace extérieur n'a été saisi.", S["base"])]
        if audit.get("synthese"):
            el += [Paragraph("L'avis de l'auditeur", S["h2"]), Paragraph(_t(audit["synthese"]), S["base"])]
        el += _presentation(donnees, res, S)
    # annexes : le détail complet
    el += [PageBreak()] + _cadre(S, "Annexe A — Cadre de l'audit et définitions")
    if entites:
        el += _synthese(res, S, "Annexe B — Statuts par local et par espace")
        el += _plan_action(res, donnees, S, "Annexe C — Plan d'action détaillé")
        el += _alertes(res, S, "Annexe D — Alertes")
        el += [PageBreak()] + _donnees_manquantes(res, S, "Annexe E — Données manquantes")
    if usagers:
        el += _usagers_detail(donnees, S, "Annexe F — Questionnaire usagers : résultats détaillés")
    el += _fiches(res, donnees, S, "G", "Annexe G — Fiches détaillées")
    el += _annexe(donnees, S, "Annexe H — Seuils utilisés")
    return _construire(el, audit, titre_pied, "Compte rendu — audit de faisabilité d'actions d'adaptation", pied)


def _construire(el, audit, titre_pied, titre, pied) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm,
                            bottomMargin=17 * mm, title=titre, author=audit.get("auditeur") or "", subject=titre_pied)
    doc.build(el, onFirstPage=pied, onLaterPages=pied)
    return buf.getvalue()
