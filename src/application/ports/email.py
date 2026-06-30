from dataclasses import dataclass


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    content: bytes
    mime_type: str
