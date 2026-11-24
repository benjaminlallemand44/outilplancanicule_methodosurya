"""Faux serveur Supabase en mémoire (auth, tables, stockage) pour tester ``surya/supabase.py`` et l'app.

Il reproduit les règles d'accès de ``supabase/migrations`` : chaque auditeur ne voit que ses audits,
ses réponses et ses photos ; un dépôt anonyme de réponse n'est accepté que pour un questionnaire
ouvert, non expiré, dans la limite de débit.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import uuid
from urllib.parse import urlparse

CLE = "sb_publishable_test"


class Reponse:
    def __init__(self, statut: int, corps=None, brut: bytes | None = None):
        self.status_code = statut
        self.content = brut if brut is not None else (b"" if corps is None else json.dumps(corps).encode())

    def json(self):
        return json.loads(self.content)


class FauxSupabase:
    def __init__(self):
        self.comptes = {}        # email -> {id, mdp, confirme}
        self.jetons = {}         # jeton -> id utilisateur
        self.audits = []
        self.reponses = []
        self.objets = {}         # chemin -> bytes
        self.confirmation = False  # True : l'inscription demande une confirmation par e-mail
        self.appels = []

    # ------------------------------------------------------------ « requests.Session »
    def request(self, methode, url, params=None, json=None, data=None, headers=None, timeout=None):
        chemin = urlparse(url).path
        params = params or {}
        self.appels.append((methode, chemin))
        assert headers.get("apikey") == CLE
        jeton = headers.get("Authorization", "").removeprefix("Bearer ")
        uid = self.jetons.get(jeton)
        if chemin.startswith("/auth/v1/"):
            return self._auth(chemin, params, json, jeton)
        if chemin == "/rest/v1/audits":
            return self._audits(methode, params, json, uid)
        if chemin == "/rest/v1/reponses_usagers":
            return self._reponses(methode, params, json, uid)
        if chemin.startswith("/storage/v1/object"):
            return self._stockage(methode, chemin, json, data, uid)
        return Reponse(404, {"message": "inconnu"})

    # ------------------------------------------------------------ auth
    def _session(self, email):
        j = uuid.uuid4().hex
        self.jetons[j] = self.comptes[email]["id"]
        return {"access_token": j, "refresh_token": "r" + j, "expires_in": 3600,
                "user": {"id": self.comptes[email]["id"], "email": email}}

    def _auth(self, chemin, params, corps, jeton):
        if chemin == "/auth/v1/signup":
            if corps["email"] in self.comptes:
                return Reponse(422, {"error_code": "user_already_exists"})
            if len(corps["password"]) < 8:
                return Reponse(422, {"error_code": "weak_password"})
            self.comptes[corps["email"]] = {"id": str(uuid.uuid4()), "mdp": corps["password"],
                                            "confirme": not self.confirmation}
            if self.confirmation:
                return Reponse(200, {"id": self.comptes[corps["email"]]["id"]})
            return Reponse(200, self._session(corps["email"]))
        if chemin == "/auth/v1/token" and params.get("grant_type") == "password":
            c = self.comptes.get(corps["email"])
            if not c or c["mdp"] != corps["password"]:
                return Reponse(400, {"error_code": "invalid_credentials"})
            if not c["confirme"]:
                return Reponse(400, {"error_code": "email_not_confirmed"})
            return Reponse(200, self._session(corps["email"]))
        if chemin == "/auth/v1/logout":
            self.jetons.pop(jeton, None)
            return Reponse(204)
        return Reponse(400, {"msg": "requête d'authentification inconnue"})

    # ------------------------------------------------------------ tables
    @staticmethod
    def _filtre(lignes, params):
        for k, v in params.items():
            if isinstance(v, str) and v.startswith("eq."):
                lignes = [l for l in lignes if str(l.get(k)) == v[3:]]
        return lignes

    @staticmethod
    def _select(lignes, params):
        champs = params.get("select", "*")
        if champs == "*":
            return [copy.deepcopy(l) for l in lignes]
        return [{c: copy.deepcopy(l.get(c)) for c in champs.split(",")} for l in lignes]

    def _audits(self, methode, params, corps, uid):
        if uid is None:  # RLS : réservé aux utilisateurs connectés
            return Reponse(200, []) if methode == "GET" else Reponse(401, {"message": "JWT manquant"})
        miennes = [a for a in self.audits if a["proprietaire"] == uid]
        maintenant = dt.datetime.now(dt.timezone.utc).isoformat()
        if methode == "GET":
            lignes = sorted(self._filtre(miennes, params), key=lambda a: a["modifie_le"], reverse=True)
            return Reponse(200, self._select(lignes, params))
        if methode == "POST":
            code = corps.get("code") or uuid.uuid4().hex[:16]
            if any(a["code"] == code for a in self.audits):
                return Reponse(409, {"code": "23505", "message": "code déjà utilisé"})
            a = {"id": str(uuid.uuid4()), "code": code, "proprietaire": uid, "nom": corps.get("nom", "Audit sans nom"),
                 "donnees": copy.deepcopy(corps["donnees"]), "questionnaire_ouvert": True,
                 "questionnaire_expire_le": dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=120),
                 "cree_le": maintenant, "modifie_le": maintenant}
            self.audits.append(a)
            return Reponse(201, self._select([a], params))
        if methode == "PATCH":
            lignes = self._filtre(miennes, params)
            for a in lignes:
                a.update(copy.deepcopy(corps))
                a["modifie_le"] = maintenant
            return Reponse(200, self._select(lignes, params))
        if methode == "DELETE":
            for a in self._filtre(miennes, params):
                self.audits.remove(a)
                self.reponses = [r for r in self.reponses if r["audit_code"] != a["code"]]
            return Reponse(204)
        return Reponse(405)

    def accepte(self, code) -> bool:
        a = next((a for a in self.audits if a["code"] == code), None)
        if not a or not a["questionnaire_ouvert"] or a["questionnaire_expire_le"] < dt.datetime.now(dt.timezone.utc):
            return False
        recentes = [r for r in self.reponses if r["audit_code"] == code
                    and r["recue_le"] > dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=10)]
        return len(recentes) < 60 and len([r for r in self.reponses if r["audit_code"] == code]) < 2000

    def _reponses(self, methode, params, corps, uid):
        codes = {a["code"] for a in self.audits if a["proprietaire"] == uid}
        if methode == "POST":
            if not self.accepte(corps["audit_code"]):
                return Reponse(401 if uid is None else 403, {"code": "42501", "message": "row-level security"})
            self.reponses.append({"id": str(uuid.uuid4()), "audit_code": corps["audit_code"],
                                  "reponses": copy.deepcopy(corps["reponses"]),
                                  "recue_le": dt.datetime.now(dt.timezone.utc)})
            return Reponse(201)
        lignes = self._filtre([r for r in self.reponses if r["audit_code"] in codes], params)
        if methode == "GET":
            return Reponse(200, [dict(self._select([r], params)[0], recue_le=r["recue_le"].isoformat())
                                 if "recue_le" in params.get("select", "") else self._select([r], params)[0]
                                 for r in lignes])
        if methode == "DELETE":
            for r in lignes:
                self.reponses.remove(r)
            return Reponse(204)
        return Reponse(405)

    # ------------------------------------------------------------ stockage
    def _dossier_autorise(self, uid, chemin_objet):
        dossier = chemin_objet.split("/")[0]
        return any(a["id"] == dossier and a["proprietaire"] == uid for a in self.audits)

    def _stockage(self, methode, chemin, corps, data, uid):
        if uid is None:
            return Reponse(400, {"error": "Unauthorized", "message": "Invalid JWT"})
        if methode == "DELETE" and chemin == "/storage/v1/object/photos":
            for c in corps["prefixes"]:
                if self._dossier_autorise(uid, c):
                    self.objets.pop(c, None)
            return Reponse(200, [])
        objet = chemin.removeprefix("/storage/v1/object/authenticated/photos/").removeprefix("/storage/v1/object/photos/")
        if not self._dossier_autorise(uid, objet):
            return Reponse(403, {"error": "Unauthorized", "message": "new row violates row-level security policy"})
        if methode == "POST":
            self.objets[objet] = bytes(data)
            return Reponse(200, {"Key": f"photos/{objet}"})
        if methode == "GET":
            if objet not in self.objets:
                return Reponse(404, {"error": "not_found", "message": "Object not found"})
            return Reponse(200, brut=self.objets[objet])
        return Reponse(405)
