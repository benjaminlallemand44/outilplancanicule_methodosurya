-- Les fonctions de contrôle des règles RLS ne doivent pas être appelables par l'API (/rest/v1/rpc) :
-- elles passent dans un schéma privé, non exposé, et ne restent utilisables que par les politiques.
create schema if not exists prive;
revoke all on schema prive from public;
grant usage on schema prive to anon, authenticated;

alter function public.questionnaire_accepte(text) set schema prive;
alter function public.audit_de_l_utilisateur(text) set schema prive;

revoke all on function prive.questionnaire_accepte(text) from public, anon, authenticated;
revoke all on function prive.audit_de_l_utilisateur(text) from public, anon, authenticated;
grant execute on function prive.questionnaire_accepte(text) to anon, authenticated;
grant execute on function prive.audit_de_l_utilisateur(text) to authenticated;
-- Les politiques existantes suivent la fonction déplacée (elles référencent son OID).
