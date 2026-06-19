from sqlalchemy.orm import Session

from src.application.services.product_service import ProductService, SupplierService
from src.infrastructure.persistence.product_repository import SqlAlchemyProductRepository
from src.infrastructure.persistence.supplier_repository import SqlAlchemySupplierRepository
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


def compose_product_service(db: Session) -> ProductService:
    return ProductService(
        products=SqlAlchemyProductRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
    )


def compose_supplier_service(db: Session) -> SupplierService:
    return SupplierService(
        suppliers=SqlAlchemySupplierRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
    )
