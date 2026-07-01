from typing import Protocol

from src.domain.execution.entity import StockWithdrawal


class StockWithdrawalRepository(Protocol):
    def add(self, withdrawal: StockWithdrawal) -> StockWithdrawal:
        ...

    def get_by_id(self, withdrawal_id: int) -> StockWithdrawal | None:
        ...

    def save(self, withdrawal: StockWithdrawal) -> StockWithdrawal:
        ...

    def list_pending(self) -> list[StockWithdrawal]:
        ...

    def list_fulfilled_service_order_ids(self) -> list[int]:
        ...

    def fulfilled_quantity_by_product(self, service_order_id: int) -> dict[int, int]:
        ...

    def list_by_service_order_id(self, service_order_id: int) -> list[StockWithdrawal]:
        ...

    def list_by_service_order_ids(
        self,
        service_order_ids: list[int],
    ) -> list[StockWithdrawal]:
        ...
