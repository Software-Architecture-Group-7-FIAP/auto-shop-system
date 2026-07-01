import pytest

from src.domain.exceptions import ValidationError
from src.domain.vehicle.entity import Vehicle
from src.domain.vehicle.value_objects import Plate


def _vehicle_kwargs(**overrides):
    base = {
        "customer_id": 1,
        "plate": "abc-1234",
        "state": "sp",
        "city": "São Paulo",
        "color": "Preto",
        "brand": " Fiat ",
        "model": " Uno ",
        "year": 2020,
    }
    base.update(overrides)
    return base


def test_plate_normalizes_legacy_format():
    assert Plate.create("abc-1234") == "ABC1234"


def test_plate_normalizes_mercosul_format():
    assert Plate.create("abc 1d23") == "ABC1D23"


def test_plate_rejects_invalid_format():
    with pytest.raises(ValidationError, match="Veículo inválido"):
        Plate.create("INVALID")


def test_vehicle_create_validates_and_normalizes_fields():
    vehicle = Vehicle.create(**_vehicle_kwargs())

    assert vehicle.plate == "ABC1234"
    assert vehicle.state == "SP"
    assert vehicle.city == "São Paulo"
    assert vehicle.color == "Preto"
    assert vehicle.brand == "Fiat"
    assert vehicle.model == "Uno"
    assert vehicle.year == 2020


def test_vehicle_rejects_invalid_year():
    with pytest.raises(ValidationError):
        Vehicle.create(**_vehicle_kwargs(year=1899))


def test_vehicle_rejects_invalid_state():
    with pytest.raises(ValidationError, match="UF inválida"):
        Vehicle.create(**_vehicle_kwargs(state="XX"))


def test_vehicle_updates_details_through_domain_behavior():
    vehicle = Vehicle.create(**_vehicle_kwargs())

    vehicle.update_details(
        state="rj",
        city="Rio de Janeiro",
        color="Branco",
        brand="VW",
        model=None,
        year=2022,
    )

    assert vehicle.state == "RJ"
    assert vehicle.city == "Rio de Janeiro"
    assert vehicle.color == "Branco"
    assert vehicle.brand == "VW"
    assert vehicle.model == "Uno"
    assert vehicle.year == 2022
