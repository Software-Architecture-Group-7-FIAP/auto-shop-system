from dataclasses import asdict

import pytest

from src.infrastructure.database import (
    CustomerModel,
    ProductModel,
    ServiceModel,
    ServiceOrderModel,
    SupplierModel,
    UserModel,
    VehicleModel,
)
from src.scripts.seed_synthetic_environment import (
    SeedConfigurationError,
    load_seed_options,
    seed_synthetic_environment,
)


def _environment(**overrides: str) -> dict[str, str]:
    environment = {
        "SEED_SYNTHETIC_DATA": "true",
        "DEPLOYMENT_STAGE": "hml",
        "DEMO_ADMIN_PASSWORD": "test-only-admin-password",
    }
    environment.update(overrides)
    return environment


def test_seed_requires_explicit_opt_in() -> None:
    with pytest.raises(SeedConfigurationError, match="explicitly enabled"):
        load_seed_options(_environment(SEED_SYNTHETIC_DATA="false"))


def test_seed_requires_additional_production_opt_in() -> None:
    with pytest.raises(SeedConfigurationError, match="production opt-in"):
        load_seed_options(_environment(DEPLOYMENT_STAGE="prd"))


def test_seed_accepts_explicit_production_opt_in() -> None:
    options = load_seed_options(
        _environment(
            DEPLOYMENT_STAGE="prd",
            ALLOW_SYNTHETIC_SEED_IN_PRD="true",
        )
    )

    assert options.stage == "prd"


def test_seed_requires_admin_password() -> None:
    with pytest.raises(SeedConfigurationError, match="DEMO_ADMIN_PASSWORD"):
        load_seed_options(_environment(DEMO_ADMIN_PASSWORD=""))


def test_seed_is_idempotent_and_contains_only_marked_synthetic_data(db_session) -> None:
    options = load_seed_options(_environment())

    first = seed_synthetic_environment(options, db_session)
    first_ids = {
        "customers": tuple(row.id for row in db_session.query(CustomerModel).order_by(CustomerModel.id)),
        "vehicles": tuple(row.id for row in db_session.query(VehicleModel).order_by(VehicleModel.id)),
        "products": tuple(row.id for row in db_session.query(ProductModel).order_by(ProductModel.id)),
        "services": tuple(row.id for row in db_session.query(ServiceModel).order_by(ServiceModel.id)),
        "orders": tuple(row.id for row in db_session.query(ServiceOrderModel).order_by(ServiceOrderModel.id)),
    }

    second = seed_synthetic_environment(options, db_session)
    second_ids = {
        "customers": tuple(row.id for row in db_session.query(CustomerModel).order_by(CustomerModel.id)),
        "vehicles": tuple(row.id for row in db_session.query(VehicleModel).order_by(VehicleModel.id)),
        "products": tuple(row.id for row in db_session.query(ProductModel).order_by(ProductModel.id)),
        "services": tuple(row.id for row in db_session.query(ServiceModel).order_by(ServiceModel.id)),
        "orders": tuple(row.id for row in db_session.query(ServiceOrderModel).order_by(ServiceOrderModel.id)),
    }

    assert first.created is True
    assert second.created is False
    assert first_ids == second_ids
    assert first.counts == second.counts == {
        "customers": 3,
        "orders": 3,
        "products": 3,
        "services": 2,
        "suppliers": 1,
        "users": 1,
        "vehicles": 3,
    }

    seeded_users = db_session.query(UserModel).filter(UserModel.username == "avaliador").all()
    seeded_customers = db_session.query(CustomerModel).filter(CustomerModel.email.like("%@demo.invalid")).all()
    seeded_supplier = db_session.query(SupplierModel).filter(
        SupplierModel.email.like("%@demo.invalid")
    ).one()

    assert len(seeded_users) == 1
    assert len(seeded_customers) == 3
    assert all("SINTETICO" in customer.name.upper() for customer in seeded_customers)
    assert "SINTETICO" in seeded_supplier.name.upper()


def test_seed_summary_does_not_expose_pii_or_password(db_session) -> None:
    options = load_seed_options(_environment(DEMO_ADMIN_PASSWORD="never-print-this-password"))

    summary = seed_synthetic_environment(options, db_session)
    serialized = str(asdict(summary))

    assert "never-print-this-password" not in serialized
    assert "11144477735" not in serialized
    assert "demo.invalid" not in serialized
