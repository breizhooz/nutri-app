"""One-off backfill : macro_errors.account_id depuis les memberships OWNER.

Le mapping ``user_id -> account_id`` (compte OWNER) vit dans la base de
service-user (``nutriplanner_user``), non joignable en SQL depuis la base
nutrition (frontière dure). Ce script lit ce mapping et remplit
``macro_errors.account_id`` là où il est NULL. Idempotent.

Usage :

    docker exec nutriplanner-service-nutrition python scripts/backfill_account_id.py
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
    nutrition_db = os.getenv("POSTGRES_NUTRITION_DB", "nutri_db")

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

    mapping = {r["identity_id"]: r["account_id"] for r in rows}
    print(f"[backfill] {len(mapping)} mapping(s) OWNER lus depuis {user_db}")

    nut_conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database=nutrition_db
    )
    try:
        updated = 0
        for identity_id, account_id in mapping.items():
            result = await nut_conn.execute(
                """
                UPDATE macro_errors
                SET account_id = $1
                WHERE user_id = $2 AND account_id IS NULL
                """,
                account_id,
                identity_id,
            )
            updated += int(result.split()[-1])
        remaining = await nut_conn.fetchval(
            "SELECT count(*) FROM macro_errors WHERE account_id IS NULL"
        )
    finally:
        await nut_conn.close()

    print(f"[backfill] {updated} macro_error(s) mis à jour dans {nutrition_db}")
    print(f"[backfill] macro_errors restants sans account_id : {remaining}")


if __name__ == "__main__":
    asyncio.run(_main())
