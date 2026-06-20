from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.composition.customers import compose_customer_service
from src.api.dependencies import domain_error_handler
from src.api.mappers.customers import customer_to_public_response
from src.api.schemas import CustomerPublicResponse
from src.domain.exceptions import DomainError
from src.infrastructure.database import get_db

router = APIRouter(prefix="/customers", tags=["Public Customers"])


@router.get("/by-document/{document}", response_model=CustomerPublicResponse)
def get_customer_by_document(document: str, db: Session = Depends(get_db)):
    try:
        customer = compose_customer_service(db).get_by_document(document)
        return customer_to_public_response(customer)
    except DomainError as e:
        raise domain_error_handler(e)
