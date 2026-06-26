import pytest

from src.domain.exceptions import ValidationError
from src.domain.service_catalog.entity import CatalogService, ServiceProductLine


def test_catalog_service_create_preserves_fields():
    service = CatalogService.create(
        name="Troca de óleo",
        description="Troca completa",
        base_price=100.0,
        estimated_hours=2.0,
    )

    assert service.name == "Troca de óleo"
    assert service.description == "Troca completa"
    assert service.base_price == 100.0
    assert service.estimated_hours == 2.0
    assert service.product_lines == []


def test_catalog_service_rejects_non_positive_base_price():
    with pytest.raises(ValidationError):
        CatalogService.create("Troca de óleo", None, 0, 1.0)


def test_catalog_service_updates_only_provided_fields():
    service = CatalogService.create("Troca de óleo", None, 100.0, 2.0)

    service.update_details(
        name="Troca de óleo premium",
        description=None,
        base_price=150.0,
        estimated_hours=None,
    )

    assert service.name == "Troca de óleo premium"
    assert service.description is None
    assert service.base_price == 150.0
    assert service.estimated_hours == 2.0


def test_service_product_line_rejects_non_positive_quantity():
    with pytest.raises(ValidationError):
        ServiceProductLine.create(service_id=1, product_id=1, quantity=0)


def test_service_product_line_create_preserves_fields():
    line = ServiceProductLine.create(service_id=1, product_id=2, quantity=3)

    assert line.service_id == 1
    assert line.product_id == 2
    assert line.quantity == 3
