from dataclasses import dataclass, field
from datetime import datetime

from src.domain.exceptions import ValidationError


@dataclass
class CatalogService:
    id: int | None
    name: str
    description: str | None
    base_price: float
    estimated_hours: float
    created_at: datetime | None = None
    product_lines: list["ServiceProductLine"] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        name: str,
        description: str | None,
        base_price: float,
        estimated_hours: float = 1.0,
    ) -> "CatalogService":
        return cls(
            id=None,
            name=name,
            description=description,
            base_price=cls._positive_number(base_price, "Preço base deve ser maior que zero"),
            estimated_hours=cls._positive_number(
                estimated_hours,
                "Horas estimadas deve ser maior que zero",
            ),
        )

    def update_details(
        self,
        name: str | None,
        description: str | None,
        base_price: float | None,
        estimated_hours: float | None,
    ) -> None:
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        if base_price is not None:
            self.base_price = self._positive_number(
                base_price,
                "Preço base deve ser maior que zero",
            )
        if estimated_hours is not None:
            self.estimated_hours = self._positive_number(
                estimated_hours,
                "Horas estimadas deve ser maior que zero",
            )

    @staticmethod
    def _positive_number(value: float, message: str) -> float:
        if value <= 0:
            raise ValidationError(message)
        return value


@dataclass
class ServiceProductLine:
    id: int | None
    service_id: int
    product_id: int
    quantity: int

    @classmethod
    def create(
        cls,
        service_id: int,
        product_id: int,
        quantity: int,
    ) -> "ServiceProductLine":
        return cls(
            id=None,
            service_id=service_id,
            product_id=product_id,
            quantity=cls._positive_quantity(quantity),
        )

    @staticmethod
    def _positive_quantity(quantity: int) -> int:
        if quantity <= 0:
            raise ValidationError("Quantidade deve ser maior que zero")
        return quantity
