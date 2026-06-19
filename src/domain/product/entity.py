from dataclasses import dataclass
from datetime import datetime

from src.domain.exceptions import ValidationError


@dataclass
class Product:
    id: int | None
    name: str
    sku: str
    unit_price: float
    stock_quantity: int
    description: str | None = None
    supplier_id: int | None = None
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        name: str,
        sku: str,
        unit_price: float,
        stock_quantity: int = 0,
        description: str | None = None,
        supplier_id: int | None = None,
    ) -> "Product":
        return cls(
            id=None,
            name=name,
            sku=sku,
            unit_price=cls._positive_price(unit_price),
            stock_quantity=cls._valid_stock(stock_quantity),
            description=description,
            supplier_id=supplier_id,
        )

    def update_details(
        self,
        name: str | None,
        unit_price: float | None,
        description: str | None,
        supplier_id: int | None,
    ) -> None:
        if name is not None:
            self.name = name
        if unit_price is not None:
            self.unit_price = self._positive_price(unit_price)
        if description is not None:
            self.description = description
        if supplier_id is not None:
            self.supplier_id = supplier_id

    def update_stock(self, quantity_delta: int) -> None:
        new_quantity = self.stock_quantity + quantity_delta
        if new_quantity < 0:
            raise ValidationError("Estoque insuficiente")
        self.stock_quantity = new_quantity

    @staticmethod
    def _positive_price(value: float) -> float:
        if value <= 0:
            raise ValidationError("Preço unitário deve ser maior que zero")
        return value

    @staticmethod
    def _valid_stock(value: int) -> int:
        if value < 0:
            raise ValidationError("Estoque não pode ser negativo")
        return value
