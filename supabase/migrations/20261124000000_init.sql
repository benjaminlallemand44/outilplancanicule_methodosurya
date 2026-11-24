-- Outil d'audit de faisabilité d'actions d'adaptation : schéma initial.
-- Audits des auditeurs (comptes Supabase Auth), réponses au questionnaire usagers, photos.

-- ------------------------------------------------------------------ audits
create table public.audits (
  id uuid primary key default gen_random_uuid(),
  code text not null unique default encode(extensions.gen_random_bytes(8), 'hex'),  -- lien du questionnaire
  proprietaire uuid not null default auth.uid() references auth.users (id) on delete cascade,
  nom text not null default 'Audit sans nom',
  donnees jsonb not null default '{}'::jsonb,               -- saisie complète (format de l'outil)
  questionnaire_ouvert boolean not null default true,
  questionnaire_expire_le timestamptz not null default now() + interval '120 days',
  cree_le timestamptz not null default now(),
  modifie_le timestamptz not null default now(),
  constraint audits_code_format check (code ~ '^[0-9a-f]{10,32}$'),
  constraint audits_taille check (pg_column_size(donnees) < 2000000)
);
create index audits_proprietaire_idx on public.audits (proprietaire, modifie_le desc);

create function public.maj_modifie_le() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.modifie_le := now();
  return new;
end $$;

create trigger audits_modifie_le before update on public.audits
  for each row execute function public.maj_modifie_le();

alter table public.audits enable row level security;

create policy "audits : le propriétaire lit" on public.audits
  for select to authenticated using ((select auth.uid()) = proprietaire);
create policy "audits : le propriétaire crée" on public.audits
  for insert to authenticated with check ((select auth.uid()) = proprietaire);
create policy "audits : le propriétaire modifie" on public.audits
  for update to authenticated using ((select auth.uid()) = proprietaire) with check ((select auth.uid()) = proprietaire);
create policy "audits : le propriétaire supprime" on public.audits
  for delete to authenticated using ((select auth.uid()) = proprietaire);

-- ------------------------------------------------------------------ réponses au questionnaire usagers
create table public.reponses_usagers (
  id uuid primary key default gen_random_uuid(),
  audit_code text not null references public.audits (code) on update cascade on delete cascade,
  reponses jsonb not null,                                  -- {"Q1": "...", "Q11": ["...", "..."], ...}
  recue_le timestamptz not null default now(),
  constraint reponses_objet check (jsonb_typeof(reponses) = 'object'),
  constraint reponses_taille check (pg_column_size(reponses) < 20000)
);
create index reponses_usagers_code_idx on public.reponses_usagers (audit_code, recue_le);

-- Un dépôt anonyme n'est accepté que pour un audit existant, dont le questionnaire est ouvert et non
-- expiré, et dans la limite de 60 réponses par 10 minutes et de 2 000 réponses par audit.
create function public.questionnaire_accepte(p_code text) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
      select 1 from public.audits a
      where a.code = p_code and a.questionnaire_ouvert and a.questionnaire_expire_le > now())
    and (select count(*) from public.reponses_usagers r
         where r.audit_code = p_code and r.recue_le > now() - interval '10 minutes') < 60
    and (select count(*) from public.reponses_usagers r where r.audit_code = p_code) < 2000
$$;
revoke all on function public.questionnaire_accepte(text) from public;
grant execute on function public.questionnaire_accepte(text) to anon, authenticated;

alter table public.reponses_usagers enable row level security;

create policy "réponses : dépôt anonyme sur un questionnaire ouvert" on public.reponses_usagers
  for insert to anon, authenticated with check (public.questionnaire_accepte(audit_code));
create policy "réponses : le propriétaire de l'audit lit" on public.reponses_usagers
  for select to authenticated using (exists (
    select 1 from public.audits a where a.code = audit_code and a.proprietaire = (select auth.uid())));
create policy "réponses : le propriétaire de l'audit supprime" on public.reponses_usagers
  for delete to authenticated using (exists (
    select 1 from public.audits a where a.code = audit_code and a.proprietaire = (select auth.uid())));

-- ------------------------------------------------------------------ photos (stockage privé)
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('photos', 'photos', false, 5242880, array['image/jpeg'])
on conflict (id) do nothing;

-- Chemin d'une photo : <id de l'audit>/<id de la photo>.jpg ; seul le propriétaire de l'audit y accède.
create function public.audit_de_l_utilisateur(p_dossier text) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.audits a where a.id::text = p_dossier and a.proprietaire = (select auth.uid()))
$$;
revoke all on function public.audit_de_l_utilisateur(text) from public;
grant execute on function public.audit_de_l_utilisateur(text) to authenticated;

create policy "photos : le propriétaire lit" on storage.objects
  for select to authenticated using (bucket_id = 'photos' and public.audit_de_l_utilisateur((storage.foldername(name))[1]));
create policy "photos : le propriétaire dépose" on storage.objects
  for insert to authenticated with check (bucket_id = 'photos' and public.audit_de_l_utilisateur((storage.foldername(name))[1]));
create policy "photos : le propriétaire remplace" on storage.objects
  for update to authenticated using (bucket_id = 'photos' and public.audit_de_l_utilisateur((storage.foldername(name))[1]));
create policy "photos : le propriétaire supprime" on storage.objects
  for delete to authenticated using (bucket_id = 'photos' and public.audit_de_l_utilisateur((storage.foldername(name))[1]));
