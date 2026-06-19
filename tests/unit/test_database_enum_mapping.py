from src.domain.enums import (
    BudgetStatus,
    InvoiceStatus,
    Priority,
    PurchaseRequestStatus,
    ReservationStatus,
    ServiceOrderStatus,
    StockWithdrawalStatus,
)
from src.infrastructure.database import (
    BudgetModel,
    InvoiceModel,
    PurchaseRequestModel,
    ReservationModel,
    ServiceOrderModel,
    StockWithdrawalModel,
)


def enum_values(enum_cls):
    return [member.value for member in enum_cls]


def test_database_enums_persist_enum_values_not_names():
    assert BudgetModel.__table__.c.status.type.enums == enum_values(BudgetStatus)
    assert ServiceOrderModel.__table__.c.status.type.enums == enum_values(ServiceOrderStatus)
    assert ServiceOrderModel.__table__.c.priority.type.enums == enum_values(Priority)
    assert ReservationModel.__table__.c.status.type.enums == enum_values(ReservationStatus)
    assert PurchaseRequestModel.__table__.c.status.type.enums == enum_values(
        PurchaseRequestStatus
    )
    assert StockWithdrawalModel.__table__.c.status.type.enums == enum_values(
        StockWithdrawalStatus
    )
    assert InvoiceModel.__table__.c.status.type.enums == enum_values(InvoiceStatus)
