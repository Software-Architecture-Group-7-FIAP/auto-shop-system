from datetime import datetime

from sqlalchemy.orm import Session

from src.domain.enums import InvoiceStatus, ServiceOrderStatus
from src.domain.exceptions import NotFoundError, ValidationError
from src.infrastructure.database import InvoiceModel, ServiceOrderModel


class InvoiceService:
    def __init__(self, db: Session):
        self.db = db

    def create_invoice(self, service_order_id: int) -> InvoiceModel:
        os = self.db.query(ServiceOrderModel).filter(ServiceOrderModel.id == service_order_id).first()
        if not os:
            raise NotFoundError("OS não encontrada")
        if os.status != ServiceOrderStatus.FINALIZADA:
            raise ValidationError("OS deve estar finalizada para gerar fatura")
        existing = (
            self.db.query(InvoiceModel)
            .filter(InvoiceModel.service_order_id == service_order_id)
            .first()
        )
        if existing:
            raise ValidationError("Fatura já existe para esta OS")
        invoice = InvoiceModel(service_order_id=service_order_id, amount=os.total_price)
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def pay_invoice(self, invoice_id: int) -> InvoiceModel:
        invoice = self.db.query(InvoiceModel).filter(InvoiceModel.id == invoice_id).first()
        if not invoice:
            raise NotFoundError("Fatura não encontrada")
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = datetime.utcnow()

        os = (
            self.db.query(ServiceOrderModel)
            .filter(ServiceOrderModel.id == invoice.service_order_id)
            .first()
        )
        if os:
            os.status = ServiceOrderStatus.ENTREGUE

        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def deliver(self, service_order_id: int) -> ServiceOrderModel:
        os = self.db.query(ServiceOrderModel).filter(ServiceOrderModel.id == service_order_id).first()
        if not os:
            raise NotFoundError("OS não encontrada")
        os.status = ServiceOrderStatus.ENTREGUE
        self.db.commit()
        self.db.refresh(os)
        return os

    def get_by_id(self, invoice_id: int) -> InvoiceModel:
        invoice = self.db.query(InvoiceModel).filter(InvoiceModel.id == invoice_id).first()
        if not invoice:
            raise NotFoundError("Fatura não encontrada")
        return invoice
