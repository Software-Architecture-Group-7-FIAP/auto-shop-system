from src.domain.customer.entity import Customer
from src.domain.customer.value_objects import Document
from src.domain.exceptions import NotFoundError
from src.infrastructure.database import CustomerDocumentModel, CustomerModel


class SqlAlchemyCustomerRepository:
    def __init__(self, db):
        self.db = db

    def add(self, customer: Customer) -> Customer:
        model = CustomerModel(
            name=customer.name,
            email=customer.email,
            phone=customer.phone,
            address=customer.address,
        )
        for document in customer.documents:
            model.documents.append(CustomerDocumentModel(document=str(document)))
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, customer_id: int) -> Customer | None:
        model = self.db.query(CustomerModel).filter(CustomerModel.id == customer_id).first()
        if not model:
            return None
        return self._to_domain(model)

    def get_by_document(self, document: Document) -> Customer | None:
        doc_model = (
            self.db.query(CustomerDocumentModel)
            .filter(CustomerDocumentModel.document == str(document))
            .first()
        )
        if not doc_model:
            return None
        return self.get_by_id(doc_model.customer_id)

    def list_all(self, skip: int = 0, limit: int = 100) -> list[Customer]:
        models = self.db.query(CustomerModel).offset(skip).limit(limit).all()
        return [self._to_domain(model) for model in models]

    def exists_by_document(self, document: Document) -> bool:
        return (
            self.db.query(CustomerDocumentModel)
            .filter(CustomerDocumentModel.document == str(document))
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
        model.address = customer.address

        existing_documents = {doc_model.document for doc_model in model.documents}
        for document in customer.documents:
            normalized = str(document)
            if normalized not in existing_documents:
                model.documents.append(CustomerDocumentModel(document=normalized))

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
        documents = [Document.create(doc_model.document) for doc_model in model.documents]
        return Customer(
            id=model.id,
            name=model.name,
            email=model.email,
            address=model.address,
            phone=model.phone,
            created_at=model.created_at,
            _documents=documents,
        )


class SqlAlchemyCustomerLookup:
    def __init__(self, db):
        self.db = db

    def exists(self, customer_id: int) -> bool:
        return (
            self.db.query(CustomerModel)
            .filter(CustomerModel.id == customer_id)
            .first()
            is not None
        )
