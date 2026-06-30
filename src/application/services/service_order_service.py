from src.application.ports.service_order import ServiceOrderContactLookup
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.enums import Priority, ServiceOrderStatus
from src.domain.exceptions import NotFoundError
from src.domain.service_order.entity import ServiceOrder
from src.domain.service_order.repository import ServiceOrderRepository
from src.domain.value_objects.validators import DocumentValidator


class ServiceOrderService:
    def __init__(
        self,
        service_orders: ServiceOrderRepository,
        contacts: ServiceOrderContactLookup,
        uow: UnitOfWork,
    ):
        self.service_orders = service_orders
        self.contacts = contacts
        self.uow = uow

    def get_by_id(self, service_order_id: int) -> ServiceOrder:
        service_order = self.service_orders.get_by_id(service_order_id)
        if not service_order:
            raise NotFoundError("OS não encontrada")
        return service_order

    def list_all(self, status: ServiceOrderStatus | None = None) -> list[ServiceOrder]:
        return self.service_orders.list_all(status)

    def get_by_customer_document(self, service_order_id: int, document: str) -> ServiceOrder:
        cleaned = DocumentValidator.validate(document)
        service_order = self.get_by_id(service_order_id)
        customer = self.contacts.get_customer(service_order.customer_id)
        if not customer or cleaned not in customer.documents:
            raise NotFoundError("OS não encontrada para este documento")
        return service_order

    def assign_mechanic(self, service_order_id: int, mechanic_name: str) -> ServiceOrder:
        service_order = self.get_by_id(service_order_id)
        service_order.assign_mechanic(mechanic_name)
        updated = self.service_orders.save(service_order)
        self.uow.commit()
        return updated

    def update(
        self,
        service_order_id: int,
        mechanic_name: str | None = None,
        priority: Priority | None = None,
        status: ServiceOrderStatus | None = None,
    ) -> ServiceOrder:
        service_order = self.get_by_id(service_order_id)
        if priority is not None:
            service_order.set_priority(priority)
        if mechanic_name is not None:
            service_order.assign_mechanic(mechanic_name)
        if status is not None:
            service_order.set_status(status)
        updated = self.service_orders.save(service_order)
        self.uow.commit()
        return updated

    def set_priority(self, service_order_id: int, priority: Priority) -> ServiceOrder:
        service_order = self.get_by_id(service_order_id)
        service_order.set_priority(priority)
        updated = self.service_orders.save(service_order)
        self.uow.commit()
        return updated

    def get_average_execution_time(self) -> dict:
        orders = self.service_orders.list_with_execution_times()
        if not orders:
            return {"average_hours": 0, "sample_size": 0}
        total_seconds = sum(
            (order.finished_at - order.started_at).total_seconds() for order in orders
        )
        avg_hours = total_seconds / len(orders) / 3600
        return {"average_hours": round(avg_hours, 2), "sample_size": len(orders)}
