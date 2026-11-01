import io
import json
from urllib.error import HTTPError

import pytest

from scripts.observability.synthetic_auth import SyntheticAuthError, run_synthetic_auth


class _Response:
    status = 200
    headers = {"x-amzn-requestid": "gateway-safe-id"}

    def __init__(self):
        self._body = io.BytesIO(b'{"access_token":"must-never-escape"}')

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _size=-1):
        return self._body.read(_size)


def test_synthetic_auth_sends_cpf_but_returns_only_safe_metadata():
    captured = {}

    def opener(request, timeout):
        captured["body"] = json.loads(request.data)
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return _Response()

    result = run_synthetic_auth(
        url="https://api.oficina-workshop.com.br/hml/auth/customer/token",
        cpf="52998224725",
        opener=opener,
    )

    assert captured["body"] == {"cpf": "52998224725"}
    assert result["status"] == 200
    assert result["gateway_request_id"] == "gateway-safe-id"
    assert "correlation_id" in result
    serialized = json.dumps(result)
    assert "52998224725" not in serialized
    assert "must-never-escape" not in serialized


def test_synthetic_auth_rejects_non_hml_target():
    with pytest.raises(SyntheticAuthError):
        run_synthetic_auth(
            url="https://attacker.invalid/hml/auth/customer/token",
            cpf="52998224725",
            opener=lambda *_args: _Response(),
        )


def test_synthetic_auth_fails_closed_and_discards_error_response_body():
    error = HTTPError(
        url="https://api.oficina-workshop.com.br/hml/auth/customer/token",
        code=401,
        msg="Unauthorized",
        hdrs={"x-amzn-requestid": "safe-error-id", "set-cookie": "secret"},
        fp=io.BytesIO(b'{"access_token":"secret-error-token"}'),
    )

    with pytest.raises(SyntheticAuthError, match="HTTP 401") as raised:
        run_synthetic_auth(
            url="https://api.oficina-workshop.com.br/hml/auth/customer/token",
            cpf="52998224725",
            opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
        )

    assert "secret" not in str(raised.value)


def test_synthetic_auth_rejects_redirect_without_exposing_location():
    redirect = HTTPError(
        url="https://api.oficina-workshop.com.br/hml/auth/customer/token",
        code=302,
        msg="Found",
        hdrs={"location": "https://attacker.invalid/capture?token=secret"},
        fp=io.BytesIO(b"redirect"),
    )

    with pytest.raises(SyntheticAuthError, match="redirects are forbidden") as raised:
        run_synthetic_auth(
            url="https://api.oficina-workshop.com.br/hml/auth/customer/token",
            cpf="52998224725",
            opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(redirect),
        )

    assert "attacker" not in str(raised.value)
    assert "secret" not in str(raised.value)


def test_synthetic_auth_rejects_untrusted_gateway_request_id():
    response = _Response()
    response.headers = {"x-amzn-requestid": "unsafe\nsecret-output"}

    result = run_synthetic_auth(
        url="https://api.oficina-workshop.com.br/hml/auth/customer/token",
        cpf="52998224725",
        opener=lambda *_args, **_kwargs: response,
    )

    assert result["gateway_request_id"] == "unavailable"
