from sqlalchemy.orm import Session

from src.domain.exceptions import ConflictError, NotFoundError
from src.domain.value_objects.validators import DocumentValidator
from src.infrastructure.database import CustomerModel


class CustomerService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, name: str, document: str, email: str, phone: str | None = None) -> CustomerModel:
        cleaned_doc = DocumentValidator.validate(document)
        existing = self.db.query(CustomerModel).filter(CustomerModel.document == cleaned_doc).first()
        if existing:
            raise ConflictError("Cliente com este documento já existe")
        customer = CustomerModel(name=name, document=cleaned_doc, email=email, phone=phone)
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def get_by_id(self, customer_id: int) -> CustomerModel:
        customer = self.db.query(CustomerModel).filter(CustomerModel.id == customer_id).first()
        if not customer:
            raise NotFoundError("Cliente não encontrado")
        return customer

    def get_by_document(self, document: str) -> CustomerModel:
        cleaned_doc = DocumentValidator.validate(document)
        customer = self.db.query(CustomerModel).filter(CustomerModel.document == cleaned_doc).first()
        if not customer:
            raise NotFoundError("Cliente não encontrado")
        return customer

    def list_all(self, skip: int = 0, limit: int = 100) -> list[CustomerModel]:
        return self.db.query(CustomerModel).offset(skip).limit(limit).all()

    def update(
        self, customer_id: int, name: str | None, email: str | None, phone: str | None
    ) -> CustomerModel:
        customer = self.get_by_id(customer_id)
        if name is not None:
            customer.name = name
        if email is not None:
            customer.email = email
        if phone is not None:
            customer.phone = phone
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def delete(self, customer_id: int) -> None:
        customer = self.get_by_id(customer_id)
        self.db.delete(customer)
        self.db.commit()
