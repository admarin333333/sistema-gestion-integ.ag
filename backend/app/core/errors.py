class Rechazo(Exception):
    """Violación de una regla de negocio.

    El mensaje es para mostrarle al usuario tal cual (en castellano).
    `codigo` es el estado HTTP que se le devuelve.
    """

    def __init__(self, mensaje: str, codigo: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
