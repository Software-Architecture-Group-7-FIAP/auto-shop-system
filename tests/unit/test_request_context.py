from uuid import UUID

from starlette.requests import Request

from src.api.request_context import request_correlation_id


def make_request(headers: list[tuple[bytes, bytes]]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        }
    )


def test_correlation_header_takes_precedence_over_legacy_request_id():
    correlation_id = "0e8cf6ae-93a5-4bc5-a902-4ef9cb8d6a30"
    request = make_request(
        [
            (b"x-correlation-id", correlation_id.encode()),
            (b"x-request-id", b"b9a6a6fe-72cc-44ca-8d2e-d79a4cd4e166"),
        ]
    )

    assert request_correlation_id(request) == correlation_id


def test_invalid_correlation_value_is_replaced_with_a_generated_uuid():
    unsafe = "bad\r\ninjected"
    request = make_request([(b"x-correlation-id", unsafe.encode())])

    generated_id = request_correlation_id(request)

    assert generated_id != unsafe
    assert str(UUID(generated_id)) == generated_id
