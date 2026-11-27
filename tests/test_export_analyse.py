"""Export des données de tous les comptes pour l'analyse (scripts/export_analyse.py)."""
import csv
import json
import sys

from cas_base import RACINE

sys.path.insert(0, str(RACINE / "scripts"))
import export_analyse as EX  # noqa: E402
from surya import moteur  # noqa: E402

ECOLE = json.loads((RACINE / "surya" / "exemple_ecole_sud.json").read_text(encoding="utf-8"))


def test_tables_a_plat_et_statuts_recalcules(tmp_path):
    audits = [{"id": "a1", "code": "c1", "proprietaire": "u1", "nom": "École A", "donnees": ECOLE},
              {"id": "a2", "code": "c2", "proprietaire": "u2", "nom": "Audit sans nom", "donnees": {}},
              {"id": "a3", "code": "c3", "proprietaire": "u1", "nom": "abîmé", "donnees": {"locaux": "x"}}]
    reponses = [{"id": "r1", "audit_code": "c1", "reponses": {"Q4": "Chaud", "Q11": ["a", "b"]}, "recue_le": "2026"}]
    t = EX.lignes(audits, reponses)
    assert [a["auditeur"] for a in t["audits"]] == ["auditeur_1", "auditeur_2", "auditeur_1"]  # pas d'e-mail
    assert len([x for x in t["lieux"] if x["audit_id"] == "a1"]) == len(ECOLE["locaux"]) + len(ECOLE["espaces"])
    res = moteur.calculer(ECOLE)
    attendu = [s["statut"] for x in res["locaux"] + res["espaces"] for s in x["solutions"]]
    assert [s["statut"] for s in t["statuts"] if s["audit_id"] == "a1"] == attendu
    assert t["reponses_usagers"] == [{"reponse_id": "r1", "audit_id": "a1", "recue_le": "2026", "Q4": "Chaud",
                                      "Q11": "a | b"}]
    fichiers = EX.ecrire(t, tmp_path)
    with (tmp_path / "statuts.csv").open(encoding="utf-8-sig") as f:
        assert len(list(csv.DictReader(f, delimiter=";"))) == len(t["statuts"])
    assert {f.name for f in fichiers} == {"audits.csv", "lieux.csv", "statuts.csv", "reponses_usagers.csv"}
