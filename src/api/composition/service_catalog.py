from sqlalchemy.orm import Session

from src.application.services.service_catalog_service import ServiceCatalogService
from src.infrastructure.persistence.product_repository import SqlAlchemyProductLookup
from src.infrastructure.persistence.service_catalog_repository import (
    SqlAlchemyServiceCatalogRepository,
)
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


def compose_service_catalog_service(db: Session) -> ServiceCatalogService:
    return ServiceCatalogService(
        services=SqlAlchemyServiceCatalogRepository(db),
        products=SqlAlchemyProductLookup(db),
        uow=SqlAlchemyUnitOfWork(db),
    )
