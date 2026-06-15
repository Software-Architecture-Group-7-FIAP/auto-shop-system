class DomainError(Exception):
    def __init__(self, message: str, code: str = "domain_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(DomainError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, "not_found")


class ValidationError(DomainError):
    def __init__(self, message: str):
        super().__init__(message, "validation_error")


class ConflictError(DomainError):
    def __init__(self, message: str):
        super().__init__(message, "conflict_error")


class UnauthorizedError(DomainError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, "unauthorized")


class ForbiddenError(DomainError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, "forbidden")
