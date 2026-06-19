from src.domain.auth.entity import User


def test_user_create_defaults_to_active():
    user = User.create(
        username="admin",
        email="admin@oficina.local",
        hashed_password="hashed",
    )

    assert user.id is None
    assert user.username == "admin"
    assert user.email == "admin@oficina.local"
    assert user.hashed_password == "hashed"
    assert user.is_active is True
