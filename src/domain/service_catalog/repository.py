from typing import Protocol

from src.domain.service_catalog.entity import CatalogService, ServiceProductLine


class ServiceCatalogRepository(Protocol):
    def add(self, service: CatalogService) -> CatalogService:
        ...

    def get_by_id(self, service_id: int) -> CatalogService | None:
        ...

    def list_all(self) -> list[CatalogService]:
        ...

    def save(self, service: CatalogService) -> CatalogService:
        ...

    def delete(self, service: CatalogService) -> None:
        ...

    def add_product_line(self, line: ServiceProductLine) -> ServiceProductLine:
        ...

    def get_product_line(
        self,
        service_id: int,
        line_id: int,
    ) -> ServiceProductLine | None:
        ...

    def get_product_line_by_product(
        self,
        service_id: int,
        product_id: int,
    ) -> ServiceProductLine | None:
        ...

    def delete_product_line(self, line: ServiceProductLine) -> None:
        ...
