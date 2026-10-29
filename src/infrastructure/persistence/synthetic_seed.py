from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.application.seeding.dataset import CUSTOMERS, ORDERS, PRODUCTS, SERVICES
from src.domain.auth.entity import UserRole
from src.domain.enums import ServiceOrderStatus
from src.domain.service_order.entity import ServiceOrder
from src.infrastructure.auth.jwt import BcryptPasswordHasher
from src.infrastructure.database import (
    CustomerDocumentModel,
    CustomerModel,
    ProductModel,
    ServiceModel,
    ServiceOrderModel,
    ServiceOrderProductLineModel,
    ServiceOrderServiceLineModel,
    ServiceOrderStatusHistoryModel,
    ServiceProductLineModel,
    SupplierModel,
    UserModel,
    VehicleModel,
)


SEED_LOCK_KEY = 7_349_842
FIXED_TIMESTAMP = datetime(2026, 1, 15, 12, 0, 0)


class SyntheticSeedConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class SyntheticSeedResult:
    created: bool
    counts: dict[str, int]


def _assert_matches(record_name: str, actual: tuple, expected: tuple) -> None:
    if actual != expected:
        raise SyntheticSeedConflictError(
            f"Synthetic seed conflict for {record_name}; existing data was preserved"
        )


def _lock_seed(session: Session) -> None:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": SEED_LOCK_KEY})


def _build_service_order(
    item,
    customer_id: int,
    vehicle_id: int,
    mechanic_marker: str,
    offset: int,
) -> ServiceOrder:
    started_at = FIXED_TIMESTAMP + timedelta(days=offset, minutes=1)
    aggregate = ServiceOrder(
        id=None,
        budget_id=None,
        customer_id=customer_id,
        vehicle_id=vehicle_id,
        priority=item.priority,
        total_price=item.total_price,
        created_at=FIXED_TIMESTAMP,
    )
    if item.status != ServiceOrderStatus.RECEBIDA:
        aggregate.assign_mechanic(mechanic_marker)
        aggregate.submit_for_approval()
        aggregate.approve_current_budget()
        aggregate.record_queue_entry()
        aggregate.start_execution(started_at)
        if item.status == ServiceOrderStatus.ENTREGUE:
            aggregate.finish_execution(started_at + timedelta(hours=2))
            aggregate.mark_delivered()
    if aggregate.status != item.status:
        raise SyntheticSeedConflictError(
            f"Synthetic seed status path is invalid for order {item.key}"
        )
    return aggregate


def _expected_history(
    aggregate: ServiceOrder,
    order_key: str,
    offset: int,
) -> list[tuple]:
    history = []
    for index, transition in enumerate(aggregate.status_history):
        if transition.transition_type == "execution_started":
            occurred_at = aggregate.started_at
        elif transition.transition_type == "execution_finished":
            occurred_at = aggregate.finished_at
        elif transition.transition_type == "delivered":
            occurred_at = aggregate.finished_at + timedelta(seconds=1)
        else:
            occurred_at = FIXED_TIMESTAMP + timedelta(days=offset, seconds=index)
        if occurred_at is None:
            raise SyntheticSeedConflictError(
                f"Synthetic seed transition timestamp is missing for order {order_key}"
            )
        history.append(
            (
                transition.from_status,
                transition.to_status,
                transition.transition_type,
                f"synthetic:f3v1:{order_key}:{index}",
                occurred_at,
            )
        )
    return history


def seed_fase3_dataset(session: Session, admin_password: str) -> SyntheticSeedResult:
    _lock_seed(session)
    created = False

    admin = session.query(UserModel).filter(UserModel.username == "avaliador").one_or_none()
    if admin is None:
        admin = UserModel(
            username="avaliador",
            email="avaliador@demo.invalid",
            hashed_password=BcryptPasswordHasher().hash(admin_password),
            is_active=True,
            role=UserRole.ADMIN,
            created_at=FIXED_TIMESTAMP,
        )
        session.add(admin)
        created = True
    else:
        _assert_matches(
            "user:avaliador",
            (admin.email, admin.is_active, admin.role),
            ("avaliador@demo.invalid", True, UserRole.ADMIN),
        )

    customers: dict[str, CustomerModel] = {}
    vehicles: dict[str, VehicleModel] = {}
    for item in CUSTOMERS:
        document = (
            session.query(CustomerDocumentModel)
            .filter(CustomerDocumentModel.document == item.document)
            .one_or_none()
        )
        customer = document.customer if document is not None else None
        if customer is None:
            customer = CustomerModel(
                name=item.name,
                email=item.email,
                phone=item.phone,
                address=item.address,
                status=item.status,
                created_at=FIXED_TIMESTAMP,
                updated_at=FIXED_TIMESTAMP,
            )
            customer.documents.append(
                CustomerDocumentModel(document=item.document, created_at=FIXED_TIMESTAMP)
            )
            session.add(customer)
            session.flush()
            created = True
        else:
            _assert_matches(
                f"customer:{item.document[-4:]}",
                (customer.name, customer.email, customer.phone, customer.address, customer.status),
                (item.name, item.email, item.phone, item.address, item.status),
            )
        customers[item.document] = customer

        vehicle = (
            session.query(VehicleModel)
            .filter(VehicleModel.customer_id == customer.id, VehicleModel.plate == item.plate)
            .one_or_none()
        )
        if vehicle is None:
            vehicle = VehicleModel(
                customer_id=customer.id,
                plate=item.plate,
                state=item.vehicle_state,
                city=item.vehicle_city,
                color=item.vehicle_color,
                brand=item.vehicle_brand,
                model=item.vehicle_model,
                year=item.vehicle_year,
                created_at=FIXED_TIMESTAMP,
            )
            session.add(vehicle)
            session.flush()
            created = True
        else:
            _assert_matches(
                f"vehicle:{item.plate}",
                (vehicle.state, vehicle.city, vehicle.color, vehicle.brand, vehicle.model, vehicle.year),
                (
                    item.vehicle_state,
                    item.vehicle_city,
                    item.vehicle_color,
                    item.vehicle_brand,
                    item.vehicle_model,
                    item.vehicle_year,
                ),
            )
        vehicles[item.document] = vehicle

    supplier = (
        session.query(SupplierModel)
        .filter(SupplierModel.document == "11222333000181")
        .one_or_none()
    )
    supplier_values = (
        "FORNECEDOR SINTETICO",
        "fornecedor@demo.invalid",
        "00000000004",
    )
    if supplier is None:
        supplier = SupplierModel(
            name=supplier_values[0],
            document="11222333000181",
            email=supplier_values[1],
            phone=supplier_values[2],
            created_at=FIXED_TIMESTAMP,
        )
        session.add(supplier)
        session.flush()
        created = True
    else:
        _assert_matches(
            "supplier:synthetic",
            (supplier.name, supplier.email, supplier.phone),
            supplier_values,
        )

    products: dict[str, ProductModel] = {}
    for item in PRODUCTS:
        product = session.query(ProductModel).filter(ProductModel.sku == item.sku).one_or_none()
        if product is None:
            product = ProductModel(
                name=item.name,
                description=item.description,
                sku=item.sku,
                unit_price=item.unit_price,
                stock_quantity=item.stock_quantity,
                supplier_id=supplier.id,
                created_at=FIXED_TIMESTAMP,
            )
            session.add(product)
            session.flush()
            created = True
        else:
            _assert_matches(
                f"product:{item.sku}",
                (
                    product.name,
                    product.description,
                    product.unit_price,
                    product.stock_quantity,
                    product.supplier_id,
                ),
                (
                    item.name,
                    item.description,
                    item.unit_price,
                    item.stock_quantity,
                    supplier.id,
                ),
            )
        products[item.sku] = product

    services: dict[str, ServiceModel] = {}
    for item in SERVICES:
        service = session.query(ServiceModel).filter(ServiceModel.name == item.name).one_or_none()
        if service is None:
            service = ServiceModel(
                name=item.name,
                description=item.description,
                base_price=item.base_price,
                estimated_hours=item.estimated_hours,
                created_at=FIXED_TIMESTAMP,
            )
            session.add(service)
            session.flush()
            created = True
        else:
            _assert_matches(
                f"service:{item.key}",
                (service.description, service.base_price, service.estimated_hours),
                (item.description, item.base_price, item.estimated_hours),
            )
        services[item.key] = service
        product = products[item.product_sku]
        line = (
            session.query(ServiceProductLineModel)
            .filter(
                ServiceProductLineModel.service_id == service.id,
                ServiceProductLineModel.product_id == product.id,
            )
            .one_or_none()
        )
        if line is None:
            session.add(
                ServiceProductLineModel(
                    service_id=service.id,
                    product_id=product.id,
                    quantity=item.product_quantity,
                )
            )
            created = True
        else:
            _assert_matches(
                f"service-product:{item.key}",
                (line.quantity,),
                (item.product_quantity,),
            )

    for offset, item in enumerate(ORDERS):
        marker = f"SINTETICO:F3V1:{item.key.upper()}"
        customer = customers[item.customer_document]
        vehicle = vehicles[item.customer_document]
        service = services[item.service_key]
        product = products[item.product_sku]
        aggregate = _build_service_order(
            item,
            customer_id=customer.id,
            vehicle_id=vehicle.id,
            mechanic_marker=marker,
            offset=offset,
        )
        expected_history = _expected_history(aggregate, item.key, offset)
        order = (
            session.query(ServiceOrderModel)
            .filter(ServiceOrderModel.mechanic_name == marker)
            .one_or_none()
        )
        if order is None and item.status == ServiceOrderStatus.RECEBIDA:
            order = (
                session.query(ServiceOrderModel)
                .filter(
                    ServiceOrderModel.customer_id == customer.id,
                    ServiceOrderModel.vehicle_id == vehicle.id,
                    ServiceOrderModel.budget_id.is_(None),
                    ServiceOrderModel.created_at == FIXED_TIMESTAMP,
                )
                .one_or_none()
            )
        if order is None:
            order = ServiceOrderModel(
                customer_id=customer.id,
                vehicle_id=vehicle.id,
                status=aggregate.status,
                priority=aggregate.priority,
                mechanic_name=aggregate.mechanic_name,
                total_price=aggregate.total_price,
                started_at=aggregate.started_at,
                finished_at=aggregate.finished_at,
                created_at=FIXED_TIMESTAMP,
                updated_at=FIXED_TIMESTAMP,
            )
            order.service_lines.append(
                ServiceOrderServiceLineModel(
                    service_id=service.id,
                    quantity=1,
                    unit_price=service.base_price,
                )
            )
            order.product_lines.append(
                ServiceOrderProductLineModel(
                    product_id=product.id,
                    quantity=1,
                    unit_price=product.unit_price,
                )
            )
            for from_status, to_status, transition_type, request_id, occurred_at in expected_history:
                order.status_history.append(
                    ServiceOrderStatusHistoryModel(
                        from_status=from_status,
                        to_status=to_status,
                        transition_type=transition_type,
                        request_id=request_id,
                        occurred_at=occurred_at,
                    )
                )
            session.add(order)
            created = True
        else:
            _assert_matches(
                f"order:{item.key}",
                (
                    order.customer_id,
                    order.vehicle_id,
                    order.status,
                    order.priority,
                    order.total_price,
                    order.mechanic_name,
                    order.started_at,
                    order.finished_at,
                ),
                (
                    customer.id,
                    vehicle.id,
                    aggregate.status,
                    aggregate.priority,
                    aggregate.total_price,
                    aggregate.mechanic_name,
                    aggregate.started_at,
                    aggregate.finished_at,
                ),
            )
            actual_service_lines = sorted(
                (line.service_id, line.quantity, line.unit_price)
                for line in order.service_lines
            )
            _assert_matches(
                f"order-service-lines:{item.key}",
                actual_service_lines,
                [(service.id, 1, service.base_price)],
            )
            actual_product_lines = sorted(
                (line.product_id, line.quantity, line.unit_price)
                for line in order.product_lines
            )
            _assert_matches(
                f"order-product-lines:{item.key}",
                actual_product_lines,
                [(product.id, 1, product.unit_price)],
            )
            actual_history = [
                (
                    transition.from_status,
                    transition.to_status,
                    transition.transition_type,
                    transition.request_id,
                    transition.occurred_at,
                )
                for transition in order.status_history
            ]
            _assert_matches(
                f"order-status-history:{item.key}",
                actual_history,
                expected_history,
            )

    session.commit()
    return SyntheticSeedResult(
        created=created,
        counts={
            "customers": len(CUSTOMERS),
            "orders": len(ORDERS),
            "products": len(PRODUCTS),
            "services": len(SERVICES),
            "suppliers": 1,
            "users": 1,
            "vehicles": len(CUSTOMERS),
        },
    )
