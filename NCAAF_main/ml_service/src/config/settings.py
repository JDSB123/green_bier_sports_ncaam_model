"""Configuration settings for the ML service."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "ncaaf_v5"
    database_user: str = "ncaaf_user"
    database_password: str
    database_ssl_mode: str = "disable"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # Application
    app_env: str = "development"
    log_level: str = "info"
    ml_service_port: int = 8000

    # Model Configuration
    model_path: str = "/app/models"

    # Timeout Configuration
    database_connect_timeout: int = 10  # seconds
    database_query_timeout: int = 300  # 5 minutes for long queries
    database_pool_timeout: int = 30  # seconds to wait for connection from pool

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def database_url(self) -> str:
        """Get PostgreSQL connection URL."""
        return (
            f"postgresql://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env == "production"


# Global settings instance
settings = Settings()
