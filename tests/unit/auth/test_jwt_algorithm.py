import jwt

from src.config import settings
from src.domain.exceptions import UnauthorizedError
from src.infrastructure.auth.jwt import JWT_ALGORITHM, JwtAccessTokenService


def test_access_tokens_are_issued_with_pinned_hs256_algorithm():
    token = JwtAccessTokenService().create_access_token("admin")

    assert jwt.get_unverified_header(token)["alg"] == JWT_ALGORITHM == "HS256"


def test_access_token_decoder_rejects_a_different_algorithm():
    token = jwt.encode(
        {"sub": "admin"},
        settings.jwt_secret(),
        algorithm="HS384",
    )

    try:
        JwtAccessTokenService().decode_token(token)
    except UnauthorizedError:
        return
    raise AssertionError("tokens signed with a different algorithm were accepted")
