from datetime import datetime

from sqlalchemy.orm import Session

from src.domain.enums import Priority, ServiceOrderStatus
from src.domain.exceptions import NotFoundError, ValidationError
from src.infrastructure.database import ServiceOrderModel


class ServiceOrderService:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, service_order_id: int) -> ServiceOrderModel:
        os = self.db.query(ServiceOrderModel).filter(ServiceOrderModel.id == service_order_id).first()
        if not os:
            raise NotFoundError("OS não encontrada")
        return os

    def list_all(self, status: ServiceOrderStatus | None = None) -> list[ServiceOrderModel]:
        query = self.db.query(ServiceOrderModel)
        if status:
            query = query.filter(ServiceOrderModel.status == status)
        return query.all()

    def get_by_customer_document(self, service_order_id: int, document: str) -> ServiceOrderModel:
        from src.domain.value_objects.validators import DocumentValidator
        from src.infrastructure.database import CustomerModel

        cleaned = DocumentValidator.validate(document)
        os = self.get_by_id(service_order_id)
        customer = self.db.query(CustomerModel).filter(CustomerModel.id == os.customer_id).first()
        if not customer or customer.document != cleaned:
            raise NotFoundError("OS não encontrada para este documento")
        return os

    def assign_mechanic(self, service_order_id: int, mechanic_name: str) -> ServiceOrderModel:
        os = self.get_by_id(service_order_id)
        os.mechanic_name = mechanic_name
        os.status = ServiceOrderStatus.EM_DIAGNOSTICO
        self.db.commit()
        self.db.refresh(os)
        return os

    def set_priority(self, service_order_id: int, priority: Priority) -> ServiceOrderModel:
        os = self.get_by_id(service_order_id)
        os.priority = priority
        self.db.commit()
        self.db.refresh(os)
        return os

    def get_average_execution_time(self) -> dict:
        orders = (
            self.db.query(ServiceOrderModel)
            .filter(
                ServiceOrderModel.started_at.isnot(None),
                ServiceOrderModel.finished_at.isnot(None),
            )
            .all()
        )
        if not orders:
            return {"average_hours": 0, "sample_size": 0}
        total_seconds = sum(
            (o.finished_at - o.started_at).total_seconds() for o in orders
        )
        avg_hours = total_seconds / len(orders) / 3600
        return {"average_hours": round(avg_hours, 2), "sample_size": len(orders)}
