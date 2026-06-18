from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongo_uri: str
    mongo_db_name: str = "dashboard_metrics"
    secret_key: str
    master_users: str = ""
    cors_origins_raw: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
        fields={
            "mongo_uri": "MONGO_URI",
            "mongo_db_name": "MONGO_DB_NAME",
            "secret_key": "SECRET_KEY",
            "master_users": "MASTER_USERS",
            "cors_origins_raw": "CORS_ORIGINS",
        },
    )

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]

    @property
    def master_user_list(self) -> list[str]:
        return [item.strip().lower() for item in self.master_users.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
