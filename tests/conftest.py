import os
import re

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["TESTING"] = "1"
os.environ["SECRET_KEY"] = "test-secret-key-with-at-least-32-chars"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.rate_limit import login_rate_limiter, public_rate_limiter
from src.domain.auth.entity import UserRole
from src.infrastructure import database as db_module
from src.infrastructure.auth.jwt import BcryptPasswordHasher
from src.infrastructure.database import Base, UserModel, get_db
from src.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_module.engine = engine
db_module.SessionLocal = TestingSessionLocal

ADMIN_CREDENTIALS = {"username": "admin", "password": "admin123"}
OPERATOR_CREDENTIALS = {"username": "operador", "password": "operador123"}

CSRF_COOKIE = "oficina_csrf"
ACCESS_COOKIE = "oficina_access"
REFRESH_COOKIE = "oficina_refresh"


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    hasher = BcryptPasswordHasher()
    db = TestingSessionLocal()
    db.add(
        UserModel(
            username=ADMIN_CREDENTIALS["username"],
            email="admin@test.local",
            hashed_password=hasher.hash(ADMIN_CREDENTIALS["password"]),
            role=UserRole.ADMIN,
        )
    )
    db.add(
        UserModel(
            username=OPERATOR_CREDENTIALS["username"],
            email="operador@test.local",
            hashed_password=hasher.hash(OPERATOR_CREDENTIALS["password"]),
            role=UserRole.OPERATOR,
        )
    )
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def reset_login_rate_limiter():
    """Process-global limiters must not leak state between tests."""
    login_rate_limiter.reset()
    public_rate_limiter.reset()
    yield
    login_rate_limiter.reset()
    public_rate_limiter.reset()


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(setup_db):
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def second_client(setup_db):
    """An independent cookie jar, for tests that need two live sessions."""
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c


def login(client, credentials=None) -> dict[str, str]:
    """Log in and return the CSRF header that pairs with the session cookies.

    Auth rides on HttpOnly cookies now, which the TestClient keeps in its own
    jar; what callers still have to pass explicitly is the double-submit
    header for state-changing requests.
    """
    response = client.post("/api/v1/auth/login", json=credentials or ADMIN_CREDENTIALS)
    assert response.status_code == 200, response.text
    return csrf_headers(client)


def csrf_headers(client) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    return (
        {"X-CSRF-Token": token, "Origin": "http://testserver"}
        if token
        else {"Origin": "http://testserver"}
    )


@pytest.fixture
def auth_headers(client):
    return login(client, ADMIN_CREDENTIALS)


@pytest.fixture
def operator_headers(second_client):
    return login(second_client, OPERATOR_CREDENTIALS)


class _CapturedEmails(list):
    def approval_token(self) -> str:
        """Pull the raw bearer token out of the approval link.

        The token is no longer returned by any API response - it only exists
        in the e-mail, in the URL fragment.
        """
        for message in self:
            for content in (message.get("html") or "", message.get("body") or ""):
                match = re.search(r"budget-approval\?action=\w+#([\w\-.]+)", content)
                if match:
                    return match.group(1)
        raise AssertionError("no approval link was e-mailed")

    def tracking_token(self) -> str:
        for message in self:
            for content in (message.get("html") or "", message.get("body") or ""):
                match = re.search(r"track-service-order#([\w\-.]+)", content)
                if match:
                    return match.group(1)
        raise AssertionError("no tracking link was e-mailed")


@pytest.fixture(autouse=True)
def captured_emails(monkeypatch):
    """Capture outgoing mail; `send_email` is a no-op while TESTING=1."""
    captured = _CapturedEmails()

    async def _capture(to, subject, body, html=None, attachments=()):
        captured.append({"to": to, "subject": subject, "body": body, "html": html})

    for module in (
        "src.infrastructure.budget_approval",
        "src.infrastructure.execution",
        "src.infrastructure.service_order",
    ):
        monkeypatch.setattr(f"{module}.send_email", _capture, raising=False)
    yield captured
