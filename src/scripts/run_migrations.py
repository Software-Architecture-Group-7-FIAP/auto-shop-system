import subprocess

import psycopg2

from src.config import settings


MIGRATION_LOCK_KEY = 7_349_841


def run_migrations() -> int:
    try:
        connection = psycopg2.connect(
            settings.database_url,
            connect_timeout=settings.database_health_check_timeout_seconds,
        )
    except (psycopg2.Error, OSError):
        return 10

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_KEY,))
            result = subprocess.run(["alembic", "upgrade", "head"], check=False)
            return result.returncode
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(run_migrations())
