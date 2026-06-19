from typing import Protocol

from src.domain.execution.entity import StockWithdrawal


class StockWithdrawalRepository(Protocol):
    def add(self, withdrawal: StockWithdrawal) -> StockWithdrawal:
        ...

    def list_pending(self) -> list[StockWithdrawal]:
        ...

    def list_fulfilled_service_order_ids(self) -> list[int]:
        ...
