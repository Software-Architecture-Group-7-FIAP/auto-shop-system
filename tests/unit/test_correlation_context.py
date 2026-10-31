from uuid import UUID

import pytest

from src.infrastructure.observability.context import accept_correlation_id


@pytest.mark.parametrize(
    "value",
    (
        "52998224725",
        "529.982.247-25",
        "11222333000181",
        "11.222.333/0001-81",
    ),
)
def test_rejects_cpf_and_cnpj_shapes(value: str):
    assert accept_correlation_id(value) is None


def test_accepts_safe_non_document_ids():
    assert accept_correlation_id("probe-1") == "probe-1"
    assert accept_correlation_id("0e8cf6ae-93a5-4bc5-a902-4ef9cb8d6a30") == (
        "0e8cf6ae-93a5-4bc5-a902-4ef9cb8d6a30"
    )


def test_cpf_header_is_replaced_in_http_flow(client):
    response = client.get("/health/live", headers={"X-Correlation-ID": "52998224725"})

    assert response.status_code == 200
    generated = response.headers["x-correlation-id"]
    assert generated != "52998224725"
    UUID(generated)
