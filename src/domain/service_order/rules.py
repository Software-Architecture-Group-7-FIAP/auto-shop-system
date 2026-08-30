from dataclasses import dataclass
from enum import StrEnum

from src.domain.enums import ServiceOrderStatus
from src.domain.exceptions import ValidationError

OPERATIONAL_STATUSES: frozenset[ServiceOrderStatus] = frozenset(
    {
        ServiceOrderStatus.RECEBIDA,
        ServiceOrderStatus.EM_DIAGNOSTICO,
        ServiceOrderStatus.AGUARDANDO_APROVACAO,
        ServiceOrderStatus.EM_EXECUCAO,
    }
)

CLOSED_STATUSES: frozenset[ServiceOrderStatus] = frozenset(
    {
        ServiceOrderStatus.FINALIZADA,
        ServiceOrderStatus.ENTREGUE,
    }
)

STATUS_RANKING: tuple[ServiceOrderStatus, ...] = (
    ServiceOrderStatus.EM_EXECUCAO,
    ServiceOrderStatus.AGUARDANDO_APROVACAO,
    ServiceOrderStatus.EM_DIAGNOSTICO,
    ServiceOrderStatus.RECEBIDA,
    ServiceOrderStatus.FINALIZADA,
    ServiceOrderStatus.ENTREGUE,
)

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


class ServiceOrderOrdering(StrEnum):
    STATUS_CREATED_AT_ASC = "status_created_at_asc"
    CREATED_AT_ASC = "created_at_asc"
    CREATED_AT_DESC = "created_at_desc"


@dataclass(frozen=True)
class ServiceOrderListQuery:
    status: ServiceOrderStatus | None = None
    include_closed: bool = False
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    order_by: ServiceOrderOrdering = ServiceOrderOrdering.STATUS_CREATED_AT_ASC

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValidationError("page deve ser maior ou igual a 1")
        if self.page_size < 1:
            raise ValidationError("page_size deve ser maior ou igual a 1")
        if self.page_size > MAX_PAGE_SIZE:
            raise ValidationError(f"page_size não pode exceder {MAX_PAGE_SIZE}")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    def visible_statuses(self) -> frozenset[ServiceOrderStatus]:
        allowed = (
            OPERATIONAL_STATUSES | CLOSED_STATUSES if self.include_closed else OPERATIONAL_STATUSES
        )
        if self.status is None:
            return allowed
        return frozenset({self.status}) & allowed
