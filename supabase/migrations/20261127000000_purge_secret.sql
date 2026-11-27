-- C2-06 (campagne de tests n° 2) : la fonction purge-conservation n'accepte plus que la tâche planifiée.
--
-- Un secret partagé, tiré au hasard dans la base (il n'apparaît ni dans le dépôt ni ailleurs), est rangé
-- dans le coffre (Vault) sous le nom « purge_secret ». La tâche l'envoie dans l'en-tête x-purge-secret ;
-- la fonction le fait vérifier par la base (verifier_secret_purge, réservée au rôle de service).

select vault.create_secret(encode(extensions.gen_random_bytes(32), 'hex'), 'purge_secret',
                           'Secret partagé entre la tâche planifiée et la fonction purge-conservation')
where not exists (select 1 from vault.secrets where name = 'purge_secret');

create or replace function public.verifier_secret_purge(p_secret text)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (select 1 from vault.decrypted_secrets
                 where name = 'purge_secret' and decrypted_secret = p_secret and p_secret <> '');
$$;
revoke all on function public.verifier_secret_purge(text) from public, anon, authenticated;
grant execute on function public.verifier_secret_purge(text) to service_role;

select cron.schedule(
  'purge-conservation-hebdomadaire',
  '17 3 * * 1',
  $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name = 'purge_url_projet')
           || '/functions/v1/purge-conservation',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets where name = 'purge_cle_anon'),
      'x-purge-secret', (select decrypted_secret from vault.decrypted_secrets where name = 'purge_secret')),
    body := '{}'::jsonb,
    timeout_milliseconds := 60000
  );
  $$
);
