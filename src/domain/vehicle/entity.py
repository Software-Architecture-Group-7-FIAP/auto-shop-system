from dataclasses import dataclass
from datetime import datetime

from src.domain.exceptions import ValidationError
from src.domain.vehicle.value_objects import Plate


@dataclass
class Vehicle:
    id: int | None
    customer_id: int
    plate: Plate
    brand: str
    model: str
    year: int
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        customer_id: int,
        plate: str,
        brand: str,
        model: str,
        year: int,
    ) -> "Vehicle":
        return cls(
            id=None,
            customer_id=customer_id,
            plate=Plate.create(plate),
            brand=cls._required_text(brand, "Marca do veículo é obrigatória"),
            model=cls._required_text(model, "Modelo do veículo é obrigatório"),
            year=cls._valid_year(year),
        )

    def update_details(
        self,
        brand: str | None,
        model: str | None,
        year: int | None,
    ) -> None:
        if brand is not None:
            self.brand = self._required_text(brand, "Marca do veículo é obrigatória")
        if model is not None:
            self.model = self._required_text(model, "Modelo do veículo é obrigatório")
        if year is not None:
            self.year = self._valid_year(year)

    @staticmethod
    def _required_text(value: str, message: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValidationError(message)
        return cleaned

    @staticmethod
    def _valid_year(year: int) -> int:
        if year < 1900 or year > 2100:
            raise ValidationError("Ano do veículo inválido")
        return year
