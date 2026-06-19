from sqlalchemy.orm import Session

from src.application.services.inventory_service import InventoryService
from src.infrastructure.persistence.inventory_repository import (
    SqlAlchemyInventoryProductGateway,
    SqlAlchemyInventoryRepository,
    SqlAlchemyInventoryServiceOrderLookup,
)
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


def compose_inventory_service(db: Session) -> InventoryService:
    return InventoryService(
        inventory=SqlAlchemyInventoryRepository(db),
        products=SqlAlchemyInventoryProductGateway(db),
        service_orders=SqlAlchemyInventoryServiceOrderLookup(db),
        uow=SqlAlchemyUnitOfWork(db),
    )
