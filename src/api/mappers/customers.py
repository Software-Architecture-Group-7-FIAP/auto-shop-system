from src.api.schemas import CustomerPublicResponse, CustomerResponse
from src.domain.customer.entity import Customer


def customer_to_response(customer: Customer) -> CustomerResponse:
    return CustomerResponse(
        id=customer.id,
        name=customer.name,
        documents=[str(document) for document in customer.documents],
        email=customer.email,
        phone=customer.phone,
        address=customer.address,
        created_at=customer.created_at,
    )


def customer_to_public_response(customer: Customer) -> CustomerPublicResponse:
    return CustomerPublicResponse(
        id=customer.id,
        name=customer.name,
    )
