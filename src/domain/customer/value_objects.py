from src.domain.value_objects.validators import DocumentValidator


class Document(str):
    def __new__(cls, raw: str) -> "Document":
        normalized = DocumentValidator.validate(raw)
        return str.__new__(cls, normalized)

    @classmethod
    def create(cls, raw: str) -> "Document":
        return cls(raw)


# Backward-compatible alias
CustomerDocument = Document
