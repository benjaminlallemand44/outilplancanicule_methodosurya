"""Questionnaire usagers « confort estival » (SURYA, version 01 du 11/11/2026).

* ``QUESTIONS`` : les 23 questions du document, plus une question ouverte facultative (Q24), que le
  document annonce (« une seule question ouverte facultative pour les remarques libres ») sans la
  rédiger ;
* format d'échange CSV : une ligne par répondant, une colonne par question (``Q1`` à ``Q24``), réponses
  multiples séparées par « ; ». C'est le format que produira le questionnaire en ligne et celui que
  l'outil importe ;
* ``synthese`` : synthèse globale des réponses (tout l'établissement) ;
* ``matrice`` : croisement des réponses avec les statuts de l'audit et indicateur de cohérence.
  La méthode annonce une « matrice de correspondance item / préconisation » et un « indicateur de
  cohérence » sans les définir : ceux-ci sont une PROPOSITION (voir docs/points_a_trancher.md, § E).

Aucune dépendance à l'interface.
"""
from __future__ import annotations

import csv
import io
import re
from collections import Counter

from . import moteur

SEP_MULTI = " ; "
JAMAIS_SOUVENT = ["Jamais", "Rarement", "Parfois", "Souvent", "Très souvent"]
GENE = ["Pas du tout gênant", "Légèrement gênant", "Assez gênant", "Très gênant", "Extrêmement gênant"]
EFFICACITE = ["Pas du tout efficaces", "Peu efficaces", "Moyennement efficaces", "Plutôt efficaces",
              "Très efficaces", "Je ne sais pas / je ne les utilise pas"]

THEMES = {
    "a": "Identification du contexte",
    "b": "Ressenti thermique global (ISO 10551)",
    "c": "Gênes spécifiques",
    "d": "Pratiques d'adaptation actuelles",
    "e": "Fréquence et moments de l'inconfort",
    "f": "Remarques",
}

QUESTIONS = [
    {"code": "Q1", "theme": "a", "type": "texte",
     "libelle": "Quelle pièce de l'école occupez-vous principalement, ou dans quelle zone intervenez-vous principalement ?"},
    {"code": "Q2", "theme": "a", "type": "choix", "libelle": "À quel étage est situé ce local ?",
     "options": ["RDC", "1er étage", "2e étage", "3e étage ou plus"]},
    {"code": "Q3", "theme": "a", "type": "choix", "libelle": "Quelle est son orientation principale ?",
     "options": ["Sud", "Ouest", "Nord", "Est"]},
    {"code": "Q4", "theme": "b", "type": "choix",
     "libelle": "Dans le local principalement occupé et de manière générale, comment ressentez-vous la température "
                "intérieure en période estivale (mois de mai, juin et septembre) ?",
     "options": ["Très froide", "Froide", "Légèrement froide", "Ni chaude ni froide", "Légèrement chaude", "Chaude",
                 "Très chaude"], "echelle": [-3, -2, -1, 0, 1, 2, 3]},
    {"code": "Q5", "theme": "b", "type": "choix",
     "libelle": "Dans le local principalement occupé, comment jugeriez-vous l'ambiance thermique en période estivale ?",
     "options": ["Confortable", "Légèrement inconfortable", "Inconfortable", "Très inconfortable",
                 "Extrêmement inconfortable"], "echelle": [0, 1, 2, 3, 4]},
    {"code": "Q6", "theme": "b", "type": "choix",
     "libelle": "En règle générale, dans le local principalement occupé, en période estivale, préféreriez-vous que "
                "cette température intérieure soit :",
     "options": ["Beaucoup plus froide", "Plus froide", "Légèrement plus froide", "Inchangée", "Légèrement plus chaude",
                 "Plus chaude", "Beaucoup plus chaude"], "echelle": [-3, -2, -1, 0, 1, 2, 3]},
    {"code": "Q7", "theme": "b", "type": "choix",
     "libelle": "À votre avis, en période estivale, l'ambiance thermique dans le local principalement occupé est-elle…",
     "options": ["Tolérable", "Plutôt tolérable", "Moyennement tolérable", "Peu tolérable", "Impossible à tolérer"],
     "echelle": [0, 1, 2, 3, 4]},
    {"code": "Q8", "theme": "c", "type": "choix",
     "libelle": "Dans le local principalement occupé, en période estivale, à quelle fréquence le soleil entre-t-il "
                "directement dans la salle (taches de soleil sur les tables, les élèves ou le tableau) ?",
     "options": JAMAIS_SOUVENT, "echelle": [0, 1, 2, 3, 4]},
    {"code": "Q9", "theme": "c", "type": "choix",
     "libelle": "Lorsque cela se produit, à quel point est-ce gênant (chaleur, éblouissement, lisibilité du tableau "
                "ou des écrans) ?", "options": GENE, "echelle": [0, 1, 2, 3, 4]},
    {"code": "Q10", "theme": "c", "type": "choix",
     "libelle": "En période estivale, à quelle fréquence l'air du local vous semble-t-il « lourd », stagnant ou confiné ?",
     "options": JAMAIS_SOUVENT, "echelle": [0, 1, 2, 3, 4]},
    {"code": "Q11", "theme": "d", "type": "multi", "libelle": "De quelles protections solaires le local dispose-t-il ?",
     "options": ["Stores intérieurs", "Stores ou volets extérieurs", "Brise-soleil fixes", "Films sur vitrages",
                 "Rideaux", "Aucune", "Je ne sais pas"]},
    {"code": "Q12", "theme": "d", "type": "choix",
     "libelle": "Si vous en avez, en période estivale, à quelle fréquence utilisez-vous ces protections solaires ?",
     "options": JAMAIS_SOUVENT, "echelle": [0, 1, 2, 3, 4]},
    {"code": "Q13", "theme": "d", "type": "multi",
     "libelle": "Si vous ne les utilisez jamais ou rarement, pour quelles raisons ?",
     "options": ["Elles sont en panne ou cassées", "La commande est inaccessible ou difficile à manœuvrer",
                 "Elles assombrissent trop le local (obligation d'allumer l'éclairage)",
                 "Elles gênent la ventilation ou l'aération (claquent, bloquent l'ouverture des fenêtres)",
                 "Elles sont gérées par une autre personne", "Je n'y pense pas", "Autre"]},
    {"code": "Q14", "theme": "d", "type": "choix", "libelle": "À quel moment les fermez-vous en général ?",
     "options": ["Dès l'arrivée le matin", "Lorsque le soleil arrive dans le local", "À partir du moment où il fait chaud",
                 "En partant le soir", "Jamais"]},
    {"code": "Q15", "theme": "d", "type": "choix",
     "libelle": "Comment jugez-vous l'efficacité de ces protections solaires pour limiter la chaleur dans le local ?",
     "options": EFFICACITE},
    {"code": "Q16", "theme": "d", "type": "multi",
     "libelle": "En période estivale, à quels moments ouvrez-vous les fenêtres ?",
     "options": ["Avant les cours", "Pendant les cours", "Pendant les récréations et intercours", "Le soir en partant",
                 "Jamais"]},
    {"code": "Q17", "theme": "d", "type": "multi",
     "libelle": "Si vous ouvrez peu ou pas les fenêtres, pour quelles raisons ?",
     "options": ["Bruit extérieur", "Sécurité (risque de chute, intrusion, consignes de l'établissement)",
                 "Fenêtres bloquées ou difficiles à manœuvrer", "Air extérieur plus chaud que l'air intérieur",
                 "Insectes, pollution, pollens", "Risque de pluie", "Courants d'air", "Autre"]},
    {"code": "Q18", "theme": "d", "type": "choix",
     "libelle": "Les fenêtres peuvent-elles rester ouvertes la nuit ou le week-end ?",
     "options": ["Oui", "Non, pour des raisons de sécurité (intrusion, nuisibles, pluie…)",
                 "Non, les fenêtres ne le permettent pas", "Je ne sais pas"]},
    {"code": "Q19", "theme": "d", "type": "choix",
     "libelle": "Comment jugez-vous l'efficacité de l'ouverture des fenêtres et portes pour diminuer la chaleur dans "
                "le local ?", "options": EFFICACITE},
    {"code": "Q20", "theme": "d", "type": "choix",
     "libelle": "Utilisez-vous un équipement de rafraîchissement dans le local ?",
     "options": ["Non", "Oui, un ventilateur fixe (plafond, mural)", "Oui, un ventilateur d'appoint mobile",
                 "Oui, un climatiseur mobile", "Oui, un climatiseur fixe"]},
    {"code": "Q21", "theme": "e", "type": "choix",
     "libelle": "Dans le local principalement occupé, en période estivale, à quelle fréquence avez-vous trop chaud ?",
     "options": JAMAIS_SOUVENT, "echelle": [0, 1, 2, 3, 4]},
    {"code": "Q22", "theme": "e", "type": "multi",
     "libelle": "À quel moment de la journée la chaleur est-elle la plus gênante ?",
     "options": ["Dès l'arrivée le matin", "En fin de matinée", "En début d'après-midi", "En fin d'après-midi",
                 "Toute la journée"]},
    {"code": "Q23", "theme": "e", "type": "choix",
     "libelle": "En période estivale, la chaleur nuit-elle à votre travail ou à la concentration des élèves ?",
     "options": GENE, "echelle": [0, 1, 2, 3, 4]},
    {"code": "Q24", "theme": "f", "type": "texte", "ajout": True,
     "libelle": "Remarques libres (facultatif)"},
]
PAR_CODE = {q["code"]: q for q in QUESTIONS}
COLONNES = [q["code"] for q in QUESTIONS]


def visible(code: str, r: dict) -> bool:
    """Questions conditionnelles du questionnaire (« Si vous en avez… », « Si vous ne les utilisez… »)."""
    sans_protection = not r.get("Q11") or set(r.get("Q11") or []) <= {"Aucune", "Je ne sais pas"}
    if code in ("Q12", "Q14", "Q15"):
        return not sans_protection
    if code == "Q13":
        return not sans_protection and r.get("Q12") in ("Jamais", "Rarement")
    if code == "Q17":
        moments = r.get("Q16") or []
        return "Jamais" in moments or len(moments) <= 1
    return True


# ------------------------------------------------------------------ format CSV
def vers_csv(reponses: list[dict]) -> str:
    """Réponses -> CSV (séparateur « ; », UTF-8). Une ligne par répondant."""
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["horodatage"] + COLONNES)
    for r in reponses:
        ligne = [r.get("horodatage", "")]
        for c in COLONNES:
            v = r.get(c)
            ligne.append(SEP_MULTI.join(v) if isinstance(v, list) else (v or ""))
        w.writerow(ligne)
    return out.getvalue()


def modele_csv() -> str:
    """Modèle vide (en-têtes seulement)."""
    return vers_csv([])


def lire_csv(contenu: bytes | str) -> tuple[list[dict], list[str]]:
    """CSV -> (réponses, avertissements).

    Accepte les séparateurs « ; » ou « , », un en-tête par code (« Q4 ») ou commençant par le code
    (« Q4 - Dans le local… », « Q4. … »), comme dans l'export d'un formulaire en ligne. Les réponses
    hors liste sont ignorées et signalées.
    """
    illisible = "Fichier illisible : enregistrez-le au format CSV à partir du modèle fourni."
    if isinstance(contenu, bytes):
        if b"\x00" in contenu[:4096] or contenu[:4] in (b"PK\x03\x04", b"%PDF"):
            return [], [illisible]
        try:
            contenu = contenu.decode("utf-8-sig")
        except UnicodeDecodeError:
            contenu = contenu.decode("cp1252", errors="replace")  # CSV enregistré par Excel sous Windows
    contenu = contenu.lstrip("\ufeff")
    if not contenu.strip():
        return [], ["Fichier vide."]
    premiere = contenu.splitlines()[0]
    # Séparateur qui isole le plus d'en-têtes « Qn » (les libellés des questions contiennent des virgules)
    delim = max(";,\t", key=lambda sep: (sum(bool(re.match(r'^\s*"?\s*Q\s*\d+', h, re.I)) for h in premiere.split(sep)),
                                         sep == ";"))
    try:
        lignes = list(csv.reader(io.StringIO(contenu, newline=""), delimiter=delim))
    except csv.Error:
        return [], [illisible]
    if not lignes:
        return [], ["Fichier vide."]
    entete, avert = lignes[0], []
    index, inconnues = {}, []
    for k, h in enumerate(entete):
        m = re.match(r"^\s*Q\s*(\d+)\b", h or "", re.I)
        if m and f"Q{int(m.group(1))}" in PAR_CODE:
            index[f"Q{int(m.group(1))}"] = k
        elif (h or "").strip().lower() in ("horodatage", "timestamp", "date"):
            index["horodatage"] = k
        elif (h or "").strip():
            inconnues.append(h.strip())
    if not any(c in index for c in COLONNES):
        return [], ["Aucune colonne Q1 à Q24 reconnue : utilisez le modèle de fichier fourni."]
    if inconnues:
        avert.append("Colonne(s) non reconnue(s), ignorée(s) : " + ", ".join(f"« {h[:40]} »" for h in inconnues) + ".")
    reponses = []
    for n, ligne in enumerate(lignes[1:], start=2):
        if not any(c.strip() for c in ligne):
            continue
        r = {}
        for code, k in index.items():
            brut = ligne[k].strip() if k < len(ligne) else ""
            if not brut:
                continue
            if code == "horodatage":
                r[code] = brut
                continue
            q = PAR_CODE[code]
            if q["type"] == "texte":
                r[code] = brut
            elif q["type"] == "choix":
                v = _normaliser(brut, q["options"])
                if v:
                    r[code] = v
                else:
                    avert.append(f"Ligne {n}, {code} : réponse « {brut} » hors liste, ignorée.")
            else:
                vals, inconnus = [], []
                for morceau in re.split(r"\s*;\s*", brut):
                    v = _normaliser(morceau, q["options"])
                    (vals if v else inconnus).append(v or morceau)
                if vals:
                    r[code] = [o for o in q["options"] if o in vals]
                if inconnus:
                    avert.append(f"Ligne {n}, {code} : « {' ; '.join(inconnus)} » hors liste, ignoré.")
        for k in [k for k in r if k in PAR_CODE and not visible(k, r)]:
            del r[k]
            avert.append(f"Ligne {n}, {k} : sans objet d'après les réponses précédentes, ignorée.")
        if any(k != "horodatage" for k in r):
            reponses.append(r)
    return reponses, avert


def _simplifier(s: str) -> str:
    s = s.lower().replace("’", "'").replace("œ", "oe").replace("...", "…")
    s = re.sub(r"[…\.]+$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _normaliser(valeur: str, options: list[str]) -> str | None:
    v = _simplifier(valeur)
    for o in options:
        if _simplifier(o) == v:
            return o
    return None


# ------------------------------------------------------------------ synthèse
def _part(n, total):
    return n / total if total else None


def synthese(reponses: list[dict]) -> dict:
    """Synthèse globale : répartitions par question et indicateurs de ressenti.
    Les réponses à des questions sans objet (conditions non remplies) ne sont pas comptées."""
    reponses = [{k: v for k, v in r.items() if k not in PAR_CODE or visible(k, r)} for r in reponses]
    n = len(reponses)
    repartition = {}
    for q in QUESTIONS:
        if q["type"] == "texte":
            continue
        c = Counter()
        nb = 0
        for r in reponses:
            v = r.get(q["code"])
            if not v:
                continue
            nb += 1
            for o in (v if isinstance(v, list) else [v]):
                c[o] += 1
        repartition[q["code"]] = {"repondants": nb, "comptes": {o: c.get(o, 0) for o in q["options"]}}

    def moyenne(code):
        q = PAR_CODE[code]
        vals = [q["echelle"][q["options"].index(r[code])] for r in reponses if r.get(code) in q["options"]]
        return sum(vals) / len(vals) if vals else None

    def part(code, valeurs, parmi=None):
        """Part des répondants à ``code`` (ou à la sous-population ``parmi``) dont la réponse est dans ``valeurs``."""
        pop = [r for r in reponses if r.get(code) and (parmi is None or parmi(r))]
        oui = [r for r in pop if (set(r[code]) & set(valeurs) if isinstance(r[code], list) else r[code] in valeurs)]
        return {"part": _part(len(oui), len(pop)), "nb": len(oui), "sur": len(pop)}

    souvent = ("Souvent", "Très souvent")
    soleil_gene = [r for r in reponses if r.get("Q8") in souvent and r.get("Q9") in GENE[2:]]
    pop_soleil = [r for r in reponses if r.get("Q8")]
    indicateurs = {
        "sensation_moyenne": moyenne("Q4"),
        "preference_moyenne": moyenne("Q6"),
        "inconfort": part("Q5", PAR_CODE["Q5"]["options"][2:]),
        "peu_tolerable": part("Q7", PAR_CODE["Q7"]["options"][3:]),
        "trop_chaud_souvent": part("Q21", souvent),
        "soleil_gene": {"part": _part(len(soleil_gene), len(pop_soleil)), "nb": len(soleil_gene), "sur": len(pop_soleil)},
        "air_lourd": part("Q10", souvent),
        "protections_peu_utilisees": part("Q12", ("Jamais", "Rarement")),
        "protections_peu_efficaces": part("Q15", EFFICACITE[:2], parmi=lambda r: r.get("Q15") != EFFICACITE[-1]),
        "fenetres_fermees_nuit": part("Q18", PAR_CODE["Q18"]["options"][1:3]),
        "ouverture_peu_efficace": part("Q19", EFFICACITE[:2], parmi=lambda r: r.get("Q19") != EFFICACITE[-1]),
        "chaleur_matin": part("Q22", ("Dès l'arrivée le matin", "Toute la journée")),
        "chaleur_apres_midi": part("Q22", ("En début d'après-midi", "En fin d'après-midi", "Toute la journée")),
        "gene_travail": part("Q23", GENE[2:]),
    }
    remarques = [r["Q24"] for r in reponses if r.get("Q24")]
    autres_raisons = [r["Q13_autre"] for r in reponses if r.get("Q13_autre")]
    return {"repondants": n, "repartition": repartition, "indicateurs": indicateurs, "remarques": remarques,
            "autres": autres_raisons}


LIBELLES_INDICATEURS = {
    "inconfort": "Ambiance jugée inconfortable à extrêmement inconfortable (Q5)",
    "peu_tolerable": "Ambiance jugée peu tolérable ou impossible à tolérer (Q7)",
    "trop_chaud_souvent": "Trop chaud souvent ou très souvent (Q21)",
    "soleil_gene": "Soleil direct souvent ou très souvent, et au moins assez gênant (Q8, Q9)",
    "air_lourd": "Air lourd ou stagnant souvent ou très souvent (Q10)",
    "protections_peu_utilisees": "Protections solaires utilisées jamais ou rarement (Q12)",
    "protections_peu_efficaces": "Protections solaires jugées pas du tout ou peu efficaces (Q15)",
    "fenetres_fermees_nuit": "Fenêtres ne pouvant pas rester ouvertes la nuit ou le week-end (Q18)",
    "ouverture_peu_efficace": "Ouverture des fenêtres jugée pas du tout ou peu efficace (Q19)",
    "chaleur_matin": "Chaleur gênante dès l'arrivée le matin ou toute la journée (Q22)",
    "chaleur_apres_midi": "Chaleur gênante l'après-midi ou toute la journée (Q22)",
    "gene_travail": "Chaleur au moins assez gênante pour le travail ou la concentration (Q23)",
}


# ------------------------------------------------------------------ matrice de correspondance
SEUIL_SIGNAL = 0.30      # part des répondants au-delà de laquelle un ressenti est considéré comme signalé
MIN_REPONDANTS = 3       # en dessous, le croisement n'est pas évalué

COHERENT, A_VERIFIER, NON_CORROBORE, NON_EVALUABLE = "Cohérent", "À vérifier", "Non corroboré", "Non évaluable"
LEVIERS = (moteur.RECOMMANDE, moteur.A_OPTIMISER, moteur.SOUS_RESERVE)
PROTECTIONS = ("Protections verticales", "Protections horizontales", "Films solaires", "Sur fenêtres de toiture",
               "Sur vérandas et/ou verrières")
NOCTURNE = ("Par ventilation naturelle nocturne", "Par ventilation mécanique nocturne")
BRASSEURS = ("Mise en place de brasseurs d'air plafonniers",)

# Proposition de matrice item / préconisation : (id, ressenti, indicateur, solutions de l'audit, explication)
MATRICE = [
    ("M1", "Gêne due au soleil direct", "soleil_gene", PROTECTIONS,
     "Une gêne solaire signalée doit trouver une réponse dans les protections solaires préconisées."),
    ("M2", "Air lourd ou stagnant", "air_lourd", NOCTURNE + BRASSEURS,
     "Un air ressenti comme lourd appelle une ventilation nocturne ou des brasseurs d'air."),
    ("M3", "Chaleur dès l'arrivée le matin", "chaleur_matin", NOCTURNE,
     "Un local déjà chaud le matin traduit un défaut de décharge nocturne."),
    ("M4", "Chaleur l'après-midi", "chaleur_apres_midi", PROTECTIONS + ("Toiture",),
     "Une chaleur d'après-midi traduit surtout les apports solaires (baies, toiture)."),
    ("M5", "Inconfort global", "inconfort", None,
     "Un inconfort déclaré doit correspondre à au moins une solution à engager dans l'établissement."),
]


def _statuts(res: dict, solutions) -> list[str]:
    out = []
    for x in res["locaux"]:
        for s in x["solutions"]:
            if solutions is None or s["solution"] in solutions:
                out.append(s["statut"])
    return out


def matrice(reponses: list[dict], res: dict, seuil: float = SEUIL_SIGNAL, minimum: int = MIN_REPONDANTS) -> dict:
    """Croise la synthèse des réponses avec les statuts de l'audit (``res`` = ``moteur.calculer``).

    Chaque croisement vaut :
    * « Cohérent » : ressenti signalé et solution préconisée, ou ni l'un ni l'autre ;
    * « À vérifier » : ressenti signalé sans solution préconisée, ou solution relevée « En place »
      contredite par les usagers ;
    * « Non corroboré » : solution préconisée sans ressenti signalé (elle reste valable : solution
      sans regret, mais n'est pas confirmée par le ressenti) ;
    * « Non évaluable » : trop peu de réponses ou pas de local concerné.

    Indicateur de cohérence = part des croisements évalués qui ne sont pas « À vérifier ».
    """
    syn = synthese(reponses)
    ind = syn["indicateurs"]
    lignes = []

    def ajouter(ident, ressenti, signal_txt, audit_txt, resultat, commentaire):
        lignes.append({"id": ident, "ressenti": ressenti, "usagers": signal_txt, "audit": audit_txt,
                       "resultat": resultat, "commentaire": commentaire})

    def fmt(i):
        return "—" if i["part"] is None else f"{i['part']:.0%} ({i['nb']}/{i['sur']})"

    for ident, ressenti, cle, solutions, expl in MATRICE:
        i = ind[cle]
        statuts = _statuts(res, solutions)
        concernes = [s for s in statuts if s != moteur.NON_CONCERNE]
        nb_leviers = sum(s in LEVIERS for s in concernes)
        audit_txt = (f"{nb_leviers} préconisation(s) sur {len(concernes)}" if concernes else "aucun local concerné")
        if i["sur"] < minimum or not concernes:
            ajouter(ident, ressenti, fmt(i), audit_txt, NON_EVALUABLE,
                    "Moins de %d réponses." % minimum if i["sur"] < minimum else "Aucun local concerné dans l'audit.")
            continue
        signal = i["part"] >= seuil
        if signal and nb_leviers:
            r, c = COHERENT, "Ressenti signalé et solution(s) préconisée(s). " + expl
        elif signal:
            r, c = A_VERIFIER, ("Ressenti signalé alors que l'audit ne préconise aucune solution correspondante : "
                                "vérifier le relevé (baies, orientations, équipements) et les usages. " + expl)
        elif nb_leviers:
            r, c = NON_CORROBORE, "Solution(s) préconisée(s) sans ressenti signalé : préconisation non confirmée par les usagers."
        else:
            r, c = COHERENT, "Ni ressenti signalé, ni solution préconisée."
        ajouter(ident, ressenti, fmt(i), audit_txt, r, c)

    # M6 : protections relevées « En place » mais peu utilisées ou jugées peu efficaces
    en_place = [s for s in _statuts(res, PROTECTIONS) if s == moteur.EN_PLACE]
    i_util, i_eff = ind["protections_peu_utilisees"], ind["protections_peu_efficaces"]
    exploitables = [x for x in (i_util, i_eff) if x["sur"] >= minimum]  # minimum de réponses par indicateur
    txt = f"utilisation rare {fmt(i_util)} ; peu efficaces {fmt(i_eff)}"
    if not en_place or not exploitables:
        ajouter("M6", "Protections solaires en place peu utilisées ou peu efficaces", txt,
                f"{len(en_place)} protection(s) « En place »", NON_EVALUABLE,
                "Aucune protection relevée « En place »." if not en_place else "Moins de %d réponses." % minimum)
    else:
        mauvais = any(x["part"] >= seuil for x in exploitables)
        raisons = Counter(o for r in reponses for o in (r.get("Q13") or []))
        detail = ", ".join(f"{o} ({n})" for o, n in raisons.most_common(3))
        ajouter("M6", "Protections solaires en place peu utilisées ou peu efficaces", txt,
                f"{len(en_place)} protection(s) « En place »", A_VERIFIER if mauvais else COHERENT,
                ("Protections relevées en place mais peu utilisées ou jugées peu efficaces : vérifier leur état, "
                 "leur commande et leur usage." + (f" Raisons citées : {detail}." if detail else ""))
                if mauvais else "Protections en place utilisées et jugées efficaces.")

    # M7 : fenêtres ne pouvant rester ouvertes la nuit et ventilation naturelle nocturne recommandée
    i = ind["fenetres_fermees_nuit"]
    vn = _statuts(res, ("Par ventilation naturelle nocturne",))
    vn_reco = sum(s == moteur.RECOMMANDE for s in vn)
    if i["sur"] < minimum or not vn:
        ajouter("M7", "Fenêtres fermées la nuit", fmt(i), f"{vn_reco} ventilation(s) naturelle(s) recommandée(s)",
                NON_EVALUABLE, "Moins de %d réponses." % minimum if vn else "Aucun local.")
    elif i["part"] >= seuil and vn_reco:
        ajouter("M7", "Fenêtres fermées la nuit", fmt(i), f"{vn_reco} ventilation(s) naturelle(s) recommandée(s)",
                A_VERIFIER, "La ventilation naturelle nocturne est recommandée alors que les usagers indiquent que les "
                            "fenêtres ne peuvent pas rester ouvertes la nuit : contrainte d'usage ou de sûreté à lever "
                            "(grilles, ventelles, consignes, alarme).")
    else:
        ajouter("M7", "Fenêtres fermées la nuit", fmt(i), f"{vn_reco} ventilation(s) naturelle(s) recommandée(s)",
                COHERENT, "Pas de contradiction entre l'usage déclaré des fenêtres et la ventilation naturelle préconisée.")

    # M8 : équipements de rafraîchissement déclarés et relevé de visite (BA-01 à BA-05)
    declares = Counter(r.get("Q20") for r in reponses if r.get("Q20") and r.get("Q20") != "Non")
    releve = {k: any(x["etats"].get(k) in moteur.PRESENT for x in res["locaux"]) for k in ("BA-01", "BA-02", "BA-04", "BA-05")}
    correspondance = {"Oui, un ventilateur fixe (plafond, mural)": ("BA-05", "brasseur d'air plafonnier"),
                      "Oui, un ventilateur d'appoint mobile": ("BA-01", "ventilateur sur pied"),
                      "Oui, un climatiseur mobile": ("BA-02", "climatisation mobile"),
                      "Oui, un climatiseur fixe": ("BA-04", "climatisation fixe")}
    if len([r for r in reponses if r.get("Q20")]) < minimum or not res["locaux"]:
        ajouter("M8", "Équipements de rafraîchissement", "—", "relevé BA-01 à BA-05", NON_EVALUABLE,
                "Moins de %d réponses." % minimum if res["locaux"] else "Aucun local dans l'audit.")
    else:
        manquants = [f"{lib} ({n} usager(s))" for eq, n in declares.items() for code, lib in [correspondance[eq]]
                     if not releve[code]]
        ajouter("M8", "Équipements de rafraîchissement", ", ".join(f"{k.removeprefix('Oui, ')} : {v}" for k, v in declares.items()) or "aucun",
                "relevé BA-01 à BA-05", A_VERIFIER if manquants else COHERENT,
                ("Équipement déclaré par les usagers mais relevé dans aucun local : " + ", ".join(manquants) + ".")
                if manquants else "Équipements déclarés cohérents avec le relevé de visite.")

    evalues = [l for l in lignes if l["resultat"] != NON_EVALUABLE]
    a_verifier = [l for l in evalues if l["resultat"] == A_VERIFIER]
    indicateur = (len(evalues) - len(a_verifier)) / len(evalues) if evalues else None
    return {"lignes": lignes, "indicateur": indicateur, "evalues": len(evalues), "a_verifier": len(a_verifier),
            "seuil": seuil, "minimum": minimum, "synthese": syn}
