# Passage à Supabase (étape suivante)

La maquette n'enregistre rien sur un serveur : la saisie de l'audit vit dans la session du
navigateur (export / import JSON) et les réponses usagers sont importées en CSV ou saisies à la main.
Le code est organisé pour brancher Supabase sans toucher au moteur, au questionnaire ni au PDF.

## Ce qui est déjà prêt

| Élément | Où | Rôle |
|---|---|---|
| Saisie de l'audit = un seul dictionnaire JSON | `st.session_state.donnees` | à stocker tel quel dans une colonne `jsonb` |
| Interface de stockage des réponses usagers | `surya/stockage.py` (`DepotReponses`) | `DepotMemoire` aujourd'hui, `DepotSupabase` demain |
| Format d'une réponse usager | `surya/questionnaire.py` (`Q1` à `Q24`) | même format en base, en CSV et dans le formulaire |
| Lien du questionnaire en ligne | `?questionnaire=<code de l'audit>` | identifie l'audit auquel rattacher une réponse |

## Schéma proposé

```sql
create table audits (
  id uuid primary key default gen_random_uuid(),
  code text unique not null,              -- code du lien questionnaire, non devinable
  proprietaire uuid references auth.users not null,
  donnees jsonb not null,                 -- saisie complète de l'audit
  cree_le timestamptz default now(),
  modifie_le timestamptz default now()
);

create table reponses_usagers (
  id uuid primary key default gen_random_uuid(),
  audit_code text not null references audits(code) on delete cascade,
  reponses jsonb not null,                -- {"Q1": "...", "Q11": ["...", "..."], ...}
  recue_le timestamptz default now()
);

alter table audits enable row level security;
alter table reponses_usagers enable row level security;

-- L'auditeur ne voit et ne modifie que ses audits
create policy audits_proprietaire on audits
  for all using (auth.uid() = proprietaire) with check (auth.uid() = proprietaire);

-- Un usager (anonyme) peut déposer une réponse pour un code d'audit existant, sans rien lire
create policy reponses_depot on reponses_usagers
  for insert to anon with check (exists (select 1 from audits a where a.code = audit_code));

-- L'auditeur lit les réponses de ses audits
create policy reponses_lecture on reponses_usagers
  for select using (exists (select 1 from audits a where a.code = audit_code and a.proprietaire = auth.uid()));
```

## Étapes du branchement

1. Créer le projet Supabase et appliquer le schéma ci-dessus.
2. Ajouter l'URL et la clé publique dans les secrets Streamlit (`.streamlit/secrets.toml`, jamais dans
   le dépôt).
3. Écrire `DepotSupabase` (mêmes méthodes que `DepotMemoire`).
4. Ajouter l'authentification de l'auditeur, la liste de ses audits et l'enregistrement automatique.
5. Points à décider avant la mise en production : durée de conservation des réponses, hébergement des
   données (RGPD), anonymat des répondants, limitation du nombre de réponses par lien.
