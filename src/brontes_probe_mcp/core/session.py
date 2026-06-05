# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from brontes_probe_mcp.core.config import BrokerConfig
from brontes_probe_mcp.core.models import SessionStatus

_PROTOCOL_VERSION = "1.1"
_PROFILE = "default"
_STALE_LOCK_SECONDS: int = 60


class _OperationLock:
    """O_CREAT|O_EXCL file lock — prevents concurrent start/stop races.

    Stale-lock recovery: if the lock file is older than _STALE_LOCK_SECONDS
    (crash left it behind), it is removed and reacquired automatically.
    Use ``session-unlock`` CLI subcommand to force-remove a live lock.
    """

    def __init__(self, lock_path: Path) -> None:
        self._path = lock_path
        self._fd: int | None = None

    def __enter__(self) -> _OperationLock:
        try:
            self._fd = os.open(
                str(self._path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
            )
        except FileExistsError:
            try:
                age = time.time() - self._path.stat().st_mtime
            except FileNotFoundError:
                age = _STALE_LOCK_SECONDS + 1  # race: already gone, retry
            if age > _STALE_LOCK_SECONDS:
                try:
                    self._path.unlink()
                except FileNotFoundError:
                    pass
                try:
                    self._fd = os.open(
                        str(self._path),
                        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                        0o600,
                    )
                except FileExistsError:
                    raise RuntimeError(
                        f"Session operation in progress; lock held at {self._path}"
                    ) from None
            else:
                raise RuntimeError(
                    f"Session operation in progress; lock held at {self._path}"
                ) from None
        return self

    def __exit__(self, *_: object) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass


def _coerce_int(val: object, default: int) -> int:
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        try:
            return int(val)
        except ValueError:
            pass
    return default


def _kill_pgid(pgid: int, sig: int, fallback_pid: int | None = None) -> None:
    """Send signal to process group; fall back to individual PID on error."""
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass
    except PermissionError:
        if fallback_pid is not None:
            try:
                os.kill(fallback_pid, sig)
            except ProcessLookupError:
                pass


class SessionManager:
    def __init__(
        self,
        config: BrokerConfig,
        _popen: Callable[..., subprocess.Popen[bytes]] | None = None,
    ) -> None:
        self._config = config
        self._popen: Callable[..., subprocess.Popen[bytes]] = _popen or subprocess.Popen

    def _log_dir(self) -> Path:
        p = Path(self._config.log_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _meta_path(self, profile: str = _PROFILE) -> Path:
        return self._log_dir() / f"{profile}.json"

    def _lock_path(self) -> Path:
        return self._log_dir() / ".lock.json"

    def _write_meta(self, data: dict[str, Any], profile: str = _PROFILE) -> None:
        self._meta_path(profile).write_text(json.dumps(data))

    def _read_meta(self, profile: str = _PROFILE) -> dict[str, Any] | None:
        try:
            raw = json.loads(self._meta_path(profile).read_text())
            if isinstance(raw, dict):
                return dict(raw)
            return None
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return None

    def _remove_meta(self, profile: str = _PROFILE) -> None:
        try:
            self._meta_path(profile).unlink()
        except FileNotFoundError:
            pass

    def _tcp_ready(self, host: str, port: int, timeout_s: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((host, port), timeout=0.5):
                    return True
            except OSError:
                time.sleep(0.1)
        return False

    def _probe_tcp(self, host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            return False

    def _derive_state(self, meta: dict[str, Any]) -> str:
        pid_raw = meta.get("pid")
        if pid_raw is not None:
            try:
                os.kill(int(pid_raw), 0)
            except ProcessLookupError:
                return "stale"
            except PermissionError:
                pass
        host = str(meta.get("gdb_host") or "127.0.0.1")
        port = _coerce_int(meta.get("gdb_port"), self._config.gdb_port)
        return "healthy" if self._probe_tcp(host, port) else "unhealthy"

    def _stop_meta(self, meta: dict[str, Any], force: bool = False) -> None:
        """Kill the process group recorded in meta."""
        pid_raw = meta.get("pid")
        pgid_raw = meta.get("process_group_id")
        if pid_raw is None:
            return
        pid = int(pid_raw)
        pgid = int(pgid_raw) if pgid_raw is not None else pid
        sig = signal.SIGKILL if force else signal.SIGTERM
        _kill_pgid(pgid, sig, fallback_pid=pid)
        if not force:
            for _ in range(30):
                time.sleep(0.1)
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
            else:
                _kill_pgid(pgid, signal.SIGKILL, fallback_pid=pid)

    def start(self, **profile_kwargs: object) -> SessionStatus:
        target_raw = profile_kwargs.get("target")
        target = str(target_raw) if target_raw is not None else "unknown"
        probe_uid_raw = profile_kwargs.get("probe_uid")
        probe_uid = str(probe_uid_raw) if probe_uid_raw is not None else None
        backend = str(profile_kwargs.get("backend") or self._config.backend)
        gdb_port = _coerce_int(profile_kwargs.get("gdb_port"), self._config.gdb_port)
        pyocd_bin = str(profile_kwargs.get("pyocd_bin") or self._config.pyocd_bin)
        frequency_hz = profile_kwargs.get("frequency_hz")
        pack = profile_kwargs.get("pack")
        extra_raw = profile_kwargs.get("extra_args")
        extra_args = [str(a) for a in extra_raw] if isinstance(extra_raw, list) else []

        with _OperationLock(self._lock_path()):
            # Single-session: implicitly replace any active session
            existing = self._read_meta()
            if existing is not None:
                self._stop_meta(existing)
                self._remove_meta()

            args: list[str] = [
                pyocd_bin,
                "gdbserver",
                "--target",
                target,
                "--port",
                str(gdb_port),
            ]
            if probe_uid:
                args.extend(["--uid", probe_uid])
            if frequency_hz is not None:
                args.extend(["--frequency", str(frequency_hz)])
            if pack is not None:
                args.extend(["--pack", str(pack)])
            args.extend(extra_args)

            log_path = str(self._log_dir() / f"{target}.log")
            with open(log_path, "a") as log_fh:
                proc = self._popen(
                    args,
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )

            try:
                pgid = os.getpgid(proc.pid)
            except OSError:
                pgid = proc.pid

            meta: dict[str, Any] = {
                "backend": backend,
                "pid": proc.pid,
                "process_group_id": pgid,
                "gdb_host": "127.0.0.1",
                "gdb_port": gdb_port,
                "log_path": log_path,
                "started_epoch_s": time.time(),
                "target": target,
                "probe_uid": probe_uid,
            }
            self._write_meta(meta)

            if not self._tcp_ready("127.0.0.1", gdb_port):
                self._stop_meta(meta, force=True)
                self._remove_meta()
                return SessionStatus(
                    protocol_version=_PROTOCOL_VERSION,
                    state="unhealthy",
                    target=target,
                )

        return SessionStatus(
            protocol_version=_PROTOCOL_VERSION,
            image_tag=self._config.image_tag,
            image_digest=self._config.image_digest,
            state="healthy",
            target=target,
            probe_uid=probe_uid,
        )

    def stop(self, force: bool = False) -> SessionStatus:
        with _OperationLock(self._lock_path()):
            meta = self._read_meta()
            if meta is not None:
                self._stop_meta(meta, force=force)
                self._remove_meta()

        return SessionStatus(
            protocol_version=_PROTOCOL_VERSION,
            image_tag=self._config.image_tag,
            image_digest=self._config.image_digest,
            state="stopped",
        )

    def status(self) -> SessionStatus:
        meta = self._read_meta()
        if meta is None:
            return SessionStatus(
                protocol_version=_PROTOCOL_VERSION,
                image_tag=self._config.image_tag,
                image_digest=self._config.image_digest,
                state="stopped",
            )
        target_raw = meta.get("target")
        probe_raw = meta.get("probe_uid")
        return SessionStatus(
            protocol_version=_PROTOCOL_VERSION,
            image_tag=self._config.image_tag,
            image_digest=self._config.image_digest,
            state=self._derive_state(meta),
            target=str(target_raw) if target_raw is not None else None,
            probe_uid=str(probe_raw) if probe_raw is not None else None,
        )
