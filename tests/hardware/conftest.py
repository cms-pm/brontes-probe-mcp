# SPDX-License-Identifier: Apache-2.0
"""HIL fixtures for hardware tests.

Configuration via environment variables (all optional):
  PROBE_HIL_TARGET       — pyocd target string     (default: stm32g474)
  PROBE_HIL_PROBE_UID    — probe serial number      (default: "")
  PROBE_HIL_ELF          — path to test firmware    (default: itm_probe path)
  PROBE_HIL_LOG_DIR      — log directory  (default: /tmp/brontes-hil-test-logs)
  PROBE_HIL_BACKEND      — pyocd|openocd            (default: pyocd)
  PROBE_HIL_SRAM_ADDR    — readable SRAM address    (default: 0x20000000)
  PROBE_HIL_PYOCD_BIN    — pyocd binary path        (default: .venv/bin/pyocd)
  PROBE_HIL_GDB_BIN      — arm-none-eabi-gdb path   (default: PlatformIO toolchain)
"""
from __future__ import annotations

import os
import secrets
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

import pytest

from brontes_probe_mcp.core.broker import BrokerCore
from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.transports.socket import _UnixServer
from brontes_probe_mcp.transports.tcp import _TcpServer

_REPO_ROOT = Path(__file__).parents[2]

_COCKPIT = Path("/Users/cms/proj/embedded/cockpit")

_DEFAULT_ELF = (
    "/Users/cms/proj/embedded/cockpit/tests/firmware/itm_probe"
    "/.pio/build/itm_probe_l4_rate_1k_stm32g474/firmware.elf"
)

# Cockpit-managed pack — contains Keil.STM32G4xx_DFP.pdsc
_DEFAULT_PACK = str(_COCKPIT / "third_party" / "STM32G4xx_DFP")

# PlatformIO GDB cross-compiler
_PIO_GDB = (
    "/Users/cms/.platformio/packages/toolchain-gccarmnoneeabi/bin/arm-none-eabi-gdb"
)

# Cockpit's pyocd has the STM32G4 pack already configured
_COCKPIT_PYOCD = str(_COCKPIT / ".venv" / "bin" / "pyocd")


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _find_binary(name: str, *hints: str) -> str:
    for h in hints:
        if h and Path(h).is_file():
            return h
    found = shutil.which(name)
    return found if found else name


@pytest.fixture(scope="session")
def hil_target() -> str:
    # stm32g474ceux is the exact part on the WeAct G474RE bench board
    return _env("PROBE_HIL_TARGET", "stm32g474ceux")


@pytest.fixture(scope="session")
def hil_probe_uid() -> str:
    return _env("PROBE_HIL_PROBE_UID", "")


@pytest.fixture(scope="session")
def hil_sram_addr() -> int:
    return int(_env("PROBE_HIL_SRAM_ADDR", "0x20000000"), 16)


@pytest.fixture(scope="session")
def hil_elf() -> Path:
    path = Path(_env("PROBE_HIL_ELF", _DEFAULT_ELF))
    if not path.exists():
        pytest.skip(f"test firmware ELF not found: {path}")
    return path


@pytest.fixture(scope="session")
def hil_pack() -> str:
    return _env("PROBE_HIL_PACK", _DEFAULT_PACK)


@pytest.fixture(scope="session")
def hil_config(tmp_path_factory: pytest.TempPathFactory) -> BrokerConfig:
    log_dir = str(tmp_path_factory.mktemp("hil-logs"))
    backend = _env("PROBE_HIL_BACKEND", "pyocd")
    pyocd_bin = _find_binary(
        "pyocd",
        _env("PROBE_HIL_PYOCD_BIN"),
        _COCKPIT_PYOCD,
        str(_REPO_ROOT / ".venv" / "bin" / "pyocd"),
    )
    gdb_bin = _find_binary(
        "arm-none-eabi-gdb",
        _env("PROBE_HIL_GDB_BIN"),
        _PIO_GDB,
    )
    return BrokerConfig(
        log_dir=log_dir,
        backend=backend,
        pyocd_bin=pyocd_bin,
        gdb_bin=gdb_bin,
    )


@pytest.fixture()
def hil_broker(hil_config: BrokerConfig) -> BrokerCore:
    return BrokerCore(config=hil_config)


@pytest.fixture()
def hil_isolated_broker(
    tmp_path_factory: pytest.TempPathFactory, hil_config: BrokerConfig
) -> BrokerCore:
    """Broker with its own isolated log_dir, for lifecycle tests that start/stop pyocd.

    Uses the same binaries/target/port as hil_config but a private meta directory
    so it won't conflict with the shared hil_session's meta file.
    """
    isolated_log = str(tmp_path_factory.mktemp("hil-isolated"))
    cfg = BrokerConfig(
        log_dir=isolated_log,
        backend=hil_config.backend,
        pyocd_bin=hil_config.pyocd_bin,
        gdb_bin=hil_config.gdb_bin,
    )
    return BrokerCore(config=cfg)


# Session-scoped session: pyocd stays up for the entire test run.
# Mirrors production where the container keeps pyocd alive persistently.
# Tests that explicitly stop/start the session manage it themselves.
@pytest.fixture(scope="session")
def hil_session(
    hil_config: BrokerConfig,
    hil_target: str,
    hil_probe_uid: str,
    hil_pack: str,
) -> Any:
    broker = BrokerCore(config=hil_config)
    kwargs: dict[str, Any] = {"target": hil_target, "pack": hil_pack}
    if hil_probe_uid:
        kwargs["probe_uid"] = hil_probe_uid
    status = broker.session_start(**kwargs)
    assert status.state == "healthy", f"session_start failed: state={status.state!r}"
    yield broker
    try:
        broker.session_stop(force=True)
    except Exception:
        pass


@pytest.fixture()
def hil_session_with_firmware(
    hil_session: BrokerCore, hil_elf: Path
) -> BrokerCore:
    hil_session.program(artifact=hil_elf, halt_after=True)
    return hil_session


@pytest.fixture()
def hil_socket_server(hil_session: Any) -> Any:
    """Unix socket server wrapping the shared hil_session broker."""
    with tempfile.TemporaryDirectory(dir="/tmp") as td:
        sock_path = str(Path(td) / "hil.sock")
        config = BrokerConfig(socket_path=sock_path)
        srv = _UnixServer(hil_session, config)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        yield srv, sock_path
        srv.shutdown()
        t.join(timeout=2)


@pytest.fixture()
def hil_tcp_server(hil_session: Any) -> Any:
    """TCP server wrapping the shared hil_session broker."""
    token = secrets.token_hex(16)
    config = BrokerConfig(tcp_host="127.0.0.1", tcp_port=0, token=token)
    srv = _TcpServer(hil_session, config, token)
    port: int = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv, port, token
    srv.shutdown()
    t.join(timeout=2)
