from datetime import datetime

from src.application.ports.budget_lookups import (
    BudgetProductLookup,
    BudgetServiceCatalogLookup,
    ReservationLookup,
    VehicleOwnershipLookup,
)
from src.application.ports.customer_lookup import CustomerLookup
from src.application.ports.unit_of_work import UnitOfWork
from src.domain.budget.entity import (
    Budget,
    BudgetProductLine,
    BudgetServiceLine,
    ProductAvailability,
)
from src.domain.budget.repository import BudgetRepository
from src.domain.exceptions import NotFoundError


class BudgetService:
    def __init__(
        self,
        budgets: BudgetRepository,
        customers: CustomerLookup,
        vehicles: VehicleOwnershipLookup,
        services: BudgetServiceCatalogLookup,
        products: BudgetProductLookup,
        reservations: ReservationLookup,
        uow: UnitOfWork,
    ):
        self.budgets = budgets
        self.customers = customers
        self.vehicles = vehicles
        self.services = services
        self.products = products
        self.reservations = reservations
        self.uow = uow

    def create(self, customer_id: int, vehicle_id: int) -> Budget:
        if not self.customers.exists(customer_id):
            raise NotFoundError("Cliente não encontrado")
        if not self.vehicles.belongs_to_customer(vehicle_id, customer_id):
            raise NotFoundError("Veículo não encontrado para este cliente")
        created = self.budgets.add(Budget.create(customer_id, vehicle_id))
        self.uow.commit()
        return created

    def get_by_id(self, budget_id: int) -> Budget:
        budget = self.budgets.get_by_id(budget_id)
        if not budget:
            raise NotFoundError("Orçamento não encontrado")
        return budget

    def list_all(self) -> list[Budget]:
        return self.budgets.list_all()

    def add_service_line(
        self,
        budget_id: int,
        service_id: int,
        quantity: int = 1,
    ) -> BudgetServiceLine:
        budget = self.get_by_id(budget_id)
        service = self.services.get_service(service_id)
        if not service:
            raise NotFoundError("Serviço não encontrado")

        line = budget.add_service_line(service_id, quantity, service.base_price)
        created_line = self.budgets.add_service_line(line)
        budget.service_lines.append(created_line)

        for requirement in service.product_requirements:
            product = self.products.get_product(requirement.product_id)
            if product:
                product_line = budget.add_product_line(
                    product_id=product.id,
                    quantity=requirement.quantity * quantity,
                    unit_price=product.unit_price,
                    from_service=True,
                )
                budget.product_lines.append(self.budgets.add_product_line(product_line))

        self._recalculate(budget)
        self.budgets.save(budget)
        self.uow.commit()
        return created_line

    def add_product_line(
        self, budget_id: int, product_id: int, quantity: int = 1
    ) -> BudgetProductLine:
        budget = self.get_by_id(budget_id)
        product = self.products.get_product(product_id)
        if not product:
            raise NotFoundError("Produto não encontrado")

        line = budget.add_product_line(
            product_id=product.id,
            quantity=quantity,
            unit_price=product.unit_price,
            from_service=False,
        )
        created_line = self.budgets.add_product_line(line)
        budget.product_lines.append(created_line)
        self._recalculate(budget)
        self.budgets.save(budget)
        self.uow.commit()
        return created_line

    def get_all_product_lines(self, budget_id: int) -> list[dict]:
        self.get_by_id(budget_id)

        lines = self.budgets.get_all_product_lines(budget_id)
        result = []

        for line in lines:
            product = self.products.get_product(line.product_id)
            if not product:
                continue

            result.append(
                {
                    "id": line.id,
                    "product_id": line.product_id,
                    "product_name": product.name,
                    "quantity": line.quantity,
                    "unit_price": line.unit_price,
                    "from_service": line.from_service,
                }
            )

        return result


    def update_product_line(
            self,
            budget_id: int,
            line_id: int,
            quantity: int,
    ) -> dict:
        budget = self.get_by_id(budget_id)

        line = self.budgets.get_product_line(budget_id, line_id)
        if not line:
            raise NotFoundError("Linha de produto não encontrada")

        line.quantity = quantity
        updated_line = self.budgets.update_product_line(line)

        for budget_line in budget.product_lines:
            if budget_line.id == line_id:
                budget_line.quantity = quantity
                break

        self._recalculate(budget)
        self.budgets.save(budget)
        self.uow.commit()

        product = self.products.get_product(updated_line.product_id)
        if not product:
            raise NotFoundError("Produto não encontrado")

        return {
            "id": updated_line.id,
            "product_id": updated_line.product_id,
            "product_name": product.name,
            "quantity": updated_line.quantity,
            "unit_price": updated_line.unit_price,
            "from_service": updated_line.from_service,
        }

    def remove_product_line(self, budget_id: int, line_id: int) -> None:
        line = self.budgets.get_product_line(budget_id, line_id)
        if not line:
            raise NotFoundError("Linha de produto não encontrada")
        self.budgets.delete_product_line(line)
        self.uow.commit()

    def _recalculate(self, budget: Budget) -> None:
        service_hours: dict[int, float] = {}
        for line in budget.service_lines:
            service = self.services.get_service(line.service_id)
            if service:
                service_hours[line.service_id] = service.estimated_hours
        budget.recalculate(service_hours)

    def check_availability(self, budget_id: int) -> list[dict]:
        budget = self.get_by_id(budget_id)
        result: list[ProductAvailability] = []
        for line in budget.product_lines:
            product = self.products.get_product(line.product_id)
            if not product:
                continue
            available = (
                product.stock_quantity
                - self.reservations.active_quantity_for_product(product.id)
            )
            result.append(
                ProductAvailability(
                    product_id=product.id,
                    product_name=product.name,
                    required=line.quantity,
                    available=available,
                    sufficient=available >= line.quantity,
                )
            )
        return [availability.as_dict() for availability in result]

    def get_estimated_delivery(self, budget_id: int) -> datetime:
        budget = self.get_by_id(budget_id)
        if not budget.estimated_delivery:
            self._recalculate(budget)
            self.budgets.save(budget)
            self.uow.commit()
        return budget.estimated_delivery
