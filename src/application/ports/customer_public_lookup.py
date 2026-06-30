from typing import Protocol


class CustomerVehicleOwnershipLookup(Protocol):
    def customer_owns_plate(self, customer_id: int, plate: str) -> bool:
        ...
