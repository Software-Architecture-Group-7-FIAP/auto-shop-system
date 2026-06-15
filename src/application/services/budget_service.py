from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from src.domain.enums import BudgetStatus
from src.domain.exceptions import NotFoundError, ValidationError
from src.infrastructure.database import (
    BudgetModel,
    BudgetProductLineModel,
    BudgetServiceLineModel,
    CustomerModel,
    ProductModel,
    ReservationModel,
    ServiceModel,
    ServiceProductLineModel,
    VehicleModel,
)
from src.domain.enums import ReservationStatus


class BudgetService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, customer_id: int, vehicle_id: int) -> BudgetModel:
        customer = self.db.query(CustomerModel).filter(CustomerModel.id == customer_id).first()
        vehicle = self.db.query(VehicleModel).filter(VehicleModel.id == vehicle_id).first()
        if not customer:
            raise NotFoundError("Cliente não encontrado")
        if not vehicle or vehicle.customer_id != customer_id:
            raise NotFoundError("Veículo não encontrado para este cliente")
        budget = BudgetModel(customer_id=customer_id, vehicle_id=vehicle_id)
        self.db.add(budget)
        self.db.commit()
        self.db.refresh(budget)
        return budget

    def get_by_id(self, budget_id: int) -> BudgetModel:
        budget = self.db.query(BudgetModel).filter(BudgetModel.id == budget_id).first()
        if not budget:
            raise NotFoundError("Orçamento não encontrado")
        return budget

    def list_all(self) -> list[BudgetModel]:
        return self.db.query(BudgetModel).all()

    def add_service_line(self, budget_id: int, service_id: int, quantity: int = 1) -> BudgetServiceLineModel:
        budget = self.get_by_id(budget_id)
        service = self.db.query(ServiceModel).filter(ServiceModel.id == service_id).first()
        if not service:
            raise NotFoundError("Serviço não encontrado")
        line = BudgetServiceLineModel(
            budget_id=budget.id,
            service_id=service_id,
            quantity=quantity,
            unit_price=service.base_price,
        )
        self.db.add(line)
        self.db.flush()

        for spl in (
            self.db.query(ServiceProductLineModel)
            .filter(ServiceProductLineModel.service_id == service_id)
            .all()
        ):
            product = self.db.query(ProductModel).filter(ProductModel.id == spl.product_id).first()
            if product:
                self._add_product_line(budget.id, product.id, spl.quantity * quantity, product.unit_price, True)

        self._recalculate(budget)
        self.db.commit()
        self.db.refresh(line)
        return line

    def add_product_line(
        self, budget_id: int, product_id: int, quantity: int = 1
    ) -> BudgetProductLineModel:
        budget = self.get_by_id(budget_id)
        product = self.db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if not product:
            raise NotFoundError("Produto não encontrado")
        line = self._add_product_line(budget.id, product_id, quantity, product.unit_price, False)
        self.db.flush()
        self._recalculate(budget)
        self.db.commit()
        self.db.refresh(line)
        return line

    def _add_product_line(
        self, budget_id: int, product_id: int, quantity: int, unit_price: float, from_service: bool
    ) -> BudgetProductLineModel:
        line = BudgetProductLineModel(
            budget_id=budget_id,
            product_id=product_id,
            quantity=quantity,
            unit_price=unit_price,
            from_service=from_service,
        )
        self.db.add(line)
        return line

    def _recalculate(self, budget: BudgetModel) -> None:
        self.db.refresh(budget)
        service_total = sum(line.unit_price * line.quantity for line in budget.service_lines)
        product_total = sum(line.unit_price * line.quantity for line in budget.product_lines)
        budget.total_price = service_total + product_total

        total_hours = 0.0
        for line in budget.service_lines:
            service = self.db.query(ServiceModel).filter(ServiceModel.id == line.service_id).first()
            if service:
                total_hours += service.estimated_hours * line.quantity
        budget.estimated_delivery = datetime.utcnow() + timedelta(hours=max(total_hours, 1))

    def check_availability(self, budget_id: int) -> list[dict]:
        budget = self.get_by_id(budget_id)
        result = []
        for line in budget.product_lines:
            product = self.db.query(ProductModel).filter(ProductModel.id == line.product_id).first()
            if not product:
                continue
            reserved = (
                self.db.query(ReservationModel)
                .filter(
                    ReservationModel.product_id == product.id,
                    ReservationModel.status == ReservationStatus.ACTIVE,
                )
                .with_entities(ReservationModel.quantity)
                .all()
            )
            reserved_qty = sum(r[0] for r in reserved)
            available = product.stock_quantity - reserved_qty
            result.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "required": line.quantity,
                    "available": available,
                    "sufficient": available >= line.quantity,
                }
            )
        return result

    def get_estimated_delivery(self, budget_id: int) -> datetime:
        budget = self.get_by_id(budget_id)
        if not budget.estimated_delivery:
            self._recalculate(budget)
            self.db.commit()
        return budget.estimated_delivery
