# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

_CSV_FIELDS: frozenset[str] = frozenset({"transports", "lanes"})


class _CsvEnvSource(EnvSettingsSource):
    """EnvSettingsSource that parses comma-separated strings for list[str] fields."""

    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        if field_name in _CSV_FIELDS and isinstance(value, str):
            return [t.strip() for t in value.split(",") if t.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class BrokerConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PROBE_BROKER_",
        extra="ignore",
        case_sensitive=False,
    )

    # Transport selection (PROBE_BROKER_TRANSPORTS)
    transports: list[str] = ["stdio", "socket"]

    # Unix-socket transport
    socket_path: str = "/run/brontes-probe-mcp/probe.sock"

    # TCP transport
    tcp_host: str = "127.0.0.1"
    tcp_port: int = 7172
    tcp_allow_remote: bool = False
    token: str | None = None
    token_file: str | None = None

    # Lane configuration (PROBE_BROKER_LANES)
    lanes: list[str] = ["swd", "itm_swo"]

    # Toolchain
    pyocd_bin: str = "pyocd"
    gdb_bin: str = "arm-none-eabi-gdb"
    backend: str = "pyocd"
    gdb_port: int = 3333
    log_dir: str = "/tmp/brontes-probe-mcp-logs/"
    default_pack: str | None = None

    # ITM/SWO
    enable_swv: bool = False

    # Image identity verification
    digest_check: str = "enforce"
    image_digest: str | None = None
    image_tag: str | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            _CsvEnvSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )
