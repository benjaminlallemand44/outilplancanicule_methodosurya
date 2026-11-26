-- Conservation des données (décision du 26/11/2026, voir docs/supabase.md).
-- Purge hebdomadaire par la fonction purge-conservation (supabase/functions/purge-conservation) :
-- audits et photos 3 ans après la dernière modification, réponses brutes 12 mois, comptes inactifs 3 ans.
-- Questionnaire en ligne ouvert 90 jours.

-- Questionnaire : 90 jours au lieu de 120 (audits existants alignés sur leur date de création)
alter table public.audits alter column questionnaire_expire_le set default now() + interval '90 days';
update public.audits set questionnaire_expire_le = cree_le + interval '90 days'
  where questionnaire_expire_le > cree_le + interval '90 days';

-- Tâche planifiée : chaque lundi à 3 h 17 (UTC), appel de la fonction de purge.
-- L'adresse du projet et la clé publique sont lues dans le coffre (Vault), créés hors du dépôt :
--   select vault.create_secret('<clé anon>', 'purge_cle_anon');
--   select vault.create_secret('https://<projet>.supabase.co', 'purge_url_projet');
create extension if not exists pg_cron;
create extension if not exists pg_net with schema extensions;

select cron.schedule(
  'purge-conservation-hebdomadaire',
  '17 3 * * 1',
  $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name = 'purge_url_projet')
           || '/functions/v1/purge-conservation',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets where name = 'purge_cle_anon')),
    body := '{}'::jsonb,
    timeout_milliseconds := 60000
  );
  $$
);
