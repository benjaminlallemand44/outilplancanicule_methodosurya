"""Matrice de couverture des règles par les cas écrits à la main (partie B).

Usage : python tests/couverture_regles.py   → tableau Markdown (règle, statut, cas qui la retiennent).
Une règle est « couverte » quand au moins un cas la retient avec une donnée complète ; les alertes
sont couvertes par les tests ``test_alertes_*``.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cas_base import donnees, evaluer, moteur  # noqa: E402
import test_cas_limites as L  # noqa: E402
import test_regles_methode as M  # noqa: E402

ALERTES = {
    "BR-AL": "BR-AL toujours ; même si non recommandé", "VN-AL1": "VN-AL1 sans grilles / aucun / pas si VN NR / ventelles",
    "VN-AL2": "VN-AL2 si VN recommandé", "FT-AL": "FT-AL ouvrante / fixe", "VV-AL": "VV-AL véranda / verrière",
    "EX-AL": "13 bornes EX-AL + 3 cas pile 0,8 (ANO-01)", "OA-AL1": "test_oa_al1_mutualisation (5 cas)",
    "OA-AL2": "OA recommandé / sous réserve / à optimiser / NR", "OA-AL3": "idem OA-AL2",
    "PR-AL1": "PR-AL1 patrimoine", "PR-AL2": "PR-AL2 préau à optimiser",
    "PR-AL3": "fibrociment 1975-1997 / après 1997 / date inconnue", "PR-AL4": "EX-AL avec et sans préau",
}


def couverture():
    cas = defaultdict(list)
    for source, liste in (("règle", M.CAS), ("borne", L.BORNES), ("priorité", L.PRIORITES)):
        for p in liste:
            if source == "règle":
                bloc, regle, statut, bat, fac, local, espace, param = p.values
                kw = dict(bat=bat, fac=fac, local=local, espace=espace, param=param)
            else:
                bloc, attendu, kw = p.values
            r, s, manquante, _ = evaluer(donnees(**kw), bloc)
            if r and not manquante:
                cas[r].append(f"{source} : {p.id}")
    return cas


def markdown() -> str:
    cas = couverture()
    lignes = ["| Règle | Statut | Couverte | Cas (nombre et exemples) |", "|---|---|---|---|"]
    for code, r in moteur.REGLES.items():
        if r["alerte"]:
            lignes.append(f"| {code} | alerte | oui | {ALERTES.get(code, '—')} |")
            continue
        c = cas.get(code, [])
        note = ""
        if code == "VM-9":
            note = " — jamais retenue : VM-7 indéterminée passe avant (QM-01) ; statut vérifié par test_vm9_…"
        if code == "VM-11":
            note = " — atteinte seulement avec une surface ou une hauteur nulle (ANO-02, QM-01)"
        ok = "oui" if c else ("statut vérifié" if code == "VM-9" else "non")
        exemples = "; ".join(x.split(" : ", 1)[1] for x in c[:3])
        lignes.append(f"| {code} | {r['statut']} | {ok} | {len(c)} : {exemples}{note} |")
    return "\n".join(lignes)


if __name__ == "__main__":
    print(markdown())
