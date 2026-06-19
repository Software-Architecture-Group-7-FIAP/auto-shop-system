from sqlalchemy.orm import Session

from src.domain.customer.entity import Customer
from src.domain.customer.value_objects import CustomerDocument
from src.domain.exceptions import NotFoundError
from src.infrastructure.database import CustomerModel


class SqlAlchemyCustomerRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, customer: Customer) -> Customer:
        model = CustomerModel(
            name=customer.name,
            document=str(customer.document),
            email=customer.email,
            phone=customer.phone,
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, customer_id: int) -> Customer | None:
        model = self.db.query(CustomerModel).filter(CustomerModel.id == customer_id).first()
        if not model:
            return None
        return self._to_domain(model)

    def get_by_document(self, document: CustomerDocument) -> Customer | None:
        model = (
            self.db.query(CustomerModel)
            .filter(CustomerModel.document == str(document))
            .first()
        )
        if not model:
            return None
        return self._to_domain(model)

    def list_all(self, skip: int = 0, limit: int = 100) -> list[Customer]:
        models = self.db.query(CustomerModel).offset(skip).limit(limit).all()
        return [self._to_domain(model) for model in models]

    def exists_by_document(self, document: CustomerDocument) -> bool:
        return (
            self.db.query(CustomerModel)
            .filter(CustomerModel.document == str(document))
            .first()
            is not None
        )

    def save(self, customer: Customer) -> Customer:
        if customer.id is None:
            raise NotFoundError("Cliente não encontrado")

        model = self.db.query(CustomerModel).filter(CustomerModel.id == customer.id).first()
        if not model:
            raise NotFoundError("Cliente não encontrado")

        model.name = customer.name
        model.email = customer.email
        model.phone = customer.phone
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def delete(self, customer: Customer) -> None:
        if customer.id is None:
            raise NotFoundError("Cliente não encontrado")

        model = self.db.query(CustomerModel).filter(CustomerModel.id == customer.id).first()
        if not model:
            raise NotFoundError("Cliente não encontrado")

        self.db.delete(model)
        self.db.flush()

    @staticmethod
    def _to_domain(model: CustomerModel) -> Customer:
        return Customer(
            id=model.id,
            name=model.name,
            document=CustomerDocument.create(model.document),
            email=model.email,
            phone=model.phone,
            created_at=model.created_at,
        )


class SqlAlchemyCustomerLookup:
    def __init__(self, db: Session):
        self.db = db

    def exists(self, customer_id: int) -> bool:
        return (
            self.db.query(CustomerModel)
            .filter(CustomerModel.id == customer_id)
            .first()
            is not None
        )
