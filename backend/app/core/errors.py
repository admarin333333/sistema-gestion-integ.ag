class Rechazo(Exception):
    """Violación de una regla de negocio.

    El mensaje es para mostrarle al usuario tal cual (en castellano).
    `codigo` es el estado HTTP que se le devuelve.
    """

    def __init__(self, mensaje: str, codigo: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


def datos_invalidos(exc) -> Rechazo:
    """Convierte un error de validación de pydantic en un Rechazo legible.

    Hace falta porque algunos routers arman el schema a mano (con `**datos`).
    Si un campo falta o viene con el tipo equivocado, sin esto la API
    contestaría un 500 sin explicación en vez de un 422 con el motivo.
    """
    partes = []
    for err in exc.errors():
        campo = str(err["loc"][-1]) if err["loc"] else "datos"
        partes.append(f"{campo}: {err['msg']}")
    detalle = "; ".join(partes) if partes else "revisá los datos"
    return Rechazo(f"Datos incorrectos — {detalle}", 422)
