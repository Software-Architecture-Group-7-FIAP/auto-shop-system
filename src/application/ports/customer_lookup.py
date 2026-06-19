from typing import Protocol


class CustomerLookup(Protocol):
    def exists(self, customer_id: int) -> bool:
        ...
