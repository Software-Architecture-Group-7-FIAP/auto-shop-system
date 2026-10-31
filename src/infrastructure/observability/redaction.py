import re

_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_BEARER = re.compile(r"(?i)\bBearer\s+\S+")
_SECRET_FIELD = re.compile(
    r"(?i)\b(password|senha|secret|token|authorization)\b\s*[:=]\s*\S+"
)


def redact(value: str) -> str:
    """Strip documents, tokens and secrets before a line is written."""
    value = _SECRET_FIELD.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    value = _JWT.sub("[REDACTED]", value)
    value = _BEARER.sub("Bearer [REDACTED]", value)
    value = _CNPJ.sub("[REDACTED]", value)
    value = _CPF.sub("[REDACTED]", value)
    return value
