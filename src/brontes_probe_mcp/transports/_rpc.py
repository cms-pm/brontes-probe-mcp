# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from brontes_probe_mcp.core.broker import SessionRequiredError

if TYPE_CHECKING:
    from brontes_probe_mcp.core.broker import BrokerCore

_VERB_ALIAS: dict[str, str] = {
    "flash": "program",
}

_PATH_KWARGS: dict[str, frozenset[str]] = {
    "program": frozenset({"artifact"}),
    "blackbox_export": frozenset({"out"}),
}


def _to_json_obj(obj: Any) -> Any:
    """Recursively convert Pydantic models to JSON-serialisable objects."""
    if isinstance(obj, BaseModel):
        return _to_json_obj(obj.model_dump(mode="json"))
    if isinstance(obj, dict):
        return {k: _to_json_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_obj(v) for v in obj]
    return obj


def dispatch(broker: BrokerCore, method: str, kwargs: dict[str, Any]) -> Any:
    """Resolve verb alias, coerce Path args, call broker method, return result."""
    kwargs = dict(kwargs)
    resolved = _VERB_ALIAS.get(method, method)

    path_keys = _PATH_KWARGS.get(resolved, frozenset())
    for key in path_keys:
        if key in kwargs and not isinstance(kwargs[key], Path):
            kwargs[key] = Path(str(kwargs[key]))

    fn = getattr(broker, resolved, None)
    if fn is None:
        raise KeyError(f"unknown method {method!r}")

    try:
        result = fn(**kwargs)
    except SessionRequiredError as exc:
        return json.loads(error_response("session_required", str(exc)))

    if resolved == "recent_lines":
        lines = result if isinstance(result, list) else []
        seqs = [
            entry.seq
            for entry in lines
            if hasattr(entry, "seq") and isinstance(entry.seq, int)
        ]
        since_seq: int = int(kwargs.get("since_seq", 0))
        next_seq = max(seqs) + 1 if seqs else since_seq
        return {"lines": _to_json_obj(lines), "next_seq": next_seq}

    return result


def serialize(obj: Any) -> str:
    """JSON-serialize a broker result."""
    return json.dumps(_to_json_obj(obj))


def error_response(
    kind: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> str:
    """Return a JSON error envelope string."""
    payload: dict[str, Any] = {
        "error": {
            "kind": kind,
            "message": message,
            "details": details if details is not None else {},
        }
    }
    return json.dumps(payload)
