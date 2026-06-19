from src.domain.value_objects.validators import PlateValidator


class Plate(str):
    def __new__(cls, raw: str) -> "Plate":
        normalized = PlateValidator.validate(raw)
        return str.__new__(cls, normalized)

    @classmethod
    def create(cls, raw: str) -> "Plate":
        return cls(raw)
