from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.errors import Rechazo
from app.routers import (
    anticipos,
    auth,
    clientes,
    dashboard,
    facturas,
    informes,
    localidades,
    recibos,
    servicios,
    sugerencias,
)

app = FastAPI(
    title="Sistema de gestión — Estudio contable",
    version="2.0.0",
    description="API REST: autenticación, roles y gestión de clientes.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(clientes.router, prefix=settings.api_prefix)
app.include_router(sugerencias.router, prefix=settings.api_prefix)
app.include_router(servicios.router, prefix=settings.api_prefix)
app.include_router(localidades.router, prefix=settings.api_prefix)
app.include_router(facturas.router, prefix=settings.api_prefix)
app.include_router(recibos.router, prefix=settings.api_prefix)
app.include_router(anticipos.router, prefix=settings.api_prefix)
app.include_router(dashboard.router, prefix=settings.api_prefix)
app.include_router(informes.router, prefix=settings.api_prefix)


@app.exception_handler(Rechazo)
def _rechazo(_request: Request, exc: Rechazo):
    """Reglas de negocio: mensaje tal cual para el usuario."""
    return JSONResponse(status_code=exc.codigo, content={"detail": exc.mensaje})


@app.exception_handler(RequestValidationError)
def _validacion(_request: Request, exc: RequestValidationError):
    """Errores de Pydantic: una sola línea por campo, en castellano."""
    errores = []
    for error in exc.errors():
        campo = " → ".join(str(p) for p in error["loc"][1:])
        errores.append(f"{campo}: {error['msg']}")
    return JSONResponse(status_code=422, content={"detail": "; ".join(errores)})


@app.get("/health", tags=["salud"])
def health():
    return {"status": "ok", "fase": 4}
