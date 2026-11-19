"""Exemple pédagogique : groupe scolaire type du Sud de la France (≈ 1 000 m², 1972, R+1).

Données fictives, construites pour illustrer les règles de la méthode sur des cas réalistes :
classes sud traversantes ou mono-orientées, salle de motricité ouest, dortoir est, bureau dense,
bibliothèque sous toiture avec fenêtres de toit, cour avec préau métallique.

``python -m surya.exemple_ecole_sud`` écrit ``surya/exemple_ecole_sud.json``.
"""
import json
from pathlib import Path

LED_NON = "Non LED (tubes fluorescents, halogène, incandescence)"
DALLE = "Sous-face de dalle ou de plancher béton apparente"
FAUX_PLAFOND = "Faux plafond démontable (dalles sur ossature)"


def mur(orientation, baies, position="Nu intérieur", retrait=20, etat="Bon état", debord="Aucun"):
    m = {"orientation": orientation, "MEX-04": position, "MEX-06": etat, "MEX-07": debord, "baies": baies}
    if position in ("Nu intérieur", "En tunnel"):
        m["MEX-05"] = retrait
    return m


COMMUN = {"L-10": ["Aucun"], "L-11": "Oui", "MEX-14": "Non", "MEX-25": "Non", "MEX-26": "Maçonnerie",
          "MEX-32": "Aucun", "MEX-36": ["Aucun"], "MEX-37": "Non", "PL-05": "Béton", "BA-01": "Aucun",
          "BA-02": "Aucun", "BA-04": "Aucun", "BA-05": "Aucun", "BA-19": ["Aucun"]}

ECOLE = {
    "audit": {"etablissement": "Groupe scolaire Les Pins (exemple)", "adresse": "12 avenue du Midi",
              "commune": "Commune du Sud (fictive)", "moa": "Ville (fictive)", "auditeur": "Auditeur SURYA",
              "date_visite": "15/06/2026",
              "synthese": "Bâtiment de 1972 en maçonnerie, R+1, toiture-terrasse peu isolée. Les classes au sud "
                          "surchauffent dès la fin de matinée ; la cour manque d'ombre."},
    "batiment": {"B-01": "De 1948 à 1974", "B-03": "Maçonnerie", "B-04": "ITI (isolation par l'intérieur)",
                 "B-05": "Non", "B-06": "Non", "B-07": "Non", "B-08": "Oui", "B-09": "Non",
                 "B-18": "Toiture-terrasse", "B-19": "Isolée", "B-20": 8, "B-21": "Non"},
    "facades": {
        "S": {"F-01": True, "F-02": "Non", "F-03": "Oui", "F-04": "Non", "F-05": "Non"},
        "N": {"F-01": True, "F-02": "Oui", "F-03": "Oui", "F-04": "Non", "F-05": "Non"},
        "E": {"F-01": True, "F-02": "Non", "F-03": "Oui", "F-04": "Oui", "F-05": "Non"},
        "O": {"F-01": True, "F-02": "Non", "F-03": "Non", "F-04": "Non", "F-05": "Non"},
    },
    "locaux": [
        dict(COMMUN, **{
            "L-01": "Classe CP (RDC, traversante)", "L-02": "Classe", "L-03": 58, "L-04": 25, "L-09": "RDC",
            "MEX-29": ["Volets roulants"], "MEX-30": "Oui (lames ajourables, toile ajourée)", "MEX-34": "Non",
            "MEX-36": ["Grilles"], "PL-01": DALLE, "PL-03": 3.0, "ECL-01": LED_NON,
            "ECL-02": ["En saillie au plafond (plafonnier, réglette, hublot)"],
            "murs": [mur("S", {"Fenêtre à la française": 4}, debord="Faible"),
                     mur("N", {"Fenêtre à la française": 2}, retrait=18)],
            "observations": "Volets roulants ajourés côté sud, utilisés l'après-midi."}),
        dict(COMMUN, **{
            "L-01": "Classe CM2 (étage, sud)", "L-02": "Classe", "L-03": 56, "L-04": 28, "L-09": "Dernier niveau",
            "MEX-29": ["Stores"], "MEX-30": "Non (pleins)", "MEX-34": "Oui",
            "MEX-35": "Non, porte coupe-feu ou à fermeture automatique",
            "PL-01": FAUX_PLAFOND, "PL-02": 0.4, "PL-03": 2.5, "ECL-01": "LED",
            "ECL-02": ["Encastré dans le faux plafond (dalle, spot)"],
            "murs": [mur("S", {"Fenêtre oscillo-battante": 4}, position="Nu extérieur")],
            "observations": "Stores extérieurs pleins : la classe est plongée dans le noir quand ils sont baissés."}),
        dict(COMMUN, **{
            "L-01": "Salle de motricité (ouest)", "L-02": "Salle de motricité, de sport ou d'activité physique",
            "L-03": 120, "L-04": 30, "L-09": "RDC et dernier niveau (plain-pied)", "MEX-29": ["Aucune"],
            "MEX-34": "Non", "PL-01": DALLE, "PL-03": 4.2, "ECL-01": LED_NON,
            "ECL-02": ["Suspendu"], "BA-05": "Présent, hors service", "BA-06": 2, "BA-09": 140, "BA-11": "Oui",
            "BA-12": 340, "BA-13": 250, "BA-14": 500,
            "murs": [mur("O", {"Vitrage fixe": 6, "Porte extérieure": 1}, retrait=25)]}),
        dict(COMMUN, **{
            "L-01": "Dortoir maternelle (est)", "L-02": "Dortoir ou salle de repos", "L-03": 45, "L-04": 20,
            "L-09": "RDC", "MEX-29": ["Aucune"], "MEX-34": "Non", "MEX-37": "Oui", "PL-01": DALLE, "PL-03": 2.8,
            "ECL-01": "LED", "ECL-02": ["En saillie au plafond (plafonnier, réglette, hublot)"],
            "murs": [mur("E", {"Fenêtre à la française": 3}, retrait=14)]}),
        dict(COMMUN, **{
            "L-01": "Bureau de direction", "L-02": "Bureau, salle des maîtres, salle de réunion", "L-03": 14,
            "L-04": 3, "L-09": "RDC", "L-10": ["Copieurs, imprimantes"], "L-11": "Non", "MEX-29": ["Volets battants"],
            "MEX-34": "Non", "PL-01": DALLE, "PL-03": 2.7, "ECL-01": "Mixte (LED et non LED)",
            "ECL-02": ["En saillie au plafond (plafonnier, réglette, hublot)"],
            "murs": [mur("N", {"Fenêtre à la française": 1}, retrait=18)]}),
        dict(COMMUN, **{
            "L-01": "Bibliothèque BCD (étage)", "L-02": "BCD", "L-03": 60, "L-04": 25, "L-09": "Dernier niveau",
            "MEX-14": "Oui", "MEX-15": ["Fenêtre de toit (type Velux)"], "MEX-16": "Oui", "MEX-17": "Électrique",
            "MEX-18": ["Volet extérieur"], "MEX-19": "Bon état", "MEX-20": "Marque et modèle identifiables",
            "MEX-21": "Non", "MEX-29": ["Aucune"], "MEX-34": "Non", "PL-01": DALLE, "PL-03": 2.9, "ECL-01": "LED",
            "ECL-02": ["En saillie au plafond (plafonnier, réglette, hublot)"],
            "murs": [mur("E", {"Fenêtre à la française": 2}, retrait=20, debord="Faible"),
                     mur("O", {"Fenêtre à la française": 2}, retrait=20)]}),
    ],
    "espaces": [
        {"E-01": "Cour élémentaire et préau", "E-02": ["Cour de récréation", "Préau"], "E-04": ["Élémentaire"],
         "E-06": 150, "E-09": "Entre 0 et 25 %", "E-10": ["Arbres", "Préau, auvent"], "E-11": 2, "E-12": "Bon",
         "E-14": 80, "E-15": "Aucune structure", "E-16": "Oui", "E-17": "Non", "E-19": "Non", "E-20": ["S"],
         "E-21": "Aucune", "E-22": "Béton ou maçonnerie pleine", "E-23": "Non",
         "E-24": "Mâts, poteaux ou élément solide existants (mur, préau, bâtiment voisin)", "E-25": "Oui",
         "E-26": "Bac acier ou tôle, non isolé", "E-28": "Foncée", "E-29": 2.8, "E-30": 1, "E-31": "Non",
         "E-32": "Pleine terre ou sol fondable",
         "observations": "Préau métallique bas, très chaud l'après-midi ; deux platanes en bord de cour."},
    ],
    "parametres": {},
}

if __name__ == "__main__":
    out = Path(__file__).with_name("exemple_ecole_sud.json")
    out.write_text(json.dumps(ECOLE, ensure_ascii=False, indent=1), encoding="utf-8")
    print("écrit", out)
