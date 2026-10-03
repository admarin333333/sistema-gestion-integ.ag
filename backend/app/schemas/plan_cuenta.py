from typing import Optional

from pydantic import BaseModel, Field


class PlanCuentaOut(BaseModel):
    """Como sale una cuenta del plan."""

    id_cuenta: int
    codigo: str
    nombre: str
    cuenta_padre_id: Optional[int] = None
    # El código del padre, para armar el árbol en el navegador sin otra consulta.
    codigo_padre: Optional[str] = None
    nivel: int
    # "BALANCE" (activo/pasivo/patrimonio neto) o "RESULTADO" (ingresos,
    # costos, gastos, resultados financieros).
    naturaleza: str
    # "DEUDORA" (suma en el Debe) o "ACREEDORA" (suma en el Haber).
    # NULL en los agrupadores: pueden mezclar las dos.
    deudora_acreadora: Optional[str] = None
    imputable: bool
    tipo_auxiliar: Optional[str] = None
    activa: bool
    # Cuántas subcuentas tiene: si tiene, no se puede borrar ni volver
    # imputable (es un agrupador).
    tiene_hijas: bool = False
    # La línea completa desde la raíz, para buscar y mostrar ("1.1 ACTIVO
    # CORRIENTE / 1.1.01 Caja y bancos / 1.1.01.01 Caja").
    camino: str = ""


class PlanCuentaCrear(BaseModel):
    """Alta de una cuenta nueva, colgada de una cuenta existente."""

    cuenta_padre_id: int = Field(..., gt=0)
    nombre: str = Field(..., min_length=1, max_length=150)
    imputable: bool = True
    tipo_auxiliar: Optional[str] = Field(default=None, max_length=30)


class PlanCuentaEditar(BaseModel):
    """Cambios de una cuenta. El código no se toca nunca."""

    nombre: Optional[str] = Field(default=None, min_length=1, max_length=150)
    imputable: Optional[bool] = None
    tipo_auxiliar: Optional[str] = Field(default=None, max_length=30)
    activa: Optional[bool] = None