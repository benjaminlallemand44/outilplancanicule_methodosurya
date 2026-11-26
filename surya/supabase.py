"""Branchement Supabase : comptes des auditeurs, audits enregistrés, réponses usagers, photos.

Client REST minimal (``requests``), sans le SDK : authentification (GoTrue), tables (PostgREST) et
fichiers (Storage). Le schéma et les règles d'accès sont dans ``supabase/migrations``.

* ``Supabase(url, cle_publique)`` : une connexion par session Streamlit ; ``connexion`` /
  ``inscription`` / ``deconnexion`` ; le jeton est rafraîchi automatiquement.
* ``DepotAudits`` : liste, ouverture, enregistrement, suppression des audits de l'auditeur connecté.
* ``DepotReponsesSupabase`` : même interface que ``stockage.DepotMemoire`` ; le dépôt d'une réponse
  fonctionne sans compte (questionnaire en ligne), la lecture est réservée au propriétaire de l'audit.
* ``DepotPhotos`` : photos rangées dans le seau privé ``photos``, un dossier par audit.

La clé publique (« publishable » ou « anon ») peut figurer côté client : ce sont les règles RLS qui
protègent les données. Elle se configure dans les secrets Streamlit (jamais dans le dépôt) :

    [supabase]
    url = "https://<projet>.supabase.co"
    cle_publique = "sb_publishable_..."
"""
from __future__ import annotations

import time

import requests


class ErreurSupabase(Exception):
    """Erreur renvoyée par Supabase, avec un message lisible pour l'utilisateur."""

    def __init__(self, message: str, statut: int | None = None):
        super().__init__(message)
        self.statut = statut


MESSAGES_AUTH = {
    "invalid_credentials": "Adresse e-mail ou mot de passe incorrect.",
    "email_not_confirmed": "Adresse e-mail non confirmée : cliquez sur le lien reçu par e-mail.",
    "user_already_exists": "Un compte existe déjà avec cette adresse.",
    "weak_password": "Mot de passe trop faible (8 caractères au moins).",
    "over_email_send_rate_limit": "Trop de demandes : réessayez dans quelques minutes.",
}


class Supabase:
    def __init__(self, url: str, cle_publique: str, session: requests.Session | None = None, delai: float = 15):
        self.url = url.rstrip("/")
        self.cle = cle_publique
        self.http = session or requests.Session()
        self.delai = delai
        self.jeton = self.jeton_rafraichissement = None
        self.expire = 0.0
        self.utilisateur: dict | None = None

    # ------------------------------------------------------------ authentification
    @property
    def connecte(self) -> bool:
        return self.jeton is not None

    def _session(self, r: dict):
        self.jeton = r["access_token"]
        self.jeton_rafraichissement = r.get("refresh_token")
        self.expire = time.time() + float(r.get("expires_in", 3600)) - 60
        self.utilisateur = r.get("user") or self.utilisateur

    def connexion(self, email: str, mot_de_passe: str) -> dict:
        r = self._requete("POST", "/auth/v1/token", params={"grant_type": "password"},
                          json={"email": email, "password": mot_de_passe}, auth=False)
        self._session(r)
        return self.utilisateur

    def inscription(self, email: str, mot_de_passe: str) -> bool:
        """Crée le compte ; renvoie True si une confirmation par e-mail est demandée."""
        r = self._requete("POST", "/auth/v1/signup", json={"email": email, "password": mot_de_passe}, auth=False)
        if r.get("access_token"):
            self._session(r)
            return False
        return True

    def deconnexion(self):
        if self.jeton:
            try:
                self._requete("POST", "/auth/v1/logout", attendu=(204, 200, 401))
            except ErreurSupabase:
                pass
        self.jeton = self.jeton_rafraichissement = self.utilisateur = None

    def _rafraichir(self):
        r = self._requete("POST", "/auth/v1/token", params={"grant_type": "refresh_token"},
                          json={"refresh_token": self.jeton_rafraichissement}, auth=False)
        self._session(r)

    @property
    def id_utilisateur(self) -> str | None:
        return (self.utilisateur or {}).get("id")

    # ------------------------------------------------------------ requêtes
    def _entetes(self, auth: bool) -> dict:
        if auth and self.jeton and time.time() > self.expire and self.jeton_rafraichissement:
            self._rafraichir()
        jeton = self.jeton if (auth and self.jeton) else self.cle
        return {"apikey": self.cle, "Authorization": f"Bearer {jeton}"}

    def _requete(self, methode, chemin, params=None, json=None, data=None, entetes=None, auth=True,
                 attendu=(200, 201, 204), brut=False):
        h = self._entetes(auth)
        h.update(entetes or {})
        try:
            rep = self.http.request(methode, self.url + chemin, params=params, json=json, data=data, headers=h,
                                    timeout=self.delai)
        except requests.RequestException as e:
            raise ErreurSupabase("Base de données injoignable : vérifiez la connexion internet.") from e
        if rep.status_code not in attendu:
            raise ErreurSupabase(self._message(rep), rep.status_code)
        if brut:
            return rep.content
        if not rep.content:
            return None
        try:
            return rep.json()
        except ValueError:
            return None

    @staticmethod
    def _message(rep) -> str:
        try:
            corps = rep.json()
        except ValueError:
            corps = {}
        code = corps.get("error_code") or corps.get("code") or corps.get("error")
        if code in MESSAGES_AUTH:
            return MESSAGES_AUTH[code]
        if rep.status_code in (401, 403) or code == "42501":
            return "Accès refusé."
        return corps.get("msg") or corps.get("message") or corps.get("error_description") or f"Erreur {rep.status_code}."


# ------------------------------------------------------------ audits
class DepotAudits:
    CHAMPS = "id,code,nom,modifie_le"

    def __init__(self, sb: Supabase):
        self.sb = sb

    def lister(self) -> list[dict]:
        return self.sb._requete("GET", "/rest/v1/audits", params={"select": self.CHAMPS, "order": "modifie_le.desc"})

    def ouvrir(self, id_audit: str) -> dict:
        r = self.sb._requete("GET", "/rest/v1/audits", params={"select": "id,code,nom,donnees", "id": f"eq.{id_audit}"})
        if not r:
            raise ErreurSupabase("Audit introuvable.", 404)
        return r[0]

    def enregistrer(self, donnees: dict, id_audit: str | None = None) -> dict:
        """Crée (``id_audit`` absent) ou met à jour l'audit ; renvoie {id, code, nom, modifie_le}."""
        audit = donnees.get("audit") or {}
        ligne = {"donnees": donnees, "nom": audit.get("etablissement") or "Audit sans nom"}
        if audit.get("code"):
            ligne["code"] = audit["code"]
        prefer = {"Prefer": "return=representation"}
        if id_audit:
            r = self.sb._requete("PATCH", "/rest/v1/audits", params={"id": f"eq.{id_audit}", "select": self.CHAMPS},
                                 json=ligne, entetes=prefer)
        else:
            r = self.sb._requete("POST", "/rest/v1/audits", params={"select": self.CHAMPS}, json=ligne, entetes=prefer)
        if not r:
            raise ErreurSupabase("Enregistrement refusé.", 403)
        return r[0]

    def supprimer(self, id_audit: str):
        self.sb._requete("DELETE", "/rest/v1/audits", params={"id": f"eq.{id_audit}"})


# ------------------------------------------------------------ réponses usagers
class DepotReponsesSupabase:
    """Même interface que ``stockage.DepotMemoire``."""

    def __init__(self, sb: Supabase):
        self.sb = sb

    def ajouter(self, code_audit: str, reponse: dict) -> dict:
        r = {k: v for k, v in reponse.items() if v not in (None, "", []) and k != "_id"}
        try:
            self.sb._requete("POST", "/rest/v1/reponses_usagers", json={"audit_code": code_audit, "reponses": r},
                             entetes={"Prefer": "return=minimal"})
        except ErreurSupabase as e:
            if e.statut in (401, 403):
                raise ErreurSupabase("Ce lien de questionnaire n'est pas valide, est clos ou a expiré.", e.statut) from e
            raise
        return r

    def lister(self, code_audit: str) -> list[dict]:
        lignes = self.sb._requete("GET", "/rest/v1/reponses_usagers",
                                  params={"select": "id,reponses,recue_le", "audit_code": f"eq.{code_audit}",
                                          "order": "recue_le.asc"}) or []
        return [dict(l["reponses"], _id=l["id"], source=l["reponses"].get("source", "en ligne"),
                     horodatage=(l.get("recue_le") or "")[:16].replace("T", " ")) for l in lignes]

    def supprimer(self, code_audit: str, id_reponse: str) -> None:
        self.sb._requete("DELETE", "/rest/v1/reponses_usagers", params={"id": f"eq.{id_reponse}"})

    def vider(self, code_audit: str) -> None:
        self.sb._requete("DELETE", "/rest/v1/reponses_usagers", params={"audit_code": f"eq.{code_audit}"})


# ------------------------------------------------------------ photos
class DepotPhotos:
    SEAU = "photos"

    def __init__(self, sb: Supabase):
        self.sb = sb

    def chemin(self, id_audit: str, id_photo: str) -> str:
        return f"{id_audit}/{id_photo}.jpg"

    def envoyer(self, id_audit: str, id_photo: str, contenu: bytes):
        self.sb._requete("POST", f"/storage/v1/object/{self.SEAU}/{self.chemin(id_audit, id_photo)}", data=contenu,
                         entetes={"Content-Type": "image/jpeg", "x-upsert": "true"})

    def telecharger(self, id_audit: str, id_photo: str) -> bytes:
        return self.sb._requete("GET", f"/storage/v1/object/authenticated/{self.SEAU}/{self.chemin(id_audit, id_photo)}",
                                brut=True)

    def supprimer(self, id_audit: str, ids_photos: list[str]):
        if ids_photos:
            self.sb._requete("DELETE", f"/storage/v1/object/{self.SEAU}",
                             json={"prefixes": [self.chemin(id_audit, i) for i in ids_photos]})


def synchroniser_photos(depot: DepotPhotos, id_audit: str, donnees: dict, contenus: dict[str, bytes],
                        supprimees: list[str]) -> int:
    """Envoie les photos pas encore envoyées, supprime celles retirées ; renvoie le nombre envoyé."""
    n = 0
    for ph in donnees.get("photos") or []:
        if not ph.get("envoyee") and ph["id"] in contenus:
            depot.envoyer(id_audit, ph["id"], contenus[ph["id"]])
            ph["envoyee"] = True
            n += 1
    if supprimees:
        depot.supprimer(id_audit, list(supprimees))
        supprimees.clear()
    return n


# Durées de conservation (décision du 26/11/2026), appliquées chaque semaine par la fonction
# supabase/functions/purge-conservation : audits et photos 3 ans après la dernière modification,
# réponses brutes 12 mois, comptes inactifs 3 ans. Questionnaire ouvert 90 jours.
CONSERVATION_AUDIT_JOURS = 3 * 365
RAPPEL_AVANT_SUPPRESSION_JOURS = 30


def filtrer_audits(audits: list[dict], recherche: str) -> list[dict]:
    """Audits dont le nom ou le code contient tous les mots cherchés (sans tenir compte des accents ni de la casse)."""
    import unicodedata

    def simple(t: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", t or "").lower() if unicodedata.category(c) != "Mn")

    mots = simple(recherche).split()
    return [a for a in audits if all(m in simple(f"{a.get('nom', '')} {a.get('code', '')}") for m in mots)]


def suppression_prevue(modifie_le: str, aujourd_hui=None) -> tuple[str, bool]:
    """(date de suppression « jj/mm/aaaa », True si elle tombe dans le mois) pour un audit."""
    import datetime as dt
    try:
        modif = dt.datetime.fromisoformat(str(modifie_le).replace("Z", "+00:00"))
    except ValueError:
        return "", False
    fin = modif + dt.timedelta(days=CONSERVATION_AUDIT_JOURS)
    jour = aujourd_hui or dt.datetime.now(tz=fin.tzinfo)
    return fin.strftime("%d/%m/%Y"), (fin - jour) <= dt.timedelta(days=RAPPEL_AVANT_SUPPRESSION_JOURS)


def configuration(secrets) -> tuple[str, str] | None:
    """(url, clé publique) lus dans les secrets Streamlit, ou None (mode maquette)."""
    try:
        s = secrets["supabase"]
        url, cle = s.get("url"), s.get("cle_publique")
    except Exception:
        return None
    return (url, cle) if url and cle else None
