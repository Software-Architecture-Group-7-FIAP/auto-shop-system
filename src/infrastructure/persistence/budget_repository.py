from sqlalchemy.orm import Session

from src.application.ports.budget_lookups import (
    BudgetProductDetails,
    BudgetServiceDetails,
    BudgetServiceProductRequirement,
)
from src.domain.budget.entity import Budget, BudgetProductLine, BudgetServiceLine
from src.domain.enums import ReservationStatus
from src.domain.exceptions import NotFoundError
from src.infrastructure.database import (
    BudgetModel,
    BudgetProductLineModel,
    BudgetServiceLineModel,
    ProductModel,
    ReservationModel,
    ServiceModel,
    ServiceProductLineModel,
    VehicleModel,
)


class SqlAlchemyBudgetRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, budget: Budget) -> Budget:
        model = BudgetModel(
            customer_id=budget.customer_id,
            vehicle_id=budget.vehicle_id,
            status=budget.status,
            total_price=budget.total_price,
            estimated_delivery=budget.estimated_delivery,
            approval_token=budget.approval_token,
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, budget_id: int) -> Budget | None:
        model = self.db.query(BudgetModel).filter(BudgetModel.id == budget_id).first()
        if not model:
            return None
        return self._to_domain(model)

    def get_by_approval_token(self, token: str) -> Budget | None:
        model = (
            self.db.query(BudgetModel)
            .filter(BudgetModel.approval_token == token)
            .first()
        )
        if not model:
            return None
        return self._to_domain(model)

    def list_all(self) -> list[Budget]:
        models = self.db.query(BudgetModel).all()
        return [self._to_domain(model) for model in models]

    def add_service_line(self, line: BudgetServiceLine) -> BudgetServiceLine:
        model = BudgetServiceLineModel(
            budget_id=line.budget_id,
            service_id=line.service_id,
            quantity=line.quantity,
            unit_price=line.unit_price,
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._service_line_to_domain(model)

    def add_product_line(self, line: BudgetProductLine) -> BudgetProductLine:
        model = BudgetProductLineModel(
            budget_id=line.budget_id,
            product_id=line.product_id,
            quantity=line.quantity,
            unit_price=line.unit_price,
            from_service=line.from_service,
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._product_line_to_domain(model)

    def get_product_line(
            self,
            budget_id: int,
            line_id: int,
    ) -> BudgetProductLine | None:
        model = (
            self.db.query(BudgetProductLineModel)
            .filter(
                BudgetProductLineModel.id == line_id,
                BudgetProductLineModel.budget_id == budget_id,
            )
            .first()
        )

        if not model:
            return None

        return self._product_line_to_domain(model)

    def delete_product_line(self, line: BudgetProductLine) -> None:
        model = (
            self.db.query(BudgetProductLineModel)
            .filter(BudgetProductLineModel.id == line.id)
            .first()
        )

        if not model:
            raise NotFoundError("Linha de produto não encontrada")

        self.db.delete(model)
        self.db.flush()

    def save(self, budget: Budget) -> Budget:
        if budget.id is None:
            raise NotFoundError("Orçamento não encontrado")

        model = self.db.query(BudgetModel).filter(BudgetModel.id == budget.id).first()
        if not model:
            raise NotFoundError("Orçamento não encontrado")

        model.status = budget.status
        model.total_price = budget.total_price
        model.estimated_delivery = budget.estimated_delivery
        model.approval_token = budget.approval_token
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    @classmethod
    def _to_domain(cls, model: BudgetModel) -> Budget:
        return Budget(
            id=model.id,
            customer_id=model.customer_id,
            vehicle_id=model.vehicle_id,
            status=model.status,
            total_price=model.total_price,
            estimated_delivery=model.estimated_delivery,
            approval_token=model.approval_token,
            created_at=model.created_at,
            service_lines=[
                cls._service_line_to_domain(line) for line in model.service_lines
            ],
            product_lines=[
                cls._product_line_to_domain(line) for line in model.product_lines
            ],
        )

    @staticmethod
    def _service_line_to_domain(model: BudgetServiceLineModel) -> BudgetServiceLine:
        return BudgetServiceLine(
            id=model.id,
            budget_id=model.budget_id,
            service_id=model.service_id,
            quantity=model.quantity,
            unit_price=model.unit_price,
        )

    @staticmethod
    def _product_line_to_domain(model: BudgetProductLineModel) -> BudgetProductLine:
        return BudgetProductLine(
            id=model.id,
            budget_id=model.budget_id,
            product_id=model.product_id,
            quantity=model.quantity,
            unit_price=model.unit_price,
            from_service=model.from_service,
        )


class SqlAlchemyVehicleOwnershipLookup:
    def __init__(self, db: Session):
        self.db = db

    def belongs_to_customer(self, vehicle_id: int, customer_id: int) -> bool:
        return (
            self.db.query(VehicleModel)
            .filter(
                VehicleModel.id == vehicle_id,
                VehicleModel.customer_id == customer_id,
            )
            .first()
            is not None
        )


class SqlAlchemyBudgetServiceCatalogLookup:
    def __init__(self, db: Session):
        self.db = db

    def get_service(self, service_id: int) -> BudgetServiceDetails | None:
        model = self.db.query(ServiceModel).filter(ServiceModel.id == service_id).first()
        if not model:
            return None

        requirements = (
            self.db.query(ServiceProductLineModel)
            .filter(ServiceProductLineModel.service_id == service_id)
            .all()
        )
        return BudgetServiceDetails(
            id=model.id,
            base_price=model.base_price,
            estimated_hours=model.estimated_hours,
            product_requirements=tuple(
                BudgetServiceProductRequirement(
                    product_id=requirement.product_id,
                    quantity=requirement.quantity,
                )
                for requirement in requirements
            ),
        )


class SqlAlchemyBudgetProductLookup:
    def __init__(self, db: Session):
        self.db = db

    def get_product(self, product_id: int) -> BudgetProductDetails | None:
        model = self.db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if not model:
            return None
        return BudgetProductDetails(
            id=model.id,
            name=model.name,
            unit_price=model.unit_price,
            stock_quantity=model.stock_quantity,
        )


class SqlAlchemyReservationLookup:
    def __init__(self, db: Session):
        self.db = db

    def active_quantity_for_product(self, product_id: int) -> int:
        rows = (
            self.db.query(ReservationModel.quantity)
            .filter(
                ReservationModel.product_id == product_id,
                ReservationModel.status == ReservationStatus.ACTIVE,
            )
            .all()
        )
        return sum(row[0] for row in rows)
