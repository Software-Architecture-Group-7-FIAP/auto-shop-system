from dataclasses import dataclass
from datetime import datetime

from src.domain.customer.value_objects import CustomerDocument
from src.domain.enums import PersonType
from src.domain.exceptions import ValidationError


@dataclass
class Customer:
    id: int | None
    name: str
    person_type: PersonType
    document: CustomerDocument
    email: str
    address: str
    phone: str | None = None
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        name: str,
        person_type: PersonType,
        document: str,
        email: str,
        address: str,
        phone: str | None = None,
    ) -> "Customer":
        customer_document = CustomerDocument.create(document)
        cls._validate_person_type_matches_document(person_type, customer_document)
        return cls(
            id=None,
            name=name,
            person_type=person_type,
            document=customer_document,
            email=email,
            address=address,
            phone=phone,
        )

    def update_contact(
        self,
        name: str | None,
        email: str | None,
        phone: str | None,
        address: str | None,
    ) -> None:
        if name is not None:
            self.name = name
        if email is not None:
            self.email = email
        if phone is not None:
            self.phone = phone
        if address is not None:
            self.address = address

    @staticmethod
    def _validate_person_type_matches_document(
        person_type: PersonType, document: CustomerDocument
    ) -> None:
        expected_length = 11 if person_type == PersonType.PF else 14
        if len(document) != expected_length:
            raise ValidationError("Cliente inválido")
