from sqlalchemy.orm import Session

from src.domain.exceptions import NotFoundError
from src.infrastructure.database import ProductModel, ServiceModel, ServiceProductLineModel


class ServiceCatalogService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, name: str, description: str | None, base_price: float, estimated_hours: float = 1.0
    ) -> ServiceModel:
        service = ServiceModel(
            name=name,
            description=description,
            base_price=base_price,
            estimated_hours=estimated_hours,
        )
        self.db.add(service)
        self.db.commit()
        self.db.refresh(service)
        return service

    def get_by_id(self, service_id: int) -> ServiceModel:
        service = self.db.query(ServiceModel).filter(ServiceModel.id == service_id).first()
        if not service:
            raise NotFoundError("Serviço não encontrado")
        return service

    def list_all(self) -> list[ServiceModel]:
        return self.db.query(ServiceModel).all()

    def update(
        self,
        service_id: int,
        name: str | None,
        description: str | None,
        base_price: float | None,
        estimated_hours: float | None,
    ) -> ServiceModel:
        service = self.get_by_id(service_id)
        if name is not None:
            service.name = name
        if description is not None:
            service.description = description
        if base_price is not None:
            service.base_price = base_price
        if estimated_hours is not None:
            service.estimated_hours = estimated_hours
        self.db.commit()
        self.db.refresh(service)
        return service

    def delete(self, service_id: int) -> None:
        service = self.get_by_id(service_id)
        self.db.delete(service)
        self.db.commit()

    def add_product_line(self, service_id: int, product_id: int, quantity: int) -> ServiceProductLineModel:
        service = self.get_by_id(service_id)
        product = self.db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if not product:
            raise NotFoundError("Produto não encontrado")
        line = ServiceProductLineModel(service_id=service.id, product_id=product_id, quantity=quantity)
        self.db.add(line)
        self.db.commit()
        self.db.refresh(line)
        return line

    def remove_product_line(self, service_id: int, line_id: int) -> None:
        line = (
            self.db.query(ServiceProductLineModel)
            .filter(
                ServiceProductLineModel.id == line_id,
                ServiceProductLineModel.service_id == service_id,
            )
            .first()
        )
        if not line:
            raise NotFoundError("Linha de produto não encontrada")
        self.db.delete(line)
        self.db.commit()
