from sqlalchemy.orm import Session

from src.domain.exceptions import ConflictError, NotFoundError, ValidationError
from src.domain.value_objects.validators import DocumentValidator
from src.infrastructure.database import ProductModel, SupplierModel


class ProductService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        name: str,
        sku: str,
        unit_price: float,
        stock_quantity: int = 0,
        description: str | None = None,
        supplier_id: int | None = None,
    ) -> ProductModel:
        existing = self.db.query(ProductModel).filter(ProductModel.sku == sku).first()
        if existing:
            raise ConflictError("Produto com este SKU já existe")
        product = ProductModel(
            name=name,
            sku=sku,
            unit_price=unit_price,
            stock_quantity=stock_quantity,
            description=description,
            supplier_id=supplier_id,
        )
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def get_by_id(self, product_id: int) -> ProductModel:
        product = self.db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if not product:
            raise NotFoundError("Produto não encontrado")
        return product

    def list_all(self) -> list[ProductModel]:
        return self.db.query(ProductModel).all()

    def update(
        self,
        product_id: int,
        name: str | None,
        unit_price: float | None,
        description: str | None,
        supplier_id: int | None,
    ) -> ProductModel:
        product = self.get_by_id(product_id)
        if name is not None:
            product.name = name
        if unit_price is not None:
            product.unit_price = unit_price
        if description is not None:
            product.description = description
        if supplier_id is not None:
            product.supplier_id = supplier_id
        self.db.commit()
        self.db.refresh(product)
        return product

    def update_stock(self, product_id: int, quantity: int) -> ProductModel:
        product = self.get_by_id(product_id)
        new_qty = product.stock_quantity + quantity
        if new_qty < 0:
            raise ValidationError("Estoque insuficiente")
        product.stock_quantity = new_qty
        self.db.commit()
        self.db.refresh(product)
        return product

    def delete(self, product_id: int) -> None:
        product = self.get_by_id(product_id)
        self.db.delete(product)
        self.db.commit()


class SupplierService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, name: str, document: str, email: str, phone: str | None = None
    ) -> SupplierModel:
        cleaned_doc = DocumentValidator.validate(document)
        supplier = SupplierModel(name=name, document=cleaned_doc, email=email, phone=phone)
        self.db.add(supplier)
        self.db.commit()
        self.db.refresh(supplier)
        return supplier

    def get_by_id(self, supplier_id: int) -> SupplierModel:
        supplier = self.db.query(SupplierModel).filter(SupplierModel.id == supplier_id).first()
        if not supplier:
            raise NotFoundError("Fornecedor não encontrado")
        return supplier

    def list_all(self) -> list[SupplierModel]:
        return self.db.query(SupplierModel).all()

    def update(
        self,
        supplier_id: int,
        name: str | None,
        email: str | None,
        phone: str | None,
    ) -> SupplierModel:
        supplier = self.get_by_id(supplier_id)
        if name is not None:
            supplier.name = name
        if email is not None:
            supplier.email = email
        if phone is not None:
            supplier.phone = phone
        self.db.commit()
        self.db.refresh(supplier)
        return supplier

    def delete(self, supplier_id: int) -> None:
        supplier = self.get_by_id(supplier_id)
        self.db.delete(supplier)
        self.db.commit()
