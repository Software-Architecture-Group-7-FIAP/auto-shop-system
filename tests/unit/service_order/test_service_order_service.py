from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from src.application.ports.service_order import ServiceOrderCustomer, ServiceOrderVehicle
from src.application.services.service_order_email_service import ServiceOrderEmailService
from src.application.services.service_order_service import ServiceOrderService
from src.application.services.service_order_tracking import build_service_order_tracking_url
from src.domain.enums import Priority, ServiceOrderStatus
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.service_order.entity import ServiceOrder


class InMemoryServiceOrderRepository:
    def __init__(self, service_orders: list[ServiceOrder] | None = None):
        self.service_orders = {
            service_order.id: service_order
            for service_order in service_orders or []
            if service_order.id is not None
        }

    def get_by_id(self, service_order_id: int) -> ServiceOrder | None:
        return self.service_orders.get(service_order_id)

    def list_all(
        self,
        status: ServiceOrderStatus | None = None,
    ) -> list[ServiceOrder]:
        orders = list(self.service_orders.values())
        if status:
            return [order for order in orders if order.status == status]
        return orders

    def list_with_execution_times(self) -> list[ServiceOrder]:
        return [
            order
            for order in self.service_orders.values()
            if order.started_at is not None and order.finished_at is not None
        ]

    def save(self, service_order: ServiceOrder) -> ServiceOrder:
        assert service_order.id is not None
        self.service_orders[service_order.id] = service_order
        return service_order


class FakeContactLookup:
    def __init__(self, document: str = "52998224725"):
        self.document = document

    def get_customer(self, customer_id: int) -> ServiceOrderCustomer | None:
        return ServiceOrderCustomer(
            name="Ana",
            email="ana@test.com",
            documents=(self.document,),
        )

    def get_vehicle(self, vehicle_id: int) -> ServiceOrderVehicle | None:
        return ServiceOrderVehicle(plate="ABC1234")


class FakeUnitOfWork:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakePdfGenerator:
    def __init__(self):
        self.calls = []

    def generate_service_order_pdf(
        self,
        service_order_id: int,
        customer_name: str,
        vehicle_plate: str,
        status: str,
        mechanic_name: str | None,
        total_price: float,
        tracking_url: str,
    ) -> bytes:
        self.calls.append(
            {
                "service_order_id": service_order_id,
                "customer_name": customer_name,
                "vehicle_plate": vehicle_plate,
                "status": status,
                "mechanic_name": mechanic_name,
                "total_price": total_price,
                "tracking_url": tracking_url,
            }
        )
        return b"pdf"


class FakeEmailSender:
    def __init__(self):
        self.messages = []

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: str | None = None,
        attachments: tuple = (),
    ) -> None:
        self.messages.append(
            {
                "to": to,
                "subject": subject,
                "body": body,
                "html": html,
                "attachments": attachments,
            }
        )


def make_service_order(**overrides) -> ServiceOrder:
    base = ServiceOrder(
        id=1,
        budget_id=2,
        customer_id=3,
        vehicle_id=4,
        total_price=150.0,
    )
    return replace(base, **overrides)


def make_service(
    repository: InMemoryServiceOrderRepository | None = None,
    contacts: FakeContactLookup | None = None,
    uow: FakeUnitOfWork | None = None,
) -> ServiceOrderService:
    return ServiceOrderService(
        service_orders=repository or InMemoryServiceOrderRepository([make_service_order()]),
        contacts=contacts or FakeContactLookup(),
        uow=uow or FakeUnitOfWork(),
    )


def test_service_order_service_lists_and_filters_orders_without_sqlalchemy():
    service = make_service(
        repository=InMemoryServiceOrderRepository(
            [
                make_service_order(id=1, status=ServiceOrderStatus.RECEBIDA),
                make_service_order(id=2, status=ServiceOrderStatus.EM_DIAGNOSTICO),
            ]
        )
    )

    orders = service.list_all(ServiceOrderStatus.EM_DIAGNOSTICO)

    assert [order.id for order in orders] == [2]


def test_service_order_service_assigns_mechanic_and_commits():
    repository = InMemoryServiceOrderRepository([make_service_order()])
    uow = FakeUnitOfWork()
    service = make_service(repository=repository, uow=uow)

    updated = service.assign_mechanic(1, "Mecânico A")

    assert updated.mechanic_name == "Mecânico A"
    assert updated.status == ServiceOrderStatus.EM_DIAGNOSTICO
    assert repository.get_by_id(1).status == ServiceOrderStatus.EM_DIAGNOSTICO
    assert uow.commits == 1


def test_service_order_service_rejects_blank_mechanic_name():
    service = make_service()

    with pytest.raises(ValidationError, match="Nome do mecânico é obrigatório"):
        service.assign_mechanic(1, "   ")


def test_service_order_service_updates_order_and_commits():
    repository = InMemoryServiceOrderRepository([make_service_order()])
    uow = FakeUnitOfWork()
    service = make_service(repository=repository, uow=uow)

    updated = service.update(
        1,
        mechanic_name="Mecânico B",
        priority=Priority.HIGH,
    )

    assert updated.mechanic_name == "Mecânico B"
    assert updated.priority == Priority.HIGH
    assert updated.status == ServiceOrderStatus.EM_DIAGNOSTICO
    assert uow.commits == 1


def test_service_order_service_updates_status_manually():
    repository = InMemoryServiceOrderRepository(
        [make_service_order(status=ServiceOrderStatus.AGUARDANDO_APROVACAO)]
    )
    uow = FakeUnitOfWork()
    service = make_service(repository=repository, uow=uow)

    updated = service.override_status(
        1,
        ServiceOrderStatus.FINALIZADA,
        "Correção administrativa",
    )

    assert updated.status == ServiceOrderStatus.FINALIZADA
    assert repository.get_by_id(1).status == ServiceOrderStatus.FINALIZADA
    assert uow.commits == 1


def test_service_order_entity_override_status_requires_reason():
    service_order = make_service_order(status=ServiceOrderStatus.AGUARDANDO_APROVACAO)

    with pytest.raises(ValidationError, match="Motivo"):
        service_order.override_status(ServiceOrderStatus.EM_EXECUCAO, " ")


def test_service_order_entity_override_status():
    service_order = make_service_order(status=ServiceOrderStatus.AGUARDANDO_APROVACAO)

    service_order.override_status(ServiceOrderStatus.EM_EXECUCAO, "Correção administrativa")

    assert service_order.status == ServiceOrderStatus.EM_EXECUCAO


def test_service_order_service_sets_priority_and_commits():
    repository = InMemoryServiceOrderRepository([make_service_order()])
    uow = FakeUnitOfWork()
    service = make_service(repository=repository, uow=uow)

    updated = service.set_priority(1, Priority.URGENT)

    assert updated.priority == Priority.URGENT
    assert repository.get_by_id(1).priority == Priority.URGENT
    assert uow.commits == 1


def test_service_order_service_tracks_by_customer_document():
    service = make_service()

    service_order = service.get_by_customer_document(1, "529.982.247-25")

    assert service_order.id == 1


def test_service_order_service_rejects_wrong_customer_document():
    service = make_service(contacts=FakeContactLookup(document="11144477735"))

    with pytest.raises(NotFoundError, match="OS não encontrada para este documento"):
        service.get_by_customer_document(1, "529.982.247-25")


def test_service_order_service_calculates_average_execution_time():
    started_at = datetime(2026, 1, 1, 8, 0, 0)
    service = make_service(
        repository=InMemoryServiceOrderRepository(
            [
                make_service_order(
                    id=1,
                    started_at=started_at,
                    finished_at=started_at + timedelta(hours=2),
                ),
                make_service_order(
                    id=2,
                    started_at=started_at,
                    finished_at=started_at + timedelta(hours=4),
                ),
            ]
        )
    )

    assert service.get_average_execution_time() == {"average_hours": 3.0, "sample_size": 2}


@pytest.mark.asyncio
async def test_service_order_email_service_uses_ports():
    pdfs = FakePdfGenerator()
    emails = FakeEmailSender()
    service = ServiceOrderEmailService(
        service_orders=InMemoryServiceOrderRepository(
            [
                make_service_order(
                    status=ServiceOrderStatus.EM_DIAGNOSTICO,
                    mechanic_name="Mecânico A",
                )
            ]
        ),
        contacts=FakeContactLookup(),
        pdfs=pdfs,
        emails=emails,
        frontend_public_url="http://localhost:4200/",
    )

    await service.send_os_email(1)

    assert pdfs.calls[0]["status"] == "Em diagnóstico"
    assert pdfs.calls[0]["mechanic_name"] == "Mecânico A"
    assert pdfs.calls[0]["tracking_url"] == "http://localhost:4200/track-service-order?serviceOrderId=1"
    message = emails.messages[0]
    assert message["to"] == "ana@test.com"
    assert message["subject"] == "Ordem de Serviço #1"
    assert message["body"] == (
        "Sua OS #1 está com status: Em diagnóstico.\n\n"
        "Acompanhe sua OS:\nhttp://localhost:4200/track-service-order?serviceOrderId=1\n\n"
        "Informe seu CPF/CNPJ para consultar o progresso."
    )
    assert message["html"] is None
    assert message["attachments"][0].filename == "ordem-servico-1.pdf"
    assert message["attachments"][0].content == b"pdf"
    assert message["attachments"][0].mime_type == "application/pdf"


@pytest.mark.asyncio
async def test_service_order_email_service_requires_customer_and_vehicle():
    class EmptyContactLookup(FakeContactLookup):
        def get_customer(self, customer_id: int) -> ServiceOrderCustomer | None:
            return None

    emails = FakeEmailSender()
    service = ServiceOrderEmailService(
        service_orders=InMemoryServiceOrderRepository([make_service_order()]),
        contacts=EmptyContactLookup(),
        pdfs=FakePdfGenerator(),
        emails=emails,
        frontend_public_url="http://localhost:4200",
    )

    with pytest.raises(NotFoundError, match="Dados da OS não encontrados"):
        await service.send_os_email(1)

    assert emails.messages == []


def test_build_service_order_tracking_url_trims_trailing_slash():
    assert build_service_order_tracking_url("http://localhost:4200/", 10) == (
        "http://localhost:4200/track-service-order?serviceOrderId=10"
    )
