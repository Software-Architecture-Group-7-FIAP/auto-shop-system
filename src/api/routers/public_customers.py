from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from src.api.composition.customers import compose_customer_public_lookup_service
from src.api.mappers.customers import customer_to_public_response
from src.api.rate_limit import enforce_public_rate_limit
from src.api.schemas import CustomerPublicLookupRequest, CustomerPublicResponse
from src.application.services.customer_public_lookup_service import (
    CustomerPublicLookupCriteria,
    GENERIC_LOOKUP_ERROR,
)
from src.domain.exceptions import DomainError
from src.infrastructure.database import get_db

router = APIRouter(prefix="/customers", tags=["Public Customers"])


@router.post(
    "/lookup",
    response_model=CustomerPublicResponse,
)
def lookup_customer(
    data: CustomerPublicLookupRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    fingerprint = "|".join(
        (
            data.document.strip(),
            str(data.email).strip().lower() if data.email is not None else "",
            data.phone.strip() if data.phone is not None else "",
            data.plate.strip().upper() if data.plate is not None else "",
        )
    )
    enforce_public_rate_limit(request, fingerprint, "customer_lookup")
    try:
        customer = compose_customer_public_lookup_service(db).lookup(
            CustomerPublicLookupCriteria(
                document=data.document,
                email=str(data.email) if data.email is not None else None,
                phone=data.phone,
                plate=data.plate,
            )
        )
        return customer_to_public_response(customer)
    except DomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=GENERIC_LOOKUP_ERROR,
        ) from exc
