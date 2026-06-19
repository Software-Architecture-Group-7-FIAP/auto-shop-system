from src.api.composition.inventory import compose_inventory_service
from src.api.composition.execution import compose_execution_service
from src.api.composition.service_orders import compose_service_order_service
from src.application.services.invoice_service import InvoiceService
from src.domain.enums import ServiceOrderStatus


def _setup_os_with_budget(db_session):
    from src.api.composition.budget_approval import compose_budget_approval_service
    from src.application.services.budget_service import BudgetService
    from src.application.services.customer_service import CustomerService
    from src.application.services.product_service import ProductService
    from src.application.services.service_catalog_service import ServiceCatalogService
    from src.application.services.vehicle_service import VehicleService
    from src.infrastructure.auth.tokens import create_signed_approval_token
    from src.infrastructure.database import BudgetModel
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

    customer = CustomerService(
        customers=SqlAlchemyCustomerRepository(db_session),
        uow=SqlAlchemyUnitOfWork(db_session),
    ).create("Test", "529.982.247-25", "t@test.com")
    vehicle_service = VehicleService(
        vehicles=SqlAlchemyVehicleRepository(db_session),
        customers=SqlAlchemyCustomerLookup(db_session),
        uow=SqlAlchemyUnitOfWork(db_session),
    )
    vehicle = vehicle_service.create(customer.id, "ABC1234", "Fiat", "Uno", 2020)
    service = ServiceCatalogService(
        services=SqlAlchemyServiceCatalogRepository(db_session),
        products=SqlAlchemyProductLookup(db_session),
        uow=SqlAlchemyUnitOfWork(db_session),
    ).create("Serv", None, 100.0)
    product = ProductService(
        products=SqlAlchemyProductRepository(db_session),
        uow=SqlAlchemyUnitOfWork(db_session),
    ).create("Part", "P-1", 10.0, 50)
    budget_service = BudgetService(
        budgets=SqlAlchemyBudgetRepository(db_session),
        customers=SqlAlchemyCustomerLookup(db_session),
        vehicles=SqlAlchemyVehicleOwnershipLookup(db_session),
        services=SqlAlchemyBudgetServiceCatalogLookup(db_session),
        products=SqlAlchemyBudgetProductLookup(db_session),
        reservations=SqlAlchemyReservationLookup(db_session),
        uow=SqlAlchemyUnitOfWork(db_session),
    )
    budget = budget_service.create(customer.id, vehicle.id)
    budget_service.add_service_line(budget.id, service.id)
    budget_service.add_product_line(budget.id, product.id, 1)
    token = create_signed_approval_token(budget.id)
    budget_model = db_session.query(BudgetModel).filter(BudgetModel.id == budget.id).first()
    assert budget_model is not None
    budget_model.approval_token = token
    db_session.commit()
    created_service_order = compose_budget_approval_service(db_session).approve_budget(token)
    os = compose_service_order_service(db_session).get_by_id(created_service_order.id)
    return os, product


def test_service_order_status_transitions(db_session):
    os, _ = _setup_os_with_budget(db_session)
    svc = compose_service_order_service(db_session)

    updated = svc.assign_mechanic(os.id, "Mecânico A")
    assert updated.status == ServiceOrderStatus.EM_DIAGNOSTICO

    exec_svc = compose_execution_service(db_session)
    exec_svc.start_service(os.id)
    exec_svc.finish_service(os.id)

    finished = svc.get_by_id(os.id)
    assert finished.status == ServiceOrderStatus.FINALIZADA


def test_invoice_and_payment(db_session):
    os, _ = _setup_os_with_budget(db_session)
    compose_service_order_service(db_session).assign_mechanic(os.id, "Mecânico B")
    compose_execution_service(db_session).start_service(os.id)
    compose_execution_service(db_session).finish_service(os.id)

    invoice_svc = InvoiceService(db_session)
    invoice = invoice_svc.create_invoice(os.id)
    assert invoice.amount == os.total_price

    paid = invoice_svc.pay_invoice(invoice.id)
    assert paid.status.value == "Paga"

    updated_os = compose_service_order_service(db_session).get_by_id(os.id)
    assert updated_os.status == ServiceOrderStatus.ENTREGUE


def test_inventory_reservation_and_purchase(db_session):
    os, product = _setup_os_with_budget(db_session)
    inv = compose_inventory_service(db_session)

    reservations = inv.create_reservations_for_os(os.id)
    assert len(reservations) >= 1

    pr = inv.create_purchase_request(product.id, 5, os.id)
    assert pr.quantity == 5

    receipt = inv.register_receipt(pr.id, 5)
    assert receipt.quantity == 5

    from src.infrastructure.database import ProductModel

    updated_product = db_session.query(ProductModel).filter(ProductModel.id == product.id).first()
    assert updated_product.stock_quantity >= 50
