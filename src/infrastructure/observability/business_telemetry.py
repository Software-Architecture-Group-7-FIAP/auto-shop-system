import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import event as sqlalchemy_event
from sqlalchemy.orm import Session

from src.application.ports.business_telemetry import ServiceOrderFailureTelemetry
from src.domain.enums import ServiceOrderStatus


_LOGGER = logging.getLogger("src.observability.business")
_QUEUE_KEY = "service_order_business_telemetry"
_TRANSITION_TYPES = frozenset(
    {
        "break_glass_override",
        "budget_approved",
        "budget_rejected",
        "budget_submitted",
        "delivered",
        "execution_finished",
        "execution_started",
        "inventory_reconciled",
        "inventory_shortage",
        "mechanic_assignment",
        "workflow",
    }
)
_FAILURE_TYPES = frozenset(
    {
        "integration_error",
        "processing_error",
    }
)
_SUBSYSTEMS = frozenset(
    {
        "event_bus",
        "service_order",
    }
)
_MAX_DURATION_MS = 10 * 365 * 24 * 60 * 60 * 1000


class SessionWithInfo(Protocol):
    info: dict[str, object]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Business telemetry timestamps must be timezone-aware")
    normalized = value
    return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validated_status(value: ServiceOrderStatus) -> str:
    if not isinstance(value, ServiceOrderStatus):
        raise ValueError("Invalid service-order status")
    return value.value


@dataclass(frozen=True)
class ServiceOrderCreatedEvent:
    occurred_at: datetime
    status: ServiceOrderStatus
    event_type: str = field(default="ServiceOrderCreated", init=False)
    event_version: int = field(default=1, init=False)

    def attributes(self) -> dict[str, object]:
        return {
            "event": self.event_type,
            "event_version": self.event_version,
            "occurred_at": _iso_utc(self.occurred_at),
            "status": _validated_status(self.status),
        }


@dataclass(frozen=True)
class ServiceOrderStatusDurationEvent:
    status: ServiceOrderStatus
    to_status: ServiceOrderStatus
    transition_type: str
    duration_ms: int
    occurred_at: datetime
    event_type: str = field(default="ServiceOrderStatusDuration", init=False)
    event_version: int = field(default=1, init=False)

    @classmethod
    def from_interval(
        cls,
        *,
        status: ServiceOrderStatus,
        to_status: ServiceOrderStatus,
        transition_type: str,
        entered_at: datetime,
        occurred_at: datetime,
    ) -> "ServiceOrderStatusDurationEvent":
        duration_ms = int((occurred_at - entered_at).total_seconds() * 1000)
        if not 0 <= duration_ms <= _MAX_DURATION_MS:
            raise ValueError("Invalid service-order status duration")
        if transition_type not in _TRANSITION_TYPES:
            raise ValueError("Invalid service-order transition type")
        return cls(
            status=status,
            to_status=to_status,
            transition_type=transition_type,
            duration_ms=duration_ms,
            occurred_at=occurred_at,
        )

    def attributes(self) -> dict[str, object]:
        if self.transition_type not in _TRANSITION_TYPES:
            raise ValueError("Invalid service-order transition type")
        if type(self.duration_ms) is not int or not 0 <= self.duration_ms <= _MAX_DURATION_MS:
            raise ValueError("Invalid service-order status duration")
        return {
            "event": self.event_type,
            "event_version": self.event_version,
            "occurred_at": _iso_utc(self.occurred_at),
            "status": _validated_status(self.status),
            "to_status": _validated_status(self.to_status),
            "transition_type": self.transition_type,
            "duration_ms": self.duration_ms,
            "duration_unit": "milliseconds",
        }


@dataclass(frozen=True)
class ServiceOrderFailureEvent:
    service_order_id: int
    failure_type: str
    subsystem: str
    occurred_at: datetime = field(default_factory=_utc_now)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: str = field(default="ServiceOrderProcessingFailure", init=False)
    event_version: int = field(default=1, init=False)

    def attributes(self) -> dict[str, object]:
        if (
            type(self.service_order_id) is not int
            or not 1 <= self.service_order_id <= 2_147_483_647
        ):
            raise ValueError("Invalid service-order identifier")
        if self.failure_type not in _FAILURE_TYPES:
            raise ValueError("Invalid service-order failure type")
        if self.subsystem not in _SUBSYSTEMS:
            raise ValueError("Invalid service-order failure subsystem")
        try:
            if str(UUID(self.event_id)) != self.event_id:
                raise ValueError
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("Invalid service-order event identifier") from exc
        return {
            "event": self.event_type,
            "event_version": self.event_version,
            "event_id": self.event_id,
            "occurred_at": _iso_utc(self.occurred_at),
            "service_order_id": self.service_order_id,
            "failure_type": self.failure_type,
            "subsystem": self.subsystem,
        }


BusinessEvent = ServiceOrderCreatedEvent | ServiceOrderStatusDurationEvent


def queue_business_event(session: SessionWithInfo, event: BusinessEvent) -> None:
    pending = session.info.setdefault(_QUEUE_KEY, [])
    if not isinstance(pending, list):
        session.info[_QUEUE_KEY] = []
        pending = session.info[_QUEUE_KEY]
    pending.append(event)


def flush_pending_business_events(session: SessionWithInfo) -> None:
    pending = session.info.pop(_QUEUE_KEY, [])
    if not isinstance(pending, list):
        return
    for event in pending:
        attributes: dict[str, object] | None = None
        try:
            if isinstance(event, (ServiceOrderCreatedEvent, ServiceOrderStatusDurationEvent)):
                attributes = event.attributes()
        except (TypeError, ValueError):
            # The transaction is already committed; telemetry must not change its outcome.
            attributes = None
        if attributes is not None:
            _emit(attributes)


def discard_pending_business_events(session: SessionWithInfo) -> None:
    session.info.pop(_QUEUE_KEY, None)


def emit_service_order_failure(event: ServiceOrderFailureEvent) -> None:
    _emit(event.attributes(), level=logging.ERROR)


class StructuredServiceOrderBusinessTelemetry:
    def record_failure(self, event: ServiceOrderFailureTelemetry) -> None:
        emit_service_order_failure(
            ServiceOrderFailureEvent(
                event_id=event.event_id,
                occurred_at=event.occurred_at,
                service_order_id=event.service_order_id,
                failure_type=event.failure_type,
                subsystem=event.subsystem,
            )
        )


def _emit(attributes: dict[str, object], *, level: int = logging.INFO) -> None:
    try:
        _LOGGER.log(
            level,
            "service_order_business_event",
            extra={**attributes, "business_event": True},
        )
    except Exception:
        # Telemetry is best effort and must never alter a committed operation.
        return


@sqlalchemy_event.listens_for(Session, "after_commit")
def _flush_after_commit(session: Session) -> None:
    flush_pending_business_events(session)


@sqlalchemy_event.listens_for(Session, "after_rollback")
def _discard_after_rollback(session: Session) -> None:
    discard_pending_business_events(session)
