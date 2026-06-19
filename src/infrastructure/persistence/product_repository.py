from sqlalchemy.orm import Session

from src.infrastructure.database import ProductModel


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
