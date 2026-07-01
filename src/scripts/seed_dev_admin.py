from src.config import settings
from src.domain.auth.entity import User
from src.infrastructure.auth.jwt import BcryptPasswordHasher
from src.infrastructure.database import SessionLocal
from src.infrastructure.persistence.auth_repository import SqlAlchemyUserRepository
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


def seed_dev_admin() -> None:
    if not settings.dev_admin_password:
        raise SystemExit("Set DEV_ADMIN_PASSWORD before seeding the local admin user")

    db = SessionLocal()
    try:
        users = SqlAlchemyUserRepository(db)
        if users.get_by_username("admin"):
            print("Local admin user already exists")
            return

        users.add(
            User.create(
                username="admin",
                email=settings.dev_admin_email,
                hashed_password=BcryptPasswordHasher().hash(settings.dev_admin_password),
            )
        )
        SqlAlchemyUnitOfWork(db).commit()
        print("Local admin user created")
    finally:
        db.close()


if __name__ == "__main__":
    seed_dev_admin()
