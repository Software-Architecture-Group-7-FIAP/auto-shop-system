from dataclasses import replace

import pytest

from src.application.services.service_catalog_service import ServiceCatalogService
from src.domain.exceptions import NotFoundError
from src.domain.service_catalog.entity import CatalogService, ServiceProductLine


class InMemoryServiceCatalogRepository:
    def __init__(self):
        self.services: dict[int, CatalogService] = {}
        self.product_lines: dict[int, ServiceProductLine] = {}
        self.next_service_id = 1
        self.next_line_id = 1

    def add(self, service: CatalogService) -> CatalogService:
        created = replace(service, id=self.next_service_id)
        self.services[self.next_service_id] = created
        self.next_service_id += 1
        return created

    def get_by_id(self, service_id: int) -> CatalogService | None:
        return self.services.get(service_id)

    def list_all(self) -> list[CatalogService]:
        return list(self.services.values())

    def save(self, service: CatalogService) -> CatalogService:
        assert service.id is not None
        self.services[service.id] = service
        return service

    def delete(self, service: CatalogService) -> None:
        assert service.id is not None
        del self.services[service.id]

    def add_product_line(self, line: ServiceProductLine) -> ServiceProductLine:
        created = replace(line, id=self.next_line_id)
        self.product_lines[self.next_line_id] = created
        self.next_line_id += 1
        return created

    def get_product_line(
        self,
        service_id: int,
        line_id: int,
    ) -> ServiceProductLine | None:
        line = self.product_lines.get(line_id)
        if not line or line.service_id != service_id:
            return None
        return line

    def delete_product_line(self, line: ServiceProductLine) -> None:
        assert line.id is not None
        del self.product_lines[line.id]


class InMemoryProductLookup:
    def __init__(self, existing_ids: set[int]):
        self.existing_ids = existing_ids

    def exists(self, product_id: int) -> bool:
        return product_id in self.existing_ids


class FakeUnitOfWork:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_service_catalog_creates_service_without_sqlalchemy():
    repository = InMemoryServiceCatalogRepository()
    uow = FakeUnitOfWork()
    service = ServiceCatalogService(repository, InMemoryProductLookup(set()), uow)

    created = service.create("Troca de óleo", None, 100.0, 2.0)

    assert created.id == 1
    assert created.base_price == 100.0
    assert uow.commits == 1


def test_service_catalog_updates_service():
    service = ServiceCatalogService(
        InMemoryServiceCatalogRepository(),
        InMemoryProductLookup(set()),
        FakeUnitOfWork(),
    )
    created = service.create("Troca de óleo", None, 100.0, 2.0)

    updated = service.update(created.id, "Alinhamento", "Descrição", 150.0, None)

    assert updated.name == "Alinhamento"
    assert updated.description == "Descrição"
    assert updated.base_price == 150.0
    assert updated.estimated_hours == 2.0


def test_service_catalog_rejects_missing_service():
    service = ServiceCatalogService(
        InMemoryServiceCatalogRepository(),
        InMemoryProductLookup(set()),
        FakeUnitOfWork(),
    )

    with pytest.raises(NotFoundError):
        service.get_by_id(1)


def test_service_catalog_adds_product_line():
    repository = InMemoryServiceCatalogRepository()
    uow = FakeUnitOfWork()
    service = ServiceCatalogService(repository, InMemoryProductLookup({2}), uow)
    created = service.create("Troca de óleo", None, 100.0, 2.0)

    line = service.add_product_line(created.id, product_id=2, quantity=3)

    assert line.id == 1
    assert line.service_id == created.id
    assert line.product_id == 2
    assert line.quantity == 3
    assert uow.commits == 2


def test_service_catalog_rejects_missing_product():
    service = ServiceCatalogService(
        InMemoryServiceCatalogRepository(),
        InMemoryProductLookup(set()),
        FakeUnitOfWork(),
    )
    created = service.create("Troca de óleo", None, 100.0, 2.0)

    with pytest.raises(NotFoundError):
        service.add_product_line(created.id, product_id=2, quantity=3)


def test_service_catalog_removes_product_line():
    repository = InMemoryServiceCatalogRepository()
    service = ServiceCatalogService(repository, InMemoryProductLookup({2}), FakeUnitOfWork())
    created = service.create("Troca de óleo", None, 100.0, 2.0)
    line = service.add_product_line(created.id, product_id=2, quantity=3)

    service.remove_product_line(created.id, line.id)

    assert repository.get_product_line(created.id, line.id) is None
