"""PDF « Plan d'action — passage en travaux » remis au maître d'ouvrage à la fin du diagnostic.

Il reprend la charte et les briques de mise en page du compte rendu (``surya.rapport``) :

1. l'essentiel en une page (verdict maîtrise d'œuvre, trois horizons, budget indicatif) ;
2. le tableau des opérations ;
3. une fiche par opération retenue (localisation, constats et vigilances par local, étapes du maître
   d'ouvrage tirées du kit, prestataire, CCTP à utiliser, coût indicatif et hypothèses) ;
4. la feuille de route ;
5. les données à compléter, les opérations écartées et la validation.

``generer_pdf(donnees)`` renvoie le PDF (bytes). Aucune dépendance à Streamlit.
"""
from __future__ import annotations

import datetime as dt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, KeepTogether, PageBreak, Paragraph, Spacer

from . import moteur, travaux
from .rapport import BLEU, NOIR, Titre1, _construire, _logo, _polices, _styles, _t, _tableau

COULEURS_NIVEAU = {"A": "#5bba50", "B": "#ffc300", "C": "#ff5400"}
COULEURS_HORIZON = {1: "#5bba50", 2: "#0dcccc", 3: "#8dc8f8"}


def _eur(v) -> str:
    return f"{v:,.0f} €".replace(",", " ")


def _fourchette(c) -> str:
    if not c:
        return "à chiffrer"
    if c["haut"] == 0:
        return "sans coût"
    if c["bas"] == c["haut"]:
        return f"env. {_eur(c['bas'])} HT"
    return f"{_eur(c['bas'])} à {_eur(c['haut'])} HT"


def _pastille(texte, couleur, S):
    t = _tableau([[Paragraph(f"<b>{_t(texte)}</b>", S["statut"])]], [9 * mm], entete=False,
                 style=[("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(couleur))])
    return t


def _essentiel(d, e, S):
    audit = d.get("audit") or {}
    el = [_logo(), Spacer(1, 4 * mm), Paragraph("Plan canicule des écoles", S["type_doc"]),
          Paragraph("Plan d'action — passage en travaux", S["titre"]), Spacer(1, 2 * mm)]
    ident = " · ".join(_t(audit[k]) for k in ("etablissement", "commune") if audit.get(k)) or "Établissement"
    el.append(Paragraph(f"<b>{ident}</b> · diagnostic du {_t(audit.get('date_visite') or 'n.r.')} · édité le "
                        f"{dt.date.today().strftime('%d/%m/%Y')}", S["base"]))
    de = travaux.externe(d)
    if de:
        el.append(Paragraph("Établi à partir du diagnostic « " + _t(de.get("source") or "diagnostic existant") + " »"
                            + (f" du {_t(de['date'])}" if de.get("date") else "")
                            + ", réalisé hors de la méthode SURYA.", S["petit"]))
    statut = ("Version validée par l'auditeur et visée par "
              f"{_t(e['choix']['validation']['visa'])}" if e["valide"] else
              "PROJET — à valider par l'auditeur et à viser par le chargé de mission ou l'économe de flux avant remise")
    el += [Spacer(1, 2 * mm), _tableau([[Paragraph(f"<b>{statut}</b>", S["base"])]], [180 * mm], entete=False,
                                       style=[("BACKGROUND", (0, 0), (-1, -1),
                                               colors.HexColor("#e0e6de" if e["valide"] else "#ffc300"))])]
    el.append(Titre1("1. L'essentiel", S["h1"]))
    if e["moe"]:
        el.append(Paragraph("<b>Une maîtrise d'œuvre est recommandée pour cette école.</b> Toutes les opérations "
                            "de travaux lui sont confiées ; les opérations simples peuvent faire l'objet d'une "
                            "première tranche avant l'été, et les actions sans travaux commencent tout de suite.",
                            S["base"]))
    else:
        el.append(Paragraph("<b>Une maîtrise d'œuvre n'est pas nécessaire au vu des opérations retenues.</b> Les "
                            "travaux peuvent être commandés directement, avec l'appui d'un relais (économe de "
                            "flux, CAUE, agence technique).", S["base"]))
    raisons = e["raisons_moe"] if e["moe"] else []
    if e["choix"]["moe"]["choix"] != "auto" and e["moe"] != e["moe_auto"]:
        raisons = [f"Verdict modifié par l'auditeur : {e['choix']['moe']['motif']}"] + raisons
    el += [Paragraph(_t(r), S["puce"], bulletText="n") for r in raisons]
    lignes = [[Paragraph("<b>Horizon</b>", S["entete"]), Paragraph("<b>Opérations retenues</b>", S["entete"])]]
    style = []
    for h in (1, 2, 3):
        ops = [o for o in e["retenues"] if o["horizon"] == h]
        if not ops:
            continue
        lignes.append([Paragraph(f"<b>{h}. {_t(travaux.HORIZONS[h])}</b>", S["cellule"]),
                       Paragraph("<br/>".join(f"[{o['niveau']}] {_t(o['action'])}" for o in ops), S["cellule"])])
        style.append(("BACKGROUND", (0, len(lignes) - 1), (0, len(lignes) - 1), colors.HexColor(COULEURS_HORIZON[h])))
    el += [Spacer(1, 3 * mm), _tableau(lignes, [50 * mm, 130 * mm], style)]
    el.append(Paragraph("Niveaux : [A] régie ou devis simples ; [B] consultation avec le CCTP type du kit ; "
                        "[C] étude ou maîtrise d'œuvre d'abord (classement proposé par ACTEE). "
                        + _t(travaux.MESSAGE_COUTS), S["petit"]))
    premieres = [t for t in e["feuille_de_route"] if t["phase"] in ("Décider", "Vérifier")][:4]
    if premieres:
        el.append(Paragraph("À faire en premier", S["h2"]))
        el += [Paragraph(f"<b>{_t(t['quoi'])}</b> — {_t(t['qui'])}, {_t(t['quand'].lower())}", S["puce"],
                         bulletText="n") for t in premieres]
    return el


def _tableau_operations(e, S):
    el = [PageBreak(), Titre1("2. Les opérations", S["h1"]),
          Paragraph("Une opération regroupe une solution dans tous les locaux ou espaces où le diagnostic la "
                    "retient. Le détail de chacune suit.", S["base"]), Spacer(1, 2 * mm)]
    lignes = [[Paragraph(f"<b>{h}</b>", S["entete"]) for h in
               ("Hor.", "Niv.", "Opération", "Où", "Prestataire", "Pièce du kit")]]
    style = []
    for o in e["retenues"]:
        ou = [x["nom"] for x in o["a_engager"]] + [f"{x['nom']} (à valider)" for x in o["a_valider"]]
        pieces = ", ".join(travaux.pieces_operation(o, e))
        lignes.append([Paragraph(str(o["horizon"]), S["statut"]), Paragraph(o["niveau"], S["statut"]),
                       Paragraph(_t(o["action"]), S["cellule"]), Paragraph(_t(", ".join(ou)), S["cellule"]),
                       Paragraph(_t(o["prestataire"]), S["cellule"]),
                       Paragraph(_t(f"Fiche {o['fiche']}" + (f" ; {pieces}" if pieces else "")), S["cellule"])])
        i = len(lignes) - 1
        style += [("BACKGROUND", (0, i), (0, i), colors.HexColor(COULEURS_HORIZON[o["horizon"]])),
                  ("BACKGROUND", (1, i), (1, i), colors.HexColor(COULEURS_NIVEAU[o["niveau"]]))]
    el.append(_tableau(lignes, [9 * mm, 9 * mm, 45 * mm, 50 * mm, 35 * mm, 32 * mm], style))
    return el


def _fiche(o, e, S):
    f = travaux.FICHES[o["fiche"]]
    el = [CondPageBreak(70 * mm), Paragraph(f"{_t(o['action'])}", S["h2"]),
          Paragraph(f"<b>Niveau {o['niveau']}</b> — {_t(travaux.NIVEAUX[o['niveau']])} · <b>Horizon {o['horizon']}</b> — "
                    f"{_t(travaux.HORIZONS[o['horizon']])}",
                    S["base"])]
    if o["raisons_niveau"]:
        el.append(Paragraph("Pourquoi ce niveau : " + _t(" ; ".join(o["raisons_niveau"])), S["petit"]))
    el.append(Paragraph(_t(travaux.CATALOGUE[o["solution"]].get("bref") or f["en_bref"]), S["petit"]))
    lignes = [[Paragraph("<b>Local ou espace</b>", S["entete"]), Paragraph("<b>Constat du diagnostic</b>", S["entete"]),
               Paragraph("<b>Points de vigilance propres au site</b>", S["entete"])]]
    for x in o["a_engager"] + o["a_valider"]:
        constat = f"<b>{_t(x['statut'])}</b>" + (f" — {_t(x['libelle_regle'])}" if x["libelle_regle"] else "")
        vig = "<br/>".join(f"<b>{_t(a)}</b> : {_t(t)}" for a, t in x["vigilances"]) or "—"
        lignes.append([Paragraph(_t(x["nom"]) + ("<br/><i>à valider</i>" if x in o["a_valider"] else ""), S["cellule"]),
                       Paragraph(constat, S["cellule"]), Paragraph(vig, S["cellule"])])
    el += [Spacer(1, 1.5 * mm), _tableau(lignes, [40 * mm, 70 * mm, 70 * mm])]
    el.append(Paragraph("Ce que fait le maître d'ouvrage, étape par étape", S["h3"]))
    if travaux.sans_fiche(o):
        el.append(Paragraph(_t(travaux.sans_fiche(o)), S["base"]))
    else:
        el += [Paragraph(f"<b>{i}. {_t(t)}</b> — {_t(txt)}", S["base"]) for i, (t, txt) in enumerate(f["etapes"], 1)]
    if o.get("commentaire"):
        el.append(Paragraph("<b>Note du diagnostic</b> : " + _t(o["commentaire"]), S["petit"]))
    pieces = travaux.pieces_operation(o, e)
    el.append(Paragraph(f"<b>Prestataire</b> : {_t('maîtrise d’œuvre, puis entreprises' if o in e['ops_moe'] else o['prestataire'])}. <b>Pièces du kit</b> : fiche {o['fiche']} "
                        f"« {_t(f['titre'])} »" + (" ; " + _t(" ; ".join(pieces)) if pieces else "") + ".", S["base"]))
    if f.get("vigilances") and not travaux.sans_fiche(o):
        el.append(Paragraph("<b>Vigilances générales</b> : " + _t(" ".join(f["vigilances"])), S["petit"]))
    if o["quantite"] is not None and o["unite"] != "forfait":
        q = f"{o['quantite']:g}".replace(".", ",")
        el.append(Paragraph(f"<b>Quantité estimée</b> : {q} {_t(o['unite'])} ("
                            + _t(" ; ".join(o["hypotheses"])) + ").", S["petit"]))
    if o.get("couverts") and o["solution"] == "Films solaires":
        el.append(Paragraph("Locaux qui recevront aussi une protection extérieure : " + _t(", ".join(o["couverts"]))
                            + ". Le film n'y est utile qu'en provisoire.", S["petit"]))
    return el


def _fiches(e, S):
    el = [PageBreak(), Titre1("3. Fiches opérations", S["h1"])]
    for o in e["retenues"]:
        el += _fiche(o, e, S)
    return el


def _feuille(e, S):
    el = [PageBreak(), Titre1("4. Feuille de route du maître d'ouvrage", S["h1"])]
    lignes = [[Paragraph(f"<b>{h}</b>", S["entete"]) for h in ("Phase", "Ce qu'il faut faire", "Qui", "Quand", "Ce qui en sort")]]
    for t in e["feuille_de_route"]:
        lignes.append([Paragraph(_t(t["phase"]), S["cellule"]), Paragraph(_t(t["quoi"]), S["cellule"]),
                       Paragraph(_t(t["qui"]), S["cellule"]), Paragraph(_t(t["quand"]), S["cellule"]),
                       Paragraph(_t(t["sortie"]), S["cellule"])])
    el.append(_tableau(lignes, [28 * mm, 74 * mm, 30 * mm, 26 * mm, 22 * mm]))
    el.append(Paragraph("Rappels : travaux sous 100 000 € HT et études ou maîtrise d'œuvre sous 60 000 € HT "
                        "dispensés de procédure (décret n° 2025-1386), mais demander au moins trois devis reste la "
                        "bonne pratique ; le montant s'apprécie sur l'ensemble de l'opération.", S["petit"]))
    return el


def _fin(e, S):
    el = [CondPageBreak(60 * mm), Titre1("5. Données à compléter et validation", S["h1"])]
    if e["completer"]:
        el.append(Paragraph("Données manquantes : ces statuts « sous réserve » ne traduisent pas un obstacle "
                            "constaté mais une information à recueillir.", S["base"]))
        el += [Paragraph(f"<b>{_t(n)}</b> : {_t(', '.join(s))}", S["puce"], bulletText="n") for n, s in e["completer"].items()]
    ecartees = [o for o in e["operations"] if not o["retenue"]]
    if ecartees:
        el.append(Paragraph("Opérations proposées par l'outil et non retenues", S["h2"]))
        el += [Paragraph(f"<b>{_t(o['action'])}</b> — {_t(o['motif'] or 'sans motif')}", S["puce"], bulletText="n")
               for o in ecartees]
    v = e["choix"]["validation"]
    el.append(Paragraph("Validation", S["h2"]))
    el.append(_tableau([[Paragraph("<b>Revue par l'auditeur</b>", S["cellule"]),
                         Paragraph(_t(f"{v['auditeur'] or '—'} · {v['date_revue'] or '—'}"), S["cellule"])],
                        [Paragraph("<b>Visa (chargé de mission ou économe de flux)</b>", S["cellule"]),
                         Paragraph(_t(f"{v['visa'] or '—'} · {v['date_visa'] or '—'}"), S["cellule"])]],
                       [70 * mm, 110 * mm], entete=False))
    if e["anomalies"]:
        el += [Paragraph(f"<b>À régler avant validation</b> : {_t(a)}", S["puce"], bulletText="n") for a in e["anomalies"]]
    el += [Spacer(1, 3 * mm), Paragraph(
        "Ce plan d'action est une aide à la décision établie à partir du diagnostic de confort d'été. Il ne "
        "constitue pas une mission de maîtrise d'œuvre et n'engage pas ses auteurs sur la conception ou l'exécution "
        "des travaux. La collectivité reste maître d'ouvrage. " + travaux.MESSAGE_COUTS,
        S["petit"])]
    return el


def generer_pdf(donnees: dict) -> bytes:
    S = _styles()
    res = None if travaux.externe(donnees) else moteur.calculer(donnees)
    e = travaux.etat(donnees, res)
    audit = donnees.get("audit") or {}
    titre_pied = " — ".join(t for t in (audit.get("etablissement"), audit.get("commune")) if t) or "Plan d'action"

    def pied(canvas, doc):
        canvas.saveState()
        canvas.setFont(_polices()["texte"], 7)
        canvas.setFillColor(NOIR)
        txt = f"Plan d'action — passage en travaux — {titre_pied}" + ("" if e["valide"] else " — PROJET NON VALIDÉ")
        canvas.drawString(15 * mm, 9 * mm, txt.encode("cp1252", "replace").decode("cp1252"))
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"p. {doc.page}")
        canvas.setStrokeColor(BLEU)
        canvas.setLineWidth(1.2)
        canvas.line(15 * mm, 12 * mm, A4[0] - 15 * mm, 12 * mm)
        canvas.restoreState()

    if not e["operations"]:
        el = _essentiel(donnees, e, S) + [Paragraph("Le diagnostic ne fait ressortir aucune opération à engager.",
                                                    S["base"])]
    else:
        el = _essentiel(donnees, e, S) + _tableau_operations(e, S) + _fiches(e, S) + _feuille(e, S) + _fin(e, S)
    return _construire(el, audit, titre_pied, "Plan d'action — passage en travaux", pied)
