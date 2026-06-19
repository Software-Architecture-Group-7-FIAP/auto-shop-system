from sqlalchemy.orm import Session

from src.domain.exceptions import NotFoundError
from src.domain.supplier.entity import Supplier
from src.domain.supplier.value_objects import SupplierDocument
from src.infrastructure.database import SupplierModel


class SqlAlchemySupplierRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, supplier: Supplier) -> Supplier:
        model = SupplierModel(
            name=supplier.name,
            document=str(supplier.document),
            email=supplier.email,
            phone=supplier.phone,
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, supplier_id: int) -> Supplier | None:
        model = self.db.query(SupplierModel).filter(SupplierModel.id == supplier_id).first()
        if not model:
            return None
        return self._to_domain(model)

    def list_all(self) -> list[Supplier]:
        models = self.db.query(SupplierModel).all()
        return [self._to_domain(model) for model in models]

    def save(self, supplier: Supplier) -> Supplier:
        if supplier.id is None:
            raise NotFoundError("Fornecedor não encontrado")

        model = self.db.query(SupplierModel).filter(SupplierModel.id == supplier.id).first()
        if not model:
            raise NotFoundError("Fornecedor não encontrado")

        model.name = supplier.name
        model.email = supplier.email
        model.phone = supplier.phone
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def delete(self, supplier: Supplier) -> None:
        if supplier.id is None:
            raise NotFoundError("Fornecedor não encontrado")

        model = self.db.query(SupplierModel).filter(SupplierModel.id == supplier.id).first()
        if not model:
            raise NotFoundError("Fornecedor não encontrado")

        self.db.delete(model)
        self.db.flush()

    @staticmethod
    def _to_domain(model: SupplierModel) -> Supplier:
        return Supplier(
            id=model.id,
            name=model.name,
            document=SupplierDocument.create(model.document),
            email=model.email,
            phone=model.phone,
            created_at=model.created_at,
        )
