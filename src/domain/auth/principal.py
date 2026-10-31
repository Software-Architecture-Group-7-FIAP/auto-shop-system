from dataclasses import dataclass


@dataclass(frozen=True)
class CustomerPrincipal:
    customer_id: int
