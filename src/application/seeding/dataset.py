from dataclasses import dataclass

from src.domain.enums import CustomerStatus, Priority, ServiceOrderStatus


DATASET_NAME = "fase3-v1"


@dataclass(frozen=True)
class SyntheticCustomer:
    document: str
    name: str
    email: str
    phone: str
    address: str
    status: CustomerStatus
    plate: str
    vehicle_state: str
    vehicle_city: str
    vehicle_color: str
    vehicle_brand: str
    vehicle_model: str
    vehicle_year: int


@dataclass(frozen=True)
class SyntheticProduct:
    sku: str
    name: str
    description: str
    unit_price: float
    stock_quantity: int


@dataclass(frozen=True)
class SyntheticService:
    key: str
    name: str
    description: str
    base_price: float
    estimated_hours: float
    product_sku: str
    product_quantity: int


@dataclass(frozen=True)
class SyntheticOrder:
    key: str
    customer_document: str
    service_key: str
    product_sku: str
    status: ServiceOrderStatus
    priority: Priority
    total_price: float


CUSTOMERS = (
    SyntheticCustomer(
        document="11144477735",
        name="CLIENTE SINTETICO ATIVO UM",
        email="cliente.ativo.um@demo.invalid",
        phone="00000000001",
        address="ENDERECO SINTETICO 1 - NAO ENTREGAR",
        status=CustomerStatus.ACTIVE,
        plate="TST1A01",
        vehicle_state="SP",
        vehicle_city="CIDADE SINTETICA",
        vehicle_color="AZUL",
        vehicle_brand="MARCA SINTETICA",
        vehicle_model="MODELO UM",
        vehicle_year=2024,
    ),
    SyntheticCustomer(
        document="52998224725",
        name="CLIENTE SINTETICO ATIVO DOIS",
        email="cliente.ativo.dois@demo.invalid",
        phone="00000000002",
        address="ENDERECO SINTETICO 2 - NAO ENTREGAR",
        status=CustomerStatus.ACTIVE,
        plate="TST2A02",
        vehicle_state="RJ",
        vehicle_city="CIDADE SINTETICA",
        vehicle_color="PRATA",
        vehicle_brand="MARCA SINTETICA",
        vehicle_model="MODELO DOIS",
        vehicle_year=2023,
    ),
    SyntheticCustomer(
        document="12345678909",
        name="CLIENTE SINTETICO INATIVO",
        email="cliente.inativo@demo.invalid",
        phone="00000000003",
        address="ENDERECO SINTETICO 3 - NAO ENTREGAR",
        status=CustomerStatus.INACTIVE,
        plate="TST3A03",
        vehicle_state="MG",
        vehicle_city="CIDADE SINTETICA",
        vehicle_color="PRETO",
        vehicle_brand="MARCA SINTETICA",
        vehicle_model="MODELO TRES",
        vehicle_year=2022,
    ),
)
PRODUCTS = (
    SyntheticProduct("DEMO-FILTRO-001", "FILTRO SINTETICO", "PRODUTO SINTETICO", 45.0, 30),
    SyntheticProduct("DEMO-OLEO-001", "OLEO SINTETICO DEMO", "PRODUTO SINTETICO", 35.0, 40),
    SyntheticProduct("DEMO-PASTILHA-001", "PASTILHA SINTETICA", "PRODUTO SINTETICO", 180.0, 20),
)

SERVICES = (
    SyntheticService(
        "revisao",
        "REVISAO SINTETICA",
        "SERVICO SINTETICO PARA HOMOLOGACAO",
        150.0,
        2.0,
        "DEMO-FILTRO-001",
        1,
    ),
    SyntheticService(
        "freios",
        "FREIOS SINTETICOS",
        "SERVICO SINTETICO PARA HOMOLOGACAO",
        220.0,
        3.0,
        "DEMO-PASTILHA-001",
        1,
    ),
)

ORDERS = (
    SyntheticOrder(
        "recebida",
        "11144477735",
        "revisao",
        "DEMO-FILTRO-001",
        ServiceOrderStatus.RECEBIDA,
        Priority.NORMAL,
        195.0,
    ),
    SyntheticOrder(
        "em-execucao",
        "52998224725",
        "freios",
        "DEMO-PASTILHA-001",
        ServiceOrderStatus.EM_EXECUCAO,
        Priority.HIGH,
        400.0,
    ),
    SyntheticOrder(
        "entregue",
        "12345678909",
        "revisao",
        "DEMO-OLEO-001",
        ServiceOrderStatus.ENTREGUE,
        Priority.LOW,
        185.0,
    ),
)
