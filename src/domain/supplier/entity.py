from dataclasses import dataclass
from datetime import datetime

from src.domain.supplier.value_objects import SupplierDocument


@dataclass
class Supplier:
    id: int | None
    name: str
    document: SupplierDocument
    email: str
    phone: str | None = None
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        name: str,
        document: str,
        email: str,
        phone: str | None = None,
    ) -> "Supplier":
        return cls(
            id=None,
            name=name,
            document=SupplierDocument.create(document),
            email=email,
            phone=phone,
        )

    def update_contact(
        self,
        name: str | None,
        email: str | None,
        phone: str | None,
    ) -> None:
        if name is not None:
            self.name = name
        if email is not None:
            self.email = email
        if phone is not None:
            self.phone = phone
