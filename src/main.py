from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.infrastructure.database import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from src.api.composition.auth import compose_auth_service

        compose_auth_service(db).ensure_default_admin()
    finally:
        db.close()
    yield


app = FastAPI(
    title="Oficina Mecânica API",
    description="Sistema Integrado de Atendimento e Execução de Serviços - FIAP 15SOAT Tech Challenge",
    version="1.0.0",
    lifespan=lifespan,
)


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
      <a href="/docs">Abrir documentação da API</a>
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
