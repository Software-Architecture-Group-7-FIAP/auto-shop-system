from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from src.domain.enums import Priority, ServiceOrderStatus


class ServiceOrderProductLineResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: float

    model_config = {"from_attributes": True}


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


class OverrideStatusRequest(BaseModel):
    status: ServiceOrderStatus
    reason: str = Field(min_length=1)
