from dataclasses import replace

import pytest

from src.application.ports.budget_lookups import (
    BudgetProductDetails,
    BudgetServiceDetails,
    BudgetServiceProductRequirement,
)
from src.application.services.budget_service import BudgetService
from src.domain.budget.entity import Budget, BudgetProductLine, BudgetServiceLine
from src.domain.exceptions import NotFoundError, ValidationError


class InMemoryBudgetRepository:
    def __init__(self):
        self.budgets: dict[int, Budget] = {}
        self.next_budget_id = 1
        self.next_service_line_id = 1
        self.next_product_line_id = 1

    def add(self, budget: Budget) -> Budget:
        created = replace(budget, id=self.next_budget_id)
        self.budgets[self.next_budget_id] = created
        self.next_budget_id += 1
        return created

    def get_by_id(self, budget_id: int) -> Budget | None:
        return self.budgets.get(budget_id)

    def list_all(self) -> list[Budget]:
        return list(self.budgets.values())

    def add_service_line(self, line: BudgetServiceLine) -> BudgetServiceLine:
        created = replace(line, id=self.next_service_line_id)
        self.next_service_line_id += 1
        return created

    def add_product_line(self, line: BudgetProductLine) -> BudgetProductLine:
        created = replace(line, id=self.next_product_line_id)
        self.next_product_line_id += 1
        return created

    def get_product_line(self, budget_id: int, line_id: int) -> BudgetProductLine | None:
        budget = self.budgets.get(budget_id)
        if not budget:
            return None
        return next((line for line in budget.product_lines if line.id == line_id), None)

    def update_product_line(self, line: BudgetProductLine) -> BudgetProductLine:
        return line

    def get_service_line(self, budget_id: int, service_id: int) -> BudgetServiceLine | None:
        budget = self.budgets.get(budget_id)
        if not budget:
            return None
        return next((line for line in budget.service_lines if line.id == service_id), None)

    def update_service_line(self, line: BudgetServiceLine) -> BudgetServiceLine:
        return line

    def delete_service_line(self, line: BudgetServiceLine) -> None:
        for current in self.budgets.values():
            current.service_lines = [existing for existing in current.service_lines if existing.id != line.id]

    def delete_product_line(self, line: BudgetProductLine) -> None:
        for current in self.budgets.values():
            current.product_lines = [existing for existing in current.product_lines if existing.id != line.id]

    def save(self, budget: Budget) -> Budget:
        assert budget.id is not None

        for line in budget.service_lines:
            if line.id is None:
                persisted = self.add_service_line(line)
                line.id = persisted.id
            else:
                self.update_service_line(line)

        for line in budget.product_lines:
            if line.id is None:
                persisted = self.add_product_line(line)
                line.id = persisted.id
            else:
                self.update_product_line(line)

        self.budgets[budget.id] = budget
        return budget


class InMemoryCustomerLookup:
    def __init__(self, existing_ids: set[int]):
        self.existing_ids = existing_ids

    def exists(self, customer_id: int) -> bool:
        return customer_id in self.existing_ids


class InMemoryVehicleOwnershipLookup:
    def __init__(self, ownerships: set[tuple[int, int]]):
        self.ownerships = ownerships

    def belongs_to_customer(self, vehicle_id: int, customer_id: int) -> bool:
        return (vehicle_id, customer_id) in self.ownerships


class InMemoryServiceCatalogLookup:
    def __init__(self, services: dict[int, BudgetServiceDetails]):
        self.services = services

    def get_service(self, service_id: int) -> BudgetServiceDetails | None:
        return self.services.get(service_id)


class InMemoryProductLookup:
    def __init__(self, products: dict[int, BudgetProductDetails]):
        self.products = products

    def get_product(self, product_id: int) -> BudgetProductDetails | None:
        return self.products.get(product_id)


class InMemoryReservationLookup:
    def __init__(self, reserved: dict[int, int] | None = None):
        self.reserved = reserved or {}

    def active_quantity_for_product(self, product_id: int) -> int:
        return self.reserved.get(product_id, 0)


class FakeUnitOfWork:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def make_budget_service(
    repository: InMemoryBudgetRepository | None = None,
    customers: InMemoryCustomerLookup | None = None,
    vehicles: InMemoryVehicleOwnershipLookup | None = None,
    services: InMemoryServiceCatalogLookup | None = None,
    products: InMemoryProductLookup | None = None,
    reservations: InMemoryReservationLookup | None = None,
    uow: FakeUnitOfWork | None = None,
) -> BudgetService:
    return BudgetService(
        budgets=repository or InMemoryBudgetRepository(),
        customers=customers or InMemoryCustomerLookup({1}),
        vehicles=vehicles or InMemoryVehicleOwnershipLookup({(2, 1)}),
        services=services or InMemoryServiceCatalogLookup({}),
        products=products or InMemoryProductLookup({}),
        reservations=reservations or InMemoryReservationLookup(),
        uow=uow or FakeUnitOfWork(),
    )


def test_budget_service_creates_budget_without_sqlalchemy():
    uow = FakeUnitOfWork()
    service = make_budget_service(uow=uow)

    budget = service.create(customer_id=1, vehicle_id=2)

    assert budget.id == 1
    assert budget.customer_id == 1
    assert budget.vehicle_id == 2
    assert uow.commits == 1


def test_budget_service_rejects_missing_customer():
    service = make_budget_service(customers=InMemoryCustomerLookup(set()))

    with pytest.raises(NotFoundError):
        service.create(customer_id=1, vehicle_id=2)


def test_budget_service_rejects_vehicle_from_another_customer():
    service = make_budget_service(vehicles=InMemoryVehicleOwnershipLookup(set()))

    with pytest.raises(NotFoundError):
        service.create(customer_id=1, vehicle_id=2)


def test_budget_service_adds_service_line_and_derived_products():
    repository = InMemoryBudgetRepository()
    service = make_budget_service(
        repository=repository,
        services=InMemoryServiceCatalogLookup(
            {
                10: BudgetServiceDetails(
                    id=10,
                    name="Óleo",
                    base_price=100.0,
                    estimated_hours=2.0,
                    product_requirements=(
                        BudgetServiceProductRequirement(product_id=20, quantity=2),
                    ),
                )
            }
        ),
        products=InMemoryProductLookup(
            {20: BudgetProductDetails(id=20, name="Óleo", unit_price=25.0, stock_quantity=10)}
        ),
    )
    budget = service.create(customer_id=1, vehicle_id=2)

    line = service.add_service_line(budget.id, service_id=10, quantity=2)
    updated = repository.get_by_id(budget.id)

    assert line.id == 1
    assert updated.total_price == 300.0
    assert len(updated.service_lines) == 1
    assert len(updated.product_lines) == 1
    assert updated.product_lines[0].quantity == 4
    assert updated.product_lines[0].from_service is True


def test_budget_service_adds_manual_product_line():
    repository = InMemoryBudgetRepository()
    service = make_budget_service(
        repository=repository,
        products=InMemoryProductLookup(
            {20: BudgetProductDetails(id=20, name="Óleo", unit_price=25.0, stock_quantity=10)}
        ),
    )
    budget = service.create(customer_id=1, vehicle_id=2)

    line = service.add_product_line(budget.id, product_id=20, quantity=3)
    updated = repository.get_by_id(budget.id)

    assert line.id == 1
    assert updated.total_price == 75.0
    assert updated.product_lines[0].from_service is False


def test_budget_service_checks_availability():
    repository = InMemoryBudgetRepository()
    service = make_budget_service(
        repository=repository,
        products=InMemoryProductLookup(
            {20: BudgetProductDetails(id=20, name="Óleo", unit_price=25.0, stock_quantity=10)}
        ),
        reservations=InMemoryReservationLookup({20: 4}),
    )
    budget = service.create(customer_id=1, vehicle_id=2)
    service.add_product_line(budget.id, product_id=20, quantity=3)

    availability = service.check_availability(budget.id)

    assert availability == [
        {
            "product_id": 20,
            "product_name": "Óleo",
            "required": 3,
            "available": 6,
            "sufficient": True,
        }
    ]


def test_budget_service_rejects_negative_quantity_for_product_line_update():
    repository = InMemoryBudgetRepository()
    service = make_budget_service(
        repository=repository,
        products=InMemoryProductLookup(
            {20: BudgetProductDetails(id=20, name="Óleo", unit_price=25.0, stock_quantity=10)}
        ),
    )
    budget = service.create(customer_id=1, vehicle_id=2)
    line = service.add_product_line(budget.id, product_id=20, quantity=3)

    with pytest.raises(ValidationError, match="Quantidade deve ser maior que zero"):
        service.update_product_line(budget.id, line.id, quantity=-1)


def test_budget_service_rejects_negative_quantity_for_service_line_update():
    repository = InMemoryBudgetRepository()
    service = make_budget_service(
        repository=repository,
        services=InMemoryServiceCatalogLookup(
            {
                10: BudgetServiceDetails(
                    id=10,
                    name="Troca de óleo",
                    base_price=100.0,
                    estimated_hours=1.5,
                    product_requirements=(),
                )
            }
        ),
    )
    budget = service.create(customer_id=1, vehicle_id=2)
    line = service.add_service_line(budget.id, service_id=10, quantity=1)

    with pytest.raises(ValidationError, match="Quantidade deve ser maior que zero"):
        service.update_service_line(budget.id, line.id, quantity=0)


def test_budget_service_rejects_excessive_quantity_for_service_line_update():
    repository = InMemoryBudgetRepository()
    service = make_budget_service(
        repository=repository,
        services=InMemoryServiceCatalogLookup(
            {
                10: BudgetServiceDetails(
                    id=10,
                    name="Troca de óleo",
                    base_price=100.0,
                    estimated_hours=1.5,
                    product_requirements=(),
                )
            }
        ),
    )
    budget = service.create(customer_id=1, vehicle_id=2)
    line = service.add_service_line(budget.id, service_id=10, quantity=1)

    with pytest.raises(ValidationError, match="Quantidade muito grande"):
        service.update_service_line(budget.id, line.id, quantity=1_000_000)


def test_budget_service_removes_service_line_and_derived_products():
    repository = InMemoryBudgetRepository()
    service = make_budget_service(
        repository=repository,
        services=InMemoryServiceCatalogLookup(
            {
                10: BudgetServiceDetails(
                    id=10,
                    name="Troca de óleo",
                    base_price=100.0,
                    estimated_hours=1.5,
                    product_requirements=(
                        BudgetServiceProductRequirement(product_id=20, quantity=2),
                    ),
                )
            }
        ),
        products=InMemoryProductLookup(
            {20: BudgetProductDetails(id=20, name="Óleo", unit_price=25.0, stock_quantity=10)}
        ),
    )
    budget = service.create(customer_id=1, vehicle_id=2)
    line = service.add_service_line(budget.id, service_id=10, quantity=2)
    service.add_product_line(budget.id, product_id=20, quantity=3)

    service.remove_service_line(budget.id, line.id)
    updated_budget = repository.get_by_id(budget.id)

    assert len(updated_budget.service_lines) == 0
    assert updated_budget.total_price == 75.0
    assert len(updated_budget.product_lines) == 1
    assert updated_budget.product_lines[0].product_id == 20
    assert updated_budget.product_lines[0].quantity == 3
    assert updated_budget.product_lines[0].from_service is False
