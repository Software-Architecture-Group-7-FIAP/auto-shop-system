from functools import lru_cache

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError, PyJWTError

from src.config import settings
from src.domain.auth.principal import CustomerPrincipal
from src.domain.exceptions import UnauthorizedError

CUSTOMER_JWT_ALGORITHM = "RS256"
REQUIRED_CUSTOMER_CLAIMS = (
    "sub",
    "principal_type",
    "scope",
    "iss",
    "aud",
    "iat",
    "exp",
    "jti",
)


class CustomerJwtConfigurationError(Exception):
    pass


class CustomerJwksUnavailableError(Exception):
    pass


@lru_cache(maxsize=8)
def _jwks_client(url: str, timeout_seconds: int, cache_seconds: int) -> PyJWKClient:
    return PyJWKClient(
        url,
        cache_jwk_set=True,
        lifespan=cache_seconds,
        timeout=timeout_seconds,
    )


class CustomerJwtVerifier:
    def verify(self, token: str) -> CustomerPrincipal:
        issuer = settings.customer_jwt_issuer
        audience = settings.customer_jwt_audience
        jwks_url = settings.customer_jwt_jwks_url
        if not issuer or not audience or not jwks_url:
            raise CustomerJwtConfigurationError("Customer JWT verification is not configured")

        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != CUSTOMER_JWT_ALGORITHM:
                raise UnauthorizedError("Credenciais inv\u00e1lidas")
            if not isinstance(header.get("kid"), str) or not header["kid"].strip():
                raise UnauthorizedError("Credenciais inv\u00e1lidas")

            signing_key = _jwks_client(
                jwks_url,
                settings.customer_jwt_jwks_timeout_seconds,
                settings.customer_jwt_jwks_cache_seconds,
            ).get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=[CUSTOMER_JWT_ALGORITHM],
                audience=audience,
                issuer=issuer,
                leeway=settings.customer_jwt_clock_skew_seconds,
                options={"require": REQUIRED_CUSTOMER_CLAIMS},
            )
        except PyJWKClientConnectionError as exc:
            raise CustomerJwksUnavailableError from exc
        except (PyJWKClientError, PyJWTError, ValueError, TypeError) as exc:
            raise UnauthorizedError("Credenciais inv\u00e1lidas") from exc

        if claims.get("principal_type") != "customer" or claims.get("scope") != "customer":
            raise UnauthorizedError("Credenciais inv\u00e1lidas")

        subject = claims.get("sub")
        if (
            not isinstance(subject, str)
            or not subject.isascii()
            or not subject.isdecimal()
            or len(subject) > 10
        ):
            raise UnauthorizedError("Credenciais inv\u00e1lidas")

        customer_id = int(subject)
        if customer_id <= 0 or str(customer_id) != subject:
            raise UnauthorizedError("Credenciais inv\u00e1lidas")

        token_id = claims.get("jti")
        if not isinstance(token_id, str) or not token_id.strip():
            raise UnauthorizedError("Credenciais inv\u00e1lidas")

        return CustomerPrincipal(customer_id=customer_id)
