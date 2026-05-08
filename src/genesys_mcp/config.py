"""Application settings loaded from environment variables."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Transport = Literal["stdio", "http"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

__all__ = ["LogLevel", "Settings", "Transport"]


class Settings(BaseSettings):
    """Runtime configuration for the Genesys MCP server.

    Settings are read from environment variables (and a `.env` file if present).
    All values are immutable after construction.

    Pro extends this class via subclassing; pass an instance to
    ``create_server(settings=...)``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    transport: Transport = Field(default="stdio", validation_alias="MCP_TRANSPORT")
    host: str = Field(default="127.0.0.1", validation_alias="MCP_HOST")
    port: int = Field(default=8000, validation_alias="MCP_PORT", ge=1, le=65535)

    log_level: LogLevel = Field(default="INFO", validation_alias="LOG_LEVEL")

    enable_writes: bool = Field(
        default=False, validation_alias="GENESYS_MCP_ENABLE_WRITES"
    )

    genesys_region: str = Field(
        default="mypurecloud.com", validation_alias="GENESYS_REGION"
    )
    genesys_client_id: str | None = Field(
        default=None, validation_alias="GENESYS_CLIENT_ID"
    )
    genesys_client_secret: SecretStr | None = Field(
        default=None, validation_alias="GENESYS_CLIENT_SECRET"
    )

    otel_endpoint: str | None = Field(
        default=None, validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_service_name: str = Field(
        default="genesys-mcp", validation_alias="OTEL_SERVICE_NAME"
    )

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, v: object) -> object:
        if isinstance(v, str):
            return v.upper()
        return v

    @field_validator("transport", mode="before")
    @classmethod
    def _lower_transport(cls, v: object) -> object:
        if isinstance(v, str):
            return v.lower()
        return v
