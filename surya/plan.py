"""Plan simplifié de l'établissement : un schéma de principe, pas un plan à l'échelle.

Chaque local est une boîte rangée sur la ligne de son niveau (L-09), de largeur proportionnelle à sa
surface (L-03). La couleur de la boîte dit le nombre de solutions à engager ; un trait orange sur un
côté signale des baies dans cette orientation (N en haut, S en bas, E à droite, O à gauche) ; un
disque orange signale une alerte maîtrise d'œuvre. Les espaces extérieurs forment la dernière ligne.

``dessin(donnees, res, largeur)`` renvoie un ``reportlab.graphics.shapes.Drawing`` : inséré tel quel
dans le PDF, converti en SVG pour l'interface (``svg(donnees, res)``).
"""
from __future__ import annotations

from collections import Counter

from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth

from . import moteur

BLEU, ORANGE, NOIR = colors.HexColor("#0a17a6"), colors.HexColor("#ff5400"), colors.black
# Nombre de solutions à engager -> (fond, texte). Échelle séquentielle de la charte ACTEE.
ECHELLE = [(0, "#e0e6de", NOIR, "aucune"), (1, "#d1bffc", NOIR, "1 à 2"), (3, "#0dcccc", NOIR, "3 à 4"),
           (5, "#0a17a6", colors.white, "5 ou plus")]
NIVEAUX = [("Dernier niveau", "Dernier niveau"), ("Étage intermédiaire", "Étage intermédiaire"),
           ("RDC", "RDC"), ("RDC et dernier niveau (plain-pied)", "RDC"), ("Sous-sol", "Sous-sol")]
ORDRE_LIGNES = ["Dernier niveau", "Étage intermédiaire", "RDC", "Sous-sol", "Niveau non renseigné"]
COTES = {"N": ("haut",), "NE": ("haut", "droite"), "E": ("droite",), "SE": ("bas", "droite"), "S": ("bas",),
         "SO": ("bas", "gauche"), "O": ("gauche",), "NO": ("haut", "gauche")}

POLICE, POLICE_GRAS = "Helvetica", "Helvetica-Bold"


def _polices():
    global POLICE, POLICE_GRAS
    try:
        from .rapport import _polices as p
        f = p()
        POLICE, POLICE_GRAS = f["texte"], f["gras"]
    except Exception:  # pragma: no cover - substituts
        pass


def _al() -> set:
    """Codes des alertes maîtrise d'œuvre (typage proposé dans rapport.TYPES_ALERTE)."""
    from .rapport import TYPES_ALERTE
    return {a for a, t in TYPES_ALERTE.items() if t == "AL"}


def a_engager(x: dict) -> int:
    """Nombre de solutions à engager : Recommandé ou À optimiser, sans alerte maîtrise d'œuvre."""
    return sum(1 for s in x["solutions"] if s["statut"] in (moteur.RECOMMANDE, moteur.A_OPTIMISER)
               and not (set(s["alertes"]) & _al()))


def alerte_moe(x: dict) -> bool:
    al = _al()
    return any(set(s["alertes"]) & al for s in x["solutions"])


def _couleur(n: int):
    fond, texte = ECHELLE[0][1], ECHELLE[0][2]
    for seuil, f, t, _ in ECHELLE:
        if n >= seuil:
            fond, texte = f, t
    return colors.HexColor(fond), texte


def _orientations(l: dict) -> Counter:
    tot = Counter()
    if l.get("aucune_baie"):
        return tot
    for m in (l.get("murs") or [])[:moteur.NB_MURS_MAX]:
        o = m.get("orientation")
        if o:
            n = sum(v for v in (m.get("baies") or {}).values() if isinstance(v, (int, float)) and not isinstance(v, bool))
            tot[o] += max(int(n), 1)
    return tot


def _lignes_texte(texte: str, largeur: float, police: str, taille: float, max_lignes: int = 2) -> list[str]:
    mots, lignes, cour = texte.split(), [], ""
    for m in mots:
        essai = (cour + " " + m).strip()
        if stringWidth(essai, police, taille) <= largeur:
            cour = essai
        else:
            if cour:
                lignes.append(cour)
            cour = m
    if cour:
        lignes.append(cour)
    if len(lignes) > max_lignes:
        lignes = lignes[:max_lignes]
        while lignes[-1] and stringWidth(lignes[-1] + "…", police, taille) > largeur:
            lignes[-1] = lignes[-1][:-1]
        lignes[-1] += "…"
    return [l if stringWidth(l, police, taille) <= largeur else l[: max(1, int(len(l) * largeur / stringWidth(l, police, taille)) - 1)] + "…"
            for l in lignes]


def _boites(donnees: dict, res: dict) -> list[tuple[str, list[dict]]]:
    """[(libellé de la ligne, [boîte])] dans l'ordre du haut vers le bas."""
    niv = dict(NIVEAUX)
    lignes: dict[str, list[dict]] = {k: [] for k in ORDRE_LIGNES}
    locaux = donnees.get("locaux") or []
    for i, x in enumerate(res["locaux"]):
        l = locaux[i] if i < len(locaux) else {}
        surf = l.get("L-03") if isinstance(l.get("L-03"), (int, float)) and not isinstance(l.get("L-03"), bool) else None
        lignes[niv.get(l.get("L-09"), "Niveau non renseigné")].append(
            {"nom": x["nom"] or f"Local {i + 1}", "surface": surf, "n": a_engager(x), "al": alerte_moe(x),
             "orient": _orientations(l), "plain_pied": l.get("L-09") == "RDC et dernier niveau (plain-pied)"})
    out = [(k, v) for k, v in ((k, lignes[k]) for k in ORDRE_LIGNES) if v]
    espaces = donnees.get("espaces") or []
    ext = []
    for i, x in enumerate(res["espaces"]):
        e = espaces[i] if i < len(espaces) else {}
        ext.append({"nom": x["nom"] or f"Espace {i + 1}", "surface": None, "n": a_engager(x), "al": alerte_moe(x),
                    "orient": Counter(), "exterieur": True, "effectif": e.get("E-06")})
    if ext:
        out.append(("Extérieur", ext))
    return out


def dessin(donnees: dict, res: dict, largeur: float = 180 * mm, legende: bool = True) -> Drawing | None:
    """Schéma de principe ; None s'il n'y a ni local ni espace."""
    _polices()
    lignes = _boites(donnees, res)
    if not lignes:
        return None
    marge_g, h_boite, ecart, min_l = 31 * mm, 17 * mm, 2.2 * mm, 24 * mm
    utile = largeur - marge_g
    # découpage des lignes trop chargées en sous-lignes
    rangees = []
    toutes = [b["surface"] for _, bs in lignes for b in bs if b["surface"]]
    ref = (sum(toutes) / len(toutes)) if toutes else 50  # surface prêtée à un local sans surface relevée
    for lib, boites in lignes:
        for b in boites:
            b["poids"] = max(b["surface"] or ref, ref * 0.45)
        cour, poids = [], 0.0
        for b in boites:
            if cour and (len(cour) + 1) * min_l + len(cour) * ecart > utile:
                rangees.append((lib, cour))
                lib, cour = "", []
            cour.append(b)
        rangees.append((lib, cour))
    # une même échelle pour tous les niveaux : un niveau peu occupé reste court
    interieures = [bs for lib, bs in rangees if not any(b.get("exterieur") for b in bs)]
    echelle = min(((utile - ecart * (len(bs) - 1)) / sum(b["poids"] for b in bs) for bs in interieures), default=1.0)
    h_legende = 15 * mm if legende else 0
    hauteur = len(rangees) * (h_boite + 4.5 * mm) + h_legende + 2 * mm
    d = Drawing(largeur, hauteur)
    y = hauteur - h_boite - 1 * mm
    for lib, boites in rangees:
        if lib:
            d.add(String(0, y + h_boite / 2 + 1, lib if lib != "Extérieur" else "Extérieur",
                         fontName=POLICE_GRAS, fontSize=7.5, fillColor=NOIR))
            d.add(Line(0, y + h_boite / 2 - 2.5, marge_g - 3 * mm, y + h_boite / 2 - 2.5, strokeColor=NOIR, strokeWidth=1.6))
        dispo = utile - ecart * (len(boites) - 1)
        if any(b.get("exterieur") for b in boites):  # sans surface : largeur fixe
            larg = [max(min_l, min(dispo / len(boites), utile * 0.55))] * len(boites)
        else:
            larg = [max(min_l, b["poids"] * echelle) for b in boites]
        k = dispo / sum(larg)
        larg = [l * k for l in larg] if k < 1 else larg
        x = marge_g
        for b, w in zip(boites, larg):
            fond, texte = _couleur(b["n"])
            if b.get("exterieur"):
                d.add(Rect(x, y, w, h_boite, fillColor=fond, strokeColor=colors.HexColor("#05700f"), strokeWidth=1.2,
                           strokeDashArray=[3, 2]))
            else:
                d.add(Rect(x, y, w, h_boite, fillColor=fond, strokeColor=NOIR, strokeWidth=0.6))
            for o, nb in b["orient"].items():  # côtés exposés : baies dans cette orientation
                for cote in COTES.get(o, ()):
                    ep = 2.6
                    if cote == "haut":
                        d.add(Rect(x, y + h_boite - ep, w, ep, fillColor=ORANGE, strokeColor=None))
                    elif cote == "bas":
                        d.add(Rect(x, y, w, ep, fillColor=ORANGE, strokeColor=None))
                    elif cote == "gauche":
                        d.add(Rect(x, y, ep, h_boite, fillColor=ORANGE, strokeColor=None))
                    else:
                        d.add(Rect(x + w - ep, y, ep, h_boite, fillColor=ORANGE, strokeColor=None))
            tx = x + 4
            from .rapport import _imprimable  # les polices du PDF n'affichent pas les emojis
            noms = _lignes_texte(_imprimable(b["nom"]).strip() or "—", w - 9, POLICE_GRAS, 6.8)
            ty = y + h_boite - 9
            for ligne in noms:
                d.add(String(tx, ty, ligne, fontName=POLICE_GRAS, fontSize=6.8, fillColor=texte))
                ty -= 7.6
            info = []
            if b["surface"]:
                info.append(f"{b['surface']:g} m²".replace(".", ","))
            if b.get("exterieur") and isinstance(b.get("effectif"), (int, float)):
                info.append(f"{b['effectif']:g} pers.")
            info.append(f"{b['n']} à engager")
            pied = " · ".join(info)
            if stringWidth(pied, POLICE, 6.2) > w - 8:
                pied = f"{b['n']} à engager"
            d.add(String(tx, y + 5, pied, fontName=POLICE, fontSize=6.2, fillColor=texte))
            if b["al"]:
                d.add(Circle(x + w - 6.5, y + h_boite - 6.5, 4.2, fillColor=ORANGE, strokeColor=None))
                d.add(String(x + w - 6.5, y + h_boite - 8.8, "!", fontName=POLICE_GRAS, fontSize=6.5,
                             fillColor=NOIR, textAnchor="middle"))
            x += w + ecart
        y -= h_boite + 4.5 * mm
    if legende:
        _legende(d, 0, 4 * mm, largeur)
    return d


def _legende(d: Drawing, x0: float, y0: float, largeur: float):
    x = x0
    d.add(String(x, y0 + 13, "Solutions à engager par local :", fontName=POLICE_GRAS, fontSize=6.5, fillColor=NOIR))
    x = x0 + stringWidth("Solutions à engager par local :", POLICE_GRAS, 6.5) + 6
    for _, fond, _, lib in ECHELLE:
        d.add(Rect(x, y0 + 11, 9, 7, fillColor=colors.HexColor(fond), strokeColor=NOIR, strokeWidth=0.4))
        d.add(String(x + 12, y0 + 12.5, lib, fontName=POLICE, fontSize=6.5, fillColor=NOIR))
        x += 16 + stringWidth(lib, POLICE, 6.5) + 6
    x += 4
    d.add(Rect(x, y0 + 11, 12, 2.6, fillColor=ORANGE, strokeColor=None))
    d.add(String(x + 15, y0 + 12.5, "côté avec baies", fontName=POLICE, fontSize=6.5, fillColor=NOIR))
    x += 15 + stringWidth("côté avec baies", POLICE, 6.5) + 10
    d.add(Circle(x + 3.5, y0 + 14.2, 3.6, fillColor=ORANGE, strokeColor=None))
    d.add(String(x + 10, y0 + 12.5, "alerte maîtrise d'œuvre", fontName=POLICE, fontSize=6.5, fillColor=NOIR))
    d.add(String(x0, y0, "Schéma de principe, ni à l'échelle ni à l'emplacement réel : une ligne par niveau, largeur selon la "
                         "surface ; côté exposé : N en haut, S en bas, E à droite, O à gauche.",
                 fontName=POLICE, fontSize=6.2, fillColor=NOIR))


def svg(donnees: dict, res: dict, largeur: float = 180 * mm) -> str | None:
    """Le schéma en SVG (interface)."""
    from reportlab.graphics import renderSVG

    d = dessin(donnees, res, largeur)
    if d is None:
        return None
    s = renderSVG.drawToString(d)
    s = s[s.index("<svg"):]
    # largeur fluide : la balise garde son viewBox, la largeur suit le conteneur (max. 900 px)
    debut = s.index(">")
    entete = s[:debut]
    import re
    entete = re.sub(r'width="[^"]+" height="[^"]+"', 'width="100%" style="max-width:900px;height:auto"', entete, count=1)
    s = entete + s[debut:]
    s = s.replace("<title>...</title>", "<title>Plan simplifié</title>").replace("<desc>...</desc>", "")
    # polices : Schibsted Grotesk intégrée au SVG (une image SVG n'accède pas aux polices de la page)
    import base64
    from pathlib import Path
    polices = Path(__file__).resolve().parent.parent / "static" / "fonts"
    faces = []
    for fichier, graisse in (("SchibstedGrotesk-Medium.ttf", 500), ("SchibstedGrotesk-Bold.ttf", 700)):
        if (polices / fichier).exists():
            b64 = base64.b64encode((polices / fichier).read_bytes()).decode()
            faces.append(f"@font-face{{font-family:'Schibsted Grotesk';font-weight:{graisse};"
                         f"src:url(data:font/ttf;base64,{b64}) format('truetype');}}")
    for nom, graisse in (("Schibsted-Medium", 500), ("Schibsted-Bold", 700), ("Helvetica-Bold", 700), ("Helvetica", 500)):
        s = s.replace(f"font-family: {nom};", f"font-family: 'Schibsted Grotesk', Arial, sans-serif; font-weight: {graisse};")
    if faces:
        fin = s.index(">") + 1
        s = s[:fin] + "<style>" + "".join(faces) + "</style>" + s[fin:]
    return s
