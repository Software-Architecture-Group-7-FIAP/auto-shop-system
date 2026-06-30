from dataclasses import replace
from types import SimpleNamespace

from src.domain.auth.entity import User
from src.scripts import seed_dev_admin


class InMemoryUserRepository:
    def __init__(self, db):
        self.db = db

    def add(self, user: User) -> User:
        created = replace(user, id=len(self.db.users) + 1)
        self.db.users[created.username] = created
        return created

    def get_by_username(self, username: str) -> User | None:
        return self.db.users.get(username)


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"


class FakeUnitOfWork:
    def __init__(self, db):
        self.db = db

    def commit(self) -> None:
        self.db.commits += 1

    def rollback(self) -> None:
        pass


class FakeDb:
    def __init__(self):
        self.users: dict[str, User] = {}
        self.commits = 0
        self.closed = False

    def close(self) -> None:
        self.closed = True


def configure_seed_dependencies(monkeypatch, db: FakeDb, password: str | None):
    monkeypatch.setattr(seed_dev_admin, "SessionLocal", lambda: db)
    monkeypatch.setattr(seed_dev_admin, "SqlAlchemyUserRepository", InMemoryUserRepository)
    monkeypatch.setattr(seed_dev_admin, "BcryptPasswordHasher", FakePasswordHasher)
    monkeypatch.setattr(seed_dev_admin, "SqlAlchemyUnitOfWork", FakeUnitOfWork)
    monkeypatch.setattr(
        seed_dev_admin,
        "settings",
        SimpleNamespace(dev_admin_password=password, dev_admin_email="owner@oficina.local"),
    )


def test_seed_dev_admin_requires_password(monkeypatch):
    db = FakeDb()
    configure_seed_dependencies(monkeypatch, db, password=None)

    try:
        seed_dev_admin.seed_dev_admin()
    except SystemExit as exc:
        assert str(exc) == "Set DEV_ADMIN_PASSWORD before seeding the local admin user"
    else:
        raise AssertionError("Expected seed_dev_admin to exit without DEV_ADMIN_PASSWORD")

    assert db.closed is False


def test_seed_dev_admin_creates_admin(monkeypatch):
    db = FakeDb()
    configure_seed_dependencies(monkeypatch, db, password="safe-dev-password")

    seed_dev_admin.seed_dev_admin()

    admin = db.users["admin"]
    assert admin.email == "owner@oficina.local"
    assert admin.hashed_password == "hashed:safe-dev-password"
    assert db.commits == 1
    assert db.closed is True


def test_seed_dev_admin_skips_existing_admin(monkeypatch):
    db = FakeDb()
    db.users["admin"] = User.create(
        username="admin",
        email="admin@oficina.local",
        hashed_password="hashed:existing",
    )
    configure_seed_dependencies(monkeypatch, db, password="safe-dev-password")

    seed_dev_admin.seed_dev_admin()

    assert db.users["admin"].hashed_password == "hashed:existing"
    assert db.commits == 0
    assert db.closed is True
