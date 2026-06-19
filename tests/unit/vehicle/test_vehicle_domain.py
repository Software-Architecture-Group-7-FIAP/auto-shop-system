import pytest

from src.domain.exceptions import ValidationError
from src.domain.vehicle.entity import Vehicle
from src.domain.vehicle.value_objects import Plate


def test_plate_normalizes_legacy_format():
    assert Plate.create("abc-1234") == "ABC1234"


def test_plate_normalizes_mercosul_format():
    assert Plate.create("abc 1d23") == "ABC1D23"


def test_plate_rejects_invalid_format():
    with pytest.raises(ValidationError):
        Plate.create("INVALID")


def test_vehicle_create_validates_and_normalizes_fields():
    vehicle = Vehicle.create(
        customer_id=1,
        plate="abc-1234",
        brand=" Fiat ",
        model=" Uno ",
        year=2020,
    )

    assert vehicle.plate == "ABC1234"
    assert vehicle.brand == "Fiat"
    assert vehicle.model == "Uno"
    assert vehicle.year == 2020


def test_vehicle_rejects_invalid_year():
    with pytest.raises(ValidationError):
        Vehicle.create(
            customer_id=1,
            plate="ABC1234",
            brand="Fiat",
            model="Uno",
            year=1899,
        )


def test_vehicle_updates_details_through_domain_behavior():
    vehicle = Vehicle.create(
        customer_id=1,
        plate="ABC1234",
        brand="Fiat",
        model="Uno",
        year=2020,
    )

    vehicle.update_details(brand="VW", model=None, year=2022)

    assert vehicle.brand == "VW"
    assert vehicle.model == "Uno"
    assert vehicle.year == 2022
