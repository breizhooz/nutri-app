#!/usr/bin/env bash
# Remédiation de l'effacement RGPD incomplet (comptes orphelins). Cf. cleaner.md.
# Lance depuis backend/. Sous-commandes : redeploy | diagnose | replay | purge-keys | all
set -euo pipefail
cd "$(dirname "$0")"

DC="docker compose"
C='\033[1;36m'; Y='\033[1;33m'; R='\033[1;31m'; G='\033[1;32m'; Z='\033[0m'
step() { echo -e "\n${C}== $* ==${Z}"; }
warn() { echo -e "${Y}$*${Z}"; }
confirm() { read -r -p "$(echo -e "${Y}$* [oui/non] ${Z}")" a; [ "$a" = "oui" ]; }

# psql superuser (trust local dans le conteneur postgres) sur une base donnée.
psql_db() { $DC exec -T postgres sh -lc "psql -U \"\$POSTGRES_USER\" -d \"$1\" -tAc \"$2\""; }

redeploy() {
  step "Redéploiement (restart → migrations au boot + reload code)"
  warn "⚠️  service-profile applique la migration DESTRUCTIVE c4f7e1a9b302 (DROP des tables santé en clair)."
  confirm "Continuer le redéploiement ?" || { echo "Abandon."; return 1; }
  $DC restart service-profile service-menu service-user celery-worker-user
  echo "Migrations (Ctrl-C pour quitter les logs) :"
  $DC logs --tail=30 service-profile service-menu | grep -iE "alembic|running upgrade|error" || true
}

diagnose() {
  step "Diagnostic des orphelins"
  echo -n "Matériel de clés orphelin (user_key_material sans user) : "
  psql_db nutriplanner_user "SELECT count(*) FROM user_key_material WHERE user_id NOT IN (SELECT id FROM users);"
  echo "Cibles d'effacement non terminées (service | statut | n) :"
  psql_db nutriplanner_user "SELECT service||' | '||status||' | '||count(*) FROM erasure_targets WHERE status <> 'done' GROUP BY service,status;" || echo "  (aucune)"
}

replay() {
  step "Rejeu du journal d'effacement (purge cross-service, idempotent)"
  $DC exec -T service-user python - <<'PY'
import asyncio
from sqlalchemy import select
from app.db.session import _session_factory
from app.models.erasure import ErasureTarget
from app.services import erasure_service

async def main():
    async with _session_factory()() as session:
        rows = await session.execute(
            select(ErasureTarget.request_id).where(ErasureTarget.status != "done").distinct()
        )
        rids = [r[0] for r in rows.all()]
        print(f"{len(rids)} requete(s) a rejouer")
        for rid in rids:
            failed = await erasure_service.process_erasure_request(session, rid)
            print(f"  {rid}: {'OK' if not failed else 'ECHECS ' + ','.join(failed)}")

asyncio.run(main())
PY
}

purge_keys() {
  step "Purge du matériel de clés orphelin"
  echo -n "Lignes concernées : "
  psql_db nutriplanner_user "SELECT count(*) FROM user_key_material WHERE user_id NOT IN (SELECT id FROM users);"
  confirm "Supprimer définitivement ces clés orphelines ?" || { echo "Abandon."; return 1; }
  $DC exec -T postgres sh -lc \
    "psql -U \"\$POSTGRES_USER\" -d nutriplanner_user -c \
     \"DELETE FROM user_key_material WHERE user_id NOT IN (SELECT id FROM users);\""
  echo -e "${G}Purge effectuée.${Z}"
}

case "${1:-help}" in
  redeploy)   redeploy ;;
  diagnose)   diagnose ;;
  replay)     replay ;;
  purge-keys) purge_keys ;;
  all)        redeploy && diagnose && replay && purge_keys && { step "Vérification finale"; diagnose; } ;;
  *) echo "Usage: ./cleaner.sh {redeploy|diagnose|replay|purge-keys|all}"; exit 1 ;;
esac
