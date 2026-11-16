"""Interface Streamlit de la méthode SURYA — maquette (preuve de concept).

Lancement : streamlit run app.py

Les réponses vivent dans ``st.session_state.donnees`` (aucune base de données) ; le calcul
est délégué à ``surya.moteur`` qui ne dépend pas de l'interface.
"""
from __future__ import annotations

import csv
import html
import io
import json
import uuid
from pathlib import Path

import streamlit as st

from surya import moteur
from surya.import_excel import lire_classeur
from surya.moteur import NB_MURS_MAX, ORIENTATIONS, PARAMETRES_DEFAUT, REFERENTIEL, REGLES
from surya.questions import (QUESTIONS_FACADE, QUESTIONS_MUR, SECTIONS_BATIMENT, SECTIONS_ESPACE,
                             SECTIONS_LOCAL, avancement, visible)

RACINE = Path(__file__).parent
PAGES = ["Accueil", "Bâtiment", "Locaux", "Espaces extérieurs", "Résultats", "Paramètres"]

# statut -> (fond, texte)
COULEURS = {
    moteur.RECOMMANDE: ("#d3f0db", "#0f5a26"),
    moteur.EN_PLACE: ("#d6e6fb", "#0e4a8a"),
    moteur.A_OPTIMISER: ("#ffe2c2", "#8a4300"),
    moteur.SOUS_RESERVE: ("#fff2b3", "#6b5300"),
    moteur.NON_RECOMMANDE: ("#f9d2d0", "#8c1d18"),
    moteur.NON_CONCERNE: ("#e6e6e6", "#4d4d4d"),
}
# Solutions dont le statut dépend d'abord d'un « cas » : question à renseigner si le cas est indéterminé
QUESTIONS_DU_CAS = {
    "Mise en place de brasseurs d'air plafonniers": "BA-05",
    "Toiture": "L-09, puis B-18, B-21 et B-22 (bâtiment)",
    "Ombrage autoportant ou végétal de la cour": "E-02",
}

st.set_page_config(page_title="Méthode SURYA — faisabilité d'actions d'adaptation", page_icon="🌡️", layout="wide")


# ------------------------------------------------------------------ état
def donnees_vides() -> dict:
    return {"batiment": {}, "facades": {}, "locaux": [], "espaces": [], "parametres": {}}


def charger(d: dict):
    """Remplace toutes les données (exemple, import) et réinitialise les champs affichés."""
    base = donnees_vides()
    base.update({k: v for k, v in d.items() if k in base})
    for x in base["locaux"] + base["espaces"]:
        x.setdefault("_id", uuid.uuid4().hex[:8])
    st.session_state.donnees = base
    st.session_state.generation = st.session_state.get("generation", 0) + 1
    st.session_state.i_local = 0
    st.session_state.i_espace = 0


if "donnees" not in st.session_state:
    charger(donnees_vides())
D = st.session_state.donnees


def cle(*parts) -> str:
    return ":".join(str(p) for p in (st.session_state.generation, *parts))


# ------------------------------------------------------------------ champs de saisie
def _etiquette(q) -> str:
    unite = f" ({q['unite']})" if q.get("unite") else ""
    code = 'MEX-01' if q['code'] == 'orientation' else q['code'].removesuffix('b')
    return f"{q['libelle']}{unite} :gray[· {code}]"


def champ(q: dict, d: dict, prefixe: str):
    """Affiche le champ d'une question et range la réponse dans ``d``."""
    code, typ, k = q["code"], q["type"], cle(prefixe, q["code"])
    aide = "Question informative : elle n'entre pas dans le calcul des statuts." if q.get("info") else None
    actuel = d.get(code)
    if typ == "choix":
        opts = q["options"]
        if actuel not in opts:
            actuel = None
        if sum(len(o) for o in opts) <= 26:
            v = st.segmented_control(_etiquette(q), opts, default=actuel, key=k, help=aide)
        else:
            v = st.selectbox(_etiquette(q), opts, index=opts.index(actuel) if actuel else None,
                             placeholder="Choisir…", key=k, help=aide)
    elif typ == "multi":
        st.markdown(f":small[{_etiquette(q)} :gray[— plusieurs réponses possibles]]", help=aide)
        v = [o for n, o in enumerate(q["options"])
             if st.checkbox(o, value=o in (actuel or []), key=f"{k}:{n}")] or None
    elif typ == "nombre":
        v = _champ_nombre(q, d, k, aide)
    else:
        v = st.text_input(_etiquette(q), value=actuel or "", key=k, help=aide).strip() or None
    if v is None:
        d.pop(code, None)
    else:
        d[code] = v


def _champ_nombre(q, d, k, aide):
    actuel, unite = d.get(q["code"]), q.get("unite", "")
    if q["code"] == "B-24":  # nombre en cm ou « inconnu »
        inconnu = st.checkbox("Épaisseur d'isolant inconnue (non visible) :gray[· B-24]", value=actuel == "inconnu",
                              key=k + ":inconnu")
        if inconnu:
            return "inconnu"
    if not isinstance(actuel, (int, float)) or isinstance(actuel, bool):
        actuel = None
    if unite in ("", "pers.", "0 à 4"):
        return st.number_input(_etiquette(q), min_value=0, max_value=4 if unite == "0 à 4" else None, step=1,
                               value=None if actuel is None else int(actuel), placeholder="—", key=k, help=aide)
    pas, fmt = (0.1, "%.2f") if unite == "m" else (1.0, "%.1f")
    return st.number_input(_etiquette(q), min_value=0.0, step=pas, format=fmt,
                           value=None if actuel is None else float(actuel), placeholder="—", key=k, help=aide)


def section(s: dict, d: dict, etats, cb: dict, prefixe: str):
    """Affiche les questions visibles d'une section, sur deux colonnes.

    ``etats`` est une fonction : les états sont recalculés avant chaque question pour qu'une
    question conditionnelle apparaisse dès que la réponse dont elle dépend vient d'être saisie.
    """
    cols = st.columns(2, gap="large")
    i = 0
    for q in s["questions"]:
        if visible(q["code"], etats(), d, cb):
            with cols[i % 2]:
                champ(q, d, prefixe)
            i += 1


def pastille(statut: str) -> str:
    if not statut:
        return "<span style='color:#999'>—</span>"
    fond, texte = COULEURS.get(statut, ("#eee", "#333"))
    return (f"<span style='background:{fond};color:{texte};padding:2px 10px;border-radius:12px;"
            f"font-size:0.85em;font-weight:600;white-space:nowrap'>{html.escape(statut)}</span>")


# ------------------------------------------------------------------ barre latérale
with st.sidebar:
    st.title("🌡️ Méthode SURYA")
    st.caption("Audit de faisabilité d'actions d'adaptation aux fortes chaleurs — maquette")
    page = st.radio("Étapes", PAGES, key="page", label_visibility="collapsed")
    st.divider()
    st.caption(f"{len(D['locaux'])} local(aux) · {len(D['espaces'])} espace(s) extérieur(s)")
    with st.expander("Données"):
        if st.button("Charger l'exemple de l'Excel", width="stretch"):
            charger(json.loads((RACINE / "surya" / "exemple.json").read_text(encoding="utf-8")))
            st.rerun()
        st.download_button("Exporter la saisie (JSON)", json.dumps(D, ensure_ascii=False, indent=1),
                           file_name="saisie_surya.json", mime="application/json", width="stretch")
        fichier = st.file_uploader("Importer une saisie (JSON) ou un Excel de la méthode (.xlsx)",
                                   type=["json", "xlsx"], key=cle("import"))
        if fichier is not None and st.button("Importer ce fichier", type="primary", width="stretch"):
            try:
                charger(json.load(fichier) if fichier.name.endswith(".json") else lire_classeur(fichier))
                st.rerun()
            except Exception as e:  # fichier illisible ou d'un autre format
                st.error(f"Import impossible : {e}")
        if st.button("Tout effacer", width="stretch"):
            charger(donnees_vides())
            st.rerun()
    st.caption("Maquette : les données ne sont pas enregistrées. Exportez la saisie pour la conserver.")

CB = moteur.etats_batiment(D["batiment"], D["facades"])


# ------------------------------------------------------------------ pages
def page_accueil():
    st.title("Audit de faisabilité d'actions d'adaptation")
    st.markdown(
        "Cet outil reprend la logique de l'Excel *« Outil d'aide au test de la méthode d'audit de faisabilité "
        "d'actions d'adaptation »* : à partir des relevés du carnet de visite, il indique pour chaque local et "
        "chaque espace extérieur le **statut de faisabilité** de chaque solution de confort d'été.")
    c1, c2, c3 = st.columns(3)
    c1.info("**1. Bâtiment**\n\nDonnées générales, ventilation mécanique, toiture et combles, façades.")
    c2.info("**2. Locaux et espaces extérieurs**\n\nUne fiche par local visité et par espace extérieur.")
    c3.info("**3. Résultats**\n\nStatut de chaque solution, règle retenue, données manquantes et alertes.")
    st.markdown("Seules les questions utiles sont affichées : certaines n'apparaissent qu'en fonction des réponses "
                "précédentes. Une réponse laissée vide est traitée comme une **donnée manquante** : la solution "
                "concernée passe alors « Sous réserve ».")
    st.subheader("Statuts possibles")
    st.markdown(" ".join(pastille(s) for s in COULEURS), unsafe_allow_html=True)
    st.subheader("Avancement de la saisie")
    fait, total = avancement(SECTIONS_BATIMENT, CB, D["batiment"], CB)
    a, b, c = st.columns(3)
    a.metric("Bâtiment", f"{fait} / {total} questions")
    b.metric("Locaux", len(D["locaux"]))
    c.metric("Espaces extérieurs", len(D["espaces"]))
    if not D["locaux"] and not D["batiment"]:
        st.caption("Pour découvrir l'outil, chargez l'exemple depuis le menu « Données » de la barre latérale.")
    st.divider()
    st.caption(f"{REFERENTIEL['version']}. © 2026 ACTEE et SURYA Ingénierie — contenu de la méthode diffusé sous "
               "licence [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.fr).")


def page_batiment():
    st.title("Bâtiment")
    b = D["batiment"]
    for s in SECTIONS_BATIMENT:
        with st.container(border=True):
            st.subheader(s["titre"])
            section(s, b, lambda: moteur.etats_batiment(b, D["facades"]), CB, "bat")
    with st.container(border=True):
        st.subheader("Façades")
        st.caption("Cochez les façades qui portent des baies visitées ou bordent un espace extérieur, puis décrivez-les. "
                   "Les règles des locaux et des espaces utilisent la façade de même orientation.")
        f01, autres = QUESTIONS_FACADE[0], QUESTIONS_FACADE[1:]
        for o in ORIENTATIONS:
            f = D["facades"].setdefault(o, {})
            cols = st.columns([1.1] + [2] * len(autres))
            decrite = cols[0].checkbox(f"Façade **{o}**", value=bool(f.get("F-01")), key=cle("fac", o, "F-01"), help=f01["libelle"])
            if decrite:
                f["F-01"] = True
                for col, q in zip(cols[1:], autres):
                    with col:
                        champ({**q, "type": "choix"}, f, f"fac:{o}")
            else:
                f.pop("F-01", None)


def _liste_entites(cle_liste: str, cle_index: str, code_nom: str, singulier: str, defaut: str):
    """Sélecteur + boutons ajouter / dupliquer / supprimer. Renvoie l'entité sélectionnée ou None."""
    liste = D[cle_liste]
    c1, c2, c3, c4 = st.columns([4, 1.3, 1.3, 1.3], vertical_alignment="bottom")
    if c2.button(f"➕ Ajouter", key=cle(cle_liste, "add"), width="stretch"):
        liste.append({"_id": uuid.uuid4().hex[:8]})
        st.session_state[cle_index] = len(liste) - 1
        st.rerun()
    if not liste:
        st.info(f"Aucun {singulier} pour l'instant : cliquez sur « Ajouter ».")
        return None
    i = min(st.session_state.get(cle_index, 0), len(liste) - 1)
    noms = [x.get(code_nom) or f"{defaut} {n + 1}" for n, x in enumerate(liste)]
    i = c1.selectbox(f"{defaut} affiché", range(len(liste)), index=i, format_func=lambda n: noms[n],
                     key=cle(cle_liste, "sel", len(liste), i))
    st.session_state[cle_index] = i
    if c3.button("⧉ Dupliquer", key=cle(cle_liste, "dup"), width="stretch"):
        copie = json.loads(json.dumps(liste[i]))
        copie["_id"] = uuid.uuid4().hex[:8]
        copie[code_nom] = f"{noms[i]} (copie)"
        liste.insert(i + 1, copie)
        st.session_state[cle_index] = i + 1
        st.rerun()
    if c4.button("🗑 Supprimer", key=cle(cle_liste, "del"), width="stretch"):
        liste.pop(i)
        st.session_state[cle_index] = max(0, i - 1)
        st.rerun()
    return liste[i]


def _apercu(solutions):
    st.markdown("**Statuts (calcul en direct)**")
    lignes = "".join(f"<div style='margin:0 0 9px 0;font-size:0.88em'>{html.escape(s['solution'])}<br>"
                     f"{pastille(s['statut'])}</div>" for s in solutions)
    st.markdown(lignes, unsafe_allow_html=True)
    st.caption("Détail des règles dans la page Résultats.")


def _murs(l: dict, pid: str):
    """Baies en façade : jusqu'à 4 murs extérieurs, un par orientation."""
    aucune = st.checkbox("Aucune baie en façade :gray[· MEX-01]", value=bool(l.get("aucune_baie")), key=cle(pid, "aucune"))
    if aucune:
        l["aucune_baie"] = True
        return
    l.pop("aucune_baie", None)
    murs = l.setdefault("murs", [])
    if not murs:
        murs.append({})
    q_baies = next(q for q in QUESTIONS_MUR if q["type"] == "baies")
    for i, m in enumerate(murs):
        with st.container(border=True):
            st.markdown(f"**Mur extérieur {i + 1}**")
            cols = st.columns(2, gap="large")
            for j, q in enumerate(q for q in QUESTIONS_MUR if q["type"] != "baies"):
                if q["code"] == "MEX-05" and m.get("MEX-04") not in ("Nu intérieur", "En tunnel"):
                    continue
                with cols[j % 2]:
                    champ(q, m, f"{pid}:mur{i}")
            ori = m.get("orientation")
            if ori and not (D["facades"].get(ori) or {}).get("F-01"):
                st.warning(f"La façade {ori} n'est pas décrite dans la page Bâtiment : les règles qui en dépendent "
                           "(alignement, accès, obstacles, désordres) resteront indéterminées.", icon="⚠️")
            anciens = m.get("baies") or {}
            types = st.multiselect("Types de baie présents sur ce mur :gray[· MEX-08]", q_baies["options"],
                                   default=[t for t in q_baies["options"] if t in anciens],
                                   placeholder="Choisir un ou plusieurs types…", key=cle(pid, f"mur{i}", "types"))
            baies = {}
            if types:
                colsn = st.columns(4)
                for n, t in enumerate(t for t in q_baies["options"] if t in types):
                    prec = anciens.get(t)
                    nb = colsn[n % 4].number_input(f"Nombre — {t}", min_value=1, step=1, placeholder="non compté",
                                                   value=int(prec) if isinstance(prec, (int, float)) else None,
                                                   key=cle(pid, f"mur{i}", "nb", t))
                    baies[t] = nb if nb is not None else "x"
            if baies:
                m["baies"] = baies
            else:
                m.pop("baies", None)
    c1, c2, _ = st.columns([1.5, 1.8, 4])
    if len(murs) < NB_MURS_MAX and c1.button("➕ Ajouter un mur", key=cle(pid, "addmur")):
        murs.append({})
        st.rerun()
    if len(murs) > 1 and c2.button("🗑 Supprimer le dernier mur", key=cle(pid, "delmur")):
        murs.pop()
        st.rerun()


def page_locaux():
    st.title("Locaux")
    l = _liste_entites("locaux", "i_local", "L-01", "local", "Local")
    if l is None:
        return
    pid, nom = f"loc:{l['_id']}", l.get("L-01")
    gauche, droite = st.columns([2.6, 1], gap="large")
    with gauche:
        titres = [s["titre"] for s in SECTIONS_LOCAL]
        titres.insert(2, "Baies en façade")
        onglets = st.tabs(titres)
        sections = iter(SECTIONS_LOCAL)
        for titre, onglet in zip(titres, onglets):
            with onglet:
                if titre == "Baies en façade":
                    _murs(l, pid)
                else:
                    section(next(sections), l, lambda: moteur.etats_local(l, CB), CB, pid)
    with droite:
        c = moteur.etats_local(l, CB)
        fait, total = avancement(SECTIONS_LOCAL, c, l, CB)
        st.progress(fait / total if total else 0, text=f"{fait} / {total} questions renseignées (hors murs)")
        r = moteur.regles_local(l, c, CB, D["batiment"], {**PARAMETRES_DEFAUT, **D["parametres"]})
        _apercu(r["solutions"])
    if l.get("L-01") != nom:  # le nom vient de changer : met à jour le sélecteur
        st.rerun()


def page_espaces():
    st.title("Espaces extérieurs")
    e = _liste_entites("espaces", "i_espace", "E-01", "espace", "Espace")
    if e is None:
        return
    pid, nom = f"esp:{e['_id']}", e.get("E-01")
    gauche, droite = st.columns([2.6, 1], gap="large")
    with gauche:
        onglets = st.tabs([s["titre"] for s in SECTIONS_ESPACE])
        for s, onglet in zip(SECTIONS_ESPACE, onglets):
            with onglet:
                section(s, e, lambda: moteur.etats_espace(e), CB, pid)
    with droite:
        c = moteur.etats_espace(e)
        fait, total = avancement(SECTIONS_ESPACE, c, e, CB)
        st.progress(fait / total if total else 0, text=f"{fait} / {total} questions renseignées")
        res = moteur.calculer(D)["espaces"][D["espaces"].index(e)]
        _apercu(res["solutions"])
    if e.get("E-01") != nom:
        st.rerun()


def _tableau(entites, defaut):
    """Tableau HTML solutions x entités."""
    noms = [html.escape(x["nom"] or f"{defaut} {i + 1}") for i, x in enumerate(entites)]
    th = "".join(f"<th style='text-align:center;padding:6px 10px'>{n}</th>" for n in noms)
    lignes, groupe_prec = "", None
    for j, s in enumerate(entites[0]["solutions"]):
        if s["groupe"] != groupe_prec:
            lignes += (f"<tr><td colspan='{len(noms) + 1}' style='padding:10px 6px 4px 0;font-weight:700;"
                       f"border-bottom:1px solid #8884'>{html.escape(s['groupe'])}</td></tr>")
            groupe_prec = s["groupe"]
        cellules = ""
        for x in entites:
            sx = x["solutions"][j]
            marque = " <span title='Donnée manquante'>❓</span>" if _manquante(x, sx) else ""
            alerte = " <span title='Alerte(s)'>⚠️</span>" if sx["alertes"] else ""
            cellules += f"<td style='text-align:center;padding:5px 10px'>{pastille(sx['statut'])}{marque}{alerte}</td>"
        lignes += f"<tr><td style='padding:5px 16px 5px 12px'>{html.escape(s['solution'])}</td>{cellules}</tr>"
    st.markdown(f"<div style='overflow-x:auto'><table style='border-collapse:collapse'>"
                f"<tr><th></th>{th}</tr>{lignes}</table></div>", unsafe_allow_html=True)
    st.caption("❓ statut « Sous réserve » dû à une donnée manquante · ⚠️ alerte associée")


def _manquante(x, s) -> bool:
    if s["statut"] != moteur.SOUS_RESERVE:
        return False
    return not s["blocs"] or any(x["blocs"][b]["manquante"] for b in s["blocs"])


def _detail(x, s):
    """Détail d'une solution : règle retenue, données manquantes, alertes, toutes les règles du bloc."""
    st.markdown(pastille(s["statut"]), unsafe_allow_html=True)
    if not s["blocs"]:
        if s["statut"] == moteur.NON_CONCERNE:
            st.write("La solution ne concerne pas cet espace (ce n'est pas une cour de récréation).")
        else:
            st.info(f"Cas non déterminé faute de données. À renseigner : {QUESTIONS_DU_CAS.get(s['solution'], '')}.", icon="❓")
    for b in s["blocs"]:
        bl = x["blocs"][b]
        code = bl["regle"]
        if code is None:
            st.info("Aucune règle n'a pu être vérifiée avec les données disponibles.", icon="❓")
        else:
            r = REGLES[code]
            st.markdown(f"**Règle retenue — {code}** : {r['regle']}")
            st.caption(f"Condition : {r['condition']}")
            if bl["manquante"]:
                st.info(f"Donnée manquante : la règle {code} n'a pas pu être tranchée. "
                        f"Questions à compléter : {r['questions'] or '—'}.", icon="❓")
    for code in s["alertes"]:
        st.warning(f"**{code}** — {REGLES[code]['regle']}", icon="⚠️")
    for b in s["blocs"]:
        with st.popover(f"Toutes les règles du bloc {b}"):
            symbole = {1: "✅ vraie", 0: "— fausse", 0.5: "❓ indéterminée"}
            st.dataframe([{"Règle": c, "Statut": REGLES[c]["statut"], "Évaluation": symbole[v], "Libellé": REGLES[c]["regle"]}
                          for c, v in x["blocs"][b]["valeurs"].items()], hide_index=True, width=900)


def _export_csv(res) -> str:
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["Type", "Nom", "Groupe", "Solution", "Statut", "Règle retenue", "Donnée manquante", "Alertes"])
    for typ, cle_, defaut in (("Local", "locaux", "Local"), ("Espace extérieur", "espaces", "Espace")):
        for i, x in enumerate(res[cle_]):
            for s in x["solutions"]:
                w.writerow([typ, x["nom"] or f"{defaut} {i + 1}", s["groupe"], s["solution"], s["statut"],
                            ", ".join(x["blocs"][b]["regle"] or "(aucune)" for b in s["blocs"]),
                            "oui" if _manquante(x, s) else "non", ", ".join(s["alertes"])])
    return out.getvalue()


def page_resultats():
    st.title("Résultats — statuts de faisabilité")
    res = moteur.calculer(D)
    if not res["locaux"] and not res["espaces"]:
        st.info("Ajoutez au moins un local ou un espace extérieur pour obtenir des résultats.")
        return
    st.markdown(" ".join(pastille(s) for s in COULEURS), unsafe_allow_html=True)
    st.download_button("Télécharger les résultats (CSV)", _export_csv(res).encode("utf-8-sig"),
                       file_name="resultats_surya.csv", mime="text/csv")
    for titre, cle_, defaut in (("Locaux", "locaux", "Local"), ("Espaces extérieurs", "espaces", "Espace")):
        entites = res[cle_]
        if not entites:
            continue
        st.header(titre)
        _tableau(entites, defaut)
        st.subheader(f"Détail — {titre.lower()}")
        noms = [x["nom"] or f"{defaut} {i + 1}" for i, x in enumerate(entites)]
        i = st.selectbox(f"{defaut} à détailler", range(len(entites)), format_func=lambda n: noms[n], key=cle("res", cle_))
        x = entites[i]
        if x.get("EX-AL") == 1:
            st.warning(f"**EX-AL** — {REGLES['EX-AL']['regle']}", icon="⚠️")
        for s in x["solutions"]:
            icone = "⚠️ " if s["alertes"] else ""
            with st.expander(f"{icone}{s['solution']} — {s['statut']}"):
                _detail(x, s)


def page_parametres():
    st.title("Paramètres — seuils des règles")
    st.caption("Valeurs de l'onglet « Paramètres » de l'Excel. Toute modification s'applique immédiatement aux règles citées.")
    p = D["parametres"]
    if st.button("Rétablir les valeurs par défaut"):
        p.clear()
        st.session_state.generation += 1
        st.rerun()
    for q in REFERENTIEL["parametres"]:
        c1, c2 = st.columns([1, 3], vertical_alignment="center")
        v = c1.number_input(f"{q['nom']} ({q['unite']})" if q["unite"] else q["nom"], value=float(p.get(q["nom"], q["valeur"])),
                            step=0.05 if q["valeur"] < 1 else 0.5, key=cle("param", q["nom"]))
        c2.markdown(f"{q['signification']}  \n:gray[Règles : {q['regles']}]")
        if v != q["valeur"]:
            p[q["nom"]] = v
        else:
            p.pop(q["nom"], None)


{"Accueil": page_accueil, "Bâtiment": page_batiment, "Locaux": page_locaux, "Espaces extérieurs": page_espaces,
 "Résultats": page_resultats, "Paramètres": page_parametres}[page]()
