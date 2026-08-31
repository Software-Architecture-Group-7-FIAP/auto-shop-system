from sqlalchemy.orm import Session

from src.application.ports.service_order import (
    ServiceOrderCatalogService,
    ServiceOrderCustomer,
    ServiceOrderProductRequirement,
    ServiceOrderProduct,
    ServiceOrderVehicle,
)
from src.domain.enums import ServiceOrderStatus
from src.domain.exceptions import NotFoundError
from src.domain.service_order.entity import (
    ServiceOrder,
    ServiceOrderProductLine,
    ServiceOrderServiceLine,
)
from src.infrastructure.database import (
    CustomerModel,
    ProductModel,
    ServiceModel,
    ServiceOrderModel,
    ServiceOrderProductLineModel,
    ServiceProductLineModel,
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

    def create(self, service_order: ServiceOrder) -> ServiceOrder:
        model = ServiceOrderModel(
            budget_id=service_order.budget_id,
            customer_id=service_order.customer_id,
            vehicle_id=service_order.vehicle_id,
            status=service_order.status,
            priority=service_order.priority,
            mechanic_name=service_order.mechanic_name,
            total_price=service_order.total_price,
        )
        self.db.add(model)
        self.db.flush()

        for service_line in service_order.service_lines:
            self.db.add(
                ServiceOrderServiceLineModel(
                    service_order_id=model.id,
                    service_id=service_line.service_id,
                    quantity=service_line.quantity,
                    unit_price=service_line.unit_price,
                )
            )
        for product_line in service_order.product_lines:
            self.db.add(
                ServiceOrderProductLineModel(
                    service_order_id=model.id,
                    product_id=product_line.product_id,
                    quantity=product_line.quantity,
                    unit_price=product_line.unit_price,
                )
            )

        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

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


class SqlAlchemyServiceOrderOpeningLookup:
    def __init__(self, db: Session):
        self.db = db

    def customer_exists(self, customer_id: int) -> bool:
        return (
            self.db.query(CustomerModel.id)
            .filter(CustomerModel.id == customer_id)
            .first()
            is not None
        )

    def vehicle_belongs_to_customer(self, vehicle_id: int, customer_id: int) -> bool:
        return (
            self.db.query(VehicleModel.id)
            .filter(
                VehicleModel.id == vehicle_id,
                VehicleModel.customer_id == customer_id,
            )
            .first()
            is not None
        )

    def get_service(self, service_id: int) -> ServiceOrderCatalogService | None:
        model = self.db.query(ServiceModel).filter(ServiceModel.id == service_id).first()
        if not model:
            return None
        requirements = self.db.query(ServiceProductLineModel).filter(
            ServiceProductLineModel.service_id == service_id
        ).all()
        return ServiceOrderCatalogService(
            id=model.id,
            base_price=model.base_price,
            product_requirements=tuple(
                ServiceOrderProductRequirement(
                    product_id=requirement.product_id,
                    quantity=requirement.quantity,
                )
                for requirement in requirements
            ),
        )

    def get_product(self, product_id: int) -> ServiceOrderProduct | None:
        model = self.db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if not model:
            return None
        return ServiceOrderProduct(id=model.id, unit_price=model.unit_price)
