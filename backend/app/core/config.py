"""Load runtime configuration for the EQIP API."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read environment-backed backend settings.

    Notes:
        Production authentication adapters are intentionally not implemented in
        this governed-portfolio increment.
    """

    mongodb_uri: str
    mongodb_db: str
    auth_mode: str = "development"
    development_user_id: str = "dev-portfolio-user"
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        """Split configured CORS origins into a normalized list.

        Returns:
            Explicit origins accepted by the browser API middleware.
        """
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the cached process configuration.

    Returns:
        Validated environment settings.
    """
    return Settings()
