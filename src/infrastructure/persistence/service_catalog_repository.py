from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from src.domain.exceptions import ConflictError, NotFoundError
from src.domain.service_catalog.entity import CatalogService, ServiceProductLine
from src.infrastructure.database import ServiceModel, ServiceProductLineModel


class SqlAlchemyServiceCatalogRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, service: CatalogService) -> CatalogService:
        model = ServiceModel(
            name=service.name,
            description=service.description,
            base_price=service.base_price,
            estimated_hours=service.estimated_hours,
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, service_id: int) -> CatalogService | None:
        model = self.db.scalar(
            select(ServiceModel)
            .options(selectinload(ServiceModel.product_lines))
            .where(ServiceModel.id == service_id)
        )
        return self._to_domain(model) if model else None

    def list_all(self) -> list[CatalogService]:
        models = self.db.scalars(
            select(ServiceModel).options(selectinload(ServiceModel.product_lines))
        ).all()
        return [self._to_domain(model) for model in models]

    def save(self, service: CatalogService) -> CatalogService:
        if service.id is None:
            raise NotFoundError("Serviço não encontrado")

        model = self.db.scalar(
            select(ServiceModel).where(ServiceModel.id == service.id)
        )
        if not model:
            raise NotFoundError("Serviço não encontrado")

        model.name = service.name
        model.description = service.description
        model.base_price = service.base_price
        model.estimated_hours = service.estimated_hours
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def delete(self, service: CatalogService) -> None:
        if service.id is None:
            raise NotFoundError("Serviço não encontrado")

        model = self.db.scalar(
            select(ServiceModel).where(ServiceModel.id == service.id)
        )
        if not model:
            raise NotFoundError("Serviço não encontrado")

        self.db.delete(model)
        self.db.flush()

    def add_product_line(self, line: ServiceProductLine) -> ServiceProductLine:
        model = ServiceProductLineModel(
            service_id=line.service_id,
            product_id=line.product_id,
            quantity=line.quantity,
        )
        self.db.add(model)
        try:
            self.db.flush()
        except IntegrityError as exc:
            raise ConflictError("Produto já vinculado ao serviço") from exc
        self.db.refresh(model)
        return self._line_to_domain(model)

    def save_product_line(self, line: ServiceProductLine) -> ServiceProductLine:
        if line.id is None:
            raise NotFoundError("Linha de produto não encontrada")

        model = self.db.scalar(
            select(ServiceProductLineModel).where(
                ServiceProductLineModel.id == line.id,
                ServiceProductLineModel.service_id == line.service_id,
            )
        )
        if not model:
            raise NotFoundError("Linha de produto não encontrada")

        model.quantity = line.quantity
        self.db.flush()
        self.db.refresh(model)
        return self._line_to_domain(model)

    def get_product_line(
        self,
        service_id: int,
        line_id: int,
    ) -> ServiceProductLine | None:
        model = self.db.scalar(
            select(ServiceProductLineModel).where(
                ServiceProductLineModel.id == line_id,
                ServiceProductLineModel.service_id == service_id,
            )
        )
        return self._line_to_domain(model) if model else None

    def get_product_line_by_product(
        self,
        service_id: int,
        product_id: int,
    ) -> ServiceProductLine | None:
        model = self.db.scalar(
            select(ServiceProductLineModel).where(
                ServiceProductLineModel.service_id == service_id,
                ServiceProductLineModel.product_id == product_id,
            )
        )
        return self._line_to_domain(model) if model else None

    def delete_product_line(self, line: ServiceProductLine) -> None:
        if line.id is None:
            raise NotFoundError("Linha de produto não encontrada")

        model = self.db.scalar(
            select(ServiceProductLineModel).where(
                ServiceProductLineModel.id == line.id,
                ServiceProductLineModel.service_id == line.service_id,
            )
        )
        if not model:
            raise NotFoundError("Linha de produto não encontrada")

        self.db.delete(model)
        self.db.flush()

    @staticmethod
    def _to_domain(model: ServiceModel) -> CatalogService:
        return CatalogService(
            id=model.id,
            name=model.name,
            description=model.description,
            base_price=model.base_price,
            estimated_hours=model.estimated_hours,
            created_at=model.created_at,
            product_lines=[
                SqlAlchemyServiceCatalogRepository._line_to_domain(line)
                for line in model.product_lines
            ],
        )

    @staticmethod
    def _line_to_domain(model: ServiceProductLineModel) -> ServiceProductLine:
        return ServiceProductLine(
            id=model.id,
            service_id=model.service_id,
            product_id=model.product_id,
            quantity=model.quantity,
        )
