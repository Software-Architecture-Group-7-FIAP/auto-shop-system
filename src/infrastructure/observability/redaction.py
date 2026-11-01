import re

_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_BEARER = re.compile(r"(?i)\bBearer\s+\S+")
_SECRET_FIELD = re.compile(
    r'''(?ix)
    (?P<prefix>["']?\b(?:[a-z0-9_-]*(?:password|senha|secret|token|authorization|cookie|session|api_key)[a-z0-9_-]*)["']?\s*[:=]\s*)
    (?P<value>"[^"]*"|'[^']*'|[^\s,}]+)
    '''
)
_DATABASE_URL = re.compile(
    r"(?i)(\b(?:postgres(?:ql)?|mysql)(?:\+[^:/?#\s]+)?://[^:/?#\s]+:)[^@/\s]+(@)"
)


def redact(value: str) -> str:
    """Strip documents, tokens and secrets before a line is written."""
    value = _SECRET_FIELD.sub(lambda match: f'{match.group("prefix")}[REDACTED]', value)
    value = _DATABASE_URL.sub(r"\1[REDACTED]\2", value)
    value = _JWT.sub("[REDACTED]", value)
    value = _BEARER.sub("Bearer [REDACTED]", value)
    value = _CNPJ.sub("[REDACTED]", value)
    value = _CPF.sub("[REDACTED]", value)
    return value
