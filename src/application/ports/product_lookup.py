from typing import Protocol


class ProductLookup(Protocol):
    def exists(self, product_id: int) -> bool:
        ...
