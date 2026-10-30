import argparse
from collections.abc import Mapping
from dataclasses import dataclass
import json
import os

from sqlalchemy.orm import Session

from src.application.seeding.dataset import DATASET_NAME
from src.infrastructure.database import SessionLocal
from src.infrastructure.persistence.synthetic_seed import seed_fase3_dataset


class SeedConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SeedOptions:
    stage: str
    admin_password: str
    dataset: str = DATASET_NAME


@dataclass(frozen=True)
class SeedSummary:
    dataset: str
    stage: str
    created: bool
    counts: dict[str, int]


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() == "true"


def load_seed_options(
    environment: Mapping[str, str] | None = None,
    *,
    requested_stage: str | None = None,
    dataset: str = DATASET_NAME,
) -> SeedOptions:
    env = environment if environment is not None else os.environ
    if not _enabled(env.get("SEED_SYNTHETIC_DATA")):
        raise SeedConfigurationError("Synthetic seed must be explicitly enabled")
    if dataset != DATASET_NAME:
        raise SeedConfigurationError("Unsupported synthetic dataset")

    configured_stage = str(env.get("DEPLOYMENT_STAGE", "")).strip().lower()
    stage = str(requested_stage or configured_stage).strip().lower()
    if stage not in {"local", "hml", "prd"}:
        raise SeedConfigurationError("DEPLOYMENT_STAGE must be local, hml, or prd")
    if requested_stage and configured_stage and requested_stage.lower() != configured_stage:
        raise SeedConfigurationError("Requested stage does not match DEPLOYMENT_STAGE")
    if stage == "prd" and not _enabled(env.get("ALLOW_SYNTHETIC_SEED_IN_PRD")):
        raise SeedConfigurationError("Synthetic seed in PRD requires production opt-in")

    password = str(env.get("DEMO_ADMIN_PASSWORD", ""))
    if not password:
        raise SeedConfigurationError("DEMO_ADMIN_PASSWORD is required")
    return SeedOptions(stage=stage, admin_password=password, dataset=dataset)


def seed_synthetic_environment(options: SeedOptions, session: Session) -> SeedSummary:
    try:
        result = seed_fase3_dataset(session, options.admin_password)
    except Exception:
        session.rollback()
        raise
    return SeedSummary(
        dataset=options.dataset,
        stage=options.stage,
        created=result.created,
        counts=result.counts,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a disposable synthetic environment")
    parser.add_argument("--dataset", default=DATASET_NAME, choices=(DATASET_NAME,))
    parser.add_argument("--stage", required=True, choices=("local", "hml", "prd"))
    args = parser.parse_args()

    try:
        options = load_seed_options(
            requested_stage=args.stage,
            dataset=args.dataset,
        )
    except SeedConfigurationError as exc:
        parser.error(str(exc))

    session = SessionLocal()
    try:
        summary = seed_synthetic_environment(options, session)
        print(
            json.dumps(
                {
                    "dataset": summary.dataset,
                    "stage": summary.stage,
                    "created": summary.created,
                    "counts": summary.counts,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
