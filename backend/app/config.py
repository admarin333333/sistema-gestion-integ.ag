from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py  ->  sube 3 niveles hasta la raíz del proyecto
BASE_DIR = Path(__file__).resolve().parents[2]

# El secreto que venía de ejemplo. Está prohibido usarlo de verdad: con él,
# cualquiera que tenga el código puede fabricar un token de administrador (el JWT
# es HS256, o sea que se firma con una clave simétrica) y entrar sin contraseña.
SECRETO_PROHIBIDO = "clave-temporal"


class ConfigError(Exception):
    """
    La configuración no sirve para arrancar.

    Va como excepción propia y no como error de validación de Pydantic porque el
    mensaje tiene que ser legible: si no, el contador ve un volcado de datos de
    Pydantic y no entiende que lo que falta es el secreto.
    """


class Settings(BaseSettings):
    """Toda la configuración vive en el archivo .env de la raíz."""

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # MySQL
    db_host: str = "127.0.0.1"
    db_port: int = 3307
    db_name: str = "gestion_contable"
    db_user: str = "root"
    db_password: str = ""

    # JWT
    # **Sin valor por defecto a propósito.** Antes era "clave-temporal", y si
    # faltaba la variable en el `.env` el sistema arrancaba igual, con una clave
    # que estaba escrita en el código y en la documentación. Eso es una puerta
    # abierta: con esa clave se puede firmar un token de administrador a mano y
    # entrar sin contraseña.
    #
    # Ahora, si no está en el `.env`, queda en `None` y `validar()` frena el
    # arranque con un mensaje que dice qué hacer.
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # API
    api_prefix: str = "/api"
    # Los orígenes vienen del .env (CORS_ORIGINS). Ahí están los cuatro que
    # hacen falta: el dev server y el preview, cada uno en localhost y en
    # 127.0.0.1. Falta uno y esa página queda en blanco con un error de CORS
    # en la consola, sin mostrar ningún mensaje.
    # 5173 es el dev server de Vite (con HMR) y 4173 el preview de `vite preview`
    # (que sirve `dist`). Los dos hacen falta: si el preview no está permitido,
    # el navegador lo manda a /login, el POST de login lo bloquea CORS y la
    # pantalla queda solo con el color del fondo — sin mensaje de error, que es
    # lo más confuso que puede pasar.
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173"
    )

    # Informes: encabezado de todos los listados en PDF y Excel
    nombre_estudio: str = "ESTUDIO INTEGRAL AM"

    # Mail (Gmail) — envío automático de la factura al cliente.
    # Si smtp_user o smtp_password están vacíos, no se manda nada y la
    # factura igual se guarda (avisándolo en la respuesta).
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def chequear_secreto(self) -> None:
        """
        Frena el arranque si el secreto del JWT no sirve.

        Se llama desde `main.py` al arrancar, no al importar el módulo: así el
        error sale una vez, cuando se levanta la API, y no en el primer import
        de cualquier archivo (que puede ser un script suelto y no la API).

        Tres casos, todos frenan:

        1. No está en el `.env`.
        2. Es el de ejemplo ("clave-temporal"), que está escrito en el código.
        3. Es cortísimo: con menos de 32 caracteres la clave se adivina por fuerza
           bruta. No es un límite arbitrario, es el mínimo de referencia para una
           clave simétrica.

        El mensaje dice **qué hacer**, no solo qué está mal: un error que no se
        entiende no se arregla, se empieza a odiar el sistema.
        """
        GENERAR = (
            '    python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )

        if self.jwt_secret is None or not self.jwt_secret.strip():
            raise ConfigError(
                "Falta JWT_SECRET en el archivo .env.\n"
                "\n"
                "Sin esa clave la API no puede arrancar. Se genera una con:\n"
                + GENERAR
                + "\n\ny se copia el resultado en la línea JWT_SECRET= del .env."
            )

        if self.jwt_secret.strip() == SECRETO_PROHIBIDO:
            raise ConfigError(
                'El JWT_SECRET del .env es el de ejemplo ("'
                + SECRETO_PROHIBIDO
                + '").\n'
                "\n"
                "Esa clave está escrita en el código y en la documentación: con ella "
                "cualquiera que tenga el proyecto puede fabricar un token de "
                "administrador. Hay que cambiarla por una propia.\n"
                "\n"
                "Para generar una:\n" + GENERAR
            )

        if len(self.jwt_secret.strip()) < 32:
            raise ConfigError(
                "El JWT_SECRET del .env tiene "
                + str(len(self.jwt_secret.strip()))
                + " caracteres y son muy pocos.\n"
                "\n"
                "Con una clave corta se pueden probar millones de combinaciones por "
                "segundo y adivinarla. Se necesitan 32 o más.\n"
                "\n"
                "Para generar una:\n" + GENERAR
            )


settings = Settings()
