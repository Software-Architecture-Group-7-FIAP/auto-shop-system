from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import domain_error_handler, get_current_user
from src.api.schemas import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    StockUpdate,
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)
from src.application.services.product_service import ProductService, SupplierService
from src.domain.exceptions import DomainError
from src.infrastructure.database import UserModel, get_db

products_router = APIRouter(prefix="/admin/products", tags=["Products"])
suppliers_router = APIRouter(prefix="/admin/suppliers", tags=["Suppliers"])


@products_router.post("", response_model=ProductResponse, status_code=201)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return ProductService(db).create(
            data.name, data.sku, data.unit_price, data.stock_quantity, data.description, data.supplier_id
        )
    except DomainError as e:
        raise domain_error_handler(e)


@products_router.get("", response_model=list[ProductResponse])
def list_products(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return ProductService(db).list_all()


@products_router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return ProductService(db).get_by_id(product_id)
    except DomainError as e:
        raise domain_error_handler(e)


@products_router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return ProductService(db).update(
            product_id, data.name, data.unit_price, data.description, data.supplier_id
        )
    except DomainError as e:
        raise domain_error_handler(e)


@products_router.patch("/{product_id}/stock", response_model=ProductResponse)
def update_stock(
    product_id: int,
    data: StockUpdate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return ProductService(db).update_stock(product_id, data.quantity)
    except DomainError as e:
        raise domain_error_handler(e)


@products_router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        ProductService(db).delete(product_id)
    except DomainError as e:
        raise domain_error_handler(e)


@suppliers_router.post("", response_model=SupplierResponse, status_code=201)
def create_supplier(
    data: SupplierCreate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return SupplierService(db).create(data.name, data.document, data.email, data.phone)
    except DomainError as e:
        raise domain_error_handler(e)


@suppliers_router.get("", response_model=list[SupplierResponse])
def list_suppliers(
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    return SupplierService(db).list_all()


@suppliers_router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return SupplierService(db).get_by_id(supplier_id)
    except DomainError as e:
        raise domain_error_handler(e)


@suppliers_router.put("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        return SupplierService(db).update(supplier_id, data.name, data.email, data.phone)
    except DomainError as e:
        raise domain_error_handler(e)


@suppliers_router.delete("/{supplier_id}", status_code=204)
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    _: UserModel = Depends(get_current_user),
):
    try:
        SupplierService(db).delete(supplier_id)
    except DomainError as e:
        raise domain_error_handler(e)
