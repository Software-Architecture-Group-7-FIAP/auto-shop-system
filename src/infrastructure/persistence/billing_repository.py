from sqlalchemy.orm import Session

from src.domain.billing.entity import Invoice
from src.domain.exceptions import NotFoundError
from src.infrastructure.database import InvoiceModel


class SqlAlchemyInvoiceRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, invoice: Invoice) -> Invoice:
        model = InvoiceModel(
            service_order_id=invoice.service_order_id,
            amount=invoice.amount,
            status=invoice.status,
            paid_at=invoice.paid_at,
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, invoice_id: int) -> Invoice | None:
        model = self.db.query(InvoiceModel).filter(InvoiceModel.id == invoice_id).first()
        if not model:
            return None
        return self._to_domain(model)

    def get_by_service_order_id(self, service_order_id: int) -> Invoice | None:
        model = (
            self.db.query(InvoiceModel)
            .filter(InvoiceModel.service_order_id == service_order_id)
            .first()
        )
        if not model:
            return None
        return self._to_domain(model)

    def save(self, invoice: Invoice) -> Invoice:
        if invoice.id is None:
            raise NotFoundError("Fatura não encontrada")

        model = self.db.query(InvoiceModel).filter(InvoiceModel.id == invoice.id).first()
        if not model:
            raise NotFoundError("Fatura não encontrada")

        model.status = invoice.status
        model.paid_at = invoice.paid_at
        model.amount = invoice.amount
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    @staticmethod
    def _to_domain(model: InvoiceModel) -> Invoice:
        return Invoice(
            id=model.id,
            service_order_id=model.service_order_id,
            amount=model.amount,
            status=model.status,
            paid_at=model.paid_at,
            created_at=model.created_at,
        )
