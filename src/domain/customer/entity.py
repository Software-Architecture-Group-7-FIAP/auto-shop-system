from dataclasses import dataclass, field
from datetime import datetime

from src.domain.customer.value_objects import Document
from src.domain.exceptions import ValidationError


@dataclass
class Customer:
    id: int | None
    name: str
    email: str
    address: str
    phone: str | None = None
    created_at: datetime | None = None
    _documents: list[Document] = field(default_factory=list)

    @property
    def documents(self) -> list[Document]:
        return self._documents.copy()

    @classmethod
    def create(
        cls,
        name: str,
        document: str,
        email: str,
        address: str,
        phone: str | None = None,
    ) -> "Customer":
        cls._validate_address(address)
        customer = cls(
            id=None,
            name=name,
            email=email,
            address=address.strip(),
            phone=phone,
        )
        customer.add_document(document)
        return customer

    def add_document(self, document_raw: str) -> None:
        new_document = Document.create(document_raw)
        is_cpf = len(new_document) == 11
        has_cpf = any(len(document) == 11 for document in self._documents)

        if is_cpf and has_cpf:
            raise ValidationError("CPF já cadastrado.")

        if new_document in self._documents:
            raise ValidationError("Documento já cadastrado.")

        self._documents.append(new_document)

    def has_document(self, document: str | Document) -> bool:
        normalized = Document.create(document) if isinstance(document, str) else document
        return normalized in self._documents

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
            self._validate_address(address)
            self.address = address.strip()

    @staticmethod
    def _validate_address(address: str) -> None:
        if not address or not address.strip():
            raise ValidationError("Endereço é obrigatório")
