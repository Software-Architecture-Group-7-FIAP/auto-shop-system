from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.domain.billing.entity import Invoice, Payment
from src.domain.enums import PaymentMethod
from src.domain.exceptions import ConflictError, NotFoundError
from src.infrastructure.database import InvoiceModel, PaymentModel


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

    def get_by_id_for_update(self, invoice_id: int) -> Invoice | None:
        model = (
            self.db.query(InvoiceModel)
            .filter(InvoiceModel.id == invoice_id)
            .with_for_update()
            .first()
        )
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
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_payment_by_idempotency_key(
        self, invoice_id: int, idempotency_key: str
    ) -> Payment | None:
        model = (
            self.db.query(PaymentModel)
            .filter(
                PaymentModel.invoice_id == invoice_id,
                PaymentModel.idempotency_key == idempotency_key,
            )
            .first()
        )
        return self._payment_to_domain(model) if model else None

    def add_payment(self, payment: Payment) -> Payment:
        try:
            model = PaymentModel(
                invoice_id=payment.invoice_id,
                amount=payment.amount,
                method=payment.method,
                paid_at=payment.paid_at,
                user_id=payment.user_id,
                idempotency_key=payment.idempotency_key,
            )
            self.db.add(model)
            self.db.flush()
            self.db.refresh(model)
            return self._payment_to_domain(model)
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "Pagamento concorrente ou chave de idempotência já utilizada"
            ) from exc

    @staticmethod
    def _to_domain(model: InvoiceModel) -> Invoice:
        return Invoice(
            id=model.id,
            service_order_id=model.service_order_id,
            amount=model.amount,
            status=model.status,
            paid_at=model.paid_at,
            created_at=model.created_at,
            payments=[SqlAlchemyInvoiceRepository._payment_to_domain(item) for item in model.payments],
        )

    @staticmethod
    def _payment_to_domain(model: PaymentModel) -> Payment:
        return Payment(
            id=model.id,
            invoice_id=model.invoice_id,
            amount=model.amount,
            method=PaymentMethod(model.method),
            paid_at=model.paid_at,
            user_id=model.user_id,
            idempotency_key=model.idempotency_key,
        )
