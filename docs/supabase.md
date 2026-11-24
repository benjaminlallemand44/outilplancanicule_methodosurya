# Supabase : comptes, audits enregistrés, questionnaire en ligne, photos

Sans configuration, l'application reste une **maquette** : rien n'est enregistré sur un serveur (export
et import de fichiers). Dès que la section `[supabase]` est renseignée dans les secrets Streamlit, elle
devient un outil multi-auditeurs.

## Ce que fait le branchement

| Fonction | Comportement |
|---|---|
| Comptes | Création de compte et connexion par e-mail et mot de passe (Supabase Auth), sur l'écran de départ. |
| Audits enregistrés | Liste « Vos audits enregistrés » (ouvrir, supprimer) ; **enregistrement automatique à chaque changement d'étape**, et bouton « Enregistrer » dans le menu Réglages. Toute la saisie est une colonne `jsonb`. |
| Questionnaire en ligne | Le lien `?questionnaire=<code>` enregistre chaque réponse, anonyme, dans la base. L'auditeur les récupère dans l'étape Questionnaires usagers (« Récupérer les réponses en ligne »). |
| Photos | Seau de stockage **privé** `photos`, un dossier par audit ; envoyées à l'enregistrement, retéléchargées à l'ouverture de l'audit, supprimées avec lui. |

Code : `surya/supabase.py` (client REST sans SDK, dépôts `DepotAudits`, `DepotReponsesSupabase`,
`DepotPhotos`). Tests : `tests/test_supabase.py`, contre un faux serveur qui reproduit les règles
d'accès (`tests/faux_supabase.py`).

## Sécurité (règles RLS, `supabase/migrations/20261124000000_init.sql`)

- Un auditeur ne voit, ne modifie et ne supprime **que ses audits**, leurs réponses et leurs photos.
- Un usager anonyme peut **seulement déposer** une réponse, et seulement si le code correspond à un
  audit existant dont le questionnaire est **ouvert** et **non expiré** (120 jours après la création).
- **Limite de débit** : 60 réponses par 10 minutes et 2 000 réponses au plus par audit.
- Taille bornée : 20 Ko par réponse, 2 Mo par saisie, 5 Mo par photo (JPEG uniquement).
- La clé utilisée par l'application est la **clé publique** (« publishable ») : ce sont les règles RLS qui
  protègent les données. Aucune clé secrète (`service_role`) n'est nécessaire ni ne doit être configurée.

## Mise en service

1. Créer un projet Supabase, région **eu-west-3 (Paris)** pour l'hébergement des données en France.
2. Appliquer la migration `supabase/migrations/20261124000000_init.sql` (éditeur SQL du tableau de bord,
   ou `supabase db push`).
3. Dans Streamlit Cloud, « Settings → Secrets », coller (voir `.streamlit/secrets.toml.example`) :

   ```toml
   [supabase]
   url = "https://<identifiant-du-projet>.supabase.co"
   cle_publique = "sb_publishable_..."
   ```

4. Dans Supabase, « Authentication → URL configuration » : mettre l'adresse de l'application comme
   « Site URL » (lien de confirmation des e-mails).

## Points à décider avant un usage réel

- **Inscriptions** : ouvertes à tous aujourd'hui. Les restreindre (invitation par l'administrateur, ou
  domaine d'e-mail autorisé) avant de diffuser le lien.
- **Durée de conservation** des audits, des photos et des réponses ; purge automatique à prévoir.
- **Durée d'ouverture** du questionnaire (120 jours par défaut) et possibilité de le clore depuis l'outil.
- **RGPD** : registre de traitement, mention d'information sur le questionnaire, sous-traitant
  (Supabase, hébergement AWS Paris), hébergement de l'application elle-même (Streamlit Community Cloud
  ajoute ses propres traceurs, voir `docs/notice_utilisation.md`).
- **Offre Supabase** : l'offre gratuite met le projet en pause après une semaine sans activité et ne
  comporte pas de sauvegarde à restaurer ; une offre payante est à prévoir pour un usage métier.
