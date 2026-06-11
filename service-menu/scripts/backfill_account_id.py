"""One-off backfill : weekly_menus.account_id depuis les memberships OWNER.

Le mapping ``user_id -> account_id`` (compte OWNER) vit dans la base de
service-user (``nutriplanner_user``), non joignable en SQL depuis la base menu
(frontière dure). Ce script lit ce mapping et remplit ``weekly_menus.account_id``
là où il est NULL. Idempotent.

Usage (one-off, depuis un conteneur ayant accès au réseau Postgres) :

    docker exec nutriplanner-service-menu python scripts/backfill_account_id.py

Connexion via le superuser Postgres. Valeurs par défaut = .env de dev,
surchargeables par variables d'env.
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
    menu_db = os.getenv("POSTGRES_MENU_DB", "nutriplanner_menu")

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

    # user_id est stocké en String(36) côté menu -> on compare en texte.
    mapping = {str(r["identity_id"]): str(r["account_id"]) for r in rows}
    print(f"[backfill] {len(mapping)} mapping(s) OWNER lus depuis {user_db}")

    menu_conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database=menu_db
    )
    try:
        updated = 0
        for identity_id, account_id in mapping.items():
            result = await menu_conn.execute(
                """
                UPDATE weekly_menus
                SET account_id = $1
                WHERE user_id = $2 AND account_id IS NULL
                """,
                account_id,
                identity_id,
            )
            updated += int(result.split()[-1])
        remaining = await menu_conn.fetchval(
            "SELECT count(*) FROM weekly_menus WHERE account_id IS NULL"
        )
    finally:
        await menu_conn.close()

    print(f"[backfill] {updated} menu(s) mis à jour dans {menu_db}")
    print(f"[backfill] menus restants sans account_id : {remaining}")


if __name__ == "__main__":
    asyncio.run(_main())
