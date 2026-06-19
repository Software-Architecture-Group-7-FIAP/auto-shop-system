from src.application.services.budget_service import BudgetService
from src.application.services.customer_service import CustomerService
from src.application.services.product_service import ProductService
from src.application.services.service_catalog_service import ServiceCatalogService
from src.application.services.vehicle_service import VehicleService
from src.infrastructure.persistence.budget_repository import (
    SqlAlchemyBudgetProductLookup,
    SqlAlchemyBudgetRepository,
    SqlAlchemyBudgetServiceCatalogLookup,
    SqlAlchemyReservationLookup,
    SqlAlchemyVehicleOwnershipLookup,
)
from src.infrastructure.persistence.customer_repository import (
    SqlAlchemyCustomerLookup,
    SqlAlchemyCustomerRepository,
)
from src.infrastructure.persistence.product_repository import (
    SqlAlchemyProductLookup,
    SqlAlchemyProductRepository,
)
from src.infrastructure.persistence.service_catalog_repository import (
    SqlAlchemyServiceCatalogRepository,
)
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.infrastructure.persistence.vehicle_repository import SqlAlchemyVehicleRepository


def _customer_service(db_session):
    return CustomerService(
        customers=SqlAlchemyCustomerRepository(db_session),
        uow=SqlAlchemyUnitOfWork(db_session),
    )


def _vehicle_service(db_session):
    return VehicleService(
        vehicles=SqlAlchemyVehicleRepository(db_session),
        customers=SqlAlchemyCustomerLookup(db_session),
        uow=SqlAlchemyUnitOfWork(db_session),
    )


def _service_catalog_service(db_session):
    return ServiceCatalogService(
        services=SqlAlchemyServiceCatalogRepository(db_session),
        products=SqlAlchemyProductLookup(db_session),
        uow=SqlAlchemyUnitOfWork(db_session),
    )


def _product_service(db_session):
    return ProductService(
        products=SqlAlchemyProductRepository(db_session),
        uow=SqlAlchemyUnitOfWork(db_session),
    )


def _budget_service(db_session):
    return BudgetService(
        budgets=SqlAlchemyBudgetRepository(db_session),
        customers=SqlAlchemyCustomerLookup(db_session),
        vehicles=SqlAlchemyVehicleOwnershipLookup(db_session),
        services=SqlAlchemyBudgetServiceCatalogLookup(db_session),
        products=SqlAlchemyBudgetProductLookup(db_session),
        reservations=SqlAlchemyReservationLookup(db_session),
        uow=SqlAlchemyUnitOfWork(db_session),
    )


def test_budget_total_calculation(db_session):
    customer = _customer_service(db_session).create(
        "João", "529.982.247-25", "joao@test.com"
    )
    vehicle = _vehicle_service(db_session).create(
        customer.id, "ABC1234", "Fiat", "Uno", 2020
    )
    service = _service_catalog_service(db_session).create(
        "Troca de óleo", None, 100.0, 2.0
    )
    product = _product_service(db_session).create(
        "Óleo 5W30", "OLEO-001", 50.0, 10
    )

    budget_svc = _budget_service(db_session)
    budget = budget_svc.create(customer.id, vehicle.id)
    budget_svc.add_service_line(budget.id, service.id, 1)
    budget_svc.add_product_line(budget.id, product.id, 2)

    updated = budget_svc.get_by_id(budget.id)
    assert updated.total_price == 200.0
