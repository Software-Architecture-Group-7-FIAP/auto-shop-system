from typing import Protocol


class ServiceOrderTrackingTokenService(Protocol):
    def create_token(self) -> str:
        ...

    def fingerprint(self, token: str) -> str:
        ...
