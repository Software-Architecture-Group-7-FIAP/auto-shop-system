from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.api.routes.health import router as health_router
from src.domain.exceptions import DomainError
from src.infrastructure.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    yield


def register_exception_handlers(app: FastAPI) -> None:
    status_map = {
        "not_found": 404,
        "validation_error": 422,
        "conflict_error": 409,
        "unauthorized": 401,
        "forbidden": 403,
    }

    @app.exception_handler(DomainError)
    async def domain_exception_handler(request: Request, exc: DomainError):
        return JSONResponse(
            status_code=status_map.get(exc.code, 400),
            content={"detail": exc.message, "code": exc.code},
        )


def create_app() -> FastAPI:
    app = FastAPI(
        title="Oficina Mecânica API",
        description="FIAP 15SOAT Tech Challenge — Fase 1",
        version="0.1.0",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    return app
