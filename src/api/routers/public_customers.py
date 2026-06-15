from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import domain_error_handler
from src.api.schemas import CustomerResponse
from src.application.services.customer_service import CustomerService
from src.domain.exceptions import DomainError
from src.infrastructure.database import get_db

router = APIRouter(prefix="/customers", tags=["Public Customers"])


@router.get("/by-document/{document}", response_model=CustomerResponse)
def get_customer_by_document(document: str, db: Session = Depends(get_db)):
    try:
        return CustomerService(db).get_by_document(document)
    except DomainError as e:
        raise domain_error_handler(e)
