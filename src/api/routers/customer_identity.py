from fastapi import APIRouter, Depends, Response

from src.api.dependencies import get_current_customer
from src.api.schemas import CustomerIdentityResponse
from src.domain.auth.principal import CustomerPrincipal

router = APIRouter(prefix="/customer", tags=["Customer Identity"])


@router.get("/me", response_model=CustomerIdentityResponse)
def me(
    response: Response,
    principal: CustomerPrincipal = Depends(get_current_customer),
) -> CustomerIdentityResponse:
    response.headers["Cache-Control"] = "no-store"
    return CustomerIdentityResponse(customer_id=principal.customer_id)
