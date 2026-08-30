from sqlalchemy import case
from sqlalchemy.orm import Query, Session

from src.application.ports.service_order import ServiceOrderCustomer, ServiceOrderVehicle
from src.domain.enums import ServiceOrderStatus
from src.domain.exceptions import NotFoundError
from src.domain.pagination import Page
from src.domain.service_order.entity import (
    ServiceOrder,
    ServiceOrderProductLine,
    ServiceOrderServiceLine,
)
from src.domain.service_order.rules import (
    STATUS_RANKING,
    ServiceOrderListQuery,
    ServiceOrderOrdering,
)
from src.infrastructure.database import (
    CustomerModel,
    ServiceOrderModel,
    ServiceOrderProductLineModel,
    ServiceOrderServiceLineModel,
    VehicleModel,
)


class SqlAlchemyServiceOrderRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, service_order_id: int) -> ServiceOrder | None:
        model = (
            self.db.query(ServiceOrderModel)
            .filter(ServiceOrderModel.id == service_order_id)
            .first()
        )
        if not model:
            return None
        return self._to_domain(model)

    def get_by_tracking_token_fingerprint(self, token_fingerprint: str) -> ServiceOrder | None:
        model = (
            self.db.query(ServiceOrderModel)
            .filter(ServiceOrderModel.tracking_token_hash == token_fingerprint)
            .first()
        )
        if not model:
            return None
        return self._to_domain(model)

    def set_tracking_token_fingerprint(
        self,
        service_order_id: int,
        token_fingerprint: str,
    ) -> None:
        model = (
            self.db.query(ServiceOrderModel)
            .filter(ServiceOrderModel.id == service_order_id)
            .first()
        )
        if not model:
            raise NotFoundError("OS não encontrada")
        model.tracking_token_hash = token_fingerprint
        self.db.flush()

    def list_all(self, status: ServiceOrderStatus | None = None) -> list[ServiceOrder]:
        query = self.db.query(ServiceOrderModel)
        if status:
            query = query.filter(ServiceOrderModel.status == status)
        return [self._to_domain(model) for model in query.all()]

    def list_operational(self, query: ServiceOrderListQuery) -> Page[ServiceOrder]:
        visible_statuses = query.visible_statuses()
        if not visible_statuses:
            return Page(items=(), total=0, page=query.page, page_size=query.page_size)

        base = self.db.query(ServiceOrderModel).filter(
            ServiceOrderModel.status.in_(tuple(visible_statuses))
        )
        total = base.order_by(None).count()
        models = (
            self._apply_ordering(base, query.order_by)
            .offset(query.offset)
            .limit(query.page_size)
            .all()
        )
        return Page(
            items=tuple(self._to_domain(model) for model in models),
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    @staticmethod
    def _apply_ordering(
        query: Query[ServiceOrderModel],
        ordering: ServiceOrderOrdering,
    ) -> Query[ServiceOrderModel]:
        if ordering is ServiceOrderOrdering.CREATED_AT_DESC:
            return query.order_by(ServiceOrderModel.created_at.desc(), ServiceOrderModel.id.desc())
        if ordering is ServiceOrderOrdering.CREATED_AT_ASC:
            return query.order_by(ServiceOrderModel.created_at.asc(), ServiceOrderModel.id.asc())
        status_rank = case(
            {status: rank for rank, status in enumerate(STATUS_RANKING)},
            value=ServiceOrderModel.status,
            else_=len(STATUS_RANKING),
        )
        return query.order_by(
            status_rank,
            ServiceOrderModel.created_at.asc(),
            ServiceOrderModel.id.asc(),
        )

    def list_with_execution_times(self) -> list[ServiceOrder]:
        models = (
            self.db.query(ServiceOrderModel)
            .filter(
                ServiceOrderModel.started_at.isnot(None),
                ServiceOrderModel.finished_at.isnot(None),
            )
            .all()
        )
        return [self._to_domain(model) for model in models]

    def list_by_ids_and_status(
        self,
        service_order_ids: list[int],
        status: ServiceOrderStatus,
    ) -> list[ServiceOrder]:
        if not service_order_ids:
            return []
        models = (
            self.db.query(ServiceOrderModel)
            .filter(
                ServiceOrderModel.id.in_(service_order_ids),
                ServiceOrderModel.status == status,
            )
            .all()
        )
        return [self._to_domain(model) for model in models]

    def save(self, service_order: ServiceOrder) -> ServiceOrder:
        if service_order.id is None:
            raise NotFoundError("OS não encontrada")

        model = (
            self.db.query(ServiceOrderModel)
            .filter(ServiceOrderModel.id == service_order.id)
            .first()
        )
        if not model:
            raise NotFoundError("OS não encontrada")

        model.status = service_order.status
        model.priority = service_order.priority
        model.mechanic_name = service_order.mechanic_name
        model.total_price = service_order.total_price
        model.started_at = service_order.started_at
        model.finished_at = service_order.finished_at
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    @classmethod
    def _to_domain(cls, model: ServiceOrderModel) -> ServiceOrder:
        return ServiceOrder(
            id=model.id,
            budget_id=model.budget_id,
            customer_id=model.customer_id,
            vehicle_id=model.vehicle_id,
            status=model.status,
            priority=model.priority,
            mechanic_name=model.mechanic_name,
            total_price=model.total_price,
            started_at=model.started_at,
            finished_at=model.finished_at,
            created_at=model.created_at,
            service_lines=[
                cls._service_line_to_domain(line) for line in model.service_lines
            ],
            product_lines=[
                cls._product_line_to_domain(line) for line in model.product_lines
            ],
        )

    @staticmethod
    def _service_line_to_domain(
        model: ServiceOrderServiceLineModel,
    ) -> ServiceOrderServiceLine:
        return ServiceOrderServiceLine(
            id=model.id,
            service_order_id=model.service_order_id,
            service_id=model.service_id,
            quantity=model.quantity,
            unit_price=model.unit_price,
        )

    @staticmethod
    def _product_line_to_domain(
        model: ServiceOrderProductLineModel,
    ) -> ServiceOrderProductLine:
        return ServiceOrderProductLine(
            id=model.id,
            service_order_id=model.service_order_id,
            product_id=model.product_id,
            quantity=model.quantity,
            unit_price=model.unit_price,
        )


class SqlAlchemyServiceOrderContactLookup:
    def __init__(self, db: Session):
        self.db = db

    def get_customer(self, customer_id: int) -> ServiceOrderCustomer | None:
        model = self.db.query(CustomerModel).filter(CustomerModel.id == customer_id).first()
        if not model:
            return None
        return ServiceOrderCustomer(
            name=model.name,
            email=model.email,
            documents=tuple(doc_model.document for doc_model in model.documents),
        )

    def get_vehicle(self, vehicle_id: int) -> ServiceOrderVehicle | None:
        model = self.db.query(VehicleModel).filter(VehicleModel.id == vehicle_id).first()
        if not model:
            return None
        return ServiceOrderVehicle(plate=model.plate)
