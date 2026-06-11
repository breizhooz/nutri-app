"""One-off backfill : profiles.account_id depuis les memberships OWNER.

Le mapping ``user_id -> account_id`` (compte personnel OWNER) vit dans la base
de service-user (``nutriplanner_user``) ; il n'est pas joignable en SQL depuis
la base de service-profile (frontière dure inter-bases). Ce script lit ce mapping
et met à jour ``profiles.account_id`` là où il est encore NULL.

Idempotent : ne touche que les lignes ``account_id IS NULL``.

Usage (one-off, depuis un conteneur ayant accès au réseau Postgres) :

    docker exec nutriplanner-service-profile python scripts/backfill_account_id.py

Connexion via le superuser Postgres (accès à toutes les bases). Les valeurs par
défaut correspondent au .env de dev ; surchargeables par variables d'env.
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
    profile_db = os.getenv("POSTGRES_PROFILE_DB", "nutriplanner_profile")

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

    profile_conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database=profile_db
    )
    try:
        updated = 0
        for identity_id, account_id in mapping.items():
            result = await profile_conn.execute(
                """
                UPDATE profiles
                SET account_id = $1
                WHERE user_id = $2 AND account_id IS NULL
                """,
                account_id,
                identity_id,
            )
            # result == "UPDATE <n>"
            updated += int(result.split()[-1])
        remaining = await profile_conn.fetchval(
            "SELECT count(*) FROM profiles WHERE account_id IS NULL"
        )
    finally:
        await profile_conn.close()

    print(f"[backfill] {updated} profil(s) mis à jour dans {profile_db}")
    print(f"[backfill] profils restants sans account_id : {remaining}")


if __name__ == "__main__":
    asyncio.run(_main())
