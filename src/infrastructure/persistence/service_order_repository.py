from datetime import datetime, timezone

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
    ServiceOrderStatusTransition,
)
from src.domain.service_order.rules import (
    STATUS_RANKING,
    ServiceOrderListItem,
    ServiceOrderListQuery,
    ServiceOrderOrdering,
)
from src.infrastructure.database import (
    CustomerModel,
    ServiceOrderModel,
    ServiceOrderProductLineModel,
    ServiceOrderServiceLineModel,
    ServiceOrderStatusHistoryModel,
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

    def get_by_budget_id(self, budget_id: int) -> ServiceOrder | None:
        model = (
            self.db.query(ServiceOrderModel)
            .filter(ServiceOrderModel.budget_id == budget_id)
            .first()
        )
        return self._to_domain(model) if model else None

    def get_by_tracking_token_fingerprint(self, token_fingerprint: str) -> ServiceOrder | None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        model = (
            self.db.query(ServiceOrderModel)
            .filter(
                ServiceOrderModel.tracking_token_hash == token_fingerprint,
                ServiceOrderModel.tracking_token_revoked_at.is_(None),
                ServiceOrderModel.tracking_token_expires_at > now,
            )
            .first()
        )
        if not model:
            return None
        return self._to_domain(model)

    def set_tracking_token_fingerprint(
        self,
        service_order_id: int,
        token_fingerprint: str,
        expires_at: datetime | None = None,
    ) -> None:
        model = (
            self.db.query(ServiceOrderModel)
            .filter(ServiceOrderModel.id == service_order_id)
            .first()
        )
        if not model:
            raise NotFoundError("OS não encontrada")
        model.tracking_token_hash = token_fingerprint
        model.tracking_token_expires_at = expires_at
        model.tracking_token_revoked_at = None
        self.db.flush()

    def list_all(self, status: ServiceOrderStatus | None = None) -> list[ServiceOrder]:
        query = self.db.query(ServiceOrderModel)
        if status:
            query = query.filter(ServiceOrderModel.status == status)
        return [self._to_domain(model) for model in query.all()]

    def list_operational(
        self,
        query: ServiceOrderListQuery,
    ) -> Page[ServiceOrderListItem]:
        base_query = self._listing_query(query.visible_statuses())
        total = base_query.order_by(None).count()
        rows = (
            self._apply_listing_order(base_query, query.order_by)
            .offset(query.offset)
            .limit(query.page_size)
            .all()
        )
        return Page(
            items=tuple(self._listing_row_to_item(row) for row in rows),
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    def _listing_query(
        self,
        visible_statuses: frozenset[ServiceOrderStatus],
    ) -> Query:
        query = (
            self.db.query(
                ServiceOrderModel.id.label("id"),
                ServiceOrderModel.budget_id.label("budget_id"),
                ServiceOrderModel.customer_id.label("customer_id"),
                ServiceOrderModel.vehicle_id.label("vehicle_id"),
                ServiceOrderModel.status.label("status"),
                ServiceOrderModel.priority.label("priority"),
                ServiceOrderModel.mechanic_name.label("mechanic_name"),
                ServiceOrderModel.total_price.label("total_price"),
                ServiceOrderModel.started_at.label("started_at"),
                ServiceOrderModel.finished_at.label("finished_at"),
                CustomerModel.name.label("customer_name"),
                VehicleModel.plate.label("vehicle_plate"),
                ServiceOrderModel.created_at.label("created_at"),
                ServiceOrderModel.updated_at.label("updated_at"),
            )
            .join(CustomerModel, CustomerModel.id == ServiceOrderModel.customer_id)
            .join(VehicleModel, VehicleModel.id == ServiceOrderModel.vehicle_id)
        )
        return query.filter(ServiceOrderModel.status.in_(tuple(visible_statuses)))

    @staticmethod
    def _apply_listing_order(query: Query, ordering: ServiceOrderOrdering) -> Query:
        if ordering is ServiceOrderOrdering.CREATED_AT_DESC:
            return query.order_by(
                ServiceOrderModel.created_at.desc(),
                ServiceOrderModel.id.asc(),
            )
        if ordering is ServiceOrderOrdering.CREATED_AT_ASC:
            return query.order_by(
                ServiceOrderModel.created_at.asc(),
                ServiceOrderModel.id.asc(),
            )

        status_rank = case(
            *(
                (ServiceOrderModel.status == status, rank)
                for rank, status in enumerate(STATUS_RANKING)
            ),
            else_=len(STATUS_RANKING),
        )
        return query.order_by(
            status_rank.asc(),
            ServiceOrderModel.created_at.asc(),
            ServiceOrderModel.id.asc(),
        )

    @staticmethod
    def _listing_row_to_item(row) -> ServiceOrderListItem:
        return ServiceOrderListItem(
            id=row.id,
            budget_id=row.budget_id,
            customer_id=row.customer_id,
            vehicle_id=row.vehicle_id,
            status=row.status,
            priority=row.priority,
            mechanic_name=row.mechanic_name,
            total_price=row.total_price,
            started_at=row.started_at,
            finished_at=row.finished_at,
            customer_name=row.customer_name,
            vehicle_plate=row.vehicle_plate,
            created_at=row.created_at,
            updated_at=row.updated_at,
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
            .with_for_update()
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
        persisted_history = self.db.query(ServiceOrderStatusHistoryModel).filter(
            ServiceOrderStatusHistoryModel.service_order_id == service_order.id
        ).all()
        existing_request_ids = {
            item.request_id for item in persisted_history if item.request_id is not None
        }
        existing_legacy_events = {
            self._history_event_key(item)
            for item in persisted_history
            if item.request_id is None
        }
        for transition in service_order.status_history:
            if (
                transition.request_id is not None
                and transition.request_id in existing_request_ids
            ):
                continue
            occurred_at = transition.occurred_at.replace(tzinfo=None)
            if (
                transition.request_id is None
                and self._history_event_key(transition, occurred_at)
                in existing_legacy_events
            ):
                continue
            self.db.add(
                ServiceOrderStatusHistoryModel(
                    service_order_id=service_order.id,
                    from_status=transition.from_status,
                    to_status=transition.to_status,
                    transition_type=transition.transition_type,
                    reason=transition.reason,
                    actor_id=transition.actor_id,
                    request_id=transition.request_id,
                    occurred_at=occurred_at,
                )
            )
            if transition.request_id is not None:
                existing_request_ids.add(transition.request_id)
            else:
                existing_legacy_events.add(
                    self._history_event_key(transition, occurred_at)
                )
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    @staticmethod
    def _history_event_key(event, occurred_at: datetime | None = None) -> tuple:
        return (
            event.from_status,
            event.to_status,
            event.transition_type,
            event.reason,
            event.actor_id,
            occurred_at if occurred_at is not None else event.occurred_at,
        )

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
            status_history=[
                ServiceOrderStatusTransition(
                    from_status=item.from_status,
                    to_status=item.to_status,
                    transition_type=item.transition_type,
                    reason=item.reason,
                    actor_id=item.actor_id,
                    request_id=item.request_id,
                    occurred_at=item.occurred_at,
                )
                for item in model.status_history
            ],
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
