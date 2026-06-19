from datetime import datetime
from typing import Protocol


class ExecutionClock(Protocol):
    def now(self) -> datetime:
        ...


class ExecutionProductGateway(Protocol):
    def decrement_stock(self, product_id: int, quantity: int) -> None:
        ...


class ExecutionReservationGateway(Protocol):
    def consume_active_for_product(self, service_order_id: int, product_id: int) -> None:
        ...


class ExecutionNotificationRecipient(Protocol):
    def stock_withdrawal_recipient(self) -> str:
        ...


class ExecutionEmailSender(Protocol):
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: str | None = None,
    ) -> None:
        ...
