from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.exceptions import RequestValidationError

from src.api.routers import (
    auth,
    budgets,
    customers,
    execution,
    inventory,
    invoices,
    products,
    public_customers,
    service_orders,
    services,
    vehicles,
)
from src.domain.exceptions import DomainError
from src.config import settings


def _configure_app_logging() -> None:
    app_logger = logging.getLogger("src")
    app_logger.setLevel(logging.INFO)
    if app_logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s - %(message)s"))
    app_logger.addHandler(handler)


_configure_app_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Oficina Mecânica API",
    description="Sistema Integrado de Atendimento e Execução de Serviços - FIAP 15SOAT Tech Challenge",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins(),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )
    if settings.security_hsts_enabled:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
    return response


@app.exception_handler(DomainError)
async def domain_exception_handler(request: Request, exc: DomainError):
    status_map = {
        "not_found": 404,
        "validation_error": 422,
        "conflict_error": 409,
        "unauthorized": 401,
        "forbidden": 403,
    }
    return JSONResponse(
        status_code=status_map.get(exc.code, 400),
        content={"detail": exc.message, "code": exc.code},
    )

ERROR_TRANSLATIONS = {
    "missing": "Este campo é obrigatório.",
    "greater_than": "O valor deve ser maior que {gt}.",
    "greater_than_equal": "O valor deve ser maior ou igual a {ge}.",
    "less_than": "O valor deve ser menor que {lt}.",
    "less_than_equal": "O valor deve ser menor ou igual a {le}.",
    "int_type": "O valor deve ser um número inteiro válido.",
    "string_type": "O valor deve ser um texto válido.",
    "value_error": "Valor inválido fornecido."
}

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first_error = exc.errors()[0]
    
    error_type = first_error.get("type")
    ctx = first_error.get("ctx", {})
    
    if error_type in ERROR_TRANSLATIONS:
        translated_message = ERROR_TRANSLATIONS[error_type].format(**ctx)
    else:
        translated_message = "Os dados enviados são inválidos. Verifique os campos."

    return JSONResponse(
        status_code=422,
        content={"detail": f"Dados inválidos: {translated_message}"}
    )

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request):
    port = request.url.port or 80
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Oficina Mecânica API</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      font-family: system-ui, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
    }}
    main {{
      text-align: center;
      padding: 2rem;
      border: 1px solid #334155;
      border-radius: 1rem;
      background: #1e293b;
      max-width: 32rem;
    }}
    h1 {{ margin: 0 0 0.5rem; font-size: 1.5rem; }}
    p {{ margin: 0.5rem 0; color: #94a3b8; }}
    .status {{
      display: inline-block;
      margin-top: 1rem;
      padding: 0.35rem 0.75rem;
      border-radius: 999px;
      background: #14532d;
      color: #bbf7d0;
      font-weight: 600;
    }}
    a {{ color: #38bdf8; }}
  </style>
</head>
<body>
  <main>
    <h1>Oficina Mecânica API</h1>
    <p>A aplicação está em execução.</p>
    <p>Porta: <strong>{port}</strong></p>
    <span class="status">Online</span>
    <p style="margin-top: 1.5rem;">
      <a href="http://localhost:4200">Painel Angular (dev)</a>
      &nbsp;·&nbsp;
      <a href="/app/">Painel legado (clientes)</a>
      &nbsp;·&nbsp;
      <a href="/docs">Documentação da API</a>
    </p>
  </main>
</body>
</html>"""


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}


api_prefix = "/api/v1"

app.include_router(auth.router, prefix=api_prefix)
app.include_router(customers.router, prefix=api_prefix)
app.include_router(public_customers.router, prefix=api_prefix)
app.include_router(vehicles.router, prefix=api_prefix)
app.include_router(services.router, prefix=api_prefix)
app.include_router(products.products_router, prefix=api_prefix)
app.include_router(products.suppliers_router, prefix=api_prefix)
app.include_router(budgets.admin_router, prefix=api_prefix)
app.include_router(budgets.public_router, prefix=api_prefix)
app.include_router(service_orders.admin_router, prefix=api_prefix)
app.include_router(service_orders.public_router, prefix=api_prefix)
app.include_router(inventory.router, prefix=api_prefix)
app.include_router(execution.execution_router, prefix=api_prefix)
app.include_router(execution.withdrawals_router, prefix=api_prefix)
app.include_router(invoices.router, prefix=api_prefix)

frontend_dir = Path(__file__).resolve().parents[1] / "frontend" / "legacy-panel"


def _frontend_asset(filename: str) -> FileResponse:
    asset = (frontend_dir / filename).resolve()
    if not str(asset).startswith(str(frontend_dir.resolve())):
        raise HTTPException(status_code=404, detail="Not found")
    if not asset.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(asset)


@app.get("/app", include_in_schema=False)
def app_root():
    return RedirectResponse(url="/app/", status_code=307)


@app.get("/app/", include_in_schema=False)
def app_index():
    index = frontend_dir / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index)


@app.get("/app/{filename}", include_in_schema=False)
def app_assets(filename: str):
    return _frontend_asset(filename)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
