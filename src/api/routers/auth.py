from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import domain_error_handler, get_current_user
from src.api.schemas import LoginRequest, TokenResponse
from src.domain.exceptions import DomainError
from src.infrastructure.auth.jwt import authenticate_user, create_access_token, ensure_default_admin
from src.infrastructure.database import UserModel, get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    ensure_default_admin(db)
    user = authenticate_user(db, data.username, data.password)
    if not user:
        raise DomainError("Credenciais inválidas", "unauthorized")
    token = create_access_token(user.username)
    return TokenResponse(access_token=token)
