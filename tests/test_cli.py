# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import sys

import pytest

from brontes_probe_mcp.cli import main


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["brontes-probe-mcp-cli", "--version"]
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "0.1.0.dev0" in captured.out


def test_config_dump(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["brontes-probe-mcp-cli", "--config-dump"]
    main()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, dict)
    assert "transports" in data
    assert "lanes" in data
    assert "backend" in data


def test_no_args_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["brontes-probe-mcp-cli"]
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
