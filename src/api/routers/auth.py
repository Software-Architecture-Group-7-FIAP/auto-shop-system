from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.composition.auth import compose_auth_service
from src.api.rate_limit import rate_limit
from src.api.schemas import LoginRequest, TokenResponse
from src.infrastructure.database import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("login", "rate_limit_login_requests"))],
)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    token = compose_auth_service(db).login(data.username, data.password)
    return TokenResponse(access_token=token)
