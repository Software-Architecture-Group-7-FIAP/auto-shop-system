"""Explicitly promote the first user to ADMIN.

This is intentionally a separate command so a migration never grants an
administrative role implicitly.
"""

from src.infrastructure.database import SessionLocal, UserModel
from src.domain.auth.entity import UserRole


def promote_first_admin() -> None:
    db = SessionLocal()
    try:
        user = db.query(UserModel).order_by(UserModel.id).first()
        if user is None:
            raise SystemExit("No users found")
        user.role = UserRole.ADMIN
        db.commit()
        print(f"Promoted user {user.username} to ADMIN")
    finally:
        db.close()


if __name__ == "__main__":
    promote_first_admin()
