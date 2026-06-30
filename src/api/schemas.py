from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, EmailStr, Field, StrictInt, model_validator

from src.domain.enums import (
    BudgetStatus,
    InvoiceStatus,
    Priority,
    PurchaseRequestStatus,
    ReservationStatus,
    ServiceOrderStatus,
    StockWithdrawalStatus,
)

T = TypeVar("T")


class MessageResponse(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class CustomerCreate(BaseModel):
    name: str
    document: str
    email: EmailStr
    phone: str | None = None
    address: str = Field(..., min_length=1)


class CustomerUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = Field(default=None, min_length=1)


class CustomerDocumentAdd(BaseModel):
    document: str


class CustomerResponse(BaseModel):
    id: int
    name: str
    documents: list[str]
    email: str
    phone: str | None
    address: str
    created_at: datetime


class CustomerPublicResponse(BaseModel):
    id: int
    name: str


class CustomerPublicLookupRequest(BaseModel):
    document: str
    email: EmailStr | None = None
    phone: str | None = None
    plate: str | None = None

    @model_validator(mode="after")
    def require_second_factor(self):
        if self.email is None and self.phone is None and self.plate is None:
            raise ValueError("Informe email, phone ou plate")
        return self


class CnpjValidationResponse(BaseModel):
    valid: bool
    legal_name: str | None = None
    trade_name: str | None = None


class CpfValidationResponse(BaseModel):
    valid: bool
    formatted: str | None = None


class VehicleCreate(BaseModel):
    customer_id: int
    plate: str
    brand: str
    model: str
    year: int = Field(ge=1900, le=2100)


class VehicleUpdate(BaseModel):
    brand: str | None = None
    model: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)


class VehicleResponse(BaseModel):
    id: int
    customer_id: int
    plate: str
    brand: str
    model: str
    year: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ServiceCreate(BaseModel):
    name: str
    description: str | None = None
    base_price: float = Field(gt=0)
    estimated_hours: float = Field(default=1.0, gt=0)


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    base_price: float | None = Field(default=None, gt=0)
    estimated_hours: float | None = Field(default=None, gt=0)


class ServiceProductLineCreate(BaseModel):
    product_id: int
    quantity: int = Field(default=1, gt=0)


class ServiceProductLineResponse(BaseModel):
    id: int
    service_id: int
    product_id: int
    quantity: int

    model_config = {"from_attributes": True}


class ServiceResponse(BaseModel):
    id: int
    name: str
    description: str | None
    base_price: float
    estimated_hours: float
    created_at: datetime
    product_lines: list[ServiceProductLineResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    name: str
    sku: str
    unit_price: float = Field(gt=0)
    stock_quantity: int = Field(default=0, ge=0)
    description: str | None = None
    supplier_id: int = Field(gt=0)


class ProductUpdate(BaseModel):
    name: str | None = None
    unit_price: float | None = Field(default=None, gt=0)
    description: str | None = None
    supplier_id: int | None = Field(default=None, gt=0)


class StockUpdate(BaseModel):
    quantity: int


class ProductResponse(BaseModel):
    id: int
    name: str
    sku: str
    unit_price: float
    stock_quantity: int
    description: str | None
    supplier_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SupplierCreate(BaseModel):
    name: str
    document: str
    email: EmailStr
    phone: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None


class SupplierResponse(BaseModel):
    id: int
    name: str
    document: str
    email: str
    phone: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BudgetCreate(BaseModel):
    customer_id: int
    vehicle_id: int


class BudgetServiceLineCreate(BaseModel):
    service_id: int
    quantity: StrictInt = Field(default=1, gt=0)

class BudgetServiceLineResponse(BaseModel):
    id: int
    service_id: int
    service_name: str
    quantity: int
    unit_price: float


class BudgetProductLineCreate(BaseModel):
    product_id: int
    quantity: StrictInt = Field(default=1, gt=0)


class BudgetProductLineUpdate(BaseModel):
    quantity: StrictInt = Field(..., gt=0)


class BudgetServiceLineUpdate(BaseModel):
    quantity: StrictInt = Field(..., gt=0)


class BudgetProductLineResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    from_service: bool
    service_id: int | None = None


class BudgetResponse(BaseModel):
    id: int
    customer_id: int
    vehicle_id: int
    status: BudgetStatus
    total_price: float
    estimated_delivery: datetime | None
    approval_token: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AvailabilityItem(BaseModel):
    product_id: int
    product_name: str
    required: int
    available: int
    sufficient: bool


class ServiceOrderResponse(BaseModel):
    id: int
    budget_id: int | None
    customer_id: int
    vehicle_id: int
    status: ServiceOrderStatus
    priority: Priority
    mechanic_name: str | None
    total_price: float
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ServiceOrderPublicResponse(BaseModel):
    id: int
    status: ServiceOrderStatus
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ServiceOrderUpdate(BaseModel):
    mechanic_name: str | None = Field(default=None, min_length=1)
    priority: Priority | None = None

    @model_validator(mode="after")
    def require_change(self):
        if self.mechanic_name is None and self.priority is None:
            raise ValueError("Informe mechanic_name ou priority")
        return self


class AssignMechanicRequest(BaseModel):
    mechanic_name: str = Field(min_length=1)


class SetPriorityRequest(BaseModel):
    priority: Priority


class ReservationResponse(BaseModel):
    id: int
    service_order_id: int
    product_id: int
    quantity: int
    status: ReservationStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class PurchaseRequestCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    service_order_id: int | None = None


class PurchaseRequestResponse(BaseModel):
    id: int
    product_id: int
    supplier_id: int | None
    service_order_id: int | None
    quantity: int
    status: PurchaseRequestStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class GoodsReceiptCreate(BaseModel):
    quantity: int = Field(gt=0)


class StockWithdrawalCreate(BaseModel):
    service_order_id: int
    product_id: int
    quantity: int = Field(gt=0)


class StockWithdrawalResponse(BaseModel):
    id: int
    service_order_id: int
    product_id: int
    quantity: int
    status: StockWithdrawalStatus
    requested_at: datetime

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    id: int
    service_order_id: int
    amount: float
    status: InvoiceStatus
    paid_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AverageExecutionTimeResponse(BaseModel):
    average_hours: float
    sample_size: int
