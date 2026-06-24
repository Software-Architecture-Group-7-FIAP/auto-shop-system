from src.application.ports.unit_of_work import UnitOfWork
from src.domain.exceptions import ConflictError, NotFoundError
from src.domain.product.entity import Product
from src.domain.product.repository import ProductRepository
from src.domain.supplier.entity import Supplier
from src.domain.supplier.repository import SupplierRepository


class ProductService:
    def __init__(
        self,
        products: ProductRepository,
        suppliers: SupplierRepository,
        uow: UnitOfWork,
    ):
        self.products = products
        self.suppliers = suppliers
        self.uow = uow

    def create(
        self,
        name: str,
        sku: str,
        unit_price: float,
        stock_quantity: int = 0,
        description: str | None = None,
        supplier_id: int | None = None,
    ) -> Product:
        if self.products.exists_by_sku(sku):
            raise ConflictError("Produto com este SKU já existe")
        self._ensure_supplier_exists(supplier_id)
        product = Product.create(
            name=name,
            sku=sku,
            unit_price=unit_price,
            stock_quantity=stock_quantity,
            description=description,
            supplier_id=supplier_id,
        )
        created = self.products.add(product)
        self.uow.commit()
        return created

    def get_by_id(self, product_id: int) -> Product:
        product = self.products.get_by_id(product_id)
        if not product:
            raise NotFoundError("Produto não encontrado")
        return product

    def list_all(self) -> list[Product]:
        return self.products.list_all()

    def update(
        self,
        product_id: int,
        name: str | None,
        unit_price: float | None,
        description: str | None,
        supplier_id: int | None,
    ) -> Product:
        if supplier_id is not None:
            self._ensure_supplier_exists(supplier_id)
        product = self.get_by_id(product_id)
        product.update_details(name, unit_price, description, supplier_id)
        updated = self.products.save(product)
        self.uow.commit()
        return updated

    def update_stock(self, product_id: int, quantity: int) -> Product:
        product = self.get_by_id(product_id)
        product.update_stock(quantity)
        updated = self.products.save(product)
        self.uow.commit()
        return updated

    def delete(self, product_id: int) -> None:
        product = self.get_by_id(product_id)
        self.products.delete(product)
        self.uow.commit()

    def _ensure_supplier_exists(self, supplier_id: int | None) -> None:
        if supplier_id is None or not self.suppliers.get_by_id(supplier_id):
            raise NotFoundError("Fornecedor não encontrado")


class SupplierService:
    def __init__(
        self,
        suppliers: SupplierRepository,
        products: ProductRepository,
        uow: UnitOfWork,
    ):
        self.suppliers = suppliers
        self.products = products
        self.uow = uow

    def create(
        self, name: str, document: str, email: str, phone: str | None = None
    ) -> Supplier:
        supplier = Supplier.create(name=name, document=document, email=email, phone=phone)
        created = self.suppliers.add(supplier)
        self.uow.commit()
        return created

    def get_by_id(self, supplier_id: int) -> Supplier:
        supplier = self.suppliers.get_by_id(supplier_id)
        if not supplier:
            raise NotFoundError("Fornecedor não encontrado")
        return supplier

    def list_all(self) -> list[Supplier]:
        return self.suppliers.list_all()

    def update(
        self,
        supplier_id: int,
        name: str | None,
        email: str | None,
        phone: str | None,
    ) -> Supplier:
        supplier = self.get_by_id(supplier_id)
        supplier.update_contact(name=name, email=email, phone=phone)
        updated = self.suppliers.save(supplier)
        self.uow.commit()
        return updated

    def delete(self, supplier_id: int) -> None:
        supplier = self.get_by_id(supplier_id)
        if self.products.exists_by_supplier_id(supplier_id):
            raise ConflictError("Fornecedor possui produtos vinculados")
        self.suppliers.delete(supplier)
        self.uow.commit()
