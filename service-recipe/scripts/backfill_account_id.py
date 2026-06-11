"""One-off backfill : recipes.account_id depuis les memberships OWNER.

Le mapping ``user_id -> account_id`` (compte OWNER) vit dans la base de
service-user (``nutriplanner_user``), non joignable en SQL depuis la base recipe
(frontière dure). Ce script lit ce mapping et remplit ``recipes.account_id`` là où
il est NULL, en se basant sur ``created_by_user_id``. Idempotent.

À lancer APRÈS la migration, et SUIVI d'une réindexation Elasticsearch
(POST /api/v1/recipe/reindex ou commande équivalente) pour que les documents ES
portent le champ ``account_id`` (sinon la recherche, filtrée par compte, ne
renvoie plus rien).

Usage :

    docker exec nutriplanner-service-recipe python scripts/backfill_account_id.py
"""

import asyncio
import os

import asyncpg


async def _main() -> None:
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    user = os.getenv("POSTGRES_SUPERUSER", "nutriadmin")
    password = os.getenv("POSTGRES_SUPERUSER_PASSWORD", "nutriadminpass")
    user_db = os.getenv("POSTGRES_USER_DB", "nutriplanner_user")
    recipe_db = os.getenv("POSTGRES_RECIPE_DB", "nutriplanner_recipe")

    user_conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database=user_db
    )
    try:
        rows = await user_conn.fetch(
            """
            SELECT identity_id, account_id
            FROM memberships
            WHERE role_code = 'OWNER' AND status = 'active'
            """
        )
    finally:
        await user_conn.close()

    mapping = {str(r["identity_id"]): str(r["account_id"]) for r in rows}
    print(f"[backfill] {len(mapping)} mapping(s) OWNER lus depuis {user_db}")

    recipe_conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database=recipe_db
    )
    try:
        updated = 0
        for identity_id, account_id in mapping.items():
            result = await recipe_conn.execute(
                """
                UPDATE recipes
                SET account_id = $1
                WHERE created_by_user_id = $2 AND account_id IS NULL
                """,
                account_id,
                identity_id,
            )
            updated += int(result.split()[-1])
        remaining = await recipe_conn.fetchval(
            "SELECT count(*) FROM recipes WHERE account_id IS NULL"
        )
    finally:
        await recipe_conn.close()

    print(f"[backfill] {updated} recette(s) mise(s) à jour dans {recipe_db}")
    print(f"[backfill] recettes restantes sans account_id : {remaining}")
    print("[backfill] ⚠️ lancer ensuite une réindexation Elasticsearch.")


if __name__ == "__main__":
    asyncio.run(_main())
