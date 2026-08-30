import pytest

from src.domain.enums import ServiceOrderStatus
from src.domain.exceptions import ValidationError
from src.domain.pagination import Page
from src.domain.service_order.rules import (
    CLOSED_STATUSES,
    MAX_PAGE_SIZE,
    OPERATIONAL_STATUSES,
    STATUS_RANKING,
    ServiceOrderListQuery,
)


def test_operational_and_closed_statuses_partition_every_status():
    assert OPERATIONAL_STATUSES | CLOSED_STATUSES == set(ServiceOrderStatus)
    assert not OPERATIONAL_STATUSES & CLOSED_STATUSES


def test_status_ranking_puts_execution_first_and_closed_last():
    assert STATUS_RANKING[:4] == (
        ServiceOrderStatus.EM_EXECUCAO,
        ServiceOrderStatus.AGUARDANDO_APROVACAO,
        ServiceOrderStatus.EM_DIAGNOSTICO,
        ServiceOrderStatus.RECEBIDA,
    )
    assert set(STATUS_RANKING[4:]) == CLOSED_STATUSES


def test_default_query_only_exposes_operational_statuses():
    assert ServiceOrderListQuery().visible_statuses() == OPERATIONAL_STATUSES


def test_include_closed_query_exposes_every_status():
    query = ServiceOrderListQuery(include_closed=True)

    assert query.visible_statuses() == set(ServiceOrderStatus)


def test_explicit_status_narrows_the_visible_statuses():
    query = ServiceOrderListQuery(status=ServiceOrderStatus.EM_EXECUCAO)

    assert query.visible_statuses() == {ServiceOrderStatus.EM_EXECUCAO}


def test_closed_status_filter_is_empty_unless_closed_orders_are_included():
    assert ServiceOrderListQuery(status=ServiceOrderStatus.FINALIZADA).visible_statuses() == set()
    assert ServiceOrderListQuery(
        status=ServiceOrderStatus.FINALIZADA,
        include_closed=True,
    ).visible_statuses() == {ServiceOrderStatus.FINALIZADA}


def test_offset_derives_from_page_and_page_size():
    assert ServiceOrderListQuery(page=1, page_size=20).offset == 0
    assert ServiceOrderListQuery(page=3, page_size=20).offset == 40


@pytest.mark.parametrize(
    "page, page_size",
    [(0, 20), (-1, 20), (1, 0), (1, MAX_PAGE_SIZE + 1)],
)
def test_query_rejects_out_of_range_pagination(page: int, page_size: int):
    with pytest.raises(ValidationError):
        ServiceOrderListQuery(page=page, page_size=page_size)


@pytest.mark.parametrize(
    "total, page_size, expected",
    [(0, 20, 0), (1, 20, 1), (42, 20, 3), (40, 20, 2)],
)
def test_page_total_pages_rounds_up(total: int, page_size: int, expected: int):
    page = Page(items=(), total=total, page=1, page_size=page_size)

    assert page.total_pages == expected
