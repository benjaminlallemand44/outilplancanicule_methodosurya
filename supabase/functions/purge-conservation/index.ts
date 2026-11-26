// Purge hebdomadaire des données arrivées au terme de leur durée de conservation.
//
// Durées (décision du 26/11/2026, voir docs/supabase.md) :
// - audits et leurs photos : 3 ans après la dernière modification (ouvrir un audit le met à jour) ;
// - réponses brutes au questionnaire usagers : 12 mois après réception (une copie récupérée par
//   l'auditeur vit dans l'audit et suit sa durée) ;
// - comptes inactifs : 3 ans sans connexion, avec leurs audits et leurs photos.
// Le questionnaire en ligne reste ouvert 90 jours (valeur par défaut de la table audits).
//
// Appelée chaque semaine par pg_cron (migration 20261126000000_conservation.sql). Elle ne supprime que
// des données expirées : un appel de plus ne fait rien de plus.
import { createClient } from "npm:@supabase/supabase-js@2.49.4";

const AN = 365 * 24 * 3600 * 1000;

Deno.serve(async () => {
  const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const maintenant = Date.now();
  const limite3ans = new Date(maintenant - 3 * AN).toISOString();
  const limite12mois = new Date(maintenant - AN).toISOString();
  const bilan = { audits: 0, photos: 0, reponses: 0, comptes: 0 };

  try {
    // 1. Comptes inactifs : aucune connexion depuis 3 ans (ou jamais connectés, créés il y a 3 ans)
    const inactifs: string[] = [];
    for (let page = 1; ; page++) {
      const { data, error } = await sb.auth.admin.listUsers({ page, perPage: 1000 });
      if (error) throw error;
      for (const u of data.users) {
        const derniere = u.last_sign_in_at ?? u.created_at;
        if (derniere < limite3ans) inactifs.push(u.id);
      }
      if (data.users.length < 1000) break;
    }

    // 2. Audits à supprimer : non modifiés depuis 3 ans, ou appartenant à un compte inactif
    const ids = new Set<string>();
    const anciens = await sb.from("audits").select("id").lt("modifie_le", limite3ans);
    if (anciens.error) throw anciens.error;
    anciens.data.forEach((a) => ids.add(a.id));
    if (inactifs.length) {
      const deComptes = await sb.from("audits").select("id").in("proprietaire", inactifs);
      if (deComptes.error) throw deComptes.error;
      deComptes.data.forEach((a) => ids.add(a.id));
    }

    // 3. Leurs photos (fichiers du stockage), puis les audits (les réponses suivent, en cascade)
    for (const id of ids) {
      const { data: fichiers, error } = await sb.storage.from("photos").list(id, { limit: 1000 });
      if (error) throw error;
      const chemins = (fichiers ?? []).map((f) => `${id}/${f.name}`);
      if (chemins.length) {
        const { error: e2 } = await sb.storage.from("photos").remove(chemins);
        if (e2) throw e2;
        bilan.photos += chemins.length;
      }
      const { error: e3 } = await sb.from("audits").delete().eq("id", id);
      if (e3) throw e3;
      bilan.audits += 1;
    }

    // 4. Réponses brutes de plus de 12 mois
    const rep = await sb.from("reponses_usagers").delete({ count: "exact" }).lt("recue_le", limite12mois);
    if (rep.error) throw rep.error;
    bilan.reponses = rep.count ?? 0;

    // 5. Comptes inactifs
    for (const id of inactifs) {
      const { error } = await sb.auth.admin.deleteUser(id);
      if (error) throw error;
      bilan.comptes += 1;
    }
  } catch (e) {
    console.error("purge-conservation", e);
    return new Response(JSON.stringify({ ok: false, erreur: String(e?.message ?? e), bilan }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
  console.log("purge-conservation", bilan);
  return new Response(JSON.stringify({ ok: true, bilan }), { headers: { "Content-Type": "application/json" } });
});
