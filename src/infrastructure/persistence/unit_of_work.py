from sqlalchemy.orm import Session

from src.infrastructure.observability.business_telemetry import (
    discard_pending_business_events,
)

class SqlAlchemyUnitOfWork:
    def __init__(self, db: Session):
        self.db = db

    def commit(self) -> None:
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            discard_pending_business_events(self.db)
            raise

    def rollback(self) -> None:
        self.db.rollback()
