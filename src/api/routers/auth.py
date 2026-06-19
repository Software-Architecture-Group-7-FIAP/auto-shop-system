from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.composition.auth import compose_auth_service
from src.api.schemas import LoginRequest, TokenResponse
from src.infrastructure.database import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    token = compose_auth_service(db).login(data.username, data.password)
    return TokenResponse(access_token=token)
