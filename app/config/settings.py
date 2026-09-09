"""Application settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = "api-palzoltan-net"
    version: str = "0.1.0"
    debug: bool = False

    class Config:
        """Settings configuration."""

        env_file = ".env"


settings = Settings()
