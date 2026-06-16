# Remédiation — effacement RGPD incomplet (comptes orphelins)

Suite à la bascule E2E zero-knowledge, la cascade d'effacement de compte (RGPD art. 17)
avait des trous qui laissaient des données **orphelines** après suppression. Ce document
explique les causes, les correctifs, et la procédure de remédiation (code + données déjà
orphelines comme `breizhooz@gmail.com`).

> Entrée centralisée via le **Makefile** (`make rgpd-*`, qui délègue à `cleaner.sh`). Lecture conseillée avant de lancer.
>
> | Cible make | Action |
> |---|---|
> | `make rgpd-clean` | remédiation complète (redeploy → diagnostic → rejeu → purge clés) |
> | `make rgpd-diagnose` | compte les orphelins |
> | `make rgpd-replay` | rejoue le journal d'effacement cross-service |
> | `make rgpd-keys` | purge le matériel de clés orphelin |
>
> Le redéploiement initial reste `make restart S="service-profile service-menu service-user celery-worker-user"`
> (ou via `make rgpd-clean` qui l'inclut).

---

## 1. Pourquoi le nettoyage était incomplet

| # | Cause | Effet | Statut |
|---|-------|-------|--------|
| 1 | **Effacement cross-service asynchrone (Celery).** `service-user` journalise la purge (`erasure_targets` en `pending`) puis la délègue à une tâche Celery. Si le worker/broker n'était pas dispo, **la purge n'a jamais tourné**. | profile / menu / notification / nutrition gardent les données du compte. Rejouable via le journal. | **opérationnel** → rejeu |
| 2 | **service-menu** ne supprimait que les menus en clair (`weekly_menus`/`menu_slots`), pas les **blobs `weekly_menu` chiffrés** ; pire, un `return 0` anticipé court-circuitait toute purge dès qu'il n'y avait plus de menu clair (cas E2E normal). | blobs de menu chiffrés orphelins. | **corrigé** (`service-menu/app/repositories/erasure.py`) |
| 3 | **service-user** ne supprimait jamais `user_key_material` (sel, params KDF, **wrapped UK + matériel de récupération**) : aucune FK `CASCADE`, aucun delete explicite. | matériel cryptographique orphelin. | **corrigé** (`service-user/app/repositories/user_repository.py`) |

> Rappel : `service-profile` purge bien désormais ses blobs santé (erasure réécrit lors de la bascule E2E).

---

## 2. Correctifs de code (déjà appliqués, à déployer)

- `service-menu/app/repositories/erasure.py` → purge menus clairs **+ blobs chiffrés** (coerce `account_id`→UUID), sans court-circuit.
- `service-user/app/repositories/user_repository.py` → `delete()` supprime explicitement `UserKeyMaterial`.

Les services sont **volume-montés** (`uvicorn --reload` / `watchmedo`) : le **code** est rechargé à chaud.
Mais les **migrations** ne tournent qu'au démarrage du conteneur (`CMD: alembic upgrade head && uvicorn …`).
Il faut donc **redémarrer** les services concernés pour (re)appliquer leurs migrations.

> ⚠️ Le redémarrage de **service-profile** applique la migration **destructive** `c4f7e1a9b302`
> (DROP des tables santé en clair). C'est voulu (zero-knowledge), mais irréversible.

---

## 3. Bases & conteneurs (stack docker `nutri-app`)

| Service | Conteneur | Base PostgreSQL |
|---|---|---|
| user | `nutriplanner-service-user` | `nutriplanner_user` |
| menu | `nutriplanner-service-menu` | `nutriplanner_menu` |
| profile | `nutriplanner-service-profile` | `nutriplanner_profile` |
| worker user | `nutriplanner-celery-worker-user` | — |
| postgres | `nutriplanner-postgres` | (toutes) |

Toutes les commandes se lancent **depuis `backend/`** (où vit `docker-compose.yml`).
`psql` se connecte via le superuser interne du conteneur postgres (`$POSTGRES_USER`, trust local).

---

## 4. Procédure de remédiation

### Étape A — Redéployer (applique correctifs + migrations)

```bash
docker compose restart service-profile service-menu service-user celery-worker-user
# suivre les migrations au boot :
docker compose logs -f --tail=40 service-profile service-menu
```

### Étape B — Diagnostiquer les orphelins

```bash
# matériel de clés orphelin (compte supprimé) :
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d nutriplanner_user -tAc \
   "SELECT count(*) FROM user_key_material WHERE user_id NOT IN (SELECT id FROM users);"'

# requêtes d'effacement non terminées (à rejouer) :
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d nutriplanner_user -tAc \
   "SELECT service, status, count(*) FROM erasure_targets WHERE status <> '\''done'\'' GROUP BY 1,2;"'
```

### Étape C — Rejouer le journal d'effacement (purge cross-service)

Rejoue **toutes** les requêtes non terminées via `process_erasure_request` (idempotent, sans broker).
Avec le code corrigé, ça purge enfin les **blobs menu** (et profile/nutrition/notification).

```bash
docker compose exec -T service-user python - <<'PY'
import asyncio, uuid
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
        print(f"{len(rids)} requête(s) à rejouer")
        for rid in rids:
            failed = await erasure_service.process_erasure_request(session, rid)
            print(f"  {rid}: {'OK' if not failed else 'ÉCHECS ' + ','.join(failed)}")

asyncio.run(main())
PY
```

### Étape D — Purger le matériel de clés orphelin

Le delete local de service-user a déjà tourné (sans supprimer les clés) → le rejeu du journal
**ne couvre pas** cette table. Purge explicite des clés sans utilisateur correspondant :

```bash
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d nutriplanner_user -c \
   "DELETE FROM user_key_material WHERE user_id NOT IN (SELECT id FROM users);"'
```

### Étape E — Vérifier

Re-lancer l'étape B : les compteurs d'orphelins doivent être à **0**, et `erasure_targets`
ne doit plus contenir de cible `pending`/`failed`.

---

## 5. À ne pas oublier

- Ces correctifs sont **non committés** : pense au commit (cf. messages proposés en session).
- Le script `cleaner.sh all` enchaîne A→E avec confirmations sur les étapes destructives.
- Tests ajoutés : effacement des blobs menu + suppression du `user_key_material` (suites menu/user vertes).
