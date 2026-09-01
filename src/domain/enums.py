from enum import StrEnum


class ServiceOrderStatus(StrEnum):
    RECEBIDA = "Recebida"
    EM_DIAGNOSTICO = "Em diagnóstico"
    AGUARDANDO_APROVACAO = "Aguardando aprovação"
    AGUARDANDO_INICIO = "Aguardando início"
    EM_EXECUCAO = "Em execução"
    FINALIZADA = "Finalizada"
    ENTREGUE = "Entregue"


class BudgetStatus(StrEnum):
    DRAFT = "Rascunho"
    SENT = "Enviado"
    APPROVED = "Aprovado"
    REJECTED = "Recusado"
    SUPERSEDED = "Substituído"


class PurchaseRequestStatus(StrEnum):
    PENDING = "Pendente"
    ORDERED = "Pedido"
    RECEIVED = "Recebido"


class ReservationStatus(StrEnum):
    ACTIVE = "Ativa"
    RELEASED = "Liberada"
    CONSUMED = "Consumida"


class StockWithdrawalStatus(StrEnum):
    PENDING = "Pendente"
    FULFILLED = "Atendida"
    CANCELLED = "Cancelada"


class InvoiceStatus(StrEnum):
    PENDING = "Pendente"
    PAID = "Paga"


class Priority(StrEnum):
    LOW = "Baixa"
    NORMAL = "Normal"
    HIGH = "Alta"
    URGENT = "Urgente"


class PersonType(StrEnum):
    PF = "PF"
    PJ = "PJ"
