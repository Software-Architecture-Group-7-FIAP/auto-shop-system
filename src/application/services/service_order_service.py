from src.application.ports.service_order import (
    RequestedPart,
    RequestedService,
    ServiceOrderContactLookup,
    ServiceOrderCatalogService,
    ServiceOrderOpeningLookup,
    ServiceOrderStockReserver,
)
from src.application.ports.service_order_tracking import ServiceOrderTrackingTokenService
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.enums import Priority, ServiceOrderStatus
from src.domain.exceptions import NotFoundError
from src.domain.service_order.entity import (
    ServiceOrder,
    ServiceOrderProductLine,
    ServiceOrderServiceLine,
)
from src.domain.service_order.repository import ServiceOrderRepository
from src.domain.value_objects.validators import DocumentValidator


class ServiceOrderService:
    def __init__(
        self,
        service_orders: ServiceOrderRepository,
        contacts: ServiceOrderContactLookup,
        openings: ServiceOrderOpeningLookup,
        stock_reserver: ServiceOrderStockReserver,
        tracking_tokens: ServiceOrderTrackingTokenService,
        uow: UnitOfWork,
    ):
        self.service_orders = service_orders
        self.contacts = contacts
        self.openings = openings
        self.stock_reserver = stock_reserver
        self.tracking_tokens = tracking_tokens
        self.uow = uow

    def open(
        self,
        customer_id: int,
        vehicle_id: int,
        services: list[RequestedService],
        parts: list[RequestedPart],
    ) -> ServiceOrder:
        if not self.openings.customer_exists(customer_id):
            raise NotFoundError("Customer not found")
        if not self.openings.vehicle_belongs_to_customer(vehicle_id, customer_id):
            raise NotFoundError("Vehicle not found or does not belong to the customer")

        service_lines: list[ServiceOrderServiceLine] = []
        product_lines = [self._build_product_line(item) for item in parts]
        for item in services:
            service = self.openings.get_service(item.service_id)
            if not service:
                raise NotFoundError("Service not found")
            service_lines.append(self._service_line_from_catalog(item, service))
            product_lines.extend(
                self._build_catalog_product_lines(service, item.quantity)
            )

        created = self.service_orders.create(
            ServiceOrder.open(customer_id, vehicle_id, service_lines, product_lines)
        )
        if created.id is None:
            raise NotFoundError("OS não encontrada após criação")
        self.stock_reserver.create_reservations_for_os(created.id, commit=False)
        self.uow.commit()
        return created

    @staticmethod
    def _service_line_from_catalog(
        item: RequestedService,
        service: ServiceOrderCatalogService,
    ) -> ServiceOrderServiceLine:
        return ServiceOrderServiceLine(
            id=None,
            service_order_id=None,
            service_id=service.id,
            quantity=item.quantity,
            unit_price=service.base_price,
        )

    def _build_catalog_product_lines(
        self,
        service: ServiceOrderCatalogService,
        service_quantity: int,
    ) -> list[ServiceOrderProductLine]:
        return [
            self._build_product_line(
                RequestedPart(
                    product_id=requirement.product_id,
                    quantity=requirement.quantity * service_quantity,
                )
            )
            for requirement in service.product_requirements
        ]

    def _build_product_line(self, item: RequestedPart) -> ServiceOrderProductLine:
        product = self.openings.get_product(item.product_id)
        if not product:
            raise NotFoundError("Part not found")
        return ServiceOrderProductLine(
            id=None,
            service_order_id=None,
            product_id=product.id,
            quantity=item.quantity,
            unit_price=product.unit_price,
        )

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

    def get_by_tracking_token(self, token: str) -> ServiceOrder:
        token_fingerprint = self.tracking_tokens.fingerprint(token)
        service_order = self.service_orders.get_by_tracking_token_fingerprint(
            token_fingerprint
        )
        if not service_order:
            raise NotFoundError("Link de acompanhamento inválido")
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
    ) -> ServiceOrder:
        service_order = self.get_by_id(service_order_id)
        if priority is not None:
            service_order.set_priority(priority)
        if mechanic_name is not None:
            service_order.assign_mechanic(mechanic_name)
        updated = self.service_orders.save(service_order)
        self.uow.commit()
        return updated

    def override_status(
        self,
        service_order_id: int,
        status: ServiceOrderStatus,
        reason: str,
    ) -> ServiceOrder:
        service_order = self.get_by_id(service_order_id)
        service_order.override_status(status, reason)
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
