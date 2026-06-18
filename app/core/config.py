from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongo_uri: str = Field(alias="MONGO_URI")
    mongo_db_name: str = Field(default="dashboard_metrics", alias="MONGO_DB_NAME")
    secret_key: str = Field(alias="SECRET_KEY")
    master_users: str = Field(default="", alias="MASTER_USERS")
    cors_origins_raw: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
