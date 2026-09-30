from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py  ->  sube 3 niveles hasta la raíz del proyecto
BASE_DIR = Path(__file__).resolve().parents[2]


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
    jwt_secret: str = "clave-temporal"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # API
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:5173"

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


settings = Settings()
