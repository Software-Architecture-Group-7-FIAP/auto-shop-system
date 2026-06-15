from src.application.services.execution_service import ExecutionService
from src.application.services.inventory_service import InventoryService
from src.application.services.invoice_service import InvoiceService
from src.application.services.service_order_service import ServiceOrderService
from src.domain.enums import ServiceOrderStatus


def _setup_os_with_budget(db_session):
    from src.application.services.budget_approval_service import BudgetApprovalService
    from src.application.services.budget_service import BudgetService
    from src.application.services.customer_service import CustomerService
    from src.application.services.product_service import ProductService
    from src.application.services.service_catalog_service import ServiceCatalogService
    from src.application.services.vehicle_service import VehicleService
    from src.infrastructure.auth.tokens import create_signed_approval_token

    customer = CustomerService(db_session).create("Test", "529.982.247-25", "t@test.com")
    vehicle = VehicleService(db_session).create(customer.id, "ABC1234", "Fiat", "Uno", 2020)
    service = ServiceCatalogService(db_session).create("Serv", None, 100.0)
    product = ProductService(db_session).create("Part", "P-1", 10.0, 50)
    budget = BudgetService(db_session).create(customer.id, vehicle.id)
    BudgetService(db_session).add_service_line(budget.id, service.id)
    BudgetService(db_session).add_product_line(budget.id, product.id, 1)
    token = create_signed_approval_token(budget.id)
    budget.approval_token = token
    db_session.commit()
    os = BudgetApprovalService(db_session).approve_budget(token)
    return os, product


def test_service_order_status_transitions(db_session):
    os, _ = _setup_os_with_budget(db_session)
    svc = ServiceOrderService(db_session)

    updated = svc.assign_mechanic(os.id, "Mecânico A")
    assert updated.status == ServiceOrderStatus.EM_DIAGNOSTICO

    exec_svc = ExecutionService(db_session)
    exec_svc.start_service(os.id)
    exec_svc.finish_service(os.id)

    finished = svc.get_by_id(os.id)
    assert finished.status == ServiceOrderStatus.FINALIZADA


def test_invoice_and_payment(db_session):
    os, _ = _setup_os_with_budget(db_session)
    ServiceOrderService(db_session).assign_mechanic(os.id, "Mecânico B")
    ExecutionService(db_session).start_service(os.id)
    ExecutionService(db_session).finish_service(os.id)

    invoice_svc = InvoiceService(db_session)
    invoice = invoice_svc.create_invoice(os.id)
    assert invoice.amount == os.total_price

    paid = invoice_svc.pay_invoice(invoice.id)
    assert paid.status.value == "Paga"

    updated_os = ServiceOrderService(db_session).get_by_id(os.id)
    assert updated_os.status == ServiceOrderStatus.ENTREGUE


def test_inventory_reservation_and_purchase(db_session):
    os, product = _setup_os_with_budget(db_session)
    inv = InventoryService(db_session)

    reservations = inv.create_reservations_for_os(os.id)
    assert len(reservations) >= 1

    pr = inv.create_purchase_request(product.id, 5, os.id)
    assert pr.quantity == 5

    receipt = inv.register_receipt(pr.id, 5)
    assert receipt.quantity == 5

    from src.infrastructure.database import ProductModel

    updated_product = inv.db.query(ProductModel).filter(ProductModel.id == product.id).first()
    assert updated_product.stock_quantity >= 50
