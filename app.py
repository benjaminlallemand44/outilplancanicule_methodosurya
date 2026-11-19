"""Interface Streamlit de la méthode SURYA — parcours guidé (maquette).

Lancement : streamlit run app.py

L'utilisateur choisit d'abord le type d'audit (résultats de faisabilité, équivalent de l'Excel, ou
diagnostic complet avec compte rendu) et la façon de saisir les locaux, puis suit les étapes dans
l'ordre ; les documents sont générés à la dernière étape.

Les réponses vivent dans ``st.session_state.donnees`` (aucune base de données) ; le calcul est
délégué à ``surya.moteur`` et le PDF à ``surya.rapport``, qui ne dépendent pas de l'interface.
"""
from __future__ import annotations

import csv
import html
import io
import json
import unicodedata
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from surya import moteur
from surya import questionnaire as QU
from surya.import_excel import ImportImpossible, importer
from surya.stockage import DepotMemoire
from surya.moteur import NB_MURS_MAX, ORIENTATIONS, REFERENTIEL, REGLES
from surya.questions import (QUESTIONS_FACADE, QUESTIONS_MUR, SECTIONS_BATIMENT, SECTIONS_ESPACE, SECTIONS_LOCAL,
                             visible)
from surya.rapport import CHAMPS_AUDIT, QUESTIONS_DU_CAS, generer_pdf
from surya.rapport import donnee_manquante as _manquante

RACINE = Path(__file__).parent

MODES = {
    "resultats": {
        "titre": "Résultats de faisabilité",
        "court": "Résultats",
        "etapes": ["Bâtiment", "Locaux", "Espaces extérieurs", "Façades", "Vérification", "Résultats"],
    },
    "complet": {
        "titre": "Diagnostic complet",
        "court": "Diagnostic complet",
        "etapes": ["Identification", "Bâtiment", "Locaux", "Espaces extérieurs", "Façades", "Questionnaires usagers",
                   "Vérification",
                   "Documents"],
    },
}
COURTS = {"Espaces extérieurs": "Espaces ext.", "Questionnaires usagers": "Questionnaires"}  # barre d'étapes
SAISIES = {
    "guidee": ("Pas à pas",
               "Le bâtiment puis chaque local et chaque espace sont remplis bloc par bloc (usages, ouvertures en "
               "plafond, murs et baies, équipements, éclairage…), un écran à la fois, avec « Suivant ». Le plus "
               "simple pendant ou juste après la visite, en suivant l'ordre du carnet."),
    "libre": ("Fiches à onglets",
              "Le bâtiment, chaque local et chaque espace sont des fiches dont tous les blocs sont accessibles par "
              "onglets, dans l'ordre de votre choix. Pratique pour reprendre ou corriger une saisie, ou si vous "
              "connaissez bien la grille."),
}
# statut -> (fond, texte)
COULEURS = {  # même ordre que la légende des PDF
    moteur.RECOMMANDE: ("#d3f0db", "#0f5a26"),
    moteur.A_OPTIMISER: ("#ffe2c2", "#8a4300"),
    moteur.EN_PLACE: ("#d6e6fb", "#0e4a8a"),
    moteur.SOUS_RESERVE: ("#fff2b3", "#6b5300"),
    moteur.NON_RECOMMANDE: ("#f9d2d0", "#8c1d18"),
    moteur.NON_CONCERNE: ("#e6e6e6", "#4d4d4d"),
}
# Aides à la saisie tirées du document de méthode (SURYA, version 01 du 27/10/2026)
AIDES = {
    "MEX-07": "Estimé à l'œil ou sur photo, sans mesure. Aucun ; Faible : profondeur inférieure à la moitié de la "
              "hauteur de la baie, ou débord nettement au-dessus de la baie ; Important : profondeur au moins égale à "
              "la moitié de la hauteur de la baie et débord juste au-dessus.",
    "MEX-05": "16 cm n'est pas une valeur de dimensionnement : c'est la profondeur de tableau qui permet d'envisager "
              "une protection solaire parallèle au vitrage posée en tableau.",
    "MEX-32": "La pose de films solaires est la dernière solution à envisager, du fait de sa faible efficacité.",
}

st.set_page_config(page_title="Méthode SURYA — faisabilité d'actions d'adaptation", page_icon="🌡️", layout="wide",
                   initial_sidebar_state="collapsed")
ss = st.session_state


# ------------------------------------------------------------------ état
def donnees_vides() -> dict:
    return {"audit": {}, "batiment": {}, "facades": {}, "locaux": [], "espaces": [], "parametres": {},
            "questionnaires": []}


def charger(d: dict):
    """Remplace toutes les données (exemple, import) et réinitialise les champs affichés."""
    base = donnees_vides()
    base.update({k: v for k, v in d.items() if k in base})
    for x in base["locaux"] + base["espaces"] + base["questionnaires"]:
        x.setdefault("_id", uuid.uuid4().hex[:8])
    ss.donnees = base
    ss.generation = ss.get("generation", 0) + 1
    ss.edition = {"locaux": None, "espaces": None}
    ss.theme = {"locaux": 0, "espaces": 0, "batiment": 0}


if "donnees" not in ss:
    charger(donnees_vides())
for k, v in (("mode", None), ("saisie", "guidee"), ("etape", 0), ("etape_max", 0), ("vue", "parcours"),
             ("message", None), ("haut", False)):
    ss.setdefault(k, v)
D = ss.donnees


def cle(*parts) -> str:
    return ":".join(str(p) for p in (ss.generation, *parts))


def etapes() -> list[str]:
    return MODES[ss.mode]["etapes"] if ss.mode else []


def aller(etape: str | int):
    """Change d'étape du parcours (et remonte en haut de page)."""
    n = etapes().index(etape) if isinstance(etape, str) else etape
    ss.etape = n
    ss.etape_max = max(ss.etape_max, n)
    ss.vue = "parcours"
    ss.haut = True
    st.rerun()


def doublons(cle_liste: str) -> list[str]:
    """Noms portés par plusieurs locaux (ou espaces) : indiscernables dans les tableaux et documents."""
    noms = [x.get(ENTITES[cle_liste]["code_nom"]) for x in D[cle_liste]]
    return sorted({n for n in noms if n and noms.count(n) > 1})


def nom_entite(x: dict, i: int, cle_liste: str) -> str:
    cfg = ENTITES[cle_liste]
    return x.get(cfg["code_nom"]) or f"{cfg['defaut']} {i + 1}"


# ------------------------------------------------------------------ champs de saisie
def _etiquette(q) -> str:
    unite = f" ({q['unite']})" if q.get("unite") else ""
    code = "MEX-01" if q["code"] == "orientation" else q["code"].removesuffix("b")
    return f"{q['libelle']}{unite} · {code}"


def champ(q: dict, d: dict, prefixe: str):
    """Affiche le champ d'une question et range la réponse dans ``d``."""
    code, typ, k = q["code"], q["type"], cle(prefixe, q["code"])
    aide = AIDES.get(code) or ("Question informative : elle n'entre pas dans le calcul des statuts." if q.get("info") else None)
    actuel = d.get(code)
    if typ == "choix":
        opts = q["options"]
        hors_liste = actuel if actuel is not None and actuel not in opts else None
        if hors_liste is not None:
            actuel = None
        if sum(len(o) for o in opts) <= 26:
            v = st.segmented_control(_etiquette(q), opts, default=actuel, key=k, help=aide)
        else:
            v = st.selectbox(_etiquette(q), opts, index=opts.index(actuel) if actuel else None,
                             placeholder="Choisir…", key=k, help=aide)
        if hors_liste is not None and v is None:  # valeur importée hors liste : conservée tant qu'on ne la change pas
            st.caption(f"⚠️ Réponse importée hors liste : « {hors_liste} ». Choisissez une réponse de la liste.")
            v = hors_liste
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
        inconnu = st.checkbox("Épaisseur d'isolant inconnue (non visible) · B-24", value=actuel == "inconnu",
                              key=k + ":inconnu")
        if inconnu:
            return "inconnu"
    if not isinstance(actuel, (int, float)) or isinstance(actuel, bool):
        actuel = None
    haut = 4 if unite == "0 à 4" else None
    hors_bornes = actuel is not None and (actuel < 0 or (haut is not None and actuel > haut))
    if hors_bornes:
        st.caption(f"⚠️ Valeur importée hors des valeurs possibles : {actuel}.")
    entier = actuel is None or float(actuel).is_integer()
    if unite in ("", "pers.", "0 à 4") and entier and not hors_bornes:
        return st.number_input(_etiquette(q), min_value=0, max_value=haut, step=1,
                               value=None if actuel is None else int(actuel), placeholder="—", key=k, help=aide)
    if hors_bornes:  # pas de bornes imposées : la valeur importée reste affichée telle quelle
        return st.number_input(_etiquette(q), value=float(actuel), key=k, help=aide)
    pas, fmt = (0.1, "%.2f") if unite == "m" else (1.0, "%.1f")
    return st.number_input(_etiquette(q), min_value=0.0, step=pas, format=fmt,
                           value=None if actuel is None else float(actuel), placeholder="—", key=k, help=aide)


def section(s: dict, d: dict, etats, cb: dict, prefixe: str):
    """Questions visibles d'une section, sur deux colonnes. ``etats`` est recalculé avant chaque
    question pour qu'une question conditionnelle apparaisse dès que sa condition est remplie."""
    cols = st.columns(2, gap="large")
    i = 0
    for q in s["questions"]:
        if visible(q["code"], etats(), d, cb):
            with cols[i % 2]:
                champ(q, d, prefixe)
            i += 1


def sans_reponse(sections, d: dict, etats, cb: dict) -> list[dict]:
    """Questions affichées, utiles au calcul, et restées sans réponse."""
    out = []
    for s in sections:
        for q in s["questions"]:
            if q.get("info") or q["type"] == "case":
                continue
            if visible(q["code"], etats(), d, cb) and d.get(q["code"]) in (None, "", []):
                out.append(q)
    return out


def murs_incomplets(l: dict) -> list[str]:
    if l.get("aucune_baie"):
        return []
    murs = [m for m in (l.get("murs") or []) if m]
    if not murs:
        return ["aucun mur extérieur décrit (ou cocher « Aucune baie en façade »)"]
    out = []
    for i, m in enumerate(murs, start=1):
        manque = [lib for k, lib in (("orientation", "orientation"), ("MEX-04", "position des baies"),
                                     ("MEX-06", "état des menuiseries"), ("MEX-07", "débord"), ("baies", "types de baie"))
                  if not m.get(k)]
        if m.get("MEX-04") in ("Nu intérieur", "En tunnel") and m.get("MEX-05") is None:
            manque.append("distance vitrage-façade")
        if manque:
            out.append(f"mur {i} : " + ", ".join(manque))
    return out


def avertir(questions: list[dict], autres: list[str] = ()):
    """Signale ce qui reste à renseigner, sans bloquer."""
    items = [f"{q['libelle']} ({q['code'].removesuffix('b')})" for q in questions] + list(autres)
    if not items:
        st.caption("✅ Tout est renseigné ici.")
        return
    with st.expander(f"⚠️ {len(items)} élément(s) sans réponse — vous pouvez continuer, la solution concernée "
                     "passera « Sous réserve »"):
        st.markdown("\n".join(f"- {html.escape(t)}" for t in items))


def pastille(statut: str) -> str:
    if not statut:
        return "<span style='color:#999'>—</span>"
    fond, texte = COULEURS.get(statut, ("#eee", "#333"))
    return (f"<span style='background:{fond};color:{texte};padding:2px 10px;border-radius:12px;"
            f"font-size:0.85em;font-weight:600;white-space:nowrap'>{html.escape(statut)}</span>")


def remonter():
    """Remonte en haut de la page après un changement d'étape."""
    if ss.haut:
        ss.haut = False
        ss.nonce = ss.get("nonce", 0) + 1
        components.html(f"<script>/*{ss.nonce}*/const m=window.parent.document.querySelector('[data-testid=\"stMain\"]');"
                        "if(m){m.scrollTo(0,0);}window.parent.scrollTo(0,0);</script>", height=0)


CB = moteur.etats_batiment(D["batiment"], D["facades"])


# ------------------------------------------------------------------ écran de départ
def ecran_depart():
    st.title("🌡️ Audit de faisabilité d'actions d'adaptation")
    st.markdown("Méthode SURYA Ingénierie / ACTEE — plan rafraîchissement des écoles. À partir des relevés de visite, "
                "l'outil établit pour chaque local et chaque espace extérieur le **statut de faisabilité** de chaque "
                "solution de confort d'été.")

    if D["locaux"] or D["espaces"] or D["batiment"]:
        st.info(f"Une saisie est en cours ({len(D['locaux'])} local(aux), {len(D['espaces'])} espace(s) extérieur(s)) : "
                "elle sera conservée quel que soit votre choix.", icon="💾")

    st.subheader("1. Comment voulez-vous remplir le questionnaire ?")
    choix = st.radio("Mode de saisie", list(SAISIES), index=list(SAISIES).index(ss.saisie),
                     format_func=lambda k: SAISIES[k][0], captions=[SAISIES[k][1] for k in SAISIES],
                     label_visibility="collapsed", key="choix_saisie")
    ss.saisie = choix
    st.caption("Vous pourrez changer de mode à tout moment depuis les étapes Bâtiment, Locaux et Espaces extérieurs.")

    st.subheader("2. Que voulez-vous produire ?")
    c1, c2 = st.columns(2, gap="large")
    with c1.container(border=True, height="stretch"):
        st.markdown("### 📊 Résultats de faisabilité")
        st.markdown("L'équivalent de l'Excel de la méthode : vous saisissez le bâtiment, les façades, les locaux et "
                    "les espaces extérieurs, et vous obtenez les statuts de chaque solution.")
        st.markdown("**À la fin :** tableau des statuts à l'écran, **PDF des résultats** (2 à 3 pages), export CSV.")
        st.markdown(f":gray[{len(MODES['resultats']['etapes'])} étapes : "
                    f"{' → '.join(MODES['resultats']['etapes'])}]")
        if st.button("Commencer — résultats", type="primary", width="stretch"):
            demarrer("resultats")
    with c2.container(border=True, height="stretch"):
        st.markdown("### 📄 Diagnostic complet")
        st.markdown("Même saisie, avec en plus l'identification de l'audit (établissement, auditeur, date), vos "
                    "observations par local et espace, les **questionnaires usagers** (confort estival) et un "
                    "commentaire général.")
        st.markdown("**À la fin :** le **compte rendu complet** (page de garde, synthèse, plan d'action, alertes, "
                    "fiches détaillées) et le PDF des résultats.")
        st.markdown(f":gray[{len(MODES['complet']['etapes'])} étapes : {' → '.join(MODES['complet']['etapes'])}]")
        if st.button("Commencer — diagnostic complet", type="primary", width="stretch"):
            demarrer("complet")

    with st.expander("Reprendre une saisie existante ou essayer avec un exemple"):
        bloc_donnees(prefixe="depart")
    st.divider()
    st.caption(f"{REFERENTIEL['version']}. © 2026 ACTEE et SURYA Ingénierie — contenu de la méthode diffusé sous "
               "licence [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.fr). Maquette : les "
               "données ne sont pas enregistrées sur un serveur ; exportez la saisie pour la conserver.")


def demarrer(mode: str):
    ss.mode = mode
    ss.etape, ss.etape_max = 0, 0
    if D["locaux"] or D["espaces"]:  # saisie reprise : toutes les étapes sont accessibles
        ss.etape_max = len(etapes()) - 1
    aller(0)


def bloc_donnees(prefixe: str):
    """Exemple, import, export, effacement."""
    c1, c2 = st.columns(2)
    if c1.button("Charger l'exemple de l'Excel", width="stretch", key=f"{prefixe}:exemple"):
        exemple = json.loads((RACINE / "surya" / "exemple.json").read_text(encoding="utf-8"))
        exemple["questionnaires"] = [dict(r, source="exemple (fictif)") for r in
                                     QU.lire_csv((RACINE / "surya" / "exemple_questionnaires.csv").read_bytes())[0]]
        charger(exemple)
        ss.message = ("Exemple chargé : 3 locaux, 1 espace extérieur et 14 questionnaires usagers fictifs.")
        ss.etape_max = len(etapes()) - 1 if ss.mode else 0
        st.rerun()
    c2.download_button("Exporter la saisie (JSON)", json.dumps(D, ensure_ascii=False, indent=1),
                       file_name="saisie_surya.json", mime="application/json", width="stretch", key=f"{prefixe}:export")
    fichier = st.file_uploader("Importer une saisie (JSON) ou un Excel de la méthode déjà rempli (.xlsx)",
                               type=["json", "xlsx"], key=cle(prefixe, "import"))
    if fichier is not None and st.button("Importer ce fichier", type="primary", key=f"{prefixe}:importer"):
        try:
            d, notes = importer(fichier.name, fichier.getvalue())
        except ImportImpossible as e:
            st.error(f"Import impossible : {e}")
        except Exception:  # cas non prévu : message générique plutôt qu'une trace Python
            st.error("Import impossible : fichier illisible. Utilisez un fichier exporté par l'outil (.json) ou "
                     "l'Excel de la méthode (.xlsx).")
        else:
            charger(d)
            ss.message = f"Fichier importé : {len(D['locaux'])} local(aux), {len(D['espaces'])} espace(s) extérieur(s)."
            ss.notes_import = notes
            ss.etape_max = len(etapes()) - 1 if ss.mode else 0
            st.rerun()
    if ss.message:
        st.success(ss.message)
        ss.message = None
    notes = ss.pop("notes_import", None)
    if notes:
        with st.expander(f"⚠️ {len(notes)} correction(s) apportée(s) au fichier importé", expanded=True):
            st.markdown("\n".join(f"- {html.escape(n)}" for n in notes))


# ------------------------------------------------------------------ en-tête et navigation
def entete():
    c1, c2 = st.columns([5, 1.4], vertical_alignment="center")
    c1.markdown(f"#### 🌡️ Audit de faisabilité d'actions d'adaptation · :green[{MODES[ss.mode]['titre']}]")
    with c2.popover("⚙️ Réglages", width="stretch"):
        if st.button("Seuils et données", width="stretch"):
            ss.vue = "reglages"
            st.rerun()
        if st.button("Changer de type d'audit", width="stretch", help="Revenir à l'écran de départ ; la saisie est conservée."):
            ss.mode = None
            st.rerun()
    # Barre d'étapes : sur une seule ligne, défilable horizontalement sur téléphone
    st.html("<style>.st-key-etapes [data-testid='stHorizontalBlock']{flex-wrap:nowrap;overflow-x:auto;gap:.4rem}"
            ".st-key-etapes [data-testid='stColumn']{min-width:max-content;flex:1 0 auto}"
            ".st-key-etapes button p{white-space:nowrap}</style>")
    with st.container(key="etapes"):
        cols = st.columns(len(etapes()))
        for i, (col, nom) in enumerate(zip(cols, etapes())):
            fait = "✓ " if i < ss.etape_max and i != ss.etape else ""
            if col.button(f"{fait}{i + 1}. {COURTS.get(nom, nom)}", key=f"nav:{i}", width="stretch",
                          disabled=i > ss.etape_max, type="primary" if i == ss.etape else "secondary", help=nom):
                ss.edition = {"locaux": None, "espaces": None}
                aller(i)


def pied(suivant_label: str | None = None, precedent: bool = True):
    """Boutons Précédent / Suivant du parcours."""
    st.divider()
    c1, _, c3 = st.columns([1, 2, 1.3])
    if precedent and ss.etape > 0 and c1.button("← Étape précédente", width="stretch"):
        aller(ss.etape - 1)
    if ss.etape < len(etapes()) - 1:
        lib = suivant_label or f"Suivant : {etapes()[ss.etape + 1]} →"
        if c3.button(lib, type="primary", width="stretch"):
            aller(ss.etape + 1)


# ------------------------------------------------------------------ étapes
def etape_identification():
    st.header("Identification de l'audit")
    st.markdown("Ces informations figurent en page de garde du compte rendu. Elles n'interviennent pas dans le calcul.")
    a = D["audit"]
    cols = st.columns(2, gap="large")
    for n, (k, lib) in enumerate(CHAMPS_AUDIT):
        v = cols[n % 2].text_input(lib, value=a.get(k, ""), key=cle("audit", k)).strip()
        if v:
            a[k] = v
        else:
            a.pop(k, None)
    manque = [lib for k, lib in CHAMPS_AUDIT if not a.get(k)]
    avertir([], [f"{lib}" for lib in manque])
    pied()


def selecteur_saisie(cle_widget: str):
    """Permet de changer de mode de saisie (pas à pas / fiches à onglets)."""
    mode = st.segmented_control("Mode de saisie", list(SAISIES), default=ss.saisie,
                                format_func=lambda k: SAISIES[k][0], key=f"saisie:{cle_widget}",
                                help=" · ".join(f"{v[0]} : {v[1]}" for v in SAISIES.values()))
    if mode and mode != ss.saisie:
        ss.saisie = mode
        st.rerun()


def _bloc_batiment(s, b, etats):
    if s["titre"] == "Ventilation mécanique":
        st.caption("Cas technique : sans compétence suffisante, laissez les champs non évalués ; la ventilation "
                   "mécanique nocturne passera alors « Sous réserve ».")
    section(s, b, etats, CB, "bat")
    avertir(sans_reponse([s], b, etats, CB))


def premier_bloc_batiment_incomplet() -> int:
    b = D["batiment"]
    etats = lambda: moteur.etats_batiment(b, D["facades"])  # noqa: E731
    for k, s in enumerate(SECTIONS_BATIMENT):
        if sans_reponse([s], b, etats, CB):
            return k
    return 0


def etape_batiment():
    c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
    c1.header("Bâtiment")
    with c2:
        selecteur_saisie("batiment")
    st.markdown("Données générales du bâtiment. Certaines questions n'apparaissent que si elles ont un objet.")
    b = D["batiment"]
    etats = lambda: moteur.etats_batiment(b, D["facades"])  # noqa: E731
    secs = SECTIONS_BATIMENT
    if ss.saisie == "guidee":
        t = min(ss.theme.get("batiment", 0), len(secs) - 1)
        choix = st.segmented_control("Bloc", range(len(secs)), default=t, key=f"bloc_bat:{t}", width="stretch",
                                     format_func=lambda k: f"{k + 1}. {secs[k]['titre']}", label_visibility="collapsed")
        if choix is not None and choix != t:
            ss.theme["batiment"] = choix
            ss.haut = True
            st.rerun()
        st.progress((t + 1) / len(secs), text=f"Bloc {t + 1} sur {len(secs)} : **{secs[t]['titre']}**")
        with st.container(border=True):
            _bloc_batiment(secs[t], b, etats)
        if t < len(secs) - 1:
            n1, _, n3 = st.columns([1, 1.5, 1.2])
            if t > 0 and n1.button("← Bloc précédent", width="stretch"):
                ss.theme["batiment"] = t - 1
                ss.haut = True
                st.rerun()
            if n3.button("Bloc suivant →", type="primary", width="stretch", help=secs[t + 1]["titre"]):
                ss.theme["batiment"] = t + 1
                ss.haut = True
                st.rerun()
            st.divider()
            if ss.etape > 0 and st.button("← Étape précédente"):
                aller(ss.etape - 1)
            return
        if st.button("← Bloc précédent"):
            ss.theme["batiment"] = t - 1
            ss.haut = True
            st.rerun()
    else:
        onglets = st.tabs([f"{k + 1}. {s['titre']}" for k, s in enumerate(secs)])
        for onglet, s in zip(onglets, secs):
            with onglet:
                _bloc_batiment(s, b, etats)
    pied()


def orientations_utilisees() -> dict[str, list[str]]:
    """Orientations citées par les murs des locaux et les espaces extérieurs."""
    out: dict[str, list[str]] = {}
    for i, l in enumerate(D["locaux"]):
        if l.get("aucune_baie"):
            continue
        for m in l.get("murs") or []:
            if m.get("orientation"):
                out.setdefault(m["orientation"], []).append(nom_entite(l, i, "locaux"))
    for i, e in enumerate(D["espaces"]):
        for o in e.get("E-20") or []:
            if o in ORIENTATIONS:
                out.setdefault(o, []).append(nom_entite(e, i, "espaces"))
    return out


def _ligne_facade(o, f, autres, f01, citee=""):
    with st.container(border=bool(f.get("F-01"))):
        cols = st.columns([1.4] + [2] * len(autres))
        decrite = cols[0].checkbox(f"Façade **{o}**", value=bool(f.get("F-01")), key=cle("fac", o, "F-01"),
                                   help=f01["libelle"])
        if citee:
            cols[0].caption(citee)
        if decrite:
            f["F-01"] = True
            for col, q in zip(cols[1:], autres):
                with col:
                    champ({**q, "type": "choix"}, f, f"fac:{o}")
        else:
            f.pop("F-01", None)


def etape_facades():
    st.header("Façades")
    st.markdown("Décrivez les façades du bâtiment qui portent les baies des locaux visités ou qui bordent un espace "
                "extérieur. Les règles des locaux (protections solaires) et des espaces (ombrage adossé) utilisent "
                "la façade de **même orientation** que le mur ou l'espace.")
    utilisees = orientations_utilisees()
    f01, autres = QUESTIONS_FACADE[0], QUESTIONS_FACADE[1:]
    for o in ORIENTATIONS:
        D["facades"].setdefault(o, {})
        deja = ss.setdefault("facades_cochees", set())
        if o in utilisees and (ss.generation, o) not in deja:
            D["facades"][o]["F-01"] = True  # façade citée : cochée d'office (une seule fois), à décrire
            deja.add((ss.generation, o))
    citees = [o for o in ORIENTATIONS if o in utilisees]
    if citees:
        st.subheader("Façades citées par vos locaux et espaces")
        for o in citees:
            _ligne_facade(o, D["facades"][o], autres, f01, "citée par " + ", ".join(dict.fromkeys(utilisees[o])))
    else:
        st.info("Aucun mur de local ni espace extérieur n'indique d'orientation pour l'instant.")
    reste = [o for o in ORIENTATIONS if o not in utilisees]
    with st.expander("Autres façades", expanded=not citees or any(D["facades"][o].get("F-01") for o in reste)):
        for o in reste:
            _ligne_facade(o, D["facades"][o], autres, f01)
    oublis = [f"façade {o} citée par {', '.join(dict.fromkeys(n))} mais non décrite" for o, n in utilisees.items()
              if not (D["facades"].get(o) or {}).get("F-01")]
    incompletes = [f"façade {o} : {q['libelle']}" for o, f in D["facades"].items() if f.get("F-01")
                   for q in autres if not f.get(q["code"])]
    avertir([], oublis + incompletes)
    pied()


# --- locaux et espaces --------------------------------------------------------------------
ENTITES = {
    "locaux": {"code_nom": "L-01", "defaut": "Local", "un": "un local", "le": "le local", "titre": "Locaux",
               "sections": SECTIONS_LOCAL, "etats": lambda x: moteur.etats_local(x, CB)},
    "espaces": {"code_nom": "E-01", "defaut": "Espace", "un": "un espace extérieur", "le": "l'espace",
                "titre": "Espaces extérieurs", "sections": SECTIONS_ESPACE, "etats": lambda x: moteur.etats_espace(x)},
}


def themes(cle_liste: str) -> list[tuple]:
    th = [("section", s["titre"], s) for s in ENTITES[cle_liste]["sections"]]
    if cle_liste == "locaux":
        th.insert(2, ("murs", "Murs et baies en façade", None))
    if ss.mode == "complet":
        th.append(("observations", "Observations", None))
    return th


def manques_theme(cle_liste: str, x: dict, th: tuple) -> tuple[list[dict], list[str]]:
    kind, _, s = th
    if kind == "section":
        return sans_reponse([s], x, lambda: ENTITES[cle_liste]["etats"](x), CB), []
    if kind == "murs":
        return [], murs_incomplets(x)
    return [], []


def nb_manques(cle_liste: str, x: dict) -> int:
    return sum(len(a) + len(b) for a, b in (manques_theme(cle_liste, x, th) for th in themes(cle_liste)))


def etape_entites(cle_liste: str):
    i = ss.edition[cle_liste]
    if i is not None and i < len(D[cle_liste]):
        editeur(cle_liste, i)
    else:
        ss.edition[cle_liste] = None
        liste_entites(cle_liste)


def liste_entites(cle_liste: str):
    cfg, liste = ENTITES[cle_liste], D[cle_liste]
    st.header(cfg["titre"])
    if cle_liste == "locaux":
        st.markdown("Ajoutez chaque local visité (classe, dortoir, salle de motricité, bureau…). Pour chacun, "
                    "les statuts sont calculés en direct.")
    else:
        st.markdown("Ajoutez chaque espace extérieur (cour, préau, jardin…). S'il n'y en a pas, passez à l'étape suivante.")
    c1, c2 = st.columns([3, 2], vertical_alignment="center")
    with c2:
        selecteur_saisie(cle_liste)
    for n in doublons(cle_liste):
        st.warning(f"Plusieurs {cfg['titre'].lower()} portent le même nom « {n} » : donnez-leur des noms distincts "
                   "pour les reconnaître dans les tableaux et les documents.", icon="⚠️")
    if ss.message:
        st.success(ss.message)
        ss.message = None

    if not liste:
        st.info(f"Aucun {cfg['defaut'].lower()} pour l'instant.")
    else:
        res = moteur.calculer(D)[cle_liste]
        cols = st.columns(3)
        for i, x in enumerate(liste):
            with cols[i % 3].container(border=True):
                st.markdown(f"**{html.escape(nom_entite(x, i, cle_liste))}**")
                sous_titre = x.get("L-02") if cle_liste == "locaux" else ", ".join(x.get("E-02") or [])
                st.caption(sous_titre or "type non renseigné")
                n = nb_manques(cle_liste, x)
                st.markdown("✅ Complet" if n == 0 else f"⚠️ {n} élément(s) sans réponse")
                compte = {}
                for s in res[i]["solutions"]:
                    compte[s["statut"]] = compte.get(s["statut"], 0) + 1
                st.markdown(" ".join(f"{pastille(s)}&nbsp;<b>{compte[s]}</b>" for s in COULEURS if s in compte),
                            unsafe_allow_html=True)
                b1, b2, b3 = st.columns([1.4, 1, 1])
                if b1.button("✏️ Modifier", key=f"mod:{cle_liste}:{x['_id']}", width="stretch"):
                    ouvrir(cle_liste, i)
                if b2.button("⧉", key=f"dup:{cle_liste}:{x['_id']}", width="stretch", help="Dupliquer"):
                    copie = json.loads(json.dumps(x))
                    copie["_id"] = uuid.uuid4().hex[:8]
                    copie[cfg["code_nom"]] = f"{nom_entite(x, i, cle_liste)} (copie)"
                    liste.insert(i + 1, copie)
                    st.rerun()
                if b3.button("🗑", key=f"del:{cle_liste}:{x['_id']}", width="stretch", help="Supprimer"):
                    liste.pop(i)
                    st.rerun()
    if st.button(f"➕ Ajouter {cfg['un']}", type="primary" if not liste else "secondary"):
        liste.append({"_id": uuid.uuid4().hex[:8]})
        ouvrir(cle_liste, len(liste) - 1)
    pied()


def ouvrir(cle_liste: str, i: int, theme: int = 0):
    ss.edition[cle_liste] = i
    ss.theme[cle_liste] = theme
    ss.haut = True
    st.rerun()


def fermer(cle_liste: str, i: int):
    x = D[cle_liste][i]
    ss.message = f"« {nom_entite(x, i, cle_liste)} » enregistré. Ajoutez-en un autre ou passez à l'étape suivante."
    ss.edition[cle_liste] = None
    ss.haut = True
    st.rerun()


def editeur(cle_liste: str, i: int):
    cfg, x = ENTITES[cle_liste], D[cle_liste][i]
    pid, nom_avant = f"{cle_liste}:{x['_id']}", x.get(cfg["code_nom"])
    th = themes(cle_liste)
    c1, c2 = st.columns([1.3, 4], vertical_alignment="center")
    if c1.button(f"← Liste des {cfg['titre'].lower()}", width="stretch"):
        ss.edition[cle_liste] = None
        st.rerun()
    c2.markdown(f"### {html.escape(nom_entite(x, i, cle_liste))} :gray[· {cfg['defaut'].lower()} {i + 1} sur {len(D[cle_liste])}]")

    gauche, droite = st.columns([2.6, 1], gap="large")
    with gauche:
        if ss.saisie == "guidee":
            t = min(ss.theme[cle_liste], len(th) - 1)
            choix = st.segmented_control("Thème", range(len(th)), default=t, key=f"theme:{pid}:{t}",
                                         format_func=lambda k: f"{k + 1}. {th[k][1]}", label_visibility="collapsed",
                                         width="stretch")
            if choix is not None and choix != t:
                ouvrir(cle_liste, i, choix)
            st.progress((t + 1) / len(th), text=f"Thème {t + 1} sur {len(th)} : **{th[t][1]}**")
            with st.container(border=True):
                afficher_theme(cle_liste, x, pid, th[t])
            n1, _, n3 = st.columns([1, 1.5, 1.2])
            if t > 0 and n1.button("← Thème précédent", width="stretch"):
                ouvrir(cle_liste, i, t - 1)
            if t < len(th) - 1:
                if n3.button("Thème suivant →", type="primary", width="stretch", help=th[t + 1][1]):
                    ouvrir(cle_liste, i, t + 1)
            elif n3.button(f"✓ Terminer {cfg['le']}", type="primary", width="stretch"):
                fermer(cle_liste, i)
        else:
            onglets = st.tabs([f"{k + 1}. {t[1]}" for k, t in enumerate(th)])
            for onglet, t in zip(onglets, th):
                with onglet:
                    afficher_theme(cle_liste, x, pid, t)
            if st.button(f"✓ Terminer {cfg['le']}", type="primary"):
                fermer(cle_liste, i)
    with droite:
        n = nb_manques(cle_liste, x)
        st.markdown("✅ Tout est renseigné" if n == 0 else f"⚠️ {n} élément(s) sans réponse")
        res = moteur.calculer(D)[cle_liste][i]
        st.markdown("**Statuts (calcul en direct)**")
        st.markdown("".join(f"<div style='margin:0 0 9px 0;font-size:0.88em'>{html.escape(s['solution'])}<br>"
                            f"{pastille(s['statut'])}</div>" for s in res["solutions"]), unsafe_allow_html=True)
    if x.get(cfg["code_nom"]) != nom_avant:  # le nom vient de changer : met à jour l'en-tête
        st.rerun()


def afficher_theme(cle_liste: str, x: dict, pid: str, th: tuple):
    kind, titre, s = th
    if kind == "section":
        section(s, x, lambda: ENTITES[cle_liste]["etats"](x), CB, pid)
    elif kind == "murs":
        _murs(x, pid)
    else:
        _observations(x, pid)
    q, autres = manques_theme(cle_liste, x, th)
    avertir(q, autres)


def _murs(l: dict, pid: str):
    """Baies en façade : jusqu'à 4 murs extérieurs, un par orientation."""
    st.caption("Décrivez chaque mur extérieur du local qui porte des baies (4 au maximum), un bloc par orientation.")
    aucune = st.checkbox("Aucune baie en façade :gray[· MEX-01]", value=bool(l.get("aucune_baie")), key=cle(pid, "aucune"))
    if aucune:
        l["aucune_baie"] = True
        return
    l.pop("aucune_baie", None)
    murs = l.get("murs") or []
    if not murs:  # mur affiché pour la saisie, enregistré seulement s'il est rempli
        murs = [{}]
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
                st.caption(f"ℹ️ La façade {ori} sera à décrire à l'étape Façades (alignement, accès, obstacles, "
                           "désordres), après les espaces extérieurs.")
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
    if l.get("murs") is not murs and any(murs):  # le mur affiché vient d'être rempli : on l'enregistre
        l["murs"] = murs
    c1, c2, _ = st.columns([1.5, 1.8, 4])
    if len(murs) < NB_MURS_MAX and c1.button("➕ Ajouter un mur", key=cle(pid, "addmur")):
        l["murs"] = murs
        murs.append({})
        st.rerun()
    if len(murs) > 1 and c2.button("🗑 Supprimer le dernier mur", key=cle(pid, "delmur")):
        murs.pop()
        st.rerun()


def _observations(x: dict, pid: str):
    st.caption("Texte libre repris dans la fiche du compte rendu. Les éléments décisifs restent saisis dans les "
               "questions fermées : ce champ ne modifie aucun statut.")
    v = st.text_area("Observations de l'auditeur", value=x.get("observations", ""), height=160,
                     key=cle(pid, "observations")).strip()
    if v:
        x["observations"] = v
    else:
        x.pop("observations", None)


def premier_theme_incomplet(cle_liste: str, x: dict) -> int:
    for k, th in enumerate(themes(cle_liste)):
        q, autres = manques_theme(cle_liste, x, th)
        if q or autres:
            return k
    return 0


# --- vérification ---------------------------------------------------------------------------
def etape_verification():
    st.header("Vérification avant les documents")
    st.markdown("Récapitulatif de ce qui n'est pas renseigné. Vous pouvez générer les documents dès maintenant : "
                "une donnée manquante fait passer la solution concernée « Sous réserve », comme dans la méthode.")
    if not D["locaux"] and not D["espaces"]:
        st.error("Aucun local ni espace extérieur : ajoutez-en au moins un pour obtenir des résultats.")
        b1, b2 = st.columns(2)
        if b1.button("Ajouter des locaux"):
            aller("Locaux")
        if b2.button("Ajouter des espaces extérieurs"):
            aller("Espaces extérieurs")
        pied(precedent=True)
        return
    res = moteur.calculer(D)
    total = 0

    def ligne(cle_ligne, titre, n, detail, action):
        nonlocal total
        total += n
        c1, c2, c3 = st.columns([3, 4, 1.3], vertical_alignment="center")
        c1.markdown(f"{'✅' if n == 0 else '⚠️'} **{html.escape(titre)}**")
        c2.markdown(html.escape(detail) if n else ":gray[complet]")
        if n and c3.button("Compléter", key=f"verif:{cle_ligne}", width="stretch"):
            action()

    with st.container(border=True):
        if ss.mode == "complet":
            manque = [lib for k, lib in CHAMPS_AUDIT if not D["audit"].get(k)]
            ligne("audit", "Identification", len(manque), ", ".join(manque), lambda: aller("Identification"))
        q = sans_reponse(SECTIONS_BATIMENT, D["batiment"], lambda: moteur.etats_batiment(D["batiment"], D["facades"]), CB)
        def vers_batiment():
            ss.theme["batiment"] = premier_bloc_batiment_incomplet()
            aller("Bâtiment")
        ligne("bat", "Bâtiment", len(q), f"{len(q)} question(s) sans réponse", vers_batiment)
        oublis = [f"{o} non décrite" for o in orientations_utilisees() if not (D["facades"].get(o) or {}).get("F-01")]
        oublis += [f"{o} : « {q['libelle']} » sans réponse" for o, f in D["facades"].items() if f.get("F-01")
                   for q in QUESTIONS_FACADE[1:] if not f.get(q["code"])]
        ligne("fac", "Façades", len(oublis), " · ".join(oublis), lambda: aller("Façades"))
        for cle_liste in ("locaux", "espaces"):
            for i, x in enumerate(D[cle_liste]):
                n = nb_manques(cle_liste, x)
                reserves = [s["solution"] for s in res[cle_liste][i]["solutions"] if _manquante(res[cle_liste][i], s)]
                detail = f"{n} élément(s) sans réponse" + (f" · « Sous réserve » faute de données : {', '.join(reserves)}"
                                                          if reserves else "")

                def action(c=cle_liste, k=i, xx=x):
                    ss.edition[c] = k
                    ss.theme[c] = premier_theme_incomplet(c, xx)
                    aller(ENTITES[c]["titre"])
                ligne(f"{cle_liste}:{x['_id']}", nom_entite(x, i, cle_liste), n, detail, action)
    if ss.mode == "complet":
        n = len(D["questionnaires"])
        c1, c2, c3 = st.columns([3, 4, 1.3], vertical_alignment="center")
        c1.markdown(f"{'✅' if n >= QU.MIN_REPONDANTS else 'ℹ️'} **Questionnaires usagers**")
        c2.markdown(f"{n} réponse(s)" + ("" if n >= QU.MIN_REPONDANTS else
                                           f" — facultatif ; la synthèse demande au moins {QU.MIN_REPONDANTS} réponses"))
        if n < QU.MIN_REPONDANTS and c3.button("Ajouter", key="verif:quest", width="stretch"):
            aller("Questionnaires usagers")
    for c in ("locaux", "espaces"):
        for n in doublons(c):
            st.warning(f"Plusieurs {ENTITES[c]['titre'].lower()} portent le même nom « {n} » : renommez-les pour les "
                       "distinguer dans les documents.", icon="⚠️")
    if total == 0:
        st.success("Tout est renseigné.")
    pied(suivant_label="Générer les documents →" if ss.mode == "complet" else "Voir les résultats →")


# --- questionnaires usagers ---------------------------------------------------------------------
def code_audit() -> str:
    a = D["audit"]
    if not a.get("code"):
        a["code"] = uuid.uuid4().hex[:10]
    return a["code"]


def formulaire_usager(r: dict, prefixe: str):
    """Les questions du questionnaire confort estival, avec leurs conditions. Remplit ``r``."""
    theme = None
    for q in QU.QUESTIONS:
        if not QU.visible(q["code"], r):
            r.pop(q["code"], None)
            continue
        if q["theme"] != theme:
            theme = q["theme"]
            st.markdown(f"##### {QU.THEMES[theme]}")
        k = f"{prefixe}:{q['code']}"
        lib = f"**{q['code'].removeprefix('Q')}.** {q['libelle']}"
        if q["type"] == "texte":
            v = (st.text_area if q["code"] == "Q24" else st.text_input)(lib, value=r.get(q["code"], ""), key=k).strip()
        elif q["type"] == "choix":
            v = st.radio(lib, q["options"], index=q["options"].index(r[q["code"]]) if r.get(q["code"]) in q["options"] else None,
                         key=k)
        else:
            st.markdown(lib + " :gray[(plusieurs réponses possibles)]")
            v = [o for n, o in enumerate(q["options"]) if st.checkbox(o, value=o in (r.get(q["code"]) or []), key=f"{k}:{n}")]
        if v:
            r[q["code"]] = v
        else:
            r.pop(q["code"], None)


def page_usager(code: str):
    """Questionnaire en ligne, tel qu'un usager le voit (lien ?questionnaire=<code>)."""
    st.title("Questionnaire confort estival")
    st.markdown("Ce questionnaire, anonyme, prend 5 minutes. Il porte sur la **période estivale** (mai, juin et "
                "septembre) et sur le **local que vous occupez principalement**. Vos réponses aideront à choisir les "
                "solutions pour limiter la chaleur dans l'école.")
    st.info("Maquette : vos réponses ne sont pas encore envoyées automatiquement. À la fin, téléchargez le fichier "
            "de votre réponse et transmettez-le à la personne qui réalise l'audit.", icon="ℹ️")
    if ss.get("usager_envoye"):
        st.success("Merci pour votre participation !")
        st.download_button("Télécharger ma réponse (CSV)", QU.vers_csv([ss.usager_envoye]).encode("utf-8-sig"),
                           file_name=f"reponse_questionnaire_{code}.csv", mime="text/csv", type="primary")
        if st.button("Répondre à nouveau"):
            ss.usager_envoye, ss.usager_r = None, {}
            ss.usager_n = ss.get("usager_n", 0) + 1
            st.rerun()
        return
    r = ss.setdefault("usager_r", {})
    formulaire_usager(r, f"usager:{ss.get('usager_n', 0)}")
    if st.button("Envoyer mes réponses", type="primary"):
        if not any(k.startswith("Q") for k in r):
            st.error("Le questionnaire est vide.")
        else:
            ss.usager_envoye = dict(r, horodatage=__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"))
            st.rerun()


def etape_questionnaires():
    st.header("Questionnaires usagers")
    st.markdown(f"Le questionnaire confort estival ({len(QU.QUESTIONS)} questions, 5 minutes) recueille le ressenti des occupants : "
                "ressenti thermique, gênes, pratiques d'adaptation, moments d'inconfort. Ses résultats sont "
                "**indicatifs** (enquête déclarative) et servent à vérifier la cohérence des préconisations. "
                "La synthèse est faite pour tout l'établissement. Cette étape est facultative.")
    depot = DepotMemoire(D["questionnaires"])
    code = code_audit()
    t1, t2, t3 = st.tabs(["📨 Questionnaire en ligne", "📥 Importer des réponses (CSV)", "✍️ Saisir un questionnaire papier"])
    with t1:
        st.markdown("Lien à diffuser aux enseignants et au personnel :")
        st.code(f"<adresse de l'application>/?questionnaire={code}", language=None)
        st.link_button("Ouvrir le questionnaire tel que le voient les usagers", f"?questionnaire={code}")
        st.caption("Maquette : les réponses données par ce lien ne sont pas encore enregistrées sur un serveur. "
                   "Chaque usager peut télécharger sa réponse (CSV) et vous l'envoyer ; vous l'importez dans "
                   "l'onglet suivant. Avec la base de données (étape suivante), elles arriveront ici automatiquement.")
    with t2:
        st.markdown("Fichier CSV au format du questionnaire en ligne : une ligne par répondant, une colonne par "
                    "question (`Q1` à `Q24`), réponses multiples séparées par « ; ». Les exports de formulaires "
                    "dont les en-têtes commencent par le numéro de question (« Q4 - … ») sont aussi acceptés.")
        st.download_button("Télécharger le modèle de fichier", QU.modele_csv().encode("utf-8-sig"),
                           file_name="modele_questionnaire_confort.csv", mime="text/csv")
        fichiers = st.file_uploader("Fichiers de réponses (CSV)", type=["csv"], accept_multiple_files=True,
                                    key=cle("quest", "import"))
        if fichiers and st.button("Importer ces réponses", type="primary"):
            total, avert = 0, []
            for f in fichiers:
                reps, av = QU.lire_csv(f.getvalue())
                for r in reps:
                    depot.ajouter(code, dict(r, source="import"))
                total += len(reps)
                avert += [f"{f.name} — {a}" for a in av]
            ss.message = f"{total} réponse(s) importée(s)."
            ss.avert_import = avert
            st.rerun()
    with t3:
        st.caption("Pour reporter un questionnaire rempli sur papier.")
        n = ss.get("papier_n", 0)
        r = ss.setdefault("papier_r", {})
        with st.container(border=True):
            formulaire_usager(r, cle("papier", n))
        if st.button("Ajouter ce questionnaire", type="primary"):
            if any(k.startswith("Q") for k in r):
                depot.ajouter(code, dict(r, source="papier"))
                ss.papier_r, ss.papier_n = {}, n + 1
                ss.message = "Questionnaire ajouté."
                st.rerun()
            st.error("Le questionnaire est vide.")
    if ss.message:
        st.success(ss.message)
        ss.message = None
    for a in ss.pop("avert_import", []) or []:
        st.warning(a)

    reponses = depot.lister(code)
    st.subheader(f"Réponses recueillies : {len(reponses)}")
    if reponses:
        lignes = [{"N°": k + 1, "Source": r.get("source", ""), "Reçue le": r.get("horodatage", ""),
                   "Local (Q1)": r.get("Q1", ""), "Ressenti (Q4)": r.get("Q4", ""), "Ambiance (Q5)": r.get("Q5", "")}
                  for k, r in enumerate(reponses)]
        st.dataframe(lignes, hide_index=True, width="stretch")
        c1, c2, c3 = st.columns([1.2, 1, 1.3], vertical_alignment="bottom")
        k = c1.selectbox("Réponse", range(len(reponses)), format_func=lambda i: f"N° {i + 1}")
        if c2.button("Supprimer cette réponse"):
            depot.supprimer(code, reponses[k].get("_id", ""))
            st.rerun()
        c3.download_button("Exporter toutes les réponses (CSV)", QU.vers_csv(reponses).encode("utf-8-sig"),
                           file_name="reponses_questionnaire_confort.csv", mime="text/csv")
        afficher_synthese_usagers(reponses)
    pied()


def afficher_synthese_usagers(reponses):
    m = QU.matrice(reponses, moteur.calculer(D))
    syn = m["synthese"]
    st.subheader("Synthèse (tout l'établissement)")
    if syn["repondants"] < QU.MIN_REPONDANTS:
        st.info(f"Au moins {QU.MIN_REPONDANTS} réponses sont nécessaires pour une synthèse interprétable.")
    i = syn["indicateurs"]
    c = st.columns(4)
    s = i["sensation_moyenne"]
    c[0].metric("Sensation moyenne (Q4)", "—" if s is None else f"{s:+.1f}", help="Échelle de −3 (très froide) à +3 (très chaude).")
    for col, cle_i in zip(c[1:], ("inconfort", "trop_chaud_souvent", "soleil_gene")):
        v = i[cle_i]["part"]
        col.metric(QU.LIBELLES_INDICATEURS[cle_i].split(" (")[0], "—" if v is None else f"{v:.0%}")
    st.markdown("**Matrice de correspondance ressenti / préconisations** :gray[(proposition, à valider)]")
    st.dataframe([{"Croisement": f"{l['id']} — {l['ressenti']}", "Usagers": l["usagers"], "Audit": l["audit"],
                   "Résultat": l["resultat"], "Commentaire": l["commentaire"]} for l in m["lignes"]],
                 hide_index=True, width="stretch")
    if m["indicateur"] is not None:
        st.markdown(f"**Indicateur de cohérence : {m['indicateur']:.0%}** "
                    f"({m['evalues'] - m['a_verifier']} croisement(s) sans incohérence sur {m['evalues']} évalué(s))")


# --- résultats / documents -------------------------------------------------------------------
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


def _detail(x, s):
    """Détail d'une solution : règle retenue, données manquantes, alertes, toutes les règles du bloc."""
    st.markdown(f"**{html.escape(s['solution'])}** &nbsp; {pastille(s['statut'])}", unsafe_allow_html=True)
    if not s["blocs"]:
        if s["statut"] == moteur.NON_CONCERNE:
            st.caption("La solution ne concerne pas cet espace (ce n'est pas une cour de récréation).")
        else:
            st.info(f"Cas non déterminé faute de données. À renseigner : {QUESTIONS_DU_CAS.get(s['solution'], '')}.", icon="❓")
    for b in s["blocs"]:
        bl = x["blocs"][b]
        code = bl["regle"]
        if code is None:
            st.info("Aucune règle n'a pu être vérifiée avec les données disponibles.", icon="❓")
            continue
        r = REGLES[code]
        st.markdown(f"Règle retenue **{code}** : {r['regle']}")
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


@st.cache_data(max_entries=20, show_spinner="Préparation du document…")
def _pdf(donnees_json: str, complet: bool) -> bytes:
    return generer_pdf(json.loads(donnees_json), complet=complet)


def etape_documents():
    complet = ss.mode == "complet"
    st.header("Documents" if complet else "Résultats")
    res = moteur.calculer(D)
    if not res["locaux"] and not res["espaces"]:
        st.info("Ajoutez au moins un local ou un espace extérieur pour obtenir des résultats.")
        pied()
        return
    a = D["audit"]
    base = unicodedata.normalize("NFKD", a.get("etablissement", "audit")).encode("ascii", "ignore").decode()
    suffixe = "".join(c if c.isalnum() else "_" for c in base).strip("_") + ".pdf"
    with st.container(border=True):
        if complet:
            st.subheader("📄 Vos documents")
            v = st.text_area("Commentaire général de l'auditeur (facultatif, repris dans le compte rendu)",
                             value=a.get("synthese", ""), key=cle("audit", "synthese")).strip()
            if v:
                a["synthese"] = v
            else:
                a.pop("synthese", None)
        else:
            st.subheader("📄 Télécharger les résultats")
        donnees_json = json.dumps(D, ensure_ascii=False, sort_keys=True)
        cols = st.columns([1.3, 1, 0.7] if complet else [1, 0.6, 1.4])
        if complet:
            cols[0].download_button("Compte rendu complet (PDF)", _pdf(donnees_json, True),
                                    file_name="compte_rendu_" + suffixe, mime="application/pdf", type="primary",
                                    width="stretch")
            cols[0].caption("Page de garde, cadre, synthèse, plan d'action, alertes, données manquantes, fiches détaillées.")
            k_res, k_csv = 1, 2
        else:
            k_res, k_csv = 0, 1
        cols[k_res].download_button("Résultats (PDF)", _pdf(donnees_json, False), file_name="resultats_" + suffixe,
                                    mime="application/pdf", type="secondary" if complet else "primary", width="stretch")
        cols[k_res].caption("Statuts, alertes et données manquantes (2 à 3 pages).")
        cols[k_csv].download_button("Tableau (CSV)", _export_csv(res).encode("utf-8-sig"),
                                    file_name="resultats_surya.csv", mime="text/csv", width="stretch")
        if not complet:
            with cols[2]:
                st.caption("Besoin du compte rendu complet (page de garde, plan d'action, fiches, observations) ?")
                if st.button("Passer au diagnostic complet", width="stretch"):
                    ss.mode = "complet"
                    ss.etape_max = len(etapes()) - 1
                    ss.message = None
                    aller("Identification")
    st.markdown(" ".join(pastille(s) for s in COULEURS), unsafe_allow_html=True)
    for titre, cle_, defaut in (("Locaux", "locaux", "Local"), ("Espaces extérieurs", "espaces", "Espace")):
        entites = res[cle_]
        if not entites:
            continue
        st.subheader(titre)
        _tableau(entites, defaut)
        for i, x in enumerate(entites):
            with st.expander(f"Détail des règles — {x['nom'] or f'{defaut} {i + 1}'}"):
                for s in x["solutions"]:
                    with st.container(border=True):
                        _detail(x, s)
    pied()


# ------------------------------------------------------------------ réglages
def vue_reglages():
    if st.button("← Retour à l'audit"):
        ss.vue = "parcours"
        st.rerun()
    st.title("Réglages")
    t1, t2 = st.tabs(["Données", "Seuils des règles"])
    with t1:
        st.caption("Maquette : rien n'est enregistré sur un serveur. Exportez la saisie (JSON) pour la conserver et "
                   "la réimporter plus tard.")
        bloc_donnees(prefixe="reglages")
        st.divider()
        if st.button("🗑 Tout effacer et recommencer"):
            charger(donnees_vides())
            ss.mode, ss.vue = None, "parcours"
            st.rerun()
    with t2:
        st.caption("Valeurs de l'onglet « Paramètres » de l'Excel. Toute modification s'applique immédiatement aux "
                   "règles citées et est signalée dans le compte rendu.")
        p = D["parametres"]
        if st.button("Rétablir les valeurs par défaut"):
            p.clear()
            ss.generation += 1
            st.rerun()
        for q in REFERENTIEL["parametres"]:
            c1, c2 = st.columns([1, 3], vertical_alignment="center")
            v = c1.number_input(f"{q['nom']} ({q['unite']})" if q["unite"] else q["nom"],
                                value=float(moteur.parametres(p)[q["nom"]]), step=0.05 if q["valeur"] < 1 else 0.5,
                                key=cle("param", q["nom"]))
            c2.markdown(f"{q['signification']}  \n:gray[Règles : {q['regles']}]")
            if v != q["valeur"]:
                p[q["nom"]] = v
            else:
                p.pop(q["nom"], None)


# ------------------------------------------------------------------ aiguillage
ETAPES = {"Identification": etape_identification, "Bâtiment": etape_batiment, "Façades": etape_facades,
          "Locaux": lambda: etape_entites("locaux"), "Espaces extérieurs": lambda: etape_entites("espaces"),
          "Questionnaires usagers": etape_questionnaires,
          "Vérification": etape_verification, "Résultats": etape_documents, "Documents": etape_documents}

if st.query_params.get("questionnaire"):
    page_usager(st.query_params["questionnaire"])
elif ss.mode is None:
    ecran_depart()
elif ss.vue == "reglages":
    entete()
    vue_reglages()
else:
    ss.etape = min(ss.etape, len(etapes()) - 1)
    entete()
    ETAPES[etapes()[ss.etape]]()
remonter()
