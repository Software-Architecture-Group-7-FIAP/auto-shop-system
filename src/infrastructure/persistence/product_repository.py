from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.product.entity import Product
from src.infrastructure.database import ProductModel


class SqlAlchemyProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, product: Product) -> Product:
        model = ProductModel(
            name=product.name,
            sku=product.sku,
            unit_price=product.unit_price,
            stock_quantity=product.stock_quantity,
            description=product.description,
            supplier_id=product.supplier_id,
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, product_id: int) -> Product | None:
        model = self.db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if not model:
            return None
        return self._to_domain(model)

    def list_all(self) -> list[Product]:
        models = self.db.query(ProductModel).all()
        return [self._to_domain(model) for model in models]

    def exists_by_sku(self, sku: str) -> bool:
        return (
            self.db.query(ProductModel)
            .filter(ProductModel.sku == sku)
            .first()
            is not None
        )

    def exists_by_supplier_id(self, supplier_id: int) -> bool:
        return (
            self.db.scalar(
                select(ProductModel.id).where(ProductModel.supplier_id == supplier_id)
            )
            is not None
        )

    def save(self, product: Product) -> Product:
        if product.id is None:
            raise NotFoundError("Produto não encontrado")

        model = self.db.query(ProductModel).filter(ProductModel.id == product.id).first()
        if not model:
            raise NotFoundError("Produto não encontrado")

        model.name = product.name
        model.unit_price = product.unit_price
        model.stock_quantity = product.stock_quantity
        model.description = product.description
        model.supplier_id = product.supplier_id
        self.db.flush()
        self.db.refresh(model)
        return self._to_domain(model)

    def adjust_stock(self, product_id: int, quantity_delta: int) -> Product:
        conditions = [ProductModel.id == product_id]
        if quantity_delta < 0:
            conditions.append(ProductModel.stock_quantity >= -quantity_delta)
        result = self.db.execute(
            update(ProductModel)
            .where(*conditions)
            .values(stock_quantity=ProductModel.stock_quantity + quantity_delta)
        )
        if result.rowcount == 0:
            exists = self.db.query(ProductModel.id).filter(ProductModel.id == product_id).first()
            if exists is None:
                raise NotFoundError("Produto não encontrado")
            raise ValidationError("Estoque insuficiente")
        self.db.flush()
        updated = self.get_by_id(product_id)
        if updated is None:
            raise NotFoundError("Produto não encontrado")
        return updated

    def delete(self, product: Product) -> None:
        if product.id is None:
            raise NotFoundError("Produto não encontrado")

        model = self.db.query(ProductModel).filter(ProductModel.id == product.id).first()
        if not model:
            raise NotFoundError("Produto não encontrado")

        self.db.delete(model)
        self.db.flush()

    @staticmethod
    def _to_domain(model: ProductModel) -> Product:
        return Product(
            id=model.id,
            name=model.name,
            sku=model.sku,
            unit_price=model.unit_price,
            stock_quantity=model.stock_quantity,
            description=model.description,
            supplier_id=model.supplier_id,
            created_at=model.created_at,
        )


class SqlAlchemyProductLookup:
    def __init__(self, db: Session):
        self.db = db

    def exists(self, product_id: int) -> bool:
        return (
            self.db.query(ProductModel)
            .filter(ProductModel.id == product_id)
            .first()
            is not None
        )
