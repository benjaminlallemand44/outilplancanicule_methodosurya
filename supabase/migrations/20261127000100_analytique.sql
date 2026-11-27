-- Vues d'analyse : les données de tous les comptes, à plat, pour les requêtes et les visualisations.
--
-- Réservées à l'administrateur : schéma « analytique » non exposé par l'API (Data API), aucun droit pour les rôles
-- anon et authenticated. On les lit depuis l'éditeur SQL de Supabase, ou par une connexion directe à la base
-- (Metabase, Power BI, Excel / ODBC, psql) avec un utilisateur en lecture seule (voir docs/base_de_donnees.md).
-- Aucune adresse e-mail dans les vues : l'auditeur est désigné par l'identifiant de son compte.
--
-- Les statuts de faisabilité ne sont pas stockés (ils sont calculés par le moteur Python) : pour les analyser,
-- utiliser scripts/export_analyse.py, qui les recalcule.

create schema if not exists analytique;
revoke all on schema analytique from public, anon, authenticated;

-- Un audit par ligne
create or replace view analytique.audits as
select a.id                                   as audit_id,
       a.proprietaire                         as auditeur_id,
       a.nom,
       a.donnees -> 'audit' ->> 'etablissement' as etablissement,
       a.donnees -> 'audit' ->> 'commune'       as commune,
       a.donnees -> 'audit' ->> 'moa'           as maitre_ouvrage,
       a.donnees -> 'audit' ->> 'date_visite'   as date_visite,
       a.donnees -> 'batiment' ->> 'B-01'       as periode_construction,
       a.donnees -> 'batiment' ->> 'B-03'       as structure,
       jsonb_array_length(coalesce(a.donnees -> 'locaux', '[]'))         as nb_locaux,
       jsonb_array_length(coalesce(a.donnees -> 'espaces', '[]'))        as nb_espaces,
       jsonb_array_length(coalesce(a.donnees -> 'photos', '[]'))         as nb_photos,
       jsonb_array_length(coalesce(a.donnees -> 'questionnaires', '[]')) as nb_questionnaires_saisis,
       (select count(*) from public.reponses_usagers r where r.audit_code = a.code) as nb_reponses_en_ligne,
       coalesce(a.donnees -> 'travaux' -> 'operations', '{}') <> '{}'    as passage_en_travaux,
       coalesce(a.donnees -> 'diagnostic_externe' -> 'operations', '[]') <> '[]' as diagnostic_externe,
       a.questionnaire_ouvert,
       a.questionnaire_expire_le,
       a.cree_le,
       a.modifie_le
from public.audits a
where jsonb_typeof(coalesce(a.donnees -> 'locaux', '[]')) = 'array'
  and jsonb_typeof(coalesce(a.donnees -> 'espaces', '[]')) = 'array';

-- Un local par ligne
create or replace view analytique.locaux as
select a.id as audit_id, l.rang, l.x ->> 'L-01' as nom, l.x ->> 'L-02' as type,
       case when jsonb_typeof(l.x -> 'L-03') = 'number' then (l.x ->> 'L-03')::numeric end as surface_m2,
       case when jsonb_typeof(l.x -> 'L-04') = 'number' then (l.x ->> 'L-04')::numeric end as effectif,
       l.x ->> 'L-09' as niveau,
       jsonb_array_length(case when jsonb_typeof(l.x -> 'murs') = 'array' then l.x -> 'murs' else '[]' end) as nb_murs
from public.audits a
cross join lateral jsonb_array_elements(case when jsonb_typeof(a.donnees -> 'locaux') = 'array'
                                             then a.donnees -> 'locaux' else '[]' end) with ordinality as l(x, rang);

-- Un espace extérieur par ligne
create or replace view analytique.espaces as
select a.id as audit_id, e.rang, e.x ->> 'E-01' as nom, e.x -> 'E-04' as public,
       case when jsonb_typeof(e.x -> 'E-06') = 'number' then (e.x ->> 'E-06')::numeric end as effectif,
       case when jsonb_typeof(e.x -> 'E-14') = 'number' then (e.x ->> 'E-14')::numeric end as ombre_m2
from public.audits a
cross join lateral jsonb_array_elements(case when jsonb_typeof(a.donnees -> 'espaces') = 'array'
                                             then a.donnees -> 'espaces' else '[]' end) with ordinality as e(x, rang);

-- Une réponse au questionnaire en ligne par ligne et par question
create or replace view analytique.reponses_usagers as
select r.id as reponse_id, a.id as audit_id, r.recue_le, q.question, q.valeur
from public.reponses_usagers r
join public.audits a on a.code = r.audit_code
cross join lateral jsonb_each(r.reponses) as q(question, valeur);

-- Comptes : activité, sans adresse e-mail
create or replace view analytique.comptes as
select u.id as auditeur_id, u.created_at as cree_le, u.last_sign_in_at as derniere_connexion,
       (select count(*) from public.audits a where a.proprietaire = u.id) as nb_audits
from auth.users u;

revoke all on all tables in schema analytique from public, anon, authenticated;
