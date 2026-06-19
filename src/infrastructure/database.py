from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from src.config import settings
from src.domain.enums import (
    BudgetStatus,
    InvoiceStatus,
    Priority,
    PurchaseRequestStatus,
    ReservationStatus,
    ServiceOrderStatus,
    StockWithdrawalStatus,
)


class Base(DeclarativeBase):
    pass


def enum_values(enum_cls):
    return [member.value for member in enum_cls]


def db_enum(enum_cls):
    return Enum(enum_cls, values_callable=enum_values)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CustomerModel(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    person_type: Mapped[str] = mapped_column(String(2))
    document: Mapped[str] = mapped_column(String(14), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    address: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    vehicles: Mapped[list["VehicleModel"]] = relationship(back_populates="customer")


class VehicleModel(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    plate: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    brand: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    year: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped["CustomerModel"] = relationship(back_populates="vehicles")


class SupplierModel(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    document: Mapped[str] = mapped_column(String(14), unique=True)
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProductModel(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True)
    unit_price: Mapped[float] = mapped_column(Float)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ServiceModel(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    base_price: Mapped[float] = mapped_column(Float)
    estimated_hours: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    product_lines: Mapped[list["ServiceProductLineModel"]] = relationship(
        back_populates="service", cascade="all, delete-orphan"
    )


class ServiceProductLineModel(Base):
    __tablename__ = "service_product_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    service: Mapped["ServiceModel"] = relationship(back_populates="product_lines")


class BudgetModel(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    status: Mapped[BudgetStatus] = mapped_column(db_enum(BudgetStatus), default=BudgetStatus.DRAFT)
    total_price: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_delivery: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approval_token: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    service_lines: Mapped[list["BudgetServiceLineModel"]] = relationship(
        back_populates="budget", cascade="all, delete-orphan"
    )
    product_lines: Mapped[list["BudgetProductLineModel"]] = relationship(
        back_populates="budget", cascade="all, delete-orphan"
    )


class BudgetServiceLineModel(Base):
    __tablename__ = "budget_service_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.id"))
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float)

    budget: Mapped["BudgetModel"] = relationship(back_populates="service_lines")


class BudgetProductLineModel(Base):
    __tablename__ = "budget_product_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float)
    from_service: Mapped[bool] = mapped_column(Boolean, default=False)

    budget: Mapped["BudgetModel"] = relationship(back_populates="product_lines")


class ServiceOrderModel(Base):
    __tablename__ = "service_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    budget_id: Mapped[int | None] = mapped_column(ForeignKey("budgets.id"), nullable=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    status: Mapped[ServiceOrderStatus] = mapped_column(
        db_enum(ServiceOrderStatus), default=ServiceOrderStatus.RECEBIDA
    )
    priority: Mapped[Priority] = mapped_column(db_enum(Priority), default=Priority.NORMAL)
    mechanic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_price: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    service_lines: Mapped[list["ServiceOrderServiceLineModel"]] = relationship(
        back_populates="service_order", cascade="all, delete-orphan"
    )
    product_lines: Mapped[list["ServiceOrderProductLineModel"]] = relationship(
        back_populates="service_order", cascade="all, delete-orphan"
    )


class ServiceOrderServiceLineModel(Base):
    __tablename__ = "service_order_service_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_order_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id"))
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float)

    service_order: Mapped["ServiceOrderModel"] = relationship(back_populates="service_lines")


class ServiceOrderProductLineModel(Base):
    __tablename__ = "service_order_product_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_order_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float)

    service_order: Mapped["ServiceOrderModel"] = relationship(back_populates="product_lines")


class ReservationModel(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_order_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[ReservationStatus] = mapped_column(
        db_enum(ReservationStatus), default=ReservationStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PurchaseRequestModel(Base):
    __tablename__ = "purchase_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    service_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_orders.id"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[PurchaseRequestStatus] = mapped_column(
        db_enum(PurchaseRequestStatus), default=PurchaseRequestStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GoodsReceiptModel(Base):
    __tablename__ = "goods_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_request_id: Mapped[int] = mapped_column(ForeignKey("purchase_requests.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StockWithdrawalModel(Base):
    __tablename__ = "stock_withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_order_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[StockWithdrawalStatus] = mapped_column(
        db_enum(StockWithdrawalStatus), default=StockWithdrawalStatus.PENDING
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class InvoiceModel(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_order_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id"), unique=True)
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[InvoiceStatus] = mapped_column(
        db_enum(InvoiceStatus), default=InvoiceStatus.PENDING
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
