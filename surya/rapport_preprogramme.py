"""PDF « Pré-programme d'adaptation à la chaleur » remis à la collectivité à la fin du diagnostic.

Document pédagogique, à lire par des élus et des services non spécialistes, qui dit :

1. l'essentiel (ce que l'on propose, pour quel budget, avec qui) ;
2. ce que l'on veut faire et pourquoi, levier par levier ;
3. local par local, les opérations prévues et les points à vérifier ;
4. comment on va le faire : calendrier, maîtrise d'œuvre, accompagnement, études préalables ;
5. les prochaines étapes et la validation.

``generer_pdf(donnees)`` renvoie le PDF (bytes). Aucune dépendance à Streamlit. Les CCTP et les fiches
détaillées viennent ensuite (plan d'action et dossier de consultation).
"""
from __future__ import annotations

import datetime as dt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, KeepTogether, PageBreak, Paragraph, Spacer

from . import moteur, travaux
from .rapport import BLEU, NOIR, Titre1, _construire, _logo, _polices, _styles, _t, _tableau
from .rapport_travaux import COULEURS_HORIZON, COULEURS_NIVEAU

ORDRE_LEVIERS = list(travaux.LEVIERS)
COURT = {
    "Mise en place de brasseurs d'air plafonniers": "Brasseurs d'air",
    "Par ventilation naturelle nocturne": "Ventilation naturelle de nuit",
    "Par ventilation mécanique nocturne": "Ventilation mécanique de nuit",
    "Protections verticales": "Protections solaires mobiles",
    "Protections horizontales": "Casquettes au sud",
    "Films solaires": "Films solaires",
    "Sur fenêtres de toiture": "Protection des fenêtres de toit",
    "Sur vérandas et/ou verrières": "Protection de la verrière",
    "Toiture": "Traitement de la toiture",
    "Occupation": "Réorganisation de l'occupation",
    "Éclairage": "Éclairage LED",
    "Équipements": "Équipements qui chauffent",
    "Ombrage rapporté adossé au bâtiment": "Voile adossée",
    "Adaptation d'un préau existant": "Adaptation du préau",
    "Ombrage autoportant ou végétal de la cour": "Ombrage de la cour",
}


def court(o: dict) -> str:
    return COURT.get(o["solution"], o["libelle"])


def _encadre(texte, S, fond="#e0e6de"):
    return _tableau([[Paragraph(texte, S["base"])]], [180 * mm], entete=False,
                    style=[("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fond)),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                           ("LEFTPADDING", (0, 0), (-1, -1), 6)])


def _bref(fiche: int, solution: str | None = None) -> str:
    """Résumé de l'action (propre à la solution s'il existe, sinon celui de la fiche du kit), sans les mentions
    internes (niveaux A/B/C)."""
    propre = travaux.CATALOGUE.get(solution or "", {}).get("bref")
    if propre:
        return propre
    phrases = travaux.FICHES[fiche]["en_bref"].split(". ")
    return ". ".join(x for x in phrases if not x.startswith("Niveau")).strip()


def _qui_fait(o: dict, e: dict) -> str:
    if o in e["ops_moe"]:
        return "Maîtrise d'œuvre"
    if o["niveau"] == "A":
        return "Collectivité, en régie ou sur devis"
    if o["niveau"] == "B":
        return "Collectivité, consultation avec le CCTP du kit"
    return "Étude préalable par un bureau d'études ou un architecte"


# ------------------------------------------------------------------ 1. l'essentiel
def _essentiel(d, e, S):
    audit = d.get("audit") or {}
    el = [_logo(), Spacer(1, 4 * mm), Paragraph("Plan canicule des écoles", S["type_doc"]),
          Paragraph("Pré-programme d'adaptation à la chaleur", S["titre"]), Spacer(1, 2 * mm)]
    ident = " · ".join(_t(audit[k]) for k in ("etablissement", "commune") if audit.get(k)) or "Établissement"
    el.append(Paragraph(f"<b>{ident}</b> · diagnostic du {_t(audit.get('date_visite') or 'n.r.')} · édité le "
                        f"{dt.date.today().strftime('%d/%m/%Y')}", S["base"]))
    de = travaux.externe(d)
    if de:
        el.append(Paragraph("Établi à partir du diagnostic « " + _t(de.get("source") or "diagnostic existant") + " »"
                            + (f" du {_t(de['date'])}" if de.get("date") else "")
                            + ", réalisé hors de la méthode ACTEE-SURYA et repris par l'auditeur.", S["petit"]))
    statut = ("Version validée par l'auditeur et visée par "
              f"{_t(e['choix']['validation']['visa'])}" if e["valide"] else
              "PROJET — à valider par l'auditeur et à viser par le chargé de mission ou l'économe de flux avant remise")
    el += [Spacer(1, 2 * mm), _encadre(f"<b>{statut}</b>", S, "#e0e6de" if e["valide"] else "#ffc300")]
    el += [Spacer(1, 4 * mm), Paragraph(
        "Ce document résume ce que le diagnostic de confort d'été propose pour protéger les élèves et le personnel "
        "de la chaleur : <b>ce que l'on veut faire</b>, <b>pourquoi</b>, <b>où</b> et <b>comment</b>. Il sert à "
        "décider. Les cahiers des charges pour consulter les prestataires viennent ensuite.", S["base"])]

    el.append(Titre1("1. L'essentiel", S["h1"]))
    nb_locaux = len({x["nom"] for o in e["retenues"] for x in o["a_engager"] + o["a_valider"]})
    chiffres = [[Paragraph(f"<b>{len(e['retenues'])}</b>", S["h1"]), Paragraph(f"<b>{nb_locaux}</b>", S["h1"]),
                 Paragraph("<b>à estimer</b>", S["h2"])],
                [Paragraph("opérations proposées", S["petit"]), Paragraph("locaux et espaces concernés", S["petit"]),
                 Paragraph("coût : base de données de coûts en cours de constitution", S["petit"])]]
    el.append(_tableau(chiffres, [50 * mm, 60 * mm, 70 * mm], entete=False,
                       style=[("GRID", (0, 0), (-1, -1), 0, colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el.append(Spacer(1, 3 * mm))
    if e["moe"]:
        el.append(_encadre("<b>Une maîtrise d'œuvre est recommandée.</b> Elle conçoit l'ensemble des travaux, "
                           "vérifie leur faisabilité et suit le chantier. Les actions d'organisation peuvent "
                           "commencer tout de suite, sans l'attendre.", S, "#ffd9c7"))
    else:
        el.append(_encadre("<b>Les travaux peuvent être commandés sans maîtrise d'œuvre</b>, avec les cahiers des "
                           "charges du kit et, si la collectivité n'a pas de service technique, l'appui d'une "
                           "structure d'ingénierie du territoire.", S))
    lignes = [[Paragraph("<b>Quand</b>", S["entete"]), Paragraph("<b>Quoi</b>", S["entete"])]]
    style = []
    for h in (1, 2, 3):
        ops = [o for o in e["retenues"] if o["horizon"] == h]
        if not ops:
            continue
        lignes.append([Paragraph(f"<b>{_t(travaux.HORIZONS[h])}</b>", S["cellule"]),
                       Paragraph(_t(", ".join(court(o) for o in ops)), S["cellule"])])
        style.append(("BACKGROUND", (0, len(lignes) - 1), (0, len(lignes) - 1), colors.HexColor(COULEURS_HORIZON[h])))
    el += [Spacer(1, 3 * mm), _tableau(lignes, [50 * mm, 130 * mm], style),
           Paragraph(_t(travaux.MESSAGE_COUTS), S["petit"])]
    return el


# ------------------------------------------------------------------ 2. quoi et pourquoi
def _leviers(e, S):
    el = [PageBreak(), Titre1("2. Ce que nous proposons, et pourquoi", S["h1"]),
          Paragraph("Contre la chaleur, l'ordre compte : d'abord empêcher la chaleur d'entrer, ensuite l'évacuer la "
                    "nuit, enfin rendre la chaleur restante supportable. Les opérations sont présentées dans cet "
                    "ordre.", S["base"])]
    groupes = sorted({o["groupe"] for o in e["retenues"]},
                     key=lambda g: ORDRE_LEVIERS.index(g) if g in ORDRE_LEVIERS else 99)
    for g in groupes:
        titre, pourquoi = travaux.LEVIERS.get(g, (g, ""))
        bloc = [CondPageBreak(45 * mm), Paragraph(_t(titre), S["h2"]), Paragraph(f"<i>{_t(pourquoi)}</i>", S["base"])]
        lignes = [[Paragraph(f"<b>{h}</b>", S["entete"]) for h in ("Ce que l'on fait", "Où", "Quand", "Qui")]]
        style, vues = [], set()
        for o in [o for o in e["retenues"] if o["groupe"] == g]:
            propre = bool(travaux.CATALOGUE[o["solution"]].get("bref"))
            bref = "" if (o["fiche"] in vues and not propre) else _bref(o["fiche"], o["solution"])
            if not propre:
                vues.add(o["fiche"])
            ou = [x["nom"] for x in o["a_engager"]] + [f"{x['nom']} (à confirmer)" for x in o["a_valider"]]
            lignes.append([Paragraph(f"<b>{_t(o['action'])}</b>" + (f"<br/>{_t(bref)}" if bref else ""),
                                     S["cellule"]),
                           Paragraph(_t(", ".join(ou)), S["cellule"]),
                           Paragraph(_t(travaux.HORIZONS[o["horizon"]]), S["cellule"]),
                           Paragraph(_t(_qui_fait(o, e)), S["cellule"])])
            style.append(("BACKGROUND", (2, len(lignes) - 1), (2, len(lignes) - 1),
                          colors.HexColor(COULEURS_HORIZON[o["horizon"]])))
        bloc += [Spacer(1, 1.5 * mm), _tableau(lignes, [78 * mm, 48 * mm, 26 * mm, 28 * mm], style)]
        el += bloc
    ecartees = [o for o in e["operations"] if not o["retenue"]]
    if ecartees:
        el.append(Paragraph("Proposé par le diagnostic mais non retenu", S["h3"]))
        el += [Paragraph(f"<b>{_t(o['action'])}</b> — {_t(o['motif'] or 'sans motif')}", S["puce"], bulletText="n")
               for o in ecartees]
    return el


# ------------------------------------------------------------------ 3. local par local
def _par_local(d, e, S):
    el = [PageBreak(), Titre1("3. Local par local", S["h1"]),
          Paragraph("Pour chaque local ou espace : ce que le diagnostic a constaté, ce qui est prévu, et ce qu'il "
                    "faut vérifier avant de lancer les travaux. « À confirmer » signale une opération qui dépend "
                    "d'une donnée manquante ou d'une vérification.", S["base"]), Spacer(1, 2 * mm)]
    ordre = [x.get("L-01") or x.get("E-01") for x in (d.get("locaux") or []) + (d.get("espaces") or [])]
    par_nom = {}
    for o in e["retenues"]:
        for x in o["a_engager"] + o["a_valider"]:
            r = par_nom.setdefault(x["nom"], {"ops": [], "vig": {}})
            r["ops"].append(court(o) + (" (à confirmer)" if x in o["a_valider"] else ""))
            r["vig"].update(dict(x["vigilances"]))
    noms = sorted(par_nom, key=lambda n: ordre.index(n) if n in ordre else 999)
    lignes = [[Paragraph(f"<b>{h}</b>", S["entete"]) for h in ("Local ou espace", "Opérations prévues", "À vérifier")]]
    for n in noms:
        r = par_nom[n]
        vig = "<br/>".join(f"• {_t(t)}" for t in r["vig"].values()) or "—"
        lignes.append([Paragraph(f"<b>{_t(n)}</b>", S["cellule"]),
                       Paragraph("<br/>".join(f"• {_t(x)}" for x in r["ops"]), S["cellule"]),
                       Paragraph(vig, S["cellule"])])
    el.append(_tableau(lignes, [38 * mm, 62 * mm, 80 * mm]))
    if e["completer"]:
        el.append(Paragraph("Données à compléter", S["h3"]))
        el.append(Paragraph("Ces opérations sont « sous réserve » faute d'une information : il ne s'agit pas d'un "
                            "obstacle constaté.", S["petit"]))
        el += [Paragraph(f"<b>{_t(n)}</b> : {_t(', '.join(s))}", S["puce"], bulletText="n")
               for n, s in e["completer"].items()]
    return el


# ------------------------------------------------------------------ 4. comment
def _comment(e, S):
    el = [PageBreak(), Titre1("4. Comment nous allons le faire", S["h1"])]
    el.append(Paragraph("Avec qui", S["h2"]))
    if e["moe"]:
        el.append(Paragraph("<b>Une maîtrise d'œuvre est recommandée</b> pour les raisons suivantes :", S["base"]))
        raisons = list(e["raisons_moe"])
        if e["choix"]["moe"]["choix"] != "auto" and e["moe"] != e["moe_auto"]:
            raisons = [f"choix de l'auditeur : {e['choix']['moe']['motif']}"]
        el += [Paragraph(_t(r.split(" — ", 1)[-1]), S["puce"], bulletText="n") for r in raisons]
        el.append(Paragraph("Toutes les opérations de travaux lui sont confiées, quel que soit leur niveau, pour "
                            "qu'un seul professionnel soit responsable de leur cohérence. La collectivité garde les "
                            "actions sans travaux"
                            + (f" ({_t(', '.join(court(o) for o in e['ops_moa']))})" if e["ops_moa"] else "")
                            + ". Les opérations simples peuvent faire l'objet d'une première tranche avant l'été.",
                            S["base"]))
    else:
        el.append(Paragraph("<b>Une maîtrise d'œuvre n'est pas indispensable</b> au vu des opérations retenues. "
                            "Elle reste utile si la collectivité souhaite confier la conception et le suivi à un "
                            "professionnel.", S["base"]))
        if e["moe_auto"]:
            el.append(Paragraph(f"L'outil la recommandait ; l'auditeur ne l'a pas retenue : "
                                f"{_t(e['choix']['moe']['motif'])}.", S["base"]))
    el.append(Paragraph("Faire sans maîtrise d'œuvre expose à des risques :", S["base"]))
    el += [Paragraph(_t(r), S["puce"], bulletText="n") for r in travaux.RISQUES_SANS_MOE]
    ing = e["choix"]["accompagnement"]["ingenierie"]
    if ing in ("non", "nsp"):
        el.append(_encadre("<b>La collectivité n'a pas de service technique bâtiment"
                           + (" (ou ne sait pas)" if ing == "nsp" else "")
                           + " : nous recommandons de se faire accompagner</b> par une structure d'ingénierie du "
                           "territoire, pour préparer les consultations, choisir les prestataires et suivre les "
                           "travaux. Selon les territoires : " + _t(" ".join(travaux.ACCOMPAGNEMENT)), S, "#d6f5f5"))
    elif ing == "oui":
        el.append(Paragraph("La collectivité dispose d'un service technique qui pilotera les études et les travaux.",
                            S["base"]))
    structures = e["choix"]["accompagnement"].get("structures") or []
    if structures:
        from . import ingenierie
        el.append(Paragraph("Les structures à contacter", S["h2"]))
        el.append(Paragraph("Ces structures peuvent, au moins en théorie, accompagner la commune. Contactez-les pour "
                            "leur demander si elles peuvent vous aider pour le passage en travaux. Liste établie le "
                            + _t(e["choix"]["accompagnement"].get("date_recherche") or "—")
                            + " à partir de l'annuaire de l'administration, du répertoire SIRENE et du fichier ACTEE ; "
                            "« à vérifier » signale une structure repérée automatiquement, dont les coordonnées sont "
                            "à chercher sur son site.", S["petit"]))
        lignes = [[Paragraph(f"<b>{h}</b>", S["entete"]) for h in ("Type", "Structure", "Téléphone", "Courriel ou site")]]
        for x in structures:
            if x["type"] == "national":
                continue
            lib = ingenierie.TYPES.get(x["type"], (x["type"],))[0]
            contact = x["courriel"] or x["site"] or "—"
            lignes.append([Paragraph(_t(lib), S["cellule"]),
                           Paragraph(f"<b>{_t(x['nom'])}</b>" + ("<br/><i>à vérifier</i>" if x["a_verifier"] else "")
                                     + (f"<br/>{_t(x['adresse'])}" if x["adresse"] else ""), S["cellule"]),
                           Paragraph(_t(x["telephone"] or "—"), S["cellule"]), Paragraph(_t(contact), S["cellule"])])
        el.append(_tableau(lignes, [38 * mm, 62 * mm, 28 * mm, 52 * mm]))

    prealables = [(n, x) for n, x in e["pieces"].items() if x["categorie"] == "prealable"]
    if prealables:
        el.append(Paragraph("Les études et missions préalables", S["h2"]))
        el.append(Paragraph("Elles sont commandées par la collectivité, avant ou pendant la conception. Le kit "
                            "fournit un cahier des charges pour chacune.", S["base"]))
        lignes = [[Paragraph(f"<b>{h}</b>", S["entete"]) for h in ("Prestation", "Pourquoi", "Pour quelles opérations")]]
        pourquoi = {
            6: "l'installation de ventilation ne permet peut-être pas le mode été par simple réglage",
            7: "connaître l'état de la toiture et de son isolant avant de choisir une solution",
            10: "obligatoire avant travaux dans un bâtiment construit avant juillet 1997",
            11: "vérifier que les supports peuvent porter ou ancrer les équipements prévus",
            12: "travaux qui chargent la structure ou touchent à la sécurité incendie d'un établissement recevant "
                "du public",
            13: "obligatoire dès que plusieurs entreprises interviennent",
        }
        for n, x in prealables:
            lignes.append([Paragraph(_t(travaux.CCTP[n].split(" — ")[1]), S["cellule"]),
                           Paragraph(_t(pourquoi.get(n, "")), S["cellule"]),
                           Paragraph(_t(", ".join(court(o) for o in x["operations"])), S["cellule"])])
        el.append(_tableau(lignes, [50 * mm, 65 * mm, 65 * mm]))

    el.append(Paragraph("Le calendrier", S["h2"]))
    for h in (1, 2, 3):
        ops = [o for o in e["retenues"] if o["horizon"] == h]
        if ops:
            el.append(Paragraph(f"<b>{_t(travaux.HORIZONS[h])}</b> : {_t(', '.join(court(o) for o in ops))}.",
                                S["puce"], bulletText="n"))
    el.append(Paragraph("Rappels : travaux sous 100 000 € HT et études ou maîtrise d'œuvre sous 60 000 € HT "
                        "dispensés de procédure (décret n° 2025-1386) ; demander au moins trois devis reste la bonne "
                        "pratique. Le montant s'apprécie sur l'ensemble de l'opération.", S["petit"]))
    return el


# ------------------------------------------------------------------ 5. suite et validation
def _suite(e, S):
    el = [CondPageBreak(70 * mm), Titre1("5. Les prochaines étapes", S["h1"])]
    for t in [t for t in e["feuille_de_route"] if t["phase"] in ("Décider", "Vérifier")][:8]:
        el.append(Paragraph(f"<b>{_t(t['quoi'])}</b> — {_t(t['qui'])}, {_t(t['quand'].lower())}", S["puce"],
                            bulletText="n"))
    v = e["choix"]["validation"]
    el.append(Paragraph("Validation", S["h2"]))
    el.append(_tableau([[Paragraph("<b>Revue par l'auditeur</b>", S["cellule"]),
                         Paragraph(_t(f"{v['auditeur'] or '—'} · {v['date_revue'] or '—'}"), S["cellule"])],
                        [Paragraph("<b>Visa (chargé de mission ou économe de flux)</b>", S["cellule"]),
                         Paragraph(_t(f"{v['visa'] or '—'} · {v['date_visa'] or '—'}"), S["cellule"])]],
                       [70 * mm, 110 * mm], entete=False))
    el += [Spacer(1, 3 * mm), Paragraph(
        "Ce pré-programme est une aide à la décision établie à partir du diagnostic de confort d'été. Il ne "
        "remplace pas une étude de maîtrise d'œuvre et n'engage pas ses auteurs sur la conception ou l'exécution des "
        "travaux. La collectivité reste maître d'ouvrage. " + travaux.MESSAGE_COUTS,
        S["petit"])]
    return el


def generer_pdf(donnees: dict) -> bytes:
    S = _styles()
    res = None if travaux.externe(donnees) else moteur.calculer(donnees)
    e = travaux.etat(donnees, res)
    audit = donnees.get("audit") or {}
    titre_pied = " — ".join(t for t in (audit.get("etablissement"), audit.get("commune")) if t) or "Pré-programme"

    def pied(canvas, doc):
        canvas.saveState()
        canvas.setFont(_polices()["texte"], 7)
        canvas.setFillColor(NOIR)
        txt = f"Pré-programme d'adaptation à la chaleur — {titre_pied}" + ("" if e["valide"] else " — PROJET NON VALIDÉ")
        canvas.drawString(15 * mm, 9 * mm, txt.encode("cp1252", "replace").decode("cp1252"))
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"p. {doc.page}")
        canvas.setStrokeColor(BLEU)
        canvas.setLineWidth(1.2)
        canvas.line(15 * mm, 12 * mm, A4[0] - 15 * mm, 12 * mm)
        canvas.restoreState()

    if not e["retenues"]:
        el = _essentiel(donnees, e, S) + [Paragraph("Le diagnostic ne fait ressortir aucune opération à engager.",
                                                    S["base"])]
    else:
        el = _essentiel(donnees, e, S) + _leviers(e, S) + _par_local(donnees, e, S) + _comment(e, S) + _suite(e, S)
    return _construire(el, audit, titre_pied, "Pré-programme d'adaptation à la chaleur", pied)
