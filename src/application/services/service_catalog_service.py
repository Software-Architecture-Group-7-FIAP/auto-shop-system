from src.application.ports.product_lookup import ProductLookup
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.exceptions import ConflictError, NotFoundError
from src.domain.service_catalog.entity import CatalogService, ServiceProductLine
from src.domain.service_catalog.repository import ServiceCatalogRepository


class ServiceCatalogService:
    def __init__(
        self,
        services: ServiceCatalogRepository,
        products: ProductLookup,
        uow: UnitOfWork,
    ):
        self.services = services
        self.products = products
        self.uow = uow

    def create(
        self, name: str, description: str | None, base_price: float, estimated_hours: float = 1.0
    ) -> CatalogService:
        service = CatalogService.create(
            name=name,
            description=description,
            base_price=base_price,
            estimated_hours=estimated_hours,
        )
        created = self.services.add(service)
        self.uow.commit()
        return created

    def get_by_id(self, service_id: int) -> CatalogService:
        service = self.services.get_by_id(service_id)
        if not service:
            raise NotFoundError("Serviço não encontrado")
        return service

    def list_all(self) -> list[CatalogService]:
        return self.services.list_all()

    def update(
        self,
        service_id: int,
        name: str | None,
        description: str | None,
        base_price: float | None,
        estimated_hours: float | None,
    ) -> CatalogService:
        service = self.get_by_id(service_id)
        service.update_details(name, description, base_price, estimated_hours)
        updated = self.services.save(service)
        self.uow.commit()
        return updated

    def delete(self, service_id: int) -> None:
        service = self.get_by_id(service_id)
        self.services.delete(service)
        self.uow.commit()

    def add_product_line(
        self,
        service_id: int,
        product_id: int,
        quantity: int,
    ) -> ServiceProductLine:
        service = self.get_by_id(service_id)
        if not self.products.exists(product_id):
            raise NotFoundError("Produto não encontrado")
        if service.id is None:
            raise NotFoundError("Serviço não encontrado")
        if self.services.get_product_line_by_product(service.id, product_id):
            raise ConflictError("Produto já vinculado ao serviço")

        line = ServiceProductLine.create(
            service_id=service.id,
            product_id=product_id,
            quantity=quantity,
        )
        created = self.services.add_product_line(line)
        self.uow.commit()
        return created

    def remove_product_line(self, service_id: int, line_id: int) -> None:
        line = self.services.get_product_line(service_id, line_id)
        if not line:
            raise NotFoundError("Linha de produto não encontrada")
        self.services.delete_product_line(line)
        self.uow.commit()

    def remove_product_line_by_product(self, service_id: int, product_id: int) -> None:
        self.get_by_id(service_id)
        line = self.services.get_product_line_by_product(service_id, product_id)
        if not line:
            raise NotFoundError("Linha de produto não encontrada")
        self.services.delete_product_line(line)
        self.uow.commit()
